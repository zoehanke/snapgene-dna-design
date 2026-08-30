# -*- coding: utf-8 -*-
"""primer_qc.py - Pure-Python primer quality analysis.

Implements the structural checks that Primer3 provides for primer
self-dimer / hairpin / pair-dimer problems, using only standard library
algorithms (no native extension, no Bio imports, fully portable):

  hairpin            intramolecular stem-loop, scored by longest stem + loop
  self_dimer         3' anchoring, scored by 3' complement strength
  pair_dimer         forward/reverse 3' cross-complement (primer-dimer)

Each check returns {score, structure, positions} where higher score = worse.
A primer is considered "at risk" if its score exceeds a threshold.
"""

# Minimum stem length to count a hairpin / dimer.
MIN_STEM = 3
# 3' anchor length for dimer scoring.
ANCHOR = 4


def _complement_base(b):
    """Complement a base; N (ambiguous) does not pair with anything."""
    return {"A": "T", "T": "A", "G": "C", "C": "G"}.get(b.upper(), "")


def _complement(s):
    return "".join(_complement_base(b) for b in s)


def score_hairpin(seq):
    """Score the strongest hairpin (stem-loop) in a primer.

    Returns (score, stem_len, loop_len, stem_start, stem_end).
    A hairpin of stem >= 4 and loop >= 3 is penalized.
    """
    s = seq.upper()
    n = len(s)
    best = (0, 0, 0, 0, 0)
    for i in range(n - MIN_STEM):
        for j in range(i + MIN_STEM, n):
            stem = 0
            while (i + stem < j - stem and
                   _complement_base(s[j - stem]) == s[i + stem]):
                stem += 1
            if stem < MIN_STEM:
                continue
            loop = j - i - 2 * stem + 1
            if loop < 1:
                continue
            # score: 10 per base pair in stem + 5 bonus if stem >= 4
            score = stem * 10 + (5 if stem >= 4 else 0) + min(loop, 5)
            if score > best[0]:
                best = (score, stem, loop, i, j)
    return best


def score_self_dimer(seq):
    """Score self-dimer: one primer region pairs with its reverse complement.

    Returns (score, aligned_length, pos_a, pos_b). 3' anchoring is penalized
    extra: alignment involving the 3' end is more dangerous.
    """
    s = seq.upper()
    # Self-dimer alignment is seq[5'->3'] vs its own reverse complement:
    # rc[j] = complement(s[n-1-j]), so a run of matches means a duplex.
    rc = _complement(s[::-1])
    n = len(s)
    best = (0, 0, 0, 0)
    for i in range(n):
        for j in range(n):
            length = 0
            while (i + length < n and j + length < n and
                   rc[j + length] == s[i + length]):
                length += 1
            if length < MIN_STEM:
                continue
            # 3' anchoring: if either region touches the 3' end (last ANCHOR bp)
            anchor = (i + length >= n - ANCHOR or j + length >= n - ANCHOR)
            score = length * 10 + (8 if anchor else 0)
            if score > best[0]:
                best = (score, length, i, j)
    return best


def score_pair_dimer(fwd, rev):
    """Score forward/reverse primer-dimer (3' cross complementarity).

    The dimer forms between the 3' ends: fwd 3' tail anneals to rev 3' tail.
    We compare the forward primer against the reverse complement of the
    reverse primer's reversed sequence (i.e., rev as it would read 3'->5').

    Returns (score, aligned_length, fwd_pos, rev_pos)."""
    f = fwd.upper()
    # reverse primer read 3'->5' for annealing to fwd
    r = _complement(rev[::-1]).upper()
    nf, nr = len(f), len(r)
    best = (0, 0, 0, 0)
    for i in range(nf):
        for j in range(nr):
            length = 0
            while (i + length < nf and j + length < nr and
                   r[j + length] == f[i + length]):
                length += 1
            if length < MIN_STEM:
                continue
            f_anchor = i + length >= nf - ANCHOR
            r_anchor = j + length >= nr - ANCHOR
            score = length * 10 + (8 if (f_anchor or r_anchor) else 0)
            if score > best[0]:
                best = (score, length, i, j)
    return best


def analyze_primers(fwd, rev):
    """Return a QC report dict for a forward/reverse primer pair."""
    hp_f = score_hairpin(fwd)
    hp_r = score_hairpin(rev)
    sd_f = score_self_dimer(fwd)
    sd_r = score_self_dimer(rev)
    pd = score_pair_dimer(fwd, rev)
    return {
        "forward": {
            "hairpin": {"score": hp_f[0], "stem": hp_f[1], "loop": hp_f[2]},
            "self_dimer": {"score": sd_f[0], "length": sd_f[1]},
        },
        "reverse": {
            "hairpin": {"score": hp_r[0], "stem": hp_r[1], "loop": hp_r[2]},
            "self_dimer": {"score": sd_r[0], "length": sd_r[1]},
        },
        "pair_dimer": {"score": pd[0], "length": pd[1]},
        "risk_flags": [],
    }


def flag_risks(report):
    """Append human-readable risk flags to a report dict (mutates)."""
    flags = report["risk_flags"]
    for side in ("forward", "reverse"):
        hp = report[side]["hairpin"]
        sd = report[side]["self_dimer"]
        if hp["score"] >= 40:
            flags.append("%s: strong hairpin (stem %d, loop %d)" %
                         (side, hp["stem"], hp["loop"]))
        if sd["score"] >= 40:
            flags.append("%s: self-dimer (%d bp)" % (side, sd["length"]))
    pd = report["pair_dimer"]
    if pd["score"] >= 40:
        flags.append("pair dimer (%d bp)" % pd["length"])
    return report
