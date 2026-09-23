# -*- coding: utf-8 -*-
"""crispr_editing task handler (v0.9.1-dev2).

Experimental CRISPR planning and editing approximation.
Marked method_maturity='experimental'.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

from Bio.SeqRecord import SeqRecord

from core.errors import PlanningError, TaskValidationError
from core.evidence_chain import validate_goal_components
from core.handlers.base import TaskHandler, record_slice, replace_record, product_features
from core.io.input_resolution import resolve_sequence_record
from core.interval import extract_interval

ROOT = pathlib.Path(__file__).resolve().parents[2]


class CrisprEditingHandler(TaskHandler):
    kind = "crispr_editing"
    handler_id = "handler-crispr-editing"
    handler_version = "1.0.0"
    method_maturity = "experimental"
    default_topology = "linear"

    def validate_contract(self, task: dict) -> None:
        op = task.get("operation") or {}
        if not op.get("nuclease"):
            raise TaskValidationError(
                "CRISPR_NUCLEASE_REQUIRED",
                "crispr_editing requires operation.nuclease",
                missing_fields=["operation.nuclease"],
                questions=["CRISPR 编辑使用哪种核酸酶（如 spcas9-wt）？"],
            )
        if not op.get("target_interval_0based"):
            raise TaskValidationError(
                "CRISPR_TARGET_INTERVAL_REQUIRED",
                "crispr_editing requires operation.target_interval_0based",
                missing_fields=["operation.target_interval_0based"],
                questions=["CRISPR 目标靶点区间 [start, end) 是什么？"],
            )

    def clarify(self, task: dict) -> list[dict]:
        questions = []
        op = task.get("operation") or {}
        if not op.get("nuclease"):
            questions.append({
                "field": "operation.nuclease",
                "question": "CRISPR 编辑使用哪种核酸酶（例如 spcas9-wt）？",
            })
        if not op.get("target_interval_0based"):
            questions.append({
                "field": "operation.target_interval_0based",
                "question": "CRISPR 目标靶点区间 [start, end) 是什么？",
            })
        return questions

    def plan(self, task: dict) -> dict:
        self.validate_contract(task)
        ref_source = next(s for s in task["sources"] if s.get("role") in ("reference", "template", "backbone"))
        ref_rec = resolve_sequence_record(ref_source["_resolved_path"])
        ref_seq = str(ref_rec.seq).upper()
        n = len(ref_seq)

        op = task["operation"]
        nuclease = str(op["nuclease"])

        target_interval = op["target_interval_0based"]
        a, b = int(target_interval[0]), int(target_interval[1])
        if a < 0 or b < 0 or a > n or b > n or a >= b:
            raise PlanningError("CRISPR_TARGET_INTERVAL_INVALID", "target interval must be [a,b) with 0<=a<b<=len")

        # Run guide scan script
        completed = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "-B",
                str(ROOT / "scripts" / "design_guides.py"),
                ref_source["_resolved_path"],
                "--nuclease",
                nuclease,
                "--region",
                str(a),
                str(b),
                "--json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            raise PlanningError("CRISPR_GUIDE_SCAN_FAILED", (completed.stderr or completed.stdout)[-500:])

        try:
            scan = json.loads(completed.stdout)
        except Exception:
            raise PlanningError("CRISPR_GUIDE_SCAN_FAILED", "guide scan returned non-JSON output")

        candidates = scan.get("candidates") or scan.get("guides") or scan.get("data", {}).get("candidates") or []
        if not candidates:
            raise PlanningError("CRISPR_NO_GUIDES_IN_TARGET", "no guide candidates in the target window")

        product_seq = ref_seq
        product_record = ref_rec
        donor = op.get("donor_strategy") or {}
        if donor.get("donor_source_id"):
            dsrc = next(s for s in task["sources"] if s["source_id"] == donor["donor_source_id"])
            drec = resolve_sequence_record(dsrc["_resolved_path"])
            ra, rb = int(donor["replacement_interval_0based"][0]), int(donor["replacement_interval_0based"][1])
            if ra < 0 or rb < 0 or ra > len(drec) or rb > len(drec) or ra >= rb:
                raise PlanningError("CRISPR_DONOR_INTERVAL_INVALID", "donor replacement interval invalid")
            repl = extract_interval(drec, ra, rb, topology=dsrc.get("topology", "linear"), whole_record_approved=True)
            arms = donor.get("homology_arms") or {}
            left = str(arms.get("left_arm") or "")
            right = str(arms.get("right_arm") or "")
            upstream = extract_interval(ref_rec, a - len(left), a, topology=ref_source.get("topology", "linear"), whole_record_approved=True) if left else ""
            downstream = extract_interval(ref_rec, b, b + len(right), topology=ref_source.get("topology", "linear"), whole_record_approved=True) if right else ""
            if left and left.upper() != upstream.upper():
                raise PlanningError("CRISPR_ARM_MISMATCH", "left donor arm does not match reference flank", details={"expected": upstream, "given": left})
            if right and right.upper() != downstream.upper():
                raise PlanningError("CRISPR_ARM_MISMATCH", "right donor arm does not match reference flank", details={"expected": downstream, "given": right})
            product_seq = ref_seq[:a] + repl.upper() + ref_seq[b:]
            product_record = replace_record(ref_rec, a, b, record_slice(drec, ra, rb))

        return {
            "task_id": task["task_id"],
            "task_revision": task["revision"],
            "task_kind": self.kind,
            "handler_id": self.handler_id,
            "handler_version": self.handler_version,
            "method_maturity": self.method_maturity,
            "sources": task["sources"],
            "nuclease": nuclease,
            "guides": candidates[:5],
            "product_topology": ref_source.get("topology", "linear"),
            "product_sequence": product_seq,
            "product_features": product_features(product_record, product_seq),
            "product_sequence_sha256": hashlib.sha256(product_seq.encode("utf-8")).hexdigest().upper(),
            "expected_components": [],
            "forbidden_components": list(task.get("product", {}).get("forbidden_components", [])),
            "steps": [
                {
                    "step": "crispr-guide-scan",
                    "nuclease": nuclease,
                    "target_interval_0based": [a, b],
                    "candidate_count": len(candidates),
                },
                {
                    "step": "simulate-repair",
                    "donor": bool(donor.get("donor_source_id")),
                    "product_length": len(product_seq),
                },
            ],
        }


    def recompute(self, task: dict, plan: dict) -> str:
        """Independently recompute CRISPR edited sequence from sources and operations."""
        ref_source = [s for s in task["sources"] if s["role"] == "reference"][0]
        ref_rec = resolve_sequence_record(ref_source["_resolved_path"])
        ref_seq = str(ref_rec.seq).upper()

        op = task.get("operation", {}).get("crispr") or task.get("operation", {})
        a, b = op["target_interval_0based"]
        donor = op.get("donor_strategy") or op.get("donor") or {}
        if not donor.get("donor_source_id"):
            return ref_seq[:a] + ref_seq[b:]
        else:
            dsrc = [s for s in task["sources"] if s["source_id"] == donor["donor_source_id"]][0]
            drec = resolve_sequence_record(dsrc["_resolved_path"])
            ra, rb = donor.get("replacement_interval_0based", [0, len(drec)])
            repl = extract_interval(drec, ra, rb, topology=dsrc.get("topology", "linear"), whole_record_approved=True)
            return ref_seq[:a] + repl.upper() + ref_seq[b:]

    def validate_goal(
        self,
        task: dict,
        plan: dict,
        execution: dict,
        product_record: SeqRecord,
        product_seq: str,
    ) -> tuple[bool, list[dict], list[str]]:
        return validate_goal_components(task, plan, execution, product_record)
