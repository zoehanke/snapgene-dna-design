# -*- coding: utf-8 -*-
"""core/tools/fusion.py - Atomic in-frame protein fusion tool.

Fuses two protein coding sequences with optional linkers, stripping premature
stop codons and maintaining reading frames.
"""
from __future__ import annotations
from typing import Any

import copy
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord
from core.models.molecule import MoleculeInput, as_molecule, derived_molecule
from core.tools.result import ToolResult, check_result

from core.tools.sequence_ops import check_reading_frame


STOP_CODONS = {"TAA", "TAG", "TGA"}


def fuse_in_frame(
    partner5_seq: MoleculeInput,
    partner3_seq: MoleculeInput,
    linker_seq: MoleculeInput = "",
    strip_p5_stop: bool = True,
    add_terminal_stop: bool = True,
) -> ToolResult:
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
    sources = [as_molecule(value) for value in (partner5_seq, partner3_seq, linker_seq)]
    p5, p3, linker = [str(record.seq).upper() for record in sources]

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
    rf_audit = check_reading_frame(fusion_dna).analysis

    from core.tools.sequence_ops import slice_record_interval
    record = SeqRecord(Seq(fusion_dna), id='fusion', annotations={'molecule_type': 'DNA', 'topology': 'linear'})
    offset = 0
    for original, sequence in ((sources[0], p5), (sources[2], linker), (sources[1], p3)):
        retained = slice_record_interval(original, 0, min(len(sequence), len(original)))
        for feature in retained.features:
            record.features.append(feature._shift(offset))
        offset += len(sequence)
    if rf_audit['valid']:
        record.features.append(SeqFeature(FeatureLocation(0, len(record), strand=1), type='CDS',
                qualifiers={'label': ['fusion_CDS'], 'translation': [rf_audit['translation'].rstrip('*')]}))
    product = derived_molecule(record, sources, operation='fuse_in_frame')
    return ToolResult(products=[product], checks=[check_result('reading_frame', subject=product,
            status='PASSED' if rf_audit['valid'] else 'FAILED', scope='complete_CDS', details=rf_audit)], analysis={
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
    })


STANDARD_ELEMENTS: dict[str, dict[str, Any]] = {
    # Epitope & affinity tags
    "6xhis": {
        "name": "6xHis",
        "category": "tag",
        "dna": "CATCATCATCATCATCAT",
        "aa": "HHHHHH",
        "description": "Hexahistidine affinity tag for IMAC purification",
        "color": "#fdbf6f",
        "citation": "Hochuli, E. et al. (1988). Genetic Approach to Facilitate Purification of Recombinant Proteins with a Novel Metal Chelate Adsorbent. Nature Biotechnology (Bio/Technology) 6:1321-1325.",
        "doi": "10.1038/nbt1188-1321",
    },
    "8xhis": {
        "name": "8xHis",
        "category": "tag",
        "dna": "CATCATCATCATCATCATCATCAT",
        "aa": "HHHHHHHH",
        "description": "Octahistidine tag for higher stringency IMAC",
        "color": "#fdbf6f",
        "citation": "Spriestersbach, A. et al. (2015). Purification of His-Tagged Proteins. Methods Enzymol 559:1-15.",
        "doi": "10.1016/bs.mie.2014.11.003",
    },
    "flag": {
        "name": "FLAG",
        "category": "tag",
        "dna": "GACTACAAGGACGACGACGACAAG",
        "aa": "DYKDDDDK",
        "description": "FLAG epitope tag (enterokinase cleavable)",
        "color": "#cab2d6",
        "citation": "Hopp, T.P. et al. (1988). A Short Polypeptide Marker Sequence Useful for Recombinant Protein Identification and Purification. Nature Biotechnology (Bio/Technology) 6:1204-1210.",
        "doi": "10.1038/nbt1088-1204",
    },
    "3xflag": {
        "name": "3xFLAG",
        "category": "tag",
        "dna": "GACTACAAAGACCATGACGGTGATTATAAAGATCATGACATCGATTACAAGGATGACGATGACAAG",
        "aa": "DYKDHDGDYKDHDIDYKDDDDK",
        "description": "Triple-repeat FLAG tag with higher antibody affinity",
        "color": "#cab2d6",
        "citation": "Hernan, R. et al. (2000). Multiple epitope tagging of proteins with the 3xFLAG system. BioTechniques 28(4):789-793.",
        "doi": "10.2144/00284pf01",
    },
    "ha": {
        "name": "HA",
        "category": "tag",
        "dna": "TACCCATACGATGTTCCAGATTACGCT",
        "aa": "YPYDVPDYA",
        "description": "Influenza hemagglutinin epitope tag",
        "color": "#b15928",
        "citation": "Field, J. et al. (1988). Purification of a RAS-responsive adenylyl cyclase complex from Saccharomyces cerevisiae by use of an epitope-addition method. Mol Cell Biol 8(5):2159-2165.",
        "doi": "10.1128/mcb.8.5.2159",
    },
    "myc": {
        "name": "Myc",
        "category": "tag",
        "dna": "GAGCAGAAGCTGATCTCCGAGGAGGACCTG",
        "aa": "EQKLISEEDL",
        "description": "c-Myc epitope tag",
        "color": "#ff7f00",
        "citation": "Evan, G.I. et al. (1985). Isolation of monoclonal antibodies specific for human c-myc proto-oncogene product. Mol Cell Biol 5(12):3610-3616.",
        "doi": "10.1128/mcb.5.12.3610",
    },
    "v5": {
        "name": "V5",
        "category": "tag",
        "dna": "GGTAAGCCTATCCCTAACCCTCTCCTCGGTCTCGATTCTACG",
        "aa": "GKPIPNPLLGLDST",
        "description": "Paramyxovirus V5 epitope tag",
        "color": "#6a3d9a",
        "citation": "Southern, J.A. et al. (1991). Identification of an epitope on the P and V proteins of simian virus 5 that can be used for ease of detection and purification of proteins. J Gen Virol 72(7):1551-1557.",
        "doi": "10.1099/0022-1317-72-7-1551",
    },
    "strep_ii": {
        "name": "Strep-tag II",
        "category": "tag",
        "dna": "TGGAGCCACCCGCAGTTCGAAAAA",
        "aa": "WSHPQFEK",
        "description": "Strep-tag II affinity tag for Strep-Tactin resins",
        "color": "#ffff99",
        "citation": "Schmidt, T.G. and Skerra, A. (2007). The Strep-tag system for one-step purification and high-affinity detection or capturing of proteins. Nature Protocols 2(3):698-709.",
        "doi": "10.1038/nprot.2007.209",
    },
    # Flexible & rigid linkers
    "g4s_1": {
        "name": "(G4S)1",
        "category": "linker",
        "dna": "GGTGGCGGTGGCTCG",
        "aa": "GGGGS",
        "description": "5-amino acid flexible glycine-serine linker",
        "color": "#b2df8a",
        "citation": "Huston, J.S. et al. (1988). Protein engineering of antibody binding sites: recovery of specific activity in an anti-digoxin single-chain Fv analogue produced in Escherichia coli. PNAS 85(16):5879-5883.",
        "doi": "10.1073/pnas.85.16.5879",
    },
    "g4s_2": {
        "name": "(G4S)2",
        "category": "linker",
        "dna": "GGTGGCGGTGGCTCGGGTGGCGGTGGCTCG",
        "aa": "GGGGSGGGGS",
        "description": "10-amino acid flexible glycine-serine linker",
        "color": "#b2df8a",
        "citation": "Huston, J.S. et al. (1988). PNAS 85(16):5879-5883.",
        "doi": "10.1073/pnas.85.16.5879",
    },
    "g4s_3": {
        "name": "(G4S)3",
        "category": "linker",
        "dna": "GGTGGCGGTGGCTCGGGTGGCGGTGGCTCGGGTGGCGGTGGCTCG",
        "aa": "GGGGSGGGGSGGGGS",
        "description": "15-amino acid standard flexible linker",
        "color": "#b2df8a",
        "citation": "Chen, X. et al. (2013). Fusion protein linkers: property, design and functionality. Adv Drug Deliv Rev 65(10):1357-1369.",
        "doi": "10.1016/j.addr.2012.09.039",
    },
    "eaaak_3": {
        "name": "(EAAAK)3",
        "category": "linker",
        "dna": "GAAGCGGCGGCGAAAGAAGCGGCGGCGAAAGAAGCGGCGGCGAAA",
        "aa": "EAAAKEAAAKEAAAK",
        "description": "15-amino acid rigid alpha-helical linker",
        "color": "#33a02c",
        "citation": "Arai, R. et al. (2001). Design of the linkers which effectively separate domains of a bifunctional fusion protein. Protein Eng 14(8):529-532.",
        "doi": "10.1093/protein/14.8.529",
    },
    # Protease cleavage sites
    "tev": {
        "name": "TEV",
        "category": "protease_site",
        "dna": "GAGAACCTGTACTTCCAGGGT",
        "aa": "ENLYFQG",
        "description": "Tobacco Etch Virus protease cleavage site (cuts between Q and G)",
        "color": "#fb9a99",
        "citation": "Carrington, J.C. and Dougherty, W.G. (1988). A viral cleavage site in a polyprotein is processed in vitro by a proteinase with a genetic relationship to the polyprotein. PNAS 85(10):3391-3395.",
        "doi": "10.1073/pnas.85.10.3391",
    },
    "precission": {
        "name": "PreScission (3C)",
        "category": "protease_site",
        "dna": "CTGGAAGTTCTGTTCCAGGGGCCC",
        "aa": "LEVLFQGP",
        "description": "Human rhinovirus 3C protease cleavage site (cuts between Q and G)",
        "color": "#e31a1c",
        "citation": "Walker, P.A. et al. (1994). Efficient site-specific cleavage of fusion proteins using cloned human rhinovirus 14 3C protease. Biotechnology (N Y) 12(6):601-605.",
        "doi": "10.1038/nbt0694-601",
    },
    "thrombin": {
        "name": "Thrombin",
        "category": "protease_site",
        "dna": "CTGGTGCCGCGCGGCAGC",
        "aa": "LVPRGS",
        "description": "Thrombin protease cleavage site (cuts between R and G)",
        "color": "#a6cee3",
        "citation": "Chang, J.Y. (1985). Thrombin specificity: requirement for apolar amino acids adjacent to the thrombin cleavage site of prothrombin. Eur J Biochem 151(1):217-224.",
        "doi": "10.1111/j.1432-1033.1985.tb09139.x",
    },
}


def get_standard_element(name: str) -> ToolResult:
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
        data = dict(STANDARD_ELEMENTS[key])
        record = SeqRecord(Seq(data.pop('dna')), id=data['name'], annotations={'molecule_type':'DNA','topology':'linear'})
        record.features = [SeqFeature(FeatureLocation(0,len(record),strand=1),type='misc_feature',qualifiers={'label':[data['name']]})]
        product = derived_molecule(record, operation='get_standard_element')
        data['scope'] = 'reference_sequence_component'
        return ToolResult(products=[product],analysis=data)

    available = list(STANDARD_ELEMENTS.keys())
    raise ValueError(f"Unknown standard element '{name}'. Available elements: {available}")

