# -*- coding: utf-8 -*-
"""plasmid_replace task handler (v0.9.1-dev2)."""
from __future__ import annotations

import hashlib

from Bio.SeqRecord import SeqRecord

from core.errors import TaskValidationError
from core.evidence_chain import validate_goal_components
from core.handlers.base import TaskHandler, record_slice, replace_record, product_features
from core.io.input_resolution import resolve_sequence_record
from core.interval import extract_interval, validate_interval


class PlasmidReplaceHandler(TaskHandler):
    kind = "plasmid_replace"
    handler_id = "handler-plasmid-replace"
    handler_version = "1.0.0"
    method_maturity = "validated"
    default_topology = "circular"

    def validate_contract(self, task: dict) -> None:
        op = task.get("operation", {}).get("replace") or {}
        if "interval_0based" not in op:
            raise TaskValidationError(
                "REPLACE_INTERVAL_REQUIRED",
                "plasmid_replace requires operation.replace.interval_0based",
                missing_fields=["operation.replace.interval_0based"],
                questions=["待替换区间的 0-based 坐标 [start, end) 是什么？"],
            )
        if not op.get("replacement_source_id"):
            raise TaskValidationError(
                "REPLACEMENT_SOURCE_REQUIRED",
                "plasmid_replace requires operation.replace.replacement_source_id",
                missing_fields=["operation.replace.replacement_source_id"],
                questions=["哪个文件作为替换片段来源？"],
            )

    def clarify(self, task: dict) -> list[dict]:
        questions = []
        op = task.get("operation", {}).get("replace") or {}
        if "interval_0based" not in op:
            questions.append({
                "field": "operation.replace.interval_0based",
                "question": "质粒骨架上待删除/替换的区间 [start, end) 是什么？",
            })
        if not op.get("replacement_source_id"):
            questions.append({
                "field": "operation.replace.replacement_source_id",
                "question": "用于替换的片段来源 ID 是什么？",
            })
        return questions

    def plan(self, task: dict) -> dict:
        self.validate_contract(task)
        bb_source = [s for s in task["sources"] if s["role"] == "backbone"][0]
        bb_rec = resolve_sequence_record(bb_source["_resolved_path"])
        bb_topo = bb_source.get("topology", "circular")
        bb_len = len(bb_rec)

        op = task["operation"]["replace"]
        repl_source = [s for s in task["sources"] if s["source_id"] == op["replacement_source_id"]][0]
        repl_rec = resolve_sequence_record(repl_source["_resolved_path"])

        # Validate replacement interval
        repl_interval = op.get("replacement_interval_0based") or [0, len(repl_rec)]
        r_start0, r_end0 = int(repl_interval[0]), int(repl_interval[1])
        repl_seq = extract_interval(repl_rec, r_start0, r_end0, topology=repl_source.get("topology", "linear"), whole_record_approved=True)

        # Validate backbone replace interval
        rep_interval = op["interval_0based"]
        a, b = int(rep_interval[0]), int(rep_interval[1])
        wraps = bool(op.get("wraps_origin", False))
        s0, e0, is_wrap = validate_interval(a, b, bb_len, topology=bb_topo, wraps_origin=wraps, whole_record_approved=False, task_kind=self.kind)

        bb_seq = str(bb_rec.seq).upper()
        if not is_wrap:
            # Normal deletion from s0 to e0
            product_seq = bb_seq[:s0] + repl_seq.upper() + bb_seq[e0:]
            repl_product_interval = [s0, s0 + len(repl_seq)]
        else:
            # Cross-origin deletion: deletes [s0, bb_len) and [0, e0)
            product_seq = repl_seq.upper() + bb_seq[e0:s0]
            repl_product_interval = [0, len(repl_seq)]

        product_record = replace_record(bb_rec, s0, e0, record_slice(repl_rec, r_start0, r_end0))

        expected_components = [{
            "name": "replacement",
            "source_id": repl_source["source_id"],
            "source_sha256": repl_source["sha256"],
            "interval_0based": [r_start0, r_end0],
            "strand": 1,
            "transformation": "plasmid replacement",
            "expected_sequence": repl_seq,
            "product_interval_0based": repl_product_interval,
        }]

        return {
            "task_id": task["task_id"],
            "task_revision": task["revision"],
            "task_kind": self.kind,
            "handler_id": self.handler_id,
            "handler_version": self.handler_version,
            "method_maturity": self.method_maturity,
            "sources": [bb_source, repl_source],
            "replace_interval_0based": [s0, e0],
            "replacement_interval_0based": [r_start0, r_end0],
            "product_topology": "circular",
            "product_sequence": product_seq,
            "product_features": product_features(product_record, product_seq),
            "product_sequence_sha256": hashlib.sha256(product_seq.encode("utf-8")).hexdigest().upper(),
            "expected_components": expected_components,
            "forbidden_components": list(task.get("product", {}).get("forbidden_components", [])),
            "steps": [
                {
                    "step": "excise-backbone",
                    "source_id": bb_source["source_id"],
                    "interval_0based": [s0, e0],
                },
                {
                    "step": "extract-replacement",
                    "source_id": repl_source["source_id"],
                    "interval_0based": [r_start0, r_end0],
                },
                {
                    "step": "ligate-replace",
                    "product_length": len(product_seq),
                },
            ],
        }


    def recompute(self, task: dict, plan: dict) -> str:
        """Independently recompute replaced plasmid sequence from sources and operations."""
        bb_source = [s for s in task["sources"] if s["role"] == "backbone"][0]
        bb_path = bb_source["_resolved_path"]
        bb_rec = resolve_sequence_record(bb_path)
        bb_seq = str(bb_rec.seq).upper()

        op = task.get("operation", {}).get("replace", {})
        s0, e0 = op["interval_0based"]
        is_wrap = (s0 > e0)

        repl_src_id = op["replacement_source_id"]
        repl_source = [s for s in task["sources"] if s["source_id"] == repl_src_id][0]
        repl_path = repl_source["_resolved_path"]
        repl_rec = resolve_sequence_record(repl_path)

        r_start0, r_end0 = op.get("replacement_interval_0based", [0, len(repl_rec.seq)])
        r_strand = 1
        repl_seq = extract_interval(repl_rec, r_start0, r_end0, topology=repl_source.get("topology", "linear"), strand=r_strand, whole_record_approved=True)

        if not is_wrap:
            return bb_seq[:s0] + repl_seq.upper() + bb_seq[e0:]
        else:
            return repl_seq.upper() + bb_seq[e0:s0]

    def validate_goal(
        self,
        task: dict,
        plan: dict,
        execution: dict,
        product_record: SeqRecord,
        product_seq: str,
    ) -> tuple[bool, list[dict], list[str]]:
        return validate_goal_components(task, plan, execution, product_record)
