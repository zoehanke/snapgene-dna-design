# -*- coding: utf-8 -*-
"""agent/clarification.py - key-condition identification for DesignSpec.

Three classes only: must-ask, default-visible, derived. Rules live in
``references/clarification-rules.json``; this module is deterministic and
never asks for a value the pipeline can compute.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from design.spec import add_evidence, add_missing, add_question, set_field  # noqa: E402


def load_rules():
    path = ROOT / "references" / "clarification-rules.json"
    return json.loads(path.read_text(encoding="utf-8"))["rules"]


def _get(spec, field):
    node = spec
    for key in field.split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _condition_matches(spec, when):
    for field, predicate in (when or {}).items():
        value = _get(spec, field)
        if "exists" in predicate and predicate.get("exists") is True:
            continue
        if "in" in predicate:
            if value not in predicate["in"]:
                return False
    return True


def collect_clarifications(spec):
    """Return (questions, defaults, derived_applied)."""
    questions = []
    defaults = []
    derived_applied = []
    for rule in load_rules():
        if not _condition_matches(spec, rule.get("when", {})):
            continue
        field = rule["field"]
        if rule["category"] == "derived":
            # Program-computed facts are registered as derived evidence.
            add_evidence(spec, "computed",
                         rule["question"],
                         field=field, rule_id=rule["rule_id"])
            derived_applied.append(rule["rule_id"])
            continue
        if _get(spec, field) is not None:
            continue
        if rule["category"] == "must-ask":
            add_question(spec, rule["rule_id"], rule["question"],
                         category="must-ask")
            add_missing(spec, field, rule["question"])
            questions.append({"question_id": rule["rule_id"],
                              "category": "must-ask",
                              "question": rule["question"], "field": field})
        elif rule["category"] == "default-visible":
            default_value = rule.get("default_value")
            set_field(spec, field.split("."), default_value,
                      evidence_layer="assumption",
                      description="visible default: %s" % rule["question"])
            add_question(spec, rule["rule_id"], rule["question"],
                         category="default-visible")
            defaults.append({"question_id": rule["rule_id"],
                             "field": field, "default_value": default_value,
                             "question": rule["question"]})
    return questions, defaults, derived_applied


def must_ask_open(spec):
    return [q for q in spec.get("questions", [])
            if q.get("category") == "must-ask"]
