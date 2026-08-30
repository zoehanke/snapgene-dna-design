# -*- coding: utf-8 -*-
"""msa.py - Multiple sequence alignment (progressive / star).

Reads multiple sequences (multi-FASTA or multiple files), performs a
progressive alignment using pairwise global alignment (Needleman-Wunsch),
and outputs the alignment as aligned FASTA or a compact block.

Method: choose the longest sequence as the initial profile, then align each
remaining sequence to the running profile, inserting gaps as needed.
"""
import argparse

from Bio import SeqIO

from align_seq import global_align
from sg_common import jprint, load_seq


def load_sequences(paths):
    seqs = []
    for path in paths:
        try:
            for rec in SeqIO.parse(path, "fasta"):
                seqs.append((rec.id, str(rec.seq).upper()))
        except Exception:
            rec, _ = load_seq(path)
            seqs.append((rec.id or "seq", str(rec.seq).upper()))
    return seqs


def _align_profile(profile, seq):
    """Align a single sequence to a profile (list of aligned strings).

    Uses the first (longest) profile sequence as the anchor. Returns the
    updated profile plus the newly aligned sequence.
    """
    anchor = profile[0]
    _score, al_anchor, al_seq = global_align(anchor, seq)
    # rebase existing profile rows onto the new anchor alignment
    new_profile = []
    for row in profile:
        new_profile.append(_rebase(row, anchor, al_anchor))
    new_profile.append(al_seq)
    return new_profile


def _rebase(row, old_anchor, new_anchor):
    """Rebase an already-aligned row onto a new anchor alignment.

    Both old_anchor and new_anchor are the SAME sequence with different
    gap patterns; we map each row position through the old->new gap map.
    """
    out = []
    old_i = new_i = 0
    # old_i walks old_anchor (gaps present), new_i walks new_anchor
    for ch in new_anchor:
        if ch == "-":
            out.append("-")
            continue
        # consume old_anchor until we hit a non-gap (== this base)
        while old_i < len(old_anchor) and old_anchor[old_i] == "-":
            old_i += 1
        if old_i < len(old_anchor):
            out.append(row[old_i])
            old_i += 1
    return "".join(out)


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
            consensus.append(max(set(col), key=col.count))
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
