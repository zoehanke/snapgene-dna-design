# -*- coding: utf-8 -*-
"""edit_plasmid.py - True plasmid editing with feature migration.

Operations (1-based closed coordinates, matching SnapGene):
  insert       insert a sequence before a position
  delete       delete an interval
  replace      replace an interval with a new sequence
  mutate       single-base substitution (or multiple, comma-separated)
  linearize    cut a circular plasmid at a position (rewrites origin)
  circularize  mark a linear sequence as circular
  rotate       rotate a circular plasmid so origin moves to a new position

Features are migrated part-by-part, including CompoundLocation and wrapped
origin features, through the v0.3 ConstructModel.
Output is a new record written as GenBank (--out), plus JSON summary.
"""
import argparse
from Bio import SeqIO

from construct_model import ConstructModel
from sg_common import DNA_IUPAC, jprint, load_seq, normalize_dna, topology


def op_insert(record, pos, seq):
    if not (1 <= pos <= len(record.seq) + 1):
        raise ValueError(
            "insert position out of range: %d (expected 1..%d)"
            % (pos, len(record.seq) + 1)
        )
    seq = normalize_dna(seq, "insert sequence")
    return ConstructModel(record).insert(pos - 1, seq).to_record()


def op_delete(record, start, end):
    if not (1 <= start <= end <= len(record.seq)):
        raise ValueError(
            "invalid delete interval: %d..%d (sequence length %d)"
            % (start, end, len(record.seq))
        )
    return ConstructModel(record).delete(start - 1, end).to_record()


def op_replace(record, start, end, seq):
    seq = normalize_dna(seq, "replacement sequence")
    if not (1 <= start <= end <= len(record.seq)):
        raise ValueError(
            "invalid replace interval: %d..%d (sequence length %d)"
            % (start, end, len(record.seq))
        )
    return ConstructModel(record).replace(start - 1, end, seq).to_record()


def op_mutate(record, mutations):
    parsed = []
    seq_length = len(record.seq)
    for m in mutations:
        if m.count(":") != 1:
            raise ValueError("invalid mutation %r; expected pos:base" % m)
        pos, base = m.split(":", 1)
        pos = int(pos)
        if not (1 <= pos <= seq_length):
            raise ValueError("mutation position out of range: %d" % pos)
        base = base.upper()
        if len(base) != 1 or base not in DNA_IUPAC:
            raise ValueError(
                "mutation base must be one DNA/IUPAC symbol: %r" % base
            )
        parsed.append((pos - 1, base))
    return ConstructModel(record).mutate(parsed).to_record()


def op_linearize(record, pos):
    """Cut circular at pos (1-based): new seq = [pos..end] + [1..pos-1]."""
    n = len(record.seq)
    if topology(record) != "circular":
        raise ValueError("linearize requires a circular input record")
    if not (1 <= pos <= n):
        raise ValueError("linearize position out of range: %d" % pos)
    return ConstructModel(record).rotate(pos - 1, topology="linear").to_record()


def op_circularize(record):
    return ConstructModel(record).set_topology("circular").to_record()


def op_rotate(record, pos):
    if topology(record) != "circular":
        raise ValueError("rotate requires a circular input record")
    if not (1 <= pos <= len(record.seq)):
        raise ValueError("rotate position out of range: %d" % pos)
    return ConstructModel(record).rotate(pos - 1, topology="circular").to_record()


def main():
    p = argparse.ArgumentParser(description="Edit a plasmid (with feature migration)")
    p.add_argument("source")
    p.add_argument("--op", required=True,
                   choices=["insert", "delete", "replace", "mutate",
                            "linearize", "circularize", "rotate"])
    p.add_argument("--pos", type=int, help="position (insert/linearize/rotate)")
    p.add_argument("--start", type=int, help="interval start (delete/replace)")
    p.add_argument("--end", type=int, help="interval end (delete/replace)")
    p.add_argument("--seq", help="sequence to insert/replace (insert/replace)")
    p.add_argument("--mutation", action="append", default=[],
                   help="mutation 'pos:base' (mutate, repeatable)")
    p.add_argument("--out", required=True, help="output GenBank path")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    record, _fmt = load_seq(args.source)

    if args.op == "insert":
        if args.pos is None or not args.seq:
            raise SystemExit("insert requires --pos and --seq")
        try:
            result = op_insert(record, args.pos, args.seq)
        except ValueError as e:
            raise SystemExit(str(e))
    elif args.op == "delete":
        if args.start is None or args.end is None:
            raise SystemExit("delete requires --start and --end")
        try:
            result = op_delete(record, args.start, args.end)
        except ValueError as e:
            raise SystemExit(str(e))
    elif args.op == "replace":
        if args.start is None or args.end is None or not args.seq:
            raise SystemExit("replace requires --start --end --seq")
        try:
            result = op_replace(record, args.start, args.end, args.seq)
        except ValueError as e:
            raise SystemExit(str(e))
    elif args.op == "mutate":
        if not args.mutation:
            raise SystemExit("mutate requires --mutation pos:base")
        try:
            result = op_mutate(record, args.mutation)
        except (ValueError, TypeError) as e:
            raise SystemExit(str(e))
    elif args.op == "linearize":
        if args.pos is None:
            raise SystemExit("linearize requires --pos")
        try:
            result = op_linearize(record, args.pos)
        except ValueError as e:
            raise SystemExit(str(e))
    elif args.op == "circularize":
        result = op_circularize(record)
    else:  # rotate
        if args.pos is None:
            raise SystemExit("rotate requires --pos")
        try:
            result = op_rotate(record, args.pos)
        except ValueError as e:
            raise SystemExit(str(e))

    with open(args.out, "w", encoding="utf-8") as fh:
        SeqIO.write(result, fh, "genbank")

    out = {
        "op": args.op,
        "out_file": args.out,
        "length_before": len(record.seq),
        "length_after": len(result.seq),
        "topology": topology(result),
        "feature_count": len(result.features),
    }
    if args.json:
        jprint(out)
    else:
        print("%s: %d -> %d bp (%s), %d features -> %s" % (
            args.op, len(record.seq), len(result.seq), topology(result),
            len(result.features), args.out))


if __name__ == "__main__":
    main()
