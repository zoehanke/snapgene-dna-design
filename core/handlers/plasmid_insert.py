# -*- coding: utf-8 -*-
"""plasmid_insert task handler (v0.9.1-dev2)."""
from __future__ import annotations

import hashlib
import pathlib

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.errors import PlanningError, TaskValidationError
from core.evidence_chain import validate_goal_components
from core.handlers.base import TaskHandler
from core.interval import extract_interval


class PlasmidInsertHandler(TaskHandler):
    kind = "plasmid_insert"
    handler_id = "handler-plasmid-insert"
    handler_version = "1.0.0"
    method_maturity = "validated"
    default_topology = "circular"

    def validate_contract(self, task: dict) -> None:
        insert = task.get("operation", {}).get("insert") or {}
        if "boundary_0based" not in insert:
            raise TaskValidationError(
                "INSERT_BOUNDARY_REQUIRED",
                "plasmid_insert requires operation.insert.boundary_0based",
                missing_fields=["operation.insert.boundary_0based"],
                questions=["插入位点的 0-based 边界位置是什么？"],
            )
        if not insert.get("insert_source_id"):
            raise TaskValidationError(
                "INSERT_SOURCE_REQUIRED",
                "plasmid_insert requires operation.insert.insert_source_id",
                missing_fields=["operation.insert.insert_source_id"],
                questions=["哪个文件作为插入片段来源？"],
            )
        if not insert.get("interval_0based"):
            raise TaskValidationError(
                "INSERT_INTERVAL_REQUIRED",
                "plasmid_insert requires an explicit insert interval; whole-file defaults are forbidden",
                missing_fields=["operation.insert.interval_0based"],
                questions=["插入片段的区间 [start, end) 是什么？"],
            )

    def clarify(self, task: dict) -> list[dict]:
        questions = []
        insert = task.get("operation", {}).get("insert") or {}
        if "boundary_0based" not in insert:
            questions.append({
                "field": "operation.insert.boundary_0based",
                "question": "质粒骨架上的插入边界位置（0-based）是什么？",
            })
        if not insert.get("insert_source_id"):
            questions.append({
                "field": "operation.insert.insert_source_id",
                "question": "插入片段的来源 ID 是什么？",
            })
        if not insert.get("interval_0based"):
            questions.append({
                "field": "operation.insert.interval_0based",
                "question": "插入片段的明确区间 [start, end) 是什么？",
            })
        return questions

    def plan(self, task: dict) -> dict:
        self.validate_contract(task)
        bb_source = [s for s in task["sources"] if s["role"] == "backbone"][0]
        bb_rec = SeqIO.read(bb_source["_resolved_path"], "genbank" if bb_source["_resolved_path"].lower().endswith((".gb", ".gbk")) else "fasta")
        bb_len = len(bb_rec)

        insert_op = task["operation"]["insert"]
        ins_source = [s for s in task["sources"] if s["source_id"] == insert_op["insert_source_id"]][0]
        ins_rec = SeqIO.read(ins_source["_resolved_path"], "genbank" if ins_source["_resolved_path"].lower().endswith((".gb", ".gbk")) else "fasta")

        boundary = int(insert_op["boundary_0based"])
        if boundary < 0 or boundary > bb_len:
            raise PlanningError("INSERT_BOUNDARY_OUT_OF_RANGE", f"insert boundary {boundary} outside backbone length {bb_len}")

        ins_interval = insert_op["interval_0based"]
        i_start0, i_end0 = int(ins_interval[0]), int(ins_interval[1])
        ins_seq = extract_interval(ins_rec, i_start0, i_end0, topology=ins_source.get("topology", "linear"), whole_record_approved=True)

        bb_seq = str(bb_rec.seq).upper()
        product_seq = bb_seq[:boundary] + ins_seq.upper() + bb_seq[boundary:]

        expected_components = []
        # Add features from insert record if any within [i_start0, i_end0)
        for f in getattr(ins_rec, "features", []):
            if f.type == "source":
                continue
            fs0 = min(int(p.start) for p in f.location.parts)
            fe0 = max(int(p.end) for p in f.location.parts)
            if fs0 >= i_start0 and fe0 <= i_end0:
                fseq = extract_interval(ins_rec, fs0, fe0, topology=ins_source.get("topology", "linear"), strand=f.location.strand or 1, whole_record_approved=True)
                for q in ("label", "gene", "product"):
                    val = f.qualifiers.get(q)
                    if val and isinstance(val, list):
                        for name in val:
                            expected_components.append({
                                "name": name,
                                "source_id": ins_source["source_id"],
                                "source_sha256": ins_source["sha256"],
                                "interval_0based": [fs0, fe0],
                                "strand": f.location.strand or 1,
                                "transformation": "insert feature",
                                "expected_sequence": fseq,
                                "product_interval_0based": [boundary + (fs0 - i_start0), boundary + (fe0 - i_start0)],
                            })

        # Add the insert component itself
        expected_components.append({
            "name": "insert",
            "source_id": ins_source["source_id"],
            "source_sha256": ins_source["sha256"],
            "interval_0based": [i_start0, i_end0],
            "strand": 1,
            "transformation": "plasmid insertion",
            "expected_sequence": ins_seq,
            "product_interval_0based": [boundary, boundary + len(ins_seq)],
        })

        return {
            "task_id": task["task_id"],
            "task_revision": task["revision"],
            "task_kind": self.kind,
            "handler_id": self.handler_id,
            "handler_version": self.handler_version,
            "method_maturity": self.method_maturity,
            "sources": [bb_source, ins_source],
            "boundary_0based": boundary,
            "insert_interval_0based": [i_start0, i_end0],
            "product_topology": "circular",
            "product_sequence": product_seq,
            "product_sequence_sha256": hashlib.sha256(product_seq.encode("utf-8")).hexdigest().upper(),
            "expected_components": expected_components,
            "forbidden_components": list(task.get("product", {}).get("forbidden_components", [])),
            "steps": [
                {
                    "step": "locate-insertion-boundary",
                    "source_id": bb_source["source_id"],
                    "boundary_0based": boundary,
                },
                {
                    "step": "extract-insert",
                    "source_id": ins_source["source_id"],
                    "interval_0based": [i_start0, i_end0],
                },
                {
                    "step": "insert-into-backbone",
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
            name="inserted_plasmid",
            description=f"Plasmid insert construct from {task['task_id']}",
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
        """Independently recompute inserted plasmid sequence from sources and operations."""
        bb_source = [s for s in task["sources"] if s["role"] == "backbone"][0]
        bb_path = bb_source["_resolved_path"]
        bb_rec = SeqIO.read(bb_path, "genbank" if bb_path.lower().endswith((".gb", ".gbk")) else "fasta")
        bb_seq = str(bb_rec.seq).upper()

        op = task.get("operation", {}).get("insert", {})
        boundary = int(op["boundary_0based"])

        ins_src_id = op["insert_source_id"]
        ins_source = [s for s in task["sources"] if s["source_id"] == ins_src_id][0]
        ins_path = ins_source["_resolved_path"]
        ins_rec = SeqIO.read(ins_path, "genbank" if ins_path.lower().endswith((".gb", ".gbk")) else "fasta")

        i_start0, i_end0 = op.get("insert_interval_0based", [0, len(ins_rec.seq)])
        i_strand = op.get("insert_strand", 1)
        ins_seq = extract_interval(ins_rec, i_start0, i_end0, topology=ins_source.get("topology", "linear"), strand=i_strand, whole_record_approved=True)

        return bb_seq[:boundary] + ins_seq.upper() + bb_seq[boundary:]

    def validate_goal(
        self,
        task: dict,
        plan: dict,
        execution: dict,
        product_record: SeqRecord,
        product_seq: str,
    ) -> tuple[bool, list[dict], list[str]]:
        return validate_goal_components(task, plan, execution, product_record)
