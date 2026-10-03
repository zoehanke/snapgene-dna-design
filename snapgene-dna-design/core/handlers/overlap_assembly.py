# -*- coding: utf-8 -*-
"""overlap_assembly task handler (v0.9.1-dev2)."""
from __future__ import annotations

import hashlib

from Bio.SeqRecord import SeqRecord

from core.errors import PlanningError, TaskValidationError
from core.evidence_chain import validate_goal_components
from core.handlers.base import TaskHandler, record_slice, product_features, overlap_record
from core.io.input_resolution import resolve_sequence_record
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


class OverlapAssemblyHandler(TaskHandler):
    kind = "overlap_assembly"
    handler_id = "handler-overlap-assembly"
    handler_version = "1.0.0"
    method_maturity = "validated"
    default_topology = "circular"

    def validate_contract(self, task: dict) -> None:
        frags = task.get("operation", {}).get("fragments") or []
        if len(frags) < 2:
            raise TaskValidationError(
                "OVERLAP_FRAGMENTS_REQUIRED",
                "overlap_assembly requires at least 2 fragments in operation.fragments",
                missing_fields=["operation.fragments"],
                questions=["组装片段列表（顺序、来源、区间）是什么？"],
            )
        for i, f in enumerate(frags):
            if not f.get("source_id"):
                raise TaskValidationError(
                    "FRAGMENT_SOURCE_REQUIRED",
                    f"fragment {i} missing source_id",
                    missing_fields=[f"operation.fragments.{i}.source_id"],
                )
            if not f.get("interval_0based"):
                raise TaskValidationError(
                    "OVERLAP_FRAGMENTS_REQUIRED",
                    f"fragment {i} missing interval_0based; whole-file defaults are forbidden",
                    missing_fields=[f"operation.fragments.{i}.interval_0based"],
                )

    def clarify(self, task: dict) -> list[dict]:
        frags = task.get("operation", {}).get("fragments") or []
        if len(frags) < 2:
            return [{
                "field": "operation.fragments",
                "question": "请提供用于重叠组装的片段列表（包含来源 source_id 与各自区间 [start, end)）。",
            }]
        return []

    def plan(self, task: dict) -> dict:
        self.validate_contract(task)
        overlap = int(task.get("operation", {}).get("overlap_length", 0))
        frags_spec = sorted(task["operation"]["fragments"], key=lambda item: int(item.get("order", 0)))
        source_map = {s["source_id"]: s for s in task["sources"]}

        extracted_frags = []
        fragment_records = []
        for spec in frags_spec:
            sid = spec["source_id"]
            if sid not in source_map:
                raise PlanningError("SOURCE_ID_NOT_FOUND", f"source {sid} not in task sources")
            src = source_map[sid]
            rec = resolve_sequence_record(src["_resolved_path"])
            interval = spec["interval_0based"]
            s0, e0 = int(interval[0]), int(interval[1])
            if s0 < 0 or e0 < 0 or s0 > len(rec) or e0 > len(rec) or s0 >= e0:
                raise PlanningError("FRAGMENT_INTERVAL_OUT_OF_RANGE", "fragment interval outside source length")
            strand = int(spec.get("strand", 1))
            seq = extract_interval(rec, s0, e0, topology=src.get("topology", "linear"), strand=strand, whole_record_approved=True)
            if not seq:
                raise PlanningError("FRAGMENT_SEQUENCE_EMPTY", f"fragment {sid} resolved to an empty sequence")
            if len(seq) <= overlap:
                raise PlanningError("OVERLAP_TOO_LONG", f"fragment {sid} length {len(seq)} is not longer than overlap {overlap}")
            fragment_records.append(record_slice(rec, s0, e0, strand))
            extracted_frags.append({
                "source_id": sid,
                "source_sha256": src["sha256"],
                "order": int(spec.get("order", len(extracted_frags))),
                "interval_0based": [s0, e0],
                "strand": strand,
                "sequence": seq,
            })

        circular = (task.get("product", {}).get("topology") == "circular")
        assembled_seq, junctions = _assemble_overlap(extracted_frags, overlap, circular)
        product_record = overlap_record(fragment_records, assembled_seq, overlap, circular)

        expected_components = []
        for i, f in enumerate(extracted_frags):
            expected_components.append({
                "name": f.get("name") or f"fragment_{i+1}",
                "source_id": f["source_id"],
                "source_sha256": f["source_sha256"],
                "interval_0based": f["interval_0based"],
                "strand": f["strand"],
                "transformation": "overlap assembly",
                "expected_sequence": f["sequence"],
            })

        return {
            "task_id": task["task_id"],
            "task_revision": task["revision"],
            "task_kind": self.kind,
            "handler_id": self.handler_id,
            "handler_version": self.handler_version,
            "method_maturity": self.method_maturity,
            "sources": task["sources"],
            "fragments": extracted_frags,
            "overlap_length": overlap,
            "junctions": junctions,
            "product_topology": "circular" if circular else "linear",
            "product_sequence": assembled_seq,
            "product_features": product_features(product_record, assembled_seq),
            "product_sequence_sha256": hashlib.sha256(assembled_seq.encode("utf-8")).hexdigest().upper(),
            "expected_components": expected_components,
            "forbidden_components": list(task.get("product", {}).get("forbidden_components", [])),
            "steps": [
                {
                    "step": "overlap-join",
                    "source_id": f["source_id"],
                    "order": f["order"],
                    "interval_0based": f["interval_0based"],
                    "overlap_length": overlap,
                }
                for f in extracted_frags
            ],
        }


    def recompute(self, task: dict, plan: dict) -> str:
        """Independently recompute assembled overlap sequence from sources and operations."""
        frags = task.get("operation", {}).get("fragments") or []
        overlap = int(task.get("operation", {}).get("overlap_length", 20))
        circular = (task.get("product", {}).get("topology") == "circular")

        sources_by_id = {s["source_id"]: s for s in task.get("sources", [])}
        extracted_frags = []
        for i, f in enumerate(frags):
            src = sources_by_id[f["source_id"]]
            rec = resolve_sequence_record(src["_resolved_path"])
            s0, e0 = f["interval_0based"]
            seq = extract_interval(rec, s0, e0, topology=src.get("topology", "linear"), strand=f.get("strand", 1), whole_record_approved=True)
            extracted_frags.append({"sequence": seq})

        assembled_seq, _ = _assemble_overlap(extracted_frags, overlap, circular)
        return assembled_seq

    def validate_goal(
        self,
        task: dict,
        plan: dict,
        execution: dict,
        product_record: SeqRecord,
        product_seq: str,
    ) -> tuple[bool, list[dict], list[str]]:
        return validate_goal_components(task, plan, execution, product_record)
