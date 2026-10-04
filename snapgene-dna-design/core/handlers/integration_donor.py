# -*- coding: utf-8 -*-
"""integration_donor task handler (v0.9.1-dev2)."""
from __future__ import annotations

import hashlib

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.errors import PlanningError, TaskValidationError
from core.evidence_chain import check_backbone_contamination, validate_goal_components
from core.handlers.base import planned_molecule, TaskHandler, record_slice, product_features
from core.io.input_resolution import resolve_sequence_record
from core.interval import extract_interval


class IntegrationDonorHandler(TaskHandler):
    kind = "integration_donor"
    handler_id = "handler-integration-donor"
    handler_version = "1.0.0"
    method_maturity = "validated"
    default_topology = "linear"

    def validate_contract(self, task: dict) -> None:
        if task.get("product", {}).get("topology") != "linear":
            raise TaskValidationError(
                "PRODUCT_TOPOLOGY_MUST_BE_LINEAR",
                "integration_donor produces a linear donor construct",
                missing_fields=["product.topology"],
            )
        arms = task.get("operation", {}).get("homology_arms") or {}
        single_arm_approved = bool(task.get("approvals", {}).get("single_arm_donor", {}).get("value"))
        if not single_arm_approved:
            if not arms.get("left_arm") or not arms.get("right_arm"):
                locus = task.get("operation", {}).get("locus") or {}
                if not (locus.get("source_id") and locus.get("interval_0based") and arms.get("arm_length")):
                    raise TaskValidationError(
                        "INTEGRATION_ARMS_REQUIRED",
                        "integration_donor requires both left_arm and right_arm homology arms by default; single-arm donor requires explicit approval",
                        missing_fields=["operation.homology_arms"],
                        questions=["请提供左右同源臂序列（left_arm / right_arm）或同源臂长度与基因组整合位点。"],
                    )

    def clarify(self, task: dict) -> list[dict]:
        questions = []
        arms = task.get("operation", {}).get("homology_arms") or {}
        if not arms.get("left_arm") or not arms.get("right_arm"):
            questions.append({
                "field": "operation.homology_arms",
                "question": "请提供用于基因组整合的左侧（5'）与右侧（3'）同源臂序列。",
            })
        return questions

    def plan(self, task: dict) -> dict:
        self.validate_contract(task)
        tmpl_source = [s for s in task["sources"] if s["role"] == "template"][0]
        tmpl_rec = resolve_sequence_record(tmpl_source["_resolved_path"])

        selection = task["target"]["selection"]
        interval = selection.get("interval_0based") or [0, len(tmpl_rec)]
        s0, e0 = int(interval[0]), int(interval[1])
        component_seq = extract_interval(tmpl_rec, s0, e0, topology=tmpl_source.get("topology", "linear"), whole_record_approved=True)

        op = task.get("operation", {})
        arms = op.get("homology_arms") or {}
        left = str(arms.get("left_arm") or "")
        right = str(arms.get("right_arm") or "")
        left_record, right_record = SeqRecord(Seq(left.upper())), SeqRecord(Seq(right.upper()))

        locus_spec = op.get("locus") or {}
        if locus_spec.get("source_id"):
            ref_source = next(s for s in task["sources"] if s["source_id"] == locus_spec["source_id"])
            ref = resolve_sequence_record(ref_source["_resolved_path"])
            ref_topo = ref_source.get("topology", "linear")
            la, lb = int(locus_spec["interval_0based"][0]), int(locus_spec["interval_0based"][1])
            if la < 0 or lb < 0 or la > len(ref) or lb > len(ref):
                raise PlanningError("INTEGRATION_LOCUS_OUT_OF_RANGE", "locus interval outside reference length")
            if la > lb:
                raise PlanningError("INTEGRATION_LOCUS_WRAP_UNSUPPORTED", "locus interval must not wrap the reference")

            strand = int(locus_spec.get("strand", 1))
            upstream_length = len(left) if strand == 1 else len(right)
            downstream_length = len(right) if strand == 1 else len(left)
            # Negative-strand biological left/right exchange genomic flanks.
            if ref_topo == "linear":
                if la - upstream_length < 0 or lb + downstream_length > len(ref):
                    raise PlanningError("INTEGRATION_LOCUS_OUT_OF_RANGE", "homology arm flank extends beyond linear chromosome boundary")

            upstream = extract_interval(ref, la - upstream_length, la, topology=ref_topo, whole_record_approved=True) if upstream_length else ""
            downstream = extract_interval(ref, lb, lb + downstream_length, topology=ref_topo, whole_record_approved=True) if downstream_length else ""
            expected_left = upstream if strand == 1 else (str(Seq(downstream).reverse_complement()) if downstream else "")
            expected_right = downstream if strand == 1 else (str(Seq(upstream).reverse_complement()) if upstream else "")

            if left and left.upper() != expected_left.upper():
                raise PlanningError(
                    "INTEGRATION_ARM_MISMATCH",
                    "left homology arm does not match the declared locus flank",
                    details={"expected": expected_left, "given": left},
                )
            if right and right.upper() != expected_right.upper():
                raise PlanningError(
                    "INTEGRATION_ARM_MISMATCH",
                    "right homology arm does not match the declared locus flank",
                    details={"expected": expected_right, "given": right},
                )
            if left:
                left_record = (record_slice(ref, la-len(left), la) if strand == 1
                               else record_slice(ref, lb, lb+len(left), -1))
            if right:
                right_record = (record_slice(ref, lb, lb+len(right)) if strand == 1
                                else record_slice(ref, la-len(right), la, -1))

        donor_seq = left.upper() + component_seq.upper() + right.upper()
        product_record = left_record + record_slice(tmpl_rec, s0, e0) + right_record

        expected_components = [{
            "name": "donor_component",
            "source_id": tmpl_source["source_id"],
            "source_sha256": tmpl_source["sha256"],
            "interval_0based": [s0, e0],
            "strand": 1,
            "transformation": "integration donor assembly",
            "expected_sequence": component_seq,
            "product_interval_0based": [len(left), len(left) + len(component_seq)],
        }]

        # Transfer features from tmpl_rec
        for f in getattr(tmpl_rec, "features", []):
            if f.type == "source":
                continue
            fs0 = min(int(p.start) for p in f.location.parts)
            fe0 = max(int(p.end) for p in f.location.parts)
            if fs0 >= s0 and fe0 <= e0:
                fseq = extract_interval(tmpl_rec, fs0, fe0, topology=tmpl_source.get("topology", "linear"), strand=f.location.strand or 1, whole_record_approved=True)
                for q in ("label", "gene", "product"):
                    val = f.qualifiers.get(q)
                    if val and isinstance(val, list):
                        for name in val:
                            expected_components.append({
                                "name": name,
                                "source_id": tmpl_source["source_id"],
                                "source_sha256": tmpl_source["sha256"],
                                "interval_0based": [fs0, fe0],
                                "strand": f.location.strand or 1,
                                "transformation": "donor component feature",
                                "expected_sequence": fseq,
                                "product_interval_0based": [len(left) + (fs0 - s0), len(left) + (fe0 - s0)],
                            })

        return {
            "task_id": task["task_id"],
            "task_revision": task["revision"],
            "task_kind": self.kind,
            "handler_id": self.handler_id,
            "handler_version": self.handler_version,
            "method_maturity": self.method_maturity,
            "sources": task["sources"],
            "product_topology": "linear",
            "product_sequence": donor_seq,
            "product_features": product_features(product_record, donor_seq),
            "product_molecule": planned_molecule(product_record, task).to_dict(),
            "product_sequence_sha256": hashlib.sha256(donor_seq.encode("utf-8")).hexdigest().upper(),
            "expected_components": expected_components,
            "forbidden_components": list(task.get("product", {}).get("forbidden_components", [])),
            "steps": [
                {
                    "step": "extract-component",
                    "source_id": tmpl_source["source_id"],
                    "interval_0based": [s0, e0],
                    "length": len(component_seq),
                },
                {
                    "step": "attach-homology-arms",
                    "left_arm_length": len(left),
                    "right_arm_length": len(right),
                    "product_length": len(donor_seq),
                },
            ],
        }


    def recompute(self, task: dict, plan: dict) -> str:
        """Independently recompute integration donor sequence from sources and operations."""
        tmpl_source = [s for s in task["sources"] if s["role"] == "template"][0]
        tmpl_rec = resolve_sequence_record(tmpl_source["_resolved_path"])

        selection = task.get("target", {}).get("selection") or {}
        interval = selection.get("interval_0based") or [0, len(tmpl_rec)]
        s0, e0 = int(interval[0]), int(interval[1])
        component_seq = extract_interval(tmpl_rec, s0, e0, topology=tmpl_source.get("topology", "linear"), whole_record_approved=True).upper()

        op = task.get("operation", {}).get("integration") or task.get("operation", {})
        arms = op.get("homology_arms") or {}
        left = str(arms.get("left_arm") or "").upper()
        right = str(arms.get("right_arm") or "").upper()

        return left + component_seq + right

    def validate_goal(
        self,
        task: dict,
        plan: dict,
        execution: dict,
        product_record: SeqRecord,
        product_seq: str,
    ) -> tuple[bool, list[dict], list[str]]:
        goal_ok, traces, errors = validate_goal_components(task, plan, execution, product_record)
        allowed = {c["name"] for c in plan.get("expected_components", [])}
        bb_errors = check_backbone_contamination(task, plan, product_record, allowed_components=allowed)
        errors.extend(bb_errors)
        if bb_errors:
            goal_ok = False
        return goal_ok, traces, errors
