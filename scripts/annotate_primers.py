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
import copy
import hashlib
import json
import os
import pathlib
import sys
from typing import Any, List, Tuple

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord


def _strand_char(strand: int | str | None) -> str:
    if strand in (-1, "-", "reverse"):
        return "-"
    return "+"


def _strand_int(strand: int | str | None) -> int:
    if strand in (-1, "-", "reverse"):
        return -1
    return 1


def find_unique_binding_site(template_seq: str, primer_seq: str) -> Tuple[int, str]:
    """Find unique binding site on forward or reverse complement strand.

    Rules:
      0 matches  -> raises ValueError (no match)
      1 match    -> returns (start_0based, strand) where strand is '+' or '-'
      >1 matches -> raises ValueError (ambiguous across strands)
    """
    tpl = template_seq.upper()
    p = primer_seq.upper()
    p_rc = str(Seq(p).reverse_complement()).upper()

    matches: List[Tuple[int, str]] = []

    # Forward strand matches
    idx = 0
    while True:
        pos = tpl.find(p, idx)
        if pos == -1:
            break
        matches.append((pos, "+"))
        idx = pos + 1

    # Reverse complement strand matches
    idx = 0
    while True:
        pos = tpl.find(p_rc, idx)
        if pos == -1:
            break
        matches.append((pos, "-"))
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

    if op == "add":
        for p_def in primers_to_add:
            p_name = p_def["name"]
            p_seq = p_def["sequence"].upper()
            bind_pos = p_def.get("bind_position")
            strand = p_def.get("strand")

            if bind_pos is None:
                pos, st = find_unique_binding_site(seq_str, p_seq)
            else:
                pos = int(bind_pos)
                st = _strand_char(strand)

            sg.add_primer(p_name, p_seq, bind_position=pos, bind_strand=st)

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

        p_name = new_primer.get("name") or target_name
        p_seq = new_primer["sequence"].upper()
        bind_pos = new_primer.get("bind_position")
        strand = new_primer.get("strand")

        if bind_pos is None:
            pos, st = find_unique_binding_site(seq_str, p_seq)
        else:
            pos = int(bind_pos)
            st = _strand_char(strand)

        sg.primers.remove(matches[0])
        sg.add_primer(p_name, p_seq, bind_position=pos, bind_strand=st)

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
    record = SeqIO.read(str(source_path), "genbank")
    seq_str = str(record.seq).upper()
    hash_before = hashlib.sha256(seq_str.encode("ascii")).hexdigest()

    prev_features_count = len(record.features)
    prev_primers = [f for f in record.features if f.type in ("primer_bind", "primer")]
    prev_primers_count = len(prev_primers)

    if op == "add":
        for p_def in primers_to_add:
            p_name = p_def["name"]
            p_seq = p_def["sequence"].upper()
            bind_pos = p_def.get("bind_position")
            strand = p_def.get("strand")

            if bind_pos is None:
                pos, st = find_unique_binding_site(seq_str, p_seq)
            else:
                pos = int(bind_pos)
                st = _strand_char(strand)

            strand_val = _strand_int(st)
            loc = FeatureLocation(pos, pos + len(p_seq), strand=strand_val)
            feat = SeqFeature(
                loc,
                type="primer_bind",
                qualifiers={"label": [p_name], "note": [f"sequence: {p_seq}"]},
            )
            record.features.append(feat)

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

        p_name = new_primer.get("name") or target_name
        p_seq = new_primer["sequence"].upper()
        bind_pos = new_primer.get("bind_position")
        strand = new_primer.get("strand")

        if bind_pos is None:
            pos, st = find_unique_binding_site(seq_str, p_seq)
        else:
            pos = int(bind_pos)
            st = _strand_char(strand)

        strand_val = _strand_int(st)
        loc = FeatureLocation(pos, pos + len(p_seq), strand=strand_val)
        new_feat = SeqFeature(
            loc,
            type="primer_bind",
            qualifiers={"label": [p_name], "note": [f"sequence: {p_seq}"]},
        )
        record.features[matches[0][0]] = new_feat

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
    check_rec = SeqIO.read(str(out_path), "genbank")
    seq_after = str(check_rec.seq).upper()
    hash_after = hashlib.sha256(seq_after.encode("ascii")).hexdigest()

    if hash_before != hash_after:
        if os.path.exists(str(out_path)):
            os.remove(str(out_path))
        raise RuntimeError(
            f"Hard invariant violated: sequence altered during primer {op}! "
            f"Expected {hash_before[:12]}..., got {hash_after[:12]}..."
        )

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
        "--bind-pos",
        type=int,
        default=None,
        help="0-based start binding coordinate (optional; auto-binds if omitted)",
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
                    "bind_position": args.bind_pos,
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
            "bind_position": args.bind_pos,
            "strand": args.strand,
        }

    elif args.op == "remove":
        if not args.name:
            parser.error("Operation 'remove' requires --name of the target primer.")

    # Execute based on format
    ext = src.suffix.lower()
    if ext == ".dna":
        result = annotate_primers_dna(
            source_path=src,
            out_path=dst,
            op=args.op,
            primers_to_add=primers_to_add,
            target_name=args.name,
            new_primer=new_primer_def,
        )
    elif ext in (".gb", ".gbk", ".genbank"):
        result = annotate_primers_gb(
            source_path=src,
            out_path=dst,
            op=args.op,
            primers_to_add=primers_to_add,
            target_name=args.name,
            new_primer=new_primer_def,
        )
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
