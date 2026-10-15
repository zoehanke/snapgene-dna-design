# -*- coding: utf-8 -*-
"""point_mutation task handler (v0.9.1-dev2)."""
from __future__ import annotations

import hashlib

from Bio.SeqRecord import SeqRecord

from core.errors import PlanningError, TaskValidationError
from core.handlers.base import planned_molecule, TaskHandler, product_features
from core.io.input_resolution import resolve_sequence_record
from core.models.construct_model import ConstructModel


class PointMutationHandler(TaskHandler):
    kind = "point_mutation"
    handler_id = "handler-point-mutation"
    handler_version = "1.0.0"
    method_maturity = "validated"
    default_topology = "circular"

    def validate_contract(self, task: dict) -> None:
        mutations = task.get("operation", {}).get("mutations") or []
        if not mutations:
            raise TaskValidationError(
                "MUTATION_SPEC_REQUIRED",
                "point_mutation requires operation.mutations with explicit "
                "position_1based, ref, and alt; default mutation is forbidden",
                missing_fields=["operation.mutations"],
                questions=["待突变位点是什么？（位置、参考碱基、目标碱基）"],
            )
        for m in mutations:
            for field in ("position_1based", "ref", "alt"):
                if field not in m:
                    raise TaskValidationError(
                        "MUTATION_SPEC_INCOMPLETE",
                        f"mutation entry missing {field}",
                        missing_fields=[f"operation.mutations.{field}"],
                    )

    def clarify(self, task: dict) -> list[dict]:
        mutations = task.get("operation", {}).get("mutations") or []
        if not mutations:
            return [{
                "field": "operation.mutations",
                "question": "需要执行的具体点突变是什么？请提供 position_1based, ref, alt（例如 100:A->G）。",
            }]
        return []

    def plan(self, task: dict) -> dict:
        self.validate_contract(task)
        tmpl_source = [s for s in task["sources"] if s["role"] == "template"][0]
        record = resolve_sequence_record(tmpl_source["_resolved_path"])
        seq_chars = list(str(record.seq).upper())
        n = len(seq_chars)

        mutations = task["operation"]["mutations"]
        verified_muts = []
        for m in mutations:
            pos1 = int(m["position_1based"])
            pos0 = pos1 - 1
            if pos0 < 0 or pos0 >= n:
                raise PlanningError("MUTATION_POSITION_OUT_OF_RANGE", f"mutation position {pos1} outside template length {n}")
            ref = str(m["ref"]).upper()
            alt = str(m["alt"]).upper()
            actual_ref = seq_chars[pos0]
            if actual_ref != ref:
                raise PlanningError(
                    "REFERENCE_RESIDUE_MISMATCH",
                    f"reference base at position {pos1} is {actual_ref}, but claimed {ref}",
                )
            seq_chars[pos0] = alt
            verified_muts.append({
                "position_1based": pos1,
                "position_0based": pos0,
                "ref": ref,
                "alt": alt,
            })

        mutated_seq = "".join(seq_chars)
        product_record = ConstructModel(record).mutate(
            [(m["position_0based"], m["alt"]) for m in verified_muts]).to_record()

        return {
            "task_id": task["task_id"],
            "task_revision": task["revision"],
            "task_kind": self.kind,
            "handler_id": self.handler_id,
            "handler_version": self.handler_version,
            "method_maturity": self.method_maturity,
            "sources": [tmpl_source],
            "mutations": verified_muts,
            "product_topology": tmpl_source.get("topology", "circular"),
            "product_sequence": mutated_seq,
            "product_features": product_features(product_record, mutated_seq),
            "product_molecule": planned_molecule(product_record, task).to_dict(),
            "product_sequence_sha256": hashlib.sha256(mutated_seq.encode("utf-8")).hexdigest().upper(),
            "expected_components": [],
            "forbidden_components": list(task.get("product", {}).get("forbidden_components", [])),
            "steps": [
                {
                    "step": "verify-reference-residues",
                    "mutation_count": len(verified_muts),
                },
                {
                    "step": "apply-point-mutations",
                    "mutations": [f"{m['position_1based']}:{m['ref']}->{m['alt']}" for m in verified_muts],
                },
            ],
        }


    def recompute(self, task: dict, plan: dict) -> str:
        """Independently recompute mutated sequence from source and task operations."""
        tmpl_source = [s for s in task["sources"] if s["role"] == "template"][0]
        record = resolve_sequence_record(tmpl_source["_resolved_path"])
        seq_chars = list(str(record.seq).upper())
        n = len(seq_chars)

        for m in task["operation"]["mutations"]:
            pos1 = int(m["position_1based"])
            pos0 = pos1 - 1
            if pos0 < 0 or pos0 >= n:
                raise PlanningError("MUTATION_POSITION_OUT_OF_RANGE", f"mutation position {pos1} outside template length {n}")
            ref = str(m["ref"]).upper()
            alt = str(m["alt"]).upper()
            actual_ref = seq_chars[pos0]
            if actual_ref != ref:
                raise PlanningError("REFERENCE_RESIDUE_MISMATCH", f"reference base at position {pos1} is {actual_ref}, but claimed {ref}")
            seq_chars[pos0] = alt

        return "".join(seq_chars)

    def validate_goal(
        self,
        task: dict,
        plan: dict,
        execution: dict,
        product_record: SeqRecord,
        product_seq: str,
    ) -> tuple[bool, list[dict], list[str]]:
        errors = []
        pseq = str(product_record.seq).upper()
        for m in plan.get("mutations", []):
            pos0 = m["position_0based"]
            alt = m["alt"]
            if pos0 >= len(pseq) or pseq[pos0] != alt:
                errors.append(f"Mutation at {m['position_1based']} expected {alt}, observed {pseq[pos0] if pos0 < len(pseq) else 'out of range'}")
        return (len(errors) == 0), [], errors
