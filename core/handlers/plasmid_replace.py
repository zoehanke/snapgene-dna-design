# -*- coding: utf-8 -*-
"""plasmid_replace task handler (v0.9.1-dev2)."""
from __future__ import annotations

import hashlib
import pathlib

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.errors import PlanningError, TaskValidationError
from core.evidence_chain import validate_goal_components
from core.handlers.base import TaskHandler
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
        bb_rec = SeqIO.read(bb_source["_resolved_path"], "genbank" if bb_source["_resolved_path"].lower().endswith((".gb", ".gbk")) else "fasta")
        bb_topo = bb_source.get("topology", "circular")
        bb_len = len(bb_rec)

        op = task["operation"]["replace"]
        repl_source = [s for s in task["sources"] if s["source_id"] == op["replacement_source_id"]][0]
        repl_rec = SeqIO.read(repl_source["_resolved_path"], "genbank" if repl_source["_resolved_path"].lower().endswith((".gb", ".gbk")) else "fasta")

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
        for req in task.get("product", {}).get("required_components", []):
            if req.lower() not in {c["name"].lower() for c in expected_components}:
                expected_components.append({
                    "name": req,
                    "source_id": repl_source["source_id"],
                    "source_sha256": repl_source["sha256"],
                    "interval_0based": [r_start0, r_end0],
                    "strand": 1,
                    "transformation": "plasmid replacement",
                    "expected_sequence": repl_seq,
                    "product_interval_0based": repl_product_interval,
                })

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

    def execute(self, task: dict, plan: dict, out_dir: pathlib.Path) -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        seq_str = plan["product_sequence"]
        prod_rec = SeqRecord(
            Seq(seq_str),
            id=task["task_id"],
            name="replaced_plasmid",
            description=f"Plasmid replace construct from {task['task_id']}",
        )
        prod_rec.annotations["molecule_type"] = "DNA"
        prod_rec.annotations["topology"] = "circular"

        gb_path = out_dir / "construct.gb"
        with open(gb_path, "w", encoding="utf-8") as fh:
            SeqIO.write(prod_rec, fh, "genbank")

        fa_path = out_dir / "construct.fasta"
        fa_path.write_text(f">{task['task_id']}\n{seq_str}\n", encoding="utf-8")

        artifact_hashes = {
            "construct.gb": hashlib.sha256(gb_path.read_bytes()).hexdigest().upper(),
            "construct.fasta": hashlib.sha256(fa_path.read_bytes()).hexdigest().upper(),
        }

        return {
            "artifact_class": "intermediate",
            "method_maturity": self.method_maturity,
            "product_gb": str(gb_path),
            "product_fasta": str(fa_path),
            "artifact_hashes": artifact_hashes,
            "product_sequence_sha256": plan["product_sequence_sha256"],
        }

    def recompute(self, task: dict, plan: dict) -> str:
        """Independently recompute replaced plasmid sequence from sources and operations."""
        bb_source = [s for s in task["sources"] if s["role"] == "backbone"][0]
        bb_path = bb_source["_resolved_path"]
        bb_rec = SeqIO.read(bb_path, "genbank" if bb_path.lower().endswith((".gb", ".gbk")) else "fasta")
        bb_seq = str(bb_rec.seq).upper()

        op = task.get("operation", {}).get("replace", {})
        s0, e0 = op["interval_0based"]
        is_wrap = (s0 > e0)

        repl_src_id = op["replacement_source_id"]
        repl_source = [s for s in task["sources"] if s["source_id"] == repl_src_id][0]
        repl_path = repl_source["_resolved_path"]
        repl_rec = SeqIO.read(repl_path, "genbank" if repl_path.lower().endswith((".gb", ".gbk")) else "fasta")

        r_start0, r_end0 = op.get("replacement_interval_0based", [0, len(repl_rec.seq)])
        r_strand = op.get("replacement_strand", 1)
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
