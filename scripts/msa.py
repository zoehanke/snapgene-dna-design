# -*- coding: utf-8 -*-
"""msa.py - Multiple sequence alignment (progressive / star).

Reads multiple sequences (multi-FASTA or multiple files), performs a
progressive alignment using pairwise global alignment (Needleman-Wunsch),
and outputs the alignment as aligned FASTA or a compact block.

Method: choose the longest sequence as the initial profile, then align each
remaining sequence to the running profile, inserting gaps as needed.
"""
import argparse

from align_seq import global_align
from sg_common import jprint, load_sequence_records


def load_sequences(paths):
    return [(rec.id, str(rec.seq)) for rec in load_sequence_records(paths)]


def _align_profile(profile, seq):
    """Align a single sequence to a profile (list of aligned strings).

    Uses the first (longest) profile sequence as the anchor. Returns the
    updated profile plus the newly aligned sequence.
    """
    anchor = profile[0]
    _score, al_anchor, al_seq = global_align(anchor.replace("-", ""), seq)
    # A gap in the anchor can contain real bases in another profile row.
    # Merge insertion columns at each anchor boundary, never discard them.
    out = [[] for _ in range(len(profile) + 1)]
    old_i = new_i = 0
    while old_i < len(anchor) or new_i < len(al_anchor):
        old_start, new_start = old_i, new_i
        while old_i < len(anchor) and anchor[old_i] == "-":
            old_i += 1
        while new_i < len(al_anchor) and al_anchor[new_i] == "-":
            new_i += 1
        old_gap, new_gap = old_i - old_start, new_i - new_start
        width = max(old_gap, new_gap)
        for index, row in enumerate(profile):
            out[index].append(row[old_start:old_i] + "-" * (width - old_gap))
        out[-1].append(al_seq[new_start:new_i] + "-" * (width - new_gap))
        if old_i < len(anchor):
            for index, row in enumerate(profile):
                out[index].append(row[old_i])
            out[-1].append(al_seq[new_i])
            old_i += 1
            new_i += 1
    return ["".join(row) for row in out]


def msa(seqs):
    """Progressive MSA. Returns (list of (id, aligned), consensus)."""
    if len(seqs) < 2:
        return seqs, seqs[0][1] if seqs else ""
    seqs = sorted(seqs, key=lambda x: -len(x[1]))
    profile = [seqs[0][1]]
    for _id, s in seqs[1:]:
        profile = _align_profile(profile, s)
    # consensus
    width = len(profile[0])
    consensus = []
    for i in range(width):
        col = [row[i] for row in profile if row[i] != "-"]
        if not col:
            consensus.append("-")
        else:
            # Stable tie policy, independent of Python's randomized hash seed.
            consensus.append(max(sorted(set(col)), key=col.count))
    return [(seqs[i][0], profile[i]) for i in range(len(seqs))], "".join(consensus)


def _format_block(aligned, consensus, width=60):
    lines = []
    for i in range(0, len(consensus), width):
        for _id, row in aligned:
            lines.append("%-20s %s" % (_id[:20], row[i:i + width]))
        lines.append("%-20s %s" % ("consensus", consensus[i:i + width]))
        lines.append("")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="Multiple sequence alignment")
    p.add_argument("sources", nargs="+", help="multi-FASTA files or individual seq files")
    p.add_argument("--out-fasta", help="write aligned FASTA")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    seqs = load_sequences(args.sources)
    aligned, consensus = msa(seqs)

    result = {
        "count": len(aligned),
        "alignment_length": len(consensus),
        "consensus": consensus,
        "sequences": [{"id": i, "aligned": a} for i, a in aligned],
    }

    if args.out_fasta:
        with open(args.out_fasta, "w", encoding="utf-8") as fh:
            for _id, row in aligned:
                fh.write(">%s\n%s\n" % (_id, row))
        result["out_file"] = args.out_fasta

    if args.json:
        jprint(result)
    else:
        print("%d sequences, %d columns" % (len(aligned), len(consensus)))
        print(_format_block(aligned, consensus))


if __name__ == "__main__":
    main()
