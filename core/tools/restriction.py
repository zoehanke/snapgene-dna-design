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

from scripts.sg_common import get_enzyme, restriction_hits
from core.tools.inspection import _load_record


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
    if isinstance(file_path_or_seq, SeqRecord):
        rec = file_path_or_seq
        seq_str = str(rec.seq).upper()
        topo = topology or rec.annotations.get("topology", "linear")
    elif isinstance(file_path_or_seq, (str, pathlib.Path)) and pathlib.Path(file_path_or_seq).exists():
        rec = _load_record(file_path_or_seq)
        seq_str = str(rec.seq).upper()
        topo = topology or rec.annotations.get("topology", "linear")
    else:
        seq_str = str(file_path_or_seq).upper()
        topo = topology or "linear"

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

    o2_rc = str(Seq(o2).reverse_complement())
    is_compat = (o1 == o2_rc) and len(o1) > 0

    return {
        "compatible": is_compat,
        "type": f"{t1}-{t2}",
        "overhang1": o1,
        "overhang2": o2,
        "overhang2_rc": o2_rc,
        "message": "Sticky ends are complementary and ligatable" if is_compat else f"Sticky ends do not match: {o1} vs {o2_rc}",
    }


def digest_sequence(
    seq: str,
    enzyme: str,
    circular: bool = False,
) -> dict[str, Any]:
    """Digest a DNA sequence with a restriction endonuclease, returning cleaved fragments and their end geometries."""
    from scripts.sg_common import get_enzyme, restriction_hits

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
    from scripts.sg_common import get_enzyme, restriction_hits

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

    if act == "fill_in" and "5" in ov_type:
        # Fill in 5' overhangs: adds complementary strand bases to sequence
        blunted = left_ov + s + str(Seq(right_ov).reverse_complement())
    elif act == "chew_back" and "3" in ov_type:
        # Chew back 3' overhang: removes the single-stranded tail
        blunted = s
    else:
        blunted = s

    return {
        "original_length": len(s),
        "blunted_sequence": blunted,
        "blunted_length": len(blunted),
        "action_applied": act,
        "end_type": "blunt",
    }
