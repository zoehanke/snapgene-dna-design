# -*- coding: utf-8 -*-
"""core/tools/sequence_ops.py - Atomic sequence operations tool.

Provides topology-aware sequence extraction, reading frame verification,
in-silico translation, and sequence mutagenesis.
"""
from __future__ import annotations

import hashlib
import pathlib
from typing import Any

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.interval import extract_interval
from core.tools.inspection import _load_record


def extract_subsequence(
    file_path_or_record: str | pathlib.Path | SeqRecord,
    start: int,
    end: int,
    strand: int = 1,
    topology: str = "linear",
    wraps_origin: bool = True,
    whole_record_approved: bool = True,
) -> dict[str, Any]:
    """Extract sub-sequence with rigorous topology, circular-wrap and strand handling."""
    rec = _load_record(file_path_or_record)
    topo = topology or rec.annotations.get("topology", "linear")

    extracted = extract_interval(
        record=rec,
        start0=start,
        end0=end,
        topology=topo,
        wraps_origin=wraps_origin,
        strand=strand,
        whole_record_approved=whole_record_approved,
    )

    seq_upper = extracted.upper()
    return {
        "sequence": seq_upper,
        "length": len(seq_upper),
        "sha256": hashlib.sha256(seq_upper.encode("utf-8")).hexdigest().upper(),
        "interval_0based": [start, end],
        "strand": strand,
        "topology": topo,
    }


def check_reading_frame(
    dna_seq: str,
    start_offset: int = 0,
    transl_table: int = 1,
) -> dict[str, Any]:
    """Check whether a coding sequence maintains an open reading frame without premature stops."""
    seq_clean = str(dna_seq).upper()[start_offset:]
    rem = len(seq_clean) % 3

    # Trim terminal codon if incomplete
    complete_codons_len = len(seq_clean) - rem
    coding_dna = seq_clean[:complete_codons_len]

    stops = []
    premature_stops = []
    aa_list = []

    for idx in range(0, complete_codons_len, 3):
        codon = coding_dna[idx : idx + 3]
        if codon in ("TAA", "TAG", "TGA"):
            codon_pos = start_offset + idx
            stops.append(codon_pos)
            if idx < complete_codons_len - 3:
                premature_stops.append(codon_pos)
            aa_list.append("*")
        else:
            try:
                aa = str(Seq(codon).translate(table=transl_table))
                aa_list.append(aa)
            except Exception:
                aa_list.append("X")

    has_terminal_stop = bool(stops and stops[-1] == (start_offset + complete_codons_len - 3))

    return {
        "length_bp": len(seq_clean),
        "start_offset": start_offset,
        "is_multiple_of_three": (rem == 0),
        "leftover_bases": rem,
        "amino_acid_count": len(aa_list),
        "translation": "".join(aa_list),
        "has_premature_stop": (len(premature_stops) > 0),
        "premature_stop_positions": premature_stops,
        "terminal_stop": has_terminal_stop,
    }


def mutate_sequence(
    dna_seq: str,
    mutations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply point mutations, insertions, or deletions with reference verification.

    Args:
        dna_seq: original DNA sequence.
        mutations: list of dicts with:
            - position_0based: int
            - ref_base: str (optional, verified if given)
            - alt_base: str (replacement nucleotide(s), or '' for deletion)

    Returns:
        dict with mutated sequence, updated length, and log of applied mutations.
    """
    seq_list = list(str(dna_seq).upper())
    applied = []

    # Sort mutations in descending order by position so insertions/deletions don't shift earlier indices
    sorted_muts = sorted(mutations, key=lambda x: int(x["position_0based"]), reverse=True)

    for m in sorted_muts:
        pos = int(m["position_0based"])
        ref = str(m.get("ref_base", "")).upper()
        alt = str(m.get("alt_base", "")).upper()

        if pos < 0 or pos >= len(seq_list):
            raise ValueError(f"Mutation position {pos} is out of range [0, {len(seq_list)})")

        if ref and seq_list[pos] != ref:
            raise ValueError(
                f"Reference base mismatch at position {pos}: expected {ref}, found {seq_list[pos]}"
            )

        old_base = seq_list[pos]
        if alt:
            seq_list[pos] = alt
        else:
            # Deletion
            del seq_list[pos]

        applied.append({
            "position_0based": pos,
            "original_base": old_base,
            "new_base": alt,
        })

    mutated_str = "".join(seq_list)
    return {
        "original_length": len(dna_seq),
        "mutated_length": len(mutated_str),
        "sequence": mutated_str,
        "mutations_count": len(applied),
        "applied_mutations": list(reversed(applied)),
    }


def strip_terminal_codons(
    cds_seq: str,
    strip_start: bool = False,
    strip_stop: bool = False,
) -> dict[str, Any]:
    """Strip terminal start (ATG) or stop (TAA/TAG/TGA) codons from a coding sequence.

    Args:
        cds_seq: Nucleotide CDS sequence.
        strip_start: If True and sequence starts with ATG, strip first 3 bp.
        strip_stop: If True and sequence ends with TAA/TAG/TGA, strip last 3 bp.

    Returns:
        dict with modified sequence, original/new length, and stripped flags.
    """
    seq = str(cds_seq).strip().upper()
    n = len(seq)
    start_stripped = False
    stop_stripped = False

    if strip_start and seq.startswith("ATG"):
        seq = seq[3:]
        start_stripped = True

    STOP_CODONS = {"TAA", "TAG", "TGA"}
    if strip_stop and len(seq) >= 3 and seq[-3:] in STOP_CODONS:
        seq = seq[:-3]
        stop_stripped = True

    return {
        "sequence": seq,
        "original_length": n,
        "new_length": len(seq),
        "start_stripped": start_stripped,
        "stop_stripped": stop_stripped,
    }
