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
from collections import Counter

from Bio import SeqIO
from Bio.Seq import Seq

from core.registry import get_task_handler
from core.runtime_execute import compute_execution_sha256
from core.runtime_plan import compute_plan_sha256
from core.task import canonical_json, task_sha256
from core.tools.sequence_ops import DNA_IUPAC_ALPHABET, validate_cds_feature


def _validate_requested_components(task: dict, product_record, plan: dict | None = None, source_records=None) -> tuple[list[dict], list[str]]:
    """Check the user's component sequences against the actual file, never the plan."""
    from core.io.input_resolution import resolve_sequence_record
    from Bio.SeqFeature import FeatureLocation
    from core.requirements import validate_component_declarations
    from core.models.molecule import as_molecule
    from core.errors import ValidationError
    validate_component_declarations(task)

    def names(feature):
        values = []
        for key in ("label", "gene", "product", "locus_tag"):
            item = feature.qualifiers.get(key, [])
            values.extend(item if isinstance(item, (list, tuple)) else [item])
        return {str(v).casefold() for v in values}

    sources = dict(source_records or {})
    source_errors = {}
    for source in task.get("sources", []):
        sid = source["source_id"]
        try:
            path=source.get("_resolved_path") or source.get("path") or source.get("filepath")
            if path is None and sid in sources:
                continue
            loaded = resolve_sequence_record(path)
            if sid in sources and as_molecule(sources[sid]).record_version != as_molecule(loaded).record_version:
                raise ValidationError('GOAL_SOURCE_CONFLICT', f'Source id {sid} refers to different original materials')
            sources[sid] = loaded
        except ValidationError:
            raise
        except Exception as exc:
            source_errors[sid] = str(exc)

    product = str(product_record.seq).upper()
    circular = product_record.annotations.get("topology") == "circular"
    traces, errors = [], [f"GOAL_SOURCE_UNAVAILABLE: {sid}" for sid in source_errors]

    def source_candidates(spec, records, name):
        selected = set()
        for record in records:
            if spec.get('interval_0based') is not None:
                start, end = spec['interval_0based']
                if not 0 <= start < end <= len(record):
                    raise ValidationError('COMPONENT_INPUT_INVALID', f"Invalid component interval for '{name}'")
                selected.add(str(FeatureLocation(start, end).extract(record.seq)).upper())
            else:
                selected.update(str(feature.extract(record.seq)).upper() for feature in record.features
                                if name.casefold() in names(feature))
        return selected

    for forbidden, components in (
        (False, list(task.get("expected_components", [])) + list(task.get("product", {}).get("required_components", []))),
        (True, list(task.get("forbidden_components", [])) + list(task.get("product", {}).get("forbidden_components", []))),
    ):
        for component in components:
            spec = {"name": component} if isinstance(component, str) else component
            name = spec.get("name", "component")
            sequence = spec.get("expected_sequence") or spec.get("sequence")
            # Historical product.required_components may name a declared
            # transformed component (e.g. a fusion partner with its stop removed).
            # Explicit top-level sequence/source requirements remain independent.
            if (not forbidden and isinstance(component, str)
                    and component in task.get("product", {}).get("required_components", [])
                    and component not in task.get("expected_components", [])):
                matches = [c for c in (plan or {}).get("expected_components", [])
                           if str(c.get("name", "")).casefold() == name.casefold()]
                if len(matches) == 1:
                    sequence = matches[0].get("expected_sequence")
            candidates = {str(sequence).upper()} if sequence else set()
            sid = spec.get("source_id")
            if sid and sid not in sources:
                errors.append(f"COMPONENT_UNRESOLVED: '{name}' names an unavailable original source {sid}")
                continue
            records = [sources[sid]] if sid in sources else ([] if sid else list(sources.values()))
            if candidates and (sid or spec.get('interval_0based') is not None):
                derived = source_candidates(spec, records, name)
                if len(derived) != 1 or derived != candidates:
                    errors.append(f"COMPONENT_DECLARATION_CONFLICT: '{name}' explicit sequence does not match its source selector")
                    continue
            if not candidates:
                candidates = source_candidates(spec, records, name)
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
            traces.append({"check": "forbidden_component" if forbidden else "expected_component", "component": name,
                           "source_id": sid, "strand": spec.get('strand'), "passed": passed,
                           "scope": "declared sequence presence/absence; copy count and order are not implied"})
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
        "scope_results": val_dict.get('scope_results', {}),
        'requirements':val_dict.get('requirements',{}),
        'goal_coverage':val_dict.get('goal_coverage',{}),
        'task_completion':val_dict.get('task_completion',{}),
    }
    return hashlib.sha256(canonical_json(semantic).encode("utf-8")).hexdigest().upper()


def _validate_artifact(execution: dict, plan: dict) -> tuple[bool, SeqIO.SeqRecord | None, list[str]]:
    errors = []
    gb_path = pathlib.Path(execution.get("product_gb", ""))
    fa_path = pathlib.Path(execution.get("product_fasta", ""))

    if not gb_path.exists() or not fa_path.exists():
        return False, None, ["Product files missing on disk"]

    try:
        from core.models.molecule import as_molecule
        gb_rec = as_molecule(gb_path)
        from core.tools.snapgene_io import normalize_primer_qualifiers
        gb_rec = normalize_primer_qualifiers(gb_rec)
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

    for label, sequence in (("GenBank", gb_seq), ("FASTA", fa_seq)):
        invalid = sorted(set(sequence) - DNA_IUPAC_ALPHABET)
        if invalid:
            errors.append(
                f"{label} product contains non-IUPAC DNA symbol(s): {invalid}"
            )

    exp_topo = plan.get("product_topology", "circular")
    actual_topo = gb_rec.annotations.get("topology", "linear")
    if actual_topo != exp_topo:
        errors.append(f"Topology mismatch: expected {exp_topo}, observed {actual_topo}")

    # Validate CDS translations, frames, and stop codons with the shared CDS
    # contract so malformed metadata cannot fall back to another table/frame.
    for feat in gb_rec.features:
        if feat.type == "CDS":
            audit = validate_cds_feature(feat, gb_rec.seq)
            errors.extend(
                f"{item['code']}: {item['message']}"
                for item in audit["errors"]
            )

    return (len(errors) == 0), gb_rec, errors


def _validate_annotation_retention(task, handler, product_record):
    """Rebuild annotations from task sources, not caller-supplied plan features."""
    from core.io.input_resolution import resolve_sequence_record
    expected_plan = handler.plan(task)
    from core.models.molecule import as_molecule
    expected_record = as_molecule(expected_plan['product_molecule'])
    return compare_retained_annotations(expected_record,product_record), expected_plan


def compare_retained_annotations(expected_record,product_record):
    """Shared comparison; callers must rebuild expected material from original inputs."""
    # Export and read-back infer missing primer sequence fields from actual
    # feature coordinates. Compare both records in that same representation.
    from core.tools.snapgene_io import normalize_primer_qualifiers, _primer_payload_from_feature, _primer_qualifiers
    expected_record = normalize_primer_qualifiers(expected_record)
    product_record = normalize_primer_qualifiers(product_record)
    for record in (expected_record,product_record):
        for feature in record.features:
            if "primer" in feature.type.lower():
                feature.qualifiers.update(_primer_qualifiers(_primer_payload_from_feature(record,feature)))

    def signature(feature):
        identity = {key: feature.qualifiers[key] for key in (
            "label", "gene", "locus_tag", "product", "codon_start", "transl_table",
            "partial", "pseudo", "primer_sequence", "binding_sequence") if key in feature.qualifiers}
        return canonical_json({"type": feature.type, "parts": [
            [str(p.start), str(p.end), p.strand] for p in feature.location.parts],
            "operator": getattr(feature.location, "operator", None), "identity": identity})

    expected = Counter(signature(f) for f in expected_record.features)
    actual = Counter(signature(f) for f in product_record.features)
    if expected - actual:
        return ["ANNOTATION_RETENTION_FAILED: product lost or changed source-derived feature geometry, identity or coding metadata"]
    if dict(product_record.letter_annotations)!=dict(expected_record.letter_annotations):
        return ['MOLECULAR_RETENTION_FAILED: per-base metadata differs from input-derived material']
    if product_record.dbxrefs!=expected_record.dbxrefs:
        return ['MOLECULAR_RETENTION_FAILED: source references differ from input-derived material']
    from core.models.molecule import Molecule
    if isinstance(product_record,Molecule):
        for name in ('strandedness','source_refs'):
            if getattr(product_record,name) != getattr(expected_record,name):
                return [f'MOLECULAR_RETENTION_FAILED: {name} differs from actual input-derived material']
        def ends(material):
            return [end.to_dict() if end else None for end in (material.left_end,material.right_end)]
        if ends(product_record) != ends(expected_record):
            return ['MOLECULAR_RETENTION_FAILED: exposed ends differ from input-derived material']
    return []


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
    source_plan = None
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
        try:
            annotation_errors, source_plan = _validate_annotation_retention(task, handler, prod_rec)
            art_errors.extend(annotation_errors)
            art_ok = art_ok and not annotation_errors
        except Exception as exc:
            art_ok = False
            art_errors.append(f"Annotation recomputation failed: {exc}")

    # 3. Goal Validation
    goal_ok = False
    evidence_traces = []
    goal_errors = []
    if prod_rec is not None:
        try:
            if source_plan is None:
                raise ValueError("Cannot establish goal components from the original task sources")
            goal_ok, evidence_traces, goal_errors = handler.validate_goal(
                task, source_plan, execution, prod_rec, str(prod_rec.seq).upper()
            )
            if task["task_kind"] != "composite_pipeline":
                traces, errors = _validate_requested_components(task, prod_rec, source_plan)
                evidence_traces.extend(traces)
                goal_errors.extend(errors)
                goal_ok = goal_ok and not errors
        except Exception as exc:
            goal_ok = False
            goal_errors.append(f"Goal validation failed: {exc}")

    from core.requirements import task_requirements,check_goal_constraints,goal_coverage,completion_report
    requirements=task_requirements(task)
    request_traces,request_errors,goal_checks=[],[],{}
    if prod_rec is not None:
        from core.task import read_record
        try:
            request_traces,request_errors,goal_checks=check_goal_constraints(requirements,prod_rec,
                {s['source_id']:read_record(s.get('_resolved_path') or s['path']) for s in task['sources']})
        except Exception as exc:
            request_errors=['GOAL_VALIDATION_FAILED: '+str(exc)]
        goal_errors.extend(request_errors)
        evidence_traces.extend(request_traces)
        goal_ok=goal_ok and not request_errors
    coverage=goal_coverage(requirements,request_traces,checks=goal_checks,
                           subject_version=getattr(prod_rec,'record_version',None))
    prior_goal_failure=not goal_ok
    unmapped_goal=any(item['status'] in ('MISSED','UNCHECKED') for item in coverage['goal_items']+coverage['check_results'])
    if unmapped_goal:
        goal_ok=False
        goal_errors.append('GOAL_COVERAGE_INCOMPLETE: recognized requirements lack checked constraints')
    scope_results = {}
    from core.models.molecule import as_molecule
    from core.tools.result import check_result
    if prod_rec is not None:
        material = as_molecule(prod_rec)
        for scope, passed in (('sequence_model',comp_ok),('file',art_ok),('user_goal',goal_ok)):
            scope_results[scope] = check_result(scope,subject=material,
                status='PASSED' if passed else 'FAILED',scope=scope)
        if unmapped_goal and not prior_goal_failure:
            scope_results['user_goal']['status']='INCOMPLETE'
        preparation = (source_plan or {}).get('preparation_check', {})
        scope_results['preparation_model'] = check_result('preparation_model',subject=material,
            status=preparation.get('status','INCOMPLETE'),scope='preparation_model',
            details=preparation.get('details',{'reason':'No actual reaction chain was checked; sequence editing is not preparation'}))
        recorded = [row['execution'] for row in (source_plan or {}).get('steps', []) if 'execution' in row]
        if recorded:
            from core.workflow_validation import _step
            from core.workflow_delivery import preparation_rows, _used_products
            from core.preparation import check_preparation_quality
            steps = [_step(row) for row in recorded]
            used = _used_products(steps, material)
            quality = check_preparation_quality(preparation_rows(steps,material))
            scope_results['preparation_model']['details']['oligo_quality'] = quality
            if quality['status'] in ('FAILED', 'INCOMPLETE'):
                scope_results['preparation_model']['status'] = quality['status']
    required = task.get('validation_requirements', ['sequence_model','file','user_goal'])
    for scope in required:
        if scope_results.get(scope,{}).get('status') != 'PASSED':
            goal_ok = False
            goal_errors.append(f'VALIDATION_SCOPE_UNSATISFIED: required {scope} was not established')
    all_errors = art_errors + comp_errors + goal_errors

    # Derive overall status
    if art_ok and comp_ok and goal_ok and not all_errors:
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
        "scope_results": scope_results,
        'requirements':requirements,'goal_coverage':coverage,
        'task_completion':completion_report(coverage,local_success=overall=='verified',scope_results=scope_results),
    }

    val_res["validation_sha256"] = compute_validation_sha256(val_res)
    return val_res
