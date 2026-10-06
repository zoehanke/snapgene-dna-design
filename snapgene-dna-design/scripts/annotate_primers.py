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


from core.io.primer_annotation import (
    _strand_char,
    _strand_int,
    _circular_matches,
    find_unique_binding_site,
    _get_gb_primer_name,
    _read_genbank_utf8,
    _gb_add_primer,
    _assert_gb_primer_payloads,
    _first_qualifier_for_feature,
    _native_add_primer,
    _assert_native_primer_payloads,
    annotate_primers_dna,
    annotate_primers_gb
)


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
