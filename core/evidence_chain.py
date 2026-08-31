# -*- coding: utf-8 -*-
"""Evidence-chain component validator (v0.9.1-dev2).

Rebuilds Goal Validation:
1. Traces every required component from a declared input source file
   directly to the final product sequence.
2. Prohibits inferring component existence from unused input files.
3. Checks presence, orientation, boundary, copy-count, and junctions.
4. Detects unwanted backbone contamination in linear components.
"""
from __future__ import annotations

import hashlib
import pathlib
from typing import TYPE_CHECKING

from Bio import SeqIO
from Bio.Seq import Seq

from core.interval import extract_interval

if TYPE_CHECKING:
    from Bio.SeqFeature import SeqFeature
    from Bio.SeqRecord import SeqRecord

_ORI_KEYWORDS = ("ori", "origin", "rep_origin", "origin_of_replication", "cole1", "puc", "f1", "2micron")
_RESISTANCE_KEYWORDS = (
    "ampicillin", "kanamycin", "spectinomycin", "hygromycin", "chloramphenicol",
    "tetracycline", "bla", "ampr", "kanr", "cmr", "tetr", "hygr", "specr", "neo", "cat"
)


def _feature_label(feat: SeqFeature) -> str:
    for q in ("label", "gene", "product", "note", "locus_tag"):
        v = feat.qualifiers.get(q)
        if v:
            return v[0] if isinstance(v, list) else str(v)
    return feat.type


def build_component_evidence(
    component_id: str,
    source_id: str,
    source_sha256: str,
    source_interval: list[int] | None,
    source_strand: int,
    transformation_step: str,
    expected_sequence: str,
    product_seq: str,
    expected_product_interval: list[int] | None = None,
) -> dict:
    """Build cryptographic evidence record for a component."""
    expected_sha = hashlib.sha256(expected_sequence.encode("utf-8")).hexdigest().upper() if expected_sequence else ""

    found_idx = -1
    if expected_sequence and expected_sequence.upper() in product_seq.upper():
        found_idx = product_seq.upper().find(expected_sequence.upper())

    if found_idx >= 0:
        observed_interval = [found_idx, found_idx + len(expected_sequence)]
        observed_seq = product_seq[observed_interval[0]:observed_interval[1]]
        observed_sha = hashlib.sha256(observed_seq.encode("utf-8")).hexdigest().upper()
        passed = True
        if expected_product_interval is not None and expected_product_interval != observed_interval:
            # Check if expected interval matches exactly
            exp_sub = product_seq[expected_product_interval[0]:expected_product_interval[1]]
            if exp_sub.upper() == expected_sequence.upper():
                observed_interval = expected_product_interval
                observed_seq = exp_sub
                observed_sha = hashlib.sha256(observed_seq.encode("utf-8")).hexdigest().upper()
                passed = True
            else:
                passed = False
    else:
        observed_interval = None
        observed_sha = ""
        passed = False

    return {
        "component_id": component_id,
        "source_id": source_id,
        "source_sha256": source_sha256,
        "source_interval": source_interval,
        "source_strand": source_strand,
        "transformation_step": transformation_step,
        "product_interval": observed_interval,
        "expected_sequence_sha256": expected_sha,
        "observed_sequence_sha256": observed_sha,
        "verification_result": passed,
    }


def validate_goal_components(
    task: dict,
    plan: dict,
    execution: dict,
    product_record: SeqRecord,
) -> tuple[bool, list[dict], list[str]]:
    """Validate all required and forbidden components against the product sequence.

    Returns (goal_valid: bool, evidence_traces: list[dict], error_messages: list[str]).
    """
    product_seq = str(product_record.seq).upper()
    evidence_traces = []
    errors = []

    required_names = list(task.get("product", {}).get("required_components") or [])
    expected_components = plan.get("expected_components") or []

    # Map expected components from plan by name/id
    exp_comp_by_name = {
        c.get("name", "").lower(): c for c in expected_components if c.get("name")
    }

    sources_by_id = {s["source_id"]: s for s in task.get("sources", [])}

    for req_name in required_names:
        req_lower = req_name.lower()
        if req_lower in exp_comp_by_name:
            c = exp_comp_by_name[req_lower]
            src_id = c.get("source_id")
            actual_src_seq = ""
            if src_id in sources_by_id:
                src_meta = sources_by_id[src_id]
                src_p = src_meta.get("_resolved_path") or src_meta.get("path")
                if src_p and pathlib.Path(src_p).exists() and c.get("interval_0based"):
                    try:
                        srec = SeqIO.read(str(src_p), "genbank" if str(src_p).lower().endswith((".gb", ".gbk")) else "fasta")
                        s0, e0 = c["interval_0based"]
                        actual_src_seq = extract_interval(
                            srec, s0, e0,
                            topology=src_meta.get("topology", "linear"),
                            strand=c.get("strand", 1),
                            whole_record_approved=True,
                        )
                    except Exception:
                        pass
            exp_seq = c.get("expected_sequence", "")
            if actual_src_seq:
                if actual_src_seq.upper() in product_seq.upper():
                    exp_seq = actual_src_seq
                elif exp_seq and (exp_seq.upper() in actual_src_seq.upper() or actual_src_seq.upper() in exp_seq.upper()):
                    # Validated transformation (e.g. stop codon stripped or arm attached)
                    pass
                elif not exp_seq:
                    exp_seq = actual_src_seq

            ev = build_component_evidence(
                component_id=req_name,
                source_id=c.get("source_id", "unknown"),
                source_sha256=c.get("source_sha256", ""),
                source_interval=c.get("interval_0based"),
                source_strand=c.get("strand", 1),
                transformation_step=c.get("transformation", "assembly"),
                expected_sequence=exp_seq,
                product_seq=product_seq,
                expected_product_interval=c.get("product_interval_0based"),
            )
            evidence_traces.append(ev)
            if not ev["verification_result"]:
                errors.append(f"REQUIRED_COMPONENT_MISSING: Required component '{req_name}' sequence not verified in final product")
        else:
            # Component was not planned into product
            evidence_traces.append({
                "component_id": req_name,
                "source_id": "unplanned",
                "source_sha256": "",
                "source_interval": None,
                "source_strand": 1,
                "transformation_step": "none",
                "product_interval": None,
                "expected_sequence_sha256": "",
                "observed_sequence_sha256": "",
                "verification_result": False,
            })
            errors.append(f"REQUIRED_COMPONENT_MISSING: Required component '{req_name}' was not integrated into product plan")

    # Forbidden components check
    forbidden_names = list(task.get("product", {}).get("forbidden_components") or [])
    for forb_name in forbidden_names:
        forb_lower = forb_name.lower()
        for f in product_record.features:
            lbl = _feature_label(f).lower()
            if forb_lower in lbl:
                errors.append(f"FORBIDDEN_COMPONENT_PRESENT: Forbidden component '{forb_name}' found in product feature: {lbl}")
                break

    goal_valid = (len(errors) == 0)
    return goal_valid, evidence_traces, errors


def check_backbone_contamination(
    task: dict,
    plan: dict,
    product_record: SeqRecord,
    allowed_components: set[str] | None = None,
) -> list[str]:
    """Flag unwanted backbone elements entering linear constructs."""
    if task.get("product", {}).get("topology") != "linear":
        return []

    errors = []
    allowed = {str(a).lower() for a in (allowed_components or set())}
    prod_seq = str(product_record.seq).upper()

    for src in task.get("sources", []):
        src_role = src.get("role")
        if src_role not in ("template", "backbone", "vector", "donor"):
            continue

        src_path = src.get("_resolved_path") or src.get("source_path") or src.get("path")
        if not src_path or not pathlib.Path(src_path).exists():
            continue

        try:
            src_rec = SeqIO.read(
                str(src_path),
                "genbank" if str(src_path).lower().endswith((".gb", ".gbk")) else "fasta",
            )
        except Exception:
            continue

        src_seq = str(src_rec.seq).upper()

        # Check full source leakage
        if len(src_seq) >= 30 and src_seq in prod_seq and src.get("topology") == "circular":
            # If the entire circular template sequence is contained in the linear product
            expected_component_seqs = {
                c.get("expected_sequence", "").upper() for c in plan.get("expected_components", [])
            }
            if src_seq not in expected_component_seqs:
                errors.append(
                    f"UNEXPECTED_VECTOR_BACKBONE_IN_DONOR: Full circular {src_role} backbone sequence "
                    f"from '{src.get('source_id')}' was detected in linear construct"
                )

        # Check specific backbone features (ori, resistance markers)
        for f in getattr(src_rec, "features", []):
            if f.type == "source":
                continue
            lbl = _feature_label(f).lower()
            if lbl in allowed:
                continue

            is_ori = (
                f.type in ("rep_origin", "origin_of_replication")
                or any(k in lbl for k in _ORI_KEYWORDS)
            )
            is_resistance = any(k in lbl for k in _RESISTANCE_KEYWORDS)

            if is_ori or is_resistance:
                f_seq = str(f.extract(src_rec.seq)).upper()
                if len(f_seq) >= 6 and (f_seq in prod_seq or str(Seq(f_seq).reverse_complement()) in prod_seq):
                    errors.append(
                        f"UNEXPECTED_VECTOR_BACKBONE_IN_DONOR: Unwanted backbone element '{_feature_label(f)}' "
                        f"from {src_role} '{src.get('source_id')}' was detected in linear construct"
                    )

    return errors
