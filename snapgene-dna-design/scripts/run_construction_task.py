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

from evidence_trace.runtime import (observe, observe_value, traced_run, add_trace_arguments, trace_options, TraceStopped)

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
    add_trace_arguments(parser)
    args = parser.parse_args(argv)

    out = pathlib.Path(args.out_dir)
    try:
        return _run(args, out, **trace_options(args))
    except TraceStopped as exc:
        print(str(exc), file=sys.stderr)
        return 4


@traced_run("construction-task")
def _run(args, out):
    out.mkdir(parents=True, exist_ok=True)
    try:
        raw_task = json.loads(pathlib.Path(args.task_json).read_text(
            encoding="utf-8"))
    except Exception as exc:
        result = _failure_result("TASK_JSON_INVALID", str(exc))
        _emit(result, args, out)
        return 2

    try:
        session = ConstructionTaskSession(raw_task, base_dir=args.base_dir)
    except CoreError as exc:
        result = _failure_result(exc.error_code, exc.message, error=exc.to_dict())
        _emit(result, args, out)
        return 2
    except Exception as exc:
        result = _failure_result("TASK_SESSION_INVALID", str(exc))
        _emit(result, args, out)
        return 2
    if args.answers_json:
        try:
            answers = json.loads(pathlib.Path(args.answers_json).read_text(
                encoding="utf-8"))
        except Exception as exc:
            result = _failure_result("ANSWERS_JSON_INVALID", str(exc), session=session)
            _emit(result, args, out)
            return 2
        if not isinstance(answers, dict):
            result = _failure_result("ANSWERS_MUST_BE_OBJECT", "answers JSON must be an object", session=session)
            _emit(result, args, out)
            return 2
        for question_id, value in answers.items():
            try:
                session.answer(question_id, value)
            except (KeyError, ValueError) as exc:
                result = _failure_result("INVALID_ANSWER", str(exc), session=session)
                _emit(result, args, out)
                return 2

    open_questions = session.questions
    if open_questions:
        result = {
            "status": "needs-clarification",
            "questions": open_questions,
            "session": session.to_record(),
            "write_authoritative_artifact": False,
            "delivery": None,
            "historical_artifacts_preserved": True,
        }
        _emit(result, args, out)
        return 3

    try:
        task = observe("task", validate_construction_task,
            session.task, base_dir=args.base_dir)
        task, plan = observe("plan", plan_task, task, base_dir=args.base_dir)
        execution = observe("execute", execute, task, plan, out)
        report = observe("validate", validate, task, plan, execution)
        delivery = None
        if report["overall"] == "verified":
            try:
                delivery = observe("finalize", finalize, task, plan, execution, report, out)
            except GateRejected as exc:
                result = {
                    "status": "blocked",
                    "error": exc.to_dict(),
                    "validation": report,
                    "session": session.to_record(),
                    "delivery": None,
                    "write_authoritative_artifact": False,
                    "historical_artifacts_preserved": True,
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
            "write_authoritative_artifact": bool(delivery),
            "historical_artifacts_preserved": delivery is None,
        }
        _emit(result, args, out)
        return 0 if delivery else 2
    except TraceStopped:
        raise
    except CoreError as exc:
        result = {
            "status": exc.status,
            "error": exc.to_dict(),
            "session": session.to_record(),
            "delivery": None,
            "write_authoritative_artifact": False,
            "historical_artifacts_preserved": True,
        }
        _emit(result, args, out)
        return 2
    except Exception as exc:
        result = _failure_result("RUNTIME_ERROR", str(exc), session=session)
        _emit(result, args, out)
        return 2


def _emit(result, args, out):
    observe_value("outcome", result)
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


def _failure_result(error_code, message, session=None, error=None):
    """Emit current failure state without touching prior delivery artifacts."""
    result = {
        "status": "blocked",
        "error": error or {
            "status": "blocked",
            "error_code": error_code,
            "message": message,
            "missing_fields": [],
            "questions": [],
            "details": {},
            "write_authoritative_artifact": False,
        },
        "delivery": None,
        "write_authoritative_artifact": False,
        "historical_artifacts_preserved": True,
    }
    if session is not None:
        result["session"] = session.to_record()
    return result


if __name__ == "__main__":
    sys.exit(main())
