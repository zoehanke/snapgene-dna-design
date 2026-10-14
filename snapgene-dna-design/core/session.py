# -*- coding: utf-8 -*-
"""ConstructionTaskSession: drafts, questions, answers, revisions.

This is the clarification loop for the new runtime.  A draft may be
incomplete; questions are derived from missing *biology* decisions only.
``auto-confirmed`` is rejected for every biology-bearing field and may
only be used for cosmetic defaults.
"""
from __future__ import annotations

import copy
import json
import uuid

from core.task import canonical_json, normalize_task, sha256_text

# question_id -> (task field path, parse function, biological: bool)
ANSWER_SPECS = {
    "file-role": ("sources", "file_role", True),
    "component-boundary": ("target.selection", "selection", True),
    "replace-interval": ("operation.replace.interval_0based",
                         "interval", True),
    "replacement-interval":
        ("operation.replace.replacement_interval_0based", "interval", True),
    "insert-boundary": ("operation.insert.boundary_0based", "int", True),
    "insert-interval": ("operation.insert.interval_0based", "interval", True),
    "mutation-spec": ("operation.mutations", "mutations", True),
    "host": ("host", "text", True),
    "method-preference": ("method_constraints.method", "text", True),
    "whole-record": ("approvals.whole_record", "approval", True),
    "near-whole-record": ("approvals.near_whole_record", "approval", True),
    "user-confirmed": ("approvals.user_confirmed_task", "approval", True),
    "sequence-upload": ("approvals.sequence_upload", "approval", True),
    "product-name": ("product.name", "text", False),
    "fusion-partner5": ("operation.partner5", "partner", True),
    "fusion-partner3": ("operation.partner3", "partner", True),
    "fusion-stop-policy": ("operation.stop_policy", "text", True),
    "fusion-linker": ("operation.linker", "linker", True),
    "donor-arms": ("operation.homology_arms", "arms", True),
    "integration-locus": ("operation.locus", "locus", True),
    "gateway-reaction": ("operation.reaction", "text", True),
    "gateway-stop-policy": ("operation.stop_policy", "text", True),
    "gateway-source-ids": ("operation", "source_ids", True),
    "restriction-spec": ("operation", "restriction_spec", True),
    "hierarchical-stages": ("operation.stages", "stages", True),
    "crispr-nuclease": ("operation.nuclease", "text", True),
    "crispr-target-interval": ("operation.target_interval_0based",
                               "interval", True),
    "crispr-donor": ("operation.donor_strategy", "donor_strategy", True),
}


def _set_dotted(obj, dotted, value):
    node = obj
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def _get_dotted(obj, dotted):
    node = obj
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _parse_interval(value):
    if isinstance(value, list) and len(value) == 2:
        return [int(value[0]), int(value[1])]
    if isinstance(value, str):
        text = value.strip()
        for sep in (":", "-", ".."):
            if sep in text:
                a, b = text.split(sep, 1)
                return [int(a.strip()), int(b.strip())]
    raise ValueError("invalid interval: %r" % (value,))


def _parse_selection(value):
    if isinstance(value, dict):
        selection = dict(value)
        selection.setdefault("resolution_status", "resolved")
        selection.setdefault(
            "resolution_evidence",
            [{"kind": "user-answer", "value": copy.deepcopy(value)}])
        return selection
    if isinstance(value, str) and value.startswith("feature:"):
        return {
            "kind": "feature",
            "feature_id": value[len("feature:"):],
            "resolution_status": "resolved",
            "resolution_evidence": [{"kind": "user-answer", "value": value}],
        }
    if isinstance(value, str) and value.startswith("interval:"):
        return {
            "kind": "interval",
            "interval_0based": _parse_interval(value[len("interval:"):]),
            "resolution_status": "resolved",
            "resolution_evidence": [{"kind": "user-answer", "value": value}],
        }
    if isinstance(value, (list, str)):
        return {
            "kind": "interval",
            "interval_0based": _parse_interval(value),
            "resolution_status": "resolved",
            "resolution_evidence": [{"kind": "user-answer", "value": value}],
        }
    raise ValueError("invalid selection answer")


def _parse_file_role(task, value):
    if not isinstance(value, dict) or "source_id" not in value or \
            "role" not in value:
        raise ValueError("file-role answer must be "
                         "{source_id, role}")
    for source in task["sources"]:
        if source["source_id"] == value["source_id"]:
            source["role"] = value["role"]
            return
    raise ValueError("unknown source_id in file-role answer")


def _parse_mutations(value):
    if not isinstance(value, list) or not value:
        raise ValueError("mutation-spec must be a non-empty list")
    out = []
    for item in value:
        if not all(k in item for k in
                   ("position_1based", "ref", "alt")):
            raise ValueError("each mutation needs position_1based/ref/alt")
        out.append({
            "position_1based": int(item["position_1based"]),
            "ref": str(item["ref"]).upper(),
            "alt": str(item["alt"]).upper(),
        })
    return out


def _parse_approval(value):
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, bool):
        return {"value": value, "evidence_layer": "user-provided"}
    raise ValueError("approval answer must be true/false or object")


def _parse_partner(value):
    if not isinstance(value, dict) or "source_id" not in value or \
            "interval_0based" not in value:
        raise ValueError("partner answer must be "
                         "{source_id, interval_0based, strand?}")
    out = {"source_id": value["source_id"],
           "interval_0based": _parse_interval(value["interval_0based"])}
    if value.get("strand") is not None:
        out["strand"] = int(value["strand"])
    return out


def _parse_arms(value):
    if not isinstance(value, dict):
        raise ValueError("arms answer must be {left_arm, right_arm}")
    return {"left_arm": str(value.get("left_arm") or ""),
            "right_arm": str(value.get("right_arm") or "")}


def _parse_locus(value):
    if not isinstance(value, dict) or "source_id" not in value or \
            "interval_0based" not in value:
        raise ValueError("locus answer must be "
                         "{source_id, interval_0based, strand?}")
    out = {"source_id": value["source_id"],
           "interval_0based": _parse_interval(value["interval_0based"])}
    if value.get("strand") is not None:
        out["strand"] = int(value["strand"])
    return out


def _parse_linker(value):
    if isinstance(value, dict):
        return {"dna": str(value.get("dna") or "")}
    if isinstance(value, str):
        return {"dna": value}
    raise ValueError("linker answer must be {dna: ...} or a DNA string")


def _parse_source_ids(task, value):
    if not isinstance(value, dict):
        raise ValueError("gateway source answer must be an object")
    return dict(value)


def _parse_restriction_spec(task, value):
    if not isinstance(value, dict):
        raise ValueError("restriction answer must be an object")
    if "vector_source_id" in value:
        _set_dotted(task, "operation.vector_source_id",
                    value["vector_source_id"])
    if "insert_source_id" in value:
        _set_dotted(task, "operation.insert_source_id",
                    value["insert_source_id"])
    if "vector_enzymes" in value:
        enzymes = value["vector_enzymes"]
        if isinstance(enzymes, str):
            enzymes = [enzymes]
        if not isinstance(enzymes, list):
            raise ValueError("vector_enzymes must be a list")
        _set_dotted(task, "operation.vector_enzymes", enzymes)
    if "insert_enzymes" in value:
        enzymes = value["insert_enzymes"]
        if isinstance(enzymes, str):
            enzymes = [enzymes]
        _set_dotted(task, "operation.insert_enzymes", enzymes)
    if "orientation" in value:
        _set_dotted(task, "operation.orientation", value["orientation"])
    return {}


def _parse_stages(value):
    if not isinstance(value, list) or not value:
        raise ValueError("stages answer must be a non-empty list")
    return value


def _parse_donor_strategy(value):
    if not isinstance(value, dict):
        raise ValueError("donor answer must be an object")
    out = {}
    if value.get("donor_source_id"):
        out["donor_source_id"] = value["donor_source_id"]
        out["replacement_interval_0based"] = _parse_interval(
            value["replacement_interval_0based"])
    if value.get("homology_arms"):
        out["homology_arms"] = _parse_arms(value["homology_arms"])
    return out


def _apply_answer(task, question_id, value):
    if question_id not in ANSWER_SPECS:
        raise KeyError("unknown question_id %r" % question_id)
    dotted, parser, biological = ANSWER_SPECS[question_id]
    if value == "auto-confirmed" and biological:
        raise ValueError(
            "auto-confirmed may not satisfy biological question %r"
            % question_id)
    if question_id == "file-role":
        _parse_file_role(task, value)
        return
    if parser == "restriction_spec":
        _parse_restriction_spec(task, value)
        return
    if parser == "selection":
        parsed = _parse_selection(value)
    elif parser == "interval":
        parsed = _parse_interval(value)
    elif parser == "mutations":
        parsed = _parse_mutations(value)
    elif parser == "approval":
        parsed = _parse_approval(value)
    elif parser == "int":
        parsed = int(value)
    elif parser == "partner":
        parsed = _parse_partner(value)
    elif parser == "arms":
        parsed = _parse_arms(value)
    elif parser == "locus":
        parsed = _parse_locus(value)
    elif parser == "linker":
        parsed = _parse_linker(value)
    elif parser == "source_ids":
        parsed = _parse_source_ids(task, value)
    elif parser == "restriction_spec":
        parsed = _parse_restriction_spec(task, value)
    elif parser == "stages":
        parsed = _parse_stages(value)
    elif parser == "donor_strategy":
        parsed = _parse_donor_strategy(value)
    else:
        parsed = value
    _set_dotted(task, dotted, parsed)


def _diff(a, b, prefix=""):
    changes = []
    for key in sorted(set(a) | set(b)):
        path = (prefix + "." + key) if prefix else key
        va, vb = a.get(key), b.get(key)
        if isinstance(va, dict) and isinstance(vb, dict):
            changes.extend(_diff(va, vb, path))
        elif va != vb:
            changes.append({"field": path, "before": va, "after": vb})
    return changes


def collect_task_questions(task):
    """Return questions for missing biological decisions, never guessing."""
    questions = []
    for source in task.get("sources", []):
        if not source.get("role"):
            questions.append({
                "question_id": "file-role",
                "category": "must-ask",
                "question": "文件 %s 承担什么角色（template/backbone/insert/"
                           "replacement/donor_component/entry/destination/"
                           "reference）？" % source["source_id"],
                "field": "sources.%s.role" % source["source_id"],
            })
            break  # one explicit question per source; asked sequentially
    kind = task.get("task_kind")
    if kind in ("component_amplification", "integration_donor"):
        selection = _get_dotted(task, "target.selection")
        if not selection or selection.get("resolution_status") != "resolved":
            questions.append({
                "question_id": "component-boundary",
                "category": "must-ask",
                "question": "目标组件的边界是什么？请给 "
                           "feature:名称 或 interval:start:end（0-based "
                           "半开区间）。",
                "field": "target.selection",
            })
    if kind == "plasmid_replace":
        replace = task.get("operation", {}).get("replace") or {}
        if "interval_0based" not in replace:
            questions.append({
                "question_id": "replace-interval",
                "category": "must-ask",
                "question": "backbone 上要替换的 0-based 半开区间是什么？",
                "field": "operation.replace.interval_0based",
            })
        if "replacement_interval_0based" not in replace:
            questions.append({
                "question_id": "replacement-interval",
                "category": "must-ask",
                "question": "replacement 来源中实际插入的区间是什么？",
                "field": "operation.replace.replacement_interval_0based",
            })
    if kind == "plasmid_insert":
        insert = task.get("operation", {}).get("insert") or {}
        if "boundary_0based" not in insert:
            questions.append({
                "question_id": "insert-boundary",
                "category": "must-ask",
                "question": "插入边界（0-based）是哪里？",
                "field": "operation.insert.boundary_0based",
            })
        if "interval_0based" not in insert:
            questions.append({
                "question_id": "insert-interval",
                "category": "must-ask",
                "question": "插入片段来源中的区间是什么？",
                "field": "operation.insert.interval_0based",
            })
    if kind == "point_mutation" and not (task.get("operation", {})
                                         .get("mutations")):
        questions.append({
            "question_id": "mutation-spec",
            "category": "must-ask",
            "question": "请给出显式突变 "
                       "[{position_1based, ref, alt}]；不接受默认突变。",
            "field": "operation.mutations",
        })
    op = task.get("operation", {})
    if kind == "protein_fusion":
        for key in ("partner5", "partner3"):
            if not (op.get(key) or {}).get("source_id"):
                questions.append({
                    "question_id": "fusion-%s" % key,
                    "category": "must-ask",
                    "question": "%s 融合伙伴是哪个 source 的哪个区间？"
                               "请给 {source_id, interval_0based, strand}。"
                               % key,
                    "field": "operation.%s" % key,
                })
        if op.get("stop_policy") not in ("stop", "no-stop"):
            questions.append({
                "question_id": "fusion-stop-policy",
                "category": "must-ask",
                "question": "融合产物是否需要终止密码子（stop/no-stop）？",
                "field": "operation.stop_policy",
            })
    if kind == "integration_donor":
        arms = op.get("homology_arms") or {}
        if not arms.get("left_arm") and not arms.get("right_arm"):
            questions.append({
                "question_id": "donor-arms",
                "category": "must-ask",
                "question": "供体同源臂序列是什么？请给 "
                           "{left_arm, right_arm}。",
                "field": "operation.homology_arms",
            })
        locus = op.get("locus") or {}
        if not locus.get("source_id") or not locus.get("interval_0based"):
            questions.append({
                "question_id": "integration-locus",
                "category": "must-ask",
                "question": "整合目标座位（locus）是哪个参考 source 的哪个"
                           "区间？请给 {source_id, interval_0based, strand}。",
                "field": "operation.locus",
            })
    if kind == "gateway_recombination":
        if op.get("reaction") not in ("bp", "lr"):
            questions.append({
                "question_id": "gateway-reaction",
                "category": "must-ask",
                "question": "Gateway 反应是 BP 还是 LR？",
                "field": "operation.reaction",
            })
        if op.get("stop_policy") not in ("stop", "no-stop"):
            questions.append({
                "question_id": "gateway-stop-policy",
                "category": "must-ask",
                "question": "表达盒终止密码子策略（stop/no-stop）？",
                "field": "operation.stop_policy",
            })
        if op.get("reaction") == "lr" and not (
                op.get("entry_source_id") and
                op.get("destination_source_id")):
            questions.append({
                "question_id": "gateway-source-ids",
                "category": "must-ask",
                "question": "LR 反应的 entry 与 destination 分别对应哪个 "
                           "source_id？请给 {entry_source_id, "
                           "destination_source_id}。",
                "field": "operation",
            })
        if op.get("reaction") == "bp" and not (
                op.get("entry_source_id") and
                op.get("donor_vector_source_id")):
            questions.append({
                "question_id": "gateway-source-ids",
                "category": "must-ask",
                "question": "BP 反应的 attB 插入片段与 attP 供体载体分别"
                           "对应哪个 source_id？请给 {entry_source_id, "
                           "donor_vector_source_id}。",
                "field": "operation",
            })
    if kind == "restriction_ligation":
        if not op.get("vector_source_id") or \
                not op.get("insert_source_id") or \
                not op.get("vector_enzymes") or \
                op.get("orientation") not in ("forward", "reverse"):
            questions.append({
                "question_id": "restriction-spec",
                "category": "must-ask",
                "question": "酶切连接规格：{vector_source_id, "
                           "insert_source_id, vector_enzymes[], "
                           "insert_enzymes[]?, orientation}。",
                "field": "operation",
            })
    if kind == "hierarchical_assembly" and not op.get("stages"):
        questions.append({
            "question_id": "hierarchical-stages",
            "category": "must-ask",
            "question": "分层组装 stages 列表：每级 "
                       "{stage_id, fragments[{source_id|stage_id, "
                       "interval_0based?, order, strand?}], overlap_length, "
                       "product_topology}。",
            "field": "operation.stages",
        })
    if kind == "crispr_editing":
        if not op.get("nuclease"):
            questions.append({
                "question_id": "crispr-nuclease",
                "category": "must-ask",
                "question": "使用哪种核酸酶（registry id，如 spcas9-wt）？",
                "field": "operation.nuclease",
            })
        if not op.get("target_interval_0based"):
            questions.append({
                "question_id": "crispr-target-interval",
                "category": "must-ask",
                "question": "目标编辑区间（reference 上 0-based 半开区间）"
                           "是什么？",
                "field": "operation.target_interval_0based",
            })
        if not op.get("donor_strategy"):
            questions.append({
                "question_id": "crispr-donor",
                "category": "must-ask",
                "question": "供体策略：{donor_source_id, "
                           "replacement_interval_0based, homology_arms}；"
                           "NHEJ 无供体请明确回答 {}。",
                "field": "operation.donor_strategy",
            })
    if not task.get("host"):
        questions.append({
            "question_id": "host",
            "category": "must-ask",
            "question": "最终宿主/表达体系是什么？",
            "field": "host",
        })
    approvals = task.get("approvals", {})
    if "sequence_upload" not in approvals:
        approvals["sequence_upload"] = {
            "value": False,
            "evidence_layer": "safe-default",
            "description": "uploads are denied by default",
        }
    if task.get("mode") == "formal" and \
            not (approvals.get("user_confirmed_task") or {}).get("value"):
        questions.append({
            "question_id": "user-confirmed",
            "category": "must-ask",
            "question": "是否确认按本 task 生成正式产物？",
            "field": "approvals.user_confirmed_task",
        })
    return questions


class ConstructionTaskSession:
    """Owns a task draft, its revisions, answers and question state."""

    def __init__(self, task, base_dir=None):
        self.base_dir = base_dir
        self.draft = normalize_task(copy.deepcopy(task))
        self.revisions = [copy.deepcopy(self.draft)]
        self.answers = []
        self.diffs = []

    @property
    def task(self):
        return self.draft

    @property
    def questions(self):
        return collect_task_questions(self.draft)

    def answer(self, question_id, value, description=None):
        previous = copy.deepcopy(self.draft)
        _apply_answer(self.draft, question_id, value)
        record = {
            "question_id": question_id,
            "value": value,
            "description": description,
            "revision_before": self.draft.get("revision", 1),
        }
        self.answers.append(record)
        self.diff_record(previous, "answer:%s" % question_id)
        return self.draft

    def diff_record(self, previous, reason):
        changes = _diff(previous, self.draft)
        if changes:
            self.draft["revision"] = int(self.draft.get("revision", 1)) + 1
            self.revisions.append(copy.deepcopy(previous))
            self.diffs.append({
                "reason": reason,
                "revision": self.draft["revision"],
                "changes": changes,
                "previous_task_sha256": sha256_text(
                    canonical_json(previous)),
                "task_sha256": sha256_text(canonical_json(self.draft)),
            })
        return self.diffs

    def apply_answers(self, answers):
        for question_id, value in answers.items():
            self.answer(question_id, value)
        return self.draft

    def to_record(self):
        return {
            "schema_version": "construction-task-session-v1",
            "task_id": self.draft.get("task_id"),
            "revision": self.draft.get("revision"),
            "questions": self.questions,
            "answers": self.answers,
            "diffs": self.diffs,
            "task": self.draft,
        }
