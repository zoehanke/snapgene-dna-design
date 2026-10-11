# -*- coding: utf-8 -*-
"""core/recipes/crispr_hdr.py - Standard SOP Recipe for CRISPR/Cas9 sgRNA & HDR Donor Design.

LITERATURE SOURCES & PROTOCOL REFERENCES:
1. Ran, F.A., Hsu, P.D., Wright, J., Agarwala, V., Scott, D.A. and Zhang, F. (2013).
   Genome engineering using the CRISPR-Cas9 system. Nature Protocols, 8(11), pp.2281-2308.
   doi:10.1038/nprot.2013.143 (Zhang Lab, MIT/Broad Institute).
2. Paquet, D., Kwart, D., Chen, A. et al. (2016).
   Efficient introduction of specific homozygous and heterozygous mutations using CRISPR/Cas9.
   Nature, 533(7601), pp.125-129. doi:10.1038/nature17664.
3. Addgene CRISPR Guide & Vectors (pX330, pX458, pX459, lentiCRISPRv2 Protocols).
"""
from __future__ import annotations
from core.models.construct_model import feature_to_dict

import pathlib
from typing import Any
from Bio.SeqRecord import SeqRecord

from core.recipes.contract import RecipeResult
from core.tools.crispr import design_hdr_donor

AUTHORITATIVE_SOURCES = [
    {
        "citation": "Ran et al. (2013). Genome engineering using the CRISPR-Cas9 system. Nature Protocols 8:2281-2308.",
        "institution": "Broad Institute / MIT (Feng Zhang Lab)",
        "doi": "10.1038/nprot.2013.143",
        "rules_enforced": [
            "Human U6 pol III promoter requires a 5' Guanine (G) for high-efficiency transcription initiation.",
            "Standard BbsI vector cloning oligos formatted with 5' CACC (top) and 5' AAAC (bottom).",
            "Single-stranded oligonucleotide (ssODN) donor homology arms optimal at 40-60 nt each side for small edits.",
            "Double-stranded plasmid donor homology arms standard at 500-800 bp each side for large payloads.",
        ],
    },
    {
        "citation": "Paquet et al. (2016). Efficient introduction of specific homozygous and heterozygous mutations using CRISPR/Cas9. Nature 533:125-129.",
        "institution": "Rockefeller University / UCSF",
        "doi": "10.1038/nature17664",
        "rules_enforced": [
            "Introduction of silent mutations in the PAM (NGG -> NGH) or proximal seed region to prevent Cas9 re-cleavage of the repaired allele in vivo.",
            "HDR efficiency drops exponentially with distance from Cas9 double-strand break (optimal within <= 5-10 bp).",
        ],
    },
]


def recipe_crispr_hdr_donor(
    target_seq_or_file: str | pathlib.Path | SeqRecord,
    cut_position_0based: int,
    edit_dna: str,
    donor_type: str = "ssODN",
    grna_seq: str = "",
    grna_strand: int = 1,
    custom_arm_length: int | None = None,
    target_is_cds: bool = False,
    cds_frame_offset: int = 0,
    edit_start_0based: int | None = None,
    edit_end_0based: int | None = None,
    require_pam_disruption: bool = False,
) -> dict[str, Any]:
    """Run the HDR SOP around the shared atomic donor calculation."""
    requested = str(donor_type).strip().lower()
    is_short_ds = requested in {"dsdna", "double-stranded dna", "double-stranded donor"}
    if custom_arm_length is not None:
        arm_len = int(custom_arm_length)
    elif requested == "ssodn":
        arm_len = 50
    elif is_short_ds:
        # Short dsDNA uses the caller's explicit arm length. The default keeps
        # the historical compact donor useful without applying plasmid rules.
        arm_len = 50
    else:
        arm_len = 600

    atomic = design_hdr_donor(
        target_seq_or_file=target_seq_or_file,
        cut_position_0based=cut_position_0based,
        edit_dna=edit_dna,
        left_arm_length=arm_len,
        right_arm_length=arm_len,
        grna_seq=grna_seq,
        grna_strand=grna_strand,
        edit_start_0based=edit_start_0based,
        edit_end_0based=edit_end_0based,
        donor_type=donor_type,
        target_is_cds=target_is_cds,
        cds_frame_offset=cds_frame_offset,
        require_pam_disruption=require_pam_disruption,
    )

    resolved_type = atomic.analysis['donor_type']
    if resolved_type == "ssODN":
        standard_arm_ok = 35 <= arm_len <= 65
    elif resolved_type == "dsDNA" and atomic.analysis['total_length'] <= 200:
        standard_arm_ok = True
    else:
        standard_arm_ok = 450 <= arm_len <= 850

    guide = atomic.analysis.get("guide") or {}
    pam_recleavage_prevented = bool(atomic.analysis.get("pam_silenced_in_donor")) if grna_seq else None
    quality_checks = {
        "standard_arm_length_conforming": standard_arm_ok,
        "pam_recleavage_prevented": pam_recleavage_prevented,
        "edit_distance_from_dsb_bp": (
            0
            if atomic.analysis.get("donor_edit_interval_0based")
            and atomic.analysis['donor_edit_interval_0based'][0]
            <= atomic.analysis['donor_cut_position_0based']
            <= atomic.analysis['donor_edit_interval_0based'][1]
            else min(
                abs(atomic.analysis['donor_cut_position_0based'] - bound)
                for bound in atomic.analysis.get("donor_edit_interval_0based", [atomic.analysis["donor_cut_position_0based"]])
            )
        ),
        "ssodn_total_length_under_200nt": (
            atomic.analysis['total_length'] <= 200 if resolved_type == "ssODN" else True
        ),
        "missense_mutation_avoided": not any(
            mutation.get("synonymous") is False
            for mutation in atomic.analysis.get("mutations_applied", [])
            if target_is_cds
        ),
        "guide_matches_original_target": bool(guide) if grna_seq else None,
        "replacement_length_preserved": (
            atomic.analysis['edit_mode'] != "replace"
            or (
                atomic.analysis['replacement_length'] == atomic.analysis['edit_length']
                and len(atomic.analysis['edited_target_sequence'])
                == len(atomic.analysis['original_target_sequence'])
            )
        ),
    }

    if resolved_type == "dsDNA" and atomic.analysis['total_length'] <= 200:
        protocol_steps = [
            {"step": 1, "action": "Order the complete top and bottom dsDNA donor oligos shown in the result."},
            {"step": 2, "action": "Mix equimolar oligos, heat-denature, and cool slowly to anneal the full donor duplex."},
            {"step": 3, "action": "Combine the annealed dsDNA donor with the validated Cas9 guide reaction."},
            {"step": 4, "action": "Recover edited cells and verify the intended replacement and PAM state by amplicon sequencing."},
        ]
    elif resolved_type == "ssODN":
        protocol_steps = [
            {"step": 1, "action": "Order the complete designed ssODN donor oligo."},
            {"step": 2, "action": "Prepare the Cas9-sgRNA ribonucleoprotein or co-transfection system."},
            {"step": 3, "action": "Deliver the validated RNP and ssODN donor to the target cells."},
            {"step": 4, "action": "Verify the intended edit and PAM state by genomic PCR and sequencing."},
        ]
    else:
        protocol_steps = [
            {"step": 1, "action": "Build or obtain the dsDNA donor with the reported homology arms."},
            {"step": 2, "action": "Prepare the Cas9-sgRNA ribonucleoprotein or co-transfection system."},
            {"step": 3, "action": "Deliver the donor and Cas9 guide system to the target cells."},
            {"step": 4, "action": "Verify the intended edit and PAM state by genomic PCR and sequencing."},
        ]

    details = dict(atomic.analysis)
    details.update({
        "recipe": "recipe_crispr_hdr_donor",
        "pam_silenced": atomic.analysis.get("pam_silenced_in_donor", False),
        "pam_silencing_details": atomic.analysis.get("silencing_details", ""),
        "quality_checks": quality_checks,
        "authoritative_sources": AUTHORITATIVE_SOURCES,
        "target_is_cds": target_is_cds,
        "cds_frame_offset": cds_frame_offset,
    })
    return RecipeResult(
        recipe_name="recipe_crispr_hdr_donor",
        result_kind="component",
        completeness="component_only",

        products=atomic.products,

        primers=[],
        quality_checks=quality_checks,
        warnings=atomic.analysis.get("warnings", []),
        protocol_steps=protocol_steps,
        citations=AUTHORITATIVE_SOURCES,
        details=details,
    )
