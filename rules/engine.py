# -*- coding: utf-8 -*-
"""M2 feasibility engine backed by the safe experience-rule grammar."""
import copy
import json
import pathlib

from provenance import source, read_version
from rules.experience import evaluate_rules, merge_by_scope, validate_rule


RULES_PATH = pathlib.Path(__file__).resolve().parent / "feasibility_rules.json"
USER_RULES_DIR = pathlib.Path(__file__).resolve().parents[1] / "user_rules"


def _read_rule_file(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
        raise ValueError("RULE_FILE_MUST_CONTAIN_RULES_LIST: %s" % path)
    return data["rules"]


def load_rules(user_rules_dir=None, project_id=None):
    """Load built-ins plus validated, applicable user feasibility rules."""
    rules = _read_rule_file(RULES_PATH)
    diagnostics = []
    user_dir = pathlib.Path(user_rules_dir or USER_RULES_DIR)
    if user_dir.exists():
        paths = []
        canonical = user_dir / "rules.json"
        if canonical.exists():
            paths.append(canonical)
        paths.extend(path for path in sorted(user_dir.glob("*.json"))
                     if path.name not in {"rules.json", "pending.json"})
        for user_file in paths:
            try:
                incoming = _read_rule_file(user_file)
            except (OSError, json.JSONDecodeError, ValueError) as error:
                diagnostics.append({"file": str(user_file), "error": str(error)})
                continue
            for rule in incoming:
                if not isinstance(rule, dict):
                    diagnostics.append({"file": str(user_file), "errors": ["rule must be an object"]})
                    continue
                if rule.get("trigger") != "assembly_feasibility":
                    continue
                try:
                    errors = validate_rule(rule, persistent=True)
                except (TypeError, ValueError) as error:
                    errors = ["invalid rule field: %s" % error]
                if errors:
                    diagnostics.append({"file": str(user_file),
                                        "rule_id": rule.get("id"),
                                        "errors": errors})
                    continue
                rules.append(copy.deepcopy(rule))
    return {"schema_version": "1.0.0",
            "rules": [rule for rule in merge_by_scope(rules, project_id)
                      if rule.get("trigger") == "assembly_feasibility"],
            "diagnostics": diagnostics}


def evaluate_plan(plan_context, user_rules_dir=None, project_id=None):
    """Return structured rule hits and a feasibility grade."""
    data = load_rules(user_rules_dir, project_id=project_id)
    evaluated = evaluate_rules(data["rules"], "assembly_feasibility",
                               plan_context, project_id=project_id)
    hits = []
    by_id = {rule["id"]: rule for rule in data["rules"]}
    for item in evaluated["hits"]:
        rule = by_id[item["rule_id"]]
        action_type = (rule.get("action") or {}).get("type")
        severity = "error" if action_type == "block" else "warn"
        hits.append({
            "rule_id": rule["id"],
            "constraint": rule.get("constraint", rule.get("name")),
            "severity": severity,
            "suggestion": (rule.get("action") or {}).get("message", ""),
            "source": (rule.get("source") or {}).get(
                "description", (rule.get("source") or {}).get("type", "")),
            "source_id": "rules:" + rule["id"],
        })
    errors = [hit for hit in hits if hit["severity"] == "error"]
    warnings = [hit for hit in hits if hit["severity"] == "warn"]
    diagnostics = data["diagnostics"] + evaluated["diagnostics"]
    grade = "low" if errors else "medium" if warnings else "unknown" if diagnostics else "high"
    return {
        "schema_version": "1.0.0", "grade": grade,
        "errors": errors, "warnings": warnings,
        "rules_evaluated": evaluated["rules_evaluated"],
        "diagnostics": diagnostics,
        "provenance": [source(
            "published-paper", "M2 feasibility rules",
            "experimental-feasibility-filter",
            version=read_version(), status="verified",
            verification={"method": "declarative-rule-evaluation",
                          "status": "verified"})],
    }
