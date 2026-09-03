# -*- coding: utf-8 -*-
"""core/tools/amplification.py - Atomic PCR amplification and primer tools.

Simulates PCR with exact or 5'-overhang primers, finds primer binding sites,
and calculates amplicon sequences.
"""
from __future__ import annotations

import hashlib
import pathlib
from typing import Any

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.tools.inspection import _load_record


def _find_primer_binding(
    template: str,
    primer: str,
    min_binding_len: int = 15,
    circular: bool = False,
) -> list[dict[str, Any]]:
    """Find binding sites for primer on template (including 5'-tail overhangs)."""
    t = template.upper()
    p = primer.upper()
    n = len(t)
    hits = []

    # Test full primer down to min_binding_len 3' binding core
    for core_len in range(len(p), min_binding_len - 1, -1):
        core = p[-core_len:]  # 3' binding core of primer
        core_rc = str(Seq(core).reverse_complement())
        tail = p[:-core_len]  # 5' non-binding tail (overhang, tag, restriction site)

        # Search top strand (+1) for forward primer
        # Search bottom strand (-1) for reverse primer (represented by core_rc on top strand)
        search_seq = (t + t[:len(core) - 1]) if circular else t
        max_idx = n if circular else (n - len(core) + 1)

        found_this_len = False
        for pos in range(max_idx):
            sub = search_seq[pos : pos + len(core)]
            if sub == core:
                hits.append({
                    "strand": 1,
                    "template_start_0based": pos % n,
                    "template_end_0based": (pos + len(core)) % n,
                    "binding_core_length": core_len,
                    "tail_5prime": tail,
                    "tail_length": len(tail),
                })
                found_this_len = True
            elif sub == core_rc:
                hits.append({
                    "strand": -1,
                    "template_start_0based": pos % n,
                    "template_end_0based": (pos + len(core)) % n,
                    "binding_core_length": core_len,
                    "tail_5prime": tail,
                    "tail_length": len(tail),
                })
                found_this_len = True

        if found_this_len:
            # Found longest binding core
            break

    return hits


def simulate_pcr(
    template_path_or_seq: str | pathlib.Path | SeqRecord,
    f_primer: str,
    r_primer: str,
    topology: str | None = None,
) -> dict[str, Any]:
    """Simulate PCR amplification with forward and reverse primers (including 5' tails).

    Returns:
        dict containing amplicon sequence, length, SHA-256, binding coordinates,
        and appended 5' tail extensions.
    """
    if isinstance(template_path_or_seq, SeqRecord):
        rec = template_path_or_seq
        t_seq = str(rec.seq).upper()
        topo = topology or rec.annotations.get("topology", "linear")
    elif isinstance(template_path_or_seq, (str, pathlib.Path)) and pathlib.Path(template_path_or_seq).exists():
        rec = _load_record(template_path_or_seq)
        t_seq = str(rec.seq).upper()
        topo = topology or rec.annotations.get("topology", "linear")
    else:
        t_seq = str(template_path_or_seq).upper()
        topo = topology or "linear"

    is_circular = (topo.lower() == "circular")
    n = len(t_seq)

    fwd_clean = str(f_primer).strip().upper()
    rev_clean = str(r_primer).strip().upper()

    f_hits = [h for h in _find_primer_binding(t_seq, fwd_clean, circular=is_circular) if h["strand"] == 1]
    r_hits = [h for h in _find_primer_binding(t_seq, rev_clean, circular=is_circular) if h["strand"] == -1]

    if not f_hits:
        raise ValueError(f"Forward primer '{fwd_clean}' has no binding site on template top strand")
    if not r_hits:
        raise ValueError(f"Reverse primer '{rev_clean}' has no binding site on template bottom strand")

    candidates = []
    for f in f_hits:
        for r in r_hits:
            f_start = f["template_start_0based"]
            r_start = r["template_start_0based"]
            r_end = r["template_end_0based"]

            if is_circular:
                dist = (r_end - f_start) % n
                if dist <= 0:
                    dist += n
                if dist < f["binding_core_length"]:
                    continue
                template_core = (t_seq + t_seq)[f_start : f_start + dist]
            else:
                if r_start < f_start:
                    continue
                dist = r_end - f_start
                if dist < f["binding_core_length"]:
                    continue
                template_core = t_seq[f_start : r_end]

            # Full amplicon includes 5' tail of forward primer + template core + RC(5' tail of reverse primer)
            f_tail = f["tail_5prime"]
            r_tail_rc = str(Seq(r["tail_5prime"]).reverse_complement()) if r["tail_5prime"] else ""

            full_amplicon = f_tail + template_core + r_tail_rc
            candidates.append({
                "amplicon": full_amplicon,
                "amplicon_length": len(full_amplicon),
                "template_core_length": len(template_core),
                "template_interval_0based": [f_start, r_end],
                "f_hit": f,
                "r_hit": r,
            })

    if not candidates:
        raise ValueError("Forward and reverse primer binding sites do not face each other to produce an amplicon")

    # Select shortest amplicon (standard PCR rule)
    candidates.sort(key=lambda x: x["amplicon_length"])
    best = candidates[0]

    amplicon_str = best["amplicon"]
    return {
        "amplicon": amplicon_str,
        "amplicon_length": len(amplicon_str),
        "amplicon_sha256": hashlib.sha256(amplicon_str.encode("utf-8")).hexdigest().upper(),
        "template_interval_0based": best["template_interval_0based"],
        "forward_binding": best["f_hit"],
        "reverse_binding": best["r_hit"],
        "topology": "linear",
    }


def calc_primer_tm(
    primer_seq: str,
    salt_conc_mM: float = 50.0,
    primer_conc_nM: float = 200.0,
) -> dict[str, Any]:
    """Calculate melting temperature (Tm), GC%, length, and 3' GC clamp of a primer.

    Uses nearest-neighbor thermodynamic calculation with salt correction.
    """
    from Bio.SeqUtils.MeltingTemp import Tm_NN

    seq = str(primer_seq).strip().upper()
    n = len(seq)
    if n == 0:
        return {"tm": 0.0, "length": 0, "gc_percent": 0.0, "warnings": ["Sequence is empty"]}

    gc_count = seq.count("G") + seq.count("C")
    gc_pct = round((gc_count / n) * 100.0, 1)

    try:
        tm_val = Tm_NN(seq, Na=salt_conc_mM, dnac=primer_conc_nM)
        tm_round = round(float(tm_val), 1)
    except Exception:
        # Fallback to standard Wallace rule
        tm_round = round((seq.count("A") + seq.count("T")) * 2.0 + gc_count * 4.0, 1)

    warnings = []
    if n < 18:
        warnings.append("Primer length < 18 bp (risk of non-specific binding)")
    elif n > 35:
        warnings.append("Primer length > 35 bp (higher secondary structure propensity)")

    if gc_pct < 40.0:
        warnings.append(f"Low GC content ({gc_pct}%), recommend 40-60%")
    elif gc_pct > 60.0:
        warnings.append(f"High GC content ({gc_pct}%), recommend 40-60%")

    # 3' clamp: check last 5 bases at 3' end
    tail5 = seq[-5:]
    tail_gc = tail5.count("G") + tail5.count("C")
    gc_clamp = (1 <= tail_gc <= 3)
    if tail_gc == 0:
        warnings.append("No G/C in last 5 bases at 3' end (weak 3' priming)")
    elif tail_gc > 3:
        warnings.append(f"High GC in 3' end ({tail_gc}/5 bases), risk of mispriming")

    return {
        "sequence": seq,
        "length": n,
        "tm": tm_round,
        "gc_percent": gc_pct,
        "gc_clamp_ideal": gc_clamp,
        "gc_in_3prime_5bp": tail_gc,
        "warnings": warnings,
    }


def design_overhang_primers(
    template_record_or_seq: str | pathlib.Path | SeqRecord,
    start: int,
    end: int,
    fwd_5prime_overhang: str = "",
    rev_5prime_overhang: str = "",
    target_tm: float = 60.0,
    min_core_len: int = 18,
    max_core_len: int = 32,
) -> dict[str, Any]:
    """Design a forward and reverse primer pair for a template interval with optional 5' overhangs.

    Finds the optimal length binding core closest to target_tm, then attaches 5' overhangs.
    """
    if isinstance(template_record_or_seq, SeqRecord):
        t_seq = str(template_record_or_seq.seq).upper()
    elif isinstance(template_record_or_seq, (str, pathlib.Path)) and pathlib.Path(template_record_or_seq).exists():
        rec = _load_record(template_record_or_seq)
        t_seq = str(rec.seq).upper()
    else:
        t_seq = str(template_record_or_seq).upper()

    n = len(t_seq)
    # Forward primer core starts at 'start' and extends forward
    best_fwd_core = ""
    best_fwd_diff = 999.0
    best_fwd_tm = 0.0

    for l in range(min_core_len, max_core_len + 1):
        if start + l > n:
            break
        core_seq = t_seq[start : start + l]
        tm_info = calc_primer_tm(core_seq)
        diff = abs(tm_info["tm"] - target_tm)
        if diff < best_fwd_diff:
            best_fwd_diff = diff
            best_fwd_core = core_seq
            best_fwd_tm = tm_info["tm"]

    # Reverse primer core ends at 'end' and extends backwards (RC of top strand)
    best_rev_core = ""
    best_rev_diff = 999.0
    best_rev_tm = 0.0

    for l in range(min_core_len, max_core_len + 1):
        if end - l < 0:
            break
        top_rev_segment = t_seq[end - l : end]
        rev_core_seq = str(Seq(top_rev_segment).reverse_complement())
        tm_info = calc_primer_tm(rev_core_seq)
        diff = abs(tm_info["tm"] - target_tm)
        if diff < best_rev_diff:
            best_rev_diff = diff
            best_rev_core = rev_core_seq
            best_rev_tm = tm_info["tm"]

    fwd_full = fwd_5prime_overhang.upper() + best_fwd_core
    rev_full = rev_5prime_overhang.upper() + best_rev_core

    delta_tm = round(abs(best_fwd_tm - best_rev_tm), 1)

    return {
        "target_interval_0based": [start, end],
        "forward_primer": {
            "full_sequence": fwd_full,
            "full_length": len(fwd_full),
            "binding_core": best_fwd_core,
            "binding_core_length": len(best_fwd_core),
            "binding_core_tm": best_fwd_tm,
            "overhang_5prime": fwd_5prime_overhang.upper(),
        },
        "reverse_primer": {
            "full_sequence": rev_full,
            "full_length": len(rev_full),
            "binding_core": best_rev_core,
            "binding_core_length": len(best_rev_core),
            "binding_core_tm": best_rev_tm,
            "overhang_5prime": rev_5prime_overhang.upper(),
        },
        "binding_core_delta_tm": delta_tm,
        "delta_tm_warning": delta_tm > 3.0,
    }
