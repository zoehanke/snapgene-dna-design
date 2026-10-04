# -*- coding: utf-8 -*-
"""component_amplification task handler (v0.9.1-dev2)."""
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.errors import PlanningError, TaskValidationError
from core.evidence_chain import check_backbone_contamination, validate_goal_components
from core.handlers.base import planned_molecule, TaskHandler, record_slice, product_features
from core.io.input_resolution import resolve_sequence_record
from core.interval import extract_interval, validate_interval
from core.tools.feature_ops import get_feature
from core.models.molecule import as_molecule
import copy

if TYPE_CHECKING:
    pass


class ComponentAmplificationHandler(TaskHandler):
    kind = "component_amplification"
    handler_id = "handler-component-amplification"
    handler_version = "1.0.0"
    method_maturity = "validated"
    default_topology = "linear"

    def validate_contract(self, task: dict) -> None:
        if task.get("product", {}).get("topology") != "linear":
            raise TaskValidationError(
                "PRODUCT_TOPOLOGY_MUST_BE_LINEAR",
                "component_amplification produces a linear component",
                missing_fields=["product.topology"],
            )
        tmpl_sources = [s for s in task.get("sources", []) if s.get("role") == "template"]
        if not tmpl_sources:
            raise TaskValidationError(
                "TEMPLATE_SOURCE_REQUIRED",
                "component_amplification requires a source with role=template",
                missing_fields=["sources"],
                questions=["哪个文件是待扩增模板？"],
            )
        selection = (task.get("target") or {}).get("selection") or {}
        if selection.get("resolution_status") != "resolved":
            raise TaskValidationError(
                "COMPONENT_BOUNDARY_REQUIRED",
                "selection must be resolved before execution; whole-record defaults are forbidden",
                missing_fields=["target.selection"],
                questions=["待扩增组件的坐标区间或 feature 名称是什么？"],
            )

    def clarify(self, task: dict) -> list[dict]:
        questions = []
        selection = (task.get("target") or {}).get("selection") or {}
        if not selection or selection.get("resolution_status") != "resolved":
            questions.append({
                "field": "target.selection",
                "question": "待扩增组件的坐标区间（[start, end)）或 feature 名称是什么？",
            })
        return questions

    def plan(self, task: dict) -> dict:
        self.validate_contract(task)
        tmpl = [s for s in task["sources"] if s["role"] == "template"][0]
        record = resolve_sequence_record(tmpl["_resolved_path"])
        topology = tmpl.get("topology", "linear")
        n = len(record)

        selection = task["target"]["selection"]
        whole_record_approved = bool(task.get("approvals", {}).get("whole_record", {}).get("value"))
        strand = int(selection.get("strand") or 1)

        if selection.get("kind") == "interval":
            interval = selection.get("interval_0based") or []
            if len(interval) != 2:
                raise PlanningError("COMPONENT_BOUNDARY_REQUIRED", "interval selection requires [start0, end0)")
            a, b = int(interval[0]), int(interval[1])
            s0, e0, is_wrap = validate_interval(
                a, b, n, topology=topology, wraps_origin=True, whole_record_approved=whole_record_approved, task_kind=self.kind
            )
            extracted = extract_interval(record, s0, e0, topology=topology, wraps_origin=is_wrap, strand=strand, whole_record_approved=whole_record_approved)
            overlapping_features = []
            for f in getattr(record, "features", []):
                if f.type != "source":
                    f_start = min(int(p.start) for p in f.location.parts)
                    f_end = max(int(p.end) for p in f.location.parts)
                    if f_start >= s0 and f_end <= e0:
                        overlapping_features.append({
                            "type": f.type,
                            "start": f_start - s0,
                            "end": f_end - s0,
                            "strand": f.location.strand or 1,
                            "qualifiers": dict(f.qualifiers),
                        })
            sel_dict = {
                "kind": "interval",
                "interval_0based": [s0, e0],
                "strand": strand,
                "wraps_origin": is_wrap,
                "extracted_sequence": extracted,
                "features": overlapping_features,
                "resolution_evidence": selection.get("resolution_evidence", []),
            }
        else:
            # feature resolution
            feat_id = (
                selection.get("feature_id")
                or selection.get("feature_name")
                or selection.get("name")
                or (selection.get("feature") if isinstance(selection.get("feature"), str) else "")
            )
            if not feat_id and isinstance(selection.get("feature"), dict):
                labels = selection.get("feature", {}).get("labels") or []
                if labels:
                    feat_id = labels[0]

            selected = get_feature(record, feat_id)
            selected_record = selected.only_product()
            match = selected.analysis['matches'][0]
            s0,e0 = match['interval_0based']
            if strand == -1 and match['strand'] != -1:
                selected_record = selected_record.reverse_complement(id=True,name=True,description=True,annotations=True,dbxrefs=True)
            extracted = str(selected_record.seq)
            sel_dict = {'kind':'feature','feature_id':feat_id,'feature_name':feat_id,
                        'interval_0based':[s0,e0], 'source_parts':match['source_parts'],
                        'strand':-1 if strand == -1 else match['strand'],
                        'extracted_sequence':extracted, 'feature_type':match['type'],
                        'qualifiers':match['qualifiers'],
                        'resolution_evidence':selection.get('resolution_evidence',[])}

        # Optional homology arms / tails
        op = task.get("operation", {})
        arms = op.get("homology_arms") or {}
        left_tail = arms.get("left_arm") or ""
        right_tail = arms.get("right_arm") or ""

        final_seq = left_tail.upper() + extracted.upper() + right_tail.upper()
        if selection.get("kind") == "interval":
            selected_record = record_slice(record, s0, e0, sel_dict["strand"])
        product_record = SeqRecord(Seq(final_seq),id=selected_record.id,name=selected_record.name,
            description=selected_record.description,annotations=copy.deepcopy(selected_record.annotations),
            dbxrefs=list(selected_record.dbxrefs))
        product_record.features = [f._shift(len(left_tail)) for f in selected_record.features]
        product_record.annotations['topology']='linear'

        expected_components = []
        # Find features inside the extracted interval in template
        for f in record.features:
            if f.type == "source":
                continue
            fs0 = min(int(p.start) for p in f.location.parts)
            fe0 = max(int(p.end) for p in f.location.parts)
            if fs0 >= s0 and fe0 <= e0:
                fseq = str(f.extract(record.seq)).upper()
                for q in ("label", "gene", "product"):
                    val = f.qualifiers.get(q)
                    if val and isinstance(val, list):
                        for name in val:
                            expected_components.append({
                                "name": name,
                                "source_id": tmpl["source_id"],
                                "source_sha256": tmpl["sha256"],
                                "interval_0based": [fs0, fe0],
                                "strand": f.location.strand or 1,
                                "transformation": "amplification feature transfer",
                                "expected_sequence": fseq,
                                "product_interval_0based": [len(left_tail) + (fs0 - s0), len(left_tail) + (fe0 - s0)],
                            })

        if not expected_components:
            expected_components.append({
                "name": task.get("product", {}).get("name") or "amplified_component",
                "source_id": tmpl["source_id"],
                "source_sha256": tmpl["sha256"],
                "interval_0based": sel_dict.get("interval_0based"),
                "strand": sel_dict.get("strand", 1),
                "transformation": "selected component extraction; primer preparation not modeled",
                "expected_sequence": extracted,
                "product_interval_0based": [len(left_tail), len(left_tail) + len(extracted)],
            })

        return {
            "task_id": task["task_id"],
            "task_revision": task["revision"],
            "task_kind": self.kind,
            "handler_id": self.handler_id,
            "handler_version": self.handler_version,
            "method_maturity": self.method_maturity,
            "sources": [tmpl],
            "selection": sel_dict,
            "component_length": len(extracted),
            "product_topology": "linear",
            "product_sequence": final_seq,
            "product_features": product_features(product_record, final_seq),
            "product_molecule": planned_molecule(product_record, task).to_dict(),
            "product_sequence_sha256": hashlib.sha256(final_seq.encode("utf-8")).hexdigest().upper(),
            "expected_components": expected_components,
            "forbidden_components": list(task.get("product", {}).get("forbidden_components", [])),
            "steps": [
                {
                    "step": "extract-component",
                    "source_id": tmpl["source_id"],
                    "interval_0based": sel_dict.get("interval_0based"),
                    "length": len(extracted),
                },
                {
                    "step": "attach-tails",
                    "left_tail_length": len(left_tail),
                    "right_tail_length": len(right_tail),
                    "product_length": len(final_seq),
                },
            ],
        }


    def recompute(self, task: dict, plan: dict) -> str:
        """Independently recompute amplified component sequence from source record and task operations."""
        tmpl = [s for s in task["sources"] if s["role"] == "template"][0]
        record = resolve_sequence_record(tmpl["_resolved_path"])
        topology = tmpl.get("topology", "linear")
        n = len(record)

        selection = task["target"]["selection"]
        whole_record_approved = bool(task.get("approvals", {}).get("whole_record", {}).get("value"))
        strand = int(selection.get("strand") or 1)

        if selection.get("kind") == "interval":
            interval = selection.get("interval_0based") or []
            a, b = int(interval[0]), int(interval[1])
            s0, e0, is_wrap = validate_interval(
                a, b, n, topology=topology, wraps_origin=True, whole_record_approved=whole_record_approved, task_kind=self.kind
            )
            extracted = extract_interval(record, s0, e0, topology=topology, wraps_origin=is_wrap, strand=strand, whole_record_approved=whole_record_approved)
        else:
            feat_id = (
                selection.get("feature_id")
                or selection.get("feature_name")
                or selection.get("name")
                or (selection.get("feature") if isinstance(selection.get("feature"), str) else "")
            )
            if not feat_id and isinstance(selection.get("feature"), dict):
                labels = selection.get("feature", {}).get("labels") or []
                if labels:
                    feat_id = labels[0]
            result = get_feature(record, feat_id)
            extracted_record = result.only_product()
            if strand == -1 and result.analysis['matches'][0]['strand'] != -1:
                extracted_record = extracted_record.reverse_complement()
            extracted = str(extracted_record.seq)

        arms = task.get("operation", {}).get("homology_arms") or {}
        left_arm = str(arms.get("left_arm") or "").upper()
        right_arm = str(arms.get("right_arm") or "").upper()

        return left_arm + extracted.upper() + right_arm

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
