# -*- coding: utf-8 -*-
"""core/tools/amplification.py - Atomic PCR amplification and primer tools.

Simulates PCR with exact or 5'-overhang primers, finds primer binding sites,
and calculates amplicon sequences.
"""
from __future__ import annotations

import copy
import hashlib
import pathlib
from typing import Any

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

def _find_primer_binding(
    template: str,
    primer: str,
    min_binding_len: int = 15,
    circular: bool = False,
    strand: int | None = None,
    binding_core_length: int | None = None,
    binding_start_0based: int | None = None,
) -> list[dict[str, Any]]:
    """Find complete 3' binding-core sites for a primer.

    A primer's 3' core is searched independently on each requested strand.
    This is deliberate: a long exact match on the wrong strand must not hide a
    shorter valid match on the strand on which the primer can participate in a
    PCR pair.  Unless a core length is supplied, only the longest exact core
    for that strand is returned.  ``binding_start_0based`` is a top-strand
    coordinate and is useful when a caller has already confirmed the boundary.
    """
    t = template.upper()
    p = primer.upper()
    n = len(t)
    if n == 0 or not p:
        return []
    if strand not in (None, 1, -1):
        raise ValueError("strand must be 1, -1, or None")
    if binding_core_length is not None:
        binding_core_length = int(binding_core_length)
        if binding_core_length < min_binding_len or binding_core_length > len(p):
            raise ValueError(
                "binding_core_length must be between %d and %d (got %d)"
                % (min_binding_len, len(p), binding_core_length)
            )
        lengths = [binding_core_length]
    else:
        lengths = list(range(len(p), min_binding_len - 1, -1))

    strands = (1, -1) if strand is None else (strand,)
    hits: list[dict[str, Any]] = []
    for wanted_strand in strands:
        strand_hits: list[dict[str, Any]] = []
        for core_len in lengths:
            if core_len > n:
                continue
            core = p[-core_len:]
            target = core if wanted_strand == 1 else str(Seq(core).reverse_complement())
            tail = p[:-core_len]
            if circular:
                search_seq = t + t[:core_len - 1]
                positions = range(n)
            else:
                search_seq = t
                positions = range(n - core_len + 1)
            for pos in positions:
                if binding_start_0based is not None:
                    requested_pos = int(binding_start_0based)
                    if circular:
                        requested_pos %= n
                    elif requested_pos < 0 or requested_pos >= n:
                        raise ValueError(
                            "binding_start_0based %d is outside template length %d"
                            % (requested_pos, n)
                        )
                sub = search_seq[pos:pos + core_len]
                if sub != target:
                    continue
                raw_end = pos + core_len
                end_c = raw_end if not circular or raw_end <= n else raw_end % n
                strand_hits.append({
                    "strand": wanted_strand,
                    "template_start_0based": pos,
                    "template_end_0based": end_c,
                    "template_end_unwrapped_0based": raw_end,
                    "wraps_origin": bool(circular and raw_end > n),
                    "binding_core_length": core_len,
                    "binding_core": core,
                    "tail_5prime": tail,
                    "tail_length": len(tail),
                })
            if strand_hits:
                if (binding_start_0based is not None and
                        not any(
                            hit["template_start_0based"] == requested_pos
                            for hit in strand_hits
                        )):
                    # A requested coordinate validates a complete hit at the
                    # selected core length. It must not hide other exact hits.
                    strand_hits = []
                    continue
                # Longest complete core wins for this strand only.  Do not let
                # a hit on the other strand suppress this result.
                break
        hits.extend(strand_hits)
    return hits


def _extract_template_record(rec, start, length, circular):
    """Extract template interval while retaining source feature annotations."""
    from core.tools.sequence_ops import slice_record_interval
    return slice_record_interval(rec, int(start), int(length), circular=circular)


def _template_record_dict(rec):
    """Serialize complete PCR input record for downstream preparation steps."""
    from core.models.construct_model import feature_to_dict

    return {
        "id": rec.id or rec.name or "template",
        "name": rec.name or rec.id or "template",
        "sequence": str(rec.seq).upper(),
        "annotations": {
            "molecule_type": rec.annotations.get("molecule_type", "DNA"),
            "topology": rec.annotations.get("topology", "linear"),
        },
        "topology": rec.annotations.get("topology", "linear"),
        "features": [feature_to_dict(feature, len(rec.seq))
                     for feature in rec.features],
    }


def simulate_pcr(
    template_path_or_seq: str | pathlib.Path | SeqRecord,
    f_primer: str,
    r_primer: str,
    topology: str | None = None,
    forward_binding_core_length: int | None = None,
    reverse_binding_core_length: int | None = None,
    forward_binding_start_0based: int | None = None,
    reverse_binding_start_0based: int | None = None,
    min_binding_len: int = 15,
) -> dict[str, Any]:
    """Simulate PCR amplification with forward and reverse primers (including 5' tails).

    Returns:
        dict containing amplicon sequence, length, SHA-256, binding coordinates,
        and appended 5' tail extensions.
    """
    from core.io.input_resolution import resolve_sequence_input
    rec, t_seq = resolve_sequence_input(template_path_or_seq, default_topology=topology or "linear")
    topo = topology or rec.annotations.get("topology", "linear")

    is_circular = (topo.lower() == "circular")
    n = len(t_seq)

    fwd_clean = str(f_primer).strip().upper()
    rev_clean = str(r_primer).strip().upper()

    # Selectors are optional.  When supplied, they make a boundary auditable
    # instead of relying on a shortest-product heuristic in a repeated template.
    f_hits = _find_primer_binding(
        t_seq, fwd_clean, min_binding_len=min_binding_len, circular=is_circular,
        strand=1, binding_core_length=forward_binding_core_length,
        binding_start_0based=forward_binding_start_0based,
    )
    r_hits = _find_primer_binding(
        t_seq, rev_clean, min_binding_len=min_binding_len, circular=is_circular,
        strand=-1, binding_core_length=reverse_binding_core_length,
        binding_start_0based=reverse_binding_start_0based,
    )

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
                if dist < f["binding_core_length"] or dist > n:
                    continue
                template_core = (t_seq + t_seq)[f_start : f_start + dist]
            else:
                if r_start < f_start:
                    continue
                dist = r_end - f_start
                if dist < f["binding_core_length"] or dist <= 0:
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
                "template_interval_unwrapped_0based": [f_start, f_start + dist],
                "wraps_origin": bool(is_circular and f_start + dist > n),
                "f_hit": f,
                "r_hit": r,
            })

    if not candidates:
        raise ValueError("Forward and reverse primer binding sites do not face each other to produce an amplicon")

    # Multiple complete products are an input ambiguity, not a reason to pick
    # the shortest in-silico product.  The caller can resolve it by providing
    # explicit core lengths and/or top-strand binding positions.
    unique_candidates = {
        (
            item["f_hit"]["template_start_0based"],
            item["r_hit"]["template_start_0based"],
            item["f_hit"]["binding_core_length"],
            item["r_hit"]["binding_core_length"],
            item["amplicon"],
        ): item
        for item in candidates
    }
    candidates = list(unique_candidates.values())
    if len(candidates) > 1:
        summary = [
            {
                "amplicon_length": item["amplicon_length"],
                "template_interval_0based": item["template_interval_0based"],
                "forward_start_0based": item["f_hit"]["template_start_0based"],
                "reverse_start_0based": item["r_hit"]["template_start_0based"],
                "forward_core_length": item["f_hit"]["binding_core_length"],
                "reverse_core_length": item["r_hit"]["binding_core_length"],
            }
            for item in sorted(candidates, key=lambda value: (
                value["f_hit"]["template_start_0based"],
                value["r_hit"]["template_start_0based"],
            ))
        ]
        raise ValueError(
            "PCR primer-binding ambiguity: %d complete amplicons match; "
            "a binding coordinate alone cannot resolve additional matches; "
            "change the complete core or target boundary after review. "
            "candidates=%r" % (len(candidates), summary)
        )
    best = candidates[0]

    amplicon_str = best["amplicon"]
    from core.models.construct_model import feature_to_dict
    start, end = best["template_interval_0based"]
    core_record = _extract_template_record(
        rec,
        best["template_interval_unwrapped_0based"][0],
        best["template_core_length"],
        is_circular,
    )
    offset = len(best["f_hit"]["tail_5prime"])
    f_hit = best["f_hit"]
    r_hit = best["r_hit"]
    primer_rows = [
        {
            "name": "forward_primer",
            "sequence": fwd_clean,
            "binding_sequence": fwd_clean[-f_hit["binding_core_length"]:],
            "binding_interval_0based": [
                f_hit["template_start_0based"],
                f_hit["template_end_0based"],
            ],
            "binding_interval_unwrapped_0based": [
                f_hit["template_start_0based"],
                f_hit["template_end_unwrapped_0based"],
            ],
            "strand": 1,
            "binding_core_length": f_hit["binding_core_length"],
            "tail_5prime": f_hit["tail_5prime"],
        },
        {
            "name": "reverse_primer",
            "sequence": rev_clean,
            "binding_sequence": rev_clean[-r_hit["binding_core_length"]:],
            "binding_interval_0based": [
                r_hit["template_start_0based"],
                r_hit["template_end_0based"],
            ],
            "binding_interval_unwrapped_0based": [
                r_hit["template_start_0based"],
                r_hit["template_end_unwrapped_0based"],
            ],
            "strand": -1,
            "binding_core_length": r_hit["binding_core_length"],
            "tail_5prime": r_hit["tail_5prime"],
        },
    ]
    return {
        "amplicon": amplicon_str,
        "amplicon_length": len(amplicon_str),
        "template_core_length": best["template_core_length"],
        "amplicon_sha256": hashlib.sha256(amplicon_str.encode("utf-8")).hexdigest().upper(),
        "features": [feature_to_dict(f._shift(offset), len(amplicon_str)) for f in core_record.features],
        "template_interval_0based": best["template_interval_0based"],
        "template_interval_unwrapped_0based": best["template_interval_unwrapped_0based"],
        "wraps_origin": best["wraps_origin"],
        "forward_binding": best["f_hit"],
        "reverse_binding": best["r_hit"],
        "template": _template_record_dict(rec),
        "primers": primer_rows,
        "candidate_count": len(candidates),
        "template_length": n,
        "template_topology": "circular" if is_circular else "linear",
        "template_id": rec.id or rec.name,
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

    seq = str(primer_seq.seq).upper() if isinstance(primer_seq, SeqRecord) else "".join(str(primer_seq).split()).upper()
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
    if any(base not in "ACGT" for base in seq):
        raise ValueError("Primer Tm requires an explicit A/C/G/T sequence")

    gc_count = seq.count("G") + seq.count("C")
    gc_pct = round((gc_count / n) * 100.0, 1)

    dnac = primer_conc_nM / 2.0
    model = "SantaLucia (1998) Nearest-Neighbor"
    tm_val = Tm_NN(seq, Na=salt_conc_mM, Mg=mg_conc_mM, dNTPs=dntp_conc_mM,
                   dnac1=dnac, dnac2=dnac)
    tm_round = round(float(tm_val), 1)
    warnings = []
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
    max_core_len: int = 40,
    prefer_primer3: bool = True,
    circular: bool | None = None,
    topology: str | None = None,
) -> dict[str, Any]:
    """Design a forward and reverse primer pair for a template interval with optional 5' overhangs.

    Finds the optimal length binding core closest to target_tm, then attaches 5' overhangs.
    """
    from core.io.input_resolution import resolve_sequence_input
    rec, t_seq = resolve_sequence_input(template_record_or_seq)
    n = len(t_seq)
    if topology is not None:
        if topology not in ("linear", "circular"):
            raise ValueError("topology must be linear or circular")
        requested_circular = topology == "circular"
        if circular is not None and bool(circular) != requested_circular:
            raise ValueError("topology and circular disagree")
        circular = requested_circular
    is_circular = (
        bool(circular)
        if circular is not None
        else str(rec.annotations.get("topology", "linear")).lower() == "circular"
    )
    start = int(start)
    end = int(end)
    wraps_origin = bool(is_circular and end < start)
    if start < 0 or start >= n or end < 0 or end > n:
        raise ValueError(
            f"Invalid target interval [{start}, {end}) for template length {n}."
        )
    if end <= start and not wraps_origin:
        raise ValueError(
            f"Invalid target interval: end ({end}) must be greater than start ({start})."
        )
    target_length = (n - start + end) if wraps_origin else (end - start)
    if target_length < min_core_len:
        raise ValueError(
            f"Amplification interval ({target_length} bp) is shorter than minimum primer core length ({min_core_len} bp). "
            "Forward and reverse primers cannot amplify an interval shorter than a single primer core."
        )

    # Primer3 sees a linearized target.  The returned binding positions are
    # mapped back to the original circular coordinate system below.
    design_sequence_start = 0 if wraps_origin else start
    interval_seq = (
        (t_seq + t_seq)[start:start + target_length]
        if wraps_origin else t_seq[start:end]
    )
    import sys
    scripts_dir = pathlib.Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from primer3_core_backend import (
        check_complete_oligo_pair,
        design_anchored_pairs, discover_primer3_core,
    )
    core_path = discover_primer3_core()
    if not core_path:
        raise ValueError("Complete-oligo structural checks require primer3_core from the standard requirements")
    if not (15 <= min_core_len <= max_core_len):
        raise ValueError("Primer binding bounds must satisfy 15 <= min_core_len <= max_core_len")
    if max(len(fwd_5prime_overhang), len(rev_5prime_overhang)) + min_core_len > 60:
        raise ValueError("OLIGO_LENGTH_LIMIT: complete primers require more than 60 nt; prepare the added sequence in successive PCR steps")
    structural_rejections = []
    overflow_seen = False

    def complete_structure(fwd, rev, fwd_tail, rev_tail):
        nonlocal overflow_seen
        full_f = fwd_tail.upper() + fwd["binding"]
        full_r = rev_tail.upper() + rev["binding"]
        if max(len(full_f), len(full_r)) > 60:
            overflow_seen = True
            return None
        annealing = min(float(fwd["tm"]), float(rev["tm"])) - 5.0
        structure = check_complete_oligo_pair(full_f, full_r, core_path,
                                             annealing_temperature=annealing)
        if not structure["passed"]:
            if len(structural_rejections) < 3:
                structural_rejections.append(structure["metrics"])
            return None
        return structure

    def _binding_match_count(core, side):
        return len(_find_primer_binding(
            t_seq, core, min_binding_len=min_core_len,
            circular=is_circular, strand=side,
            binding_core_length=len(core),
        ))

    def _assess_pair(fwd, rev, fwd_tail, rev_tail):
        f_core = str(fwd.get("binding") or "").upper()
        r_core = str(rev.get("binding") or "").upper()
        f_tm = float(fwd.get("tm") or calc_primer_tm(f_core)["tm"])
        r_tm = float(rev.get("tm") or calc_primer_tm(r_core)["tm"])
        dimer = check_primer_dimers(
            fwd_tail.upper() + f_core,
            rev_tail.upper() + r_core,
        )
        f_unique = _binding_match_count(f_core, 1) == 1
        r_unique = _binding_match_count(r_core, -1) == 1
        tm_out = int(not (52.0 <= f_tm <= 72.0)) + int(
            not (52.0 <= r_tm <= 72.0)
        )
        delta = abs(f_tm - r_tm)
        target_distance = abs(f_tm - target_tm) + abs(r_tm - target_tm)
        max_3prime = int(dimer.get("max_3prime_complementarity") or 0)
        return {
            "dimer": dimer,
            "max_3prime_complementarity": max_3prime,
            "dimer_safe": max_3prime < 4,
            "forward_unique": f_unique,
            "reverse_unique": r_unique,
            "unique": f_unique and r_unique,
            "tm_out_of_range": tm_out,
            "forward_tm": round(f_tm, 1),
            "reverse_tm": round(r_tm, 1),
            "target_distance": round(target_distance, 1),
            "delta_tm": round(delta, 1),
            "acceptable": (
                max_3prime < 4 and f_unique and r_unique and
                tm_out == 0 and delta <= 3.0
            ),
        }

    def _pair_sort_key(assessment):
        # Unique binding is a hard provenance condition. A selected position
        # must not be used to hide another real binding site. Only after that
        # condition is satisfied do dimer and Tm heuristics rank candidates.
        return (
            0 if assessment["acceptable"] else 1,
            0 if assessment["unique"] else 1,
            0 if assessment["dimer_safe"] else 1,
            assessment["tm_out_of_range"],
            assessment["target_distance"],
            assessment["max_3prime_complementarity"],
            assessment["delta_tm"],
        )

    def _select_backend_pair(result, fwd_tail, rev_tail):
        candidates = []
        for pair in result.get("pairs", []):
            fwd = result["forward_candidates"][pair["forward_index"]]
            rev = result["reverse_candidates"][pair["reverse_index"]]
            assessment = _assess_pair(fwd, rev, fwd_tail, rev_tail)
            candidates.append((
                _pair_sort_key(assessment), pair, fwd, rev, assessment,
            ))
        if not candidates:
            return None, None, None, None
        unique = [row for row in candidates if row[4]["unique"]]
        if not unique:
            raise ValueError(
                "No unique complete primer pair remains for the requested "
                "boundary; adjust the target interval or binding boundary."
            )
        for _, pair, fwd, rev, assessment in sorted(unique, key=lambda row: row[0]):
            if not assessment["acceptable"]:
                continue
            structure = complete_structure(fwd, rev, fwd_tail, rev_tail)
            if structure is not None:
                assessment["complete_oligo_structure"] = structure
                return pair, fwd, rev, assessment
        return None, None, None, None

    # --- Step 1: Attempt official Primer3 engine ---
    p3_pair = None
    p3_fwd = None
    p3_rev = None
    p3_assessment = None
    engine_name = "SantaLucia-Heuristic [Fallback]"

    if prefer_primer3:
        # Core-only search is candidate generation, never full-oligo approval.
        attempts = [(fwd_5prime_overhang, rev_5prime_overhang, target_tm, (52.0, 72.0))]
        if fwd_5prime_overhang or rev_5prime_overhang:
            attempts.append(("", "", target_tm, (52.0, 72.0)))
        # A higher, explicit annealing window may suppress a structure which
        # is problematic for a 60 C design. The molecule and margins stay fixed.
        for higher_target in (65.0, 70.0):
            if target_tm < higher_target:
                attempts.append(("", "", higher_target, (higher_target-1.0, 72.0)))
        for search_f_tail, search_r_tail, search_tm, tm_range in attempts:
            maximum = min(max_core_len, 36, 60-len(search_f_tail),
                          60-len(search_r_tail), len(interval_seq))
            if maximum < min_core_len:
                continue
            res_p3 = design_anchored_pairs(
                core_path, interval_seq, design_sequence_start, search_tm,
                min_core_len, maximum, 20,
                fwd_tail=search_f_tail.upper(), rev_tail=search_r_tail.upper(),
                tm_range=tm_range,
            )
            if res_p3.get("pairs"):
                p3_pair, p3_fwd, p3_rev, p3_assessment = _select_backend_pair(
                    res_p3, fwd_5prime_overhang, rev_5prime_overhang)
                if p3_pair:
                    p3_assessment["requested_target_tm"] = target_tm
                    p3_assessment["search_target_tm"] = search_tm
                    engine_name = "primer3-core"
                    if (fwd_5prime_overhang or rev_5prime_overhang) and not (search_f_tail or search_r_tail):
                        engine_name += " (core search; complete oligos rechecked)"
                    break

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
            "complete_oligo_dimer": p3_assessment["dimer"],
            "selected_pair_quality": p3_assessment,
        }
    else:
        # --- Step 2: Fallback to SantaLucia (1998) Nearest-Neighbor thermodynamic scan ---
        best_fwd_core = ""
        best_fwd_tm = 0.0

        fwd_options = []
        for l in range(min_core_len, max_core_len + 1):
            if target_length < l:
                break
            core_seq = interval_seq[:l]
            tm_info = calc_primer_tm(core_seq, primer_conc_nM=50.0, mg_conc_mM=1.5, dntp_conc_mM=0.6)
            diff = abs(tm_info["tm"] - target_tm)
            fwd_options.append((core_seq, tm_info["tm"], diff))

        best_rev_core = ""
        best_rev_tm = 0.0
        rev_options = []
        for l in range(min_core_len, max_core_len + 1):
            if target_length < l:
                break
            top_rev_segment = interval_seq[target_length - l:target_length]
            rev_core_seq = str(Seq(top_rev_segment).reverse_complement())
            tm_info = calc_primer_tm(rev_core_seq, primer_conc_nM=50.0, mg_conc_mM=1.5, dntp_conc_mM=0.6)
            diff = abs(tm_info["tm"] - target_tm)
            rev_options.append((rev_core_seq, tm_info["tm"], diff))

        if fwd_options and rev_options:
            pair_options = []
            for f_core, f_tm, f_diff in fwd_options:
                for r_core, r_tm, r_diff in rev_options:
                    # Primer3 cannot search cores longer than 36 nt. Extend
                    # only that missing search space, not pairs it rejected
                    # inside its supported bounds.
                    if prefer_primer3 and max(len(f_core), len(r_core)) <= 36:
                        continue
                    f_info = {"binding": f_core, "tm": f_tm}
                    r_info = {"binding": r_core, "tm": r_tm}
                    assessment = _assess_pair(
                        f_info, r_info, fwd_5prime_overhang, rev_5prime_overhang
                    )
                    pair_options.append((
                        _pair_sort_key(assessment),
                        f_core, f_tm, r_core, r_tm, assessment,
                    ))
            unique_options = [item for item in pair_options if item[5]["unique"]]
            if not unique_options:
                raise ValueError(
                    ("No unique complete primer pair remains within the requested bounds; " if pair_options else "NO_VALID_PRIMER_PAIR: no complete primer pair found within the requested bounds; ")
                    + repr(structural_rejections)
                )
            selected = None
            for item in sorted(unique_options, key=lambda value: value[0]):
                if not item[5]["acceptable"]:
                    continue
                structure = complete_structure({"binding": item[1], "tm": item[2]}, {"binding": item[3], "tm": item[4]},
                                               fwd_5prime_overhang, rev_5prime_overhang)
                if structure is not None:
                    item[5]["complete_oligo_structure"] = structure
                    selected = item
                    break
            if selected is None:
                code = "OLIGO_LENGTH_LIMIT" if overflow_seen else "NO_VALID_PRIMER_PAIR"
                raise ValueError(code + ": no complete primer pair meets structural and core constraints; " + repr(structural_rejections))
            _, best_fwd_core, best_fwd_tm, best_rev_core, best_rev_tm, fallback_assessment = selected

        primer3_metrics = {
            "engine": "Biopython NN extended-core search + Primer3 structure" if prefer_primer3 else "Biopython NN core search + Primer3 structure",
            "penalty": None,
            "heterodimer_tm": None,
            "complete_oligo_dimer": fallback_assessment["dimer"] if fwd_options and rev_options else None,
            "selected_pair_quality": fallback_assessment if fwd_options and rev_options else None,
        }

    if not best_fwd_core or not best_rev_core:
        raise ValueError(
            f"Could not design viable primer cores within bounds for interval [{start}, {end}] on template of length {n}."
        )

    if target_length < len(best_fwd_core) or target_length < len(best_rev_core):
        raise ValueError(
            f"Amplification interval [{start}:{end}] ({target_length} bp) is too short for target Tm {target_tm}°C primers "
            f"(Fwd core: {len(best_fwd_core)} bp, Rev core: {len(best_rev_core)} bp). "
            "Primers cross each other and cannot face each other to produce an amplicon."
        )

    complete_qc = primer3_metrics["selected_pair_quality"]["complete_oligo_structure"]
    for prefix, side in (("fwd", "forward"), ("rev", "reverse")):
        primer3_metrics[prefix + "_hairpin_tm"] = complete_qc["metrics"][side]["hairpin_tm"]
        primer3_metrics[prefix + "_self_dimer_tm"] = complete_qc["metrics"][side]["self_any_tm"]
    primer3_metrics["heterodimer_tm"] = complete_qc["metrics"]["pair"]["any_tm"]
    primer3_metrics["structure_scope"] = complete_qc["scope"]

    fwd_full = fwd_5prime_overhang.upper() + best_fwd_core
    rev_full = rev_5prime_overhang.upper() + best_rev_core

    delta_tm = round(abs(best_fwd_tm - best_rev_tm), 1)

    def _binding_metadata(candidate, side, core):
        local_start = int(candidate.get("bind_start", 0)) - int(design_sequence_start)
        if side == 1:
            source_start = (start + local_start) % n if is_circular else start + local_start
        else:
            source_start = (start + local_start) % n if is_circular else start + local_start
        hits = _find_primer_binding(
            t_seq, core, min_binding_len=min_core_len, circular=is_circular,
            strand=side, binding_core_length=len(core),
        )
        matched = [h for h in hits if h["template_start_0based"] == source_start]
        return {
            "template_start_0based": source_start,
            "template_end_0based": (
                (source_start + len(core)) % n if is_circular
                else source_start + len(core)
            ),
            "strand": side,
            "binding_core_length": len(core),
            "unique_match_count": len(hits),
            "unique": len(hits) == 1,
            "matched": bool(matched),
        }

    # Fallback candidates have no backend coordinates; their cores are forced
    # to the requested target boundaries.
    fwd_candidate = p3_fwd or {"bind_start": design_sequence_start}
    rev_candidate = p3_rev or {
        "bind_start": design_sequence_start + target_length - len(best_rev_core)
    }
    fwd_binding = _binding_metadata(fwd_candidate, 1, best_fwd_core)
    rev_binding = _binding_metadata(rev_candidate, -1, best_rev_core)

    return {
        "target_interval_0based": [start, end],
        "target_interval_length": target_length,
        "target_interval_wraps_origin": wraps_origin,
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
            "binding": fwd_binding,
            "unique_binding": fwd_binding["unique"],
            "binding_match_count": fwd_binding["unique_match_count"],
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
            "binding": rev_binding,
            "unique_binding": rev_binding["unique"],
            "binding_match_count": rev_binding["unique_match_count"],
        },
        "binding_core_delta_tm": delta_tm,
        "delta_tm_warning": delta_tm > 3.0,
        "engine": primer3_metrics["engine"],
        "primer3_metrics": primer3_metrics,
    }


def prepare_pcr_fragment(template, start, end, fwd_tail="", rev_tail="", name="fragment", target_tm=60.0):
    """Prepare exact tailed DNA, splitting long additions into actual PCR steps."""
    from core.io.input_resolution import resolve_sequence_record
    current = resolve_sequence_record(template)
    original = str(current.seq).upper()
    circular = current.annotations.get("topology", "linear") == "circular"
    core = original[start:end] if end > start else (original[start:] + original[:end] if circular else "")
    expected = fwd_tail.upper() + core + str(Seq(rev_tail).reverse_complement()).upper()

    def reaction(record, begin, finish, left, right, step_name):
        design = design_overhang_primers(record, begin, finish,
            fwd_5prime_overhang=left, rev_5prime_overhang=right,
            target_tm=target_tm, min_core_len=15, max_core_len=40)
        f, r = design["forward_primer"], design["reverse_primer"]
        pcr = simulate_pcr(record, f["full_sequence"], r["full_sequence"],
            forward_binding_core_length=f["binding_core_length"],
            reverse_binding_core_length=r["binding_core_length"])
        for primer, side, info in zip(pcr["primers"], ("F", "R"), (f, r)):
            primer["name"] = step_name + "_" + side
            primer["tm"] = info["binding_core_tm"]
            primer["binding_core_tm"] = info["binding_core_tm"]
        row = {"id": step_name, "method": "PCR", "template": pcr["template"],
               "primers": pcr["primers"],
               "product": {"sequence": pcr["amplicon"], "features": pcr["features"], "topology": "linear",
                           "length": pcr["amplicon_length"]},
               "primer_design": design,
               "annealing_temperature_hint_C": design["primer3_metrics"]["selected_pair_quality"]["complete_oligo_structure"]["annealing_temperature_C"]}
        return pcr, design, row

    try:
        pcr, design, row = reaction(current, start, end, fwd_tail, rev_tail, name)
        preparations = [row]
    except ValueError as exc:
        if not str(exc).startswith("OLIGO_LENGTH_LIMIT"):
            raise
        # Add the template-adjacent portions first. Every following template
        # is the actual preceding PCR product, not the requested ideal DNA.
        import math
        longest = max(len(fwd_tail), len(rev_tail))
        # First reserve 30 nt for binding. If a low-GC boundary needs longer
        # cores, add a stage, up to the 36 nt core / 24 nt extension split.
        minimum_stages = math.ceil(longest / 30)
        maximum_stages = math.ceil(longest / 20)
        for stage_count in range(minimum_stages, maximum_stages + 1):
            current = resolve_sequence_record(template)
            left, right = fwd_tail.upper(), rev_tail.upper()
            preparations = []
            begin, finish = start, end
            try:
                for index in range(stage_count):
                    stages_left = stage_count - index
                    left_len = math.ceil(len(left) / stages_left)
                    right_len = math.ceil(len(right) / stages_left)
                    left_part = left[-left_len:] if left_len else ""
                    right_part = right[-right_len:] if right_len else ""
                    step_name = f"{name}_PCR{index+1}"
                    pcr, design, row = reaction(current, begin, finish, left_part, right_part, step_name)
                    preparations.append(row)
                    left = left[:-left_len] if left_len else ""
                    right = right[:-right_len] if right_len else ""
                    current = resolve_sequence_record(pcr)
                    current.id = current.name = step_name + "_product"
                    begin, finish = 0, len(current)
                break
            except ValueError as stage_error:
                if not str(stage_error).startswith("OLIGO_LENGTH_LIMIT") or stage_count == maximum_stages:
                    raise
        if not preparations:
            raise ValueError("No PCR preparation could be generated")
    if pcr["amplicon"] != expected:
        raise ValueError("PCR_PREPARATION_MISMATCH: actual successive PCR does not match requested interval and additions")
    return {"sequence": pcr["amplicon"], "features": pcr["features"], "topology": "linear",
            "pcr": pcr, "design": design, "preparation": preparations,
            "primers": [primer for row in preparations for primer in row["primers"]]}


def check_primer_dimers(
    primer1: str,
    primer2: str | None = None,
) -> dict[str, Any]:
    """Check for primer-dimer (heterodimer) or self-dimer (homodimer) base-pairing.

    Scans for complementary alignments between the two primers, specifically flagging
    3' end complementarity which causes catastrophic primer-dimer artifacts in PCR.
    """
    p1 = str(primer1.seq if isinstance(primer1, SeqRecord) else primer1).strip().upper()
    p2 = str(primer2.seq if isinstance(primer2, SeqRecord) else primer2).strip().upper() if primer2 else p1
    is_self = p1 == p2

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
                    # Keep the largest run seen anywhere in this alignment.
                    # The run may be followed by a mismatch before the scan
                    # reaches its final position.
                    max_continuous_match = max(max_continuous_match, match_len)
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
