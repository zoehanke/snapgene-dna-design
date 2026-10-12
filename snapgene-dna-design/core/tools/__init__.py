# -*- coding: utf-8 -*-
"""core/tools/ - Atomic Biological Tools for AI Agents.

A rich suite of side-effect free, deterministic sequence analysis and manipulation tools.
AI agents call these tools to inspect DNA records, analyze restriction sites,
silence internal sites via synonymous mutations, design primers, simulate PCR
and cloning, fuse proteins in-frame, and export native SnapGene (.dna) files.
"""
from __future__ import annotations
from core.tools.comparison import compare_sequences

from core.tools.amplification import (
    anneal_oligos,
    calc_primer_tm,
    check_primer_dimers,
    design_overhang_primers,
    prepare_pcr_fragment,
    simulate_pcr,
)
from core.tools.assembly import (
    ligate_fragments,
    simulate_digest_ligation,
    simulate_golden_gate,
    simulate_overlap_assembly,
)
from core.tools.crispr import (
    design_crispr_grna,
    design_hdr_donor,
    extract_homology_arms,
    prepare_grna_oligos,
    prepare_pml104_guide,
)
from core.tools.grna import replace_grna_spacer, check_grna
from core.tools.experience_helper import (
    get_experience_categories,
    get_experience_rule_by_id,
    list_all_experience_rules,
    query_lab_experience,
)
from core.tools.feature_ops import (
    annotate_feature,
    get_feature,
    migrate_features_after_assembly,
)
from core.tools.fusion import (
    STANDARD_ELEMENTS,
    fuse_in_frame,
    get_standard_element,
)
from core.tools.inspection import (
    find_open_reading_frames,
    inspect_dna,
    summarize_backbone,
)
from core.tools.restriction import (
    check_overhang_compatibility,
    digest_sequence,
    digest_type_iis,
    fill_or_chew_overhang,
    find_restriction_sites,
)
from core.tools.sequence_ops import (
    rotate_sequence,
    check_reading_frame,
    extract_subsequence,
    mutate_sequence,
    strip_terminal_codons,
)
from core.tools.snapgene_io import export_snapgene, open_in_snapgene
from core.tools.translation import (
    get_codon_synonyms,
    reverse_complement,
    silent_mutation_remove_site,
    translate_dna,
)

__all__ = [
    'rotate_sequence',
    'ligate_fragments',
    "inspect_dna",
    "summarize_backbone",
    "find_open_reading_frames",
    "find_restriction_sites",
    "digest_sequence",
    "digest_type_iis",
    "fill_or_chew_overhang",
    "check_overhang_compatibility",
    "extract_subsequence",
    "check_reading_frame",
    "mutate_sequence",
    "strip_terminal_codons",
    "calc_primer_tm",
    "check_primer_dimers",
    "design_overhang_primers",
    "prepare_pcr_fragment",
    "anneal_oligos",
    "simulate_pcr",
    "simulate_overlap_assembly",
    "simulate_digest_ligation",
    "simulate_golden_gate",
    "design_crispr_grna",
    "prepare_grna_oligos",
    "prepare_pml104_guide",
    "replace_grna_spacer",
    "check_grna",
    "design_hdr_donor",
    "extract_homology_arms",
    "get_feature",
    "annotate_feature",
    "migrate_features_after_assembly",
    "reverse_complement",
    "translate_dna",
    "get_codon_synonyms",
    "compare_sequences",
    "silent_mutation_remove_site",
    "fuse_in_frame",
    "get_standard_element",
    "STANDARD_ELEMENTS",
    "export_snapgene",
    "open_in_snapgene",
    "query_lab_experience",
    "get_experience_categories",
    "get_experience_rule_by_id",
    "list_all_experience_rules",
    "ToolSpec",
    "TOOL_REGISTRY",
    "register_tool",
    "get_tool",
    "list_tool_definitions",
    "GET_TOOL_DEFINITIONS",
]

from core.tools.registry import (
    ToolSpec,
    TOOL_REGISTRY,
    register_tool,
    get_tool,
    list_tool_definitions,
)

GET_TOOL_DEFINITIONS = list_tool_definitions
