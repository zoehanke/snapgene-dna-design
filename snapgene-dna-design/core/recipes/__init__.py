# -*- coding: utf-8 -*-
"""core/recipes/ - Standard Laboratory SOP Recipes for SnapGene DNA Design.

Tier 2 in the 3+1 architecture. Provides standard, literature-grounded protocol
routes for high-frequency workflows and composes them from deterministic atomic
tools.
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

from core.recipes.contract import RecipeResult

recipe_point_mutagenesis = recipe_site_directed_mutagenesis

__all__ = [
    "RecipeResult",
    "recipe_crispr_hdr_donor",
    "recipe_gibson_assembly",
    "recipe_golden_gate",
    "recipe_restriction_cloning",
    "recipe_site_directed_mutagenesis",
    "recipe_point_mutagenesis",
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
    "recipe_point_mutagenesis": MUTAGENESIS_SOURCES,
    "recipe_protein_tagging": TAGGING_SOURCES,
    "recipe_cloning_verification": VERIFICATION_SOURCES,
}


def get_recipe_sources(recipe_name: str) -> list[dict]:
    """Retrieve literature citations and grounded rules for a standard recipe."""
    return ALL_RECIPE_SOURCES.get(recipe_name, [])


def GET_RECIPE_DEFINITIONS() -> list[dict]:
    """Return JSON Schema tool declarations for standard SOP recipes."""
    return [
        {
            "name": "recipe_crispr_hdr_donor",
            "description": "Design an ssODN, short dsDNA, or plasmid HDR donor around a Cas9 cut, with optional guide matching and PAM-silencing checks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_seq_or_file": {"type": "string", "description": "Target genomic sequence or file."},
                    "cut_position_0based": {"type": "integer", "description": "0-based Cas cut position coordinate."},
                    "edit_dna": {"type": "string", "description": "Desired mutation, insertion, or deletion DNA sequence."},
                    "donor_type": {"type": "string", "enum": ["ssODN", "dsDNA", "plasmid", "double-stranded DNA", "double-stranded donor", "double-stranded plasmid donor"], "default": "ssODN", "description": "Donor mode. dsDNA is the short annealed-duplex branch; plasmid is the larger double-stranded donor branch."},
                    "grna_seq": {"type": "string", "default": "", "description": "Optional 20-nt spacer used to match the original target and assess PAM re-cleavage."},
                    "grna_strand": {"type": "integer", "enum": [1, -1], "default": 1, "description": "Strand of sgRNA."},
                    "custom_arm_length": {"type": ["integer", "null"], "default": None, "description": "Override both homology-arm lengths."},
                    "target_is_cds": {"type": "boolean", "default": False, "description": "Apply CDS-aware PAM-silencing checks."},
                    "cds_frame_offset": {"type": "integer", "default": 0, "description": "CDS frame offset used for synonymous PAM edits."},
                    "edit_start_0based": {"type": ["integer", "null"], "default": None, "description": "Start of explicit half-open edit interval. Omit with edit_end for insertion at the cut."},
                    "edit_end_0based": {"type": ["integer", "null"], "default": None, "description": "End of explicit half-open edit interval. Supply with edit_start for replacement or insertion."},
                },
                "required": ["target_seq_or_file", "cut_position_0based", "edit_dna"],
            },
        },
        {
            "name": "recipe_gibson_assembly",
            "description": "Prepare and assemble Gibson fragments. Prefer fragments mode when the backbone and every insert must come from complete source templates and actual PCR products.",
            "parameters": {
                "type": "object",
                "properties": {
                    "vector_linear_seq": {"type": ["string", "object", "null"], "default": None, "description": "Legacy pre-linearized vector input."},
                    "insert_template_seq": {"type": ["string", "object", "null"], "default": None, "description": "Legacy insert source template."},
                    "insert_start": {"type": ["integer", "null"], "default": None, "description": "Legacy half-open insert start coordinate."},
                    "insert_end": {"type": ["integer", "null"], "default": None, "description": "Legacy half-open insert end coordinate."},
                    "overlap_length": {"type": "integer", "default": 22, "description": "Homology overlap length (standard: 20-25 bp)."},
                    "circular_product": {"type": "boolean", "default": True, "description": "Whether the assembled product is circular."},
                    "fragments": {
                        "type": ["array", "null"],
                        "default": None,
                        "description": "Recommended ordered full-template mode. Every item contains a complete template plus a target interval, including the backbone.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "template": {"type": ["string", "object"]},
                                "source": {"type": ["string", "object"]},
                                "start": {"type": "integer"},
                                "start_0based": {"type": "integer"},
                                "end": {"type": "integer"},
                                "end_0based": {"type": "integer"},
                            },
                            "anyOf": [
                                {"required": ["template", "start", "end"]},
                                {"required": ["source", "start", "end"]},
                                {"required": ["template", "start_0based", "end_0based"]},
                                {"required": ["source", "start_0based", "end_0based"]},
                            ],
                        },
                    },
                },
                "anyOf": [
                    {"required": ["fragments"]},
                    {"required": ["vector_linear_seq", "insert_template_seq", "insert_start", "insert_end"]},
                ],
                "required": [],
            },
        },
        {
            "name": "recipe_golden_gate",
            "description": "Digest Type IIS fragments and simulate Golden Gate ligation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fragments": {"type": "array", "items": {"type": ["string", "object"]}, "description": "At least two sequence, file, record, or serialized fragment inputs carrying Type IIS sites."},
                    "enzyme": {"type": "string", "default": "BsaI", "description": "Type IIS enzyme."},
                    "circular": {"type": "boolean", "default": True, "description": "Whether to circularize the assembled construct."},
                    "enzyme_name": {"type": ["string", "null"], "default": None, "description": "Compatibility alias that overrides enzyme when supplied."},
                    "circular_product": {"type": ["boolean", "null"], "default": None, "description": "Compatibility alias that overrides circular when supplied."},
                },
                "required": ["fragments"],
            },
        },
        {
            "name": "recipe_restriction_cloning",
            "description": "PCR-amplify an insert, digest vector and insert with restriction enzymes, and simulate T4 ligation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "vector_source": {"type": "string", "description": "Vector plasmid file or sequence."},
                    "insert_template": {"type": "string", "description": "Insert template file or sequence for PCR."},
                    "insert_start": {"type": "integer", "description": "0-based start on insert template."},
                    "insert_end": {"type": "integer", "description": "0-based end on insert template."},
                    "enzyme5": {"type": "string", "default": "EcoRI", "description": "5' restriction enzyme."},
                    "enzyme3": {"type": "string", "default": "BamHI", "description": "3' restriction enzyme."},
                    "insert_enzyme5": {"type": "string", "description": "Optional insert-side 5' enzyme; defaults to enzyme5 and supports compatible ends such as BspHI/NcoI."},
                    "insert_enzyme3": {"type": "string", "description": "Optional insert-side 3' enzyme; defaults to enzyme3."},
                    "insert_prefix": {"type": "string", "default": "", "description": "Product-side sequence before the selected insert; included in the forward primer tail and expression-boundary check."},
                    "insert_suffix": {"type": "string", "default": "", "description": "Product-side sequence after the selected insert; reverse-primer tail uses its reverse complement."},
                    "coding_sequence": {"type": ["boolean", "null"], "default": None, "description": "Whether to apply coding-boundary checks. Null infers coding intent from a target beginning with ATG."},
                    "expression_start": {"type": ["boolean", "null"], "default": None, "description": "Whether the caller asserts the expression start."},
                    "orientation": {"type": "string", "enum": ["auto", "forward", "reverse"], "default": "auto", "description": "Insert orientation for digest-ligation simulation."},
                },
                "required": ["vector_source", "insert_template", "insert_start", "insert_end"],
            },
        },
        {
            "name": "recipe_site_directed_mutagenesis",
            "description": "Design site-directed mutagenesis by QuikChange or inverse PCR from a complete parental template.",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_seq_or_file": {"type": "string", "description": "Template plasmid sequence or file."},
                    "start_0based": {"type": "integer", "description": "0-based start of mutation on template."},
                    "end_0based": {"type": "integer", "description": "0-based end of mutation on template."},
                    "alt_seq": {"type": "string", "description": "Replacement mutant nucleotide sequence."},
                    "target_flank_bp": {"type": "integer", "default": 15, "description": "Flanking base pairs on each side."},
                    "method": {"type": "string", "enum": ["quikchange", "inverse_pcr"], "default": "quikchange", "description": "Mutagenesis route."},
                },
                "required": ["template_seq_or_file", "start_0based", "end_0based", "alt_seq"],
            },
        },
        {
            "name": "recipe_protein_tagging",
            "description": "Design an in-frame protein tag, linker, and optional protease cassette from a complete target CDS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_cds_seq_or_file": {"type": "string", "description": "Target coding DNA sequence (CDS)."},
                    "tag_name_or_seq": {"type": "string", "default": "6xHis", "description": "Tag name or custom DNA sequence."},
                    "tag_position": {"type": "string", "enum": ["C-terminal", "N-terminal"], "default": "C-terminal", "description": "Position of tag relative to CDS."},
                    "linker_type": {"type": "string", "default": "flexible_G4S_x2", "description": "Linker identifier or custom DNA sequence."},
                    "protease_cleavage": {"type": ["string", "null"], "enum": ["TEV", "PreScission", "Thrombin", None], "default": None, "description": "Optional endoprotease cleavage site."},
                    "include_kozak": {"type": "boolean", "default": False, "description": "Whether to prepend eukaryotic Kozak consensus (GCCACC)."},
                    "terminal_stop_codon": {"type": "string", "default": "TAA", "description": "Stop codon appended when needed."},
                    "protease_site": {"type": ["string", "null"], "enum": ["TEV", "PreScission", "Thrombin", None], "default": None, "description": "Compatibility alias used when protease_cleavage is not supplied."},
                },
                "required": ["target_cds_seq_or_file"],
            },
        },
        {
            "name": "recipe_cloning_verification",
            "description": "Design cloning QC primers and optional diagnostic digest predictions from a complete recombinant record.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recombinant_plasmid_seq_or_file": {"type": "string", "description": "Recombinant plasmid sequence or file."},
                    "insert_start_0based": {"type": "integer", "description": "0-based start coordinate of insert in recombinant plasmid."},
                    "insert_end_0based": {"type": "integer", "description": "0-based end coordinate of insert in recombinant plasmid."},
                    "diagnostic_enzymes": {"type": ["array", "null"], "items": {"type": "string"}, "default": None, "description": "Optional list of restriction enzymes to simulate."},
                },
                "required": ["recombinant_plasmid_seq_or_file", "insert_start_0based", "insert_end_0based"],
            },
        },
    ]
