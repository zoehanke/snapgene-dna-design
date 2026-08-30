# -*- coding: utf-8 -*-
"""align_sanger.py - Align Sanger sequencing reads to a reference construct.

Verifies that sequenced reads match the reference. Reports:
  - coverage (which reference positions are covered by at least one read)
  - per-read mismatch and indel counts
  - consensus confirmation status per reference position
  - a coverage summary (covered / uncovered spans)

Reads may be supplied as one multi-record FASTA (--reads) or multiple files.
"""
import argparse

from Bio import SeqIO
from Bio.Seq import Seq

from align_seq import global_align, local_align, _stats
from sg_common import jprint, load_seq


def load_reads(paths):
    reads = []
    for path in paths:
        try:
            def parse_with_encoding(encoding):
                with open(path, "r", encoding=encoding) as handle:
                    return list(SeqIO.parse(handle, "fasta"))
            try:
                records = parse_with_encoding("utf-8-sig")
            except UnicodeDecodeError:
                records = parse_with_encoding("latin-1")
            if not records:
                raise ValueError("no FASTA reads")
            for rec in records:
                reads.append((rec.id, str(rec.seq).upper()))
        except Exception:
            rec, _fmt = load_seq(path)
            reads.append((rec.id or "read", str(rec.seq).upper()))
    return reads


def align_read_to_ref(read, ref):
    """Local-align a read to the reference; return covered span and stats."""
    sc, al_r, al_ref, _read_start, _read_end, ref_start0, ref_end = local_align(
        read, ref)
    stats = _stats(al_r, al_ref)
    ref_start = ref_start0 + 1 if ref_end > ref_start0 else 0
    return {
        "read": read[:20] + ("..." if len(read) > 20 else ""),
        "score": sc,
        "ref_start": ref_start,
        "ref_end": ref_end,
        **stats,
    }


def main():
    p = argparse.ArgumentParser(description="Align Sanger reads to a reference construct")
    p.add_argument("reference", help="reference construct file / raw seq")
    p.add_argument("--reads", nargs="+", required=True,
                   help="Sanger read file(s) (FASTA)")
    p.add_argument("--min-identity", type=float, default=80.0,
                   help="minimum identity %% to confirm a read (default 80)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    ref_rec, _ = load_seq(args.reference)
    ref = str(ref_rec.seq).upper()
    n = len(ref)

    reads = load_reads(args.reads)
    results = []
    covered = [0] * n  # 0-based coverage track
    for rid, rseq in reads:
        res = align_read_to_ref(rseq, ref)
        res["id"] = rid
        res["confirmed"] = res["identity"] >= args.min_identity
        # mark coverage (0-based [ref_start-1, ref_end))
        for pos in range(max(0, res["ref_start"] - 1), min(n, res["ref_end"])):
            covered[pos] += 1
        results.append(res)

    # coverage summary: contiguous covered spans
    spans = []
    i = 0
    while i < n:
        if covered[i] > 0:
            j = i
            while j < n and covered[j] > 0:
                j += 1
            spans.append({"start": i + 1, "end": j})
            i = j
        else:
            i += 1

    covered_bp = sum(1 for c in covered if c > 0)
    report = {
        "reference": ref_rec.name or ref_rec.id,
        "reference_length": n,
        "reads": results,
        "coverage_percent": round(covered_bp / n * 100, 2) if n else 0.0,
        "covered_spans": spans,
        "uncovered_spans": [{"start": i + 1, "end": j} for (i, j) in
                            [(a - 1, b - 1) for a, b in _complement_spans(spans, n)]],
    }

    if args.json:
        jprint(report)
    else:
        print("reference %s (%d bp), coverage %.1f%%" % (
            report["reference"], n, report["coverage_percent"]))
        for r in results:
            status = "CONFIRMED" if r["confirmed"] else "REJECTED"
            print("  [%s] %s: identity %.1f%% (matches=%d mismatches=%d gaps=%d) ref %d..%d" % (
                status, r["id"], r["identity"], r["matches"], r["mismatches"], r["gaps"],
                r["ref_start"], r["ref_end"]))
        if report["uncovered_spans"]:
            print("  uncovered:", report["uncovered_spans"])


def _complement_spans(spans, n):
    """Return 0-based [start,end) uncovered spans given covered spans (1-based)."""
    out = []
    cursor = 1
    for s in spans:
        if s["start"] > cursor:
            out.append((cursor - 1, s["start"] - 1))
        cursor = s["end"] + 1
    if cursor <= n:
        out.append((cursor - 1, n))
    return out


if __name__ == "__main__":
    main()
