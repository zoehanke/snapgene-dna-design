#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/inspect_plasmid.py - Fast, token-efficient plasmid inspection for Host LLMs.

Usage:
    python scripts/inspect_plasmid.py pUC19.gb [insert.fasta] [--json]

Extracts topology, length, GC%, origins of replication, antibiotic resistance markers,
CDS features with coordinates and reading frame status, and unique MCS restriction cutters.
Outputs clean, compact Markdown (default) or structured JSON.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

# Ensure project root is on sys.path
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.tools.inspection import _load_record, selection_marker_evidence
from core.tools.restriction import find_restriction_sites
from evidence_trace.runtime import add_trace_arguments, trace_options, trace_file_call

COMMON_MCS_ENZYMES = [
    "EcoRI", "BamHI", "HindIII", "XhoI", "NdeI", "NcoI", "NotI", "SalI",
    "XbaI", "SacI", "KpnI", "PstI", "SpeI", "ClaI", "BglII", "BsaI", "BsmBI"
]


def inspect_single_file(file_path: str | pathlib.Path, enzymes: list[str] | None = None) -> dict[str, Any]:
    p = pathlib.Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    rec = _load_record(p)
    seq_str = str(rec.seq).upper()
    n = len(seq_str)
    topo = rec.annotations.get("topology", "unknown")
    gc = round((seq_str.count("G") + seq_str.count("C")) / n * 100.0, 1) if n > 0 else 0.0

    target_enzymes = enzymes or COMMON_MCS_ENZYMES

    restr_res = find_restriction_sites(rec, enzymes=target_enzymes).analysis
    unique_cutters = restr_res.get("unique_cutters", [])
    unique_cutter_details = []
    enzymes_map = restr_res.get("enzymes", {})
    for enz_name in unique_cutters:
        enz_info = enzymes_map.get(enz_name, {})
        cuts = enz_info.get("cuts", [])
        if cuts:
            c = cuts[0]
            unique_cutter_details.append({
                "enzyme": enz_name,
                "cut_0based": c["top_cut_boundary_0based"],
                "recognition_seq": enz_info.get("recognition_sequence"),
                "overhang": c.get("overhang_type"),
            })

    oris = []
    markers = []
    promoters = []
    cds_list = []
    other_features = []
    marker_evidence = selection_marker_evidence(rec)
    supported_markers = {entry['feature_index'] for entry in marker_evidence['selection_markers']}

    for index, f in enumerate(getattr(rec, "features", [])):
        ftype = f.type
        if ftype == "source" or f.location is None:
            continue

        name = ""
        for q in ("label", "gene", "product", "note", "locus_tag"):
            vals = f.qualifiers.get(q)
            if vals and isinstance(vals, list) and vals[0]:
                name = str(vals[0])
                break
        if not name:
            name = f"{ftype}_{int(f.location.start)}"

        start = int(f.location.start)
        end = int(f.location.end)
        length = len(f)
        strand = 1 if f.location.strand != -1 else -1

        feat_dict = {
            "name": name,
            "type": ftype,
            "start_0based": start,
            "end_0based": end,
            "length_bp": length,
            "strand": strand,
            "parts_0based": [[int(part.start), int(part.end)] for part in f.location.parts],
        }

        name_lower = name.lower()
        if ftype in ("rep_origin", "origin"):
            oris.append(feat_dict)
        elif index in supported_markers:
            feat_dict['annotation_status'] = 'CDS_SUPPORTED'
            feat_dict['functional_status'] = 'NOT_TESTED'
            markers.append(feat_dict)
        elif ftype == "promoter" or (ftype in ("misc_feature", "regulatory") and "promoter" in name_lower):
            promoters.append(feat_dict)
        elif ftype == "CDS":
            in_frame = (length % 3 == 0)
            feat_dict["in_frame"] = in_frame
            cds_list.append(feat_dict)
        else:
            other_features.append(feat_dict)

    return {
        "file_name": p.name,
        "file_path": str(p.resolve()),
        "length_bp": n,
        "topology": topo,
        "gc_percent": gc,
        "origin_of_replication": oris,
        "selection_markers": markers,
        "promoters": promoters,
        "cds_features": cds_list,
        "unique_restriction_cutters": unique_cutter_details,
        "total_features": len(rec.features),
        "warnings": marker_evidence['warnings'],
    }


def format_markdown_report(data: dict[str, Any]) -> str:
    lines = []
    lines.append(f"### Plasmid Inspection: `{data['file_name']}`")
    lines.append(f"- **Length**: {data['length_bp']} bp | **Topology**: {data['topology']} | **GC%**: {data['gc_percent']}%")

    # Replication & Markers
    ori_str = ", ".join(f"{o['name']} ({o['start_0based']}-{o['end_0based']})" for o in data["origin_of_replication"]) or "None annotated"
    marker_str = ", ".join(f"{m['name']} ({m['start_0based']}-{m['end_0based']})" for m in data["selection_markers"]) or "None annotated"
    lines.append(f"- **Replication Origin**: {ori_str}")
    lines.append(f"- **Selection Markers**: {marker_str}")
    for warning in data.get('warnings', []):
        lines.append(f"- **Annotation warning**: {warning['name']}: {warning['message']}")

    # Promoters
    if data["promoters"]:
        prom_str = ", ".join(f"{p['name']} ({p['start_0based']}-{p['end_0based']}, {'+' if p['strand'] == 1 else '-'})" for p in data["promoters"])
        lines.append(f"- **Promoters / Operators**: {prom_str}")

    # CDS Features
    if data["cds_features"]:
        lines.append("\n**Annotated CDS:**")
        lines.append("| Name | Coordinates (0-based) | Length (bp) | Strand | Mod 3 Frame |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for cds in data["cds_features"][:10]:
            frame_status = "In-frame (divisible by 3)" if cds.get("in_frame") else "Frameshift / non-divisible by 3"
            strand_symbol = "+" if cds["strand"] == 1 else "-"
            lines.append(f"| `{cds['name']}` | {cds['start_0based']}..{cds['end_0based']} | {cds['length_bp']} | {strand_symbol} | {frame_status} |")
        if len(data["cds_features"]) > 10:
            lines.append(f"*... and {len(data['cds_features']) - 10} more CDS features.*")

    # Unique Cutters (MCS Candidates)
    if data["unique_restriction_cutters"]:
        cutters_formatted = [f"`{c['enzyme']}` ({c['cut_0based']} bp, {c['overhang']})" for c in data["unique_restriction_cutters"]]
        lines.append("\n**Unique Single-Cut Restriction Sites (Cloning Candidates):**")
        lines.append(", ".join(cutters_formatted))
    else:
        lines.append("\n**Unique Single-Cut Restriction Sites:** None found among common lab enzymes.")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Fast, token-efficient plasmid and sequence inspection CLI for Host LLMs."
    )
    parser.add_argument("files", nargs="+", help="Sequence file(s) (.gb, .dna, .fasta, .fa)")
    parser.add_argument("--json", action="store_true", help="Output results in machine-readable JSON format")
    parser.add_argument("--enzymes", nargs="*", help="Custom list of restriction enzymes to scan")
    add_trace_arguments(parser)

    args = parser.parse_args()

    results = []
    for f in args.files:
        try:
            info = trace_file_call("inspect", inspect_single_file, args=(f,), kwargs={"enzymes": args.enzymes},
                                   input_paths=[f], **trace_options(args))
            results.append(info)
        except Exception as exc:
            results.append({"file_name": pathlib.Path(f).name, "error": str(exc)})

    if args.json:
        print(json.dumps(results if len(results) > 1 else results[0], indent=2, ensure_ascii=False))
    else:
        for r in results:
            if "error" in r:
                print(f"Error inspecting {r.get('file_name')}: {r['error']}", file=sys.stderr)
            else:
                print(format_markdown_report(r))
                print("\n---\n")
    return 1 if any('error' in result for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
