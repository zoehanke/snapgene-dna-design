# -*- coding: utf-8 -*-
"""scripts/annotate_primers.py - Safe in-place primer annotation & editing tool.

Supports modifying primer annotations on existing construct files (.dna and .gb/.gbk)
without altering the underlying nucleotide sequence or pre-existing non-primer features.

Operations:
  add       Add one or more primers (supports auto-binding to template sequence)
  remove    Remove a primer by exact unique name (0 -> fail, >1 -> ambiguous fail)
  replace   Replace a primer by exact unique name with a new definition
  clear     Clear all primer annotations on the construct

Hard Invariant:
  Nucleotide sequence before and after editing must be identical (SHA256).
  The tool edits annotations only; it never alters construct sequence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys
from typing import Any, Tuple

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import SeqFeature
from Bio.SeqRecord import SeqRecord

_PROJECT_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
from evidence_trace.runtime import add_trace_arguments, trace_options, trace_file_call
from core.tools.snapgene_io import (
    _primer_location,
    annotate_record_primers,
    normalize_primer_definition,
)


def _strand_char(strand: int | str | None) -> str:
    if strand in (-1, "-", "reverse"):
        return "-"
    return "+"


def _strand_int(strand: int | str | None) -> int:
    if strand in (-1, "-", "reverse"):
        return -1
    return 1


def _circular_matches(template_seq: str, primer_seq: str) -> list[Tuple[int, str]]:
    tpl = template_seq.upper()
    p = primer_seq.upper()
    if not p or len(p) > len(tpl):
        return []
    search = tpl + tpl[: len(p) - 1]
    matches: list[Tuple[int, str]] = []
    for strand, needle in (
        ("+", p),
        ("-", str(Seq(p).reverse_complement()).upper()),
    ):
        for pos in range(len(tpl)):
            if search[pos : pos + len(p)] == needle:
                matches.append((pos, strand))
    return matches


def find_unique_binding_site(
    template_seq: str,
    primer_seq: str,
    circular: bool = False,
) -> Tuple[int, str]:
    """Find unique binding site on forward or reverse complement strand.

    Rules:
      0 matches  -> raises ValueError (no match)
      1 match    -> returns (start_0based, strand) where strand is '+' or '-'
      >1 matches -> raises ValueError (ambiguous across strands)
    """
    tpl = template_seq.upper()
    p = primer_seq.upper()
    if circular:
        matches = _circular_matches(tpl, p)
    else:
        p_rc = str(Seq(p).reverse_complement()).upper()
        matches = []
        for strand, needle in (("+", p), ("-", p_rc)):
            idx = 0
            while True:
                pos = tpl.find(needle, idx)
                if pos == -1:
                    break
                matches.append((pos, strand))
                idx = pos + 1

    if len(matches) == 0:
        raise ValueError(
            f"Primer sequence '{primer_seq}' (len {len(primer_seq)}) has 0 binding sites on the template."
        )
    if len(matches) > 1:
        match_desc = ", ".join(f"pos {m[0]} ({m[1]})" for m in matches)
        raise ValueError(
            f"Ambiguous binding for primer '{primer_seq}': found {len(matches)} matches ({match_desc})."
        )

    return matches[0]


def _get_gb_primer_name(feat: SeqFeature) -> str:
    for q in ("label", "note", "gene"):
        vals = feat.qualifiers.get(q)
        if vals:
            return str(vals[0])
    return str(feat.id or "")


def _read_genbank_utf8(path: str | pathlib.Path) -> SeqRecord:
    with open(str(path), "r", encoding="utf-8-sig") as handle:
        return SeqIO.read(handle, "genbank")


def _gb_add_primer(record: SeqRecord, definition: dict[str, Any]) -> tuple[SeqRecord, dict[str, Any]]:
    payload = normalize_primer_definition(record, definition)
    return annotate_record_primers(record, [payload]), payload


def _assert_gb_primer_payloads(record: SeqRecord, payloads: list[dict[str, Any]]) -> None:
    for payload in payloads:
        matches = [
            feature
            for feature in record.features
            if feature.type in ("primer_bind", "primer")
            and _get_gb_primer_name(feature) == payload["name"]
        ]
        if len(matches) != 1:
            raise RuntimeError(
                "GenBank primer read-back expected one '%s', found %d"
                % (payload["name"], len(matches))
            )
        feature = matches[0]
        full = _first_qualifier_for_feature(feature, "primer_sequence", "primer_seq")
        core = _first_qualifier_for_feature(feature, "binding_sequence", "binding_seq")
        if full is None or "".join(full.split()).upper() != payload["sequence"].upper():
            raise RuntimeError(
                "GenBank primer '%s' full sequence changed during write"
                % payload["name"]
            )
        if core is None or "".join(core.split()).upper() != payload["binding_sequence"].upper():
            raise RuntimeError(
                "GenBank primer '%s' binding sequence changed during write"
                % payload["name"]
            )
        expected_location = _primer_location(
            payload["binding_interval_0based"][0],
            payload["binding_interval_0based"][1],
            payload["strand_int"],
            len(record.seq),
            payload["topology"],
        )
        if str(feature.location) != str(expected_location):
            raise RuntimeError(
                "GenBank primer '%s' binding location changed during write"
                % payload["name"]
            )


def _first_qualifier_for_feature(feature: SeqFeature, *keys: str) -> str | None:
    for key in keys:
        values = feature.qualifiers.get(key)
        if values:
            value = values[0] if isinstance(values, list) else values
            return str(value)
    return None


def _native_add_primer(sg, record: SeqRecord, definition: dict[str, Any]) -> dict[str, Any]:
    from sgffp import SgffBindingSite, SgffPrimer

    payload = normalize_primer_definition(record, definition)
    start, end = payload["binding_interval_0based"]
    sg.primers.add(
        SgffPrimer(
            name=payload["name"],
            sequence=payload["sequence"],
            binding_sites=[
                SgffBindingSite(
                    start=start,
                    end=end,
                    bound_strand=payload["strand"],
                    annealed_bases=payload["binding_sequence"],
                )
            ],
        )
    )
    return payload


def _assert_native_primer_payloads(check_obj, payloads: list[dict[str, Any]]) -> None:
    for payload in payloads:
        matches = [primer for primer in check_obj.primers if primer.name == payload["name"]]
        if len(matches) != 1:
            raise RuntimeError(
                "Native primer read-back expected one '%s', found %d"
                % (payload["name"], len(matches))
            )
        primer = matches[0]
        if primer.sequence.upper() != payload["sequence"].upper():
            raise RuntimeError(
                "Native primer '%s' full sequence changed during write"
                % payload["name"]
            )
        sites = [site for site in primer.binding_sites if not site.simplified]
        if len(sites) != 1:
            raise RuntimeError(
                "Native primer '%s' read-back has %d binding sites"
                % (payload["name"], len(sites))
            )
        site = sites[0]
        start, end = payload["binding_interval_0based"]
        if (
            site.start != start
            or site.end != end
            or site.bound_strand != payload["strand"]
            or site.annealed_bases.upper() != payload["binding_sequence"].upper()
        ):
            raise RuntimeError(
                "Native primer '%s' binding metadata changed during write"
                % payload["name"]
            )


def annotate_primers_dna(
    source_path: str | pathlib.Path,
    out_path: str | pathlib.Path,
    op: str,
    primers_to_add: list[dict[str, Any]],
    target_name: str | None = None,
    new_primer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """In-place primer modification for native SnapGene .dna files."""
    from sgffp import SgffReader, SgffWriter

    sg = SgffReader.from_file(str(source_path))
    seq_str = str(sg.sequence.data.value).upper()
    hash_before = hashlib.sha256(seq_str.encode("ascii")).hexdigest()

    prev_primers_count = len(sg.primers)
    prev_features_count = len(sg.features)

    topology = getattr(sg.sequence.data, "topology", None) or "linear"
    record = SeqRecord(
        Seq(seq_str),
        id="native",
        annotations={"molecule_type": "DNA", "topology": topology},
    )
    pending_payloads: list[dict[str, Any]] = []

    if op == "add":
        for p_def in primers_to_add:
            pending_payloads.append(_native_add_primer(sg, record, p_def))

    elif op == "remove":
        if not target_name:
            raise ValueError("Operation 'remove' requires primer --name.")
        matches = [i for i, p in enumerate(sg.primers) if p.name == target_name]
        if len(matches) == 0:
            raise ValueError(f"Primer '{target_name}' not found for removal (0 matches).")
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous primer name '{target_name}': found {len(matches)} matches. Refusing to remove."
            )
        sg.primers.remove(matches[0])

    elif op == "replace":
        if not target_name:
            raise ValueError("Operation 'replace' requires primer --name.")
        if not new_primer:
            raise ValueError("Operation 'replace' requires new primer definition (--seq).")

        matches = [i for i, p in enumerate(sg.primers) if p.name == target_name]
        if len(matches) == 0:
            raise ValueError(f"Primer '{target_name}' not found for replacement (0 matches).")
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous primer name '{target_name}': found {len(matches)} matches. Refusing to replace."
            )

        sg.primers.remove(matches[0])
        replacement = dict(new_primer)
        replacement["name"] = replacement.get("name") or target_name
        pending_payloads.append(_native_add_primer(sg, record, replacement))

    elif op == "clear":
        sg.primers.clear()
    else:
        raise ValueError(f"Unsupported operation: {op}")

    # Write output
    SgffWriter.to_file(sg, str(out_path))

    # Re-read output and enforce sequence invariance
    check_obj = SgffReader.from_file(str(out_path))
    seq_after = str(check_obj.sequence.data.value).upper()
    hash_after = hashlib.sha256(seq_after.encode("ascii")).hexdigest()

    if hash_before != hash_after:
        if os.path.exists(str(out_path)):
            os.remove(str(out_path))
        raise RuntimeError(
            f"Hard invariant violated: sequence altered during primer {op}! "
            f"Expected {hash_before[:12]}..., got {hash_after[:12]}..."
        )
    if pending_payloads:
        _assert_native_primer_payloads(check_obj, pending_payloads)

    return {
        "status": "success",
        "op": op,
        "format": "dna",
        "source": str(source_path),
        "output": str(out_path),
        "length": len(seq_after),
        "features_count": len(check_obj.features),
        "primers_count": len(check_obj.primers),
        "previous_primers_count": prev_primers_count,
        "previous_features_count": prev_features_count,
    }


def annotate_primers_gb(
    source_path: str | pathlib.Path,
    out_path: str | pathlib.Path,
    op: str,
    primers_to_add: list[dict[str, Any]],
    target_name: str | None = None,
    new_primer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """In-place primer modification for GenBank (.gb/.gbk) files."""
    record = _read_genbank_utf8(source_path)
    seq_str = str(record.seq).upper()
    hash_before = hashlib.sha256(seq_str.encode("ascii")).hexdigest()

    prev_features_count = len(record.features)
    prev_primers = [f for f in record.features if f.type in ("primer_bind", "primer")]
    prev_primers_count = len(prev_primers)
    pending_payloads: list[dict[str, Any]] = []

    if op == "add":
        for p_def in primers_to_add:
            record, payload = _gb_add_primer(record, p_def)
            pending_payloads.append(payload)

    elif op == "remove":
        if not target_name:
            raise ValueError("Operation 'remove' requires primer --name.")
        matches = [
            (idx, f)
            for idx, f in enumerate(record.features)
            if f.type in ("primer_bind", "primer") and _get_gb_primer_name(f) == target_name
        ]
        if len(matches) == 0:
            raise ValueError(f"Primer '{target_name}' not found for removal (0 matches).")
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous primer name '{target_name}': found {len(matches)} matches. Refusing to remove."
            )
        del record.features[matches[0][0]]

    elif op == "replace":
        if not target_name:
            raise ValueError("Operation 'replace' requires primer --name.")
        if not new_primer:
            raise ValueError("Operation 'replace' requires new primer definition (--seq).")

        matches = [
            (idx, f)
            for idx, f in enumerate(record.features)
            if f.type in ("primer_bind", "primer") and _get_gb_primer_name(f) == target_name
        ]
        if len(matches) == 0:
            raise ValueError(f"Primer '{target_name}' not found for replacement (0 matches).")
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous primer name '{target_name}': found {len(matches)} matches. Refusing to replace."
            )

        replacement = dict(new_primer)
        replacement["name"] = replacement.get("name") or target_name
        updated_record, payload = _gb_add_primer(record, replacement)
        # Preserve the original feature position in the feature list while
        # replacing only that primer definition.
        added_feature = updated_record.features.pop()
        updated_record.features[matches[0][0]] = added_feature
        record = updated_record
        pending_payloads.append(payload)

    elif op == "clear":
        record.features = [
            f for f in record.features if f.type not in ("primer_bind", "primer")
        ]
    else:
        raise ValueError(f"Unsupported operation: {op}")

    # Write output
    with open(str(out_path), "w", encoding="utf-8") as fh:
        SeqIO.write(record, fh, "genbank")

    # Re-read output and enforce sequence invariance
    check_rec = _read_genbank_utf8(out_path)
    seq_after = str(check_rec.seq).upper()
    hash_after = hashlib.sha256(seq_after.encode("ascii")).hexdigest()

    if hash_before != hash_after:
        if os.path.exists(str(out_path)):
            os.remove(str(out_path))
        raise RuntimeError(
            f"Hard invariant violated: sequence altered during primer {op}! "
            f"Expected {hash_before[:12]}..., got {hash_after[:12]}..."
        )
    if pending_payloads:
        _assert_gb_primer_payloads(check_rec, pending_payloads)

    current_primers = [
        f for f in check_rec.features if f.type in ("primer_bind", "primer")
    ]
    return {
        "status": "success",
        "op": op,
        "format": "genbank",
        "source": str(source_path),
        "output": str(out_path),
        "length": len(seq_after),
        "features_count": len(check_rec.features),
        "primers_count": len(current_primers),
        "previous_primers_count": prev_primers_count,
        "previous_features_count": prev_features_count,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Safely annotate and edit primer annotations on existing construct files (.dna, .gb)"
    )
    parser.add_argument("source", help="Path to input construct file (.dna or .gb/.gbk)")
    parser.add_argument("--out", required=True, help="Path to output construct file")
    parser.add_argument(
        "--op",
        choices=["add", "remove", "replace", "clear"],
        default="add",
        help="Operation to perform (default: add)",
    )
    parser.add_argument("--name", help="Primer name (for remove/replace, or single add)")
    parser.add_argument("--seq", help="Primer sequence (for single add or replace)")
    parser.add_argument(
        "--binding-seq", "--binding-sequence", dest="binding_sequence",
        help="Actual 3' annealing core in primer 5' to 3' orientation",
    )
    parser.add_argument(
        "--bind-pos",
        type=int,
        default=None,
        help="0-based start binding coordinate (optional; auto-binds if omitted)",
    )
    parser.add_argument(
        "--bind-end",
        type=int,
        default=None,
        help="0-based half-open binding end coordinate",
    )
    parser.add_argument(
        "--strand",
        choices=["+", "-", "1", "-1"],
        default=None,
        help="Strand ('+' or '-') if bind-pos specified",
    )
    parser.add_argument(
        "--primers-json",
        help="JSON file or inline JSON string with list of primers: [{'name': '...', 'sequence': '...', 'bind_position': 100, 'strand': '+'}]",
    )
    parser.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="Allow output path to overwrite source file",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON summary to stdout")
    add_trace_arguments(parser)

    args = parser.parse_args()

    src = pathlib.Path(args.source).resolve()
    dst = pathlib.Path(args.out).resolve()

    if not src.exists():
        parser.error(f"Source file does not exist: {src}")

    # Overwrite protection check
    if src == dst and not args.allow_overwrite:
        parser.error(
            f"Output path equals source path ({src}). "
            "Pass --allow-overwrite explicitly to overwrite in place."
        )

    # Parse primer inputs
    primers_to_add: list[dict[str, Any]] = []
    new_primer_def: dict[str, Any] | None = None

    if args.op == "add":
        if args.primers_json:
            raw_input = args.primers_json.strip()
            if os.path.exists(raw_input):
                with open(raw_input, "r", encoding="utf-8") as fh:
                    primers_to_add = json.load(fh)
            else:
                primers_to_add = json.loads(raw_input)
            if not isinstance(primers_to_add, list):
                parser.error("--primers-json must resolve to a list of primer definitions.")
        elif args.name and args.seq:
            primers_to_add = [
                {
                    "name": args.name,
                    "sequence": args.seq,
                    "binding_sequence": args.binding_sequence,
                    "bind_position": args.bind_pos,
                    "bind_end": args.bind_end,
                    "strand": args.strand,
                }
            ]
        else:
            parser.error("Operation 'add' requires either (--name and --seq) or --primers-json.")

    elif args.op == "replace":
        if not args.name:
            parser.error("Operation 'replace' requires --name of the target primer to replace.")
        if not args.seq:
            parser.error("Operation 'replace' requires --seq for the new primer definition.")
        new_primer_def = {
            "name": args.name,
            "sequence": args.seq,
            "binding_sequence": args.binding_sequence,
            "bind_position": args.bind_pos,
            "bind_end": args.bind_end,
            "strand": args.strand,
        }

    elif args.op == "remove":
        if not args.name:
            parser.error("Operation 'remove' requires --name of the target primer.")

    # Execute based on format
    ext = src.suffix.lower()
    if ext == ".dna":
        result = trace_file_call("annotate_primers", annotate_primers_dna, kwargs=dict(
            source_path=src,
            out_path=dst,
            op=args.op,
            primers_to_add=primers_to_add,
            target_name=args.name,
            new_primer=new_primer_def,
        ), input_paths=[src], expected_paths=[dst], output_paths=lambda value: [value["output"]],
            artifact_role="primer-annotated", **trace_options(args))
    elif ext in (".gb", ".gbk", ".genbank"):
        result = trace_file_call("annotate_primers", annotate_primers_gb, kwargs=dict(
            source_path=src,
            out_path=dst,
            op=args.op,
            primers_to_add=primers_to_add,
            target_name=args.name,
            new_primer=new_primer_def,
        ), input_paths=[src], expected_paths=[dst], output_paths=lambda value: [value["output"]],
            artifact_role="primer-annotated", **trace_options(args))
    else:
        parser.error(f"Unsupported format '{ext}'. Must be .dna or .gb/.gbk.")

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"[OK] {args.op.upper()} succeeded: {result['source']} -> {result['output']} "
            f"(length={result['length']} bp, features={result['features_count']}, primers={result['primers_count']})"
        )


if __name__ == "__main__":
    main()
