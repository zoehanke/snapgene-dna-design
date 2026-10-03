# -*- coding: utf-8 -*-
"""restriction_ligation task handler (v0.9.1-dev2).

Experimental cloning approximation. Marked method_maturity='experimental'.
"""
from __future__ import annotations

import hashlib

from Bio.SeqRecord import SeqRecord

from core.errors import PlanningError, TaskValidationError
from core.evidence_chain import validate_goal_components
from core.handlers.base import TaskHandler, record_slice, replace_record, product_features
from core.io.input_resolution import resolve_sequence_record
from core.models.construct_model import ConstructModel

from core.models.assembly_model import (
    AssemblyFragment,
    check_sticky_junctions,
    overhang_end,
)
from core.tools.assembly import _hit_end_sequences, digest_ligate
from core.tools.restriction import get_enzyme, restriction_hits


class RestrictionLigationHandler(TaskHandler):
    kind = "restriction_ligation"
    handler_id = "handler-restriction-ligation"
    handler_version = "1.0.0"
    method_maturity = "experimental"
    default_topology = "circular"

    def validate_contract(self, task: dict) -> None:
        op = task.get("operation") or {}
        if not op.get("vector_source_id") or not op.get("insert_source_id"):
            raise TaskValidationError(
                "RESTRICTION_SOURCES_REQUIRED",
                "restriction_ligation requires operation.vector_source_id and operation.insert_source_id",
                missing_fields=["operation.vector_source_id", "operation.insert_source_id"],
            )
        enzymes = op.get("vector_enzymes") or op.get("enzymes") or []
        if not enzymes:
            raise TaskValidationError(
                "RESTRICTION_ENZYMES_REQUIRED",
                "restriction_ligation requires operation.vector_enzymes",
                missing_fields=["operation.vector_enzymes"],
            )
        if task.get("product", {}).get("topology") != "circular":
            raise TaskValidationError(
                "PRODUCT_TOPOLOGY_MUST_BE_CIRCULAR",
                "restriction_ligation produces a circular product",
                missing_fields=["product.topology"],
            )

    def clarify(self, task: dict) -> list[dict]:
        questions = []
        op = task.get("operation") or {}
        if not op.get("vector_source_id") or not op.get("insert_source_id"):
            questions.append({
                "field": "operation",
                "question": "请提供载体骨架与插入片段的来源 ID。",
            })
        if not op.get("vector_enzymes") and not op.get("enzymes"):
            questions.append({
                "field": "operation.vector_enzymes",
                "question": "限制性酶切克隆使用哪种限制酶？",
            })
        return questions

    def plan(self, task: dict) -> dict:
        self.validate_contract(task)
        op = task["operation"]
        source_map = {s["source_id"]: s for s in task["sources"]}
        vec_src = source_map[op["vector_source_id"]]
        ins_src = source_map[op["insert_source_id"]]

        vec_rec = resolve_sequence_record(vec_src["_resolved_path"])
        ins_rec = resolve_sequence_record(ins_src["_resolved_path"])

        enzymes = op.get("vector_enzymes") or op.get("enzymes")
        if isinstance(enzymes, str):
            enzymes = [enzymes]
        insert_enzymes = op.get("insert_enzymes") or enzymes
        if isinstance(insert_enzymes, str):
            insert_enzymes = [insert_enzymes]

        orientation = op.get("orientation", "forward")

        if len(enzymes) == 1 and insert_enzymes == enzymes:
            # Single enzyme digest ligation
            enzyme_name = enzymes[0]
            product_rec, frags, junctions = digest_ligate(vec_rec, ins_rec, enzyme_name)
            product_seq = str(product_rec.seq).upper()
            steps = [
                {
                    "step": "digest-ligate-single-enzyme",
                    "enzyme": enzyme_name,
                    "vector_source_id": vec_src["source_id"],
                    "insert_source_id": ins_src["source_id"],
                    "product_length": len(product_seq),
                }
            ]
        else:
            # Two-enzyme digest ligation
            if len(enzymes) != 2 or len(insert_enzymes) != 2:
                raise PlanningError("RESTRICTION_ENZYME_PAIR_REQUIRED", "two-enzyme ligation requires exactly two enzymes")

            if orientation == "reverse":
                ins_rec = ins_rec.reverse_complement(id=True, name=True, description=True)

            vseq = str(vec_rec.seq).upper()
            iseq = str(ins_rec.seq).upper()

            vector_hits = []
            for enzyme_name in enzymes:
                enzyme = get_enzyme(enzyme_name)
                hits = [h for h in restriction_hits(vseq, enzyme, circular=True) if h["cuts_within_sequence"]]
                if len(hits) != 1:
                    raise PlanningError("RESTRICTION_SITE_COUNT", f"vector enzyme {enzyme_name} must cut exactly once; found {len(hits)}")
                vector_hits.append(hits[0])

            insert_hits = []
            for enzyme_name in insert_enzymes:
                enzyme = get_enzyme(enzyme_name)
                hits = [h for h in restriction_hits(iseq, enzyme, circular=False) if h["cuts_within_sequence"]]
                if len(hits) != 1:
                    raise PlanningError("RESTRICTION_SITE_COUNT", f"insert enzyme {enzyme_name} must cut exactly once; found {len(hits)}")
                insert_hits.append(hits[0])

            n = len(vseq)
            t1 = vector_hits[0]["top_cut_boundary_0based"] % n
            t2 = vector_hits[1]["top_cut_boundary_0based"] % n
            if t1 > t2:
                raise PlanningError("RESTRICTION_WRAP_UNSUPPORTED", "vector cut boundaries wrap the origin; rotate vector before ligation")
            if t1 == t2:
                raise PlanningError("RESTRICTION_ZERO_LENGTH_EXCISION", "vector cut boundaries coincide")

            i1 = insert_hits[0]["top_cut_boundary_0based"] % len(iseq)
            i2 = insert_hits[1]["top_cut_boundary_0based"] % len(iseq)
            if i1 > i2:
                i1, i2 = i2, i1
                insert_hits[0], insert_hits[1] = insert_hits[1], insert_hits[0]
            if i1 == i2:
                raise PlanningError("RESTRICTION_ZERO_LENGTH_EXCISION", "insert cut boundaries coincide")

            ins_frag = iseq[i1:i2]
            backbone = vseq[:t1] + vseq[t2:]
            l_kind, l_ov, _ = _hit_end_sequences(vseq, vector_hits[1])
            r_kind, _, r_ov = _hit_end_sequences(vseq, vector_hits[0])
            backbone_frag = AssemblyFragment(
                "vector", backbone, topology="linear",
                left_end=overhang_end(l_kind, l_ov, 0, source_cut_boundary=t2),
                right_end=overhang_end(r_kind, r_ov, len(backbone), source_cut_boundary=t1),
                source=vec_rec.id,
            )
            il_kind, il_ov, _ = _hit_end_sequences(iseq, insert_hits[0])
            ir_kind, _, ir_ov = _hit_end_sequences(iseq, insert_hits[1])
            insert_frag = AssemblyFragment(
                "insert", ins_frag, topology="linear",
                left_end=overhang_end(il_kind, il_ov, 0, source_cut_boundary=i1),
                right_end=overhang_end(ir_kind, ir_ov, len(ins_frag), source_cut_boundary=i2),
                source=ins_rec.id,
            )
            junctions = check_sticky_junctions([backbone_frag, insert_frag], circular=True)
            if any(j["compatibility"] == "MISMATCH" for j in junctions):
                raise PlanningError("STICKY_END_MISMATCH", "digest-ligation sticky ends are not complementary", details=junctions)

            product_rec = replace_record(vec_rec, t1, t2, record_slice(ins_rec, i1, i2))
            product_rec.annotations["topology"] = "circular"
            product_seq = str(product_rec.seq).upper()
            steps = [
                {
                    "step": "digest-ligate-two-enzyme",
                    "vector_enzymes": enzymes,
                    "insert_enzymes": insert_enzymes,
                    "vector_cuts_0based": [t1, t2],
                    "insert_cuts_0based": [i1, i2],
                    "product_length": len(product_seq),
                }
            ]

        expected_components = [{
            "name": "ligated_insert",
            "source_id": ins_src["source_id"],
            "source_sha256": ins_src["sha256"],
            "interval_0based": [0, len(ins_rec)],
            "strand": 1,
            "transformation": f"Digest-ligation with {','.join(enzymes)}",
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
            "sources": [vec_src, ins_src],
            "enzymes": enzymes,
            "orientation": orientation,
            "product_topology": "circular",
            "product_sequence": product_seq,
            "product_features": product_features(product_rec, product_seq),
            "product_sequence_sha256": hashlib.sha256(product_seq.encode("utf-8")).hexdigest().upper(),
            "expected_components": expected_components,
            "forbidden_components": list(task.get("product", {}).get("forbidden_components", [])),
            "steps": steps,
        }


    def recompute(self, task: dict, plan: dict) -> str:
        """Independently recompute restriction-ligation sequence from sources and operations."""
        op = task.get("operation", {}).get("restriction_ligation") or task.get("operation", {})
        enzymes = op.get("vector_enzymes") or op.get("enzymes")
        if isinstance(enzymes, str):
            enzymes = [enzymes]
        insert_enzymes = op.get("insert_enzymes") or enzymes
        if isinstance(insert_enzymes, str):
            insert_enzymes = [insert_enzymes]

        source_map = {s["source_id"]: s for s in task["sources"]}
        vec_src = source_map.get(op.get("vector_source_id")) or [s for s in task["sources"] if s.get("role") in ("vector", "backbone")][0]
        ins_src = source_map.get(op.get("insert_source_id")) or [s for s in task["sources"] if s.get("role") in ("insert", "template", "donor")][0]

        vec_rec = resolve_sequence_record(vec_src["_resolved_path"])
        ins_rec = resolve_sequence_record(ins_src["_resolved_path"])

        orientation = op.get("orientation", "forward")
        if orientation == "reverse":
            ins_rec = ins_rec.reverse_complement(id=True, name=True, description=True)

        if len(enzymes) == 1 and insert_enzymes == enzymes:
            product_rec, _, _ = digest_ligate(vec_rec, ins_rec, enzymes[0])
            return str(product_rec.seq).upper()
        else:
            vseq = str(vec_rec.seq).upper()
            iseq = str(ins_rec.seq).upper()
            vector_hits = []
            for enzyme_name in enzymes:
                enzyme = get_enzyme(enzyme_name)
                vector_hits.append([h for h in restriction_hits(vseq, enzyme, circular=True) if h["cuts_within_sequence"]][0])
            insert_hits = []
            for enzyme_name in insert_enzymes:
                enzyme = get_enzyme(enzyme_name)
                insert_hits.append([h for h in restriction_hits(iseq, enzyme, circular=False) if h["cuts_within_sequence"]][0])
            n = len(vseq)
            t1 = vector_hits[0]["top_cut_boundary_0based"] % n
            t2 = vector_hits[1]["top_cut_boundary_0based"] % n
            i1 = insert_hits[0]["top_cut_boundary_0based"] % len(iseq)
            i2 = insert_hits[1]["top_cut_boundary_0based"] % len(iseq)
            if i1 > i2:
                i1, i2 = i2, i1
                insert_hits[0], insert_hits[1] = insert_hits[1], insert_hits[0]
            ins_frag = iseq[i1:i2]
            product = ConstructModel(vec_rec).replace(t1, t2, ins_frag)
            return str(product.to_record().seq).upper()

    def validate_goal(
        self,
        task: dict,
        plan: dict,
        execution: dict,
        product_record: SeqRecord,
        product_seq: str,
    ) -> tuple[bool, list[dict], list[str]]:
        return validate_goal_components(task, plan, execution, product_record)
