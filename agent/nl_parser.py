# -*- coding: utf-8 -*-
"""agent/nl_parser.py - deterministic, provider-neutral request parser.

The parser may ONLY produce: a DesignSpec draft, missing information,
questions, assumptions and file-role candidates. It never emits a final
plasmid sequence. The interface is deliberately simple so a future LLM
provider can implement the same contract.
"""
from __future__ import annotations

import re

from design.spec import add_evidence, new_spec
from agent.clarification import collect_clarifications


def _lower(text):
    return str(text or "").lower()


def _has(text, *needles):
    low = _lower(text)
    return any(n in low for n in needles)


def _detect_host(text):
    low = _lower(text)
    if "酵母" in low or "saccharomyces" in low or "yeast" in low:
        return {"organism": "Saccharomyces cerevisiae",
                "evidence": "user-provided"}
    if "哺乳" in low or "mammalian" in low or "hek" in low or "cho" in low:
        return {"organism": "mammalian cells (user stated)",
                "evidence": "user-provided"}
    if "大肠" in low or "e. coli" in low or "ecoli" in low or "e.coli" in low:
        return {"organism": "Escherichia coli", "evidence": "user-provided"}
    return {}


def _detect_method(text):
    low = _lower(text)
    if _has(low, "golden gate", "goldengate", "bsai", "bsmbi", "type iis"):
        return "golden_gate"
    if _has(low, "gibson", "nebuilder", "neb hifi", "hifi"):
        return "gibson"
    if _has(low, "gateway lr", "gateway-lr"):
        return "gateway"
    if _has(low, "酶切连接", "digest-ligate", "digest ligate",
            "ecori", "bamhi", "hindiii", "xhoi"):
        return "digest_ligate"
    if _has(low, "定点突变", "点突变", "site-directed", "mutagen"):
        return "site_directed_mutagenesis_pcr"
    return None


def _detect_objective(text):
    low = _lower(text)
    if _has(low, "启动子换成", "启动子替换", "replace promoter",
            "swap promoter"):
        return "promoter-replacement", "promoter"
    if _has(low, "抗性", "resistance", "ampicillin", "kanamycin", "hygromycin"):
        return "resistance-replacement", "resistance"
    if _has(low, "融合标签", "fusion tag", "tag 融合", "ha tag", "his tag",
            "flag tag"):
        return "fusion-tag", "tag"
    if _has(low, "crispr hdr", "hdr donor", "同源修复供体"):
        return "crispr-hdr-donor", "donor"
    if _has(low, "gateway lr", "gateway-lr"):
        return "gateway-lr", "orf"
    if _has(low, "定点突变", "点突变", "site-directed", "mutagen"):
        return "point-mutation", "mutation-site"
    if _has(low, "gibson 插入", "gibson insert", "插入"):
        return "gibson-insert", "insert"
    if _has(low, "golden gate", "goldengate"):
        return "golden-gate", "fragment"
    if _has(low, "组装", "assemble", "build"):
        return "assembly", "fragment"
    return "assembly", "fragment"


def _file_role_candidates(text, file_summaries):
    roles = []
    low = _lower(text)
    ordinal_map = {
        "第一": 0, "第1": 0, "第一个": 0, "first": 0,
        "第二": 1, "第2": 1, "第二个": 1, "second": 1,
        "第三": 2, "第3": 2, "第三个": 2, "third": 2,
    }
    for key, index in ordinal_map.items():
        if key in low and index < len(file_summaries):
            roles.append({"role": "backbone" if index == 0 else
                          "insert-%d" % index,
                          "path": list(file_summaries.keys())[index],
                          "basis": "ordinal-reference",
                          "explicit": True})
            break
    if not roles and file_summaries:
        for path, summary in file_summaries.items():
            nm = _lower(summary.get("name") or "")
            if nm and nm in low:
                # Named reference in user text
                roles.append({
                    "role": "backbone" if ("骨架" in low or "backbone" in low or "载体" in low) else "insert",
                    "path": path,
                    "basis": "named-reference",
                    "explicit": True,
                })
    return roles


def parse_request(user_text, file_summaries, previous_spec=None,
                    mode="exploration"):
    """Parse one user request into a DesignSpec draft.

    ``file_summaries`` is a dict path -> summarize_file(path).
    ``previous_spec`` is used only to preserve spec_id lineage if revisions
    are requested later; parsing itself starts a fresh draft.
    """
    text = str(user_text or "")
    spec = new_spec(text, mode=mode)
    if previous_spec:
        spec["spec_id"] = previous_spec["spec_id"]
        spec["revision"] = int(previous_spec.get("revision", 1)) + 1

    obj_type, target_kind = _detect_objective(text)
    spec["objective"] = {
        "type": obj_type,
        "target_kind": target_kind,
        "text": text,
    }
    if obj_type == "point-mutation":
        match = re.search(r"(\d{1,7})\s*[:：]\s*([ACGTacgt])", text)
        if match:
            spec["objective"]["mutation"] = "%s:%s" % (
                match.group(1), match.group(2).upper())
            add_evidence(spec, "user-provided",
                         "explicit nucleotide mutation extracted from "
                         "request text",
                         mutation=spec["objective"]["mutation"])
    host = _detect_host(text)
    if host:
        spec["host"] = host
        add_evidence(spec, host.get("evidence", "user-provided"),
                     "host detected from request text", host=host)
    method = _detect_method(text)
    if method:
        spec["constraints"]["method"] = method
        add_evidence(spec, "user-provided",
                     "method detected from request text", method=method)

    roles = _file_role_candidates(text, file_summaries)
    file_summary_list = list(file_summaries.values())
    if roles:
        for role in roles:
            summary = file_summaries.get(role["path"]) or {}
            spec["objective"].setdefault("file_roles", []).append({
                "role": role["role"],
                "path": role["path"],
                "basis": role["basis"],
                "explicit": role["explicit"],
                "sha256": summary.get("sha256"),
            })

    # Multi-feature ambiguity is detected from file summaries, never guessed.
    ambiguous = []
    for summary in file_summaries.values():
        labels = [f["name"] for f in summary.get("features", [])
                  if f.get("name")]
        seen = set()
        for label in labels:
            if label in seen:
                ambiguous.append({"path": summary["path"],
                                  "feature_name": label})
            seen.add(label)
    if ambiguous:
        spec["missing_information"].append({
            "key": "target.feature_name",
            "reason": "duplicate feature labels: %s" % ambiguous,
        })
        spec["questions"].append({
            "question_id": "clarify-target-feature",
            "category": "must-ask",
            "question": "多个同名 feature，请选择坐标或唯一 identifier",
        })

    questions, defaults, derived = collect_clarifications(spec)
    missing = [{"key": item["field"], "reason": item["question"]}
               for item in questions]
    return {
        "spec": spec,
        "draft": spec,
        "questions": questions,
        "defaults": defaults,
        "derived_rule_ids": derived,
        "file_roles": roles,
        "missing_information": missing,
    }
