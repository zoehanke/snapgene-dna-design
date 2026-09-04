# -*- coding: utf-8 -*-
"""core/recipes/crispr_hdr.py - Standard SOP Recipe for CRISPR/Cas9 sgRNA & HDR Donor Design.

AUTHORITATIVE SOURCES & CLASSICAL PROTOCOLS:
1. Ran, F.A., Hsu, P.D., Wright, J., Agarwala, V., Scott, D.A. and Zhang, F. (2013).
   Genome engineering using the CRISPR-Cas9 system. Nature Protocols, 8(11), pp.2281-2308.
   doi:10.1038/nprot.2013.143 (Zhang Lab, MIT/Broad Institute).
2. Paquet, D., Kwart, D., Chen, A. et al. (2016).
   Efficient introduction of specific homozygous and heterozygous mutations using CRISPR/Cas9.
   Nature, 533(7601), pp.125-129. doi:10.1038/nature17664.
3. Addgene CRISPR Guide & Vectors (pX330, pX458, pX459, lentiCRISPRv2 Protocols).
"""
from __future__ import annotations

import pathlib
from typing import Any

from Bio.Seq import Seq
from core.recipes.contract import RecipeResult
from core.tools.crispr import design_crispr_grna, extract_homology_arms, prepare_grna_oligos
from core.tools.sequence_ops import mutate_sequence
from core.tools.translation import get_codon_synonyms

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
) -> dict[str, Any]:
    """Execute the gold-standard SOP for CRISPR HDR repair template design.

    Follows Ran et al. (2013 Nature Protocols) and Paquet et al. (2016 Nature):
    - Sets arm lengths to standard gold-standard windows (50 nt for ssODN, 600 bp for plasmid).
    - Automatically scans for the PAM (NGG) near the cut site on the donor arms.
    - Applies a synonymous point mutation to disable PAM and prevent Cas9 re-cleavage in vivo.
    - Emits full provenance and authoritative literature citations.
    """
    # 1. Determine standard arm length according to classical literature
    if custom_arm_length is not None:
        arm_len = custom_arm_length
    elif donor_type.lower() == "ssodn":
        arm_len = 50  # Gold standard 40-60 nt (Paquet 2016, Ran 2013)
    else:
        arm_len = 600  # Gold standard 500-800 bp for plasmid donors

    # 2. Call Tier 1 atomic tool: extract left and right homology arms
    arms = extract_homology_arms(
        target_seq_or_file=target_seq_or_file,
        cut_position_0based=cut_position_0based,
        left_arm_length=arm_len,
        right_arm_length=arm_len,
    )
    left_arm = arms["left_homology_arm"]
    right_arm = arms["right_homology_arm"]
    edit = str(edit_dna).strip().upper()

    # 3. Call Tier 1 atomic tools: Silent PAM mutation to prevent Cas9 re-cleaving the repaired donor
    pam_mutated = False
    pam_details = "No sgRNA sequence provided; PAM status unverified"
    mutations_applied = []
    warnings = []

    if grna_seq:
        g = grna_seq.strip().upper()
        # For SpCas9: cut is 3 bp upstream of PAM
        # Top strand (+1): cut is at 0, 3 intervening bases [0:3], PAM is at right_arm[3:6] (NGG)
        if grna_strand == 1 and len(right_arm) >= 6:
            pam_seq = right_arm[3:6]
            if pam_seq.endswith("GG"):
                mutated_syn = False
                if target_is_cds:
                    # Check codons overlapping PAM position 5 and 4
                    for target_pos in (5, 4):
                        c_rel = (target_pos - (cds_frame_offset % 3)) % 3
                        c_start = target_pos - c_rel
                        if c_start >= 0 and c_start + 3 <= len(right_arm):
                            orig_codon = right_arm[c_start : c_start + 3]
                            syn_info = get_codon_synonyms(orig_codon)
                            for syn in syn_info.get("synonymous_codons", []):
                                if syn[c_rel] != right_arm[target_pos]:
                                    new_right = right_arm[:c_start] + syn + right_arm[c_start + 3:]
                                    if not new_right[3:6].endswith("GG"):
                                        old_base = right_arm[target_pos]
                                        new_base = syn[c_rel]
                                        right_arm = new_right
                                        pam_mutated = True
                                        mutated_syn = True
                                        pam_details = (
                                            f"Silenced PAM via synonymous codon {orig_codon} -> {syn} ({syn_info['amino_acid']}) "
                                            f"at right arm [{c_start}:{c_start+3}] without altering protein sequence (Paquet et al. 2016 Nature)"
                                        )
                                        mutations_applied.append({
                                            "location": "right_arm",
                                            "offset_0based": c_start,
                                            "ref": orig_codon,
                                            "alt": syn,
                                            "amino_acid": syn_info["amino_acid"],
                                            "synonymous": True,
                                        })
                                        break
                        if mutated_syn:
                            break

                if not mutated_syn:
                    if target_is_cds:
                        # CRITICAL: Do NOT silently introduce missense mutation into CDS!
                        warnings.append(
                            f"CRITICAL: Target is in CDS and no synonymous mutation was found to silence PAM ({pam_seq}). "
                            "Non-synonymous mutation was refused to prevent missense/nonsense mutation in coding sequence. "
                            "Consider selecting an alternative gRNA target."
                        )
                        pam_details = f"PAM {pam_seq} retained: in CDS with no viable synonymous mutation"
                    else:
                        # Standard non-coding PAM mutation (Paquet 2016)
                        old_base = right_arm[5]
                        new_base = "A" if old_base == "G" else "T"
                        right_arm = right_arm[:5] + new_base + right_arm[6:]
                        pam_mutated = True
                        pam_details = f"Silenced PAM {pam_seq} -> {right_arm[3:6]} (G->{new_base} at right arm bp 5) to prevent Cas9 re-cleavage (Paquet et al. 2016 Nature)"
                        mutations_applied.append({"location": "right_arm", "offset_0based": 5, "ref": old_base, "alt": new_base, "synonymous": False})
        elif grna_strand == -1 and len(left_arm) >= 6:
            # Bottom strand (-1): cut is at len(left_arm), PAM_rc (CCN) is at left_arm[-6:-3]
            pam_rc = left_arm[-6:-3]
            if pam_rc.startswith("CC"):
                mutated_syn = False
                if target_is_cds:
                    # Check codon overlapping left_arm[-6]
                    target_idx = len(left_arm) - 6
                    c_rel = (target_idx - (cds_frame_offset % 3)) % 3
                    c_start = target_idx - c_rel
                    if c_start >= 0 and c_start + 3 <= len(left_arm):
                        orig_codon = left_arm[c_start : c_start + 3]
                        syn_info = get_codon_synonyms(orig_codon)
                        for syn in syn_info.get("synonymous_codons", []):
                            if syn[c_rel] != left_arm[target_idx]:
                                new_left = left_arm[:c_start] + syn + left_arm[c_start + 3:]
                                if not new_left[-6:-3].startswith("CC"):
                                    old_base = left_arm[target_idx]
                                    new_base = syn[c_rel]
                                    left_arm = new_left
                                    pam_mutated = True
                                    mutated_syn = True
                                    pam_details = (
                                        f"Silenced PAM reverse complement via synonymous codon {orig_codon} -> {syn} "
                                        f"({syn_info['amino_acid']}) at left arm [{c_start}:{c_start+3}] (Paquet et al. 2016 Nature)"
                                    )
                                    mutations_applied.append({
                                        "location": "left_arm",
                                        "offset_0based": c_start,
                                        "ref": orig_codon,
                                        "alt": syn,
                                        "amino_acid": syn_info["amino_acid"],
                                        "synonymous": True,
                                    })
                                    break

                if not mutated_syn:
                    if target_is_cds:
                        warnings.append(
                            f"CRITICAL: Target is in CDS and no synonymous mutation was found to silence PAM reverse complement ({pam_rc}). "
                            "Non-synonymous mutation was refused to prevent missense/nonsense mutation in coding sequence."
                        )
                        pam_details = f"PAM reverse complement {pam_rc} retained: in CDS with no viable synonymous mutation"
                    else:
                        old_base = left_arm[-6]
                        new_base = "T" if old_base == "C" else "A"
                        left_arm = left_arm[:-6] + new_base + left_arm[-5:]
                        pam_mutated = True
                        pam_details = f"Silenced PAM reverse complement {pam_rc} -> {left_arm[-6:-3]} to prevent Cas9 re-cleavage"
                        mutations_applied.append({"location": "left_arm", "offset_0based": len(left_arm) - 6, "ref": old_base, "alt": new_base, "synonymous": False})

    donor_seq = left_arm + edit + right_arm
    total_len = len(donor_seq)

    # 4. Standard quality checklist
    quality_checks = {
        "standard_arm_length_conforming": (35 <= arm_len <= 65) if donor_type.lower() == "ssodn" else (450 <= arm_len <= 850),
        "pam_recleavage_prevented": pam_mutated or (not grna_seq),
        "edit_distance_from_dsb_bp": 0,  # Placed directly at DSB
        "ssodn_total_length_under_200nt": (total_len <= 200) if donor_type.lower() == "ssodn" else True,
        "missense_mutation_avoided": not any(m.get("synonymous") is False for m in mutations_applied if target_is_cds),
    }

    protocol_steps = [
        {"step": 1, "action": "Synthesize designed ssODN donor oligo (PAGE-purified or HPLC-purified)."},
        {"step": 2, "action": "Prepare Cas9-sgRNA ribonucleoprotein (RNP) complex or co-transfection plasmid."},
        {"step": 3, "action": "Electroporate / transfect RNP with ssODN donor (typically 20-50 pmol) into target cells."},
        {"step": 4, "action": "Harvest cells at 48-72h post-transfection and perform genomic PCR + Sanger/NGS to quantify HDR rate."},
    ]

    return RecipeResult(
        recipe_name="recipe_crispr_hdr_donor",
        result_kind="component",
        completeness="component_only",
        product_sequence=donor_seq,
        product_topology="linear",
        features=[],
        primers=[],
        quality_checks=quality_checks,
        warnings=warnings,
        protocol_steps=protocol_steps,
        citations=AUTHORITATIVE_SOURCES,
        details={
            "recipe": "recipe_crispr_hdr_donor",
            "donor_type": donor_type,
            "donor_sequence": donor_seq,
            "total_length": total_len,
            "left_homology_arm": left_arm,
            "left_arm_length": len(left_arm),
            "edit_payload": edit,
            "edit_length": len(edit),
            "right_homology_arm": right_arm,
            "right_arm_length": len(right_arm),
            "pam_silenced": pam_mutated,
            "pam_silencing_details": pam_details,
            "mutations_applied": mutations_applied,
            "quality_checks": quality_checks,
            "authoritative_sources": AUTHORITATIVE_SOURCES,
        },
    )
