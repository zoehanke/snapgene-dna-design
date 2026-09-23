# -*- coding: utf-8 -*-
"""assemble_contig.py - Greedy contig assembly from sequencing reads.

Finds suffix-prefix overlaps between reads and greedily merges the highest
overlaps into contigs (CAP3-style assembly, simplified).

Outputs merged contig sequences. Per-read placement coordinates are not
tracked by this simplified assembler; use the reported merged contig IDs
to reconstruct read membership.
"""
import argparse

from sg_common import jprint, load_sequence_records


def load_reads(paths):
    return [(rec.id, str(rec.seq)) for rec in load_sequence_records(paths)]


def best_overlap(a, b, min_overlap):
    """Largest suffix-of-a == prefix-of-b length (and vice versa).

    Returns (len, orientation) where orientation is 'ab' (b extends a) or
    'ba' (a extends b)."""
    best = (0, None)
    for L in range(min(len(a), len(b)), min_overlap - 1, -1):
        if a[-L:] == b[:L]:
            return (L, "ab")
        if b[-L:] == a[:L]:
            return (L, "ba")
    return best


def assemble(reads, min_overlap=20):
    """Greedy exact, same-strand assembly. Returns (id, sequence) pairs."""
    if min_overlap < 1:
        raise ValueError("min_overlap must be positive")
    if not reads or any(not seq for _id, seq in reads):
        raise ValueError("non-empty reads are required")

    # iterative greedy merge
    # work with a list of fragments (id -> seq); merge into larger fragments
    frags = list(reads)  # [(id, seq)]
    changed = True
    while changed and len(frags) > 1:
        changed = False
        best = (0, -1, -1, None)
        for i in range(len(frags)):
            for j in range(len(frags)):
                if i == j:
                    continue
                L, ori = best_overlap(frags[i][1], frags[j][1], min_overlap)
                if L > best[0]:
                    best = (L, i, j, ori)
        L, i, j, ori = best
        if L <= 0:
            break
        id_a, sa = frags[i]
        id_b, sb = frags[j]
        if ori == "ab":
            merged = sa + sb[L:]
            merged_id = id_a + "+" + id_b
        else:
            merged = sb + sa[L:]
            merged_id = id_b + "+" + id_a
        # replace
        new_frags = []
        merged_inserted = False
        for k, (fid, fs) in enumerate(frags):
            if k in (i, j):
                if not merged_inserted:
                    new_frags.append((merged_id, merged))
                    merged_inserted = True
                continue
            new_frags.append((fid, fs))
        frags = new_frags
        changed = True

    # record placements by walking merged ids
    contigs = frags
    return contigs


def main():
    p = argparse.ArgumentParser(description="Greedy contig assembly")
    p.add_argument("--reads", nargs="+", required=True, help="read FASTA file(s)")
    p.add_argument("--min-overlap", type=int, default=20, help="minimum overlap bp (default 20)")
    p.add_argument("--out", help="write contigs FASTA")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    reads = load_reads(args.reads)
    contigs = assemble(reads, args.min_overlap)

    result = {
        "method": "greedy-exact-same-strand-overlap",
        "limitations": ["No read quality or error correction; reverse-complement reads are not inferred."],
        "read_count": len(reads),
        "contig_count": len(contigs),
        "contigs": [{"id": cid, "length": len(seq), "sequence": seq}
                    for cid, seq in contigs],
    }

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            for i, (cid, seq) in enumerate(contigs):
                fh.write(">contig_%d (%s)\n%s\n" % (i + 1, cid, seq))
        result["out_file"] = args.out

    if args.json:
        jprint(result)
    else:
        print("%d reads -> %d contig(s)" % (len(reads), len(contigs)))
        for i, (cid, seq) in enumerate(contigs):
            print("  contig_%d (%s): %d bp" % (i + 1, cid, len(seq)))


if __name__ == "__main__":
    main()
