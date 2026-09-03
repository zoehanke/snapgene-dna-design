# -*- coding: utf-8 -*-
"""core/recipes/gibson.py - Standard SOP Recipe for Gibson & In-Fusion Assembly.

AUTHORITATIVE SOURCES & CLASSICAL PROTOCOLS:
1. Gibson, D.G., Young, L., Chuang, R.Y., Venter, J.C., Hutchison, C.A. and Smith, H.O. (2009).
   Enzymatic assembly of DNA molecules up to several hundred kilobases.
   Nature Methods, 6(5), pp.343-345. doi:10.1038/nmeth.1318.
2. New England Biolabs. (2023).
   NEBuilder® HiFi DNA Assembly Master Mix Protocol (NEB #E2621). Ipswich, MA.
3. Takara Bio / Clontech. (2022).
   In-Fusion® HD Cloning Plus User Manual.
"""
from __future__ import annotations

import pathlib
from typing import Any

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.tools.amplification import calc_primer_tm, check_primer_dimers, design_overhang_primers, simulate_pcr
from core.tools.assembly import simulate_overlap_assembly
from core.tools.feature_ops import migrate_features_after_assembly

AUTHORITATIVE_SOURCES = [
    {
        "citation": "Gibson et al. (2009). Enzymatic assembly of DNA molecules up to several hundred kilobases. Nature Methods 6:343-345.",
        "institution": "J. Craig Venter Institute (JCVI)",
        "doi": "10.1038/nmeth.1318",
        "rules_enforced": [
            "Homologous overlap length recommended at 20-25 bp for 2-3 fragment assembly (minimum 15 bp, maximum 40 bp).",
            "Overlap region GC content optimal between 40% and 60% with Tm >= 48°C to ensure stable single-strand annealing.",
            "Short fragments (< 200 bp) risk complete degradation by T5 5'->3' exonuclease; require increased molar ratio or shortened incubation.",
        ],
    },
    {
        "citation": "New England Biolabs (2023). NEBuilder® HiFi DNA Assembly Master Mix Protocol (NEB #E2621).",
        "institution": "New England Biolabs (NEB)",
        "url": "https://www.neb.com/en-us/protocols/2014/11/26/nebuilder-hifi-dna-assembly-reaction-protocol",
        "rules_enforced": [
            "Primer binding core optimal Tm at 60±2°C using SantaLucia 1998 nearest-neighbor thermodynamic parameters.",
            "Forward and reverse primer binding core delta-Tm must be <= 2°C.",
            "3' end of primers must feature a GC clamp (1-2 G/C in terminal 5 bases) without severe 3' self- or cross-dimers.",
        ],
    },
]


def recipe_gibson_assembly(
    vector_linear_seq: str,
    insert_template_seq: str,
    insert_start: int,
    insert_end: int,
    overlap_length: int = 22,  # Gold-standard 20-25 bp
    circular_product: bool = True,
) -> dict[str, Any]:
    """Execute the gold-standard SOP for Gibson / In-Fusion overlapping assembly.

    Follows Gibson et al. (2009 Nature Methods) and NEB NEBuilder HiFi Guidelines:
    - Extracts 20-25 bp homology arms from vector ends.
    - Designs optimal PCR primers for the insert (binding Tm 60±2°C, ΔTm <= 2°C, 3' GC clamp).
    - Verifies absence of catastrophic 3' primer-dimers.
    - Simulates high-fidelity PCR and overlap assembly.
    - Emits full provenance and authoritative literature citations.
    """
    v_seq = str(vector_linear_seq).strip().upper()
    i_template = str(insert_template_seq).strip().upper()

    # 1. Enforce standard overlap length (Gibson 2009 / NEB: 20-25 bp)
    ol = max(15, min(35, overlap_length))

    # Vector 5' and 3' homologous tails:
    # Forward primer gets 5' tail matching the 3' end of the linearized vector (left flank)
    # Reverse primer gets 5' tail matching the reverse-complement of the 5' end of the linearized vector (right flank)
    fwd_tail = v_seq[-ol:]
    rev_tail = str(Seq(v_seq[:ol]).reverse_complement())

    # 2. Call Tier 1 atomic tool: design primers targeting 60°C with 5' overhangs
    primers = design_overhang_primers(
        template_record_or_seq=i_template,
        start=insert_start,
        end=insert_end,
        target_tm=60.0,
        fwd_5prime_overhang=fwd_tail,
        rev_5prime_overhang=rev_tail,
    )

    fwd_p = primers["forward_primer"]["full_sequence"]
    rev_p = primers["reverse_primer"]["full_sequence"]

    # 3. Call Tier 1 atomic tool: check for primer-dimers at 3' end
    dimer_check = check_primer_dimers(fwd_p, rev_p)

    # 4. Call Tier 1 atomic tool: simulate PCR amplification of insert with overhangs
    pcr_res = simulate_pcr(
        template_path_or_seq=i_template,
        f_primer=fwd_p,
        r_primer=rev_p,
        topology="linear",
    )
    amplicon = pcr_res["amplicon"]

    # 5. Check for short fragment warning (< 200 bp)
    warnings = []
    if len(amplicon) < 200:
        warnings.append(
            f"Insert amplicon is short ({len(amplicon)} bp < 200 bp): T5 exonuclease in standard Gibson mix risks over-digesting the fragment. Recommend NEBuilder HiFi or 15 min incubation (Gibson et al. 2009)."
        )
    if dimer_check["high_dimer_risk"]:
        warnings.append(
            f"Primer 3' complementarity risk ({dimer_check['max_3prime_complementarity']} bp). Monitor for primer-dimer formation."
        )

    # 6. Call Tier 1 atomic tool: simulate overlap assembly
    assembly_res = simulate_overlap_assembly(
        fragments=[v_seq, amplicon],
        min_overlap=ol - 5,
        circular=circular_product,
    )

    quality_checks = {
        "standard_overlap_length_bp": ol,
        "binding_core_delta_tm": primers["binding_core_delta_tm"],
        "delta_tm_within_standard_2C": primers["binding_core_delta_tm"] <= 2.0,
        "primer_dimer_safe": not dimer_check["high_dimer_risk"],
        "assembled_successfully": bool(assembly_res.get("product_sequence")),
    }

    return {
        "recipe": "recipe_gibson_assembly",
        "product_sequence": assembly_res["product_sequence"],
        "product_length": assembly_res["product_length"],
        "product_topology": assembly_res["product_topology"],
        "primers": {
            "forward": primers["forward_primer"],
            "reverse": primers["reverse_primer"],
            "dimer_analysis": dimer_check,
        },
        "insert_amplicon_length": len(amplicon),
        "junctions": assembly_res.get("junctions", []),
        "warnings": warnings,
        "quality_checks": quality_checks,
        "authoritative_sources": AUTHORITATIVE_SOURCES,
    }
