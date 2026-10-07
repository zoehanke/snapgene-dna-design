#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/run_recipe.py - CLI Runner for 7 Standard Laboratory SOP Recipes.

Usage:
    python scripts/run_recipe.py --recipe recipe_gibson_assembly --params-json params.json --out-dir ./build
    python scripts/run_recipe.py --recipe recipe_protein_tagging --params '{"target_cds_seq_or_file": "ATG...", "tag_name_or_seq": "6xHis"}'
    python scripts/run_recipe.py --recipe recipe_gibson_assembly --params-json params.json --out-dir ./build --finalize --confirmed

Outputs:
    Writes candidate artifacts to <out-dir>/candidate/.
    If --finalize and --confirmed are set for a complete plasmid construct,
    validates and promotes artifacts to <out-dir>/authoritative/ with DELIVERY-MANIFEST.json.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import shutil
import sys
from typing import Any

# Ensure project root is on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence_trace.runtime import (observe, observe_value, traced_run, add_trace_arguments, trace_options, TraceStopped)

import core.recipes as recipes
from core.guardrails.checklist import quick_biological_sanity_check
from core.recipes.contract import RecipeResult
from core.tools.snapgene_io import export_plasmid
from core.io.input_resolution import resolve_sequence_record


from core.preparation import write_preparation_artifacts, _check_quikchange_preparation


def get_recipe_function(recipe_name: str):
    clean_name = recipe_name.strip()
    if not clean_name.startswith("recipe_"):
        clean_name = f"recipe_{clean_name}"
    if hasattr(recipes, clean_name):
        return getattr(recipes, clean_name), clean_name
    available = [attr for attr in dir(recipes) if attr.startswith("recipe_")]
    raise ValueError(f"Unknown recipe '{recipe_name}'. Available recipes: {', '.join(available)}")


@traced_run("recipe")
def run_recipe_cli(
    recipe_name: str,
    params: dict[str, Any],
    out_dir: str | pathlib.Path,
    finalize_requested: bool = False,
    user_confirmed: bool = False,
) -> dict[str, Any]:
    fn, canonical_name = get_recipe_function(recipe_name)
    out_path = pathlib.Path(out_dir).resolve()
    candidate_dir = out_path / "candidate"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    result_json_path = candidate_dir / f"{canonical_name}_result.json"
    # Retained candidate files are diagnostics, not this attempt's receipt.
    result_json_path.unlink(missing_ok=True)
    params = dict(params)
    requirements = {key: params.pop(key, []) for key in ("expected_components", "forbidden_components")}
    requirements["sources"] = params.pop("sources", [])
    if any(not isinstance(value, list) for value in requirements.values()):
        raise ValueError("expected_components, forbidden_components and sources must be lists")
    from core.requirements import validate_component_declarations
    validate_component_declarations(requirements)

    # 1. Execute Recipe
    from core.workflow import run_step, recipe_result, _materials
    input_sources={f'input_{index}':material for index,material in enumerate(_materials(params))}
    executed=observe('recipe_execute',run_step,canonical_name,params,step_id='recipe',sources=input_sources)
    if executed.error:
        from core.errors import ToolExecutionError
        raise ToolExecutionError(executed.error['error_code'],executed.error['message'],details=executed.error.get('details'))
    res: RecipeResult = recipe_result(executed.result)

    # 2. Biological Guardrails Check with contextual parameters
    prod_seq = res.product_sequence or res.get("product_dna_sequence") or ""
    topo = res.product_topology or "linear"
    product_record = res.product_record
    if product_record is None and prod_seq:
        raise ValueError('Recipe did not supply its complete molecular product')
    if res.result_kind == "verification" and res.primers:
        from core.tools.snapgene_io import annotate_record_primers
        product_record = annotate_record_primers(product_record, res.primers)

    # Only treat as CDS if explicitly designated or standard coding recipe
    is_cds = False
    if res.result_kind == "component":
        if canonical_name in ("recipe_protein_tagging", "recipe_site_directed_mutagenesis", "recipe_point_mutagenesis"):
            is_cds = True
        elif params.get("is_cds") is not None:
            is_cds = bool(params.get("is_cds"))

    # Extract execution context
    cloning_enz = params.get("enzyme") or params.get("enzymes") or res.details.get("enzyme") or res.details.get("enzymes")
    if canonical_name == "recipe_restriction_cloning":
        cloning_enz = None  # Ordinary cloning retains its flanking sites; the recipe checks actual digests.
    if cloning_enz and isinstance(cloning_enz, str):
        cloning_enz = [cloning_enz]
    grna_seq = params.get("grna_seq") or params.get("target_grna_seq") or res.details.get("grna_seq") or ""
    pr_seqs = [p.get("sequence") or p.get("seq") for p in (res.primers or []) if (p.get("sequence") or p.get("seq"))]
    u6_term = bool(params.get("check_u6_termination"))
    method = str(res.details.get("method") or params.get("method") or
                 ("quikchange" if "mutagenesis" in canonical_name or canonical_name == "recipe_point_mutagenesis" else "pcr"))

    sanity = quick_biological_sanity_check(
        product_record,
        topology=topo,
        is_cds=is_cds,
        cloning_enzymes=cloning_enz,
        crispr_grna_seq=grna_seq,
        primers=pr_seqs if len(pr_seqs) >= 2 else None,
        check_u6_termination=u6_term,
        primer_method=method,
    )

    observe_value("sanity", sanity)

    # 3. Save Candidate Artifacts
    candidate_files = []
    if prod_seq:
        fa_path = candidate_dir / f"{canonical_name}.fasta"
        fa_path.write_text(f">{canonical_name} length={len(prod_seq)} topology={topo}\n{prod_seq}\n", encoding="utf-8")
        candidate_files.append(str(fa_path))

    if prod_seq:
        export_res = export_plasmid(
            record_or_seq=product_record,
            out_dir=candidate_dir,
            filename_base=canonical_name,
            topology=topo,
        )
        candidate_files.append(export_res.analysis["gb_file"])
        candidate_files.append(export_res.analysis["dna_file"])

    preparation_files = observe("preparation", write_preparation_artifacts, res.details.get("preparation", []), out_path)
    if res.details.get("edited_target_record"):
        edited = resolve_sequence_record(res.details["edited_target_record"])
        edited_files = export_plasmid(edited, candidate_dir, "expected_edited_target",
                                     edited.annotations.get("topology", "linear"))
        candidate_files.extend([edited_files.analysis["gb_file"], edited_files.analysis["dna_file"]])
        preparation_files["expected_edited_target"] = edited_files.analysis
    oligos = [(name, res.details.get(name)) for name in ("top_oligo", "bottom_oligo")]
    if any(sequence for _, sequence in oligos):
        oligo_path = out_path / "donor_oligo_order_table.tsv"
        with oligo_path.open("w", encoding="utf-8", errors="replace", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(["name", "sequence_5to3", "length_nt", "method"])
            for name, sequence in oligos:
                if sequence:
                    writer.writerow([name, sequence, len(sequence), "oligo synthesis and annealing"])
        preparation_files["donor_oligo_order_table"] = str(oligo_path)

    result_dict = res.to_dict()
    result_dict["sanity_check"] = sanity
    result_dict["preparation_files"] = preparation_files
    goal_check = {"status": "not_requested", "checks": [], "errors": []}
    if requirements["expected_components"] or requirements["forbidden_components"]:
        from Bio import SeqIO
        from core.runtime_validate import _validate_requested_components
        with (candidate_dir / f"{canonical_name}.gb").open(encoding="utf-8", errors="replace") as handle:
            actual_candidate = SeqIO.read(handle, "genbank")
        traces, errors = _validate_requested_components(requirements, actual_candidate)
        goal_check = {"status": "failed" if errors else "passed", "checks": traces, "errors": errors}
    observe_value("goal_check", goal_check)
    result_dict["goal_check"] = goal_check
    result_json_path.write_text(json.dumps(result_dict, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    candidate_files.append(str(result_json_path))
    observe_value("candidate_files", candidate_files)
    if goal_check["errors"]:
        from core.errors import GateRejected
        raise GateRejected("GATE_GOAL_FAILED", "; ".join(goal_check["errors"]))

    authoritative_delivery = None
    if finalize_requested:
        if not user_confirmed:
            raise PermissionError(
                "Authoritative promotion refused: --finalize requires explicit --confirmed flag from user."
            )
        if not res.is_plasmid_construct():
            raise ValueError(
                f"Authoritative promotion refused: Recipe result '{res.result_kind}' ({res.completeness}) is not a complete plasmid construct."
            )
        if sanity.get('all_applicable_pass') is not True:
            from core.runtime_gate import _guardrail_failure_details
            from core.errors import GateRejected
            raise GateRejected('GATE_GUARDRAILS_FAILED','Annotated candidate failed actual biological checks',
                details={**_guardrail_failure_details(sanity),'candidate_files':candidate_files,'result_json':str(result_json_path)})

        cand_gb = candidate_dir / f"{canonical_name}.gb"
        cand_fa = candidate_dir / f"{canonical_name}.fasta"
        if not cand_gb.exists() or not cand_fa.exists():
            raise FileNotFoundError(f"Candidate files missing for promotion: {cand_gb}, {cand_fa}")

        from core.workflow_delivery import deliver_result
        from core.errors import GateRejected
        try:
            request={**requirements,'topology':topo}
            authoritative_delivery = observe('finalize',deliver_result,request,input_sources,[executed],
                product_record,out_path,primers=[{**p,'role':'preparation'} for p in res.primers],result_kind=res.result_kind,
                sanity_context=sanity['validation_context'])
        except GateRejected as exc:
            exc.details = {**exc.details, "candidate_files": candidate_files,
                           "result_json": str(result_json_path)}
            raise

    return {
        "recipe": canonical_name,
        "result_kind": res.result_kind,
        "completeness": res.completeness,
        "product_length": len(prod_seq) if prod_seq else 0,
        "product_topology": topo,
        "candidate_directory": str(candidate_dir),
        "candidate_files": candidate_files,
        "authoritative_delivery": authoritative_delivery,
        "present_files": authoritative_delivery.get('present_files', []) if authoritative_delivery else [],
        "recipe_result": res,
        "sanity_check": sanity,
        "preparation_files": preparation_files,
        "goal_check": goal_check,
    }


def format_markdown_summary(exec_summary: dict[str, Any]) -> str:
    res: RecipeResult = exec_summary["recipe_result"]
    sanity = exec_summary["sanity_check"]

    lines = []
    lines.append(f"## Recipe Execution: `{exec_summary['recipe']}`")
    lines.append(f"- **Result Kind**: `{exec_summary['result_kind']}` ({exec_summary['completeness']})")
    if exec_summary["product_length"] > 0:
        lines.append(f"- **Product Sequence Length**: {exec_summary['product_length']} bp ({exec_summary['product_topology']})")
    if exec_summary.get("goal_check", {}).get("status") != "not_requested":
        lines.append(f"- **Requested components**: {exec_summary['goal_check']['status']}")

    # Primers Table
    if res.primers:
        lines.append("\n### Designed Primers")
        lines.append("| Name | Sequence (5'->3') | Length | Tm (°C) | Role |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for pr in res.primers:
            seq = pr.get("sequence") or pr.get("seq") or ""
            tm = next((pr[key] for key in ("tm", "tm_celsius", "qc_tm", "binding_core_tm")
                       if pr.get(key) is not None), None)
            tm_text = str(round(float(tm), 1)) if tm is not None else "not provided"
            role = pr.get("role") or pr.get("name", "primer")
            lines.append(f"| `{pr.get('name')}` | `{seq}` | {len(seq)} nt | {tm_text} | {role} |")

    # Biological Guardrails Checklist
    lines.append("\n### Biological Guardrails Status")
    lines.append("| Code | Description | Status | Details |")
    lines.append("| :--- | :--- | :--- | :--- |")
    table = sanity.get("guardrail_status_table", {})
    if isinstance(table, dict):
        for code, info in table.items():
            status = info.get("status", "UNKNOWN")
            icon = "[PASS]" if status == "PASS" else ("[N/A]" if status == "N/A" else f"**[{status}]**")
            lines.append(f"| `{code}` | {info.get('title', '')} | {icon} | {info.get('details', '')} |")
    elif isinstance(table, list):
        for g in table:
            icon = "[PASS]" if g["status"] == "PASS" else ("[N/A]" if g["status"] == "N/A" else f"**[{g['status']}]**")
            lines.append(f"| `{g.get('code')}` | {g.get('name', '')} | {icon} | {g.get('message', '')} |")

    # Protocol Steps
    if res.protocol_steps:
        lines.append("\n### Standard Laboratory Protocol Steps")
        for step in res.protocol_steps:
            lines.append(f"{step.get('step', '-')}. {step.get('action')}")

    # Artifact Locations
    lines.append("\n### Artifact Deliveries")
    lines.append(f"- **Candidate Directory**: `{exec_summary['candidate_directory']}`")
    if exec_summary.get("authoritative_delivery"):
        lines.append(f"- **Authoritative Directory**: `{exec_summary['authoritative_delivery']['directory']}` (hash-bound DELIVERY-MANIFEST.json)")
        for entry in exec_summary['authoritative_delivery'].get('present_files', []):
            lines.append(f"- [{entry['description']}]({entry['path']})")

    return "\n".join(lines)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Run standard molecular biology recipes (Gibson, Restriction Cloning, Golden Gate, Mutagenesis, etc.)."
    )
    parser.add_argument("--recipe", required=True, help="Recipe name (e.g. recipe_gibson_assembly, recipe_restriction_cloning)")
    parser.add_argument("--params-json", help="Path to JSON file with recipe parameters")
    parser.add_argument("--params", help="JSON string of recipe parameters")
    parser.add_argument("--out-dir", default="./output", help="Output directory (default: ./output)")
    parser.add_argument("--finalize", action="store_true", help="Promote verified construct to authoritative directory")
    parser.add_argument("--confirmed", action="store_true", help="Explicit user confirmation for authoritative release")
    parser.add_argument("--json", action="store_true", help="Output complete report in JSON format")

    add_trace_arguments(parser)
    args = parser.parse_args()

    try:
        params = {}
        if args.params_json:
            params = json.loads(pathlib.Path(args.params_json).read_text(encoding="utf-8"))
        elif args.params:
            p_path = pathlib.Path(args.params)
            if p_path.is_file():
                params = json.loads(p_path.read_text(encoding="utf-8"))
            else:
                try:
                    params = json.loads(args.params)
                except Exception:
                    import ast
                    params = ast.literal_eval(args.params)
        summary = run_recipe_cli(
            recipe_name=args.recipe,
            params=params,
            out_dir=args.out_dir,
            finalize_requested=args.finalize,
            user_confirmed=args.confirmed,
            **trace_options(args),
        )
        if args.json:
            out_data = {
                "recipe": summary["recipe"],
                "result_kind": summary["result_kind"],
                "completeness": summary["completeness"],
                "product_length": summary["product_length"],
                "product_topology": summary["product_topology"],
                "candidate_directory": summary["candidate_directory"],
                "candidate_files": summary["candidate_files"],
                "authoritative_delivery": summary["authoritative_delivery"],
                "recipe_result": summary["recipe_result"].to_dict(),
                "sanity_check": summary["sanity_check"],
                "preparation_files": summary["preparation_files"],
                "goal_check": summary["goal_check"],
            }
            print(json.dumps(out_data, indent=2, ensure_ascii=False, default=str))
        else:
            print(format_markdown_summary(summary))
    except Exception as exc:
        from core.errors import CoreError
        if args.json:
            error = exc.to_dict() if isinstance(exc, CoreError) else {
                "status": "failed", "message": str(exc), "type": type(exc).__name__,
                "write_authoritative_artifact": False,
            }
            print(json.dumps({"recipe": args.recipe, "status": "failed", "error": error,
                              "authoritative_delivery": None}, ensure_ascii=False, indent=2, default=str))
        print(f"Error running recipe {args.recipe}: {exc}", file=sys.stderr)
        for failure in getattr(exc, "details", {}).get("cds_failures", []):
            for issue in failure.get("validation_errors") or []:
                print(f"{issue.get('code')}: {issue.get('message')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
