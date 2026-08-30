# -*- coding: utf-8 -*-
"""Unified CLI for the ConstructionTask runtime.

Usage:
  run_construction_task.py --task-json task.json [--answers-json answers.json]
      [--base-dir DIR] [--out-dir DIR] [--json]

Exit codes:
  0  delivered (authoritative written)
  2  blocked/failed with structured error (no authoritative written)
  3  needs-clarification (questions printed / written to result.json)
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import (ConstructionTaskSession, execute, finalize,
                  validate, validate_construction_task)
from core import plan as plan_task
from core.errors import CoreError, GateRejected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-json", required=True)
    parser.add_argument("--answers-json", default=None)
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    raw_task = json.loads(pathlib.Path(args.task_json).read_text(
        encoding="utf-8"))

    session = ConstructionTaskSession(raw_task, base_dir=args.base_dir)
    if args.answers_json:
        answers = json.loads(pathlib.Path(args.answers_json).read_text(
            encoding="utf-8"))
        if not isinstance(answers, dict):
            result = {"status": "blocked",
                      "error_code": "ANSWERS_MUST_BE_OBJECT",
                      "write_authoritative_artifact": False}
            _emit(result, args, out)
            return 2
        for question_id, value in answers.items():
            try:
                session.answer(question_id, value)
            except (KeyError, ValueError) as exc:
                result = {"status": "blocked",
                          "error_code": "INVALID_ANSWER",
                          "message": str(exc),
                          "write_authoritative_artifact": False}
                _emit(result, args, out)
                return 2

    open_questions = session.questions
    if open_questions:
        result = {
            "status": "needs-clarification",
            "questions": open_questions,
            "session": session.to_record(),
            "write_authoritative_artifact": False,
        }
        _emit(result, args, out)
        return 3

    try:
        task = validate_construction_task(
            session.task, base_dir=args.base_dir)
        task, plan = plan_task(task, base_dir=args.base_dir)
        execution = execute(task, plan, out)
        report = validate(task, plan, execution)
        delivery = None
        if report["overall"] == "verified":
            try:
                delivery = finalize(task, plan, execution, report, out)
            except GateRejected as exc:
                result = {
                    "status": "blocked",
                    "error": exc.to_dict(),
                    "validation": report,
                    "session": session.to_record(),
                }
                _emit(result, args, out)
                return 2
        result = {
            "status": "delivered" if delivery else report["overall"],
            "task": task,
            "plan_id": plan.get("plan_id"),
            "plan_summary": {
                "plan_id": plan.get("plan_id"),
                "task_kind": plan.get("task_kind"),
                "method_maturity": plan.get("method_maturity"),
                "steps": plan.get("steps"),
                "expected_length": plan["product"].get("expected_length"),
                "topology": plan["product"].get("topology"),
            },
            "execution_artifact_class": execution.get("artifact_class"),
            "execution_summary": {
                "artifact_class": execution.get("artifact_class"),
                "artifact_hashes": execution.get("artifact_hashes"),
                "product_sequence": execution.get("product_sequence"),
            },
            "validation": report,
            "delivery": delivery,
            "session": session.to_record(),
        }
        _emit(result, args, out)
        return 0 if delivery else 2
    except CoreError as exc:
        result = {
            "status": exc.status,
            "error": exc.to_dict(),
            "session": session.to_record(),
        }
        _emit(result, args, out)
        return 2


def _emit(result, args, out):
    (out / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("status=%s" % result.get("status"))
        if result.get("questions"):
            for question in result["questions"]:
                print("[%s] %s" % (question["question_id"],
                                   question["question"]))


if __name__ == "__main__":
    sys.exit(main())
