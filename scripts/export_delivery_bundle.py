# -*- coding: utf-8 -*-
"""Create a conservative SnapGene delivery bundle with an audit manifest."""
import argparse
import copy
import hashlib
import json
import pathlib

from Bio import SeqIO

from sg_common import jprint, load_seq
from snapgene_compatibility import analyze_record
from write_dna import _ensure_annotations, write_native_dna


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _entry(path, role, fmt):
    return {
        "path": path.name,
        "role": role,
        "format": fmt,
        "size": path.stat().st_size,
        "sha256": _sha256(path),
    }


def build_bundle(source, out_dir, name=None, allow_core_risk=False,
                 require_dna=False):
    """Build a preview-class delivery bundle for a low-level tool output.

    v0.9.1 architecture recovery: this script is a low-level tool.  Only
    ``core.finalize`` may emit authoritative products, so the bundle is
    explicitly preview-class and must never be labeled authoritative.
    """
    record, source_format = load_seq(source)
    assessment = analyze_record(record, source_format)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = name or record.name or record.id or "construct"
    safe_stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)
    safe_stem = safe_stem.strip("_") or "construct"

    preview_gb = out_dir / (safe_stem + ".preview.gb")
    gb_record = _ensure_annotations(copy.deepcopy(record))
    with preview_gb.open("w", encoding="utf-8") as handle:
        SeqIO.write(gb_record, handle, "genbank")

    files = [_entry(preview_gb, "preview", "genbank")]
    dna_assessment = assessment["formats"]["dna"]
    dna_written = False
    native_path = out_dir / (safe_stem + ".dna")
    if dna_assessment["core_safe"] or allow_core_risk:
        write_native_dna(copy.deepcopy(record), str(native_path))
        role = "convenience" if dna_assessment["core_safe"] else "core-risk-opt-in"
        files.append(_entry(native_path, role, "dna"))
        dna_written = True
    if require_dna and not dna_written:
        raise ValueError(
            "native .dna blocked by core compatibility findings; rerun with "
            "--allow-core-risk only after reviewing compatibility-report.json")

    compatibility_path = out_dir / "compatibility-report.json"
    compatibility_path.write_text(
        json.dumps(assessment, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8")
    files.append(_entry(compatibility_path, "audit", "json"))

    manifest = {
        "schema_version": "0.6.0-rc2",
        "source": str(source),
        "source_format": source_format,
        "artifact_class": "preview",
        "not_authoritative": True,
        "delivery_policy": "preview-genbank-plus-safe-convenience-files",
        "authoritative_gate_note": (
            "v0.9.1: only core.finalize may emit authoritative products; "
            "this bundle is a preview from a low-level tool"),
        "native_dna_written": dna_written,
        "native_dna_core_risk_accepted": bool(
            dna_written and not dna_assessment["core_safe"]),
        "manual_review_required": assessment["recommendation"][
            "manual_review_required"],
        "files": files,
    }
    manifest_path = out_dir / "DELIVERY-MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8")
    return {
        "bundle_dir": str(out_dir),
        "manifest": str(manifest_path),
        "native_dna_written": dna_written,
        "manual_review_required": manifest["manual_review_required"],
        "artifact_class": "preview",
        "files": files,
        "warnings": assessment["warnings"] + (
            ["Native .dna omitted because it has core compatibility risks."]
            if not dna_written else []),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--name")
    parser.add_argument("--allow-core-risk", action="store_true")
    parser.add_argument("--require-dna", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = build_bundle(
            args.source, args.out_dir, args.name, args.allow_core_risk,
            args.require_dna)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))
    if args.json:
        jprint(result)
    else:
        print("delivery bundle:", result["bundle_dir"])
        print("  native .dna:", "written" if result["native_dna_written"] else "omitted")
        print("  manual review:", result["manual_review_required"])
        for warning in result["warnings"]:
            print("warning:", warning)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
