# -*- coding: utf-8 -*-
"""core/tools/crispr.py - Atomic CRISPR/Cas Gene Editing and HDR Donor Design Tools.

Provides deterministic, side-effect free tools for:
1. sgRNA candidate scanning with PAM recognition, GC content, and Pol III poly-T termination checks.
2. sgRNA forward/reverse cloning oligo duplex preparation for U6 plasmids (pX458, pX459, lentiCRISPR).
3. Homology-Directed Repair (HDR) donor template design (ssODN or plasmid arms) with silent PAM mutation to prevent re-cleavage.
"""
from __future__ import annotations

import pathlib
import re
from typing import Any

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.tools.inspection import _load_record
from core.tools.translation import reverse_complement


def design_crispr_grna(
    target_seq_or_file: str | pathlib.Path | SeqRecord,
    nuclease: str = "SpCas9",
    start: int | None = None,
    end: int | None = None,
    circular: bool = False,
) -> list[dict[str, Any]]:
    """Scan DNA sequence for CRISPR sgRNA candidate target sites.

    Args:
        target_seq_or_file: Target DNA sequence or file.
        nuclease: 'SpCas9' (NGG, 3' side, 20 nt spacer) or 'AsCas12a' (TTTV, 5' side, 23 nt spacer).
        start: Optional 0-based start coordinate to restrict scan.
        end: Optional 0-based end coordinate to restrict scan.
        circular: Whether sequence is circular.

    Returns:
        List of candidate sgRNA dictionaries sorted by objective quality score.
    """
    from core.io.input_resolution import resolve_sequence_input
    rec, seq = resolve_sequence_input(target_seq_or_file)

    n = len(seq)
    scan_start = 0 if start is None else max(0, start)
    scan_end = n if end is None else min(n, end)

    nuc_lower = nuclease.lower()
    is_cas12 = "cas12" in nuc_lower or "cpf1" in nuc_lower

    candidates = []
    search_seq = (seq + seq[:30]) if circular else seq

    if not is_cas12:
        # SpCas9: 20 nt spacer + NGG PAM (3' PAM)
        # Search top strand (+1): [spacer: 20 nt][PAM: .GG]
        pat_top = re.compile(r"(?=([ACGT]{20}[ACGT]GG))")
        for m in pat_top.finditer(search_seq):
            pos = m.start()
            if pos >= n:
                break
            full_hit = m.group(1)
            spacer = full_hit[:20]
            pam = full_hit[20:23]
            cut_pos = (pos + 17) % n

            if (scan_start <= pos and (pos + 23) <= scan_end) or (circular and pos < n):
                candidates.append(_evaluate_grna_candidate(spacer, pam, pos, (pos + 23) % n, 1, cut_pos, n))

        # Search bottom strand (-1): reverse complement of target has NGG PAM
        # Top strand contains CCN + 20 nt spacer_rc: [CCN: 3 nt][spacer_rc: 20 nt]
        pat_bottom = re.compile(r"(?=(CC[ACGT]([ACGT]{20})))")
        for m in pat_bottom.finditer(search_seq):
            pos = m.start()
            if pos >= n:
                break
            pam_rc = m.group(1)[:3]
            spacer_rc = m.group(1)[3:23]
            pam = str(Seq(pam_rc).reverse_complement())
            spacer = str(Seq(spacer_rc).reverse_complement())
            cut_pos = (pos + 6) % n

            if (scan_start <= pos and (pos + 23) <= scan_end) or (circular and pos < n):
                candidates.append(_evaluate_grna_candidate(spacer, pam, pos, (pos + 23) % n, -1, cut_pos, n))
    else:
        # AsCas12a: TTTV PAM on 5' end + 23 nt spacer
        # Top strand: [TTT[ACG]: 4 nt][spacer: 23 nt]
        pat_top = re.compile(r"(?=(TTT[ACG]([ACGT]{23})))")
        for m in pat_top.finditer(search_seq):
            pos = m.start()
            if pos >= n:
                break
            pam = m.group(1)[:4]
            spacer = m.group(1)[4:27]
            cut_pos = (pos + 22) % n

            if (scan_start <= pos and (pos + 27) <= scan_end) or (circular and pos < n):
                candidates.append(_evaluate_grna_candidate(spacer, pam, pos, (pos + 27) % n, 1, cut_pos, n))

        # Bottom strand: reverse complement has TTTV PAM
        # Top strand contains [spacer_rc: 23 nt][CGT]AAA: 4 nt]
        pat_bottom = re.compile(r"(?=(([ACGT]{23})[CGT]AAA))")
        for m in pat_bottom.finditer(search_seq):
            pos = m.start()
            if pos >= n:
                break
            spacer_rc = m.group(1)[:23]
            pam_rc = m.group(1)[23:27]
            pam = str(Seq(pam_rc).reverse_complement())
            spacer = str(Seq(spacer_rc).reverse_complement())
            cut_pos = (pos + 5) % n

            if (scan_start <= pos and (pos + 27) <= scan_end) or (circular and pos < n):
                candidates.append(_evaluate_grna_candidate(spacer, pam, pos, (pos + 27) % n, -1, cut_pos, n))

    # Sort candidates by objective quality score descending
    candidates.sort(key=lambda c: c["quality_score"], reverse=True)
    return candidates


def _evaluate_grna_candidate(
    spacer: str,
    pam: str,
    start_0b: int,
    end_0b: int,
    strand: int,
    cut_pos: int,
    total_len: int,
) -> dict[str, Any]:
    n = len(spacer)
    gc_count = spacer.count("G") + spacer.count("C")
    gc_pct = round((gc_count / n) * 100.0, 1)

    warnings = []
    # Pol III U6 transcription termination check: >= 4 T's in a row aborts transcription!
    has_poly_t = ("TTTT" in spacer)
    if has_poly_t:
        warnings.append("Poly-T motif (TTTT) present: causes premature termination by RNA Pol III (U6 promoter)")

    if gc_pct < 40.0:
        warnings.append(f"Low GC content ({gc_pct}%); ideal range is 40-70%")
    elif gc_pct > 70.0:
        warnings.append(f"High GC content ({gc_pct}%); risk of off-target or secondary structure")

    # Objective heuristic score (0 - 100)
    score = 80.0
    if 45.0 <= gc_pct <= 65.0:
        score += 10.0
    elif gc_pct < 35.0 or gc_pct > 75.0:
        score -= 20.0

    if has_poly_t:
        score -= 40.0

    # SpCas9 favors G at 5' end for U6 promoter transcription initiation
    if spacer.startswith("G"):
        score += 10.0

    return {
        "spacer": spacer,
        "pam": pam,
        "strand": strand,
        "target_interval_0based": [start_0b, end_0b],
        "cut_position_0based": cut_pos,
        "gc_percent": gc_pct,
        "has_poly_t": has_poly_t,
        "quality_score": max(0.0, min(100.0, round(score, 1))),
        "warnings": warnings,
    }


def prepare_grna_oligos(
    spacer_seq: str,
    vector_type: str = "BbsI",
) -> dict[str, Any]:
    """Prepare top and bottom forward/reverse oligos with cloning overhangs for sgRNA vectors.

    For BbsI/BsmBI plasmids (e.g. pX458, pX459, lentiCRISPRv2):
    - Top oligo: CACC + [optional G] + spacer
    - Bottom oligo: AAAC + reverse_complement([optional G] + spacer)
    An extra 'G' is automatically prepended if the 20 nt spacer does not start with G,
    as human U6 RNA Pol III promoter requires a 5' Guanine for high-efficiency transcription.
    """
    clean_spacer = str(spacer_seq).strip().upper()
    vec = str(vector_type).strip().lower()

    u6_needs_g = not clean_spacer.startswith("G")
    init_g = "G" if u6_needs_g else ""

    top_seq = init_g + clean_spacer
    bottom_rc = str(Seq(top_seq).reverse_complement())

    if "bsmbi" in vec or "lenti" in vec:
        # lentiCRISPRv2 (BsmBI cut): 5' CACC on top, 5' AAAC on bottom
        fwd_oligo = "CACC" + top_seq
        rev_oligo = "AAAC" + bottom_rc
        overhang_5p = "CACC"
        overhang_3p = "AAAC"
    else:
        # Standard pX330 / pX458 / pX459 (BbsI cut): 5' CACC on top, 5' AAAC on bottom
        fwd_oligo = "CACC" + top_seq
        rev_oligo = "AAAC" + bottom_rc
        overhang_5p = "CACC"
        overhang_3p = "AAAC"

    return {
        "spacer": clean_spacer,
        "vector_type": vector_type,
        "u6_5prime_g_added": u6_needs_g,
        "forward_oligo": {
            "sequence": fwd_oligo,
            "length": len(fwd_oligo),
            "description": f"Top strand oligo with {overhang_5p} sticky overhang",
        },
        "reverse_oligo": {
            "sequence": rev_oligo,
            "length": len(rev_oligo),
            "description": f"Bottom strand oligo with {overhang_3p} sticky overhang",
        },
    }


def design_hdr_donor(
    target_seq_or_file: str | pathlib.Path | SeqRecord,
    cut_position_0based: int,
    edit_dna: str,
    left_arm_length: int = 50,
    right_arm_length: int = 50,
    grna_seq: str = "",
    grna_strand: int = 1,
) -> dict[str, Any]:
    """Design a Homology-Directed Repair (HDR) donor template (ssODN or plasmid arms).

    Args:
        target_seq_or_file: Target locus sequence or file.
        cut_position_0based: 0-based index of Cas cut site.
        edit_dna: New sequence to insert/substitute at the cut site.
        left_arm_length: Length of left homology arm (e.g. 40-60 bp for ssODN, 500-800 bp for plasmid).
        right_arm_length: Length of right homology arm.
        grna_seq: Optional 20-nt sgRNA sequence used for cutting.
        grna_strand: Strand of the sgRNA (+1 or -1).

    Returns:
        dict with donor_sequence, left_arm, right_arm, donor_type, and PAM silencing report.
    """
    from core.io.input_resolution import resolve_sequence_input
    rec, seq = resolve_sequence_input(target_seq_or_file)

    n = len(seq)
    s_left = max(0, cut_position_0based - left_arm_length)
    e_right = min(n, cut_position_0based + right_arm_length)

    left_arm = seq[s_left:cut_position_0based]
    right_arm = seq[cut_position_0based:e_right]
    edit = str(edit_dna).strip().upper()

    # Check for sgRNA / PAM in donor arms to prevent Cas re-cleavage of repair template
    pam_silenced = False
    silencing_details = ""

    if grna_seq:
        g = grna_seq.strip().upper()
        # Check if PAM or seed region is in right arm or left arm
        # For SpCas9: PAM is 3 bp downstream of cut on top strand (+1): right_arm starts at cut+3?
        # Actually cut is 3 bp upstream of PAM, so PAM is at bases [3:6] of right_arm on top strand!
        if grna_strand == 1 and len(right_arm) >= 6:
            # Top strand (+1): cut is at index 0 of right_arm, bases [0:3] are spacer ends, PAM (NGG) is at [3:6]
            pam_candidate = right_arm[3:6]
            if pam_candidate.endswith("GG"):
                old_base = right_arm[5]
                new_base = "A" if old_base == "G" else "T"
                right_arm = right_arm[:5] + new_base + right_arm[6:]
                pam_silenced = True
                silencing_details = f"Silenced PAM {pam_candidate} -> {right_arm[3:6]} (G->{new_base} at right arm bp 5) to prevent Cas9 re-cleavage (Paquet et al. 2016 Nature)"
        elif grna_strand == -1 and len(left_arm) >= 6:
            # Bottom strand (-1): cut is at end of left_arm, PAM reverse complement (CCN) is at left_arm[-6:-3]
            pam_candidate_rc = left_arm[-6:-3]
            if pam_candidate_rc.startswith("CC"):
                old_base = left_arm[-6]
                new_base = "T" if old_base == "C" else "A"
                left_arm = left_arm[:-6] + new_base + left_arm[-5:]
                pam_silenced = True
                silencing_details = f"Silenced PAM reverse complement {pam_candidate_rc} -> {left_arm[-6:-3]} to prevent Cas9 re-cleavage"

    donor_seq = left_arm + edit + right_arm
    total_len = len(donor_seq)
    donor_type = "ssODN" if total_len <= 200 else "double-stranded plasmid donor"

    return {
        "donor_sequence": donor_seq,
        "total_length": total_len,
        "donor_type": donor_type,
        "left_homology_arm": left_arm,
        "left_arm_length": len(left_arm),
        "edit_payload": edit,
        "edit_length": len(edit),
        "right_homology_arm": right_arm,
        "right_arm_length": len(right_arm),
        "pam_silenced_in_donor": pam_silenced,
        "silencing_details": silencing_details,
    }


def extract_homology_arms(
    target_seq_or_file: str | pathlib.Path | SeqRecord,
    cut_position_0based: int,
    left_arm_length: int = 50,
    right_arm_length: int = 50,
    circular: bool | None = None,
) -> dict[str, Any]:
    """Extract left and right homology arms centered at a target cut/insertion site."""
    from core.io.input_resolution import resolve_sequence_input
    rec, seq = resolve_sequence_input(target_seq_or_file)
    topo = rec.annotations.get("topology")

    n = len(seq)
    is_circular = (circular if circular is not None else (topo == "circular"))
    cut = (cut_position_0based % n) if is_circular and n > 0 else cut_position_0based
    warnings = []

    if is_circular and n > 0:
        # Wrap around origin if needed
        # Left arm: [cut - left_arm_length, cut)
        if cut - left_arm_length >= 0:
            left_arm = seq[cut - left_arm_length : cut]
            left_interval = [cut - left_arm_length, cut]
        else:
            wrap_len = left_arm_length - cut
            left_arm = seq[n - wrap_len :] + seq[:cut]
            left_interval = [n - wrap_len, cut]

        # Right arm: [cut, cut + right_arm_length)
        if cut + right_arm_length <= n:
            right_arm = seq[cut : cut + right_arm_length]
            right_interval = [cut, cut + right_arm_length]
        else:
            wrap_len = (cut + right_arm_length) - n
            right_arm = seq[cut:] + seq[:wrap_len]
            right_interval = [cut, wrap_len]
    else:
        s_left = max(0, cut - left_arm_length)
        e_right = min(n, cut + right_arm_length)
        if cut - left_arm_length < 0:
            warnings.append(f"Left homology arm truncated by 5' template boundary (requested {left_arm_length} nt, obtained {cut - s_left} nt)")
        if cut + right_arm_length > n:
            warnings.append(f"Right homology arm truncated by 3' template boundary (requested {right_arm_length} nt, obtained {e_right - cut} nt)")
        left_arm = seq[s_left:cut]
        right_arm = seq[cut:e_right]
        left_interval = [s_left, cut]
        right_interval = [cut, e_right]

    return {
        "cut_position_0based": cut,
        "left_homology_arm": left_arm,
        "left_arm_interval": left_interval,
        "left_arm_length": len(left_arm),
        "right_homology_arm": right_arm,
        "right_arm_interval": right_interval,
        "right_arm_length": len(right_arm),
        "circular": is_circular,
        "warnings": warnings,
    }
