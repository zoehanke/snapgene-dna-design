# -*- coding: utf-8 -*-
"""core/tools/restriction.py - Atomic restriction endonuclease analysis tool.

Scans sequences or files for restriction sites, determines cut coordinates,
cut counts, overhang types (5', 3', blunt), and recognizes Type IIS enzymes.
"""
from __future__ import annotations

import pathlib
import re
from typing import Any

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.tools.inspection import _load_record


def get_enzyme(enzyme_name: str):
    """Resolve a restriction enzyme name case-insensitively.

    Returns a Bio.Restriction enzyme class, or raises ValueError.
    """
    import Bio.Restriction as restr
    name = enzyme_name.strip()
    # exact attribute lookup first (handles EcoRI, BamHI, etc.)
    for candidate in (name, name.capitalize()):
        try:
            return getattr(restr, candidate)
        except AttributeError:
            continue
    # case-insensitive fallback over all known enzymes
    lower = name.lower()
    for attr in dir(restr):
        if attr.lower() == lower:
            return getattr(restr, attr)
    raise ValueError(f"Unknown restriction enzyme: {enzyme_name}")


def enzyme_sites(seq: str | Seq, enzyme: Any, circular: bool = False) -> list[int]:
    """Return 1-based first-base-after-top-cut positions.

    Follows Bio.Restriction.search semantics. Cut coordinate, not recognition start.
    """
    try:
        positions = list(enzyme.search(Seq(str(seq)), linear=not circular))
        if circular and len(seq):
            positions = [((int(pos) - 1) % len(seq)) + 1 for pos in positions]
        return sorted(set(int(pos) for pos in positions))
    except Exception:
        return []


def restriction_hits(seq: str | Seq, enzyme: Any, circular: bool = False) -> list[dict[str, Any]]:
    """Return recognition sites and explicit double-strand cut boundaries.

    Circular hits may have ``end < start`` and ``wraps_origin=True``.
    Non-palindromic sites are searched on both orientations.
    """
    s = str(seq).upper()
    site = str(enzyme.site).upper()
    n, width = len(s), len(site)
    iupac = {
        "A": "A", "C": "C", "G": "G", "T": "T", "U": "U",
        "R": "AG", "Y": "CT", "S": "GC", "W": "AT", "K": "GT",
        "M": "AC", "B": "CGT", "D": "AGT", "H": "ACT",
        "V": "ACG", "N": "ACGT",
    }

    def matches(window, pattern):
        return len(window) == len(pattern) and all(
            base in iupac.get(symbol, symbol)
            for base, symbol in zip(window, pattern))
    if not n or not width:
        return []

    rc_site = str(Seq(site).reverse_complement())
    if circular:
        repeats = ((width - 1) // n) + 2
        searchable = (s * repeats)[:n + width - 1]
        starts = range(n)
    else:
        searchable = s
        starts = range(max(n - width + 1, 0))

    hits = []
    for start0 in starts:
        window = searchable[start0:start0 + width]
        orientations = []
        if matches(window, site):
            orientations.append(1)
        if rc_site != site and matches(window, rc_site):
            orientations.append(-1)
        for strand in orientations:
            end0 = start0 + width
            wraps = circular and end0 > n
            end_1based = ((end0 - 1) % n) + 1 if circular else end0
            fst5 = int(enzyme.fst5)
            fst3 = int(enzyme.fst3)
            if strand == 1:
                top_cut = start0 + fst5
                bottom_cut = start0 + width + fst3
            else:
                top_cut = start0 - fst3
                bottom_cut = start0 + width - fst5
            raw_top_cut, raw_bottom_cut = top_cut, bottom_cut
            if circular:
                top_cut %= n
                bottom_cut %= n
            hits.append({
                "start": start0 + 1,
                "end": end_1based,
                "strand": strand,
                "wraps_origin": wraps,
                "recognition_start0": start0,
                "recognition_end0": end0,
                "top_cut_boundary_0based": top_cut,
                "bottom_cut_boundary_0based": bottom_cut,
                "raw_top_cut_boundary_0based": raw_top_cut,
                "raw_bottom_cut_boundary_0based": raw_bottom_cut,
                "top_cut_after_base_1based": top_cut,
                "bottom_cut_after_base_1based": bottom_cut,
                "cuts_within_sequence": (
                    circular or (
                        0 <= raw_top_cut <= n and 0 <= raw_bottom_cut <= n
                    )
                ),
            })
    return hits


COMMON_CLONING_ENZYMES = [
    "EcoRI", "BamHI", "HindIII", "XhoI", "NdeI", "NotI", "NcoI", "SalI", "SacI",
    "KpnI", "PstI", "SpeI", "XbaI", "BglII", "ClaI", "DpnI", "SmaI", "EcoRV",
    "BsaI", "BsmBI", "Esp3I", "BbsI", "SapI", "AarI",
]


def find_restriction_sites(
    file_path_or_seq: str | pathlib.Path | SeqRecord,
    enzymes: list[str] | None = None,
    topology: str | None = None,
) -> dict[str, Any]:
    """Analyze restriction endonuclease sites in DNA sequence.

    Args:
        file_path_or_seq: Path to sequence file, SeqRecord, or raw DNA string.
        enzymes: List of enzyme names. Defaults to COMMON_CLONING_ENZYMES.
        topology: "circular" or "linear". If None, inferred from record.

    Returns:
        dict containing per-enzyme site locations, counts, overhang geometries,
        and single-cutter / unique-cutter classifications.
    """
    from core.io.input_resolution import resolve_sequence_input
    rec, seq_str = resolve_sequence_input(file_path_or_seq, default_topology=topology or "linear")
    topo = topology or rec.annotations.get("topology", "linear")

    is_circular = (topo.lower() == "circular")
    n = len(seq_str)
    query_enzymes = list(enzymes) if enzymes else COMMON_CLONING_ENZYMES

    results: dict[str, Any] = {}
    unique_cutters = []
    double_cutters = []
    non_cutters = []
    unknown_enzymes = []
    warnings = []

    for name in query_enzymes:
        try:
            enz = get_enzyme(name)
        except Exception:
            unknown_enzymes.append(name)
            warnings.append(f"Restriction enzyme '{name}' is unrecognized by REBASE database; site scan omitted.")
            continue

        raw_hits = restriction_hits(Seq(seq_str), enz, circular=is_circular)
        sites = []
        for h in raw_hits:
            recog_start = h.get("recognition_start0", h.get("site_start_0based", h.get("start", 1) - 1))
            recog_seq = h.get("site", str(getattr(enz, "site", "")))
            top_cut = h.get("top_cut_boundary_0based", 0)
            bottom_cut = h.get("bottom_cut_boundary_0based", 0)
            overhang_type = h.get("overhang_type", "blunt")
            overhang_seq = h.get("overhang_sequence", "")
            cuts_within = h.get("cuts_within_sequence", True)

            # Check for prokaryotic Dam/Dcm methylation overlap
            recog_len = len(recog_seq) if recog_seq else 6
            blocked_by = []
            for m_name, m_pat in [("dam", "GATC"), ("dcm", "CC[AT]GG"), ("ecoki", "AAC[ACGT]{6}GTGC")]:
                for m in re.finditer(m_pat, seq_str):
                    m_start = m.start()
                    m_end = m.end()
                    if not (recog_start + recog_len <= m_start or m_end <= recog_start):
                        blocked_by.append(f"{m_name} overlap ({m.group(0)} at bp {m_start})")

            sites.append({
                "recognition_start_0based": recog_start,
                "recognition_sequence": recog_seq,
                "top_cut_boundary_0based": top_cut,
                "bottom_cut_boundary_0based": bottom_cut,
                "overhang_type": overhang_type,
                "overhang_sequence": overhang_seq,
                "cuts_within_sequence": cuts_within,
                "strand": h.get("strand", 1),
                "methylation_warnings": blocked_by,
            })

        count = len(sites)
        is_type_iis = name in ("BsaI", "BsmBI", "Esp3I", "BbsI", "SapI", "AarI", "PaqCI", "FokI", "BtsI") or getattr(enz, "fst5", 0) > len(str(getattr(enz, "site", "")))
        recog_pattern = str(enz.site) if hasattr(enz, "site") else ""

        results[name] = {
            "enzyme": name,
            "recognition_sequence": recog_pattern,
            "is_type_iis": is_type_iis,
            "cut_count": count,
            "cuts": sites,
        }

        if count == 1:
            unique_cutters.append(name)
        elif count == 2:
            double_cutters.append(name)
        elif count == 0:
            non_cutters.append(name)

    return {
        "sequence_length": n,
        "topology": topo,
        "enzymes_analyzed": len(results),
        "unique_cutters": unique_cutters,
        "double_cutters": double_cutters,
        "non_cutters": non_cutters,
        "unknown_enzymes": unknown_enzymes,
        "warnings": warnings,
        "enzymes": results,
    }


def check_overhang_compatibility(
    overhang1: str,
    overhang2: str,
    type1: str = "5prime",
    type2: str = "5prime",
) -> dict[str, Any]:
    """Check whether two overhangs can ligate (sticky end complementarity or blunt)."""
    o1 = str(overhang1 or "").strip().upper()
    o2 = str(overhang2 or "").strip().upper()
    t1 = str(type1).lower()
    t2 = str(type2).lower()

    if t1 == "blunt" and t2 == "blunt":
        return {
            "compatible": True,
            "type": "blunt-blunt",
            "message": "Both ends are blunt; non-directional ligation possible",
        }

    if t1 != t2:
        return {
            "compatible": False,
            "type": f"{t1}-{t2}",
            "message": f"End geometry mismatch: {t1} cannot ligate with {t2}",
        }

    o2_rc = str(Seq(o2).reverse_complement()) if o2 else ""
    # Compatible if either:
    # 1. Matching top-strand junction motif (e.g. Golden Gate / Type IIS convention): o1 == o2
    # 2. Opposing single-stranded extensions (Watson-Crick complementary annealing): o1 == o2_rc
    is_compat = (o1 == o2 or o1 == o2_rc) and len(o1) > 0

    return {
        "compatible": is_compat,
        "type": f"{t1}-{t2}",
        "overhang1": o1,
        "overhang2": o2,
        "overhang2_rc": o2_rc,
        "message": "Sticky ends are complementary and ligatable" if is_compat else f"Sticky ends do not match: {o1} vs {o2}",
    }


def digest_sequence(
    seq: str,
    enzyme: str,
    circular: bool = False,
) -> dict[str, Any]:
    """Digest a DNA sequence with a restriction endonuclease, returning cleaved fragments and their end geometries."""
    enz = get_enzyme(enzyme)
    s = str(seq).strip().upper()
    hits = restriction_hits(Seq(s), enz, circular=circular)

    if not hits:
        return {
            "enzyme": enzyme,
            "cut_count": 0,
            "fragments": [{"fragment_index": 0, "sequence": s, "length": len(s), "left_end": "blunt", "right_end": "blunt"}],
        }

    # Sort cuts
    cuts = sorted(hits, key=lambda h: h["top_cut_boundary_0based"])
    n = len(s)
    frags = []

    def _overhang_info(h, dna_str):
        if not h:
            return "", "blunt"
        t = h.get("top_cut_boundary_0based", 0)
        b = h.get("bottom_cut_boundary_0based", 0)
        if t == b:
            return "", "blunt"
        ov = dna_str[min(t, b) : max(t, b)]
        ov_type = "5prime" if t < b else "3prime"
        return ov, ov_type

    if not circular:
        # Linear cuts produce len(cuts) + 1 fragments
        boundaries = [0] + [c["top_cut_boundary_0based"] for c in cuts] + [n]
        for i in range(len(boundaries) - 1):
            sub = s[boundaries[i] : boundaries[i + 1]]
            l_hit = cuts[i - 1] if i > 0 else None
            r_hit = cuts[i] if i < len(cuts) else None
            l_ov, l_geom = _overhang_info(l_hit, s)
            r_ov, r_geom = _overhang_info(r_hit, s)

            frags.append({
                "fragment_index": i,
                "sequence": sub,
                "length": len(sub),
                "left_overhang": l_ov,
                "left_geometry": l_geom,
                "right_overhang": r_ov,
                "right_geometry": r_geom,
            })
    else:
        # Circular cuts produce len(cuts) fragments
        b_coords = [c["top_cut_boundary_0based"] for c in cuts]
        num_cuts = len(b_coords)
        for i in range(num_cuts):
            start_b = b_coords[i]
            end_b = b_coords[(i + 1) % num_cuts]
            sub = s[start_b:end_b] if end_b > start_b else (s[start_b:] + s[:end_b])
            l_hit = cuts[i]
            r_hit = cuts[(i + 1) % num_cuts]
            l_ov, l_geom = _overhang_info(l_hit, s)
            r_ov, r_geom = _overhang_info(r_hit, s)

            frags.append({
                "fragment_index": i,
                "sequence": sub,
                "length": len(sub),
                "left_overhang": l_ov,
                "left_geometry": l_geom,
                "right_overhang": r_ov,
                "right_geometry": r_geom,
            })

    return {
        "enzyme": enzyme,
        "cut_count": len(hits),
        "fragment_count": len(frags),
        "fragments": frags,
    }


def digest_type_iis(
    fragment_seq: str,
    enzyme: str = "BsaI",
) -> dict[str, Any]:
    """Perform single-fragment Type IIS digestion (e.g. BsaI, BsmBI), stripping recognition sites and liberating cohesive overhangs."""
    enz = get_enzyme(enzyme)
    s = str(fragment_seq).strip().upper()
    hits = restriction_hits(Seq(s), enz, circular=False)

    if len(hits) < 2:
        raise ValueError(f"Type IIS fragment must have at least 2 flanking sites; found {len(hits)}")

    hits.sort(key=lambda h: h["recognition_start0"])
    h_left, h_right = hits[0], hits[-1]

    t_left = h_left["top_cut_boundary_0based"]
    b_left = h_left["bottom_cut_boundary_0based"]
    t_right = h_right["top_cut_boundary_0based"]
    b_right = h_right["bottom_cut_boundary_0based"]

    left_cut = min(t_left, b_left)
    left_cut_max = max(t_left, b_left)
    left_ov = s[left_cut:left_cut_max]

    right_cut = min(t_right, b_right)
    right_cut_max = max(t_right, b_right)
    right_ov = s[right_cut:right_cut_max]

    insert_core = s[left_cut:right_cut_max]

    return {
        "original_sequence": s,
        "insert_core": insert_core,
        "insert_length": len(insert_core),
        "left_overhang": left_ov,
        "right_overhang": right_ov,
        "enzyme": enzyme,
        "stripped_5prime_site": s[:left_cut],
        "stripped_3prime_site": s[right_cut_max:],
    }


def fill_or_chew_overhang(
    seq: str,
    left_overhang: str = "",
    right_overhang: str = "",
    overhang_type: str = "5prime",
    action: str = "fill_in",
) -> dict[str, Any]:
    """Simulate enzymatic end-repair (Klenow / T4 DNA Polymerase) to blunt DNA sticky ends.

    action="fill_in": Fills in 5' overhangs with complementary nucleotides.
    action="chew_back": Uses 3'->5' exonuclease activity to remove 3' single-stranded overhangs.
    """
    s = str(seq).strip().upper()
    left_ov = str(left_overhang).strip().upper()
    right_ov = str(right_overhang).strip().upper()
    act = str(action).lower()
    ov_type = str(overhang_type).lower()

    if act == "fill_in":
        if "3" in ov_type:
            # 3' overhangs cannot be filled in by 5'->3' polymerase
            blunted = s
        else:
            # Fill in 5' overhangs
            res_seq = s
            if left_ov and not res_seq.startswith(left_ov):
                res_seq = left_ov + res_seq
            if right_ov and not res_seq.endswith(right_ov):
                res_seq = res_seq + right_ov
            blunted = res_seq
    elif act == "chew_back":
        if "5" in ov_type:
            # 3'->5' exonuclease does not chew 5' overhangs
            blunted = s
        else:
            # Chew back 3' protruding overhangs
            res_seq = s
            if left_ov and res_seq.startswith(left_ov):
                res_seq = res_seq[len(left_ov):]
            if right_ov and res_seq.endswith(right_ov):
                res_seq = res_seq[:-len(right_ov)]
            blunted = res_seq
    else:
        blunted = s

    return {
        "original_length": len(s),
        "blunted_sequence": blunted,
        "blunted_length": len(blunted),
        "action_applied": act,
        "end_type": "blunt",
    }
