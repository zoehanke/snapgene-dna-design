# -*- coding: utf-8 -*-
"""core/tools/fusion.py - Atomic in-frame protein fusion tool.

Fuses two protein coding sequences with optional linkers, stripping premature
stop codons and maintaining reading frames.
"""
from __future__ import annotations

from Bio.Seq import Seq

from core.tools.sequence_ops import check_reading_frame


STOP_CODONS = {"TAA", "TAG", "TGA"}


def fuse_in_frame(
    partner5_seq: str,
    partner3_seq: str,
    linker_seq: str = "",
    strip_p5_stop: bool = True,
    add_terminal_stop: bool = True,
) -> dict:
    """Fuse two protein coding sequences in frame with optional linker.

    Args:
        partner5_seq: 5' partner CDS sequence.
        partner3_seq: 3' partner CDS sequence (e.g. epitope tag or fusion domain).
        linker_seq: Optional linker DNA sequence (e.g. (G4S) linker).
        strip_p5_stop: Whether to automatically strip terminal stop codon from partner5.
        add_terminal_stop: Whether to ensure the final fusion ends with a stop codon.

    Returns:
        dict with fusion_sequence, fusion_length, translation, in_frame status,
        and stop codon report.
    """
    p5 = str(partner5_seq).strip().upper()
    p3 = str(partner3_seq).strip().upper()
    linker = str(linker_seq).strip().upper()

    p5_stop_stripped = False
    if strip_p5_stop and len(p5) >= 3 and p5[-3:] in STOP_CODONS:
        p5 = p5[:-3]
        p5_stop_stripped = True

    if len(linker) % 3 != 0:
        raise ValueError(
            f"Linker sequence length ({len(linker)} bp) is not a multiple of 3, causing a frameshift!"
        )

    if len(p5) % 3 != 0:
        raise ValueError(
            f"5' partner CDS length ({len(p5)} bp) is not a multiple of 3!"
        )

    p3_had_stop = bool(len(p3) >= 3 and p3[-3:] in STOP_CODONS)
    if add_terminal_stop and not p3_had_stop:
        p3 += "TAA"

    fusion_dna = p5 + linker + p3
    rf_audit = check_reading_frame(fusion_dna)

    return {
        "fusion_sequence": fusion_dna,
        "fusion_length": len(fusion_dna),
        "partner5_length": len(p5),
        "partner5_stop_stripped": p5_stop_stripped,
        "linker_length": len(linker),
        "partner3_length": len(p3),
        "is_in_frame": rf_audit["is_multiple_of_three"],
        "has_premature_stop": rf_audit["has_premature_stop"],
        "premature_stop_positions": rf_audit["premature_stop_positions"],
        "terminal_stop": rf_audit["terminal_stop"],
        "translation": rf_audit["translation"],
    }


STANDARD_ELEMENTS: dict[str, dict[str, Any]] = {
    # Epitope & affinity tags
    "6xhis": {
        "name": "6xHis",
        "category": "tag",
        "dna": "CATCATCATCATCATCAT",
        "aa": "HHHHHH",
        "description": "Hexahistidine affinity tag for IMAC purification",
        "color": "#fdbf6f",
    },
    "8xhis": {
        "name": "8xHis",
        "category": "tag",
        "dna": "CATCATCATCATCATCATCATCAT",
        "aa": "HHHHHHHH",
        "description": "Octahistidine tag for higher stringency IMAC",
        "color": "#fdbf6f",
    },
    "flag": {
        "name": "FLAG",
        "category": "tag",
        "dna": "GACTACAAGGACGACGACGACAAG",
        "aa": "DYKDDDDK",
        "description": "FLAG epitope tag (enterokinase cleavable)",
        "color": "#cab2d6",
    },
    "3xflag": {
        "name": "3xFLAG",
        "category": "tag",
        "dna": "GACTACAAAGACCATGACGGTGATTATAAAGATCATGACATCGATTACAAGGATGACGATGACAAG",
        "aa": "DYKDHDGDYKDHDIDYKDDDDK",
        "description": "Triple-repeat FLAG tag with higher antibody affinity",
        "color": "#cab2d6",
    },
    "ha": {
        "name": "HA",
        "category": "tag",
        "dna": "TACCCATACGATGTTCCAGATTACGCT",
        "aa": "YPYDVPDYA",
        "description": "Influenza hemagglutinin epitope tag",
        "color": "#b15928",
    },
    "myc": {
        "name": "Myc",
        "category": "tag",
        "dna": "GAGCAGAAGCTGATCTCCGAGGAGGACCTG",
        "aa": "EQKLISEEDL",
        "description": "c-Myc epitope tag",
        "color": "#ff7f00",
    },
    "v5": {
        "name": "V5",
        "category": "tag",
        "dna": "GGTAAGCCTATCCCTAACCCTCTCCTCGGTCTCGATTCTACG",
        "aa": "GKPIPNPLLGLDST",
        "description": "Paramyxovirus V5 epitope tag",
        "color": "#6a3d9a",
    },
    "strep_ii": {
        "name": "Strep-tag II",
        "category": "tag",
        "dna": "TGGAGCCACCCGCAGTTCGAAAAA",
        "aa": "WSHPQFEK",
        "description": "Strep-tag II affinity tag for Strep-Tactin resins",
        "color": "#ffff99",
    },
    # Flexible & rigid linkers
    "g4s_1": {
        "name": "(G4S)1",
        "category": "linker",
        "dna": "GGTGGCGGTGGCTCG",
        "aa": "GGGGS",
        "description": "5-amino acid flexible glycine-serine linker",
        "color": "#b2df8a",
    },
    "g4s_2": {
        "name": "(G4S)2",
        "category": "linker",
        "dna": "GGTGGCGGTGGCTCGGGTGGCGGTGGCTCG",
        "aa": "GGGGSGGGGS",
        "description": "10-amino acid flexible glycine-serine linker",
        "color": "#b2df8a",
    },
    "g4s_3": {
        "name": "(G4S)3",
        "category": "linker",
        "dna": "GGTGGCGGTGGCTCGGGTGGCGGTGGCTCGGGTGGCGGTGGCTCG",
        "aa": "GGGGSGGGGSGGGGS",
        "description": "15-amino acid standard flexible linker",
        "color": "#b2df8a",
    },
    "eaaak_3": {
        "name": "(EAAAK)3",
        "category": "linker",
        "dna": "GAAGCGGCGGCGAAAGAAGCGGCGGCGAAAGAAGCGGCGGCGAAA",
        "aa": "EAAAKEAAAKEAAAK",
        "description": "15-amino acid rigid alpha-helical linker",
        "color": "#33a02c",
    },
    # Protease cleavage sites
    "tev": {
        "name": "TEV",
        "category": "protease_site",
        "dna": "GAGAACCTGTACTTCCAGGGT",
        "aa": "ENLYFQG",
        "description": "Tobacco Etch Virus protease cleavage site (cuts between Q and G)",
        "color": "#fb9a99",
    },
    "precission": {
        "name": "PreScission (3C)",
        "category": "protease_site",
        "dna": "CTGGAAGTTCTGTTCCAGGGGCCC",
        "aa": "LEVLFQGP",
        "description": "Human rhinovirus 3C protease cleavage site (cuts between Q and G)",
        "color": "#e31a1c",
    },
    "thrombin": {
        "name": "Thrombin",
        "category": "protease_site",
        "dna": "CTGGTGCCGCGCGGCAGC",
        "aa": "LVPRGS",
        "description": "Thrombin protease cleavage site (cuts between R and G)",
        "color": "#a6cee3",
    },
}


def get_standard_element(name: str) -> dict[str, Any]:
    """Retrieve nucleotide sequence, amino acid translation, and color of a standard biological part.

    Args:
        name: Name or alias of standard element (e.g. '6xHis', 'FLAG', 'HA', 'TEV', '(G4S)3', 'EAAAK')

    Returns:
        dict with name, category, dna, aa, description, color.
    """
    clean_name = str(name).strip().lower().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "")

    # Common aliases
    alias_map = {
        "his": "6xhis",
        "6xhis": "6xhis",
        "his6": "6xhis",
        "his_tag": "6xhis",
        "flag": "flag",
        "flag_tag": "flag",
        "3xflag": "3xflag",
        "ha": "ha",
        "ha_tag": "ha",
        "myc": "myc",
        "myc_tag": "myc",
        "v5": "v5",
        "strep": "strep_ii",
        "streptag": "strep_ii",
        "strep_tag": "strep_ii",
        "g4s": "g4s_1",
        "g4s1": "g4s_1",
        "g4s2": "g4s_2",
        "g4s3": "g4s_3",
        "eaaak": "eaaak_3",
        "eaaak3": "eaaak_3",
        "tev": "tev",
        "precission": "precission",
        "3c": "precission",
        "thrombin": "thrombin",
    }

    key = alias_map.get(clean_name, clean_name)
    if key in STANDARD_ELEMENTS:
        return dict(STANDARD_ELEMENTS[key])

    available = list(STANDARD_ELEMENTS.keys())
    raise ValueError(f"Unknown standard element '{name}'. Available elements: {available}")

