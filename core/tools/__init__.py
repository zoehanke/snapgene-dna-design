# -*- coding: utf-8 -*-
"""core/tools/ - Atomic Biological Tools for AI Agents.

A rich suite of side-effect free, deterministic sequence analysis and manipulation tools.
AI agents call these tools to inspect DNA records, analyze restriction sites,
silence internal sites via synonymous mutations, design primers, simulate PCR
and cloning, fuse proteins in-frame, and export native SnapGene (.dna) files.
"""
from __future__ import annotations

from core.tools.amplification import (
    anneal_oligos,
    calc_primer_tm,
    check_primer_dimers,
    design_overhang_primers,
    simulate_pcr,
)
from core.tools.assembly import (
    simulate_digest_ligation,
    simulate_golden_gate,
    simulate_overlap_assembly,
)
from core.tools.crispr import (
    design_crispr_grna,
    design_hdr_donor,
    extract_homology_arms,
    prepare_grna_oligos,
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
    "anneal_oligos",
    "simulate_pcr",
    "simulate_overlap_assembly",
    "simulate_digest_ligation",
    "simulate_golden_gate",
    "design_crispr_grna",
    "prepare_grna_oligos",
    "design_hdr_donor",
    "extract_homology_arms",
    "get_feature",
    "annotate_feature",
    "migrate_features_after_assembly",
    "reverse_complement",
    "translate_dna",
    "get_codon_synonyms",
    "silent_mutation_remove_site",
    "fuse_in_frame",
    "get_standard_element",
    "STANDARD_ELEMENTS",
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
            "name": "summarize_backbone",
            "description": "Quickly identify key plasmid backbone components: replication origins (e.g. pUC, ColE1), antibiotic selection markers (e.g. AmpR, KanR, CmR), and expression promoters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path_or_record": {
                        "type": "string",
                        "description": "Path to the plasmid file or SeqRecord.",
                    }
                },
                "required": ["file_path_or_record"],
            },
        },
        {
            "name": "get_feature",
            "description": "Find and extract a specific feature from a plasmid by name, type, or alias (e.g. 'GFP', 'AmpR', 'pCMV', 'bla', 'kan'), returning its exact sequence, coordinates, and strand.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path_or_record": {
                        "type": "string",
                        "description": "Path to sequence file or record identifier.",
                    },
                    "name_or_type": {
                        "type": "string",
                        "description": "Name, type, or alias of the feature to find.",
                    },
                    "return_all": {
                        "type": "boolean",
                        "description": "Whether to return all matches as a list (default: false).",
                        "default": False,
                    }
                },
                "required": ["file_path_or_record", "name_or_type"],
            },
        },
        {
            "name": "find_restriction_sites",
            "description": "Analyze restriction endonuclease recognition and cleavage sites in a DNA sequence or file. Identifies cut count, unique cutters, overhang geometry (5', 3', blunt), Type IIS status, and prokaryotic Dam/Dcm methylation overlap warnings.",
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
            "name": "check_overhang_compatibility",
            "description": "Check whether two DNA sticky/blunt overhangs can ligate together based on end geometry (5', 3', blunt) and Watson-Crick sequence complementarity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "overhang1": {"type": "string", "description": "Overhang sequence 1."},
                    "overhang2": {"type": "string", "description": "Overhang sequence 2."},
                    "type1": {"type": "string", "enum": ["5prime", "3prime", "blunt"], "default": "5prime"},
                    "type2": {"type": "string", "enum": ["5prime", "3prime", "blunt"], "default": "5prime"},
                },
                "required": ["overhang1", "overhang2"],
            },
        },
        {
            "name": "extract_subsequence",
            "description": "Topology-aware sequence extraction supporting origin-crossing circular intervals and reverse complement strand extraction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path_or_record": {"type": "string", "description": "File path or record."},
                    "start": {"type": "integer", "description": "0-based inclusive start index."},
                    "end": {"type": "integer", "description": "0-based exclusive end index."},
                    "strand": {"type": "integer", "enum": [1, -1], "default": 1},
                    "topology": {"type": "string", "enum": ["circular", "linear"], "default": "linear"},
                    "wraps_origin": {"type": "boolean", "default": False},
                },
                "required": ["file_path_or_record", "start", "end"],
            },
        },
        {
            "name": "calc_primer_tm",
            "description": "Calculate exact melting temperature (Tm) with nearest-neighbor thermodynamics and salt correction, GC percentage, and 3' GC clamp status of a PCR primer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "primer_seq": {"type": "string", "description": "Primer nucleotide sequence."},
                    "salt_conc_mM": {"type": "number", "default": 50.0, "description": "Na+ concentration in mM."},
                    "primer_conc_nM": {"type": "number", "default": 200.0, "description": "Primer concentration in nM."},
                },
                "required": ["primer_seq"],
            },
        },
        {
            "name": "design_overhang_primers",
            "description": "Design an optimal forward and reverse primer pair to amplify a target interval with optional 5' overhangs (homology arms, tags, restriction sites) targeting a specific annealing Tm.",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_record_or_seq": {"type": "string", "description": "Template file or sequence."},
                    "start": {"type": "integer", "description": "0-based start coordinate of target interval."},
                    "end": {"type": "integer", "description": "0-based end coordinate of target interval."},
                    "fwd_5prime_overhang": {"type": "string", "default": "", "description": "5' overhang tail for forward primer."},
                    "rev_5prime_overhang": {"type": "string", "default": "", "description": "5' overhang tail for reverse primer."},
                    "target_tm": {"type": "number", "default": 60.0, "description": "Target annealing Tm in Celsius."},
                },
                "required": ["template_record_or_seq", "start", "end"],
            },
        },
        {
            "name": "simulate_pcr",
            "description": "Simulate PCR amplification with forward and reverse primers (including 5' tails with homology arms or restriction sites) on a template sequence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_path_or_seq": {"type": "string", "description": "Template file or sequence string."},
                    "f_primer": {"type": "string", "description": "Forward primer sequence (5' to 3')."},
                    "r_primer": {"type": "string", "description": "Reverse primer sequence (5' to 3')."},
                    "topology": {"type": "string", "enum": ["circular", "linear"], "default": "linear"},
                },
                "required": ["template_path_or_seq", "f_primer", "r_primer"],
            },
        },
        {
            "name": "fuse_in_frame",
            "description": "Fuse two protein coding sequences (CDS) in-frame with an optional linker, stripping 5' partner's stop codon and verifying multiple of 3 reading frame.",
            "parameters": {
                "type": "object",
                "properties": {
                    "partner5_seq": {"type": "string", "description": "5' partner CDS sequence."},
                    "partner3_seq": {"type": "string", "description": "3' partner CDS sequence."},
                    "linker_seq": {"type": "string", "default": "", "description": "Optional linker sequence (must be multiple of 3)."},
                    "strip_p5_stop": {"type": "boolean", "default": True},
                    "add_terminal_stop": {"type": "boolean", "default": True},
                },
                "required": ["partner5_seq", "partner3_seq"],
            },
        },
        {
            "name": "get_standard_element",
            "description": "Retrieve exact nucleotide sequence, translation, and recommended SnapGene color of standard biological parts (epitope tags: 6xHis, FLAG, HA, Myc, Strep; linkers: (G4S)n, (EAAAK)n; proteases: TEV, PreScission).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of standard part, e.g. '6xHis', 'FLAG', 'HA', 'TEV', '(G4S)3', 'EAAAK'."},
                },
                "required": ["name"],
            },
        },
        {
            "name": "simulate_overlap_assembly",
            "description": "Simulate homologous overlap assembly (Gibson Assembly / In-Fusion) of 2 or more overlapping fragments into a circular plasmid or linear construct.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fragments": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of fragment sequences or files.",
                    },
                    "min_overlap": {"type": "integer", "default": 15},
                    "circular": {"type": "boolean", "default": True},
                },
                "required": ["fragments"],
            },
        },
        {
            "name": "simulate_golden_gate",
            "description": "Simulate Type IIS Golden Gate one-pot assembly (e.g. with BsaI or BsmBI), cleaving recognition sites and joining cohesive 4-bp sticky overhangs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fragments": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of DNA fragment sequences or files containing flanking Type IIS sites.",
                    },
                    "enzyme": {"type": "string", "default": "BsaI", "description": "Type IIS enzyme name (e.g. BsaI, BsmBI, Esp3I)."},
                    "circular": {"type": "boolean", "default": True},
                },
                "required": ["fragments"],
            },
        },
        {
            "name": "simulate_digest_ligation",
            "description": "Simulate restriction enzyme digestion of vector and insert followed by directional T4 DNA ligase ligation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "vector_source": {"type": "string", "description": "Vector plasmid file or record."},
                    "insert_source": {"type": "string", "description": "Insert file or record."},
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
            "name": "silent_mutation_remove_site",
            "description": "Introduce synonymous (silent) nucleotide mutations into a coding sequence (CDS) to destroy an unwanted internal restriction site without altering the amino acid translation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cds_seq": {"type": "string", "description": "In-frame protein coding sequence (length must be multiple of 3)."},
                    "enzyme_name": {"type": "string", "description": "Name of restriction enzyme whose site must be eliminated (e.g. 'EcoRI', 'BsaI')."},
                    "frame_offset": {"type": "integer", "default": 0, "description": "Reading frame offset (0, 1, or 2)."},
                },
                "required": ["cds_seq", "enzyme_name"],
            },
        },
        {
            "name": "export_snapgene",
            "description": "Export the designed construct into native SnapGene .dna and standard GenBank (.gb) files, preserving topology, annotations, and official SnapGene color palette.",
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
        {
            "name": "design_crispr_grna",
            "description": "Scan a target gene or genomic locus for candidate CRISPR sgRNA target sites with PAM recognition, GC content evaluation, and Pol III poly-T termination checks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_seq_or_file": {"type": "string", "description": "Target DNA sequence or file path."},
                    "nuclease": {"type": "string", "enum": ["SpCas9", "AsCas12a"], "default": "SpCas9"},
                    "start": {"type": "integer", "description": "Optional 0-based start coordinate."},
                    "end": {"type": "integer", "description": "Optional 0-based end coordinate."},
                },
                "required": ["target_seq_or_file"],
            },
        },
        {
            "name": "prepare_grna_oligos",
            "description": "Generate top and bottom forward/reverse cloning oligos with sticky overhangs for sgRNA vectors (e.g. BbsI-digested pX458/pX459 or BsmBI-digested lentiCRISPR), adding a 5' G if needed for human U6 promoter initiation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "spacer_seq": {"type": "string", "description": "20-nt spacer guide sequence."},
                    "vector_type": {"type": "string", "default": "BbsI", "description": "Cloning vector type or enzyme ('BbsI', 'BsmBI', 'pX458')."},
                },
                "required": ["spacer_seq"],
            },
        },
        {
            "name": "design_hdr_donor",
            "description": "Design a Homology-Directed Repair (HDR) donor template (ssODN or double-stranded plasmid arms) with automated synonymous PAM mutation to prevent Cas re-cleavage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_seq_or_file": {"type": "string", "description": "Target genomic sequence or file."},
                    "cut_position_0based": {"type": "integer", "description": "0-based Cas cut position coordinate."},
                    "edit_dna": {"type": "string", "description": "Mutation, insertion, or deletion DNA sequence."},
                    "left_arm_length": {"type": "integer", "default": 50, "description": "Left homology arm length."},
                    "right_arm_length": {"type": "integer", "default": 50, "description": "Right homology arm length."},
                    "grna_seq": {"type": "string", "description": "Optional sgRNA sequence to identify and silently mutate PAM."},
                },
                "required": ["target_seq_or_file", "cut_position_0based", "edit_dna"],
            },
        },
        {
            "name": "strip_terminal_codons",
            "description": "Strip start codon (ATG) or stop codons (TAA/TAG/TGA) from a CDS before in-frame fusion or tag engineering.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cds_seq": {"type": "string", "description": "Nucleotide CDS sequence."},
                    "strip_start": {"type": "boolean", "default": False, "description": "Whether to strip first 3 bp if ATG."},
                    "strip_stop": {"type": "boolean", "default": False, "description": "Whether to strip last 3 bp if stop codon."},
                },
                "required": ["cds_seq"],
            },
        },
        {
            "name": "get_codon_synonyms",
            "description": "Retrieve all synonymous codons translating to the same amino acid under the specified genetic code table.",
            "parameters": {
                "type": "object",
                "properties": {
                    "codon": {"type": "string", "description": "3-nucleotide codon triplet (e.g. 'CTG')."},
                    "table": {"type": "integer", "default": 1, "description": "NCBI genetic code table ID (1 = standard)."},
                },
                "required": ["codon"],
            },
        },
        {
            "name": "check_primer_dimers",
            "description": "Check for primer-dimer cross-hybridization (heterodimer) or self-dimerization (homodimer), especially at 3' ends.",
            "parameters": {
                "type": "object",
                "properties": {
                    "primer1": {"type": "string", "description": "Forward primer sequence."},
                    "primer2": {"type": "string", "description": "Optional reverse primer sequence (checks heterodimer if provided)."},
                },
                "required": ["primer1"],
            },
        },
        {
            "name": "anneal_oligos",
            "description": "Simulate in-vitro annealing of two single-stranded oligos, returning the duplex core and 5'/3' sticky overhangs on each end.",
            "parameters": {
                "type": "object",
                "properties": {
                    "top_oligo": {"type": "string", "description": "Top strand oligo sequence (5' to 3')."},
                    "bottom_oligo": {"type": "string", "description": "Bottom strand oligo sequence (5' to 3')."},
                },
                "required": ["top_oligo", "bottom_oligo"],
            },
        },
        {
            "name": "digest_sequence",
            "description": "Digest a sequence with a restriction endonuclease, returning cleaved fragments and their sticky/blunt overhang geometries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seq": {"type": "string", "description": "DNA sequence to digest."},
                    "enzyme": {"type": "string", "description": "Restriction enzyme name (e.g. 'EcoRI', 'BamHI')."},
                    "circular": {"type": "boolean", "default": False, "description": "Whether molecule is circular."},
                },
                "required": ["seq", "enzyme"],
            },
        },
        {
            "name": "digest_type_iis",
            "description": "Digest a single fragment flanked by Type IIS restriction sites (e.g. BsaI, BsmBI), stripping the recognition sites and returning the insert core with its 4-bp cohesive overhangs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fragment_seq": {"type": "string", "description": "Fragment sequence flanked by inward-facing Type IIS sites."},
                    "enzyme": {"type": "string", "default": "BsaI", "description": "Type IIS enzyme name."},
                },
                "required": ["fragment_seq"],
            },
        },
        {
            "name": "fill_or_chew_overhang",
            "description": "Simulate enzymatic end-repair (Klenow / T4 DNA Polymerase) to blunt sticky ends via 5' fill-in or 3' chew-back.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seq": {"type": "string", "description": "Double-stranded sequence core."},
                    "left_overhang": {"type": "string", "default": "", "description": "Left single-stranded overhang."},
                    "right_overhang": {"type": "string", "default": "", "description": "Right single-stranded overhang."},
                    "overhang_type": {"type": "string", "default": "5prime", "description": "'5prime' or '3prime'."},
                    "action": {"type": "string", "default": "fill_in", "enum": ["fill_in", "chew_back"], "description": "Repair action."},
                },
                "required": ["seq"],
            },
        },
        {
            "name": "extract_homology_arms",
            "description": "Extract left and right homology arms centered at a genomic cut or insertion site for HDR donor template design.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_seq_or_file": {"type": "string", "description": "Target genomic sequence or file path."},
                    "cut_position_0based": {"type": "integer", "description": "0-based coordinate of cut site."},
                    "left_arm_length": {"type": "integer", "default": 50, "description": "Left arm length."},
                    "right_arm_length": {"type": "integer", "default": 50, "description": "Right arm length."},
                },
                "required": ["target_seq_or_file", "cut_position_0based"],
            },
        },
    ]
