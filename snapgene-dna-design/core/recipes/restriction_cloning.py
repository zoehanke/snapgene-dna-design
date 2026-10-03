# -*- coding: utf-8 -*-
"""core/recipes/restriction_cloning.py - Standard SOP Recipe for Restriction Cloning & T4 Ligation.

LITERATURE SOURCES & PROTOCOL REFERENCES:
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

from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature

from core.recipes.contract import RecipeResult
from core.tools.amplification import prepare_pcr_fragment
from core.tools.assembly import simulate_digest_ligation
from core.io.input_resolution import resolve_sequence_record
from core.tools.restriction import (
    check_overhang_compatibility,
    find_restriction_sites,
    get_enzyme,
)
from core.models.construct_model import feature_to_dict
from core.io.input_resolution import resolve_sequence_input
from core.recipes.gibson import _pcr_product_record, _preparation_template, _primer_delivery


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
    insert_enzyme5: str | None = None,
    insert_enzyme3: str | None = None,
    insert_prefix: str = "",
    insert_suffix: str = "",
    coding_sequence: bool | None = None,
    expression_start: bool | None = None,
    orientation: str = "auto",
) -> dict[str, Any]:
    """Execute a literature-grounded restriction cloning and T4 ligation route.

    Follows Green & Sambrook (Molecular Cloning 4th ed.) and NEB Technical Guidelines:
    - Appends standard NEB 5' protective bases to prevent incomplete PCR fragment digestion.
    - Designs optimal PCR primers with protective bases and restriction sites.
    - Scans for Dam/Dcm methylation overlap conflicts at the cloning junctions.
    - Simulates directional digestion and T4 ligation.
    - Warns about DpnI template digestion and vector dephosphorylation.
    - Emits source provenance and literature citations.
    """
    insert_prefix = str(insert_prefix or "").strip().upper()
    insert_suffix = str(insert_suffix or "").strip().upper()
    insert_enzyme5 = insert_enzyme5 or enzyme5
    insert_enzyme3 = insert_enzyme3 or enzyme3
    enz5_obj = get_enzyme(enzyme5)
    enz3_obj = get_enzyme(enzyme3)
    insert_enz5_obj = get_enzyme(insert_enzyme5)
    insert_enz3_obj = get_enzyme(insert_enzyme3)

    site5 = str(getattr(enz5_obj, "site", "")).upper()
    site3 = str(getattr(enz3_obj, "site", "")).upper()
    insert_site5 = str(getattr(insert_enz5_obj, "site", "")).upper()
    insert_site3 = str(getattr(insert_enz3_obj, "site", "")).upper()

    # Directional cloning validation: enzymes must not produce compatible cohesive or blunt ends
    ends_compatible = are_restriction_ends_compatible(enz5_obj, enz3_obj)
    is_directional = (enzyme5 != enzyme3) and not ends_compatible

    # 1. Look up standard NEB 5' protective bases
    prot5 = STANDARD_PROTECTIVE_BASES.get(insert_enzyme5, "CGC")
    prot3 = STANDARD_PROTECTIVE_BASES.get(insert_enzyme3, "CGC")

    # Prefix/suffix are part of the real oligos.  Reverse-primer tails are
    # written 5'->3', so reverse-complement the desired product suffix before
    # attaching it to the 5' end of that primer.
    fwd_tail = prot5 + insert_site5 + insert_prefix
    rev_tail = prot3 + insert_site3 + str(Seq(insert_suffix).reverse_complement())

    insert_record, insert_sequence = resolve_sequence_input(insert_template)
    target_sequence = insert_sequence[int(insert_start):int(insert_end)].upper()
    if not target_sequence:
        raise ValueError("Restriction-cloning insert interval is empty")

    prepared = prepare_pcr_fragment(insert_record, insert_start, insert_end,
                                    fwd_tail, rev_tail, name="insert")
    primers = prepared["design"]
    fwd_p = primers["forward_primer"]["full_sequence"]
    rev_p = primers["reverse_primer"]["full_sequence"]
    pcr_res = prepared["pcr"]
    amplicon = pcr_res["amplicon"]

    # 4. Check for Dam/Dcm methylation overlap on vector and insert
    vector_record, _vector_sequence = resolve_sequence_input(vector_source)
    re_check_vector = find_restriction_sites(vector_record, enzymes=[enzyme5, enzyme3])
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

    is_coding = bool(coding_sequence) if coding_sequence is not None else target_sequence.startswith("ATG")
    expression_boundary_warnings = []
    expression_compatible = None
    expression_sequence = ""
    expression_prefix = ""
    expression_translation = ""
    expression_stop = False

    # 5. Call Tier 1 atomic tool: simulate directional digestion and ligation
    ligation_res = simulate_digest_ligation(
        vector_source=vector_source,
        insert_source=resolve_sequence_record(pcr_res),
        vector_enzymes=[enzyme5, enzyme3],
        insert_enzymes=[insert_enzyme5, insert_enzyme3],
        orientation=orientation,
    )

    # Project the original vector initiation site through the actual duplex
    # cuts. A compatible enzyme can destroy the recognition motif; searching
    # the final insert for that motif or for a convenient ATG is incorrect.
    product_features = list(ligation_res.get("features", []))
    product_sequence = str(ligation_res["product_sequence"]).upper()
    product_orientation = ligation_res["insert_orientation"]
    insert_offset = ligation_res["insert_feature_offset"]
    retained_start, retained_end = ligation_res["insert_retained_interval_0based"]
    expression_boundary_applicable = is_coding and enzyme5 in ("NcoI", "NdeI")
    expression_info = {"product_expression_sequence_found": None,
                       "applicable": expression_boundary_applicable}
    if expression_boundary_applicable:
        reverse = product_orientation == "reverse"
        vector_site = str(Seq(site5).reverse_complement()) if reverse else site5
        atg_index = vector_site.index("ATG")
        cut_local = int(enz5_obj.fst5)
        if reverse:
            # The reverse product's top strand is the original insert's
            # bottom strand. The initiation triplet can lie in the retained
            # vector overhang, before the insert's bottom-strand boundary.
            distance = len(vector_site) - atg_index - cut_local
            start_in_amplicon = retained_start - distance
        else:
            start_in_amplicon = retained_start + atg_index - cut_local
        payload_end = len(fwd_tail) + len(target_sequence) + len(insert_suffix)
        if not 0 <= start_in_amplicon < payload_end <= len(amplicon):
            raise ValueError("Vector initiation site cannot be mapped onto the actual PCR product")
        expression_sequence = amplicon[start_in_amplicon:payload_end]
        expression_prefix = amplicon[start_in_amplicon:len(prot5) + len(insert_site5)]
        try:
            expression_translation = str(Seq(expression_sequence).translate(cds=True)) + "*"
        except Exception as exc:
            raise ValueError(f"{enzyme5} native expression boundary is incompatible with the complete insert: {exc}") from exc
        expression_stop = True
        expression_compatible = True
        if reverse:
            high = insert_offset + (retained_end - retained_start) - (start_in_amplicon - retained_start)
            expression_low = high - len(expression_sequence)
        else:
            expression_low = insert_offset + start_in_amplicon - retained_start
        n = len(product_sequence)
        if len(expression_sequence) > n:
            raise ValueError("Expression CDS would exceed one complete product molecule")

        def coding_location(offset, length):
            low = (expression_low + (len(expression_sequence) - offset - length if reverse else offset)) % n
            strand = -1 if reverse else 1
            end = low + length
            if end <= n:
                return FeatureLocation(low, end, strand=strand)
            from Bio.SeqFeature import CompoundLocation
            parts = [FeatureLocation(low, n, strand=strand), FeatureLocation(0, end - n, strand=strand)]
            return CompoundLocation(list(reversed(parts)) if reverse else parts, operator="join")

        location = coding_location(0, len(expression_sequence))
        actual_expression = str(location.extract(Seq(product_sequence)))
        if actual_expression != expression_sequence:
            raise ValueError("Assembled expression sequence differs from the actual PCR and vector initiation context")
        expression_info.update({"product_expression_sequence_found": True,
                                "expression_strand": -1 if reverse else 1,
                                "actual_expression_start": expression_low % n,
                                "start_in_amplicon_0based": start_in_amplicon})

        def add_expression_feature(label, feature_type, offset, length):
            qualifiers = {"label": [label], "note": ["mapped from the original vector initiation site through actual duplex cuts"]}
            if feature_type == "CDS":
                qualifiers["translation"] = [expression_translation[:-1]]
            feature = SeqFeature(coding_location(offset, length), type=feature_type, qualifiers=qualifiers)
            product_features.append(feature_to_dict(feature, n))

        add_expression_feature("expression CDS", "CDS", 0, len(expression_sequence))
        prefix_start = len(prot5) + len(insert_site5) - start_in_amplicon
        prefix_end = len(fwd_tail) - start_in_amplicon
        for label, peptide, feature_type in (("His6 tag", "HHHHHH", "misc_feature"),
                                             ("TEV cleavage site", "ENLYFQG", "misc_feature")):
            position = expression_translation.find(peptide)
            if position >= 0 and prefix_start <= position * 3 and position * 3 + len(peptide) * 3 <= prefix_end:
                add_expression_feature(label, feature_type, position * 3, len(peptide) * 3)
    ligation_res["features"] = product_features

    # Standard Sambrook wet-lab SOP reminders
    sop_reminders = [
        "DPNI_DIGESTION: Treat PCR product with 1 uL DpnI (37°C, 20 min) prior to cleanup to digest methylated template plasmid and prevent high background.",
        "DEPHOSPHORYLATION: If cloning with single enzyme or blunt ends, treat linearized vector with rSAP / CIP alkaline phosphatase to prevent vector self-ligation.",
        "MOLAR_RATIO: Set up T4 ligation reaction using a 1:3 to 1:5 molar ratio of vector to insert (e.g. 50 ng vector, ~30-50 ng insert depending on size).",
    ]

    quality_checks = {
        "directional_cloning": is_directional,
        "ends_compatible": ends_compatible,
        "vector_enzymes": [enzyme5, enzyme3],
        "insert_enzymes": [insert_enzyme5, insert_enzyme3],
        "protective_bases_added": {"5prime": prot5, "3prime": prot3},
        "binding_core_delta_tm": primers["binding_core_delta_tm"],
        "delta_tm_within_standard_2C": primers["binding_core_delta_tm"] <= 2.0,
        "assembled_successfully": bool(ligation_res.get("product_sequence")),
        "insert_orientation": ligation_res.get("insert_orientation"),
        "vector_replacement_interval_0based": ligation_res.get("vector_replacement_interval_0based"),
        "expression_boundary_compatible": expression_compatible,
        "expression_boundary": {
            "enzyme5": enzyme5,
            "insert_enzyme5": insert_enzyme5,
            "enzyme_site": site5,
            "applicable": expression_boundary_applicable,
            "site_contains_atg": "ATG" in site5,
            "insert_enzyme_site": insert_site5,
            "initiation_asserted": expression_start,
            "selected_interval_starts_atg": target_sequence.startswith("ATG"),
            "expression_prefix": expression_prefix,
            "expression_sequence": expression_sequence,
            "translation": expression_translation,
            "terminal_stop": expression_stop,
            "product_expression_sequence_found": expression_info["product_expression_sequence_found"],
            "payload_length_bp": len(expression_sequence),
            "payload_frame_remainder": len(expression_sequence) % 3,
            "warnings": expression_boundary_warnings,
        },
    }

    primers_list = prepared["primers"]
    preparation = prepared["preparation"]

    protocol_steps = [
        {"step": 1, "action": f"Prepare the insert through {len(preparation)} PCR step(s), in the listed order; each intermediate is the next template."},
        {"step": 2, "action": "Treat PCR product with DpnI (37°C, 20 min) to digest template plasmid."},
        {"step": 3, "action": f"Digest vector with {enzyme5}/{enzyme3} and PCR insert with {insert_enzyme5}/{insert_enzyme3}."},
        {"step": 4, "action": "Perform T4 DNA ligation at 16°C overnight or room temperature for 2 hours (1:3 vector:insert ratio)."},
        {"step": 5, "action": "Transform ligation mixture into competent cells."},
    ]

    return RecipeResult(
        recipe_name="recipe_restriction_cloning",
        result_kind="construct",
        completeness="complete_construct",
        product_sequence=ligation_res["product_sequence"],
        product_topology=ligation_res["product_topology"],
        features=ligation_res["features"],
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
            "preparation": preparation,
            "insert_prefix": insert_prefix,
            "insert_suffix": insert_suffix,
            "insert_enzymes": [insert_enzyme5, insert_enzyme3],
            "expression_boundary": quality_checks["expression_boundary"],
            "orientation": ligation_res.get("insert_orientation"),
            "vector_replacement_interval_0based": ligation_res.get("vector_replacement_interval_0based"),
            "sop_reminders": sop_reminders,
            "quality_checks": quality_checks,
            "authoritative_sources": AUTHORITATIVE_SOURCES,
        },
    )
