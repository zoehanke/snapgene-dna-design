# -*- coding: utf-8 -*-
"""characterize_reaction.py - Objective reaction profile for PCR fragments.

This script does NOT recommend reagents. It produces a structured feature
table that later protocol matching can use. No experimental condition is
invented.
"""
import argparse
import json

from Bio.Seq import Seq
from Bio.SeqUtils import gc_fraction

from sg_common import jprint, load_seq, topology
from provenance import source, now_iso, read_version
import pathlib


def _windows(seq, width=40, step=10):
    return [seq[i:i + width] for i in range(0, max(len(seq) - width + 1, 1), step)]


def characterize_fragment(record, fragment_id):
    seq = str(record.seq).upper()
    windows = _windows(seq)
    gc_values = [(gc_fraction(Seq(window)) * 100) for window in windows]
    return {
        "fragment_id": fragment_id,
        "source": record.id or record.name,
        "template_type": "unknown",
        "length": len(seq),
        "topology": topology(record),
        "gc_percent": round(gc_fraction(record.seq) * 100, 2),
        "gc_5prime_40": round(gc_fraction(Seq(seq[:40])) * 100, 2),
        "gc_3prime_40": round(gc_fraction(Seq(seq[-40:])) * 100, 2),
        "max_local_gc_window_40": round(max(gc_values), 2) if gc_values else None,
        "homopolymer_runs": _homopolymer_runs(seq),
        "predicted_difficulty": "not_scored",
        "high_fidelity_required": "unknown",
        "five_prime_tail": "unknown",
        "assembly_method": "unknown",
        "specificity_checked": False,
        "provenance": [source(
            "software", "SnapGene DNA Design characterize_reaction",
            "reaction-profile", version=read_version(), status="verified",
            verification={"method": "unit-tests", "status": "verified"})],
    }


def _homopolymer_runs(seq, threshold=6):
    runs = []
    if not seq:
        return runs
    current = seq[0]
    count = 1
    for base in seq[1:]:
        if base == current:
            count += 1
        else:
            if count >= threshold:
                runs.append({"base": current, "length": count})
            current = base
            count = 1
    if count >= threshold:
        runs.append({"base": current, "length": count})
    return runs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("fragments", nargs="+")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    profiles = []
    for path in args.fragments:
        record, _ = load_seq(path)
        profiles.append(characterize_fragment(record, pathlib.Path(path).stem))
    result = {
        "reaction_profiles": profiles,
        "generated_at": now_iso(),
        "note": "reaction profile only; no reagent or protocol recommendation included",
    }
    if args.json:
        jprint(result)
    else:
        for profile in profiles:
            print("%s: %d bp, GC %.1f%%" % (
                profile["fragment_id"], profile["length"], profile["gc_percent"]))
    return 0


if __name__ == "__main__":
    main()
