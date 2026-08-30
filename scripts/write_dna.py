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


def _ensure_annotations(record):
    record.annotations["molecule_type"] = "DNA"
    if "topology" not in record.annotations:
        record.annotations["topology"] = topology(record)
    return record


def _snapgene_annotated(record):
    """Return the record annotated for the GenBank-SnapGene dialect.

    Uses real Reference objects (not string post-processing) so the file
    re-reads cleanly with no malformed LOCUS or phantom features.
    """
    _ensure_annotations(record)
    record.name = "Exported"
    ref = Reference()
    ref.title = "Direct Submission"
    ref.journal = "Exported from snapgene-dna-design (SnapGene)"
    ref.authors = "."
    refs = list(record.annotations.get("references", []))
    refs.append(ref)
    record.annotations["references"] = refs
    return record


def _strand_char(strand):
    return "-" if strand == -1 else "+"


def write_native_dna(record, out_path):
    """Write a native SnapGene .dna file via sgffp (0-based coords).

    CompoundLocation features are written as multiple segments so that
    wrapped / multi-part features survive a native round trip.
    """
    from sgffp import SgffFeature, SgffObject, SgffSegment, SgffWriter
    sg = SgffObject.new(str(record.seq), topology=topology(record))
    for f in record.features:
        if "primer" in f.type.lower():
            seq = str(f.extract(record.seq))
            if seq:
                sg.add_primer(
                    f.qualifiers.get("label", [f.id or "primer"])[0],
                    seq,
                    bind_position=int(f.location.start),
                    bind_strand=_strand_char(f.location.strand),
                )
            continue
        name = f.qualifiers.get(
            "label", f.qualifiers.get("gene", [f.id or "feature"])
        )[0]
        parts = getattr(f.location, "parts", [f.location])
        segments = [
            SgffSegment(start=int(p.start), end=int(p.end)) for p in parts
        ]
        feature = SgffFeature(
            name=name,
            type=f.type,
            strand=_strand_char(f.location.strand),
            segments=segments,
        )
        sg.features.add(feature)
    SgffWriter.to_file(sg, out_path)
    return out_path


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
