# -*- coding: utf-8 -*-
"""align_seq.py - Pairwise sequence alignment.

Subcommands:
  global   Needleman-Wunsch (end-to-end, for constructs vs reference)
  local    Smith-Waterman (best local match, for finding a read in a larger seq)

Reports identity, gaps, mismatches, and a compact alignment.
"""
import argparse

from sg_common import jprint, load_seq

MATCH, MISMATCH, GAP = 2, -1, -2


def _traceback(score, trace, a, b, i, j, stop_at_zero=False):
    al_a, al_b = [], []
    while i > 0 or j > 0:
        if stop_at_zero and score[i][j] == 0:
            break
        op = trace[i][j]
        if op == "diag":
            al_a.append(a[i - 1]); al_b.append(b[j - 1]); i -= 1; j -= 1
        elif op == "up":
            al_a.append(a[i - 1]); al_b.append("-"); i -= 1
        elif op == "left":
            al_a.append("-"); al_b.append(b[j - 1]); j -= 1
        else:
            break
    return "".join(reversed(al_a)), "".join(reversed(al_b)), i, j


def global_align(a, b):
    n, m = len(a), len(b)
    score = [[0] * (m + 1) for _ in range(n + 1)]
    trace = [[""] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        score[i][0] = i * GAP; trace[i][0] = "up"
    for j in range(1, m + 1):
        score[0][j] = j * GAP; trace[0][j] = "left"
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diag = score[i - 1][j - 1] + (MATCH if a[i - 1] == b[j - 1] else MISMATCH)
            up = score[i - 1][j] + GAP
            left = score[i][j - 1] + GAP
            best = max(diag, up, left)
            score[i][j] = best
            if best == diag:
                trace[i][j] = "diag"
            elif best == up:
                trace[i][j] = "up"
            else:
                trace[i][j] = "left"
    al_a, al_b, _start_i, _start_j = _traceback(score, trace, a, b, n, m)
    return score[n][m], al_a, al_b


def local_align(a, b):
    n, m = len(a), len(b)
    score = [[0] * (m + 1) for _ in range(n + 1)]
    trace = [[""] * (m + 1) for _ in range(n + 1)]
    best_i, best_j, best_score = 0, 0, 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            diag = score[i - 1][j - 1] + (MATCH if a[i - 1] == b[j - 1] else MISMATCH)
            up = score[i - 1][j] + GAP
            left = score[i][j - 1] + GAP
            best = max(0, diag, up, left)
            score[i][j] = best
            if best == diag:
                trace[i][j] = "diag"
            elif best == up:
                trace[i][j] = "up"
            elif best == left:
                trace[i][j] = "left"
            else:
                trace[i][j] = ""
            if best > best_score:
                best_score, best_i, best_j = best, i, j
    al_a, al_b, start_i, start_j = _traceback(
        score, trace, a, b, best_i, best_j, stop_at_zero=True)
    return best_score, al_a, al_b, start_i, best_i, start_j, best_j


def _stats(al_a, al_b):
    ident = sum(1 for x, y in zip(al_a, al_b) if x == y)
    mism = sum(1 for x, y in zip(al_a, al_b) if x != y and x != "-" and y != "-")
    gaps = sum(1 for c in al_a + al_b if c == "-")
    return {
        "length": len(al_a),
        "matches": ident,
        "mismatches": mism,
        "gaps": gaps,
        "identity": round(ident / len(al_a) * 100, 2) if al_a else 0.0,
    }


def _format_pair(al_a, al_b, width=60):
    out = []
    for k in range(0, len(al_a), width):
        a_seg = al_a[k:k + width]
        b_seg = al_b[k:k + width]
        mid = "".join("|" if x == y else (" " if x == "-" or y == "-" else ".") for x, y in zip(a_seg, b_seg))
        out.append(a_seg); out.append(mid); out.append(b_seg); out.append("")
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser(description="Pairwise sequence alignment")
    p.add_argument("source", help="query sequence file / raw seq")
    p.add_argument("reference", help="reference sequence file / raw seq")
    p.add_argument("--mode", choices=["global", "local"], default="global")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    q, _ = load_seq(args.source)
    r, _ = load_seq(args.reference)
    a, b = str(q.seq).upper(), str(r.seq).upper()

    if args.mode == "global":
        sc, al_a, al_b = global_align(a, b)
        extra = {}
    else:
        sc, al_a, al_b, si, ei, sj, ej = local_align(a, b)
        extra = {
            "local_start_query": si + 1 if ei > si else 0,
            "local_end_query": ei,
            "local_start_reference": sj + 1 if ej > sj else 0,
            "local_end_reference": ej,
        }

    stats = _stats(al_a, al_b)
    result = {
        "mode": args.mode,
        "score": sc,
        **stats,
        **extra,
        "alignment": {"query": al_a, "reference": al_b},
    }

    if args.json:
        jprint(result)
    else:
        print("mode=%s score=%d identity=%s%% (matches=%d mismatches=%d gaps=%d)" % (
            args.mode, sc, stats["identity"], stats["matches"], stats["mismatches"], stats["gaps"]))
        if args.mode == "local":
            print("local region: query %d..%d, reference %d..%d" % (
                extra["local_start_query"], extra["local_end_query"],
                extra["local_start_reference"], extra["local_end_reference"]))
        print(_format_pair(al_a, al_b))


if __name__ == "__main__":
    main()
