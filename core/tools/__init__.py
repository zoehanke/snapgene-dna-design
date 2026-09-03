# -*- coding: utf-8 -*-
"""core/tools/ - Atomic Biological Tools for AI Agents.

A rich suite of side-effect free, deterministic sequence analysis and manipulation tools.
AI agents call these tools to inspect DNA records, analyze restriction sites,
silence internal sites via synonymous mutations, design primers, simulate PCR
and cloning, fuse proteins in-frame, and export native SnapGene (.dna) files.
"""
from __future__ import annotations

from core.tools.amplification import simulate_pcr
from core.tools.assembly import simulate_digest_ligation, simulate_overlap_assembly
from core.tools.feature_ops import annotate_feature, get_feature
from core.tools.fusion import fuse_in_frame
from core.tools.inspection import find_open_reading_frames, inspect_dna
from core.tools.restriction import find_restriction_sites
from core.tools.sequence_ops import check_reading_frame, extract_subsequence, mutate_sequence
from core.tools.snapgene_io import export_snapgene, open_in_snapgene
from core.tools.translation import reverse_complement, silent_mutation_remove_site, translate_dna

__all__ = [
    "inspect_dna",
    "find_open_reading_frames",
    "find_restriction_sites",
    "extract_subsequence",
    "check_reading_frame",
    "mutate_sequence",
    "simulate_pcr",
    "simulate_overlap_assembly",
    "simulate_digest_ligation",
    "get_feature",
    "annotate_feature",
    "reverse_complement",
    "translate_dna",
    "silent_mutation_remove_site",
    "fuse_in_frame",
    "export_snapgene",
    "open_in_snapgene",
    "GET_TOOL_DEFINITIONS",
]


def GET_TOOL_DEFINITIONS() -> list[dict]:
    """Return JSON Schema tool declarations for LLM function calling."""
    return [
        {
            "name": "inspect_dna",
            "description": "Parse and inspect a DNA sequence file (GenBank, FASTA, SnapGene .dna) to retrieve topology, length, GC%, and all annotated features (promoters, CDS, terminators, tags, origins, resistances) with exact coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the GenBank, FASTA, or SnapGene .dna file.",
                    }
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "get_feature",
            "description": "Find and extract a specific feature from a plasmid by name (e.g. 'GFP', 'AmpR', 'pCMV') or type ('promoter', 'CDS', 'terminator'), returning its exact sequence, coordinates, and strand.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path_or_record": {
                        "type": "string",
                        "description": "Path to sequence file or record identifier.",
                    },
                    "name_or_type": {
                        "type": "string",
                        "description": "Name or type of the feature to find.",
                    },
                },
                "required": ["file_path_or_record", "name_or_type"],
            },
        },
        {
            "name": "find_restriction_sites",
            "description": "Analyze restriction endonuclease recognition and cleavage sites in a DNA sequence or file. Identifies cut count, unique cutters, overhang geometry (5', 3', blunt), and Type IIS status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path_or_seq": {
                        "type": "string",
                        "description": "File path or raw DNA nucleotide string.",
                    },
                    "enzymes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of restriction enzyme names to scan (e.g. ['EcoRI', 'NotI', 'BsaI']).",
                    },
                    "topology": {
                        "type": "string",
                        "enum": ["circular", "linear"],
                        "description": "DNA topology.",
                    },
                },
                "required": ["file_path_or_seq"],
            },
        },
        {
            "name": "extract_subsequence",
            "description": "Safely extract a specific coordinate interval [start, end) from a sequence or file with topology awareness (circular origin-wrap) and strand orientation (+1 or -1).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path_or_record": {
                        "type": "string",
                        "description": "Path to sequence file or record identifier.",
                    },
                    "start": {
                        "type": "integer",
                        "description": "0-based start coordinate.",
                    },
                    "end": {
                        "type": "integer",
                        "description": "0-based half-open end coordinate.",
                    },
                    "strand": {
                        "type": "integer",
                        "enum": [1, -1],
                        "description": "+1 for top strand, -1 for reverse complement.",
                    },
                    "topology": {
                        "type": "string",
                        "enum": ["circular", "linear"],
                    },
                },
                "required": ["file_path_or_record", "start", "end"],
            },
        },
        {
            "name": "reverse_complement",
            "description": "Compute the 5'->3' reverse complement of a DNA nucleotide sequence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seq": {"type": "string", "description": "DNA sequence."},
                },
                "required": ["seq"],
            },
        },
        {
            "name": "translate_dna",
            "description": "Translate a DNA sequence into amino acid peptide in a specified reading frame (1, 2, 3, -1, -2, -3).",
            "parameters": {
                "type": "object",
                "properties": {
                    "seq": {"type": "string", "description": "DNA sequence."},
                    "frame": {"type": "integer", "enum": [1, 2, 3, -1, -2, -3], "default": 1},
                },
                "required": ["seq"],
            },
        },
        {
            "name": "check_reading_frame",
            "description": "Verify coding sequence reading frame, checking for multiples of 3, premature stop codons, and generating in-silico translation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dna_seq": {
                        "type": "string",
                        "description": "Coding DNA nucleotide sequence.",
                    },
                    "start_offset": {
                        "type": "integer",
                        "default": 0,
                        "description": "0-based reading frame offset (0, 1, or 2).",
                    },
                },
                "required": ["dna_seq"],
            },
        },
        {
            "name": "fuse_in_frame",
            "description": "Fuse two protein coding sequences in frame with an optional linker. Automatically strips the 5' partner's stop codon and verifies that the linker and fusion maintain the open reading frame.",
            "parameters": {
                "type": "object",
                "properties": {
                    "partner5_seq": {"type": "string", "description": "5' CDS sequence."},
                    "partner3_seq": {"type": "string", "description": "3' CDS sequence (e.g. tag or domain)."},
                    "linker_seq": {"type": "string", "default": "", "description": "Linker DNA sequence (must be multiple of 3)."},
                    "strip_p5_stop": {"type": "boolean", "default": True},
                    "add_terminal_stop": {"type": "boolean", "default": True},
                },
                "required": ["partner5_seq", "partner3_seq"],
            },
        },
        {
            "name": "silent_mutation_remove_site",
            "description": "Perform synonymous (silent) single-base mutations within a CDS to eliminate an internal restriction enzyme recognition site while keeping the translated amino acid sequence 100% unchanged.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cds_seq": {"type": "string", "description": "Coding DNA sequence."},
                    "enzyme_name": {"type": "string", "description": "Restriction enzyme to silence (e.g. 'EcoRI', 'BsaI')."},
                    "frame_offset": {"type": "integer", "default": 0, "description": "Reading frame offset (0, 1, or 2)."},
                },
                "required": ["cds_seq", "enzyme_name"],
            },
        },
        {
            "name": "simulate_pcr",
            "description": "Simulate PCR amplification with forward and reverse primers. Supports primers with 5' non-binding tails (homology arms, restriction tags) and computes the exact amplicon product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_path_or_seq": {
                        "type": "string",
                        "description": "Template file path or raw sequence.",
                    },
                    "f_primer": {
                        "type": "string",
                        "description": "5'->3' forward primer sequence (may include 5' tail).",
                    },
                    "r_primer": {
                        "type": "string",
                        "description": "5'->3' reverse primer sequence (may include 5' tail).",
                    },
                    "topology": {
                        "type": "string",
                        "enum": ["circular", "linear"],
                    },
                },
                "required": ["template_path_or_seq", "f_primer", "r_primer"],
            },
        },
        {
            "name": "simulate_overlap_assembly",
            "description": "Simulate Gibson, In-Fusion, or Overlap-PCR assembly of multiple DNA fragments. Checks terminal homologous overlaps and computes circular or linear product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fragments": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered list of DNA sequence strings.",
                    },
                    "min_overlap": {
                        "type": "integer",
                        "default": 15,
                        "description": "Minimum required homology overlap in bp.",
                    },
                    "circular": {
                        "type": "boolean",
                        "default": True,
                        "description": "Whether product is circular plasmid.",
                    },
                },
                "required": ["fragments"],
            },
        },
        {
            "name": "simulate_digest_ligation",
            "description": "Simulate sticky-end restriction digestion and directional ligation into a vector backbone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "vector_source": {
                        "type": "string",
                        "description": "Vector file path.",
                    },
                    "insert_source": {
                        "type": "string",
                        "description": "Insert file path.",
                    },
                    "vector_enzymes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of enzymes cutting the vector (1 or 2).",
                    },
                    "insert_enzymes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of enzymes cutting the insert (defaults to vector_enzymes).",
                    },
                    "orientation": {
                        "type": "string",
                        "enum": ["forward", "reverse"],
                        "default": "forward",
                    },
                },
                "required": ["vector_source", "insert_source", "vector_enzymes"],
            },
        },
        {
            "name": "export_snapgene",
            "description": "Export the designed construct into native SnapGene .dna and standard GenBank (.gb) files, preserving topology and annotated features.",
            "parameters": {
                "type": "object",
                "properties": {
                    "record_or_seq": {"type": "string", "description": "Construct sequence string or SeqRecord."},
                    "out_dir": {"type": "string", "description": "Output directory."},
                    "filename_base": {"type": "string", "default": "construct"},
                    "topology": {"type": "string", "enum": ["circular", "linear"], "default": "circular"},
                },
                "required": ["record_or_seq", "out_dir"],
            },
        },
        {
            "name": "open_in_snapgene",
            "description": "Launch the local desktop SnapGene application (D:\\SnapGene\\SnapGene.exe) to display the newly designed plasmid map directly on the user's screen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the .dna or .gb file."},
                },
                "required": ["file_path"],
            },
        },
    ]
