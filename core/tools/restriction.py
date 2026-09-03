# -*- coding: utf-8 -*-
"""core/tools/restriction.py - Atomic restriction endonuclease analysis tool.

Scans sequences or files for restriction sites, determines cut coordinates,
cut counts, overhang types (5', 3', blunt), and recognizes Type IIS enzymes.
"""
from __future__ import annotations

import pathlib
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

    for name in query_enzymes:
        try:
            enz = get_enzyme(name)
        except Exception:
            continue

        raw_hits = restriction_hits(Seq(seq_str), enz, circular=is_circular)
        sites = []
        for h in raw_hits:
            recog_seq = h.get("site", "")
            recog_start = h.get("site_start_0based", 0)
            top_cut = h.get("top_cut_boundary_0based", 0)
            bottom_cut = h.get("bottom_cut_boundary_0based", 0)
            overhang_type = h.get("overhang_type", "blunt")
            overhang_seq = h.get("overhang_sequence", "")
            cuts_within = h.get("cuts_within_sequence", True)

            sites.append({
                "recognition_start_0based": recog_start,
                "recognition_sequence": recog_seq,
                "top_cut_boundary_0based": top_cut,
                "bottom_cut_boundary_0based": bottom_cut,
                "overhang_type": overhang_type,
                "overhang_sequence": overhang_seq,
                "cuts_within_sequence": cuts_within,
                "strand": h.get("strand", 1),
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
        "enzymes": results,
    }
