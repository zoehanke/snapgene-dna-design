# -*- coding: utf-8 -*-
"""Three-layer validation engine (v0.9.1-dev2).

artifact-valid: file syntax, topology, CDS, feature coordinates.
computation-valid: independent re-computation from inputs and transformations.
goal-valid: required and forbidden components, boundaries, junctions, frames.

overall = verified iff artifact-valid AND computation-valid AND goal-valid
AND method_maturity == 'validated'.
If any layer fails, overall is always 'failed'.
"""
from __future__ import annotations

import hashlib
import pathlib

from Bio import SeqIO
from Bio.Seq import Seq

from core.registry import get_task_handler
from core.runtime_execute import compute_execution_sha256
from core.runtime_plan import compute_plan_sha256
from core.task import canonical_json, task_sha256


def _validate_requested_components(task: dict, product_record) -> tuple[list[dict], list[str]]:
    """Check the user's component sequences against the actual file, never the plan."""
    from core.io.input_resolution import resolve_sequence_record
    from Bio.SeqFeature import FeatureLocation

    def names(feature):
        return {str(v).casefold() for key in ("label", "gene", "product", "locus_tag")
                for v in feature.qualifiers.get(key, [])}

    sources = {}
    source_errors = {}
    for source in task.get("sources", []):
        sid = source["source_id"]
        try:
            sources[sid] = resolve_sequence_record(source.get("_resolved_path") or source.get("path") or source.get("filepath"))
        except Exception as exc:
            source_errors[sid] = str(exc)

    product = str(product_record.seq).upper()
    circular = product_record.annotations.get("topology") == "circular"
    traces, errors = [], []
    for forbidden, components in (
        (False, list(task.get("expected_components", [])) + list(task.get("product", {}).get("required_components", []))),
        (True, list(task.get("forbidden_components", [])) + list(task.get("product", {}).get("forbidden_components", []))),
    ):
        for component in components:
            spec = {"name": component} if isinstance(component, str) else component
            name = spec.get("name", "component")
            sequence = spec.get("expected_sequence") or spec.get("sequence")
            candidates = {str(sequence).upper()} if sequence else set()
            sid = spec.get("source_id")
            records = [sources[sid]] if sid in sources else ([] if sid else list(sources.values()))
            if not candidates:
                for record in records:
                    if spec.get("interval_0based") is not None:
                        start, end = spec["interval_0based"]
                        if not 0 <= start < end <= len(record):
                            raise ValueError(f"Invalid component interval for '{name}'")
                        candidates.add(str(FeatureLocation(start, end).extract(record.seq)).upper())
                    else:
                        for feature in record.features:
                            if name.casefold() in names(feature):
                                candidates.add(str(feature.extract(record.seq)).upper())
            labelled = any(name.casefold() in names(f) for f in product_record.features)
            if forbidden and labelled:
                present = True
            elif len(candidates) != 1 or "" in candidates:
                errors.append(f"COMPONENT_UNRESOLVED: '{name}' requires one unambiguous source feature or explicit sequence; source errors: {source_errors}")
                continue
            else:
                needle = next(iter(candidates))
                if any(base not in "ACGT" for base in needle):
                    errors.append(f"COMPONENT_UNRESOLVED: '{name}' contains ambiguous bases")
                    continue
                strand = spec.get("strand")
                if strand not in (None, 1, -1):
                    raise ValueError(f"Invalid component strand for '{name}'")
                reverse = str(Seq(needle).reverse_complement())
                needles = [needle, reverse] if forbidden or strand is None else ([reverse] if strand == -1 else [needle])
                searchable = product + product[:len(needle) - 1] if circular else product
                present = len(needle) <= len(product) and any(n in searchable for n in needles)
            passed = not present if forbidden else present
            traces.append({"check": "forbidden_component" if forbidden else "expected_component", "component": name, "passed": passed})
            if not passed:
                code = "FORBIDDEN_COMPONENT_PRESENT" if forbidden else "REQUIRED_COMPONENT_MISSING"
                errors.append(f"{code}: '{name}' failed the user's component requirement")
    return traces, errors


def compute_validation_sha256(val_dict: dict) -> str:
    """Compute deterministic cryptographic SHA-256 over validation result fields."""
    semantic = {
        "task_id": val_dict.get("task_id"),
        "task_revision": val_dict.get("task_revision"),
        "task_sha256": val_dict.get("task_sha256"),
        "plan_hash": val_dict.get("plan_hash"),
        "execution_sha256": val_dict.get("execution_sha256"),
        "artifact_valid": val_dict.get("artifact_valid"),
        "computation_valid": val_dict.get("computation_valid"),
        "goal_valid": val_dict.get("goal_valid"),
        "overall": val_dict.get("overall"),
        "artifact_hashes": val_dict.get("artifact_hashes", {}),
    }
    return hashlib.sha256(canonical_json(semantic).encode("utf-8")).hexdigest().upper()


def _validate_artifact(execution: dict, plan: dict) -> tuple[bool, SeqIO.SeqRecord | None, list[str]]:
    errors = []
    gb_path = pathlib.Path(execution.get("product_gb", ""))
    fa_path = pathlib.Path(execution.get("product_fasta", ""))

    if not gb_path.exists() or not fa_path.exists():
        return False, None, ["Product files missing on disk"]

    try:
        with gb_path.open(encoding="utf-8") as handle:
            gb_rec = SeqIO.read(handle, "genbank")
        with fa_path.open(encoding="utf-8") as handle:
            fa_rec = SeqIO.read(handle, "fasta")
    except Exception as exc:
        return False, None, [f"Failed to parse product files: {exc}"]

    gb_seq = str(gb_rec.seq).upper()
    fa_seq = str(fa_rec.seq).upper()

    if not gb_seq:
        errors.append("Product sequence in GenBank is empty")
    if gb_seq != fa_seq:
        errors.append(f"GenBank sequence ({len(gb_seq)} bp) does not match FASTA sequence ({len(fa_seq)} bp)")

    exp_topo = plan.get("product_topology", "circular")
    actual_topo = gb_rec.annotations.get("topology", "linear")
    if actual_topo != exp_topo:
        errors.append(f"Topology mismatch: expected {exp_topo}, observed {actual_topo}")

    # Validate CDS translations, frames, and stop codons
    for feat in gb_rec.features:
        if feat.type == "CDS":
            feat_lbl = feat.qualifiers.get("label", feat.qualifiers.get("gene", [feat.type]))[0]
            table_qual = feat.qualifiers.get("transl_table", ["11"])[0]
            try:
                table_id = int(table_qual)
            except ValueError:
                table_id = 11
            try:
                sub_seq = feat.extract(gb_rec.seq)
                if len(sub_seq) == 0:
                    errors.append(f"CDS_EMPTY: CDS '{feat_lbl}' is empty (0 bp)")
                elif len(sub_seq) % 3 != 0:
                    errors.append(f"CDS_FRAME_INVALID: CDS '{feat_lbl}' length ({len(sub_seq)} bp) is not a multiple of 3")
                else:
                    trans = str(sub_seq.translate(table=table_id, to_stop=False))
                    claimed = feat.qualifiers.get("translation", [""])[0]
                    if claimed and claimed.rstrip("*") != trans.rstrip("*"):
                        errors.append(
                            f"CDS_TRANSLATION_MISMATCH: Claimed translation for CDS '{feat_lbl}' "
                            f"does not match computed translation using transl_table={table_id}"
                        )
            except Exception as exc:
                errors.append(f"CDS translation failed: {exc}")

    return (len(errors) == 0), gb_rec, errors


def validate(task: dict, plan: dict, execution: dict) -> dict:
    """Public seam: execute three-layer validation and return ValidationResult."""
    t_sha = task_sha256(task)
    p_sha = compute_plan_sha256(plan)
    e_sha = compute_execution_sha256(execution)

    handler = get_task_handler(task["task_kind"])

    # 1. Artifact Validation
    art_ok, prod_rec, art_errors = _validate_artifact(execution, plan)

    # 2. Computation Validation
    comp_ok = False
    comp_errors = []
    if prod_rec is not None:
        try:
            recomputed = handler.recompute(task, plan).upper()
            observed = str(prod_rec.seq).upper()
            if recomputed == observed:
                comp_ok = True
            else:
                comp_errors.append(f"Recomputed sequence ({len(recomputed)} bp) does not match product ({len(observed)} bp)")
        except Exception as exc:
            comp_errors.append(f"Recomputation failed: {exc}")

    # 3. Goal Validation
    goal_ok = False
    evidence_traces = []
    goal_errors = []
    if prod_rec is not None:
        try:
            goal_ok, evidence_traces, goal_errors = handler.validate_goal(
                task, plan, execution, prod_rec, str(prod_rec.seq).upper()
            )
            if task["task_kind"] != "composite_pipeline" and (task.get("expected_components") or task.get("forbidden_components")):
                traces, errors = _validate_requested_components(task, prod_rec)
                evidence_traces.extend(traces)
                goal_errors.extend(errors)
                goal_ok = goal_ok and not errors
        except Exception as exc:
            goal_errors.append(f"Goal validation failed: {exc}")

    all_errors = art_errors + comp_errors + goal_errors

    # Derive overall status
    if art_ok and comp_ok and goal_ok:
        if handler.method_maturity == "validated":
            overall = "verified"
        else:
            overall = "experimental-preview"
    else:
        overall = "failed"

    error_codes = []
    for e in all_errors:
        if ":" in e and e.split(":", 1)[0].isupper():
            error_codes.append(e.split(":", 1)[0].strip())
        else:
            error_codes.append(e[:50])

    val_res = {
        "task_id": task["task_id"],
        "task_revision": task["revision"],
        "task_sha256": t_sha,
        "plan_hash": p_sha,
        "execution_sha256": e_sha,
        "artifact_valid": art_ok,
        "computation_valid": comp_ok,
        "goal_valid": goal_ok,
        "overall": overall,
        "error_codes": error_codes,
        "errors": all_errors,
        "evidence_traces": evidence_traces,
        "artifact_hashes": execution.get("artifact_hashes", {}),
    }

    val_res["validation_sha256"] = compute_validation_sha256(val_res)
    return val_res
