#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/run_recipe.py - CLI Runner for 7 Standard Laboratory SOP Recipes.

Usage:
    python scripts/run_recipe.py --recipe recipe_gibson_assembly --params-json params.json --out-dir ./build
    python scripts/run_recipe.py --recipe recipe_protein_tagging --params '{"target_cds_or_file": "ATG...", "tag_name_or_seq": "6xHis"}'
    python scripts/run_recipe.py --recipe recipe_gibson_assembly --params-json params.json --out-dir ./build --finalize --confirmed

Outputs:
    Writes candidate artifacts to <out-dir>/candidate/.
    If --finalize and --confirmed are set for a complete plasmid construct,
    validates and promotes artifacts to <out-dir>/authoritative/ with DELIVERY-MANIFEST.json.
"""
from __future__ import annotations

import argparse
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

import core.recipes as recipes
from core.guardrails.checklist import quick_biological_sanity_check
from core.recipes.contract import RecipeResult
from core.tools.snapgene_io import export_plasmid


def get_recipe_function(recipe_name: str):
    clean_name = recipe_name.strip()
    if not clean_name.startswith("recipe_"):
        clean_name = f"recipe_{clean_name}"
    if hasattr(recipes, clean_name):
        return getattr(recipes, clean_name), clean_name
    available = [attr for attr in dir(recipes) if attr.startswith("recipe_")]
    raise ValueError(f"Unknown recipe '{recipe_name}'. Available recipes: {', '.join(available)}")


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

    # 1. Execute Recipe
    res: RecipeResult = fn(**params)

    # 2. Biological Guardrails Check with contextual parameters
    prod_seq = res.product_sequence or res.get("product_dna_sequence") or ""
    topo = res.product_topology or "linear"

    # Only treat as CDS if explicitly designated or standard coding recipe
    is_cds = False
    if res.result_kind == "component":
        if canonical_name in ("recipe_protein_tagging", "recipe_site_directed_mutagenesis", "recipe_point_mutagenesis"):
            is_cds = True
        elif params.get("is_cds") is not None:
            is_cds = bool(params.get("is_cds"))

    # Extract execution context
    cloning_enz = params.get("enzyme") or params.get("enzymes") or res.details.get("enzyme") or res.details.get("enzymes")
    if cloning_enz and isinstance(cloning_enz, str):
        cloning_enz = [cloning_enz]
    grna_seq = params.get("grna_seq") or params.get("target_grna_seq") or res.details.get("grna_seq") or ""
    pr_seqs = [p.get("sequence") or p.get("seq") for p in (res.primers or []) if (p.get("sequence") or p.get("seq"))]
    u6_term = bool(canonical_name == "recipe_crispr_hdr_donor" or params.get("check_u6_termination"))

    sanity = quick_biological_sanity_check(
        prod_seq,
        topology=topo,
        is_cds=is_cds,
        cloning_enzymes=cloning_enz,
        crispr_grna_seq=grna_seq,
        primers=pr_seqs if len(pr_seqs) >= 2 else None,
        check_u6_termination=u6_term,
    )

    # 3. Save Candidate Artifacts
    candidate_files = []
    if prod_seq:
        fa_path = candidate_dir / f"{canonical_name}.fasta"
        fa_path.write_text(f">{canonical_name} length={len(prod_seq)} topology={topo}\n{prod_seq}\n", encoding="utf-8")
        candidate_files.append(str(fa_path))

    if res.is_plasmid_construct() and prod_seq:
        export_res = export_plasmid(
            record_or_seq=prod_seq,
            out_dir=candidate_dir,
            filename_base=canonical_name,
            topology=topo,
            features=res.features,
        )
        candidate_files.append(export_res["gb_file"])
        candidate_files.append(export_res["dna_file"])

    result_json_path = candidate_dir / f"{canonical_name}_result.json"
    result_dict = res.to_dict()
    result_dict["sanity_check"] = sanity
    result_json_path.write_text(json.dumps(result_dict, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    candidate_files.append(str(result_json_path))

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

        cand_gb = candidate_dir / f"{canonical_name}.gb"
        cand_fa = candidate_dir / f"{canonical_name}.fasta"
        if not cand_gb.exists() or not cand_fa.exists():
            raise FileNotFoundError(f"Candidate files missing for promotion: {cand_gb}, {cand_fa}")

        from core.runtime_gate import finalize_candidate_construct
        authoritative_delivery = finalize_candidate_construct(
            candidate_gb=cand_gb,
            candidate_fasta=cand_fa,
            out_dir=out_path,
            metadata={
                "recipe": canonical_name,
                "result_kind": res.result_kind,
                "completeness": res.completeness,
                "product_length": len(prod_seq),
                "product_topology": topo,
            },
            sanity_check=sanity,
            user_confirmed=user_confirmed,
        )

    return {
        "recipe": canonical_name,
        "result_kind": res.result_kind,
        "completeness": res.completeness,
        "product_length": len(prod_seq) if prod_seq else 0,
        "product_topology": topo,
        "candidate_directory": str(candidate_dir),
        "candidate_files": candidate_files,
        "authoritative_delivery": authoritative_delivery,
        "recipe_result": res,
        "sanity_check": sanity,
    }


def format_markdown_summary(exec_summary: dict[str, Any]) -> str:
    res: RecipeResult = exec_summary["recipe_result"]
    sanity = exec_summary["sanity_check"]

    lines = []
    lines.append(f"## Recipe Execution: `{exec_summary['recipe']}`")
    lines.append(f"- **Result Kind**: `{exec_summary['result_kind']}` ({exec_summary['completeness']})")
    if exec_summary["product_length"] > 0:
        lines.append(f"- **Product Sequence Length**: {exec_summary['product_length']} bp ({exec_summary['product_topology']})")

    # Primers Table
    if res.primers:
        lines.append("\n### Designed Primers")
        lines.append("| Name | Sequence (5'->3') | Length | Tm (°C) | Role |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for pr in res.primers:
            seq = pr.get("sequence") or pr.get("seq") or ""
            tm = pr.get("tm") or pr.get("tm_celsius") or 0.0
            role = pr.get("role") or pr.get("name", "primer")
            lines.append(f"| `{pr.get('name')}` | `{seq}` | {len(seq)} nt | {round(float(tm), 1)} | {role} |")

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
        lines.append(f"- **Authoritative Directory**: `{exec_summary['authoritative_delivery']['directory']}` (DELIVERY-MANIFEST.json signed)")

    return "\n".join(lines)


def main():
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

    args = parser.parse_args()

    params = {}
    if args.params_json:
        p_path = pathlib.Path(args.params_json)
        if not p_path.exists():
            print(f"Error: params-json file not found: {args.params_json}", file=sys.stderr)
            sys.exit(1)
        params = json.loads(p_path.read_text(encoding="utf-8"))
    elif args.params:
        try:
            params = json.loads(args.params)
        except Exception:
            import ast
            params = ast.literal_eval(args.params)

    try:
        summary = run_recipe_cli(
            recipe_name=args.recipe,
            params=params,
            out_dir=args.out_dir,
            finalize_requested=args.finalize,
            user_confirmed=args.confirmed,
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
            }
            print(json.dumps(out_data, indent=2, ensure_ascii=False, default=str))
        else:
            print(format_markdown_summary(summary))
    except Exception as exc:
        print(f"Error running recipe {args.recipe}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
