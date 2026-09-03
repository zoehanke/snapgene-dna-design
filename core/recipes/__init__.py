# -*- coding: utf-8 -*-
"""core/recipes/ - Standard Laboratory SOP Recipes for SnapGene DNA Design.

Tier 2 in the 3+1 architecture. Provides gold-standard, authoritative protocols
for high-frequency routine workflows, preventing AI hallucinations while grounding
all operations in Tier 1 atomic tools and classical molecular biology literature.
"""
from __future__ import annotations

from core.recipes.crispr_hdr import AUTHORITATIVE_SOURCES as CRISPR_SOURCES, recipe_crispr_hdr_donor
from core.recipes.gibson import AUTHORITATIVE_SOURCES as GIBSON_SOURCES, recipe_gibson_assembly
from core.recipes.golden_gate import AUTHORITATIVE_SOURCES as GOLDEN_GATE_SOURCES, recipe_golden_gate
from core.recipes.mutagenesis import (
    AUTHORITATIVE_SOURCES as MUTAGENESIS_SOURCES,
    recipe_site_directed_mutagenesis,
)
from core.recipes.protein_tagging import (
    AUTHORITATIVE_SOURCES as TAGGING_SOURCES,
    recipe_protein_tagging,
)
from core.recipes.restriction_cloning import (
    AUTHORITATIVE_SOURCES as RESTRICTION_SOURCES,
    recipe_restriction_cloning,
)
from core.recipes.verification import (
    AUTHORITATIVE_SOURCES as VERIFICATION_SOURCES,
    recipe_cloning_verification,
)

__all__ = [
    "recipe_crispr_hdr_donor",
    "recipe_gibson_assembly",
    "recipe_golden_gate",
    "recipe_restriction_cloning",
    "recipe_site_directed_mutagenesis",
    "recipe_protein_tagging",
    "recipe_cloning_verification",
    "get_recipe_sources",
    "GET_RECIPE_DEFINITIONS",
]

ALL_RECIPE_SOURCES = {
    "recipe_crispr_hdr_donor": CRISPR_SOURCES,
    "recipe_gibson_assembly": GIBSON_SOURCES,
    "recipe_golden_gate": GOLDEN_GATE_SOURCES,
    "recipe_restriction_cloning": RESTRICTION_SOURCES,
    "recipe_site_directed_mutagenesis": MUTAGENESIS_SOURCES,
    "recipe_protein_tagging": TAGGING_SOURCES,
    "recipe_cloning_verification": VERIFICATION_SOURCES,
}


def get_recipe_sources(recipe_name: str) -> list[dict]:
    """Retrieve authoritative literature citations and grounded rules for a standard SOP recipe."""
    return ALL_RECIPE_SOURCES.get(recipe_name, [])


def GET_RECIPE_DEFINITIONS() -> list[dict]:
    """Return JSON Schema tool declarations for standard SOP recipes."""
    return [
        {
            "name": "recipe_crispr_hdr_donor",
            "description": "Standard SOP for CRISPR/Cas9 sgRNA & HDR repair donor template design. Enforces 40-60 nt ssODN arms (Paquet 2016 Nature) or 500-800 bp plasmid arms, with synonymous PAM mutation to block Cas9 re-cleavage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_seq_or_file": {"type": "string", "description": "Target genomic sequence or file."},
                    "cut_position_0based": {"type": "integer", "description": "0-based Cas cut position coordinate."},
                    "edit_dna": {"type": "string", "description": "Desired mutation, insertion, or deletion DNA sequence."},
                    "donor_type": {"type": "string", "enum": ["ssODN", "plasmid"], "default": "ssODN", "description": "'ssODN' (small edits) or 'plasmid' (large edits)."},
                    "grna_seq": {"type": "string", "description": "20-nt sgRNA sequence to identify and silently mutate PAM."},
                    "grna_strand": {"type": "integer", "enum": [1, -1], "default": 1, "description": "Strand of sgRNA."},
                },
                "required": ["target_seq_or_file", "cut_position_0based", "edit_dna"],
            },
        },
        {
            "name": "recipe_gibson_assembly",
            "description": "Standard SOP for Gibson / In-Fusion overlapping assembly. Enforces 20-25 bp overlaps, primer binding Tm 60±2°C, delta-Tm <= 2°C, 3' GC clamp, and T5 short fragment protection (Gibson 2009 Nature Methods).",
            "parameters": {
                "type": "object",
                "properties": {
                    "vector_linear_seq": {"type": "string", "description": "Linearized vector sequence."},
                    "insert_template_seq": {"type": "string", "description": "Insert template sequence for PCR."},
                    "insert_start": {"type": "integer", "description": "0-based start coordinate on insert template."},
                    "insert_end": {"type": "integer", "description": "0-based end coordinate on insert template."},
                    "overlap_length": {"type": "integer", "default": 22, "description": "Homology overlap length (standard: 20-25 bp)."},
                },
                "required": ["vector_linear_seq", "insert_template_seq", "insert_start", "insert_end"],
            },
        },
        {
            "name": "recipe_golden_gate",
            "description": "Standard SOP for Type IIS Golden Gate assembly (BsaI/BsmBI). Enforces orthogonal 4-bp non-palindromic cohesive ends and complete excision of recognition sites (Engler 2008 PLoS ONE, Potapov 2018 ACS Synth Biol).",
            "parameters": {
                "type": "object",
                "properties": {
                    "fragments": {"type": "array", "items": {"type": "string"}, "description": "List of DNA fragments with Type IIS flanking sites."},
                    "enzyme": {"type": "string", "default": "BsaI", "description": "Type IIS enzyme ('BsaI' or 'BsmBI')."},
                    "circular": {"type": "boolean", "default": True, "description": "Whether to circularize the assembled construct."},
                },
                "required": ["fragments"],
            },
        },
        {
            "name": "recipe_restriction_cloning",
            "description": "Standard SOP for restriction endonuclease cloning and T4 ligation. Enforces NEB 5' protective bases, directional sticky-end pairing, Dam/Dcm methylation checks, and DpnI template clearance (Sambrook Molecular Cloning 4th ed.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "vector_source": {"type": "string", "description": "Vector plasmid file or sequence."},
                    "insert_template": {"type": "string", "description": "Insert template file or sequence for PCR."},
                    "insert_start": {"type": "integer", "description": "0-based start on insert template."},
                    "insert_end": {"type": "integer", "description": "0-based end on insert template."},
                    "enzyme5": {"type": "string", "default": "EcoRI", "description": "5' restriction enzyme."},
                    "enzyme3": {"type": "string", "default": "BamHI", "description": "3' restriction enzyme."},
                },
                "required": ["vector_source", "insert_template", "insert_start", "insert_end"],
            },
        },
        {
            "name": "recipe_site_directed_mutagenesis",
            "description": "Standard SOP for QuikChange Site-Directed Mutagenesis (SDM). Enforces centered mutation, QuikChange Tm >= 78°C, and DpnI parental plasmid digestion (Zheng et al. 2004 NAR, Sambrook Ch. 13).",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_seq_or_file": {"type": "string", "description": "Template plasmid sequence or file."},
                    "start_0based": {"type": "integer", "description": "0-based start of mutation on template."},
                    "end_0based": {"type": "integer", "description": "0-based end of mutation on template."},
                    "alt_seq": {"type": "string", "description": "Replacement mutant nucleotide sequence."},
                    "target_flank_bp": {"type": "integer", "default": 15, "description": "Flanking base pairs on each side."},
                },
                "required": ["template_seq_or_file", "start_0based", "end_0based", "alt_seq"],
            },
        },
        {
            "name": "recipe_protein_tagging",
            "description": "Standard SOP for recombinant protein expression, affinity tagging, and endoprotease cleavage cassettes. Enforces stop-codon stripping for C-terminal tags, mod 3 == 0 linker length, and Kozak sequence (Terpe 2003, Kozak 1986).",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_cds_seq_or_file": {"type": "string", "description": "Target coding DNA sequence (CDS)."},
                    "tag_name_or_seq": {"type": "string", "default": "6xHis", "description": "Tag name (6xHis, FLAG, HA, Myc, StrepII, GST, MBP, GFP) or DNA sequence."},
                    "tag_position": {"type": "string", "enum": ["C-terminal", "N-terminal"], "default": "C-terminal", "description": "Position of tag relative to CDS."},
                    "linker_type": {"type": "string", "default": "flexible_G4S_x2", "description": "Linker identifier or custom DNA sequence."},
                    "protease_cleavage": {"type": "string", "enum": ["TEV", "PreScission", "Thrombin"], "description": "Optional endoprotease cleavage site."},
                    "include_kozak": {"type": "boolean", "default": False, "description": "Whether to prepend eukaryotic Kozak consensus (GCCACC)."},
                },
                "required": ["target_cds_seq_or_file"],
            },
        },
        {
            "name": "recipe_cloning_verification",
            "description": "Standard SOP for cloning quality control: colony PCR primers (vector-insert junction crossing), Sanger sequencing primer layout (avoiding 30-50 bp dye-blob blind zone), and diagnostic restriction digest band prediction (Sambrook Ch. 1 & 8, Sanger 1977).",
            "parameters": {
                "type": "object",
                "properties": {
                    "recombinant_plasmid_seq_or_file": {"type": "string", "description": "Recombinant plasmid sequence or file."},
                    "insert_start_0based": {"type": "integer", "description": "0-based start coordinate of insert in recombinant plasmid."},
                    "insert_end_0based": {"type": "integer", "description": "0-based end coordinate of insert in recombinant plasmid."},
                    "diagnostic_enzymes": {"type": "array", "items": {"type": "string"}, "description": "List of restriction enzymes to simulate diagnostic digest."},
                },
                "required": ["recombinant_plasmid_seq_or_file", "insert_start_0based", "insert_end_0based"],
            },
        },
    ]
