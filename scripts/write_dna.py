# -*- coding: utf-8 -*-
"""write_dna.py - Export sequences to files.

Formats:
  genbank      standard GenBank (.gb)
  snapgene-gb  GenBank with SnapGene markers (LOCUS 'Exported' + a Direct
               Submission reference with a SnapGene journal) so SnapGene
               decodes colors/directions; opens directly without warnings.
  dna          native SnapGene binary (.dna), written via sgffp (MIT).
  fasta        FASTA

Optionally attach features from a JSON file (list of
{type,name,start,end,strand} with 1-based closed coords).
"""
import argparse
import json

from Bio import SeqIO
from Bio.SeqFeature import Reference, SeqFeature, FeatureLocation

from sg_common import jprint, load_seq, topology


def attach_features(record, feat_path):
    """Attach features from a JSON file (1-based closed coords)."""
    with open(feat_path, encoding="utf-8") as fh:
        feats = json.load(fh)
    for f in feats:
        strand = f.get("strand", 1) or 1
        record.features.append(SeqFeature(
            FeatureLocation(int(f["start"]) - 1, int(f["end"]), strand=strand),
            type=f.get("type", "misc_feature"),
            qualifiers={"label": [f.get("name", "feature")]}))
    return record


import pathlib
import sys

_ROOT = str(pathlib.Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.tools.snapgene_io import (
    _ensure_annotations,
    _snapgene_annotated,
    _strand_char,
    write_native_dna,
)


def main():
    p = argparse.ArgumentParser(description="Export sequences / build construct files")
    p.add_argument("source", help="sequence file or raw sequence string")
    p.add_argument("--out", required=True, help="output file path")
    p.add_argument("--format", choices=["genbank", "snapgene-gb", "dna", "fasta"],
                   default="dna")
    p.add_argument("--name", default=None, help="record name (default: from source)")
    p.add_argument("--features-json", help="JSON file with features [{type,name,start,end,strand}]")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    record, _fmt = load_seq(args.source)
    if args.name:
        record.id = args.name
        record.name = args.name
    if args.features_json:
        record = attach_features(record, args.features_json)

    topo = topology(record)
    fmt = args.format
    if fmt == "genbank":
        _ensure_annotations(record)
        with open(args.out, "w", encoding="utf-8") as fh:
            SeqIO.write(record, fh, "genbank")
    elif fmt == "fasta":
        with open(args.out, "w", encoding="utf-8") as fh:
            SeqIO.write(record, fh, "fasta")
    elif fmt == "snapgene-gb":
        record = _snapgene_annotated(record)
        with open(args.out, "w", encoding="utf-8") as fh:
            SeqIO.write(record, fh, "genbank")
    else:  # dna
        write_native_dna(record, args.out)

    warnings = []
    if fmt == "dna" and record.features:
        warnings.append(
            "Native .dna export preserves sequence, topology, feature segments and strand, "
            "but may not preserve all qualifiers, notes or history; "
            "prefer snapgene-gb when metadata fidelity matters"
        )
    result = {
        "out_file": args.out,
        "format": fmt,
        "length": len(record.seq),
        "topology": topo,
        "name": record.name,
        "note": ("SnapGene can open this file directly"
                 if fmt in ("snapgene-gb", "dna") else None),
        "warnings": warnings,
    }
    if args.json:
        jprint(result)
    else:
        print("wrote %s (%s, %d bp, %s)" % (args.out, fmt, len(record.seq), topo))
        for warning in warnings:
            print("warning:", warning)


if __name__ == "__main__":
    main()
