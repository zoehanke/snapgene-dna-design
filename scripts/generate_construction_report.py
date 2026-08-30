# -*- coding: utf-8 -*-
"""generate_construction_report.py - human-readable construction report.

Renders a run_construction_task result.json (or an explicit task /
validation pair) into a user-readable Markdown report with the fixed
verdict vocabulary from the v0.9.1 architecture spec:

    PUBLIC_RECORD_REPRODUCTION_PASS
    USER_SPECIFIED_CONSTRUCTION_PASS
    INTERNAL_FIXTURE_REGRESSION_PASS
    SYNTHETIC_COMPUTATIONAL_PASS
    EXPERIMENTAL_PREVIEW_ONLY
    PARTIAL
    BLOCKED_AS_DESIGNED
    FAIL

Evidence levels are never merged: the report records which evidence
level it was asked to describe.
"""
import argparse
import json
import pathlib
import sys

VERDICTS = (
    "PUBLIC_RECORD_REPRODUCTION_PASS",
    "USER_SPECIFIED_CONSTRUCTION_PASS",
    "INTERNAL_FIXTURE_REGRESSION_PASS",
    "SYNTHETIC_COMPUTATIONAL_PASS",
    "EXPERIMENTAL_PREVIEW_ONLY",
    "PARTIAL",
    "BLOCKED_AS_DESIGNED",
    "FAIL",
)

_BLOCKED_CODES = {
    "MUTATION_SPEC_REQUIRED", "REFERENCE_RESIDUE_MISMATCH",
    "CODON_CHOICE_REQUIRED", "REPLACE_INTERVAL_REQUIRED",
    "COMPONENT_BOUNDARY_REQUIRED", "WHOLE_TEMPLATE_SELECTED_FOR_COMPONENT",
    "NEAR_FULL_TEMPLATE_SELECTED_FOR_COMPONENT", "OVERLAP_MISMATCH",
    "OPERATION_TYPE_MISMATCH", "REPRODUCTION_BOUNDARY_REQUIRED",
    "INSERT_BOUNDARY_REQUIRED", "INSERT_INTERVAL_REQUIRED",
    "FUSION_STOP_POLICY_REQUIRED", "INTEGRATION_ARMS_REQUIRED",
    "INTEGRATION_LOCUS_REQUIRED", "GATEWAY_REACTION_REQUIRED",
    "GATEWAY_STOP_POLICY_REQUIRED", "RESTRICTION_SOURCES_REQUIRED",
    "RESTRICTION_ENZYMES_REQUIRED", "RESTRICTION_ORIENTATION_REQUIRED",
    "HIERARCHICAL_STAGES_REQUIRED", "CRISPR_NUCLEASE_REQUIRED",
    "CRISPR_TARGET_INTERVAL_REQUIRED", "TASK_KIND_NOT_REGISTERED",
    "TASK_KIND_NOT_IMPLEMENTED", "LEGACY_AGENT_FORMAL_DEPRECATED",
}


def _weakest(classes):
    rank = {"heuristic": 0, "synthetic-fixture": 1,
            "internal-fixture": 2, "user-provided": 3,
            "public-record": 4}
    return min(classes, key=lambda c: rank.get(c, 0)) if classes else \
        "heuristic"


def _circular_equal(a, b):
    if len(a) != len(b):
        return False
    double = a + a
    return any(double[i:i + len(a)] == b for i in range(len(a)))


def _derive_verdict(result, truth=None):
    status = result.get("status")
    task = result.get("task") or {}
    validation = result.get("validation") or {}
    classes = [s.get("evidence", {}).get("source_evidence_class")
               for s in task.get("sources", [])]
    weakest = _weakest([c for c in classes if c])
    if status in ("needs-clarification", "blocked"):
        error = (result.get("error") or {}).get("error_code")
        if error in _BLOCKED_CODES:
            return "BLOCKED_AS_DESIGNED"
        return "FAIL"
    if validation.get("overall") == "experimental-preview" or \
            status == "experimental-preview":
        return "EXPERIMENTAL_PREVIEW_ONLY"
    if status != "delivered":
        if validation.get("overall") == "verified":
            return "PARTIAL"
        return "FAIL"
    reproduction = any(
        p.get("kind") in ("public-record-reproduction", "reproduction")
        for p in task.get("provenance", []))
    if reproduction or truth is not None:
        if truth is None:
            return "PARTIAL"
        product_sequence = (result.get("execution_summary") or {}).get(
            "product_sequence")
        if not product_sequence:
            return "PARTIAL"
        match = _circular_equal(product_sequence.upper(),
                                truth.get("sequence", "").upper())
        if match:
            return "PUBLIC_RECORD_REPRODUCTION_PASS"
        return "PARTIAL"
    if weakest == "internal-fixture":
        return "INTERNAL_FIXTURE_REGRESSION_PASS"
    if weakest == "synthetic-fixture":
        return "SYNTHETIC_COMPUTATIONAL_PASS"
    return "USER_SPECIFIED_CONSTRUCTION_PASS"


def build_report(result, evidence_level="unknown", truth=None):
    task = result.get("task") or {}
    validation = result.get("validation") or {}
    plan_summary = result.get("plan_summary") or {}
    session = result.get("session") or {}
    verdict = _derive_verdict(result, truth=truth)
    sources = []
    for source in task.get("sources", []):
        sources.append({
            "source_id": source.get("source_id"),
            "role": source.get("role"),
            "evidence_class": source.get("evidence", {}).get(
                "source_evidence_class"),
            "accession": source.get("evidence", {}).get("accession"),
            "version": source.get("evidence", {}).get("version"),
            "sha256": source.get("sha256"),
            "topology": source.get("topology"),
            "annotation_status": source.get("annotation_status"),
        })
    delivery = result.get("delivery") or {}
    manifest = {}
    if delivery and delivery.get("directory"):
        manifest_path = pathlib.Path(delivery["directory"]) / \
            "DELIVERY-MANIFEST.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = {
        "schema_version": "construction-report-v1",
        "evidence_level": evidence_level,
        "verdict": verdict,
        "status": result.get("status"),
        "task": {
            "task_id": task.get("task_id"),
            "revision": task.get("revision"),
            "task_kind": task.get("task_kind"),
            "mode": task.get("mode"),
            "raw_request": task.get("raw_request"),
            "host": task.get("host"),
        },
        "sources": sources,
        "method_maturity": plan_summary.get("method_maturity"),
        "validation": {
            "overall": validation.get("overall"),
            "artifact_valid": validation.get("artifact_valid"),
            "computation_valid": validation.get("computation_valid"),
            "goal_valid": validation.get("goal_valid"),
            "error_codes": validation.get("error_codes"),
        },
        "steps": plan_summary.get("steps"),
        "expected_length": plan_summary.get("expected_length"),
        "topology": plan_summary.get("topology"),
        "delivery": {
            "directory": delivery.get("directory"),
            "files": delivery.get("files"),
            "manifest_artifact_class": manifest.get("artifact_class"),
            "manifest_evidence": manifest.get("evidence"),
        },
        "clarification": {
            "questions": result.get("questions") or [],
            "answers": session.get("answers") or [],
            "revision": session.get("revision"),
        },
        "assumptions": task.get("assumptions") or [],
    }
    return report


def render_markdown(report):
    lines = []
    verdict = report["verdict"]
    lines.append("# 构建报告")
    lines.append("")
    lines.append("**Verdict: %s**" % verdict)
    lines.append("")
    lines.append("证据等级（本报告口径）：%s" % report["evidence_level"])
    lines.append("")
    task = report["task"]
    lines.append("## 目标")
    lines.append("- task_id: %s (revision %s)" % (task["task_id"],
                                                 task["revision"]))
    lines.append("- task_kind: %s" % task["task_kind"])
    lines.append("- mode: %s" % task["mode"])
    lines.append("- host: %s" % (task["host"] or "未指定"))
    if task["raw_request"]:
        lines.append("- 需求原文: %s" % str(task["raw_request"])[:500])
    lines.append("")
    lines.append("## 来源与证据等级")
    for source in report["sources"]:
        lines.append("- %s (role=%s, evidence=%s, sha256=%s)"
                    % (source["source_id"], source["role"],
                       source["evidence_class"],
                       (source["sha256"] or "")[:12]))
    lines.append("")
    lines.append("## 方法与成熟度")
    lines.append("- method_maturity: %s" % report["method_maturity"])
    for step in report["steps"] or []:
        lines.append("- step: %s %s" % (
            step.get("step"), json.dumps(
                {k: v for k, v in step.items() if k != "step"},
                ensure_ascii=False)))
    lines.append("")
    lines.append("## 验证结论")
    validation = report["validation"]
    lines.append("- overall: %s" % validation["overall"])
    lines.append("- artifact_valid: %s" % validation["artifact_valid"])
    lines.append("- computation_valid: %s" % validation["computation_valid"])
    lines.append("- goal_valid: %s" % validation["goal_valid"])
    for code in validation.get("error_codes") or []:
        lines.append("- error_code: %s" % code)
    lines.append("")
    lines.append("## 交付")
    if report["delivery"]["directory"]:
        lines.append("- directory: %s" % report["delivery"]["directory"])
        for rel in report["delivery"]["files"] or []:
            lines.append("- file: %s" % rel)
        lines.append("- manifest artifact_class: %s"
                     % report["delivery"]["manifest_artifact_class"])
    else:
        lines.append("- 无 authoritative 交付")
    lines.append("")
    lines.append("## 澄清记录")
    for question in report["clarification"]["questions"]:
        lines.append("- 问题 [%s]: %s" % (question.get("question_id"),
                                          question.get("question")))
    for answer in report["clarification"]["answers"]:
        lines.append("- 回答 [%s]: %s" % (answer.get("question_id"),
                                          json.dumps(answer.get("value"),
                                                     ensure_ascii=False)))
    if report["assumptions"]:
        lines.append("")
        lines.append("## 假设")
        for assumption in report["assumptions"]:
            lines.append("- %s" % json.dumps(assumption,
                                             ensure_ascii=False))
    lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-json", required=True)
    parser.add_argument("--truth-json", default=None,
                        help="optional frozen truth {sequence: ...} for "
                             "public-record reproduction comparison")
    parser.add_argument("--evidence-level", default="unknown",
                        help="evidence level label, e.g. unit / synthetic "
                             "/ natural-language-e2e / blind-test")
    parser.add_argument("--out-markdown", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = json.loads(pathlib.Path(args.result_json).read_text(
        encoding="utf-8"))
    truth = None
    if args.truth_json:
        truth = json.loads(pathlib.Path(args.truth_json).read_text(
            encoding="utf-8"))
    report = build_report(result, evidence_level=args.evidence_level,
                          truth=truth)
    markdown = render_markdown(report)
    out = pathlib.Path(args.out_markdown) if args.out_markdown else None
    if out:
        out.write_text(markdown, encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
