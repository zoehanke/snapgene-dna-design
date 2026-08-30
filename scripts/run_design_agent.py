# -*- coding: utf-8 -*-
"""run_design_agent.py - CLI entry for the v0.9.0-dev1 construction Agent.

This is a deterministic scheduler over the existing toolchain. It never
reimplements primer/restriction/assembly algorithms.
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from design.spec import diff_specs, spec_sha256  # noqa: E402
from agent.session import Session  # noqa: E402
from agent.orchestrator import Orchestrator  # noqa: E402
from agent.rule_capture import (  # noqa: E402
    handle_rule_request, load_preloaded_experience,
)
from rules.experience import ExperienceRuleStore  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", default="")
    parser.add_argument("--files", nargs="*", default=[])
    parser.add_argument("--mode", choices=("exploration", "formal"),
                        default="exploration")
    parser.add_argument("--out-dir", default=".")
    parser.add_argument("--user-rules-dir", default=str(ROOT / "user_rules"),
                        help="confirmed experience-rule directory")
    parser.add_argument("--project-id",
                        help="project scope identifier; defaults to out-dir name")
    parser.add_argument("--auto-confirm", action="store_true",
                        help="automatically approve all must-ask questions "
                             "with the recorded answer 'auto-confirmed'")
    parser.add_argument("--answers-json",
                        help="path to a JSON object {question_id: value}")
    parser.add_argument("--deliver", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.mode == "formal":
        result = {
            "status": "blocked",
            "error_code": "LEGACY_AGENT_FORMAL_DEPRECATED",
            "message": ("v0.9.1 formal construction must use the "
                        "ConstructionTask runtime "
                        "(core.validate_construction_task / plan / execute / "
                        "validate / finalize). The v0.9.0 keyword-parser "
                        "formal path is deprecated and no longer executes."),
            "write_authoritative_artifact": False,
        }
        _emit(result, args)
        return 4

    # Rule-maintenance utterances are a separate, non-biological workflow.
    # Handle them before creating a DesignSpec so "查看规则" cannot be
    # misinterpreted as a construct-design request.
    project_id = args.project_id or pathlib.Path(args.out_dir).resolve().name
    rule_store = ExperienceRuleStore(args.user_rules_dir)
    preloaded_rules = load_preloaded_experience(
        ROOT / "rules" / "preloaded_experience_rules.json")
    rule_result = handle_rule_request(
        args.text, rule_store, project_id=project_id,
        out_dir=args.out_dir, preloaded_rules=preloaded_rules)
    if rule_result is not None:
        _emit_rule_result(rule_result, args)
        return 3 if rule_result.get("status") in (
            "awaiting-confirmation", "needs-clarification",
            "needs-selection") else 0

    session = Session.create(args.text, mode=args.mode, files=args.files,
                             workdir=args.out_dir)
    orch = Orchestrator(session, out_dir=args.out_dir)
    try:
        parsed = orch.start(args.text, args.files)
        if args.answers_json:
            answers = json.loads(pathlib.Path(args.answers_json).read_text(
                encoding="utf-8"))
        else:
            answers = {}
        for question in parsed["questions"]:
            value = answers.get(question["question_id"])
            if value is None and args.auto_confirm:
                value = "auto-confirmed"
            if value is not None:
                orch.answer(question["question_id"], value)
        if session.spec["status"] == "needs-clarification" and not \
                (args.auto_confirm or args.answers_json):
            result = {"status": session.spec["status"],
                      "spec": session.spec,
                      "questions": session.spec["questions"],
                      "missing_information":
                          session.spec["missing_information"]}
            _emit(result, args)
            return 3
        orch.confirm()
        orch.resolve_evidence()
        orch.plan()
        orch.execute()
        orch.verify()
        delivery = None
        if args.deliver:
            delivery = orch.deliver()
        result = {
            "status": session.spec["status"],
            "spec": session.spec,
            "delivery": delivery,
            "recovery_actions": orch.report.get("recovery_actions", []),
        }
        _emit(result, args)
        return 0 if session.spec["status"] == "delivered" or \
            not args.deliver else 1
    except Exception as error:  # noqa: BLE001 - structured agent failure
        orch.block_with_recovery(str(error), orch.report.get("recovery_actions"))
        result = {"status": "blocked", "error": str(error),
                  "recovery_actions": orch.report.get("recovery_actions", []),
                  "spec": session.spec}
        _emit(result, args)
        return 2


def _emit(result, args):
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("status=%s" % result.get("status"))
        if result.get("questions"):
            for question in result["questions"]:
                print("[%s] %s (%s)" % (
                    question.get("category"), question.get("question"),
                    question.get("question_id")))
        if result.get("recovery_actions"):
            for action in result["recovery_actions"]:
                print("RECOVERY: %s" % action)


def _emit_rule_result(result, args):
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    printable = (result.get("markdown") or
                 (result.get("candidate") or {}).get("preview") or
                 result.get("message"))
    if printable:
        print(printable)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
