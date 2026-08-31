# -*- coding: utf-8 -*-
"""hierarchical_assembly task handler (v0.9.1-dev2)."""
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


def _assemble_overlap(fragments: list[dict], overlap: int, circular: bool) -> tuple[str, list[dict]]:
    mismatches = []
    pairs = list(range(len(fragments))) if circular else list(range(len(fragments) - 1))
    for idx in pairs:
        left = fragments[idx]["sequence"][-overlap:]
        right = fragments[(idx + 1) % len(fragments)]["sequence"][:overlap]
        if left.upper() != right.upper():
            mismatches.append({
                "between": f"fragment-{idx} -> fragment-{(idx + 1) % len(fragments)}",
                "left": left,
                "right": right,
            })
    if mismatches:
        raise PlanningError(
            "OVERLAP_MISMATCH",
            "explicit fragment overlaps do not match; refusing to assemble",
            details={"mismatches": mismatches},
        )
    if circular:
        product = "".join(f["sequence"][overlap:] for f in fragments)
    else:
        product = fragments[0]["sequence"] + "".join(f["sequence"][overlap:] for f in fragments[1:])
    junctions = [
        {
            "between": f"fragment-{idx} -> fragment-{(idx + 1) % len(fragments)}",
            "overlap": fragments[idx]["sequence"][-overlap:],
        }
        for idx in pairs
    ]
    return product, junctions


def _string_arc(seq: str, a: int, b: int) -> str:
    n = len(seq)
    a, b = int(a) % n, int(b) % n
    if a <= b:
        return seq[a:b]
    return seq[a:] + seq[:b]


class HierarchicalAssemblyHandler(TaskHandler):
    kind = "hierarchical_assembly"
    handler_id = "handler-hierarchical-assembly"
    handler_version = "1.0.0"
    method_maturity = "validated"
    default_topology = "circular"

    def validate_contract(self, task: dict) -> None:
        stages = task.get("operation", {}).get("stages") or []
        if not stages:
            raise TaskValidationError(
                "HIERARCHICAL_STAGES_REQUIRED",
                "hierarchical_assembly requires operation.stages",
                missing_fields=["operation.stages"],
                questions=["分层组装的各阶段定义（Level 0 / Level 1 / Level 2）是什么？"],
            )
        final_topo = task.get("product", {}).get("topology")
        if final_topo and stages:
            last_stage_topo = stages[-1].get("product_topology")
            if last_stage_topo and last_stage_topo != final_topo:
                raise TaskValidationError(
                    "HIERARCHICAL_FINAL_TOPOLOGY_MISMATCH",
                    f"final stage topology ({last_stage_topo}) does not match product topology ({final_topo})",
                    missing_fields=["product.topology"],
                )

    def clarify(self, task: dict) -> list[dict]:
        questions = []
        stages = task.get("operation", {}).get("stages") or []
        if not stages:
            questions.append({
                "field": "operation.stages",
                "question": "请提供多阶段分层组装的 stages 图定义。",
            })
        return questions

    def plan(self, task: dict) -> dict:
        self.validate_contract(task)
        stages_spec = task["operation"]["stages"]
        source_map = {s["source_id"]: s for s in task["sources"]}

        stage_products = {}
        processed_stages = []

        for st in stages_spec:
            st_id = st.get("stage_id", "unnamed")
            overlap = int(st.get("overlap_length", 0))
            is_circ = (st.get("product_topology") == "circular")
            frags_spec = sorted(st.get("fragments", []), key=lambda item: int(item.get("order", 0)))

            fragments = []
            for f in frags_spec:
                if f.get("source_id"):
                    sid = f["source_id"]
                    if sid not in source_map:
                        raise PlanningError("SOURCE_ID_NOT_FOUND", f"source {sid} not in task sources")
                    src = source_map[sid]
                    rec = SeqIO.read(src["_resolved_path"], "genbank" if src["_resolved_path"].lower().endswith((".gb", ".gbk")) else "fasta")
                    interval = f.get("interval_0based")
                    if interval:
                        s0, e0 = int(interval[0]), int(interval[1])
                        if s0 < 0 or e0 < 0 or s0 > len(rec) or e0 > len(rec):
                            raise PlanningError("FRAGMENT_INTERVAL_OUT_OF_RANGE", f"stage {st_id} fragment interval outside source")
                        seq = extract_interval(rec, s0, e0, topology=src.get("topology", "linear"), strand=int(f.get("strand", 1)), whole_record_approved=True)
                    else:
                        seq = str(rec.seq)
                else:
                    ref_st_id = f.get("stage_id")
                    if not ref_st_id or ref_st_id not in stage_products:
                        raise PlanningError("HIERARCHICAL_STAGE_REFERENCE_MISSING", f"stage {st_id} references unknown stage {ref_st_id}")
                    parent_seq = stage_products[ref_st_id]
                    interval = f.get("interval_0based")
                    if interval:
                        seq = _string_arc(parent_seq, interval[0], interval[1])
                    else:
                        seq = parent_seq

                if int(f.get("strand", 1)) == -1:
                    seq = str(Seq(seq).reverse_complement())

                if not seq:
                    raise PlanningError("FRAGMENT_SEQUENCE_EMPTY", f"stage {st_id} fragment is empty")
                if len(seq) <= overlap:
                    raise PlanningError("OVERLAP_TOO_LONG", f"stage {st_id} fragment length {len(seq)} is not longer than overlap {overlap}")

                fragments.append({
                    "source_id": f.get("source_id") or f"stage:{f.get('stage_id')}",
                    "order": int(f.get("order", 0)),
                    "interval_0based": f.get("interval_0based"),
                    "strand": int(f.get("strand", 1)),
                    "sequence": seq,
                })

            prod_seq, junctions = _assemble_overlap(fragments, overlap, circular=is_circ)
            stage_products[st_id] = prod_seq
            processed_stages.append({
                "stage_id": st_id,
                "fragments": fragments,
                "junctions": junctions,
                "overlap_length": overlap,
                "product_topology": st.get("product_topology", "circular"),
                "product_sequence": prod_seq,
            })

        final_stage = processed_stages[-1]
        final_seq = final_stage["product_sequence"]

        return {
            "task_id": task["task_id"],
            "task_revision": task["revision"],
            "task_kind": self.kind,
            "handler_id": self.handler_id,
            "handler_version": self.handler_version,
            "method_maturity": self.method_maturity,
            "sources": task["sources"],
            "stages": processed_stages,
            "fragments": final_stage["fragments"],
            "overlap_length": final_stage["overlap_length"],
            "junctions": final_stage["junctions"],
            "product_topology": final_stage["product_topology"],
            "product_sequence": final_seq,
            "product_sequence_sha256": hashlib.sha256(final_seq.encode("utf-8")).hexdigest().upper(),
            "expected_components": [],
            "forbidden_components": list(task.get("product", {}).get("forbidden_components", [])),
            "steps": [
                {
                    "step": "hierarchical-stage",
                    "stage_id": s["stage_id"],
                    "fragments": len(s["fragments"]),
                    "product_topology": s["product_topology"],
                    "product_length": len(s["product_sequence"]),
                }
                for s in processed_stages
            ],
        }

    def execute(self, task: dict, plan: dict, out_dir: pathlib.Path) -> dict:
        out_dir.mkdir(parents=True, exist_ok=True)
        seq_str = plan["product_sequence"]
        prod_rec = SeqRecord(
            Seq(seq_str),
            id=task["task_id"],
            name="hierarchical_construct",
            description=f"Hierarchical assembly construct from {task['task_id']}",
        )
        prod_rec.annotations["molecule_type"] = "DNA"
        prod_rec.annotations["topology"] = plan["product_topology"]

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
        """Independently recompute hierarchical assembly sequence from sources and operations."""
        op = task["operation"]
        stages = op["stages"]
        sources_by_id = {s["source_id"]: s for s in task["sources"]}
        stage_products = {}
        final_seq = ""

        for st in stages:
            st_id = st["stage_id"]
            overlap = int(st.get("overlap_length", 20))
            is_circ = (st.get("product_topology") == "circular")
            fragments = []
            for f in st["fragments"]:
                if f.get("source_id"):
                    src = sources_by_id[f["source_id"]]
                    rec = SeqIO.read(src["_resolved_path"], "genbank" if src["_resolved_path"].lower().endswith((".gb", ".gbk")) else "fasta")
                    interval = f.get("interval_0based")
                    if interval:
                        seq = extract_interval(rec, interval[0], interval[1], topology=src.get("topology", "linear"), strand=int(f.get("strand", 1)), whole_record_approved=True)
                    else:
                        seq = str(rec.seq)
                else:
                    ref_st_id = f.get("stage_id")
                    parent_seq = stage_products[ref_st_id]
                    interval = f.get("interval_0based")
                    if interval:
                        seq = _string_arc(parent_seq, interval[0], interval[1])
                    else:
                        seq = parent_seq
                if int(f.get("strand", 1)) == -1:
                    seq = str(Seq(seq).reverse_complement())
                fragments.append({"sequence": seq})

            prod_seq, _ = _assemble_overlap(fragments, overlap, circular=is_circ)
            stage_products[st_id] = prod_seq
            final_seq = prod_seq

        return final_seq

    def validate_goal(
        self,
        task: dict,
        plan: dict,
        execution: dict,
        product_record: SeqRecord,
        product_seq: str,
    ) -> tuple[bool, list[dict], list[str]]:
        return validate_goal_components(task, plan, execution, product_record)
