# -*- coding: utf-8 -*-
"""parse_dna.py - Parse a SnapGene .dna / GenBank / FASTA file into structured JSON.

Outputs: sequence metadata (length, topology), features (1-based closed coords),
primers (when available), and notes/description.
"""
import argparse
import sys

from sg_common import jprint, load_seq, features_to_dict, topology


def parse_primers(record):
    """Extract primers if present in qualifiers of features named primer."""
    primers = []
    for f in record.features:
        if f.type == "primer_bind" or "primer" in f.type.lower():
            quals = {k: v for k, v in f.qualifiers.items()}
            primers.append({
                "name": f.qualifiers.get("label", f.qualifiers.get("gene", ["primer"]))[0],
                "type": f.type,
                "start": int(f.location.start) + 1,
                "end": int(f.location.end),
                "strand": 0 if f.location.strand is None else int(f.location.strand),
                "sequence": str(f.extract(record.seq)),
                "qualifiers": {k: [str(x) for x in v] for k, v in quals.items()},
            })
    return primers


def main():
    p = argparse.ArgumentParser(description="Parse sequence file into structured JSON")
    p.add_argument("source", help=".dna / .gb / .fa / .embl file path")
    p.add_argument("--seq-limit", type=int, default=0,
                   help="include first N bp of sequence in output (0 = omit)")
    p.add_argument("--json", action="store_true", help="force JSON output")
    args = p.parse_args()

    record, fmt = load_seq(args.source)
    seq = str(record.seq)
    result = {
        "source": args.source,
        "format": fmt,
        "id": record.id,
        "name": record.name,
        "description": record.description[:500] if record.description else "",
        "length": len(seq),
        "topology": topology(record),
        "dna": all(c.upper() in "ACGTN" for c in seq),
        "features": features_to_dict(record),
        "primers": parse_primers(record),
        "feature_count": len(record.features),
    }
    if args.seq_limit and args.seq_limit > 0:
        result["sequence_preview"] = seq[:args.seq_limit]

    if args.json:
        jprint(result)
    else:
        print("== %s (%s) ==" % (record.name or record.id, fmt))
        print("length: %d  topology: %s" % (len(seq), topology(record)))
        print("description: %s" % (record.description or ""))
        print("features (%d):" % len(record.features))
        for f in features_to_dict(record):
            print("  %s  %s  %d..%d  strand=%d  %s" % (
                f["type"], f["name"], f["start"], f["end"], f["strand"],
                ",".join(k for k in list(f["qualifiers"])[:4])))
        prims = parse_primers(record)
        if prims:
            print("primers (%d):" % len(prims))
            for pr in prims:
                print("  %s  %d..%d  %s" % (pr["name"], pr["start"], pr["end"], pr["sequence"]))


if __name__ == "__main__":
    main()
