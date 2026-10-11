# -*- coding: utf-8 -*-
"""align_sanger.py - Align Sanger sequencing reads to a reference construct.

Verifies that sequenced reads match the reference. Reports:
  - coverage (which reference positions are covered by at least one read)
  - per-read mismatch and indel counts
  - positions with unambiguous sequence matches (not quality-based consensus)
  - a coverage summary (covered / uncovered spans)

Reads may be supplied as one multi-record FASTA (--reads) or multiple files.
"""
import argparse

from Bio.Seq import Seq

from align_seq import local_align, _stats
from sg_common import jprint, load_seq, load_sequence_records, normalize_dna


def load_reads(paths):
    return [(rec.id, str(rec.seq)) for rec in load_sequence_records(paths)]


def align_read_to_ref(read, ref):
    """Compare both read orientations; report bases, not just bounding spans.

    This is a sequence comparison, without chromatogram quality assessment.
    A local hit is not accepted until the caller checks its read coverage.
    """
    read = normalize_dna(read, "read")
    ref = normalize_dna(ref, "reference")
    orientations = [("+", read), ("-", str(Seq(read).reverse_complement()))]
    candidates = [(strand, local_align(sequence, ref)) for strand, sequence in orientations]
    strand, alignment = max(candidates, key=lambda item: item[1][0])
    sc, al_r, al_ref, read_start, read_end, ref_start0, ref_end = alignment
    stats = _stats(al_r, al_ref)
    covered, matched, mismatched, deleted = [], [], [], []
    position = ref_start0
    for query_base, ref_base in zip(al_r, al_ref):
        if ref_base == "-":
            continue
        position += 1
        if query_base == "-":
            deleted.append(position)
        elif query_base in "ACGT" and ref_base in "ACGT":
            covered.append(position)
            if query_base == ref_base:
                matched.append(position)
            else:
                mismatched.append(position)
    # Ambiguous symbols are not confirmed bases even when N == N.
    stats["matches"] = len(matched)
    stats["identity"] = round(100 * len(matched) / len(al_r), 2) if al_r else 0.0
    ref_start = ref_start0 + 1 if ref_end > ref_start0 else 0
    return {
        "read": read[:20] + ("..." if len(read) > 20 else ""),
        "read_length": len(read),
        "strand": strand,
        "aligned_read_percent": round(100 * (read_end - read_start) / len(read), 2),
        "covered_positions": covered,
        "matched_positions": matched,
        "mismatch_positions": mismatched,
        "deletion_positions": deleted,
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
    p.add_argument("--min-read-coverage", type=float, default=80.0,
                   help="minimum %% of each read aligned (default 80)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    if not 0 <= args.min_identity <= 100 or not 0 <= args.min_read_coverage <= 100:
        p.error("identity and read coverage thresholds must be between 0 and 100")

    ref_rec, _ = load_seq(args.reference)
    ref = str(ref_rec.seq).upper()
    n = len(ref)

    reads = load_reads(args.reads)
    results = []
    covered = [0] * n  # 0-based coverage track
    matched = [0] * n
    for rid, rseq in reads:
        res = align_read_to_ref(rseq, ref)
        res["id"] = rid
        res["confirmed"] = bool(res["covered_positions"]) and (
            res["identity"] >= args.min_identity and
            res["aligned_read_percent"] >= args.min_read_coverage)
        if res["confirmed"]:
            for pos in res["covered_positions"]:
                covered[pos - 1] += 1
            for pos in res["matched_positions"]:
                matched[pos - 1] += 1
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
        "matched_reference_percent": round(sum(bool(c) for c in matched) / n * 100, 2) if n else 0.0,
        "coverage_semantics": "Unambiguous bases in reads meeting identity and aligned-read thresholds; mismatches remain covered, deletions do not.",
        "limitations": ["No chromatogram quality analysis, repeat-placement uniqueness assessment or circular-origin alignment; read acceptance is not full-construct sequence confirmation."],
        "covered_spans": spans,
        "uncovered_spans": [{"start": i + 1, "end": j}
                            for i, j in _complement_spans(spans, n)],
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
