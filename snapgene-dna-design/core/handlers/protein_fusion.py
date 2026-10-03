# -*- coding: utf-8 -*-
"""protein_fusion task handler (v0.9.1-dev2)."""
from __future__ import annotations

import hashlib

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.errors import PlanningError, TaskValidationError
from core.evidence_chain import validate_goal_components
from core.handlers.base import TaskHandler, record_slice, product_features
from core.io.input_resolution import resolve_sequence_record
from core.interval import extract_interval

_STOP_CODONS = ("TAA", "TAG", "TGA")


class ProteinFusionHandler(TaskHandler):
    kind = "protein_fusion"
    handler_id = "handler-protein-fusion"
    handler_version = "1.0.0"
    method_maturity = "validated"
    default_topology = "linear"

    def validate_contract(self, task: dict) -> None:
        op = task.get("operation") or {}
        for key in ("partner5", "partner3"):
            part = op.get(key)
            if not part or not part.get("source_id"):
                raise TaskValidationError(
                    "FUSION_PARTNERS_REQUIRED",
                    f"protein_fusion requires operation.{key}.source_id",
                    missing_fields=[f"operation.{key}.source_id"],
                    questions=[f"融合蛋白 {key} 的来源文件是什么？"],
                )
            if not part.get("interval_0based"):
                raise TaskValidationError(
                    "FUSION_INTERVAL_REQUIRED",
                    f"protein_fusion requires operation.{key}.interval_0based",
                    missing_fields=[f"operation.{key}.interval_0based"],
                    questions=[f"融合蛋白 {key} 的具体 CDS 区间 [start, end) 是什么？"],
                )
        if op.get("stop_policy") not in ("stop", "no-stop"):
            raise TaskValidationError(
                "FUSION_STOP_POLICY_REQUIRED",
                "protein_fusion requires operation.stop_policy ('stop' or 'no-stop')",
                missing_fields=["operation.stop_policy"],
                questions=["融合产物是否需要保留/添加终止密码子（stop/no-stop）？"],
            )
        linker = op.get("linker") or {}
        if linker.get("dna") is not None and len(str(linker["dna"])) % 3 != 0:
            raise TaskValidationError(
                "FUSION_LINKER_NOT_IN_FRAME",
                "linker DNA length must be a multiple of 3",
                missing_fields=["operation.linker.dna"],
            )

    def clarify(self, task: dict) -> list[dict]:
        questions = []
        op = task.get("operation") or {}
        if not op.get("partner5") or not op.get("partner3"):
            questions.append({
                "field": "operation",
                "question": "请提供 5' 端与 3' 端融合伴侣的来源 ID 与区间 [start, end)。",
            })
        if op.get("stop_policy") not in ("stop", "no-stop"):
            questions.append({
                "field": "operation.stop_policy",
                "question": "融合末端是否保留终止密码子（stop / no-stop）？",
            })
        return questions

    def plan(self, task: dict) -> dict:
        self.validate_contract(task)
        op = task["operation"]
        source_map = {s["source_id"]: s for s in task["sources"]}

        # 5' partner
        p5_spec = op["partner5"]
        s5 = source_map[p5_spec["source_id"]]
        r5 = resolve_sequence_record(s5["_resolved_path"])
        p5_s0, p5_e0 = int(p5_spec["interval_0based"][0]), int(p5_spec["interval_0based"][1])
        if p5_s0 < 0 or p5_e0 < 0 or p5_s0 > len(r5) or p5_e0 > len(r5) or p5_s0 >= p5_e0:
            raise PlanningError("FUSION_PARTNER_INTERVAL_OUT_OF_RANGE", "partner5 interval outside source length")
        p5 = extract_interval(r5, p5_s0, p5_e0, topology=s5.get("topology", "linear"), strand=int(p5_spec.get("strand", 1)), whole_record_approved=True)

        # 3' partner
        p3_spec = op["partner3"]
        s3 = source_map[p3_spec["source_id"]]
        r3 = resolve_sequence_record(s3["_resolved_path"])
        p3_s0, p3_e0 = int(p3_spec["interval_0based"][0]), int(p3_spec["interval_0based"][1])
        if p3_s0 < 0 or p3_e0 < 0 or p3_s0 > len(r3) or p3_e0 > len(r3) or p3_s0 >= p3_e0:
            raise PlanningError("FUSION_PARTNER_INTERVAL_OUT_OF_RANGE", "partner3 interval outside source length")
        p3 = extract_interval(r3, p3_s0, p3_e0, topology=s3.get("topology", "linear"), strand=int(p3_spec.get("strand", 1)), whole_record_approved=True)

        linker_dna = str(op.get("linker", {}).get("dna") or "").upper()
        if len(linker_dna) % 3 != 0:
            raise PlanningError("FUSION_LINKER_NOT_IN_FRAME", "linker DNA length must be a multiple of 3")

        if not p5.upper().startswith("ATG"):
            raise PlanningError("FUSION_PARTNER5_START_MISSING", "partner5 must supply the start codon ATG")

        p5_stripped = p5
        if p5[-3:].upper() in _STOP_CODONS:
            p5_stripped = p5[:-3]

        if len(p5_stripped) % 3 != 0:
            raise PlanningError("FUSION_PARTNER5_NOT_IN_FRAME", "partner5 (after stop removal) is not a multiple of 3 nt")

        # Check internal stop codons in partner5
        for i in range(0, len(p5_stripped), 3):
            codon = p5_stripped[i:i+3].upper()
            if codon in _STOP_CODONS:
                raise PlanningError("FUSION_INTERNAL_STOP", f"partner5 contains internal stop codon {codon} at nt {i}")

        p3_final = p3
        if op["stop_policy"] == "no-stop" and p3[-3:].upper() in _STOP_CODONS:
            p3_final = p3[:-3]

        if op["stop_policy"] == "stop" and p3_final[-3:].upper() not in _STOP_CODONS:
            raise PlanningError("FUSION_STOP_CODON_REQUIRED", "stop_policy=stop requires partner3 to end with a stop codon")

        if not p3_final.upper().startswith("ATG"):
            raise PlanningError("FUSION_PARTNER3_START_MISSING", "partner3 must start with ATG")

        # Check internal stop codons in partner3
        body_p3 = p3_final[:-3] if p3_final[-3:].upper() in _STOP_CODONS else p3_final
        for i in range(0, len(body_p3), 3):
            codon = body_p3[i:i+3].upper()
            if codon in _STOP_CODONS:
                raise PlanningError("FUSION_INTERNAL_STOP", f"partner3 contains internal stop codon {codon} at nt {i}")

        if len(p3_final) % 3 != 0:
            raise PlanningError("FUSION_PARTNER3_NOT_IN_FRAME", "partner3 is not a multiple of 3 nt")

        product = p5_stripped + linker_dna + p3_final
        part5 = record_slice(r5, p5_s0, p5_e0, int(p5_spec.get("strand", 1)))
        part3 = record_slice(r3, p3_s0, p3_e0, int(p3_spec.get("strand", 1)))
        part5 = record_slice(part5, 0, len(p5_stripped))
        part3 = record_slice(part3, 0, len(p3_final))
        product_record = part5 + SeqRecord(Seq(linker_dna)) + part3

        expected_components = [
            {
                "name": "partner5",
                "source_id": s5["source_id"],
                "source_sha256": s5["sha256"],
                "interval_0based": [p5_s0, p5_e0],
                "strand": int(p5_spec.get("strand", 1)),
                "transformation": "in-frame fusion 5' partner",
                "expected_sequence": p5_stripped,
                "product_interval_0based": [0, len(p5_stripped)],
            },
            {
                "name": "partner3",
                "source_id": s3["source_id"],
                "source_sha256": s3["sha256"],
                "interval_0based": [p3_s0, p3_e0],
                "strand": int(p3_spec.get("strand", 1)),
                "transformation": "in-frame fusion 3' partner",
                "expected_sequence": p3_final,
                "product_interval_0based": [len(p5_stripped) + len(linker_dna), len(product)],
            },
        ]

        # Transfer features from partner5 and partner3
        for f in getattr(r5, "features", []):
            if f.type == "source":
                continue
            fs0 = min(int(p.start) for p in f.location.parts)
            fe0 = max(int(p.end) for p in f.location.parts)
            if fs0 >= p5_s0 and fe0 <= p5_e0:
                fseq = extract_interval(r5, fs0, fe0, topology=s5.get("topology", "linear"), strand=f.location.strand or 1, whole_record_approved=True)
                if fe0 == p5_e0 and p5[-3:].upper() in _STOP_CODONS:
                    fseq = fseq[:-3]
                for q in ("label", "gene", "product"):
                    val = f.qualifiers.get(q)
                    if val and isinstance(val, list):
                        for name in val:
                            expected_components.append({
                                "name": name,
                                "source_id": s5["source_id"],
                                "source_sha256": s5["sha256"],
                                "interval_0based": [fs0, fe0],
                                "strand": f.location.strand or 1,
                                "transformation": "fusion partner5 feature",
                                "expected_sequence": fseq,
                                "product_interval_0based": [fs0 - p5_s0, (fe0 - p5_s0) - (3 if fe0 == p5_e0 and p5[-3:].upper() in _STOP_CODONS else 0)],
                            })

        for f in getattr(r3, "features", []):
            if f.type == "source":
                continue
            fs0 = min(int(p.start) for p in f.location.parts)
            fe0 = max(int(p.end) for p in f.location.parts)
            if fs0 >= p3_s0 and fe0 <= p3_e0:
                fseq = extract_interval(r3, fs0, fe0, topology=s3.get("topology", "linear"), strand=f.location.strand or 1, whole_record_approved=True)
                if fe0 == p3_e0 and op["stop_policy"] == "no-stop" and p3[-3:].upper() in _STOP_CODONS:
                    fseq = fseq[:-3]
                offset = len(p5_stripped) + len(linker_dna)
                for q in ("label", "gene", "product"):
                    val = f.qualifiers.get(q)
                    if val and isinstance(val, list):
                        for name in val:
                            expected_components.append({
                                "name": name,
                                "source_id": s3["source_id"],
                                "source_sha256": s3["sha256"],
                                "interval_0based": [fs0, fe0],
                                "strand": f.location.strand or 1,
                                "transformation": "fusion partner3 feature",
                                "expected_sequence": fseq,
                                "product_interval_0based": [offset + (fs0 - p3_s0), offset + (fe0 - p3_s0) - (3 if fe0 == p3_e0 and op["stop_policy"] == "no-stop" and p3[-3:].upper() in _STOP_CODONS else 0)],
                            })

        return {
            "task_id": task["task_id"],
            "task_revision": task["revision"],
            "task_kind": self.kind,
            "handler_id": self.handler_id,
            "handler_version": self.handler_version,
            "method_maturity": self.method_maturity,
            "sources": [s5, s3],
            "product_topology": "linear",
            "product_sequence": product,
            "product_features": product_features(product_record, product),
            "product_sequence_sha256": hashlib.sha256(product.encode("utf-8")).hexdigest().upper(),
            "expected_components": expected_components,
            "forbidden_components": list(task.get("product", {}).get("forbidden_components", [])),
            "steps": [
                {
                    "step": "extract-partner5",
                    "source_id": s5["source_id"],
                    "interval_0based": [p5_s0, p5_e0],
                    "length": len(p5_stripped),
                },
                {
                    "step": "extract-partner3",
                    "source_id": s3["source_id"],
                    "interval_0based": [p3_s0, p3_e0],
                    "length": len(p3_final),
                },
                {
                    "step": "join-fusion",
                    "linker_length": len(linker_dna),
                    "stop_policy": op["stop_policy"],
                    "product_length": len(product),
                },
            ],
        }


    def recompute(self, task: dict, plan: dict) -> str:
        """Independently recompute protein fusion sequence from sources and operations."""
        op = task.get("operation", {}).get("fusion") or task.get("operation", {})
        sources_by_id = {s["source_id"]: s for s in task["sources"]}

        p5_spec = op["partner5"]
        s5 = sources_by_id[p5_spec["source_id"]]
        r5 = resolve_sequence_record(s5["_resolved_path"])
        p5_s0, p5_e0 = p5_spec.get("interval_0based", [0, len(r5.seq)])
        p5 = extract_interval(r5, p5_s0, p5_e0, topology=s5.get("topology", "linear"), strand=int(p5_spec.get("strand", 1)), whole_record_approved=True).upper()
        p5_stripped = p5[:-3] if p5[-3:].upper() in _STOP_CODONS else p5

        p3_spec = op["partner3"]
        s3 = sources_by_id[p3_spec["source_id"]]
        r3 = resolve_sequence_record(s3["_resolved_path"])
        p3_s0, p3_e0 = p3_spec.get("interval_0based", [0, len(r3.seq)])
        p3 = extract_interval(r3, p3_s0, p3_e0, topology=s3.get("topology", "linear"), strand=int(p3_spec.get("strand", 1)), whole_record_approved=True).upper()
        p3_final = p3[:-3] if (op["stop_policy"] == "no-stop" and p3[-3:].upper() in _STOP_CODONS) else p3

        linker = op.get("linker") or {}
        linker_dna = str(op.get("linker_dna") or linker.get("dna") or "").upper()
        return p5_stripped + linker_dna + p3_final

    def validate_goal(
        self,
        task: dict,
        plan: dict,
        execution: dict,
        product_record: SeqRecord,
        product_seq: str,
    ) -> tuple[bool, list[dict], list[str]]:
        return validate_goal_components(task, plan, execution, product_record)
