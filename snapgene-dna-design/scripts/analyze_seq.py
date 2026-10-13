# -*- coding: utf-8 -*-
"""analyze_seq.py - Basic sequence analysis.

Subcommands:
  stats     length, GC%, base counts, ambiguous bases, Tm estimate
  revcomp   reverse complement
  translate translate to protein (all 6 frames or specified frame)
"""
import argparse
import sys
import warnings

from Bio.Seq import Seq

from sg_common import gc_percent, jprint, load_seq

warnings.filterwarnings("ignore", message="Partial codon")


def tm_estimate(seq):
    """Nearest-neighbor Tm (salt corrected 50mM Na+) via Bio.SeqUtils."""
    from Bio.SeqUtils import MeltingTemp as mt
    return round(mt.Tm_NN(str(seq)), 1)


def cmd_stats(record, as_json):
    seq = str(record.seq)
    bases = {b: seq.upper().count(b) for b in "ACGT"}
    ambiguous = sum(1 for c in seq.upper() if c not in "ACGT")
    result = {
        "id": record.id,
        "name": record.name,
        "length": len(seq),
        "gc_percent": round(gc_percent(seq), 2),
        "base_counts": bases,
        "ambiguous_count": ambiguous,
        "ambiguous_fraction": round(ambiguous / len(seq), 4) if seq else 0,
        "tm_estimate_nn": tm_estimate(seq) if len(seq) >= 10 else None,
    }
    if as_json:
        jprint(result)
    else:
        print("length=%d GC=%s%% Tm(NN)~%s" % (
            result["length"], result["gc_percent"], result["tm_estimate_nn"]))
        print("bases:", bases, "ambiguous:", ambiguous)


def cmd_revcomp(record, as_json):
    rc = record.seq.reverse_complement()
    if as_json:
        jprint({"id": record.id, "reverse_complement": str(rc)})
    else:
        print(str(rc))


def cmd_translate(record, as_json, frame=None):
    seq = str(record.seq)
    results = []
    if frame is None:
        frames = list(range(1, 7))  # frames 1..6
    else:
        f = int(frame)
        if f < 1 or f > 6:
            raise SystemExit("frame must be 1..6 (1..3 forward, 4..6 reverse)")
        frames = [f]
    for f in frames:
        # frame 1..3 = forward strand offset 0..2
        # frame 4..6 = reverse strand offset 0..2
        if f <= 3:
            off = f - 1
            aa = Seq(seq[off:]).translate()
            label = "+%d" % f
        else:
            off = f - 4
            rc = Seq(seq).reverse_complement()
            aa = rc[off:].translate()
            label = "-%d" % (f - 3)
        results.append({"frame": label, "aa_length": len(str(aa).rstrip("*")),
                        "protein": str(aa)})
    if as_json:
        payload = {
            "id": record.id,
            "length": len(seq),
            "frame": frame if frame else "all",
            "translations": results,
        }
        jprint(payload)
    else:
        for r in results:
            print("%s frame: %d aa -> %s" % (r["frame"], r["aa_length"], r["protein"][:60]))


def main():
    p = argparse.ArgumentParser(description="Analyze a DNA sequence")
    p.add_argument("source")
    p.add_argument("command", choices=["stats", "revcomp", "translate"])
    p.add_argument("--frame", help="translation frame 1..6 (default: all)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    record, _fmt = load_seq(args.source)
    if args.command == "stats":
        cmd_stats(record, args.json)
    elif args.command == "revcomp":
        cmd_revcomp(record, args.json)
    elif args.command == "translate":
        cmd_translate(record, args.json, args.frame)


if __name__ == "__main__":
    main()
