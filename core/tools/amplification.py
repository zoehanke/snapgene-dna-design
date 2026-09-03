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
