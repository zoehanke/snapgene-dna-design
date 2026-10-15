# -*- coding: utf-8 -*-
"""Natural-language surface for the strict experience-rule registry.

Only phrases that can be mapped without guessing are compiled locally.  An
embedding LLM may provide a richer structured candidate, but it must pass the
same validator before it can be confirmed and persisted.
"""
from __future__ import annotations

import copy
import json
import pathlib
import re

from rules.experience import (
    ExperienceRuleStore, RuleValidationError, evaluate_rules, now_iso,
    rule_card, sha256_value,
)


def _scope_from_text(text, project_id=None, explicit_scope=None):
    if explicit_scope:
        if explicit_scope == "project":
            return {"type": "project", "project_id": project_id}
        return {"type": explicit_scope}
    if any(token in text for token in ("仅本次", "这一次", "本次任务")):
        return {"type": "session"}
    if any(token in text for token in ("当前项目", "这个项目", "本项目")):
        return {"type": "project", "project_id": project_id}
    if any(token in text for token in ("以后", "默认", "所有任务", "每次", "一直")):
        return {"type": "global"}
    return None


def _length_bp(text):
    patterns = [
        r"(?:小于|不超过|控制在|上限(?:为|是)?|超过)\s*(\d+(?:\.\d+)?)\s*(kb|k|bp)?",
        r"(\d+(?:\.\d+)?)\s*(kb|k|bp)\s*(?:以内|以下|之内|上限)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = (match.group(2) or "bp").lower()
            if unit in ("kb", "k"):
                value *= 1000
            return int(round(value))
    return None


def _base_rule(rule_id, name, trigger, scope, when, action, original_text):
    return {
        "schema_version": "1.0.0",
        "id": rule_id,
        "name": name,
        "status": "pending",
        "scope": scope,
        "trigger": trigger,
        "when": when,
        "action": action,
        "source": {
            "type": "user-experience",
            "original_text": original_text,
        },
    }


def compile_candidate(user_text, project_id=None, scope=None):
    """Compile supported experience phrases or return clarification questions."""
    text = str(user_text or "").strip()
    selected_scope = _scope_from_text(text, project_id, scope)
    questions = []
    if selected_scope is None:
        questions.append({
            "field": "scope",
            "question": "这条经验只用于当前项目，还是用于以后所有任务？",
            "choices": ["当前项目", "以后所有任务"],
        })
    elif selected_scope.get("type") == "project" and not selected_scope.get("project_id"):
        questions.append({"field": "project_id", "question": "当前项目名称是什么？"})

    lower = text.lower()
    validation_primer = ("引物" in text and any(token in text for token in
                         ("验证", "鉴定")) and any(token in text for token in
                         ("询问", "先问", "确认", "不要擅自", "不能擅自", "已有")))
    colony_pcr = any(token in lower for token in
                     ("菌落pcr", "菌落 pcr", "煮菌pcr", "煮菌 pcr", "colony pcr"))
    if validation_primer:
        rule = _base_rule(
            "primer.validation.confirm-before-design",
            "验证引物设计前确认",
            "before_validation_primer_design",
            selected_scope or {"type": "global"},
            {"all": [
                {"field": "primer.role", "operator": "eq", "value": "validation"},
                {"field": "primer.request_explicit", "operator": "eq", "value": False},
            ]},
            {"type": "ask", "message":
             "请先询问用户是否已有验证引物；只有用户明确要求时才设计新引物。"},
            text)
        return {"status": "candidate", "rule": rule, "questions": questions}
    if colony_pcr:
        threshold = _length_bp(text)
        if threshold is None:
            questions.append({
                "field": "pcr.amplicon_bp",
                "question": "菌落/煮菌 PCR 的推荐产物长度上限是多少 bp？",
            })
            threshold = 1000
        permits_override = any(token in text for token in
                               ("可以超过", "允许超过", "略微超过", "提醒", "警告"))
        hard_block = any(token in text for token in ("禁止", "绝不允许", "硬门禁")) \
            and not permits_override
        action_type = "block" if hard_block else "warn_and_confirm"
        message = ("预计产物超过菌落/煮菌 PCR 的 %d bp 推荐值。显示实际长度并询问"
                   "用户调整验证位点或确认继续。" % threshold)
        if hard_block:
            message = "预计产物超过菌落/煮菌 PCR 的 %d bp 上限，阻止继续。" % threshold
        rule = _base_rule(
            "pcr.colony.preferred-amplicon-length",
            "菌落 PCR 推荐产物长度",
            "after_pcr_plan",
            selected_scope or {"type": "global"},
            {"all": [
                {"field": "pcr.type", "operator": "in",
                 "value": ["colony", "boiled_colony"]},
                {"field": "pcr.amplicon_bp", "operator": "gt",
                 "value": threshold},
            ]},
            {"type": action_type, "message": message}, text)
        return {"status": "candidate", "rule": rule, "questions": questions}
    return {
        "status": "needs-clarification",
        "rule": None,
        "questions": [{
            "field": "experience",
            "question": "请说明规则适用的实验场景、可计算的判断条件，以及触发后要询问、警告还是阻止。",
        }],
    }


def render_rule_list(rules, project_id=None, title="规则清单"):
    ordered = sorted(rules, key=lambda item: (
        {"active": 0, "disabled": 1, "pending": 2, "invalid": 3,
         "deleted": 4}.get(
            item.get("status"), 4),
        {"project": 0, "global": 1, "session": 2}.get(
            (item.get("scope") or {}).get("type"), 4),
        item.get("id", "")))
    counts = {key: sum(item.get("status") == key for item in ordered)
              for key in ("active", "disabled", "deleted", "pending", "invalid")}
    lines = [
        title,
        "当前项目：%s" % (project_id or "未指定"),
        "共 %d 条｜启用 %d｜停用 %d｜已删除 %d｜待确认 %d｜无效 %d" % (
            len(ordered), counts["active"], counts["disabled"],
            counts["deleted"], counts["pending"], counts["invalid"]),
        "",
    ]
    for index, rule in enumerate(ordered, 1):
        errors = []
        try:
            from rules.experience import validate_rule
            errors = validate_rule(rule)
        except Exception as error:  # pragma: no cover - defensive rendering
            errors = [str(error)]
        validation = "通过" if not errors else "无效：" + "; ".join(errors)
        lines.extend([rule_card(rule, index, validation), ""])
    if not ordered:
        lines.append("当前没有用户维护的规则。")
    return "\n".join(lines).rstrip() + "\n"


def export_rule_list(store, output_path, project_id=None, include_deleted=False):
    rules = _listing_rules(store, include_deleted=include_deleted)
    body = render_rule_list(rules, project_id)
    snapshot = {
        "project_id": project_id,
        "rules": rules,
        "generated_at": now_iso(),
    }
    header = (
        "<!-- schema_version: 1.0.0 -->\n"
        "<!-- snapshot_sha256: %s -->\n\n" % sha256_value(snapshot))
    path = pathlib.Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + body, encoding="utf-8")
    return {"status": "exported", "path": str(path),
            "snapshot_sha256": sha256_value(snapshot), "rule_count": len(rules)}


def _listing_rules(store, include_deleted=False):
    rules = [copy.deepcopy(rule) for rule in store.read_rules()["rules"]
             if include_deleted or rule.get("status") != "deleted"]
    for candidate in store.open_candidates():
        rule = copy.deepcopy(candidate.get("rule") or {})
        rule["status"] = "invalid" if candidate.get("validation_errors") else "pending"
        rule["candidate_id"] = candidate.get("candidate_id")
        rules.append(rule)
    return rules


def _matches_rule(rule, text):
    rule_id = str(rule.get("id", ""))
    if any(token in text for token in ("菌落", "煮菌")) and \
            rule_id == "pcr.colony.preferred-amplicon-length":
        return True
    if "引物" in text and any(token in text for token in ("验证", "鉴定")) and \
            rule_id == "primer.validation.confirm-before-design":
        return True
    hay = (str(rule.get("id", "")) + " " + str(rule.get("name", ""))).lower()
    tokens = [token for token in re.split(r"[\s，。,.]+", text.lower())
              if len(token) >= 2 and token not in {"规则", "这条", "那个", "一下"}]
    return any(token in hay for token in tokens)


def handle_rule_request(user_text, store, project_id=None, out_dir=None,
                        preloaded_rules=None, builtin_rules=None):
    """Handle a rule-management utterance; return ``None`` for design text."""
    text = str(user_text or "").strip()
    lower = text.lower()
    presets = preloaded_rules if preloaded_rules is not None else builtin_rules
    store.ensure_preloaded(presets or [])
    mentions_rule = "规则" in text or any(token in lower for token in
                    ("user_rules", "经验库", "经验规则"))
    known_experience = ("菌落" in text or "煮菌" in text or
                        (("验证" in text or "鉴定" in text) and "引物" in text))

    clarification_items = [item for item in store.open_candidates()
                           if item.get("status") == "needs-clarification"]
    if len(clarification_items) == 1:
        answers = {}
        if any(token in text for token in ("以后所有任务", "全局", "以后都", "默认")):
            answers["scope"] = {"type": "global"}
        elif any(token in text for token in ("当前项目", "这个项目", "本项目")):
            answers["scope"] = {"type": "project", "project_id": project_id}
        elif any(token in text for token in ("仅本次", "本次任务", "这一次")):
            answers["scope"] = {"type": "session"}
        number = _length_bp(text)
        if number is None:
            plain_number = re.fullmatch(r"\s*(\d+)\s*(?:bp)?\s*", text,
                                        flags=re.IGNORECASE)
            number = int(plain_number.group(1)) if plain_number else None
        if number is not None and any(
                question.get("field") == "pcr.amplicon_bp"
                for question in clarification_items[0].get("questions", [])):
            answers["pcr.amplicon_bp"] = number
        if answers:
            candidate = store.resolve_candidate(
                clarification_items[0]["candidate_id"], answers)
            return {"status": candidate["status"], "candidate": candidate,
                    "message": "候选规则已更新；请核对后回复“确认保存”。"}

    if mentions_rule and any(token in text for token in ("生成", "导出")) and \
            any(token in text for token in ("清单", "文件")):
        output = pathlib.Path(out_dir or ".") / "user-rules-list.md"
        return export_rule_list(store, output, project_id=project_id,
                                include_deleted=("已删除" in text or
                                                 "回收站" in text))
    if mentions_rule and any(token in text for token in ("查看", "列出", "清单", "有哪些")):
        return {"status": "listed", "markdown": render_rule_list(
            _listing_rules(store, include_deleted=("已删除" in text or
                                                    "回收站" in text)),
            project_id)}
    if any(token in text for token in (
            "确认保存", "确认这条", "保存这条规则", "确认删除",
            "确认停用", "确认恢复", "确认回滚")):
        open_items = [item for item in store.open_candidates()
                      if item.get("status") == "awaiting-confirmation"]
        if len(open_items) != 1:
            return {"status": "needs-selection",
                    "message": "待确认候选不是一条，请指定 candidate_id。",
                    "candidates": open_items}
        rule = store.confirm_status(open_items[0]["candidate_id"], text)
        return {"status": "confirmed", "rule": rule,
                "markdown": rule_card(rule, validation="通过")}
    if any(token in text for token in ("不保存", "取消这条规则", "拒绝保存")):
        open_items = store.open_candidates()
        if len(open_items) != 1:
            return {"status": "needs-selection", "candidates": open_items}
        return {"status": "rejected",
                "candidate": store.reject(open_items[0]["candidate_id"], text)}
    if mentions_rule and any(token in text for token in ("停用", "暂停")):
        matches = [rule for rule in store.read_rules()["rules"] if _matches_rule(rule, text)]
        if len(matches) != 1:
            return {"status": "needs-selection", "matches": matches}
        candidate = store.propose_status(matches[0]["id"], "disabled")
        return {"status": "awaiting-confirmation", "candidate": candidate}
    if mentions_rule and any(token in text for token in ("删除", "移除")):
        matches = [rule for rule in store.read_rules()["rules"]
                   if rule.get("status") != "deleted" and _matches_rule(rule, text)]
        if len(matches) != 1:
            return {"status": "needs-selection", "matches": matches}
        candidate = store.propose_status(matches[0]["id"], "deleted")
        return {"status": "awaiting-confirmation", "candidate": candidate,
                "message": "删除尚未执行；请核对后明确回复“确认删除”。"}
    if mentions_rule and any(token in text for token in ("启用", "恢复")):
        matches = [rule for rule in store.read_rules()["rules"] if _matches_rule(rule, text)]
        if len(matches) != 1:
            return {"status": "needs-selection", "matches": matches}
        candidate = store.propose_status(matches[0]["id"], "active")
        return {"status": "awaiting-confirmation", "candidate": candidate}
    if mentions_rule and "回滚" in text:
        version_match = re.search(r"v?(\d+)", lower)
        matches = [rule for rule in store.read_rules()["rules"] if _matches_rule(rule, text)]
        if len(matches) != 1 or not version_match:
            return {"status": "needs-selection", "matches": matches,
                    "message": "请指定一条规则和目标版本，例如“将菌落 PCR 规则回滚到 v1”。"}
        candidate = store.propose_rollback(matches[0]["id"], int(version_match.group(1)))
        return {"status": "awaiting-confirmation", "candidate": candidate}
    if mentions_rule or known_experience:
        compiled = compile_candidate(text, project_id=project_id)
        if compiled["rule"] is None:
            return compiled
        candidate = store.add_candidate(compiled["rule"], compiled["questions"])
        return {"status": candidate["status"], "candidate": candidate,
                "message": "候选规则尚未生效。请核对预览并明确回复“确认保存”。"}
    return None


def load_preloaded_experience(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))["rules"]


def load_builtin_experience(path):
    """Backward-compatible alias; presets are no longer immutable built-ins."""
    return load_preloaded_experience(path)


def evaluate_experience(trigger, context, store, project_id=None,
                        preloaded_rules=None, session_rules=None,
                        builtin_rules=None):
    presets = preloaded_rules if preloaded_rules is not None else builtin_rules
    store.ensure_preloaded(presets or [])
    rules = list(copy.deepcopy(store.read_rules()["rules"]))
    rules.extend(copy.deepcopy(session_rules or []))
    return evaluate_rules(rules, trigger, context, project_id=project_id)
