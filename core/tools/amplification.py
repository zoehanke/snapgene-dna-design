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
            raw_end = pos + len(core)
            if not circular:
                start_c = pos
                end_c = raw_end
            else:
                start_c = pos % n
                end_c = raw_end if raw_end <= n else (raw_end % n)

            if sub == core:
                hits.append({
                    "strand": 1,
                    "template_start_0based": start_c,
                    "template_end_0based": end_c,
                    "binding_core_length": core_len,
                    "tail_5prime": tail,
                    "tail_length": len(tail),
                })
                found_this_len = True
            if sub == core_rc:
                hits.append({
                    "strand": -1,
                    "template_start_0based": start_c,
                    "template_end_0based": end_c,
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
    mg_conc_mM: float = 0.0,
    dntp_conc_mM: float = 0.0,
) -> dict[str, Any]:
    """Calculate melting temperature (Tm), GC%, length, and 3' GC clamp of a primer.

    Uses SantaLucia (1998) unified nearest-neighbor thermodynamic calculation with salt correction.
    Literature source:
    - SantaLucia, J. (1998). A unified view of polymer, dumbbell, and oligonucleotide DNA nearest-neighbor thermodynamics.
      PNAS 95(4):1460-1465. doi:10.1073/pnas.95.4.1460.
    """
    from Bio.SeqUtils.MeltingTemp import Tm_NN

    seq = str(primer_seq).strip().upper()
    n = len(seq)
    if n == 0:
        return {
            "sequence": "",
            "length": 0,
            "tm": 0.0,
            "gc_percent": 0.0,
            "gc_clamp_ideal": False,
            "gc_in_3prime_5bp": 0,
            "thermodynamic_model": "None",
            "warnings": ["Sequence is empty"],
        }

    gc_count = seq.count("G") + seq.count("C")
    gc_pct = round((gc_count / n) * 100.0, 1)

    dnac = primer_conc_nM / 2.0
    model = "SantaLucia (1998) Nearest-Neighbor"
    try:
        tm_val = Tm_NN(
            seq,
            Na=salt_conc_mM,
            Mg=mg_conc_mM,
            dNTPs=dntp_conc_mM,
            dnac1=dnac,
            dnac2=dnac,
        )
        tm_round = round(float(tm_val), 1)
    except Exception as exc:
        model = "Wallace (1979) 2(A+T)+4(G+C) [Fallback]"
        tm_round = round((seq.count("A") + seq.count("T")) * 2.0 + gc_count * 4.0, 1)

    warnings = []
    if model != "SantaLucia (1998) Nearest-Neighbor":
        warnings.append(f"Nearest-neighbor thermodynamic model unavailable ({exc}); fell back to Wallace rule.")
    if n < 18:
        warnings.append("Primer length < 18 bp (risk of non-specific binding)")
    elif n > 35:
        warnings.append("Primer length > 35 bp (higher secondary structure propensity)")

    if gc_pct < 40.0:
        warnings.append(f"Low GC content ({gc_pct}%), recommend 40-60%")
    elif gc_pct > 60.0:
        warnings.append(f"High GC content ({gc_pct}%), recommend 40-60%")

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
        "thermodynamic_model": model,
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
    prefer_primer3: bool = True,
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

    if end <= start:
        raise ValueError(f"Invalid target interval: end ({end}) must be greater than start ({start}).")
    if (end - start) < min_core_len:
        raise ValueError(
            f"Amplification interval ({end - start} bp) is shorter than minimum primer core length ({min_core_len} bp). "
            "Forward and reverse primers cannot amplify an interval shorter than a single primer core."
        )

    n = len(t_seq)
    interval_seq = t_seq[start:end]

    # --- Step 1: Attempt official Primer3 engine ---
    p3_pair = None
    p3_fwd = None
    p3_rev = None
    engine_name = "SantaLucia-Heuristic [Fallback]"

    if prefer_primer3:
        try:
            import sys
            scripts_dir = pathlib.Path(__file__).resolve().parent.parent.parent / "scripts"
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            from primer3_core_backend import (
                design_anchored_pairs,
                discover_primer3_core,
                ensure_primer3_core,
            )
            core_path = discover_primer3_core() or ensure_primer3_core(auto_install=False, verbose=False)
            if core_path:
                # Attempt A: with overhang tails
                res_p3 = design_anchored_pairs(
                    core_path=core_path,
                    sequence=interval_seq,
                    region_start=start,
                    target_tm=target_tm,
                    min_len=min_core_len,
                    max_len=min(max_core_len, len(interval_seq)),
                    top_n=1,
                    fwd_tail=fwd_5prime_overhang.upper(),
                    rev_tail=rev_5prime_overhang.upper(),
                    tm_range=(max(45.0, target_tm - 6.0), target_tm + 6.0),
                )
                if res_p3.get("pairs"):
                    p3_pair = res_p3["pairs"][0]
                    p3_fwd = res_p3["forward_candidates"][0]
                    p3_rev = res_p3["reverse_candidates"][0]
                    engine_name = "primer3-core"
                else:
                    # Attempt B: binding-only (in case tail caused hairpin/dimer penalty rejection)
                    res_p3_bo = design_anchored_pairs(
                        core_path=core_path,
                        sequence=interval_seq,
                        region_start=start,
                        target_tm=target_tm,
                        min_len=min_core_len,
                        max_len=min(max_core_len, len(interval_seq)),
                        top_n=1,
                        fwd_tail="",
                        rev_tail="",
                        tm_range=(max(45.0, target_tm - 8.0), target_tm + 8.0),
                    )
                    if res_p3_bo.get("pairs"):
                        p3_pair = res_p3_bo["pairs"][0]
                        p3_fwd = res_p3_bo["forward_candidates"][0]
                        p3_rev = res_p3_bo["reverse_candidates"][0]
                        engine_name = "primer3-core (binding-only retry)"
        except Exception:
            p3_pair = None

    if p3_pair and p3_fwd and p3_rev:
        best_fwd_core = p3_fwd["binding"]
        best_rev_core = p3_rev["binding"]
        best_fwd_tm = p3_fwd["tm"]
        best_rev_tm = p3_rev["tm"]
        primer3_metrics = {
            "engine": engine_name,
            "penalty": p3_pair.get("primer3_penalty"),
            "heterodimer_tm": (p3_pair.get("heterodimer") or {}).get("tm_any"),
            "fwd_hairpin_tm": (p3_fwd.get("hairpin") or {}).get("tm"),
            "fwd_self_dimer_tm": (p3_fwd.get("self_dimer") or {}).get("tm_any"),
            "fwd_end_stability_3p": (p3_fwd.get("end_stability_3p") or {}).get("value"),
            "rev_hairpin_tm": (p3_rev.get("hairpin") or {}).get("tm"),
            "rev_self_dimer_tm": (p3_rev.get("self_dimer") or {}).get("tm_any"),
            "rev_end_stability_3p": (p3_rev.get("end_stability_3p") or {}).get("value"),
        }
    else:
        # --- Step 2: Fallback to SantaLucia (1998) Nearest-Neighbor thermodynamic scan ---
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

        primer3_metrics = {
            "engine": "SantaLucia-Heuristic [Fallback]",
            "penalty": None,
            "heterodimer_tm": None,
        }

    if not best_fwd_core or not best_rev_core:
        raise ValueError(
            f"Could not design viable primer cores within bounds for interval [{start}, {end}] on template of length {n}."
        )

    if (start + len(best_fwd_core)) > end or (end - len(best_rev_core)) < start:
        raise ValueError(
            f"Amplification interval [{start}:{end}] ({end - start} bp) is too short for target Tm {target_tm}°C primers "
            f"(Fwd core: {len(best_fwd_core)} bp, Rev core: {len(best_rev_core)} bp). "
            "Primers cross each other and cannot face each other to produce an amplicon."
        )

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
            "hairpin_tm": primer3_metrics.get("fwd_hairpin_tm"),
            "self_dimer_tm": primer3_metrics.get("fwd_self_dimer_tm"),
            "end_stability_3p": primer3_metrics.get("fwd_end_stability_3p"),
        },
        "reverse_primer": {
            "full_sequence": rev_full,
            "full_length": len(rev_full),
            "binding_core": best_rev_core,
            "binding_core_length": len(best_rev_core),
            "binding_core_tm": best_rev_tm,
            "overhang_5prime": rev_5prime_overhang.upper(),
            "hairpin_tm": primer3_metrics.get("rev_hairpin_tm"),
            "self_dimer_tm": primer3_metrics.get("rev_self_dimer_tm"),
            "end_stability_3p": primer3_metrics.get("rev_end_stability_3p"),
        },
        "binding_core_delta_tm": delta_tm,
        "delta_tm_warning": delta_tm > 3.0,
        "engine": primer3_metrics["engine"],
        "primer3_metrics": primer3_metrics,
    }


def check_primer_dimers(
    primer1: str,
    primer2: str | None = None,
) -> dict[str, Any]:
    """Check for primer-dimer (heterodimer) or self-dimer (homodimer) base-pairing.

    Scans for complementary alignments between the two primers, specifically flagging
    3' end complementarity which causes catastrophic primer-dimer artifacts in PCR.
    """
    p1 = str(primer1).strip().upper()
    p2 = str(primer2).strip().upper() if primer2 else p1
    is_self = (primer2 is None or primer1 == primer2)

    # Convert primer2 to its complement so we can search for direct matching substrings
    comp_map = str.maketrans("ACGT", "TGCA")
    p2_comp = p2.translate(comp_map)

    # Scan all relative shifts between p1 and p2_comp (in antiparallel direction)
    max_continuous_match = 0
    max_3prime_match = 0
    best_alignment = ""

    # Reverse p2_comp so 3' of p1 aligns against 3' of p2
    p2_rev_comp = p2_comp[::-1]

    n1, n2 = len(p1), len(p2_rev_comp)
    for shift in range(-n2 + 1, n1):
        match_len = 0
        cur_3prime = 0
        for i in range(n1):
            j = i - shift
            if 0 <= j < n2:
                if p1[i] == p2_rev_comp[j]:
                    match_len += 1
                    # Check if this match touches the 3' end of p1 (i == n1 - 1) or p2 (j == 0)
                    if i == n1 - 1 or j == 0:
                        cur_3prime = max(cur_3prime, match_len)
                else:
                    match_len = 0
            else:
                match_len = 0
        max_continuous_match = max(max_continuous_match, match_len)
        max_3prime_match = max(max_3prime_match, cur_3prime)

    warnings = []
    if max_3prime_match >= 4:
        warnings.append(
            f"Severe 3'-end complementarity ({max_3prime_match} bp): high risk of primer-dimer amplification in PCR"
        )
    elif max_3prime_match >= 3:
        warnings.append(f"Moderate 3'-end complementarity ({max_3prime_match} bp)")

    if max_continuous_match >= 7:
        warnings.append(f"Internal complementarity ({max_continuous_match} bp): possible competitive annealing")

    return {
        "analysis_type": "homodimer" if is_self else "heterodimer",
        "primer1_length": n1,
        "primer2_length": n2,
        "max_continuous_complementarity": max_continuous_match,
        "max_3prime_complementarity": max_3prime_match,
        "high_dimer_risk": (max_3prime_match >= 4),
        "warnings": warnings,
    }


def anneal_oligos(
    top_oligo: str,
    bottom_oligo: str,
) -> dict[str, Any]:
    """Simulate in-vitro annealing of two single-stranded oligos into a double-stranded duplex with sticky overhangs.

    Used for CRISPR sgRNA/shRNA vector cloning, adapter generation, and linker cassette assembly.
    """
    top = str(top_oligo).strip().upper()
    bot = str(bottom_oligo).strip().upper()

    # The bottom oligo is written 5' to 3'. Its reverse complement pairs with the top oligo (5' to 3').
    bot_rc = str(Seq(bot).reverse_complement())

    # Find where bot_rc aligns inside top or vice versa
    # Case 1: bot_rc is inside top (e.g. top has 5' and/or 3' overhangs)
    # Case 2: top is inside bot_rc (e.g. bottom has 5' and/or 3' overhangs)
    # Standard heuristic: find maximal overlap
    best_overlap = 0
    best_offset = 0  # offset of bot_rc relative to top

    n_top = len(top)
    n_bot = len(bot_rc)

    for offset in range(-n_bot + 1, n_top):
        overlap = 0
        mismatch = 0
        for i in range(n_top):
            j = i - offset
            if 0 <= j < n_bot:
                if top[i] == bot_rc[j]:
                    overlap += 1
                else:
                    mismatch += 1
        if mismatch == 0 and overlap > best_overlap:
            best_overlap = overlap
            best_offset = offset

    if best_overlap == 0:
        raise ValueError("The two oligos share no complementary duplex region!")

    # Calculate overhangs
    # If offset > 0: top extends to the left of bot_rc -> 5' overhang on top strand!
    # If offset < 0: bot_rc extends to the left of top -> bottom strand 5' overhang! (since bot 5' is at the right of bot_rc)
    left_top_overhang = top[:max(0, best_offset)]
    right_top_overhang = top[best_offset + n_bot:] if (best_offset + n_bot < n_top) else ""

    # Bot strand 5' overhang is at the 3' end of bot (left of bot_rc)
    left_bot_overhang = bot_rc[:max(0, -best_offset)]
    right_bot_overhang = bot_rc[n_top - best_offset:] if (n_top - best_offset < n_bot) else ""

    # Format into standard biological representation:
    # 5' overhang on left:
    left_5prime_ov = left_top_overhang if left_top_overhang else str(Seq(left_bot_overhang).reverse_complement())
    left_type = "5prime_top" if left_top_overhang else ("5prime_bottom" if left_bot_overhang else "blunt")

    # 5' overhang on right:
    # Bottom strand 5' end is right of bot_rc (reverse complement to get bottom strand 5' to 3' sequence)
    right_5prime_ov = str(Seq(right_bot_overhang).reverse_complement()) if right_bot_overhang else right_top_overhang
    right_type = "5prime_bottom" if right_bot_overhang else ("5prime_top" if right_top_overhang else "blunt")

    duplex_seq = top[max(0, best_offset) : min(n_top, best_offset + n_bot)]

    return {
        "top_oligo": top,
        "bottom_oligo": bot,
        "duplex_core_sequence": duplex_seq,
        "duplex_core_length": len(duplex_seq),
        "left_overhang": {
            "sequence": left_5prime_ov,
            "length": len(left_5prime_ov),
            "geometry": left_type,
        },
        "right_overhang": {
            "sequence": right_5prime_ov,
            "length": len(right_5prime_ov),
            "geometry": right_type,
        },
    }
