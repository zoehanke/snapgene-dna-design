# -*- coding: utf-8 -*-
"""Safe, versioned experience-rule registry used by the DNA design Agent.

Natural language is an input surface, never an executable rule language.  This
module accepts only a small declarative condition grammar, validates it, keeps
confirmed user rules in ``user_rules/rules.json`` and writes append-only event
files under ``user_rules/history/``.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import pathlib
import tempfile
import uuid


SCHEMA_VERSION = "1.0.0"
ALLOWED_TRIGGERS = {
    "assembly_feasibility",
    "before_protocol_recommendation",
    "before_pcr_plan",
    "before_validation_primer_design",
    "before_primer_design",
    "after_primer_design",
    "after_pcr_plan",
    "before_method_selection",
    "after_validation_plan",
    "before_culture_plan",
    "before_delivery",
}
ALLOWED_SCOPES = {"session", "project", "global", "builtin"}
ALLOWED_STATUSES = {
    "active", "disabled", "deleted", "pending", "invalid", "superseded",
}
ALLOWED_ACTIONS = {"ask", "warn", "warn_and_confirm", "block", "set_default"}
ALLOWED_OPERATORS = {"eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in", "exists"}
FORBIDDEN_EXECUTABLE_KEYS = {"check", "eval"}
KNOWN_FIELDS = {
    "method", "fragment_count", "internal_site_count",
    "min_overlap_length", "max_overlap_length", "min_overlap_gc",
    "max_overlap_gc", "max_fragment_length", "total_length",
    "any_primer_tm_outside_52_72", "any_primer_strong_structure",
    "primer.role", "primer.request_explicit", "primer.user_supplied",
    "primer.binding_length_min", "primer.binding_length_max",
    "primer.binding_gc_min", "primer.binding_gc_max",
    "primer.three_prime_last5_gc_max", "primer.max_homopolymer_length",
    "primer.tm_difference_c", "primer.dimer_detected",
    "primer.hairpin_detected", "primer.specificity_status",
    "primer.has_5p_nonbinding_tail", "primer.tail_binds_initial_template",
    "primer.tm_basis",
    "pcr.type", "pcr.amplicon_bp", "pcr.purpose",
    "pcr.product_downstream_use", "pcr.template_gc_percent",
    "pcr.previous_failure", "pcr.primer_final_concentration_um",
    "pcr.special_system", "pcr.template_type",
    "pcr.template_dam_methylated", "pcr.parental_template_removed",
    "pcr.direct_downstream_use", "pcr.additive_compatibility_confirmed",
    "protocol.polymerase_known", "protocol.template_type_known",
    "protocol.methylation_sensitive_enzyme", "protocol.host_strain_known",
    "validation.objective", "validation.colony_pcr_positive",
    "validation.evidence_level", "validation.uncut_control_planned",
    "validation.min_band_separation_percent",
    "validation.min_visible_fragment_bp", "validation.junction_count",
    "validation.junctions_covered", "validation.clone_count",
    "validation.special_region_verified",
    "sanger.provider_requirements_known",
    "assembly.insert_fragment_count", "assembly.product_or_kit_known",
    "assembly.overlap_outside_product_guidance",
    "assembly.min_fragment_length",
    "source.repository_record", "source.full_sequence_verified",
    "sequence.special_region_present",
    "sequence.instability_feature_present",
    "sequence.max_homopolymer_length",
    "culture.host_strain_known", "culture.temperature_known",
    "delivery.formal", "delivery.specificity_checked",
    "delivery.has_unverified_regions",
}

FIELD_LABELS = {
    "method": "组装方法",
    "fragment_count": "片段数量",
    "internal_site_count": "片段内部 Type IIS 位点数量",
    "min_overlap_length": "最短 overlap 长度",
    "max_overlap_length": "最长 overlap 长度",
    "min_overlap_gc": "最低 overlap GC",
    "max_overlap_gc": "最高 overlap GC",
    "max_fragment_length": "最大片段长度",
    "total_length": "构建体总长度",
    "any_primer_tm_outside_52_72": "是否存在超出 52–72 °C 的引物 Tm",
    "any_primer_strong_structure": "是否存在强引物二级结构",
    "primer.role": "引物用途",
    "primer.request_explicit": "用户是否明确要求设计引物",
    "primer.user_supplied": "用户是否已提供引物",
    "primer.binding_length_min": "最短引物结合区长度",
    "primer.binding_length_max": "最长引物结合区长度",
    "primer.binding_gc_min": "最低引物结合区 GC%",
    "primer.binding_gc_max": "最高引物结合区 GC%",
    "primer.three_prime_last5_gc_max": "引物 3' 末 5 nt 的最大 G/C 数",
    "primer.max_homopolymer_length": "引物最长同聚物长度",
    "primer.tm_difference_c": "引物对 Tm 差",
    "primer.dimer_detected": "是否检测到引物二聚体",
    "primer.hairpin_detected": "是否检测到引物发夹",
    "primer.specificity_status": "引物特异性检查状态",
    "primer.has_5p_nonbinding_tail": "是否含 5' 非模板结合尾",
    "primer.tail_binds_initial_template": "5' 尾是否与起始模板配对",
    "primer.tm_basis": "引物 Tm 计算区域",
    "pcr.type": "PCR 类型",
    "pcr.amplicon_bp": "预计扩增产物长度",
    "pcr.purpose": "PCR 用途",
    "pcr.product_downstream_use": "PCR 产物后续用途",
    "pcr.template_gc_percent": "PCR 模板 GC%",
    "pcr.previous_failure": "是否已有 PCR 失败记录",
    "pcr.primer_final_concentration_um": "单条引物终浓度",
    "pcr.special_system": "是否为简并/多重等特殊 PCR 体系",
    "pcr.template_type": "PCR 模板类型",
    "pcr.template_dam_methylated": "质粒模板是否为 dam+ 来源",
    "pcr.parental_template_removed": "母本质粒是否已充分去除",
    "pcr.direct_downstream_use": "PCR 产物是否直接用于组装或转化",
    "pcr.additive_compatibility_confirmed": "添加剂与聚合酶是否已核对",
    "protocol.polymerase_known": "是否已知聚合酶型号",
    "protocol.template_type_known": "是否已知模板类型",
    "protocol.methylation_sensitive_enzyme": "是否涉及甲基化敏感酶",
    "protocol.host_strain_known": "是否已知相关宿主菌株",
    "validation.objective": "验证目标",
    "validation.colony_pcr_positive": "菌落 PCR 是否为初筛阳性",
    "validation.evidence_level": "验证证据等级",
    "validation.uncut_control_planned": "是否计划未切对照",
    "validation.min_band_separation_percent": "最小条带差异百分比",
    "validation.min_visible_fragment_bp": "最小可见片段长度",
    "validation.junction_count": "组装接缝数量",
    "validation.junctions_covered": "接缝是否被验证覆盖",
    "validation.clone_count": "计划筛选的独立克隆数",
    "validation.special_region_verified": "特殊区域是否已针对性验证",
    "sanger.provider_requirements_known": "是否已知测序服务商要求",
    "assembly.insert_fragment_count": "插入片段数量",
    "assembly.product_or_kit_known": "是否已知组装产品/试剂盒",
    "assembly.overlap_outside_product_guidance": "overlap 是否超出产品建议",
    "assembly.min_fragment_length": "最短组装片段长度",
    "source.repository_record": "是否来自公共质粒库记录",
    "source.full_sequence_verified": "来源是否声明全序列验证",
    "sequence.special_region_present": "是否存在高 GC/重复/低质量区域",
    "sequence.instability_feature_present": "是否存在不稳定或重复元件",
    "sequence.max_homopolymer_length": "最长同聚物长度",
    "culture.host_strain_known": "是否已知培养宿主菌株",
    "culture.temperature_known": "是否已知培养温度",
    "delivery.formal": "是否正式交付",
    "delivery.specificity_checked": "正式交付前是否完成特异性检查",
    "delivery.has_unverified_regions": "交付物是否含未验证区域",
}
OPERATOR_LABELS = {
    "eq": "=", "neq": "!=", "gt": ">", "gte": ">=",
    "lt": "<", "lte": "<=", "in": "属于", "not_in": "不属于",
    "exists": "存在",
}
SCOPE_LABELS = {
    "session": "仅本次", "project": "当前项目",
    "global": "全局", "builtin": "系统可行性规则",
}
STATUS_LABELS = {
    "active": "启用", "disabled": "停用", "pending": "待确认",
    "deleted": "已删除", "invalid": "无效", "superseded": "已被新版本替代",
}
ACTION_LABELS = {
    "ask": "询问",
    "warn": "警告",
    "warn_and_confirm": "警告并询问",
    "block": "阻止",
    "set_default": "设置默认值",
}


class RuleValidationError(ValueError):
    """Raised when a candidate cannot become an executable rule."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("RULE_VALIDATION_FAILED: " + "; ".join(self.errors))


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def sha256_value(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest().upper()


def _get_field(context, field):
    if field in context:
        return context[field]
    node = context
    for part in field.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def validate_condition(condition, path="when"):
    errors = []
    if not isinstance(condition, dict):
        return ["%s must be an object" % path]
    groups = [key for key in ("all", "any", "not") if key in condition]
    if groups:
        if len(groups) != 1 or len(condition) != 1:
            return ["%s must contain exactly one of all/any/not" % path]
        key = groups[0]
        value = condition[key]
        if key == "not":
            return validate_condition(value, "%s.not" % path)
        if not isinstance(value, list) or not value:
            return ["%s.%s must be a non-empty list" % (path, key)]
        for index, child in enumerate(value):
            errors.extend(validate_condition(child, "%s.%s[%d]" % (path, key, index)))
        return errors
    required = {"field", "operator"}
    missing = sorted(required - set(condition))
    if missing:
        errors.append("%s missing %s" % (path, ",".join(missing)))
        return errors
    field = condition.get("field")
    operator = condition.get("operator")
    if field not in KNOWN_FIELDS:
        errors.append("%s unknown field: %s" % (path, field))
    if operator not in ALLOWED_OPERATORS:
        errors.append("%s unsupported operator: %s" % (path, operator))
    if operator != "exists" and "value" not in condition:
        errors.append("%s missing value" % path)
    if operator in ("gt", "gte", "lt", "lte") and \
            not isinstance(condition.get("value"), (int, float)):
        errors.append("%s comparison value must be numeric" % path)
    if operator in ("in", "not_in") and \
            not isinstance(condition.get("value"), list):
        errors.append("%s membership value must be a list" % path)
    unknown = set(condition) - {"field", "operator", "value"}
    if unknown:
        errors.append("%s unknown keys: %s" % (path, ",".join(sorted(unknown))))
    return errors


def condition_matches(condition, context):
    """Evaluate the declarative grammar without eval or executable strings."""
    errors = validate_condition(condition)
    if errors:
        raise RuleValidationError(errors)
    if "all" in condition:
        return all(condition_matches(item, context) for item in condition["all"])
    if "any" in condition:
        return any(condition_matches(item, context) for item in condition["any"])
    if "not" in condition:
        return not condition_matches(condition["not"], context)
    actual = _get_field(context, condition["field"])
    operator = condition["operator"]
    expected = condition.get("value")
    if operator == "exists":
        return (actual is not None) is bool(expected if "value" in condition else True)
    if actual is None:
        return False
    if operator == "eq":
        return actual == expected
    if operator == "neq":
        return actual != expected
    if operator == "gt":
        return actual > expected
    if operator == "gte":
        return actual >= expected
    if operator == "lt":
        return actual < expected
    if operator == "lte":
        return actual <= expected
    if operator == "in":
        return actual in expected
    if operator == "not_in":
        return actual not in expected
    return False


def _forbidden_executable_keys(value, path="rule"):
    """Reject executable-rule escape hatches at every nesting level.

    Rule metadata is data only.  In particular, accepting an ``eval`` or
    ``check`` key—even if this module never executes it—would make the public
    contract weaker than the documented non-executable rule format and would
    allow downstream consumers to accidentally interpret it as code.
    """
    errors = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_EXECUTABLE_KEYS:
                if key == "check":
                    errors.append(
                        "check expressions are not allowed; use structured "
                        "when conditions (%s.check)" % path)
                else:
                    errors.append(
                        "eval expressions are not allowed; use structured "
                        "when conditions (%s.eval)" % path)
            errors.extend(_forbidden_executable_keys(
                child, "%s.%s" % (path, key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_forbidden_executable_keys(
                child, "%s[%d]" % (path, index)))
    return errors


def validate_rule(rule, persistent=False):
    errors = []
    if not isinstance(rule, dict):
        return ["rule must be an object"]
    errors.extend(_forbidden_executable_keys(rule))
    for field in ("id", "name", "trigger", "scope", "when", "action", "source"):
        if field not in rule:
            errors.append("missing %s" % field)
    rule_id = rule.get("id")
    if not isinstance(rule_id, str) or not rule_id or any(
            char not in "abcdefghijklmnopqrstuvwxyz0123456789.-_" for char in rule_id):
        errors.append("id must use lowercase ASCII letters, digits, dot, dash or underscore")
    if rule.get("trigger") not in ALLOWED_TRIGGERS:
        errors.append("unsupported trigger: %s" % rule.get("trigger"))
    scope = rule.get("scope")
    if not isinstance(scope, dict) or scope.get("type") not in ALLOWED_SCOPES:
        errors.append("scope.type must be session/project/global/builtin")
    elif scope.get("type") == "project" and not scope.get("project_id"):
        errors.append("project scope requires project_id")
    elif persistent and scope.get("type") == "session":
        errors.append("session rules belong to the current DesignSpec and cannot be persisted")
    status = rule.get("status", "pending")
    if status not in ALLOWED_STATUSES:
        errors.append("unsupported status: %s" % status)
    version = rule.get("version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        errors.append("version must be a positive integer")
    errors.extend(validate_condition(rule.get("when"), "when"))
    action = rule.get("action")
    if not isinstance(action, dict) or action.get("type") not in ALLOWED_ACTIONS:
        errors.append("action.type must be ask/warn/warn_and_confirm/block/set_default")
    elif action.get("type") != "set_default" and not action.get("message"):
        errors.append("action.message is required")
    source = rule.get("source")
    if not isinstance(source, dict) or not source.get("type"):
        errors.append("source.type is required")
    return errors


def validated_rule(rule, persistent=False):
    result = copy.deepcopy(rule)
    errors = validate_rule(result, persistent=persistent)
    if errors:
        raise RuleValidationError(errors)
    result.setdefault("schema_version", SCHEMA_VERSION)
    result.setdefault("version", 1)
    result.setdefault("status", "pending")
    return result


def _format_value(value, field=None):
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, list):
        return "[" + "、".join(_format_value(item) for item in value) + "]"
    suffix = ""
    if field and field.endswith("_bp") or field in {
            "min_overlap_length", "max_overlap_length",
            "max_fragment_length", "total_length"}:
        suffix = " bp"
    return "%s%s" % (value, suffix)


def condition_to_text(condition):
    if "all" in condition:
        return " AND ".join("(%s)" % condition_to_text(item)
                            for item in condition["all"])
    if "any" in condition:
        return " OR ".join("(%s)" % condition_to_text(item)
                           for item in condition["any"])
    if "not" in condition:
        return "NOT (%s)" % condition_to_text(condition["not"])
    field = condition.get("field", "?")
    operator = condition.get("operator", "?")
    label = FIELD_LABELS.get(field, field)
    return "%s %s %s" % (
        label, OPERATOR_LABELS.get(operator, operator),
        _format_value(condition.get("value", True), field))


def rule_card(rule, index=None, validation="通过"):
    scope = rule.get("scope") or {}
    scope_text = SCOPE_LABELS.get(scope.get("type"), scope.get("type", "?"))
    if scope.get("type") == "project":
        scope_text += "（%s）" % scope.get("project_id")
    title = "[规则 %02d] %s" % (index, rule.get("name", "未命名")) \
        if index is not None else rule.get("name", "未命名")
    action = rule.get("action") or {}
    action_text = ACTION_LABELS.get(action.get("type"), action.get("type", "?"))
    if action.get("message"):
        action_text += "：" + str(action["message"])
    return "\n".join([
        title,
        "ID：%s" % rule.get("id", "?"),
        "状态：%s" % STATUS_LABELS.get(rule.get("status", "pending"), rule.get("status")),
        "范围：%s" % scope_text,
        "触发：%s" % rule.get("trigger", "?"),
        "条件：%s" % condition_to_text(rule.get("when") or {}),
        "动作：%s" % action_text,
        "来源：%s" % (rule.get("source") or {}).get("type", "?"),
        "版本：v%s｜更新于 %s" % (rule.get("version", 1), rule.get("updated_at", "未保存")),
        "校验：%s" % validation,
    ])


def _atomic_write_json(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".tmp",
            prefix=".%s-" % path.name, dir=str(path.parent), delete=False) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp_path = pathlib.Path(handle.name)
    temp_path.replace(path)


class ExperienceRuleStore:
    """Persistence for confirmed rules, pending candidates and history."""

    def __init__(self, directory):
        self.directory = pathlib.Path(directory)
        self.rules_path = self.directory / "rules.json"
        self.pending_path = self.directory / "pending.json"
        self.history_dir = self.directory / "history"

    @staticmethod
    def _empty(kind):
        return {"schema_version": SCHEMA_VERSION, kind: []}

    def _read(self, path, kind):
        if not path.exists():
            return self._empty(kind)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuleValidationError(["cannot read %s: %s" % (path, error)]) from error
        if not isinstance(data, dict) or not isinstance(data.get(kind), list):
            raise RuleValidationError(["%s must contain a %s list" % (path, kind)])
        return data

    def read_rules(self):
        return self._read(self.rules_path, "rules")

    def read_pending(self):
        return self._read(self.pending_path, "candidates")

    def ensure_preloaded(self, preloaded_rules):
        """Seed newly introduced editable presets without resurrecting deletions.

        ``preloaded_rule_ids`` records every preset ID already introduced to a
        store.  On an upgrade, only IDs absent from that ledger are seeded.
        Consequently a previously deleted or modified preset is preserved,
        while genuinely new presets become available to existing users.
        """
        data = self.read_rules()
        existing_ids = {item.get("id") for item in data["rules"]}
        introduced_ids = set(data.get("preloaded_rule_ids") or [])
        legacy_initialized = bool(data.get("preloaded_initialized"))
        timestamp = now_iso()
        seeded_ids = list(data.get("preloaded_rule_ids") or [])
        changed = not legacy_initialized
        for original in preloaded_rules or []:
            rule = copy.deepcopy(original)
            rule["scope"] = {"type": "global"}
            rule["status"] = "active"
            rule["version"] = int(rule.get("version", 1))
            source = copy.deepcopy(rule.get("source") or {})
            source["type"] = "preloaded"
            rule["source"] = source
            rule.setdefault("created_at", timestamp)
            rule.setdefault("updated_at", timestamp)
            errors = validate_rule(rule, persistent=True)
            if errors:
                raise RuleValidationError(
                    ["invalid preloaded rule %s: %s" %
                     (rule.get("id", "?"), "; ".join(errors))])
            if rule["id"] in introduced_ids:
                continue
            seeded_ids.append(rule["id"])
            introduced_ids.add(rule["id"])
            changed = True
            if rule["id"] not in existing_ids:
                rule["sha256"] = sha256_value(
                    {key: value for key, value in rule.items()
                     if key != "sha256"})
                data["rules"].append(rule)
        if changed:
            data["preloaded_initialized"] = True
            data["preloaded_rule_ids"] = seeded_ids
            _atomic_write_json(self.rules_path, data)
        return data

    def add_candidate(self, rule, questions=None):
        candidate_rule = copy.deepcopy(rule)
        candidate_rule["status"] = "pending"
        errors = validate_rule(candidate_rule, persistent=False)
        candidate = {
            "candidate_id": "candidate-" + uuid.uuid4().hex[:12],
            "status": "needs-clarification" if questions or errors else "awaiting-confirmation",
            "created_at": now_iso(),
            "questions": list(questions or []),
            "validation_errors": errors,
            "rule": candidate_rule,
            "preview": rule_card(candidate_rule,
                                 validation="待确认" if not errors else "无效：" + "; ".join(errors)),
        }
        data = self.read_pending()
        data["candidates"].append(candidate)
        _atomic_write_json(self.pending_path, data)
        return candidate

    def open_candidates(self):
        return [item for item in self.read_pending()["candidates"]
                if item.get("status") in ("awaiting-confirmation", "needs-clarification")]

    def resolve_candidate(self, candidate_id, answers):
        """Apply explicit clarification answers and revalidate a pending rule."""
        data = self.read_pending()
        candidate = next((item for item in data["candidates"]
                          if item.get("candidate_id") == candidate_id), None)
        if candidate is None or candidate.get("status") != "needs-clarification":
            raise RuleValidationError(["clarification candidate not found: %s" % candidate_id])
        rule = candidate["rule"]
        answered = set()
        if answers.get("scope"):
            rule["scope"] = copy.deepcopy(answers["scope"])
            answered.add("scope")
            if rule["scope"].get("type") == "project" and rule["scope"].get("project_id"):
                answered.add("project_id")
        if answers.get("project_id"):
            rule["scope"] = {"type": "project", "project_id": answers["project_id"]}
            answered.update(("scope", "project_id"))
        if answers.get("pcr.amplicon_bp") is not None:
            threshold = int(answers["pcr.amplicon_bp"])
            for condition in rule.get("when", {}).get("all", []):
                if condition.get("field") == "pcr.amplicon_bp":
                    condition["value"] = threshold
            rule["action"]["message"] = (
                "预计产物超过菌落/煮菌 PCR 的 %d bp 推荐值。显示实际长度并询问"
                "用户调整验证位点或确认继续。" % threshold)
            answered.add("pcr.amplicon_bp")
        candidate["questions"] = [item for item in candidate.get("questions", [])
                                  if item.get("field") not in answered]
        errors = validate_rule(rule, persistent=False)
        candidate["validation_errors"] = errors
        candidate["status"] = (
            "awaiting-confirmation" if not candidate["questions"] and not errors
            else "needs-clarification")
        candidate["preview"] = rule_card(
            rule, validation="待确认" if candidate["status"] == "awaiting-confirmation"
            else "待澄清")
        candidate["clarified_at"] = now_iso()
        _atomic_write_json(self.pending_path, data)
        return candidate

    def _history_event(self, operation, previous, current, confirmation):
        event = {
            "schema_version": SCHEMA_VERSION,
            "event_id": "rule-event-" + uuid.uuid4().hex[:12],
            "operation": operation,
            "at": now_iso(),
            "previous": previous,
            "current": current,
            "confirmation": confirmation,
        }
        self.history_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        _atomic_write_json(self.history_dir / (stamp + "-" + event["event_id"] + ".json"), event)
        return event

    def confirm(self, candidate_id, confirmation_text):
        if not str(confirmation_text or "").strip():
            raise RuleValidationError(["explicit confirmation text is required"])
        pending = self.read_pending()
        matches = [item for item in pending["candidates"]
                   if item.get("candidate_id") == candidate_id]
        if len(matches) != 1:
            raise RuleValidationError(["candidate not found: %s" % candidate_id])
        candidate = matches[0]
        if candidate.get("status") != "awaiting-confirmation":
            raise RuleValidationError(["candidate is not ready for confirmation"])
        if (candidate.get("rule", {}).get("scope") or {}).get("type") == "session":
            rule = validated_rule(candidate["rule"], persistent=False)
            rule["status"] = "active"
            rule["version"] = 1
            rule["updated_at"] = now_iso()
            rule["confirmation"] = {
                "text": str(confirmation_text), "at": rule["updated_at"],
                "source": "explicit-user-confirmation",
            }
            candidate["status"] = "confirmed-session"
            candidate["confirmed_at"] = rule["updated_at"]
            _atomic_write_json(self.pending_path, pending)
            return rule
        requested_status = candidate.get("rule", {}).pop("requested_status", None)
        rule = validated_rule(candidate["rule"], persistent=True)
        rules_data = self.read_rules()
        previous = next((item for item in rules_data["rules"]
                         if item.get("id") == rule["id"]), None)
        timestamp = now_iso()
        rule["version"] = int(previous.get("version", 0)) + 1 if previous else 1
        rule["status"] = requested_status or "active"
        rule["created_at"] = previous.get("created_at", timestamp) if previous else timestamp
        rule["updated_at"] = timestamp
        rule["confirmation"] = {
            "text": str(confirmation_text), "at": timestamp,
            "source": "explicit-user-confirmation",
        }
        rule["sha256"] = sha256_value({k: v for k, v in rule.items() if k != "sha256"})
        rules_data["rules"] = [item for item in rules_data["rules"]
                               if item.get("id") != rule["id"]] + [rule]
        _atomic_write_json(self.rules_path, rules_data)
        candidate["status"] = "confirmed"
        candidate["confirmed_at"] = timestamp
        candidate["confirmed_rule_version"] = rule["version"]
        _atomic_write_json(self.pending_path, pending)
        operation = candidate.get("operation") or (
            "create" if previous is None else "revise")
        self._history_event(operation,
                            previous, rule, rule["confirmation"])
        return rule

    def reject(self, candidate_id, reason):
        pending = self.read_pending()
        matches = [item for item in pending["candidates"]
                   if item.get("candidate_id") == candidate_id]
        if len(matches) != 1:
            raise RuleValidationError(["candidate not found: %s" % candidate_id])
        matches[0]["status"] = "rejected"
        matches[0]["rejected_at"] = now_iso()
        matches[0]["reason"] = str(reason or "user rejected")
        _atomic_write_json(self.pending_path, pending)
        return matches[0]

    def propose_status(self, rule_id, status):
        if status not in ("active", "disabled", "deleted"):
            raise RuleValidationError(
                ["status change must be active, disabled or deleted"])
        current = next((item for item in self.read_rules()["rules"]
                        if item.get("id") == rule_id), None)
        if current is None:
            raise RuleValidationError(["rule not found: %s" % rule_id])
        proposed = copy.deepcopy(current)
        proposed.pop("confirmation", None)
        proposed.pop("sha256", None)
        proposed["status"] = "pending"
        proposed["requested_status"] = status
        candidate = self.add_candidate(proposed)
        candidate["operation"] = {
            "active": "enable", "disabled": "disable", "deleted": "delete",
        }[status]
        data = self.read_pending()
        for item in data["candidates"]:
            if item["candidate_id"] == candidate["candidate_id"]:
                item.update(candidate)
        _atomic_write_json(self.pending_path, data)
        return candidate

    def confirm_status(self, candidate_id, confirmation_text):
        pending = self.read_pending()
        candidate = next((item for item in pending["candidates"]
                          if item.get("candidate_id") == candidate_id), None)
        if not candidate or candidate.get("operation") not in (
                "enable", "disable", "delete"):
            return self.confirm(candidate_id, confirmation_text)
        return self.confirm(candidate_id, confirmation_text)

    def historical_versions(self, rule_id):
        versions = {}
        if not self.history_dir.exists():
            return []
        for path in sorted(self.history_dir.glob("*.json")):
            try:
                event = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for key in ("previous", "current"):
                rule = event.get(key)
                if isinstance(rule, dict) and rule.get("id") == rule_id:
                    versions[int(rule.get("version", 0))] = rule
        return [versions[key] for key in sorted(versions)]

    def propose_rollback(self, rule_id, version):
        old = next((item for item in self.historical_versions(rule_id)
                    if int(item.get("version", 0)) == int(version)), None)
        if old is None:
            raise RuleValidationError(["historical version not found: %s v%s" % (rule_id, version)])
        proposed = copy.deepcopy(old)
        for key in ("version", "created_at", "updated_at", "confirmation", "sha256"):
            proposed.pop(key, None)
        proposed["status"] = "pending"
        candidate = self.add_candidate(proposed)
        candidate["operation"] = "rollback"
        candidate["rollback_from_version"] = int(version)
        data = self.read_pending()
        for item in data["candidates"]:
            if item["candidate_id"] == candidate["candidate_id"]:
                item.update(candidate)
        _atomic_write_json(self.pending_path, data)
        return candidate


def scope_applies(rule, project_id=None):
    scope = (rule.get("scope") or {}).get("type")
    if scope in ("builtin", "global", "session"):
        return True
    return scope == "project" and (rule.get("scope") or {}).get("project_id") == project_id


def merge_by_scope(rules, project_id=None):
    priority = {"builtin": 0, "global": 1, "project": 2, "session": 3}
    selected = {}
    for rule in rules:
        if rule.get("status", "active") != "active" or not scope_applies(rule, project_id):
            continue
        key = rule.get("id")
        rank = (priority.get((rule.get("scope") or {}).get("type"), -1),
                int(rule.get("version", 0)))
        if key not in selected or rank >= selected[key][0]:
            selected[key] = (rank, rule)
    return [selected[key][1] for key in sorted(selected)]


def evaluate_rules(rules, trigger, context, project_id=None):
    hits = []
    diagnostics = []
    applicable = [rule for rule in merge_by_scope(rules, project_id)
                  if rule.get("trigger") == trigger]
    for rule in applicable:
        errors = validate_rule(rule)
        if errors:
            diagnostics.append({"rule_id": rule.get("id"), "errors": errors})
            continue
        try:
            matched = condition_matches(rule["when"], context)
        except (RuleValidationError, TypeError, ValueError) as error:
            diagnostics.append({"rule_id": rule.get("id"), "errors": [str(error)]})
            continue
        if matched:
            hits.append({
                "rule_id": rule["id"],
                "name": rule["name"],
                "trigger": trigger,
                "action": copy.deepcopy(rule["action"]),
                "scope": copy.deepcopy(rule["scope"]),
                "source": copy.deepcopy(rule["source"]),
                "version": rule.get("version", 1),
            })
    return {"hits": hits, "diagnostics": diagnostics,
            "rules_evaluated": len(applicable)}
