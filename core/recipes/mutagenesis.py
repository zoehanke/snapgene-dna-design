# -*- coding: utf-8 -*-
"""core/recipes/mutagenesis.py - Standard SOP Recipe for Site-Directed Mutagenesis (SDM).

AUTHORITATIVE SOURCES & CLASSICAL PROTOCOLS:
1. Zheng, L., Baumann, U. and Reymond, J.L. (2004).
   An efficient one-step site-directed and site-saturation mutagenesis protocol.
   Nucleic Acids Research, 32(14), p.e115. doi:10.1093/nar/gnh110.
2. Green, M.R. and Sambrook, J. (2012).
   Molecular Cloning: A Laboratory Manual. 4th ed.
   Cold Spring Harbor Laboratory Press, Cold Spring Harbor, NY.
   Chapter 13: In Vitro Mutagenesis.
3. Agilent Technologies. (2020).
   QuikChange II Site-Directed Mutagenesis Kit Instruction Manual.
"""
from __future__ import annotations

import pathlib
from typing import Any

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.recipes.contract import RecipeResult
from core.tools.amplification import calc_primer_tm
from core.tools.inspection import _load_record
from core.tools.sequence_ops import mutate_sequence
from core.tools.translation import translate_dna

AUTHORITATIVE_SOURCES = [
    {
        "citation": "Zheng et al. (2004). An efficient one-step site-directed and site-saturation mutagenesis protocol. Nucleic Acids Res 32(14):e115.",
        "institution": "University of Bern",
        "doi": "10.1093/nar/gnh110",
        "rules_enforced": [
            "Mutagenic primers must place the desired mutation at or near the center of the oligonucleotide.",
            "Primer must have 10-15 bp of strict complementary wild-type flanking sequence on both sides.",
            "Melting temperature calculated via QuikChange thermodynamic formula: Tm = 81.5 + 0.41(%GC) - 675/N - %mismatch.",
            "Standard QuikChange protocol requires Tm >= 78°C to ensure stable primer-template hybridization.",
        ],
    },
    {
        "citation": "Green, M.R. and Sambrook, J. (2012). Molecular Cloning: A Laboratory Manual (4th ed.). Chapter 13.",
        "institution": "Cold Spring Harbor Laboratory (CSHL)",
        "rules_enforced": [
            "Post-PCR reaction must be treated with 1 uL DpnI endonuclease (37°C, 1 hr) to digest Dam-methylated parental template DNA.",
            "DpnI selection reduces wild-type background colonies by > 100-fold.",
        ],
    },
]


def calc_quikchange_tm(primer_seq: str, mismatch_bp_count: int) -> float:
    """Calculate QuikChange-specific mutagenic primer Tm according to Zheng 2004 & Agilent.

    Formula: Tm = 81.5 + 0.41(%GC) - 675/N - %mismatch
    where N is primer length, %mismatch = (mismatched_bases / N) * 100.
    """
    s = str(primer_seq).upper()
    n = len(s)
    if n == 0:
        return 0.0
    gc_count = s.count("G") + s.count("C")
    gc_pct = (gc_count / n) * 100.0
    mismatch_pct = (mismatch_bp_count / n) * 100.0
    return round(81.5 + 0.41 * gc_pct - (675.0 / n) - mismatch_pct, 1)


def recipe_site_directed_mutagenesis(
    template_seq_or_file: str | pathlib.Path | SeqRecord,
    start_0based: int,
    end_0based: int,
    alt_seq: str,
    target_flank_bp: int = 15,
) -> dict[str, Any]:
    """Execute the gold-standard SOP for Site-Directed Mutagenesis (SDM).

    Follows Zheng et al. 2004 (NAR) and Sambrook *Molecular Cloning* 4th ed.:
    - Accurately introduces point, insertion, or deletion mutations into the template.
    - Symmetrically extends flanking wild-type sequences to design central-mutated QuikChange primers.
    - Evaluates QuikChange-specific Tm targeting >= 78°C and checks 3' GC clamp.
    - Enforces mandatory post-PCR DpnI digestion reminder.
    - Emits full provenance and authoritative literature citations.
    """
    rec = _load_record(template_seq_or_file)
    t_seq = str(rec.seq).upper()
    alt = str(alt_seq).strip().upper()
    ref_len = end_0based - start_0based

    # 1. Tier 1 atomic tool / sequence operation: apply mutation to sequence
    mutated_product = t_seq[:start_0based] + alt + t_seq[end_0based:]
    from core.models.construct_model import ConstructModel, feature_to_dict
    model = ConstructModel(rec)
    if ref_len == len(alt):
        model.mutate([(start_0based + i, base) for i, base in enumerate(alt)])
    elif ref_len == 0:
        model.insert(start_0based, alt)
    elif alt:
        model.replace(start_0based, end_0based, alt)
    else:
        model.delete(start_0based, end_0based)

    # 2. Design standard QuikChange primers centered around the mutation
    flank = max(10, min(25, target_flank_bp))
    left_start = max(0, start_0based - flank)
    right_end = min(len(t_seq), end_0based + flank)

    left_flank_seq = t_seq[left_start:start_0based]
    right_flank_seq = t_seq[end_0based:right_end]

    fwd_primer = left_flank_seq + alt + right_flank_seq
    rev_primer = str(Seq(fwd_primer).reverse_complement())

    # Calculate mismatch base count for QuikChange formula
    mismatch_count = max(ref_len, len(alt))
    qc_tm = calc_quikchange_tm(fwd_primer, mismatch_count)
    santalucia_tm = calc_primer_tm(fwd_primer)["tm"]

    # 3. Quality checks
    has_gc_clamp = fwd_primer[-1] in ("G", "C") or (len(fwd_primer) >= 2 and fwd_primer[-2] in ("G", "C"))
    quality_checks = {
        "primer_length_nt": len(fwd_primer),
        "quikchange_tm": qc_tm,
        "quikchange_tm_meets_78C_standard": qc_tm >= 78.0,
        "santalucia_tm": santalucia_tm,
        "left_flank_length_bp": len(left_flank_seq),
        "right_flank_length_bp": len(right_flank_seq),
        "mutation_centered": abs(len(left_flank_seq) - len(right_flank_seq)) <= 3,
        "gc_clamp_present": has_gc_clamp,
    }

    warnings = []
    if qc_tm < 78.0:
        warnings.append(
            f"QuikChange Tm ({qc_tm}°C) is below recommended 78°C threshold (Zheng et al. 2004). Consider increasing flanking length."
        )
    if not has_gc_clamp:
        warnings.append("Primer 3' end lacks G/C clamp; consider shifting flanking boundary by 1-2 bp.")

    sop_reminders = [
        "DPNI_DIGESTION: Treat 50 uL PCR product with 1 uL DpnI (37°C for 60 min) to destroy Dam-methylated plasmid template.",
        "THERMOCYCLING: Standard QuikChange cycling uses 16-18 cycles (95°C 30s, 55°C 1min, 68°C 1min/kb plasmid length).",
    ]

    primers_list = [
        {"name": "forward_mutagenic_primer", "seq": fwd_primer, "qc_tm": qc_tm, "santalucia_tm": santalucia_tm},
        {"name": "reverse_mutagenic_primer", "seq": rev_primer, "qc_tm": qc_tm, "santalucia_tm": santalucia_tm},
    ]

    protocol_steps = [
        {"step": 1, "action": "Set up mutagenic PCR reaction with high-fidelity DNA polymerase (PfuUltra / Q5)."},
        {"step": 2, "action": "Thermal cycling: 95°C 30s, followed by 16-18 cycles of (95°C 30s, 55°C 1min, 68°C 1min/kb plasmid length)."},
        {"step": 3, "action": "Digest reaction with 1 uL DpnI at 37°C for 60 min to eliminate parent plasmid template."},
        {"step": 4, "action": "Transform 2-5 uL into competent XL1-Blue / DH5alpha cells."},
    ]

    return RecipeResult(
        recipe_name="recipe_site_directed_mutagenesis",
        result_kind="construct",
        completeness="complete_construct",
        product_sequence=mutated_product,
        product_topology="circular",
        features=[feature_to_dict(f, len(mutated_product)) for f in model.to_record().features],
        primers=primers_list,
        quality_checks=quality_checks,
        warnings=warnings,
        protocol_steps=protocol_steps,
        citations=AUTHORITATIVE_SOURCES,
        details={
            "recipe": "recipe_site_directed_mutagenesis",
            "mutated_sequence": mutated_product,
            "product_length": len(mutated_product),
            "mutation_type": "substitution" if (ref_len == len(alt) and ref_len > 0) else ("insertion" if ref_len == 0 else "deletion"),
            "primers": {
                "forward_mutagenic_primer": fwd_primer,
                "reverse_mutagenic_primer": rev_primer,
                "primer_length": len(fwd_primer),
                "quikchange_tm": qc_tm,
                "santalucia_tm": santalucia_tm,
            },
            "quality_checks": quality_checks,
            "warnings": warnings,
            "sop_reminders": sop_reminders,
            "authoritative_sources": AUTHORITATIVE_SOURCES,
        },
    )
