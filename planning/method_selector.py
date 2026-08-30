# -*- coding: utf-8 -*-
"""planning/method_selector.py - deterministic construction-method comparison.

The selector is a decision-support layer, not a wet-lab success predictor.
Scores sort candidate routes; they must never be presented as experimental
success probability.
"""
from __future__ import annotations

import copy
import json
import sys

METHODS = (
    "gibson",
    "golden_gate",
    "digest_ligate",
    "gateway",
    "site_directed_mutagenesis_pcr",
    "homologous_recombination",
    "synthesis_or_staged",
)

EVIDENCE = {
    "gibson": {
        "source": "Gibson et al. 2009, Nat Methods 6:343-345, "
                  "DOI 10.1038/nmeth.1318; NEB NEBuilder HiFi protocol",
        "score_base": 80,
    },
    "golden_gate": {
        "source": "Engler et al. 2008, PLoS One 3:e3647, "
                  "DOI 10.1371/journal.pone.0003647; NEB Golden Gate",
        "score_base": 80,
    },
    "digest_ligate": {
        "source": "Sambrook & Russell, Molecular Cloning; "
                  "NEB traditional cloning protocols",
        "score_base": 65,
    },
    "gateway": {
        "source": "Hartley et al. 2000, Genome Res 10:1788-1795, "
                  "DOI 10.1101/gr.143000; Thermo Fisher Gateway manual",
        "score_base": 70,
    },
    "site_directed_mutagenesis_pcr": {
        "source": "NEB Q5 Site-Directed Mutagenesis Kit E0554; "
                  "Kunkel 1985 PNAS 82:488-492",
        "score_base": 75,
    },
    "homologous_recombination": {
        "source": "Orr-Weaver et al. 1983, PNAS 80:4417-4421 "
                  "(yeast recombination); Gibson 2009 for in-vitro assembly",
        "score_base": 60,
    },
    "synthesis_or_staged": {
        "source": "IDT/gBlocks and commercial gene synthesis guidance; "
                  "staged assembly practice",
        "score_base": 40,
    },
}


def _candidate(method, status, score, advantages, risks, materials,
               hard_blockers, assumptions, source_evidence):
    return {
        "method": method,
        "status": status,
        "score": score,
        "advantages": advantages,
        "risks": risks,
        "required_materials": materials,
        "hard_blockers": hard_blockers,
        "assumptions": assumptions,
        "source_evidence": source_evidence,
    }


def select_methods(spec, context=None):
    """Compare every method and return candidates sorted by score desc.

    ``context`` may contain keys: fragment_count, internal_site_count,
    internal_type_iis_sites, unique_two_enzyme, entry_destination,
    point_mutation, high_gc, long_fragment, total_length, enzyme_available,
    primer_design_failed.
    Missing context values are treated as unknown and recorded as
    assumptions, never silently guessed.
    """
    ctx = copy.deepcopy(context or {})
    candidates = []

    # -------- gibson --------
    adv = ["无缝组装，无 scar；1-5 片段成熟", "不依赖内部限制位点",
           "NEBuilder HiFi 商业化试剂盒可直接对应"]
    risk = ["末端重叠 15-40 bp 必须正确；高 GC/长片段 PCR 仍可能困难"]
    blockers = []
    if ctx.get("fragment_count", 1) > 5:
        blockers.append("fragment-count-over-5")
    if ctx.get("total_length", 0) > 30000:
        blockers.append("total-length-over-30kb")
    score = EVIDENCE["gibson"]["score_base"] - 5 * (ctx.get("fragment_count", 1) - 1)
    if ctx.get("high_gc"):
        score -= 10
    candidates.append(_candidate(
        "gibson", "blocked" if blockers else "compatible", max(0, score),
        adv, risk, ["NEBuilder HiFi Master Mix 或 Gibson mix",
                    "高保真聚合酶 + 引物"], blockers,
        ["overlap 15-40 bp", "fragment_count <= 5"],
        [EVIDENCE["gibson"]["source"]]))

    # -------- golden_gate --------
    adv = ["模块化、可复用 parts、scar 可设计", "一锅多片段（<=8）"]
    risk = ["片段内部不能出现所选 Type IIS 位点", "末端 4bp overhang 必须唯一配对"]
    blockers = []
    if ctx.get("internal_type_iis_sites"):
        blockers.append("internal-type-iis-site")
    if ctx.get("type_iis_sites_available") is False:
        blockers.append("type-iis-sites-not-available")
    if ctx.get("fragment_count", 1) > 8:
        blockers.append("fragment-count-over-8")
    score = EVIDENCE["golden_gate"]["score_base"] - 4 * (ctx.get("fragment_count", 1) - 1)
    candidates.append(_candidate(
        "golden_gate", "blocked" if blockers else "compatible", max(0, score),
        adv, risk, ["BsaI 或 BsmBI", "T4 DNA ligase + buffer", "parts"],
        blockers,
        ["each source fragment has >=2 usable Type IIS sites",
         "no internal BsaI/BsmBI/Esp3I/BbsI site", "fragment_count <= 8"],
        [EVIDENCE["golden_gate"]["source"]]))

    # -------- digest_ligate --------
    adv = ["经典、便宜、易调试", "无 PCR 时可用"]
    risk = ["需要每片段唯一酶切位点且粘性端兼容", "阳性克隆比例低于无缝法"]
    blockers = []
    if not ctx.get("unique_two_enzyme"):
        blockers.append("no-unique-two-enzyme-pair")
    score = EVIDENCE["digest_ligate"]["score_base"]
    candidates.append(_candidate(
        "digest_ligate", "blocked" if blockers else "compatible", max(0, score),
        adv, risk, ["两种限制酶", "T4 ligase"], blockers,
        ["每个片段有且仅有一个对应识别位点", "末端兼容"],
        [EVIDENCE["digest_ligate"]["source"]]))

    # -------- gateway --------
    adv = ["Entry/DEST 标准化、高保真", "无需限制酶消化插入片段"]
    risk = ["需要 att 位点载体", "残留 attB scar"]
    blockers = []
    if not ctx.get("entry_destination"):
        blockers.append("no-gateway-entry-destination-pair")
    score = EVIDENCE["gateway"]["score_base"]
    candidates.append(_candidate(
        "gateway", "blocked" if blockers else "compatible", max(0, score),
        adv, risk, ["Gateway BP/LR Clonase", "pDONR/pDEST vectors"],
        blockers, ["entry 与 destination 均已具备 att 位点"],
        [EVIDENCE["gateway"]["source"]]))

    # -------- site-directed mutagenesis PCR --------
    adv = ["小改动无需重合成", "点突变/短 indel 标准路径"]
    risk = ["不适用于大片段重排"]
    blockers = []
    if not ctx.get("point_mutation"):
        blockers.append("not-a-point-mutation")
    score = EVIDENCE["site_directed_mutagenesis_pcr"]["score_base"]
    candidates.append(_candidate(
        "site_directed_mutagenesis_pcr",
        "blocked" if blockers else "compatible", max(0, score),
        adv, risk, ["Q5 SDM kit 或 KLD mix", "phosphorylated primers"],
        blockers, ["change is a point mutation/short indel"],
        [EVIDENCE["site_directed_mutagenesis_pcr"]["source"]]))

    # -------- homologous recombination --------
    adv = ["酵母/细胞中直接重组", "可处理较大片段"]
    risk = ["同源臂长度与转化条件依赖宿主"]
    blockers = []
    if not ctx.get("host_supports_recombination"):
        blockers.append("host-recombination-not-confirmed")
    score = EVIDENCE["homologous_recombination"]["score_base"]
    candidates.append(_candidate(
        "homologous_recombination", "blocked" if blockers else "compatible",
        max(0, score), adv, risk, ["感受态细胞/转化体系"],
        blockers, ["宿主具备同源重组能力"],
        [EVIDENCE["homologous_recombination"]["source"]]))

    # -------- synthesis_or_staged --------
    adv = ["可绕过模板与酶切限制", "复杂/过长构建体兜底"]
    risk = ["成本与周期", "合成后仍需克隆/组装"]
    blockers = []
    if ctx.get("total_length", 0) <= 30000 and not ctx.get("primer_design_failed"):
        blockers.append("not-required-for-current-input")
    score = EVIDENCE["synthesis_or_staged"]["score_base"]
    candidates.append(_candidate(
        "synthesis_or_staged", "blocked" if blockers else "compatible",
        max(0, score), adv, risk, ["合成供应商或分步构建物料"],
        blockers, ["用于大构建体/模板缺失/引物失败兜底"],
        [EVIDENCE["synthesis_or_staged"]["source"]]))

    candidates.sort(key=lambda item: item["score"], reverse=True)
    # A method explicitly stated by the user is a constraint, not a soft
    # ranking hint.  Silently replacing an explicit Gibson/Gateway request by
    # the highest-scoring Golden Gate route can change the biological workflow
    # (enzymes, scars, primers and controls).  Keep all alternatives visible,
    # but select only the requested route when it is compatible; otherwise
    # fail closed and return actionable blockers.
    requested = str((spec.get("constraints", {}) or {}).get("method") or "").strip().lower()
    aliases = {"gateway-lr": "gateway", "gateway_bp": "gateway"}
    requested = aliases.get(requested, requested)
    if requested:
        requested_candidate = next(
            (item for item in candidates if item["method"] == requested), None)
        if requested_candidate is None:
            return {
                "candidates": candidates,
                "selected": None,
                "excluded": candidates,
                "requested_method": requested,
                "requested_method_status": "unknown",
                "requested_method_blockers": ["unsupported-method"],
                "scoring_note": ("explicit method request was not recognized; "
                                 "no alternative was selected automatically"),
            }
        if requested_candidate["status"] != "compatible":
            return {
                "candidates": candidates,
                "selected": None,
                "excluded": candidates,
                "requested_method": requested,
                "requested_method_status": "blocked",
                "requested_method_blockers": list(
                    requested_candidate.get("hard_blockers") or []),
                "scoring_note": ("explicit method request is blocked by the "
                                 "observed constraints; choose an alternative "
                                 "only after user confirmation"),
            }
        return {
            "candidates": candidates,
            "selected": requested_candidate,
            "excluded": [item for item in candidates
                         if item is not requested_candidate],
            "requested_method": requested,
            "requested_method_status": "compatible",
            "requested_method_blockers": [],
            "scoring_note": ("explicit method request honored; score is a "
                             "deterministic ranking aid, not a success probability"),
        }
    return {
        "candidates": candidates,
        "selected": next((c for c in candidates if c["status"] == "compatible"),
                         None),
        "requested_method": None,
        "requested_method_status": None,
        "requested_method_blockers": [],
        "excluded": [c for c in candidates if c["status"] != "compatible"],
        "scoring_note": ("score is a deterministic ranking aid only; "
                         "not an experimental success probability"),
    }


def _context_from_spec(spec):
    target = spec.get("target", {}) or {}
    constraints = spec.get("constraints", {}) or {}
    derived = {item.get("field"): item.get("value")
               for item in spec.get("derived_facts", [])
               if isinstance(item.get("field"), str)}
    ctx = dict(derived)
    ctx.update(target.get("method_context", {}))
    ctx.update(constraints.get("method_context", {}))
    return ctx


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--context-json")
    args = parser.parse_args(argv)
    spec = json.loads(open(args.spec, encoding="utf-8").read())
    context = _context_from_spec(spec)
    if args.context_json:
        context.update(json.loads(open(args.context_json,
                                       encoding="utf-8").read()))
    print(json.dumps(select_methods(spec, context), ensure_ascii=False,
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
