# -*- coding: utf-8 -*-
"""core/recipes/protein_tagging.py - Standard SOP Recipe for Protein Expression & Tagging.

AUTHORITATIVE SOURCES & CLASSICAL PROTOCOLS:
1. Terpe, K. (2003).
   Overview of tag protein fusion: from molecular and biochemical fundamentals to commercial systems.
   Applied Microbiology and Biotechnology, 60(5), pp.523-533. doi:10.1007/s00253-002-1158-6.
2. Kozak, M. (1986).
   Point mutations define a sequence flanking the AUG initiator codon that modulates translation by eukaryotic ribosomes.
   Cell, 44(2), pp.283-292. doi:10.1016/0092-8674(86)90762-2.
3. Waugh, D.S. (2011).
   An overview of enzymatic reagents for removal of affinity tags.
   Protein Expression and Purification, 80(2), pp.283-293. doi:10.1016/j.pep.2011.08.005.
"""
from __future__ import annotations

import pathlib
from typing import Any

from core.recipes.contract import RecipeResult
from core.tools.fusion import fuse_in_frame, get_standard_element
from core.tools.inspection import _load_record
from core.tools.sequence_ops import check_reading_frame, strip_terminal_codons
from core.tools.translation import translate_dna

AUTHORITATIVE_SOURCES = [
    {
        "citation": "Terpe, K. (2003). Overview of tag protein fusion. Appl Microbiol Biotechnol 60(5):523-533.",
        "institution": "University of Braunschweig",
        "doi": "10.1007/s00253-002-1158-6",
        "rules_enforced": [
            "C-terminal tagging requires strictly stripping the stop codon of the target CDS.",
            "Linker sequences must be an exact multiple of 3 to preserve reading frame.",
            "In-frame fusion must maintain continuous translation across junctions.",
        ],
    },
    {
        "citation": "Kozak, M. (1986). Point mutations define a sequence flanking the AUG initiator codon. Cell 44(2):283-292.",
        "institution": "University of Pittsburgh",
        "doi": "10.1016/0092-8674(86)90762-2",
        "rules_enforced": [
            "Eukaryotic mammalian expression requires a consensus Kozak sequence (GCCACC) preceding the initiator ATG.",
        ],
    },
    {
        "citation": "Waugh, D.S. (2011). An overview of enzymatic reagents for removal of affinity tags. Protein Expr Purif 80(2):283-293.",
        "institution": "National Cancer Institute (NCI-Frederick)",
        "doi": "10.1016/j.pep.2011.08.005",
        "rules_enforced": [
            "Protease cleavage sites (TEV, PreScission) should be positioned immediately adjacent to target CDS.",
            "Post-cleavage residual amino acids must be explicitly documented and consistent with the intended protein.",
        ],
    },
]

# Standard cleavage sites in DNA (E. coli / standard codon preference)
PROTEASE_CLEAVAGE_SITES = {
    "TEV": {
        "aa_recognition": "ENLYFQG",
        "dna_sequence": "GAAAACCTGTATTTTCAGGGC",  # Cleaves between Q and G
        "cleaved_aa": "ENLYFQ | G",
        "expected_residual_amino_acids": "G",
    },
    "PreScission": {
        "aa_recognition": "LEVLFQGP",
        "dna_sequence": "CTGGAAGTTCTGTTCCAGGGGCCC",  # Cleaves between Q and GP
        "cleaved_aa": "LEVLFQ | GP",
        "expected_residual_amino_acids": "GP",
    },
    "Thrombin": {
        "aa_recognition": "LVPRGS",
        "dna_sequence": "CTGGTGCCGCGCGGCAGC",  # Cleaves between R and GS
        "cleaved_aa": "LVPR | GS",
        "expected_residual_amino_acids": "GS",
    },
}

STANDARD_LINKERS = {
    "flexible_G4S_x1": "GGTGGCGGTGGCTCG",
    "flexible_G4S_x2": "GGTGGCGGTGGCTCGGGTGGCGGTGGCTCG",
    "flexible_G4S_x3": "GGTGGCGGTGGCTCGGGTGGCGGTGGCTCGGGTGGCGGTGGCTCG",
    "rigid_EAAAK_x2": "GAAGCCGCCGCCAAAGAAGCCGCCGCCAAA",
    "rigid_EAAAK_x3": "GAAGCCGCCGCCAAAGAAGCCGCCGCCAAAGAAGCCGCCGCCAAA",
}


def recipe_protein_tagging(
    target_cds_seq_or_file: str | pathlib.Path | SeqRecord,
    tag_name_or_seq: str = "6xHis",
    tag_position: str = "C-terminal",  # 'C-terminal' or 'N-terminal'
    linker_type: str = "flexible_G4S_x2",  # key in STANDARD_LINKERS or custom DNA
    protease_cleavage: str | None = None,  # 'TEV', 'PreScission', 'Thrombin'
    include_kozak: bool = False,
    terminal_stop_codon: str = "TAA",
    protease_site: str | None = None,
) -> dict[str, Any]:
    """Execute the gold-standard SOP for recombinant protein expression, tagging, and cleavage cassettes.

    Follows Terpe 2003 (Appl Microbiol Biotechnol) and Kozak 1986 (Cell):
    - When C-terminal tagging: automatically strips the target CDS stop codon (TAA/TAG/TGA).
    - When N-terminal tagging: preserves tag initiator ATG, adds Kozak sequence if requested.
    - Verifies linker nucleotide length is divisible by 3 (mod 3 == 0).
    - Optionally incorporates high-efficiency endoprotease cleavage sites (TEV / PreScission).
    - Checks reading frame throughout the entire fused construct without internal pre-mature stop codons.
    - Emits full provenance and authoritative literature citations.
    """
    if protease_cleavage is None and protease_site is not None:
        protease_cleavage = protease_site

    rec = _load_record(target_cds_seq_or_file)
    target_cds = str(rec.seq).upper().strip()

    # 1. Resolve Tag DNA sequence
    try:
        tag_info = get_standard_element(tag_name_or_seq)
        tag_dna = tag_info["dna"]
    except ValueError:
        tag_dna = str(tag_name_or_seq).strip().upper()

    # 2. Resolve Linker DNA sequence
    if linker_type in STANDARD_LINKERS:
        linker_dna = STANDARD_LINKERS[linker_type]
    else:
        try:
            linker_info = get_standard_element(linker_type)
            linker_dna = linker_info["dna"]
        except ValueError:
            linker_dna = str(linker_type).strip().upper()

    if len(linker_dna) % 3 != 0:
        raise ValueError(
            f"Linker DNA length ({len(linker_dna)} bp) is not divisible by 3! Violates in-frame fusion rule (Terpe 2003)."
        )

    # 3. Resolve Protease Cleavage DNA sequence
    cleavage_dna = ""
    cleavage_meta = None
    if protease_cleavage:
        cleavage_meta = PROTEASE_CLEAVAGE_SITES.get(protease_cleavage)
        if not cleavage_meta:
            raise ValueError(f"Unknown protease cleavage site '{protease_cleavage}'. Choose from TEV, PreScission, Thrombin.")
        cleavage_dna = cleavage_meta["dna_sequence"]

    pos = tag_position.strip().lower()
    kozak_dna = "GCCACC" if include_kozak else ""

    warnings = []

    if "c" in pos:
        # C-TERMINAL TAGGING SOP:
        # Target CDS must have its terminal stop codon stripped!
        cds_stripped_res = strip_terminal_codons(target_cds, strip_start=False, strip_stop=True)
        cds_core = cds_stripped_res["sequence"]
        stop_stripped = cds_stripped_res["stop_stripped"]
        if not stop_stripped:
            warnings.append("No canonical stop codon (TAA/TAG/TGA) detected at 3' end of target CDS; proceeding with stripped sequence.")

        # Order: [Kozak] + Target_CDS_core + [Cleavage] + [Linker] + Tag + Stop
        # Placing cleavage adjacent to CDS ensures protease digestion removes both Linker and Tag
        components = [cds_core]
        if cleavage_dna:
            components.append(cleavage_dna)
        if linker_dna:
            components.append(linker_dna)
        components.append(tag_dna)

        # Fuse components in frame
        fused = "".join(components)
        if fused.endswith(("TAA", "TAG", "TGA")):
            product_dna = (kozak_dna + fused) if include_kozak else fused
        else:
            product_dna = (kozak_dna + fused + terminal_stop_codon) if include_kozak else (fused + terminal_stop_codon)

    else:
        # N-TERMINAL TAGGING SOP:
        # Order: [Kozak] + Tag + [Linker] + [Cleavage] + Target_CDS (with its own stop or terminal_stop)
        tag_stripped_res = strip_terminal_codons(tag_dna, strip_start=False, strip_stop=True)
        tag_core = tag_stripped_res["sequence"]
        if not tag_core.startswith("ATG"):
            tag_core = "ATG" + tag_core

        # If target CDS has start codon ATG, we can keep it or strip it; standard SOP usually strips target ATG if directly preceded by protease/tag
        cds_stripped_start = strip_terminal_codons(target_cds, strip_start=True, strip_stop=False)["sequence"]

        components = [tag_core]
        if linker_dna:
            components.append(linker_dna)
        if cleavage_dna:
            components.append(cleavage_dna)
        components.append(cds_stripped_start)

        fused = "".join(components)
        if not fused.endswith(("TAA", "TAG", "TGA")):
            fused = fused + terminal_stop_codon

        product_dna = (kozak_dna + fused) if include_kozak else fused

    # 4. In-frame translation verification
    trans_dna = product_dna[len(kozak_dna):]
    aa_seq = translate_dna(trans_dna, frame=1)
    internal_stops = aa_seq[:-1].count("*")

    quality_checks = {
        "tag_position": tag_position,
        "tag_name": tag_name_or_seq,
        "in_frame_fusion": (len(trans_dna) % 3 == 0),
        "zero_internal_stop_codons": (internal_stops == 0),
        "terminal_stop_codon_present": aa_seq.endswith("*"),
        "kozak_motif_included": include_kozak,
        "linker_length_divisible_by_3": (len(linker_dna) % 3 == 0),
    }

    if internal_stops > 0:
        warnings.append(
            f"CRITICAL: {internal_stops} internal stop codon(s) detected in translated fusion protein! Check reading frame."
        )

    protocol_steps = [
        {"step": 1, "action": f"Synthesize or clone the in-frame {tag_position.upper()}-terminal tagged CDS into expression vector."},
        {"step": 2, "action": "Verify in-frame continuity by Sanger sequencing through the junction and linker region."},
        {"step": 3, "action": f"Express recombinant protein and perform affinity purification or Western blot for {tag_name_or_seq}."},
    ]
    if cleavage_meta and cleavage_meta.get("protease"):
        protocol_steps.append({
            "step": 4,
            "action": f"Incubate with {cleavage_meta.get('protease')} protease to cleave tag; residual scar: '{cleavage_meta.get('expected_residual_amino_acids')}'."
        })

    return RecipeResult(
        recipe_name="recipe_protein_tagging",
        result_kind="component",
        completeness="component_only",
        product_sequence=product_dna,
        product_topology="linear",
        features=[
            {"name": f"Fusion_{tag_name_or_seq}", "type": "CDS", "start": 1, "end": len(product_dna), "strand": 1}
        ],
        primers=[],
        quality_checks=quality_checks,
        warnings=warnings,
        protocol_steps=protocol_steps,
        citations=AUTHORITATIVE_SOURCES,
        details={
            "recipe": "recipe_protein_tagging",
            "product_dna_sequence": product_dna,
            "product_dna_length": len(product_dna),
            "translated_protein_sequence": aa_seq,
            "protein_length_aa": len(aa_seq.rstrip("*")),
            "tag_position": tag_position,
            "tag_sequence": tag_dna,
            "linker_sequence": linker_dna,
            "protease_cleavage": cleavage_meta,
            "quality_checks": quality_checks,
            "authoritative_sources": AUTHORITATIVE_SOURCES,
        },
    )

