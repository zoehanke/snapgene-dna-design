# -*- coding: utf-8 -*-
"""mutagenesis.py - Site-directed mutagenesis simulation.

Methods:
  point        introduce point mutations (pos:base, repeatable)
  insert-codon insert a codon (3 bp) before a 1-based position
  delete-codon delete a codon span (multiple of 3 bp, aligned to the reading
               frame assumed to start at position 1)
  overlap-pcr  NOT implemented: full overlap-extension PCR requires
               mutagenic primer-tail simulation, so the command now fails
               loudly instead of returning the unchanged template.

Point and codon operations validate positions and DNA/IUPAC alphabets before
editing. All successful operations return the mutated sequence, optionally
written as FASTA/GenBank.
"""
import argparse

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from sg_common import DNA_IUPAC, jprint, load_seq


def mutate_point(seq, mutations):
    """Apply 'pos:base' point mutations (1-based closed positions)."""
    parsed = []
    for m in mutations:
        if m.count(":") != 1:
            raise ValueError("invalid mutation %r; expected pos:base" % m)
        pos_s, base_s = m.split(":", 1)
        try:
            pos = int(pos_s)
        except ValueError:
            raise ValueError("invalid mutation position %r" % pos_s)
        if not (1 <= pos <= len(seq)):
            raise ValueError("mutation position out of range: %d (length %d)"
                             % (pos, len(seq)))
        base = base_s.strip().upper()
        if len(base) != 1 or base not in DNA_IUPAC:
            raise ValueError("mutation base must be one DNA/IUPAC symbol: %r"
                             % base_s)
        parsed.append((pos - 1, base))

    s = list(seq)
    for idx, base in parsed:
        s[idx] = base
    return "".join(s)


def insert_codon(seq, pos, codon):
    """Insert a 3-bp codon before 1-based position ``pos``.

    ``pos`` may be 1..len(seq)+1, matching edit_plasmid.py insertion
    semantics (pos=1 prepends, pos=len(seq)+1 appends).
    """
    codon = "".join(str(codon).split()).upper()
    if len(codon) != 3 or any(b not in DNA_IUPAC for b in codon):
        raise ValueError("codon must be exactly 3 DNA/IUPAC bases: %r" % codon)
    if not (1 <= pos <= len(seq) + 1):
        raise ValueError("insert-codon position out of range: %d (expected 1..%d)"
                         % (pos, len(seq) + 1))
    return seq[:pos - 1] + codon + seq[pos - 1:]


def delete_codon(seq, start, end):
    """Delete a 1-based closed interval that is a whole number of codons.

    The coding frame is assumed to start at sequence position 1, so ``start``
    must be a codon boundary (1, 4, 7, ...) and the span length must be a
    multiple of 3 bp.
    """
    if not (1 <= start <= end <= len(seq)):
        raise ValueError("invalid delete-codon interval: %d..%d (sequence length %d)"
                         % (start, end, len(seq)))
    if (start - 1) % 3 != 0:
        raise ValueError(
            "delete-codon start %d is not on a codon boundary; the reading "
            "frame is assumed to start at position 1 (valid starts: 1, 4, 7, ...)"
            % start
        )
    if (end - start + 1) % 3 != 0:
        raise ValueError("delete-codon interval must be a multiple of 3 bp: %d..%d"
                         % (start, end))
    return seq[:start - 1] + seq[end:]


def overlap_pcr(seq, fwd_outer, rev_outer, fwd_inner, rev_inner):
    """Overlap-extension PCR is intentionally not simulated yet.

    A meaningful simulation must place all four primers, apply the mutations
    carried by the inner-primer tails, build both amplicons and assemble them
    over the complementary overlap. Returning the unchanged template (the
    v0.3.0 behavior) was misleading, so this function now refuses.
    """
    raise ValueError(
        "overlap-pcr simulation is not implemented: it would need to place "
        "all four primers and assemble mutagenic overlap tails. Use "
        "edit_plasmid.py --op mutate for explicit point mutations instead."
    )


def main():
    p = argparse.ArgumentParser(description="Site-directed mutagenesis")
    p.add_argument("source")
    p.add_argument("--op", required=True,
                   choices=["point", "insert-codon", "delete-codon", "overlap-pcr"])
    p.add_argument("--mutation", action="append", default=[],
                   help="'pos:base' for point mutation (repeatable)")
    p.add_argument("--pos", type=int,
                   help="1-based position before which the codon is inserted (insert-codon)")
    p.add_argument("--codon", help="3-bp codon to insert (insert-codon)")
    p.add_argument("--start", type=int,
                   help="delete start, 1-based codon boundary 1/4/7/... (delete-codon)")
    p.add_argument("--end", type=int, help="delete end, 1-based (delete-codon)")
    p.add_argument("--fwd-outer", help="overlap-pcr: outer forward primer")
    p.add_argument("--rev-outer", help="overlap-pcr: outer reverse primer")
    p.add_argument("--fwd-inner", help="overlap-pcr: inner forward primer (mutagenic)")
    p.add_argument("--rev-inner", help="overlap-pcr: inner reverse primer (mutagenic)")
    p.add_argument("--out", help="output FASTA path")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    record, _fmt = load_seq(args.source)
    seq = str(record.seq).upper()
    notes = []

    try:
        if args.op == "point":
            if not args.mutation:
                raise ValueError("point requires --mutation pos:base")
            new_seq = mutate_point(seq, args.mutation)
        elif args.op == "insert-codon":
            if args.pos is None or not args.codon:
                raise ValueError("insert-codon requires --pos and --codon")
            new_seq = insert_codon(seq, args.pos, args.codon)
        elif args.op == "delete-codon":
            if args.start is None or args.end is None:
                raise ValueError("delete-codon requires --start and --end")
            new_seq = delete_codon(seq, args.start, args.end)
        else:
            if not (args.fwd_outer and args.rev_outer and args.fwd_inner and args.rev_inner):
                raise ValueError("overlap-pcr requires all four primers")
            new_seq, _notes = overlap_pcr(
                seq, args.fwd_outer, args.rev_outer, args.fwd_inner, args.rev_inner)
    except ValueError as e:
        raise SystemExit(str(e))

    out = {
        "op": args.op,
        "length_before": len(seq),
        "length_after": len(new_seq),
        "sequence": new_seq,
        "notes": notes,
    }

    if args.out:
        rec = SeqRecord(Seq(new_seq), id="mutant", name="mutant",
                        description="mutagenesis %s" % args.op)
        with open(args.out, "w", encoding="utf-8") as fh:
            SeqIO.write(rec, fh, "fasta")
        out["out_file"] = args.out

    if args.json:
        jprint(out)
    else:
        print("%s: %d -> %d bp" % (args.op, len(seq), len(new_seq)))
        print("sequence:")
        print(new_seq)
        for n in notes:
            print("  note: %s" % n)


if __name__ == "__main__":
    main()
