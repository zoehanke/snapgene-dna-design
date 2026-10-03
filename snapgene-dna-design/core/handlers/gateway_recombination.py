# -*- coding: utf-8 -*-
"""gateway_recombination task handler (v0.9.1-dev2)."""
from __future__ import annotations

import hashlib

from Bio.SeqRecord import SeqRecord

from core.errors import PlanningError, TaskValidationError
from core.evidence_chain import validate_goal_components
from core.handlers.base import TaskHandler, product_features
from core.io.input_resolution import resolve_sequence_record

from core.models.assembly_model import AssemblyError
from core.tools.recombination import gateway_bp, gateway_lr


class GatewayRecombinationHandler(TaskHandler):
    kind = "gateway_recombination"
    handler_id = "handler-gateway-recombination"
    handler_version = "1.0.0"
    method_maturity = "validated"
    default_topology = "circular"

    def validate_contract(self, task: dict) -> None:
        op = task.get("operation") or {}
        reaction = op.get("reaction")
        if reaction not in ("bp", "lr"):
            raise TaskValidationError(
                "GATEWAY_REACTION_REQUIRED",
                "gateway_recombination requires operation.reaction ('bp' or 'lr')",
                missing_fields=["operation.reaction"],
                questions=["Gateway 重组反应类型是什么（bp 或 lr）？"],
            )
        if op.get("stop_policy") not in ("stop", "no-stop", "require_stop"):
            raise TaskValidationError(
                "GATEWAY_STOP_POLICY_REQUIRED",
                "gateway_recombination requires operation.stop_policy ('stop', 'no-stop', or 'require_stop')",
                missing_fields=["operation.stop_policy"],
                questions=["入门克隆/表达克隆是否需要保留或去除终止密码子（stop/no-stop）？"],
            )
        if reaction == "lr":
            if not op.get("entry_source_id") or not op.get("destination_source_id"):
                raise TaskValidationError(
                    "GATEWAY_LR_SOURCES_REQUIRED",
                    "gateway lr requires operation.entry_source_id and operation.destination_source_id",
                    missing_fields=["operation.entry_source_id", "operation.destination_source_id"],
                )
        else:
            if not op.get("entry_source_id") or not op.get("donor_vector_source_id"):
                raise TaskValidationError(
                    "GATEWAY_BP_SOURCES_REQUIRED",
                    "gateway bp requires operation.entry_source_id (attB insert) and operation.donor_vector_source_id (attP vector)",
                    missing_fields=["operation.entry_source_id", "operation.donor_vector_source_id"],
                )

    def clarify(self, task: dict) -> list[dict]:
        questions = []
        op = task.get("operation") or {}
        if not op.get("reaction"):
            questions.append({
                "field": "operation.reaction",
                "question": "Gateway 重组类型是 BP（生成 Entry clone）还是 LR（生成 Destination 表达克隆）？",
            })
        if not op.get("stop_policy"):
            questions.append({
                "field": "operation.stop_policy",
                "question": "C 端融合或产物终止密码子策略是什么（stop / no-stop）？",
            })
        return questions

    def plan(self, task: dict) -> dict:
        self.validate_contract(task)
        op = task["operation"]
        reaction = op["reaction"]
        source_map = {s["source_id"]: s for s in task["sources"]}

        if reaction == "lr":
            entry_src = source_map[op["entry_source_id"]]
            dest_src = source_map[op["destination_source_id"]]
            entry_rec = resolve_sequence_record(entry_src["_resolved_path"])
            dest_rec = resolve_sequence_record(dest_src["_resolved_path"])

            # Check circular topology for Destination vector
            if dest_rec.annotations.get("topology") == "linear" and dest_src.get("topology") != "circular":
                raise PlanningError("INVALID_TOPOLOGY", "destination vector must be circular for Gateway LR")

            try:
                product_rec, body, notes = gateway_lr(entry_rec, dest_rec)
            except AssemblyError as exc:
                raise PlanningError(exc.code or "GATEWAY_ERROR", str(exc))
            used_sources = [entry_src, dest_src]
        else:
            insert_src = source_map[op["entry_source_id"]]
            donor_src = source_map[op["donor_vector_source_id"]]
            insert_rec = resolve_sequence_record(insert_src["_resolved_path"])
            donor_rec = resolve_sequence_record(donor_src["_resolved_path"])

            try:
                product_rec, body, notes = gateway_bp(donor_rec, insert_rec)
            except AssemblyError as exc:
                raise PlanningError(exc.code or "GATEWAY_ERROR", str(exc))
            used_sources = [insert_src, donor_src]

        product_seq = str(product_rec.seq).upper()

        expected_components = [{
            "name": "gateway_insert",
            "source_id": used_sources[0]["source_id"],
            "source_sha256": used_sources[0]["sha256"],
            "interval_0based": [0, len(product_seq)],
            "strand": 1,
            "transformation": f"Gateway {reaction.upper()} recombination",
            "expected_sequence": product_seq,
            "product_interval_0based": [0, len(product_seq)],
        }]

        return {
            "task_id": task["task_id"],
            "task_revision": task["revision"],
            "task_kind": self.kind,
            "handler_id": self.handler_id,
            "handler_version": self.handler_version,
            "method_maturity": self.method_maturity,
            "sources": used_sources,
            "reaction": reaction,
            "stop_policy": op.get("stop_policy"),
            "product_topology": "circular",
            "product_sequence": product_seq,
            "product_features": product_features(product_rec, product_seq),
            "product_sequence_sha256": hashlib.sha256(product_seq.encode("utf-8")).hexdigest().upper(),
            "expected_components": expected_components,
            "forbidden_components": list(task.get("product", {}).get("forbidden_components", [])),
            "steps": [
                {
                    "step": f"gateway-{reaction}",
                    "entry_source_id": used_sources[0]["source_id"],
                    "vector_source_id": used_sources[1]["source_id"],
                    "product_length": len(product_seq),
                }
            ],
        }


    def recompute(self, task: dict, plan: dict) -> str:
        """Independently recompute gateway product sequence from sources and operations."""
        op = task["operation"]
        reaction = op["reaction"]
        source_map = {s["source_id"]: s for s in task["sources"]}

        if reaction == "lr":
            entry_src = source_map[op["entry_source_id"]]
            dest_src = source_map[op["destination_source_id"]]
            entry_rec = resolve_sequence_record(entry_src["_resolved_path"])
            dest_rec = resolve_sequence_record(dest_src["_resolved_path"])
            product_rec, _, _ = gateway_lr(entry_rec, dest_rec)
        else:
            insert_src = source_map[op["entry_source_id"]]
            donor_src = source_map[op["donor_vector_source_id"]]
            insert_rec = resolve_sequence_record(insert_src["_resolved_path"])
            donor_rec = resolve_sequence_record(donor_src["_resolved_path"])
            product_rec, _, _ = gateway_bp(donor_rec, insert_rec)

        return str(product_rec.seq).upper()

    def validate_goal(
        self,
        task: dict,
        plan: dict,
        execution: dict,
        product_record: SeqRecord,
        product_seq: str,
    ) -> tuple[bool, list[dict], list[str]]:
        return validate_goal_components(task, plan, execution, product_record)
