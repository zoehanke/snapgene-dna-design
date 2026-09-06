# -*- coding: utf-8 -*-
"""core/guardrails/checklist.py - Foundational Biological Self-Audit Checklist (Tier 3 Guardrails).

Provides a standard molecular biology self-inspection checklist and lightweight
factual sanity audit to prevent LLM hallucinations:
- BIO-01: Reading frame and premature stop codon check
- BIO-02: Stop codon integrity in fusions
- BIO-03: Internal restriction site conflicts
- BIO-04: Feature / strand orientation consistency
- BIO-05: CRISPR HDR donor in vivo recleavage risk
- BIO-06: RNA Pol III (U6) transcription poly-T termination abort
- BIO-07: PCR primer 3' catastrophic cross- and self-dimer risk
- BIO-08: Circular plasmid replicon & selectable marker presence
- BIO-09: Host Dam/Dcm methylation restriction cut blockade
- BIO-10: Extreme long inverted repeats and synthesis complexity
"""
from __future__ import annotations

import pathlib
import re
from typing import Any

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.tools.amplification import check_primer_dimers
from core.tools.inspection import inspect_dna
from core.tools.restriction import find_restriction_sites
from core.tools.sequence_ops import check_reading_frame

FOUNDATIONAL_CHECKLIST = [
    {
        "id": "BIO-01-FRAME",
        "title": "读码框与提前终止 (Reading Frame & Premature Stops)",
        "prompt": "目的蛋白编码区（CDS）长度是否为 3 的倍数？翻译出的氨基酸序列中是否出现非预期的提前终止密码子（*）？",
        "tool_to_use": "check_reading_frame",
        "citation": "Crick, F.H. et al. (1961). General nature of the genetic code for proteins. Nature 192:1227-1232.",
        "doi": "10.1038/1921227a0",
    },
    {
        "id": "BIO-02-STOP",
        "title": "融合蛋白终止密码子策略 (Stop Codon in Fusion)",
        "prompt": "做 C 端融合或串联表达时，上游片段末尾的原有终止密码子（TAA/TAG/TGA）是否已被剔除？最终产物末尾是否保留了合法的终止密码子？",
        "tool_to_use": "fuse_in_frame / strip_terminal_codons",
        "citation": "Terpe, K. (2003). Overview of tag protein fusion. Appl Microbiol Biotechnol 60(5):523-533.",
        "doi": "10.1007/s00253-002-1158-6",
    },
    {
        "id": "BIO-03-ENZYME",
        "title": "限制性酶切位点内部冲突 (Internal Restriction Sites)",
        "prompt": "计划使用的克隆内切酶，在目的插入片段内部是否已被破坏或不存在？若存在内部切点，是否已通过同义突变（silent mutation）沉默？",
        "tool_to_use": "find_restriction_sites / silent_mutation_remove_site",
        "citation": "Green, M.R. and Sambrook, J. (2012). Molecular Cloning: A Laboratory Manual (4th ed.). Cold Spring Harbor Laboratory Press. Chapter 3.",
        "institution": "Cold Spring Harbor Laboratory (CSHL)",
    },
    {
        "id": "BIO-04-STRAND",
        "title": "正负链与方向核对 (Strand Orientation)",
        "prompt": "原质粒中目的基因位于正链（+1）还是负链（-1）？若为负链，拼接或扩增时是否已执行反向互补（reverse complement）？",
        "tool_to_use": "reverse_complement / inspect_dna",
        "citation": "IUPAC-IUB Commission on Biochemical Nomenclature (1970). Abbreviations and symbols for the description of the conformation of polypeptide and polynucleotide chains. Eur J Biochem 15(2):203-208.",
        "doi": "10.1111/j.1432-1033.1970.tb00996.x",
    },
    {
        "id": "BIO-05-RECLEAVAGE",
        "title": "CRISPR 供体防体内二次切割 (CRISPR Recleavage Prevention)",
        "prompt": "HDR 修复供体模板（ssODN 或质粒）整合入基因组后，残留的 PAM（NGG）或 Seed 核心区是否已被同义突变破坏，杜绝游离 Cas9 再次复切？",
        "tool_to_use": "recipe_crispr_hdr_donor / get_codon_synonyms",
        "citation": "Paquet, D. et al. (2016). Efficient introduction of specific homozygous and heterozygous mutations using CRISPR/Cas9. Nature 533(7601):125-129.",
        "doi": "10.1038/nature17664",
    },
    {
        "id": "BIO-06-POL3_TERMINATION",
        "title": "RNA Pol III (U6) 转录提前终止规避 (Pol III Terminator Avoidance)",
        "prompt": "在人源/鼠源 U6 pol III 启动子驱动的 sgRNA 编码区内，是否存在连续 4 个或更多个胸腺嘧啶（TTTT），导致转录提前终止？",
        "tool_to_use": "design_crispr_grna / quick_biological_sanity_check",
        "citation": "Bogenhagen, D.F. and Brown, D.D. (1981). Nucleotide sequences in Xenopus 5S DNA required for transcription termination. Cell 24(1):261-270.",
        "doi": "10.1016/0092-8674(81)90523-7",
    },
    {
        "id": "BIO-07-PRIMER_DIMER",
        "title": "PCR 引物 3' 端严重二聚体拦截 (Primer 3' Dimer Check)",
        "prompt": "扩增或组装用引物的 3' 核心结合末端是否存在 $\\ge 4$ bp 连续互补，导致严重的二聚体竞争消耗聚合酶与试剂？",
        "tool_to_use": "check_primer_dimers / calc_primer_tm",
        "citation": "SantaLucia, J. (1998). A unified view of polymer, dumbbell, and oligonucleotide DNA nearest-neighbor thermodynamics. PNAS 95(4):1460-1465.",
        "doi": "10.1073/pnas.95.4.1460",
    },
    {
        "id": "BIO-08-REPLICON_MARKER",
        "title": "质粒宿主维持要素完整性 (Replicon & Selection Marker Presence)",
        "prompt": "环状质粒构建产物中，是否至少包含一个功能性复制原点（ori，如 pUC/ColE1）和一个抗性筛选标记（如 AmpR/KanR），确保质粒在宿主菌中能够复制扩增与抗性筛选？",
        "tool_to_use": "inspect_dna / quick_biological_sanity_check",
        "citation": "Casali, N. (2003). Escherichia coli Host Strains and Plasmid Vectors. Methods Mol Biol 235:19-26.",
        "doi": "10.1385/1-59259-409-3:19",
    },
    {
        "id": "BIO-09-METHYLATION",
        "title": "宿主内源甲基化对酶切的完全封闭 (Dam/Dcm Methylation Cut Blockade)",
        "prompt": "计划使用的限制酶切位点（如 XbaI/ClaI/StuI），是否与大肠杆菌宿主 Dam（GATC）或 Dcm（CCWGG）甲基化识别模体发生重叠，导致质粒提出来后完全无法切开？",
        "tool_to_use": "find_restriction_sites / quick_biological_sanity_check",
        "citation": "Marinus, M.G. and Morris, N.R. (1973). Isolation of deoxyribonucleic acid methylase mutants of Escherichia coli K-12. J Bacteriol 114(3):1143-1150; Roberts, R.J. et al. (2015). REBASE. Nucleic Acids Res 43:D298-D299.",
        "doi": "10.1093/nar/gku1046",
    },
    {
        "id": "BIO-10-HAIRPIN_REPEAT",
        "title": "极端长回文反向重复与体内自发缺失 (Inverted Repeats & Hairpin Crash)",
        "prompt": "序列中是否存在连续 $\\ge 14$ bp 的严格反向重复回文结构或极端高 GC 区，导致细菌复制叉停滞、启动 SbcCD 酶切造成体内自发缺失或基因合成拒单？",
        "tool_to_use": "quick_biological_sanity_check",
        "citation": "Leach, D.R. (1994). Long DNA palindromes, cruciform structures, genetic instability and secondary structure repair. BioEssays 16(12):893-900; Connelly, J.C. et al. (1998). The SbcCD nuclease of Escherichia coli. Cell 95(2):249-258.",
        "doi": "10.1002/bies.950161207",
    },
]


def get_biological_self_audit_checklist() -> list[dict[str, str]]:
    """Return the foundational biological checklist for LLM prompt injection."""
    return FOUNDATIONAL_CHECKLIST


def scan_crispr_recleavage_risk(
    donor_seq: str,
    grna_seq: str,
    pam: str = "NGG",
) -> dict[str, Any]:
    """Scan donor repair sequence for intact PAM/Seed regions that risk Cas9 in vivo re-cleavage."""
    d = str(donor_seq).upper()
    g = str(grna_seq).strip().upper()
    if not g or not d:
        return {
            "recleavage_risk": False,
            "intact_spacer_found": False,
            "intact_seed_pam_found": False,
            "details": "No gRNA or donor sequence provided to check recleavage risk.",
        }

    seed = g[-10:] if len(g) >= 10 else g
    seed_rc = str(Seq(seed).reverse_complement())
    g_rc = str(Seq(g).reverse_complement())

    top_pattern = re.compile(rf"{re.escape(seed)}[ACGT]GG")
    bottom_pattern = re.compile(rf"CC[ACGT]{re.escape(seed_rc)}")

    top_hits = [m.start() for m in top_pattern.finditer(d)]
    bottom_hits = [m.start() for m in bottom_pattern.finditer(d)]

    has_intact_seed_pam = len(top_hits) > 0 or len(bottom_hits) > 0
    exact_spacer_top = g in d
    exact_spacer_bottom = g_rc in d

    risk = has_intact_seed_pam or exact_spacer_top or exact_spacer_bottom
    details = []
    if exact_spacer_top or exact_spacer_bottom:
        details.append("Exact full 20-nt sgRNA spacer target found intact in donor sequence.")
    if top_hits:
        details.append(f"Top strand intact Seed+PAM ([seed]NGG) detected at 0-based offset(s): {top_hits}.")
    if bottom_hits:
        details.append(f"Bottom strand intact Seed+PAM (CCN[seed_rc]) detected at 0-based offset(s): {bottom_hits}.")

    return {
        "recleavage_risk": risk,
        "intact_spacer_found": exact_spacer_top or exact_spacer_bottom,
        "intact_seed_pam_found": has_intact_seed_pam,
        "top_strand_hits": top_hits,
        "bottom_strand_hits": bottom_hits,
        "details": "; ".join(details) if details else "No intact PAM/Seed found; donor safe from Cas9 re-cleavage.",
    }


def scan_u6_pol3_termination(seq: str) -> dict[str, Any]:
    """Scan sequence (e.g. sgRNA spacer or U6 cassette) for consecutive TTTT Pol III terminators."""
    s = str(seq).upper()
    matches = []
    for m in re.finditer(r"T{4,}", s):
        matches.append({
            "position_0based": m.start(),
            "length": len(m.group()),
            "sequence": m.group(),
        })

    has_terminator = len(matches) > 0
    return {
        "has_poly_t_terminator": has_terminator,
        "terminator_count": len(matches),
        "terminators": matches,
        "details": (
            f"Detected {len(matches)} poly-T (TTTT) Pol III termination motif(s) at 0-based offset(s) {[m['position_0based'] for m in matches]}. Will abort sgRNA transcription in U6 systems."
            if has_terminator
            else "No consecutive TTTT motifs found; safe for U6 Pol III transcription."
        ),
    }


def scan_plasmid_maintenance_elements(
    record_or_seq: SeqRecord | str,
    topology: str = "linear",
) -> dict[str, Any]:
    """Scan circular plasmid for fundamental maintenance elements: origin of replication (ori) and selectable marker."""
    top = topology.lower()
    if isinstance(record_or_seq, SeqRecord):
        top = str(record_or_seq.annotations.get("topology", topology)).lower()

    if top != "circular":
        return {
            "applicable": False,
            "is_circular": False,
            "has_origin": True,
            "has_marker": True,
            "missing_essential_maintenance": False,
            "details": "Linear fragment or oligo; replication origin and marker check not applicable.",
        }

    ori_found = []
    marker_found = []

    ori_keywords = {"ori", "origin", "rep_origin", "puc", "cole1", "colie1", "p15a", "f1", "2micron", "sv40", "sc101", "pt181", "incp"}
    marker_keywords = {"ampr", "ampicillin", "bla", "kanr", "kanamycin", "neo", "neomycin", "cmr", "cat", "chloramphenicol", "tetr", "tetracycline", "hygr", "hygromycin", "puro", "puromycin", "spec", "spectinomycin", "zeo", "zeocin", "blasticidin", "bsd", "gentamicin"}

    if isinstance(record_or_seq, SeqRecord) and record_or_seq.features:
        for feat in record_or_seq.features:
            ftype = feat.type.lower()
            text_corpus = f"{ftype} "
            for k, v in feat.qualifiers.items():
                text_corpus += " ".join(str(x) for x in v).lower() + " "

            if ftype in ("rep_origin", "origin") or any(kw in text_corpus for kw in ori_keywords):
                label = feat.qualifiers.get("label", [feat.type])[0]
                if label not in ori_found:
                    ori_found.append(label)

            if any(kw in text_corpus for kw in marker_keywords):
                label = feat.qualifiers.get("label", [feat.type])[0]
                if label not in marker_found:
                    marker_found.append(label)

    seq_str = str(record_or_seq.seq if isinstance(record_or_seq, SeqRecord) else record_or_seq).upper()
    if not ori_found:
        if "TTGAGATCCTTTTTTTCTGCGCG" in seq_str or "AGATTAGCGGATCCT" in seq_str or "GTTTTCCCAGTCACGAC" in seq_str:
            ori_found.append("Inferred-pUC/ColE1-core")

    has_ori = len(ori_found) > 0
    has_marker = len(marker_found) > 0
    missing = (not has_ori) and (not has_marker)

    details = []
    if not has_ori:
        details.append("No replication origin (ori) found")
    else:
        details.append(f"Replication origin detected: {ori_found}")
    if not has_marker:
        details.append("No selectable antibiotic marker found")
    else:
        details.append(f"Selectable marker detected: {marker_found}")

    return {
        "applicable": True,
        "is_circular": True,
        "has_origin": has_ori,
        "has_marker": has_marker,
        "origins_detected": ori_found,
        "markers_detected": marker_found,
        "missing_essential_maintenance": missing,
        "details": "; ".join(details) + (". Critical: Circular plasmid lacks both ori and selection marker!" if missing else "."),
    }


def scan_methylation_blockade(
    record_or_seq: SeqRecord | str,
    cloning_enzymes: list[str] | None = None,
) -> dict[str, Any]:
    """Scan if restriction enzyme cut sites overlap with Dam/Dcm methylation motifs, blocking cleavage in E. coli."""
    if not cloning_enzymes:
        return {
            "has_methylation_blockade": False,
            "blocked_sites": [],
            "details": "No cloning enzymes specified to check methylation blockade.",
        }

    seq_str = str(record_or_seq.seq if isinstance(record_or_seq, SeqRecord) else record_or_seq).upper()
    res = find_restriction_sites(seq_str, enzymes=cloning_enzymes)

    blocked = []
    for enz_name, details in res.get("enzymes", {}).items():
        for cut in details.get("cuts", []):
            warnings = cut.get("methylation_warnings", [])
            if warnings:
                blocked.append({
                    "enzyme": enz_name,
                    "position_0based": cut.get("recognition_start_0based"),
                    "strand": cut.get("strand", 1),
                    "methylation_warnings": warnings,
                })

    has_blockade = len(blocked) > 0
    return {
        "has_methylation_blockade": has_blockade,
        "blocked_sites": blocked,
        "blocked_enzymes": list({b["enzyme"] for b in blocked}),
        "details": (
            f"Detected {len(blocked)} restriction site(s) completely or partially blocked by prokaryotic Dam/Dcm methylation: {[b['enzyme'] + ' at ' + str(b['position_0based']) for b in blocked]}. Enzyme will fail to cut plasmid isolated from standard DH5a/TOP10 strains."
            if has_blockade
            else "No methylation overlaps detected on specified enzymes."
        ),
    }


def scan_inverted_repeats_and_hairpins(
    seq: str,
    min_repeat_len: int = 14,
    max_distance: int = 500,
) -> dict[str, Any]:
    """Scan sequence for long inverted repeats (>=14 bp) and extreme GC clusters that cause in vivo deletion or synthesis failure."""
    s = str(seq).upper()
    n = len(s)
    k = min_repeat_len
    if n < k * 2:
        return {
            "has_severe_secondary_structure": False,
            "has_inverted_repeats": False,
            "inverted_repeats": [],
            "extreme_gc_windows": [],
            "details": "Sequence too short for long inverted repeats.",
        }

    # 1. Extreme GC scan (>85% GC in 50 bp window)
    extreme_gc = []
    window = 50
    if n >= window:
        for i in range(0, n - window + 1, 10):
            win_seq = s[i:i+window]
            gc_count = win_seq.count("G") + win_seq.count("C")
            gc_pct = gc_count / window
            if gc_pct >= 0.85:
                extreme_gc.append({
                    "position_0based": i,
                    "gc_percent": round(gc_pct * 100, 1),
                    "sequence": win_seq,
                })

    # 2. Inverted repeat scan (k-mer hash)
    kmers: dict[str, list[int]] = {}
    limit = min(n - k + 1, 8000)
    for i in range(limit):
        sub = s[i:i+k]
        if "N" in sub:
            continue
        kmers.setdefault(sub, []).append(i)

    raw_matches = []
    seen_pairs = set()
    for i in range(limit):
        sub = s[i:i+k]
        rc = str(Seq(sub).reverse_complement())
        if rc in kmers:
            for j in kmers[rc]:
                if j >= i + k and (j - i) <= max_distance:
                    L = k
                    while i + L < n and j + L < n:
                        if str(Seq(s[i:i+L+1]).reverse_complement()) == s[j:j+L+1]:
                            L += 1
                        else:
                            break
                    if L >= min_repeat_len and (i, j) not in seen_pairs:
                        seen_pairs.add((i, j))
                        raw_matches.append({
                            "pos1": i,
                            "pos2": j,
                            "length": L,
                            "seq1": s[i:i+L],
                            "seq2": s[j:j+L],
                        })

    # Filter sub-matches
    filtered = []
    for r in sorted(raw_matches, key=lambda x: -x["length"]):
        p1, p2, l = r["pos1"], r["pos2"], r["length"]
        if not any(f["pos1"] <= p1 and p1 + l <= f["pos1"] + f["length"] and f["pos2"] <= p2 and p2 + l <= f["pos2"] + f["length"] for f in filtered):
            filtered.append(r)

    has_repeats = len(filtered) > 0
    has_gc = len(extreme_gc) > 0
    has_severe = has_repeats or has_gc

    details = []
    if has_repeats:
        details.append(f"Detected {len(filtered)} long inverted repeat(s) (>= {min_repeat_len} bp, max length {filtered[0]['length']} bp). Stalls E. coli replication fork, triggers SbcCD spontaneous deletion, and causes gene synthesis vendor rejection.")
    if has_gc:
        details.append(f"Detected {len(extreme_gc)} extreme GC cluster(s) (>= 85% in 50 bp window).")

    return {
        "has_severe_secondary_structure": has_severe,
        "has_inverted_repeats": has_repeats,
        "inverted_repeats": filtered[:5],
        "extreme_gc_windows": extreme_gc[:3],
        "details": "; ".join(details) if details else "No severe inverted repeats or extreme GC clusters detected.",
    }


def quick_biological_sanity_check(
    record_or_seq: SeqRecord | str,
    cds_start_offset: int = 0,
    cloning_enzymes: list[str] | None = None,
    crispr_grna_seq: str = "",
    check_u6_termination: bool = False,
    primers: list[str] | tuple[str, str] | None = None,
    topology: str = "linear",
    check_secondary_structure: bool = False,
    is_cds: bool = True,
    expected_orientation: str | None = None,
) -> dict[str, Any]:
    """Lightweight objective factual scan to assist the agent in catching obvious biological glitches.

    Reports purely objective numbers and facts without heavy policy blocking:
    - BIO-01: Reading frame & premature stop codons (applicable when is_cds=True)
    - BIO-02: Terminal stop codon presence (applicable when is_cds=True)
    - BIO-03: Internal restriction site conflicts
    - BIO-05: CRISPR donor in vivo recleavage risk
    - BIO-06: RNA Pol III (U6) poly-T transcription abort
    - BIO-07: PCR primer 3' catastrophic primer-dimers
    - BIO-08: Circular plasmid replicon & selectable marker presence
    - BIO-09: Host Dam/Dcm methylation restriction cut blockade
    - BIO-10: Extreme long inverted repeats and synthesis complexity
    """
    if isinstance(record_or_seq, SeqRecord):
        seq_str = str(record_or_seq.seq).upper()
        rec_top = str(record_or_seq.annotations.get("topology", topology)).lower()
    else:
        seq_str = str(record_or_seq).upper()
        rec_top = topology.lower()

    # 1. Reading Frame & Stop Codons (BIO-01 & BIO-02)
    # Principled Molecular Model:
    # A) If record_or_seq has annotated CDS features (e.g. recombinant plasmid):
    #    Every individual annotated CDS must be verified for reading frame,
    #    absence of internal premature stops, and proper terminal stop codon.
    # B) If no annotated CDS features are present:
    #    Evaluate the sequence as a single CDS if is_cds is True.
    cds_features = []
    if isinstance(record_or_seq, SeqRecord):
        cds_features = [
            f for f in getattr(record_or_seq, "features", [])
            if str(f.type).lower() in ("cds", "gene")
        ]

    # If circular and no CDS features are annotated, do not treat whole plasmid as a single CDS
    if rec_top == "circular" and not cds_features:
        is_cds = False

    annotated_cds_audits = []
    rf_result = None
    if cds_features:
        for f in cds_features:
            s0 = int(f.location.start)
            e0 = int(f.location.end)
            strand = int(f.location.strand or 1)
            cds_dna = str(f.extract(record_or_seq.seq)).upper()
            name = f.qualifiers.get("label", f.qualifiers.get("gene", [f.type]))[0]

            rf = check_reading_frame(cds_dna, start_offset=0)
            annotated_cds_audits.append({
                "name": name,
                "interval_0based": [s0, e0],
                "strand": strand,
                "length_bp": len(cds_dna),
                "is_multiple_of_three": rf["is_multiple_of_three"],
                "has_premature_stop": rf["has_premature_stop"],
                "premature_stop_positions": rf["premature_stop_positions"],
                "terminal_stop": rf["terminal_stop"],
            })
    elif is_cds:
        rf_result = check_reading_frame(seq_str, start_offset=cds_start_offset)

    # 2. Restriction Enzyme Conflicts (BIO-03)
    enzyme_conflicts = []
    if cloning_enzymes:
        res_sites = find_restriction_sites(seq_str, enzymes=cloning_enzymes)
        for enz_name, details in res_sites.get("enzymes", {}).items():
            if details["cut_count"] > 0:
                enzyme_conflicts.append({
                    "enzyme": enz_name,
                    "internal_cut_count": details["cut_count"],
                    "cuts": details["cuts"],
                })

    # 3. CRISPR Recleavage Check (BIO-05)
    crispr_recleavage = scan_crispr_recleavage_risk(
        donor_seq=seq_str,
        grna_seq=crispr_grna_seq,
    ) if crispr_grna_seq else None

    # 4. U6 Pol III Termination Check (BIO-06)
    u6_check = None
    if check_u6_termination:
        u6_check = scan_u6_pol3_termination(seq_str)
    elif crispr_grna_seq:
        u6_check = scan_u6_pol3_termination(crispr_grna_seq)

    # 5. PCR Primer Dimers (BIO-07)
    primer_dimer_res = None
    if primers and len(primers) >= 2:
        p_check = check_primer_dimers(primers[0], primers[1])
        primer_dimer_res = {
            "high_dimer_risk": p_check["high_dimer_risk"],
            "max_3prime_complementarity": p_check["max_3prime_complementarity"],
            "analysis": p_check,
        }

    # 6. Plasmid Maintenance Elements (BIO-08)
    maint_check = scan_plasmid_maintenance_elements(record_or_seq, topology=rec_top)

    # 7. Dam/Dcm Methylation Cut Blockade (BIO-09)
    meth_check = scan_methylation_blockade(record_or_seq, cloning_enzymes=cloning_enzymes) if cloning_enzymes else None

    # 8. Secondary Structure / Inverted Repeats (BIO-10)
    sec_struct_check = scan_inverted_repeats_and_hairpins(seq_str) if check_secondary_structure else None

    # Summary of objective issues found with severity tiers: CRITICAL vs WARNING
    issues_found = []
    critical_issues = []
    warnings_list = []

    if annotated_cds_audits:
        for audit in annotated_cds_audits:
            name = audit["name"]
            coords = f"{audit['interval_0based'][0]}..{audit['interval_0based'][1]}"
            if not audit["is_multiple_of_three"]:
                msg = f"BIO-01: Annotated CDS '{name}' ({coords}) length {audit['length_bp']} bp is not a multiple of 3 (frameshift)."
                issues_found.append(msg)
                critical_issues.append({"code": "BIO-01-FRAMESHIFT", "message": msg, "severity": "CRITICAL"})
            if audit["has_premature_stop"]:
                msg = f"BIO-01: Annotated CDS '{name}' ({coords}) contains {len(audit['premature_stop_positions'])} premature stop codon(s)."
                issues_found.append(msg)
                critical_issues.append({"code": "BIO-01-PREMATURE_STOP", "message": msg, "severity": "CRITICAL"})
            if not audit["terminal_stop"]:
                msg = f"BIO-02: Annotated CDS '{name}' ({coords}) does not end with a canonical stop codon (TAA/TAG/TGA)."
                issues_found.append(msg)
                warnings_list.append({"code": "BIO-02-TERMINAL_STOP_MISSING", "message": msg, "severity": "WARNING"})
    elif rf_result is not None:
        if not rf_result["is_multiple_of_three"]:
            msg = "BIO-01: CDS sequence length is not a multiple of 3 (frameshift)."
            issues_found.append(msg)
            critical_issues.append({"code": "BIO-01-FRAMESHIFT", "message": msg, "severity": "CRITICAL"})
        if rf_result["has_premature_stop"]:
            msg = f"BIO-01: Detected {len(rf_result['premature_stop_positions'])} premature stop codon(s)."
            issues_found.append(msg)
            critical_issues.append({"code": "BIO-01-PREMATURE_STOP", "message": msg, "severity": "CRITICAL"})
        if not rf_result["terminal_stop"]:
            msg = "BIO-02: No canonical terminal stop codon (TAA/TAG/TGA) at sequence 3' end."
            issues_found.append(msg)
            warnings_list.append({"code": "BIO-02-TERMINAL_STOP_MISSING", "message": msg, "severity": "WARNING"})

    if enzyme_conflicts:
        msg = f"BIO-03: Internal restriction cut conflict detected for: {[e['enzyme'] for e in enzyme_conflicts]}."
        issues_found.append(msg)
        critical_issues.append({"code": "BIO-03-INTERNAL_RESTRICTION_CONFLICT", "message": msg, "severity": "CRITICAL", "conflicts": enzyme_conflicts})

    if crispr_recleavage and crispr_recleavage["recleavage_risk"]:
        msg = "BIO-05: CRISPR donor contains intact PAM/Seed target; severe risk of in vivo Cas9 re-cleavage."
        issues_found.append(msg)
        critical_issues.append({"code": "BIO-05-CRISPR_RECLEAVAGE", "message": msg, "severity": "CRITICAL"})

    if u6_check and u6_check["has_poly_t_terminator"]:
        msg = "BIO-06: Consecutive TTTT detected; will trigger premature Pol III transcription termination in U6 promoter systems."
        issues_found.append(msg)
        warnings_list.append({"code": "BIO-06-POL3_TERMINATOR", "message": msg, "severity": "WARNING"})

    if primer_dimer_res and primer_dimer_res["high_dimer_risk"]:
        msg = f"BIO-07: Primers exhibit severe 3' complementarity ({primer_dimer_res['max_3prime_complementarity']} bp); high risk of primer-dimer amplification."
        issues_found.append(msg)
        warnings_list.append({"code": "BIO-07-PRIMER_DIMER", "message": msg, "severity": "WARNING"})

    if maint_check["applicable"] and maint_check["missing_essential_maintenance"]:
        msg = "BIO-08: Circular plasmid construct lacks both functional replication origin (ori) and antibiotic selection marker."
        issues_found.append(msg)
        critical_issues.append({"code": "BIO-08-REPLICON_MISSING", "message": msg, "severity": "CRITICAL"})

    if meth_check and meth_check["has_methylation_blockade"]:
        msg = f"BIO-09: Specified cloning enzyme(s) {meth_check['blocked_enzymes']} are completely/partially blocked by host Dam/Dcm methylation overlap."
        issues_found.append(msg)
        warnings_list.append({"code": "BIO-09-METHYLATION_BLOCKADE", "message": msg, "severity": "WARNING"})

    if sec_struct_check and sec_struct_check["has_severe_secondary_structure"]:
        msg = "BIO-10: Detected long inverted repeat (>=14 bp) or extreme GC cluster; high risk of in vivo spontaneous deletion or vendor synthesis rejection."
        issues_found.append(msg)
        warnings_list.append({"code": "BIO-10-SECONDARY_STRUCTURE", "message": msg, "severity": "WARNING"})

    if annotated_cds_audits:
        clean_for_expression = all(
            a["is_multiple_of_three"] and not a["has_premature_stop"] and a["terminal_stop"]
            for a in annotated_cds_audits
        ) and len(enzyme_conflicts) == 0
    elif rf_result is not None:
        clean_for_expression = (
            rf_result["is_multiple_of_three"]
            and not rf_result["has_premature_stop"]
            and rf_result["terminal_stop"]
            and len(enzyme_conflicts) == 0
        )
    else:
        clean_for_expression = len(enzyme_conflicts) == 0

    if annotated_cds_audits:
        is_m3 = all(a["is_multiple_of_three"] for a in annotated_cds_audits)
        has_stop = any(a["has_premature_stop"] for a in annotated_cds_audits)
        premature_stops = [pos for a in annotated_cds_audits for pos in a["premature_stop_positions"]]
        term_stop = all(a["terminal_stop"] for a in annotated_cds_audits)
        preview = f"Audited {len(annotated_cds_audits)} annotated CDS(s): {', '.join(a['name'] for a in annotated_cds_audits)}"
    elif rf_result is not None:
        is_m3 = rf_result["is_multiple_of_three"]
        has_stop = rf_result["has_premature_stop"]
        premature_stops = rf_result["premature_stop_positions"]
        term_stop = rf_result["terminal_stop"]
        preview = rf_result["translation"][:50] + ("..." if len(rf_result["translation"]) > 50 else "")
    else:
        is_m3 = True
        has_stop = False
        premature_stops = []
        term_stop = True
        preview = "Non-coding sequence"

    # Objective assessment of strand and orientation (BIO-04)
    has_corrupt_coords_or_strand = False
    observed_orientations = []
    if isinstance(record_or_seq, SeqRecord):
        for f in getattr(record_or_seq, "features", []):
            st = getattr(f.location, "strand", 1)
            if st not in (1, -1, 0, None):
                has_corrupt_coords_or_strand = True
            s0 = int(f.location.start)
            e0 = int(f.location.end)
            if s0 < 0 or (e0 < s0 and rec_top != "circular"):
                has_corrupt_coords_or_strand = True
            if st == 1:
                observed_orientations.append("forward")
            elif st == -1:
                observed_orientations.append("reverse")

    if has_corrupt_coords_or_strand:
        bio04_status = "FAIL"
        bio04_applicable = True
        bio04_details = "Corrupted coordinate or strand detected on sequence feature(s)"
    elif expected_orientation:
        bio04_applicable = True
        exp_clean = str(expected_orientation).strip().lower()
        if exp_clean in ("+1", "1", "+", "fwd", "forward"):
            exp_norm = "forward"
        elif exp_clean in ("-1", "-", "rev", "reverse"):
            exp_norm = "reverse"
        else:
            exp_norm = exp_clean

        if not observed_orientations:
            bio04_status = "UNKNOWN"
            bio04_details = f"Target orientation '{expected_orientation}' specified, but no annotated features exist to verify orientation"
        else:
            primary_orient = observed_orientations[0]
            if primary_orient == exp_norm:
                bio04_status = "PASS"
                bio04_details = f"Observed orientation '{primary_orient}' matches expected '{exp_norm}'"
            else:
                bio04_status = "FAIL"
                bio04_details = f"Orientation conflict: observed '{primary_orient}', expected '{exp_norm}'"
    else:
        bio04_status = "N/A"
        bio04_applicable = False
        bio04_details = "No target orientation constraint specified; feature coordinates syntactically valid" if observed_orientations else "No strand or feature annotations present to evaluate orientation"

    guardrail_status_table = {
        "BIO-01-FRAME": {
            "title": "Reading Frame & Premature Stops",
            "status": "PASS" if ((annotated_cds_audits and all(a["is_multiple_of_three"] and not a["has_premature_stop"] for a in annotated_cds_audits)) or (rf_result is not None and rf_result["is_multiple_of_three"] and not rf_result["has_premature_stop"])) else ("N/A" if not annotated_cds_audits and not is_cds else "FAIL"),
            "applicable": bool(annotated_cds_audits or is_cds),
            "details": f"{len(annotated_cds_audits)} annotated CDS(s) audited" if annotated_cds_audits else ("Direct CDS audited" if is_cds else "Non-coding sequence / whole plasmid"),
        },
        "BIO-02-STOP": {
            "title": "Stop Codon Integrity",
            "status": "PASS" if ((annotated_cds_audits and all(a["terminal_stop"] for a in annotated_cds_audits)) or (rf_result is not None and rf_result["terminal_stop"])) else ("N/A" if not annotated_cds_audits and not is_cds else "WARN"),
            "applicable": bool(annotated_cds_audits or is_cds),
            "details": "Canonical stop codon present" if ((annotated_cds_audits and all(a["terminal_stop"] for a in annotated_cds_audits)) or (rf_result and rf_result["terminal_stop"])) else ("N/A" if not annotated_cds_audits and not is_cds else "Terminal stop missing (warning: permitted for non-stop fusions/intermediate fragments)"),
        },
        "BIO-03-ENZYME": {
            "title": "Internal Restriction Cut Conflict",
            "status": ("PASS" if len(enzyme_conflicts) == 0 else "FAIL") if cloning_enzymes else "N/A",
            "applicable": bool(cloning_enzymes),
            "details": f"No internal cuts for {cloning_enzymes}" if (cloning_enzymes and len(enzyme_conflicts) == 0) else (f"Conflicts: {[e['enzyme'] for e in enzyme_conflicts]}" if enzyme_conflicts else "No restriction enzymes specified"),
        },
        "BIO-04-STRAND": {
            "title": "Strand & Orientation Consistency",
            "status": bio04_status,
            "applicable": bio04_applicable,
            "details": bio04_details,
        },
        "BIO-05-RECLEAVAGE": {
            "title": "CRISPR In Vivo Recleavage Prevention",
            "status": ("FAIL" if crispr_recleavage and crispr_recleavage["recleavage_risk"] else "PASS") if crispr_grna_seq else "N/A",
            "applicable": bool(crispr_grna_seq),
            "details": crispr_recleavage.get("details", "N/A") if crispr_recleavage else "Not a CRISPR HDR donor design",
        },
        "BIO-06-POL3_TERMINATION": {
            "title": "RNA Pol III (U6) Poly-T Termination",
            "status": ("FAIL" if u6_check and u6_check["has_poly_t_terminator"] else "PASS") if (check_u6_termination or crispr_grna_seq) else "N/A",
            "applicable": bool(check_u6_termination or crispr_grna_seq),
            "details": u6_check.get("details", "N/A") if u6_check else "Not a U6 Pol III expression system",
        },
        "BIO-07-PRIMER_DIMER": {
            "title": "PCR Primer 3' Dimer Risk",
            "status": ("FAIL" if primer_dimer_res and primer_dimer_res["high_dimer_risk"] else "PASS") if (primers and len(primers) >= 2) else "N/A",
            "applicable": bool(primers and len(primers) >= 2),
            "details": "Primer dimers safe" if (primers and len(primers) >= 2 and not primer_dimer_res["high_dimer_risk"]) else ("High dimer risk" if primer_dimer_res and primer_dimer_res["high_dimer_risk"] else "No primer pairs specified"),
        },
        "BIO-08-REPLICON_MARKER": {
            "title": "Replicon & Selection Marker Presence",
            "status": ("FAIL" if maint_check.get("missing_essential_maintenance") else "PASS") if maint_check.get("applicable") else "N/A",
            "applicable": bool(maint_check.get("applicable")),
            "details": maint_check.get("details", "N/A"),
        },
        "BIO-09-METHYLATION": {
            "title": "Dam/Dcm Methylation Cut Blockade",
            "status": ("FAIL" if meth_check and meth_check.get("has_methylation_blockade") else "PASS") if cloning_enzymes else "N/A",
            "applicable": bool(cloning_enzymes),
            "details": meth_check.get("details", "N/A") if meth_check else "No restriction enzymes specified",
        },
        "BIO-10-HAIRPIN_REPEAT": {
            "title": "Extreme Inverted Repeats & Complexity",
            "status": ("FAIL" if sec_struct_check and sec_struct_check.get("has_severe_secondary_structure") else "PASS") if check_secondary_structure else "N/A",
            "applicable": bool(check_secondary_structure),
            "details": sec_struct_check.get("details", "N/A") if sec_struct_check else "Secondary structure screening not requested",
        },
    }

    failed_codes = [code for code, g in guardrail_status_table.items() if g["status"] == "FAIL"]
    unknown_codes = [code for code, g in guardrail_status_table.items() if g["status"] == "UNKNOWN"]
    blocking_codes = [code for code, g in guardrail_status_table.items() if g["status"] in ("FAIL", "UNKNOWN")]
    all_applicable_pass = len(blocking_codes) == 0
    all_clean = len(issues_found) == 0 and all_applicable_pass

    return {
        "sequence_length": len(seq_str),
        "is_multiple_of_three": is_m3,
        "has_premature_stop": has_stop,
        "premature_stop_positions": premature_stops,
        "terminal_stop_present": term_stop,
        "translation_preview": preview,
        "annotated_cds_audits": annotated_cds_audits,
        "internal_enzyme_conflicts": enzyme_conflicts,
        "crispr_recleavage": crispr_recleavage,
        "u6_pol3_termination": u6_check,
        "primer_dimer_audit": primer_dimer_res,
        "maintenance_elements": maint_check,
        "methylation_blockade": meth_check,
        "secondary_structure": sec_struct_check,
        "issues_found": issues_found,
        "critical_issues": critical_issues,
        "warnings": warnings_list,
        "has_critical_error": len(critical_issues) > 0,
        "all_clean": all_clean,
        "clean_for_expression": clean_for_expression,
        "guardrail_status_table": guardrail_status_table,
        "failed_codes": failed_codes,
        "unknown_codes": unknown_codes,
        "blocking_codes": blocking_codes,
        "all_applicable_pass": all_applicable_pass,
    }
