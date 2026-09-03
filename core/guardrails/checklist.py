# -*- coding: utf-8 -*-
"""core/guardrails/checklist.py - Foundational Biological Self-Audit Checklist.

Provides a standard molecular biology self-inspection checklist and lightweight
factual sanity audit to prevent LLM hallucinations (frameshifts, internal site blindness,
strand inversion, missing stops).
"""
from __future__ import annotations

import pathlib
from typing import Any

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

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
        "tool_to_use": "fuse_in_frame",
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
        "id": "BIO-05-EXPRESSION",
        "title": "表达调控盒完整性 (Expression Cassette Integrity)",
        "prompt": "启动子（Promoter）-> 核糖体结合位点/Kozak -> 起始密码子 ATG -> 编码区 CDS -> 终止密码子 -> 终止子（Terminator），顺序与逻辑是否完整闭环？",
        "tool_to_use": "inspect_dna",
    },
]


def get_biological_self_audit_checklist() -> list[dict[str, str]]:
    """Return the foundational biological checklist for LLM prompt injection."""
    return FOUNDATIONAL_CHECKLIST


def quick_biological_sanity_check(
    record_or_seq: SeqRecord | str,
    cds_start_offset: int = 0,
    cloning_enzymes: list[str] | None = None,
) -> dict[str, Any]:
    """Lightweight objective factual scan to assist the agent in catching obvious glitches.

    Reports purely objective numbers and facts without heavy policy blocking.
    """
    if isinstance(record_or_seq, SeqRecord):
        seq_str = str(record_or_seq.seq).upper()
    else:
        seq_str = str(record_or_seq).upper()

    rf_result = check_reading_frame(seq_str, start_offset=cds_start_offset)

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

    return {
        "sequence_length": len(seq_str),
        "is_multiple_of_three": rf_result["is_multiple_of_three"],
        "has_premature_stop": rf_result["has_premature_stop"],
        "premature_stop_positions": rf_result["premature_stop_positions"],
        "terminal_stop_present": rf_result["terminal_stop"],
        "translation_preview": rf_result["translation"][:50] + ("..." if len(rf_result["translation"]) > 50 else ""),
        "internal_enzyme_conflicts": enzyme_conflicts,
        "clean_for_expression": (
            rf_result["is_multiple_of_three"]
            and not rf_result["has_premature_stop"]
            and rf_result["terminal_stop"]
            and len(enzyme_conflicts) == 0
        ),
    }
