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
    },
    {
        "id": "BIO-02-STOP",
        "title": "融合蛋白终止密码子策略 (Stop Codon in Fusion)",
        "prompt": "做 C 端融合或串联表达时，上游片段末尾的原有终止密码子（TAA/TAG/TGA）是否已被剔除？最终产物末尾是否保留了合法的终止密码子？",
        "tool_to_use": "fuse_in_frame / strip_terminal_codons",
    },
    {
        "id": "BIO-03-ENZYME",
        "title": "限制性酶切位点内部冲突 (Internal Restriction Sites)",
        "prompt": "计划使用的克隆内切酶，在目的插入片段内部是否已被破坏或不存在？若存在内部切点，是否已通过同义突变（silent mutation）沉默？",
        "tool_to_use": "find_restriction_sites / silent_mutation_remove_site",
    },
    {
        "id": "BIO-04-STRAND",
        "title": "正负链与方向核对 (Strand Orientation)",
        "prompt": "原质粒中目的基因位于正链（+1）还是负链（-1）？若为负链，拼接或扩增时是否已执行反向互补（reverse complement）？",
        "tool_to_use": "reverse_complement / inspect_dna",
    },
    {
        "id": "BIO-05-RECLEAVAGE",
        "title": "CRISPR 供体防体内二次切割 (CRISPR Recleavage Prevention)",
        "prompt": "HDR 修复供体模板（ssODN 或质粒）整合入基因组后，残留的 PAM（NGG）或 Seed 核心区是否已被同义突变破坏，杜绝游离 Cas9 再次复切？",
        "tool_to_use": "recipe_crispr_hdr_donor / get_codon_synonyms",
    },
    {
        "id": "BIO-06-POL3_TERMINATION",
        "title": "RNA Pol III (U6) 转录提前终止规避 (Pol III Terminator Avoidance)",
        "prompt": "在人源/鼠源 U6 pol III 启动子驱动的 sgRNA 编码区内，是否存在连续 4 个或更多个胸腺嘧啶（TTTT），导致转录提前终止？",
        "tool_to_use": "design_crispr_grna / quick_biological_sanity_check",
    },
    {
        "id": "BIO-07-PRIMER_DIMER",
        "title": "PCR 引物 3' 端严重二聚体拦截 (Primer 3' Dimer Check)",
        "prompt": "扩增或组装用引物的 3' 核心结合末端是否存在 $\\ge 4$ bp 连续互补，导致严重的二聚体竞争消耗聚合酶与试剂？",
        "tool_to_use": "check_primer_dimers / calc_primer_tm",
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

    # Extract seed (last 10 bp of 20-nt spacer)
    seed = g[-10:] if len(g) >= 10 else g
    # SpCas9 top strand search: [spacer/seed] + [N][GG]
    # SpCas9 bottom strand search: [CC][N] + [revcomp(spacer/seed)]
    seed_rc = str(Seq(seed).reverse_complement())
    g_rc = str(Seq(g).reverse_complement())

    # Regex for top strand: seed + .GG
    top_pattern = re.compile(rf"{re.escape(seed)}[ACGT]GG")
    # Regex for bottom strand: CC[ACGT] + seed_rc
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


def quick_biological_sanity_check(
    record_or_seq: SeqRecord | str,
    cds_start_offset: int = 0,
    cloning_enzymes: list[str] | None = None,
    crispr_grna_seq: str = "",
    check_u6_termination: bool = False,
    primers: list[str] | tuple[str, str] | None = None,
) -> dict[str, Any]:
    """Lightweight objective factual scan to assist the agent in catching obvious biological glitches.

    Reports purely objective numbers and facts without heavy policy blocking:
    - BIO-01: Reading frame & premature stop codons
    - BIO-02: Terminal stop codon presence
    - BIO-03: Internal restriction site conflicts
    - BIO-05: CRISPR donor in vivo recleavage risk
    - BIO-06: RNA Pol III (U6) poly-T transcription abort
    - BIO-07: PCR primer 3' catastrophic primer-dimers
    """
    if isinstance(record_or_seq, SeqRecord):
        seq_str = str(record_or_seq.seq).upper()
    else:
        seq_str = str(record_or_seq).upper()

    # 1. Reading Frame & Stop Codons (BIO-01 & BIO-02)
    rf_result = check_reading_frame(seq_str, start_offset=cds_start_offset)

    # 2. Restriction Enzyme Conflicts (BIO-03)
    enzyme_conflicts = []
    if cloning_enzymes:
        res_sites = find_restriction_sites(seq_str, enzymes=cloning_enzymes)
        for enz_name, details in res_sites["enzymes"].items():
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
    # Check on seq_str if check_u6_termination is True, or if crispr_grna_seq provided, check crispr_grna_seq
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

    # Summary of objective issues found
    issues_found = []
    if not rf_result["is_multiple_of_three"]:
        issues_found.append("BIO-01: CDS sequence length is not a multiple of 3 (frameshift).")
    if rf_result["has_premature_stop"]:
        issues_found.append(f"BIO-01: Detected {len(rf_result['premature_stop_positions'])} premature stop codon(s).")
    if not rf_result["terminal_stop"]:
        issues_found.append("BIO-02: No canonical terminal stop codon (TAA/TAG/TGA) at sequence 3' end.")
    if enzyme_conflicts:
        issues_found.append(f"BIO-03: Internal restriction cut conflict detected for: {[e['enzyme'] for e in enzyme_conflicts]}.")
    if crispr_recleavage and crispr_recleavage["recleavage_risk"]:
        issues_found.append("BIO-05: CRISPR donor contains intact PAM/Seed target; severe risk of in vivo Cas9 re-cleavage.")
    if u6_check and u6_check["has_poly_t_terminator"]:
        issues_found.append("BIO-06: Consecutive TTTT detected; will trigger premature Pol III transcription termination in U6 promoter systems.")
    if primer_dimer_res and primer_dimer_res["high_dimer_risk"]:
        issues_found.append(f"BIO-07: Primers exhibit severe 3' complementarity ({primer_dimer_res['max_3prime_complementarity']} bp); high risk of primer-dimer amplification.")

    clean_for_expression = (
        rf_result["is_multiple_of_three"]
        and not rf_result["has_premature_stop"]
        and rf_result["terminal_stop"]
        and len(enzyme_conflicts) == 0
    )

    all_clean = len(issues_found) == 0

    return {
        "sequence_length": len(seq_str),
        "is_multiple_of_three": rf_result["is_multiple_of_three"],
        "has_premature_stop": rf_result["has_premature_stop"],
        "premature_stop_positions": rf_result["premature_stop_positions"],
        "terminal_stop_present": rf_result["terminal_stop"],
        "translation_preview": rf_result["translation"][:50] + ("..." if len(rf_result["translation"]) > 50 else ""),
        "internal_enzyme_conflicts": enzyme_conflicts,
        "crispr_recleavage": crispr_recleavage,
        "u6_pol3_termination": u6_check,
        "primer_dimer_audit": primer_dimer_res,
        "issues_found": issues_found,
        "all_clean": all_clean,
        "clean_for_expression": clean_for_expression,
    }
