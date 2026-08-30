# -*- coding: utf-8 -*-
"""Natural-language experience-rule management and deterministic evaluation."""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.rule_capture import (  # noqa: E402
    evaluate_experience, handle_rule_request, load_preloaded_experience,
)
from rules.experience import ExperienceRuleStore, RuleValidationError  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", help="natural-language rule-management request")
    parser.add_argument("--trigger", choices=(
        "assembly_feasibility", "before_protocol_recommendation",
        "before_pcr_plan", "before_validation_primer_design",
        "before_primer_design", "after_primer_design",
        "after_pcr_plan", "before_method_selection",
        "after_validation_plan", "before_culture_plan",
        "before_delivery"))
    parser.add_argument("--context-json", help="JSON object or path used with --trigger")
    parser.add_argument(
        "--candidate-json",
        help="validated rule candidate as a JSON object or path; it is staged "
             "for preview and still requires explicit confirmation")
    parser.add_argument("--user-rules-dir", default=str(ROOT / "user_rules"))
    parser.add_argument("--project-id")
    parser.add_argument("--out-dir", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    store = ExperienceRuleStore(args.user_rules_dir)
    preloaded = load_preloaded_experience(
        ROOT / "rules" / "preloaded_experience_rules.json")
    store.ensure_preloaded(preloaded)
    try:
        if args.trigger:
            if not args.context_json:
                raise RuleValidationError(["--context-json is required with --trigger"])
            context_text = args.context_json.strip()
            if context_text.startswith("{"):
                context = json.loads(context_text)
            else:
                context = json.loads(
                    pathlib.Path(args.context_json).read_text(encoding="utf-8"))
            result = evaluate_experience(
                args.trigger, context, store, project_id=args.project_id,
                preloaded_rules=preloaded)
        elif args.candidate_json:
            candidate_text = args.candidate_json.strip()
            if candidate_text.startswith("{"):
                rule = json.loads(candidate_text)
            else:
                rule = json.loads(pathlib.Path(args.candidate_json).read_text(
                    encoding="utf-8"))
            candidate = store.add_candidate(rule)
            result = {
                "status": candidate["status"],
                "candidate": candidate,
                "message": "候选规则已校验并暂存；只有明确确认后才会生效。",
            }
        elif args.text:
            result = handle_rule_request(
                args.text, store, project_id=args.project_id,
                out_dir=args.out_dir, preloaded_rules=preloaded)
            if result is None:
                result = {"status": "not-a-rule-request"}
        else:
            raise RuleValidationError(
                ["--text, --candidate-json or --trigger is required"])
    except (RuleValidationError, OSError, json.JSONDecodeError) as error:
        result = {"status": "failed", "error": str(error),
                  "details": getattr(error, "errors", [])}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result.get("markdown") or
              (result.get("candidate") or {}).get("preview") or
              result.get("message") or json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") not in ("failed",) else 2


if __name__ == "__main__":
    sys.exit(main())
