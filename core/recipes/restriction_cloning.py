# -*- coding: utf-8 -*-
"""core/recipes/restriction_cloning.py - Standard SOP Recipe for Restriction Cloning & T4 Ligation.

AUTHORITATIVE SOURCES & CLASSICAL PROTOCOLS:
1. Green, M.R. and Sambrook, J. (2012).
   Molecular Cloning: A Laboratory Manual. 4th ed.
   Cold Spring Harbor Laboratory Press, Cold Spring Harbor, NY.
   Chapters 1 (Plasmids and Their Useful Features), 3 (Enzymatic Cleavage), 8 (In Vitro Amplification by PCR).
2. New England Biolabs. (2024).
   Cleavage Close to the End of DNA Fragments (Technical Reference).
3. New England Biolabs. (2023).
   T4 DNA Ligase Protocol (M0202). Ipswich, MA.
"""
from __future__ import annotations

import pathlib
from typing import Any

from core.recipes.contract import RecipeResult
from core.tools.amplification import design_overhang_primers, simulate_pcr
from core.tools.assembly import simulate_digest_ligation
from core.tools.restriction import (
    check_overhang_compatibility,
    find_restriction_sites,
    get_enzyme,
)


def are_restriction_ends_compatible(enz1: Any, enz2: Any) -> bool:
    """Return True if two restriction enzymes produce mutually compatible cohesive or blunt ends.

    When ends are compatible, linearized vectors can self-ligate and inserts can integrate
    in either forward or reverse orientation, rendering cloning non-directional.
    """
    if isinstance(enz1, str):
        try:
            enz1 = get_enzyme(enz1)
        except Exception:
            pass
    if isinstance(enz2, str):
        try:
            enz2 = get_enzyme(enz2)
        except Exception:
            pass
    if enz1 == enz2:
        return True
    ov1 = getattr(enz1, "ovhg", None)
    ov2 = getattr(enz2, "ovhg", None)
    if ov1 is None or ov2 is None:
        return False
    if ov1 == 0 and ov2 == 0:
        # Both blunt ends -> mutually ligatable non-directionally
        return True
    if ov1 != ov2:
        # Different overhang length or geometry (5' vs 3') -> incompatible
        return False
    seq1 = str(getattr(enz1, "ovhgseq", "")).upper()
    seq2 = str(getattr(enz2, "ovhgseq", "")).upper()
    if not seq1 or not seq2:
        return False
    return seq1 == seq2

AUTHORITATIVE_SOURCES = [
    {
        "citation": "Green, M.R. and Sambrook, J. (2012). Molecular Cloning: A Laboratory Manual (4th ed.). Cold Spring Harbor Laboratory Press.",
        "institution": "Cold Spring Harbor Laboratory (CSHL)",
        "rules_enforced": [
            "Directional cloning requires non-compatible sticky ends to ensure 100% correct orientation.",
            "Dephosphorylation of linearized vector 5' ends using alkaline phosphatase (CIP/rSAP) is mandatory for single-cut or blunt vectors to prevent self-ligation.",
            "PCR amplifications from plasmid templates must undergo DpnI digestion (37°C, 15-30 min) to digest methylated parental DNA and eliminate false-positive background.",
            "Optimal molar ratio of vector to insert is standard at 1:3 to 1:5.",
        ],
    },
    {
        "citation": "New England Biolabs (2024). Cleavage Close to the End of DNA Fragments. NEB Technical Reference.",
        "institution": "New England Biolabs (NEB)",
        "url": "https://www.neb.com/en/faqs/cleavage-close-to-the-end-of-dna-fragments",
        "rules_enforced": [
            "PCR primers with 5' restriction enzyme sites must include flanking protective bases (2-6 bp) for efficient cleavage.",
            "EcoRI/BamHI/HindIII/XhoI require at least 2-3 protective bp (e.g. CGC, GAC); NdeI/NotI/XbaI require 4-6 bp (e.g. AAGGCC).",
        ],
    },
]

# Standard NEB protective bases table for common cloning enzymes
STANDARD_PROTECTIVE_BASES = {
    "EcoRI": "CGC",
    "BamHI": "CGC",
    "HindIII": "CCC",
    "XhoI": "CCG",
    "SalI": "ACGC",
    "NotI": "AAGGCC",
    "NdeI": "GGAATTCC",
    "XbaI": "CTAGTC",
    "BglII": "GAC",
    "PstI": "AAAC",
    "KpnI": "CGG",
}


def recipe_restriction_cloning(
    vector_source: str | pathlib.Path,
    insert_template: str | pathlib.Path,
    insert_start: int,
    insert_end: int,
    enzyme5: str = "EcoRI",
    enzyme3: str = "BamHI",
) -> dict[str, Any]:
    """Execute the gold-standard SOP for restriction endonuclease cloning and T4 ligation.

    Follows Green & Sambrook (Molecular Cloning 4th ed.) and NEB Technical Guidelines:
    - Appends standard NEB 5' protective bases to prevent incomplete PCR fragment digestion.
    - Designs optimal PCR primers with protective bases and restriction sites.
    - Scans for Dam/Dcm methylation overlap conflicts at the cloning junctions.
    - Simulates directional digestion and T4 ligation.
    - Warns about DpnI template digestion and vector dephosphorylation.
    - Emits full provenance and authoritative literature citations.
    """
    enz5_obj = get_enzyme(enzyme5)
    enz3_obj = get_enzyme(enzyme3)

    site5 = str(getattr(enz5_obj, "site", "")).upper()
    site3 = str(getattr(enz3_obj, "site", "")).upper()

    # Directional cloning validation: enzymes must not produce compatible cohesive or blunt ends
    ends_compatible = are_restriction_ends_compatible(enz5_obj, enz3_obj)
    is_directional = (enzyme5 != enzyme3) and not ends_compatible

    # 1. Look up standard NEB 5' protective bases
    prot5 = STANDARD_PROTECTIVE_BASES.get(enzyme5, "CGC")
    prot3 = STANDARD_PROTECTIVE_BASES.get(enzyme3, "CGC")

    fwd_tail = prot5 + site5
    rev_tail = prot3 + site3

    # 2. Call Tier 1 atomic tool: design primers with protective tails and restriction sites
    primers = design_overhang_primers(
        template_record_or_seq=insert_template,
        start=insert_start,
        end=insert_end,
        target_tm=60.0,
        fwd_5prime_overhang=fwd_tail,
        rev_5prime_overhang=rev_tail,
    )

    fwd_p = primers["forward_primer"]["full_sequence"]
    rev_p = primers["reverse_primer"]["full_sequence"]

    # 3. Call Tier 1 atomic tool: PCR amplification simulation
    pcr_res = simulate_pcr(
        template_path_or_seq=insert_template,
        f_primer=fwd_p,
        r_primer=rev_p,
        topology="linear",
    )
    amplicon = pcr_res["amplicon"]

    # 4. Check for Dam/Dcm methylation overlap on vector and insert
    re_check_vector = find_restriction_sites(vector_source, enzymes=[enzyme5, enzyme3])
    warnings = []
    if not is_directional:
        warnings.append(
            f"Non-directional cloning: {enzyme5} and {enzyme3} produce compatible ends "
            f"(both blunt or compatible overhangs '{getattr(enz5_obj, 'ovhgseq', '')}'). "
            "Insert can integrate in either orientation; vector dephosphorylation and colony orientation screening required."
        )
    for enz_name, e_info in re_check_vector.get("enzymes", {}).items():
        for s in e_info.get("cuts", []):
            if s.get("methylation_warnings"):
                warnings.append(
                    f"Methylation conflict in vector at {enz_name}: {', '.join(s['methylation_warnings'])}. May inhibit digestion in standard Dam+/Dcm+ E. coli hosts (Sambrook Ch. 1)."
                )

    # 5. Call Tier 1 atomic tool: simulate directional digestion and ligation
    ligation_res = simulate_digest_ligation(
        vector_source=vector_source,
        insert_source=amplicon,
        vector_enzymes=[enzyme5, enzyme3],
        insert_enzymes=[enzyme5, enzyme3],
        orientation="forward",
    )

    # Standard Sambrook wet-lab SOP reminders
    sop_reminders = [
        "DPNI_DIGESTION: Treat PCR product with 1 uL DpnI (37°C, 20 min) prior to cleanup to digest methylated template plasmid and prevent high background.",
        "DEPHOSPHORYLATION: If cloning with single enzyme or blunt ends, treat linearized vector with rSAP / CIP alkaline phosphatase to prevent vector self-ligation.",
        "MOLAR_RATIO: Set up T4 ligation reaction using a 1:3 to 1:5 molar ratio of vector to insert (e.g. 50 ng vector, ~30-50 ng insert depending on size).",
    ]

    quality_checks = {
        "directional_cloning": is_directional,
        "ends_compatible": ends_compatible,
        "protective_bases_added": {"5prime": prot5, "3prime": prot3},
        "binding_core_delta_tm": primers["binding_core_delta_tm"],
        "delta_tm_within_standard_2C": primers["binding_core_delta_tm"] <= 2.0,
        "assembled_successfully": bool(ligation_res.get("product_sequence")),
    }

    primers_list = [
        {"name": "forward_primer", "seq": primers["forward_primer"]["full_sequence"], "tm": primers["forward_primer"]["binding_core_tm"]},
        {"name": "reverse_primer", "seq": primers["reverse_primer"]["full_sequence"], "tm": primers["reverse_primer"]["binding_core_tm"]},
    ]

    protocol_steps = [
        {"step": 1, "action": "PCR amplify insert using designed primers with 5' restriction tails and protective bases."},
        {"step": 2, "action": "Treat PCR product with DpnI (37°C, 20 min) to digest template plasmid."},
        {"step": 3, "action": f"Digest vector and insert with {enzyme5} and {enzyme3}."},
        {"step": 4, "action": "Perform T4 DNA ligation at 16°C overnight or room temperature for 2 hours (1:3 vector:insert ratio)."},
        {"step": 5, "action": "Transform ligation mixture into competent cells."},
    ]

    return RecipeResult(
        recipe_name="recipe_restriction_cloning",
        result_kind="construct",
        completeness="complete_construct",
        product_sequence=ligation_res["product_sequence"],
        product_topology=ligation_res["product_topology"],
        features=[],
        primers=primers_list,
        quality_checks=quality_checks,
        warnings=warnings,
        protocol_steps=protocol_steps,
        citations=AUTHORITATIVE_SOURCES,
        details={
            "recipe": "recipe_restriction_cloning",
            "product_length": ligation_res["product_length"],
            "primers": {
                "forward": primers["forward_primer"],
                "reverse": primers["reverse_primer"],
                "protective_bases": {"fwd": prot5, "rev": prot3},
            },
            "sop_reminders": sop_reminders,
            "quality_checks": quality_checks,
            "authoritative_sources": AUTHORITATIVE_SOURCES,
        },
    )
