# -*- coding: utf-8 -*-
"""core/tools/fusion.py - Atomic in-frame protein fusion tool.

Fuses two protein coding sequences with optional linkers, stripping premature
stop codons and maintaining reading frames.
"""
from __future__ import annotations

from Bio.Seq import Seq

from core.tools.sequence_ops import check_reading_frame


STOP_CODONS = {"TAA", "TAG", "TGA"}


def fuse_in_frame(
    partner5_seq: str,
    partner3_seq: str,
    linker_seq: str = "",
    strip_p5_stop: bool = True,
    add_terminal_stop: bool = True,
) -> dict:
    """Fuse two protein coding sequences in frame with optional linker.

    Args:
        partner5_seq: 5' partner CDS sequence.
        partner3_seq: 3' partner CDS sequence (e.g. epitope tag or fusion domain).
        linker_seq: Optional linker DNA sequence (e.g. (G4S) linker).
        strip_p5_stop: Whether to automatically strip terminal stop codon from partner5.
        add_terminal_stop: Whether to ensure the final fusion ends with a stop codon.

    Returns:
        dict with fusion_sequence, fusion_length, translation, in_frame status,
        and stop codon report.
    """
    p5 = str(partner5_seq).strip().upper()
    p3 = str(partner3_seq).strip().upper()
    linker = str(linker_seq).strip().upper()

    p5_stop_stripped = False
    if strip_p5_stop and len(p5) >= 3 and p5[-3:] in STOP_CODONS:
        p5 = p5[:-3]
        p5_stop_stripped = True

    if len(linker) % 3 != 0:
        raise ValueError(
            f"Linker sequence length ({len(linker)} bp) is not a multiple of 3, causing a frameshift!"
        )

    if len(p5) % 3 != 0:
        raise ValueError(
            f"5' partner CDS length ({len(p5)} bp) is not a multiple of 3!"
        )

    p3_had_stop = bool(len(p3) >= 3 and p3[-3:] in STOP_CODONS)
    if add_terminal_stop and not p3_had_stop:
        p3 += "TAA"

    fusion_dna = p5 + linker + p3
    rf_audit = check_reading_frame(fusion_dna)

    return {
        "fusion_sequence": fusion_dna,
        "fusion_length": len(fusion_dna),
        "partner5_length": len(p5),
        "partner5_stop_stripped": p5_stop_stripped,
        "linker_length": len(linker),
        "partner3_length": len(p3),
        "is_in_frame": rf_audit["is_multiple_of_three"],
        "has_premature_stop": rf_audit["has_premature_stop"],
        "premature_stop_positions": rf_audit["premature_stop_positions"],
        "terminal_stop": rf_audit["terminal_stop"],
        "translation": rf_audit["translation"],
    }
