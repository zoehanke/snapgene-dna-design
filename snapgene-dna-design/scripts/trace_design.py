"""Append scientific decisions or rebuild offline Evidence Trace views."""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evidence_trace.recorder import Recorder, load_events, project
from evidence_trace.render import render
from evidence_trace.chain import build_chains
from evidence_trace.coverage import extract_choices, match_choices
from evidence_trace.runtime import input_snapshot
from evidence_trace.settings import get_level, set_level, settings_path, LEVELS
from evidence_trace.projection import build_facts
from evidence_trace.process import assemble, organize, save_report_plan
from evidence_trace.intake import observe_material, record_handoff
from evidence_trace.storage import machine_export


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["config", "record", "render", "inspect", "reader", "coverage", "compare",
                                      "observe", "handoff", "organize", "report-plan"])
    p.add_argument("--trace-dir")
    p.add_argument("--set-level", choices=LEVELS, help="Change the single global collection setting (config only)")
    p.add_argument("--input", help="JSON bundle with nodes and links (record only)")
    p.add_argument("--design-json", help="Preflight task, pipeline or recipe parameter JSON; never executes it")
    p.add_argument("--from-run", help="Recorded baseline run for compare")
    p.add_argument("--to-run", help="Later recorded run for compare")
    p.add_argument("--run-id", help="Reader projection for one recorded run (reader only)")
    p.add_argument("--handoff-id", help="Focus an exact recorded handoff event without discarding supporting history")
    p.add_argument("--format", choices=["html", "markdown", "both"], default="both", help="render output formats")
    p.add_argument("--language", choices=["zh", "en"], default="zh", help="Report UI language; original captured text is preserved")
    p.add_argument("--data", action="store_true", help="inspect: full captured snapshot for authored organization")
    p.add_argument("--process-ref", help="Exact organization version for report-plan/render/inspect")
    p.add_argument("--through-sequence", type=int, help="Read a historical event prefix")
    args = p.parse_args()
    try:
        if args.action == "config":
            if args.set_level:
                set_level(args.set_level)
            print(json.dumps({"trace_level": get_level(), "settings_file": str(settings_path()),
                              "scope": "Subsequent captures; no conversation override"}, ensure_ascii=False))
            return 0
        if args.set_level:
            p.error("--set-level is only valid with config")
        if args.run_id and args.action != "reader":
            p.error("--run-id is only valid with reader")
        if args.handoff_id and (args.action != "reader" or args.run_id):
            p.error("--handoff-id is for reader and is mutually exclusive with --run-id")
        if not args.trace_dir:
            p.error("--trace-dir is required for trace operations")
        if args.action in {"record", "compare", "observe", "handoff", "organize", "report-plan"} and get_level() == "off":
            print(json.dumps({"trace_level": "off", "recorded": False}, ensure_ascii=False))
            return 0
        if args.action in {"observe", "handoff", "organize", "report-plan"}:
            if not args.input:
                p.error(args.action + " requires --input")
            data = json.loads(pathlib.Path(args.input).read_text(encoding="utf-8-sig"))
            if args.action != "observe" and not isinstance(data, dict):
                raise ValueError(args.action + " input must be a JSON object")
            recorder = Recorder(args.trace_dir)
            if args.action == "observe":
                items = data if isinstance(data, list) else [data]
                response = []
                for item in items:
                    try:
                        response.append({"event_ref": observe_material(recorder, item)})
                    except (ValueError, OSError, KeyError, TypeError) as exc:
                        response.append({"error": str(exc)})
                print(json.dumps({"observations": response}, ensure_ascii=False, indent=2))
                return 2 if any("error" in r for r in response) else 0
            if args.action == "handoff":
                response = record_handoff(recorder, data.get("files"))
            elif args.action == "organize":
                response = {"process_ref": organize(recorder, data)}
            else:
                if not args.process_ref:
                    p.error("report-plan requires --process-ref")
                response = {"report_plan_ref": save_report_plan(recorder, args.process_ref, data)}
            graph = recorder.render()
            response["snapshot"] = graph["snapshot"]
            print(json.dumps(response, ensure_ascii=False, indent=2))
            return 0
        if args.action == "record":
            if not args.input:
                p.error("record requires --input")
            Recorder(args.trace_dir).ingest(json.loads(pathlib.Path(args.input).read_text(encoding="utf-8-sig")))
        events, errors = load_events(args.trace_dir)
        if args.action == "compare":
            if not args.from_run or not args.to_run:
                p.error("compare requires --from-run and --to-run")
            Recorder(args.trace_dir).compare_runs(args.from_run, args.to_run)
            events, errors = load_events(args.trace_dir)
        if not events and args.action != "coverage":
            raise ValueError("No trace events recorded")
        graph = project(events, errors)
        if args.action == "inspect" and args.data:
            facts = build_facts(events, errors, through_sequence=args.through_sequence)
            facts.pop("legacy_graph")
            print(json.dumps(facts, ensure_ascii=False, indent=2))
            return 2 if errors else 0
        if args.action == "coverage":
            if not args.design_json:
                p.error("coverage requires --design-json")
            design = json.loads(pathlib.Path(args.design_json).read_text(encoding="utf-8-sig"))
            current = [n for n in graph["nodes"] if n["kind"] == "decision" and graph["latest"][n["id"]] == n["key"]]
            choices = match_choices(extract_choices(input_snapshot(design)), current)
            print(json.dumps({"mode": "preflight, not executed", "choices": choices,
                "observed": len(choices), "explained": sum(c["status"] == "explained" for c in choices),
                "target_matched": sum(c["target_match"] == "matched" for c in choices),
                "original_explanation_recorded": sum(c["original_explanation_recorded"] for c in choices)}, ensure_ascii=False, indent=2))
            return 0
        if args.action in {"record", "render", "compare"}:
            if args.process_ref or args.through_sequence is not None:
                graph = assemble(events, errors, process_ref=args.process_ref, through_sequence=args.through_sequence)
            graph = render(pathlib.Path(args.trace_dir), graph, formats=args.format, language=args.language)
        else:
            graph = build_chains(graph)
        if args.action == "reader":
            from evidence_trace.reader import reader_for_run
            result = assemble(events, errors, process_ref=args.process_ref, through_sequence=args.through_sequence)
            if args.run_id:
                result["focused_reader"] = reader_for_run(result["reader"], args.run_id)
                result["focus"] = {"run_id": args.run_id, "scope": "Full process and supporting records retained"}
            if args.handoff_id:
                handoff = next((e for e in events if e["event_id"] == args.handoff_id and e["event_type"] == "handoff_recorded"
                                and e["sequence"] <= result["snapshot"]["through_sequence"]), None)
                if handoff is None:
                    raise ValueError("Unknown handoff event in snapshot")
                result["focus"] = {"handoff_id": args.handoff_id, "files": handoff["payload"]["files"],
                                   "scope": "Full process and supporting records retained"}
            print(json.dumps(machine_export(result), ensure_ascii=False, indent=2))
            return 2 if errors else 0
        response = {"trace_integrity": graph["integrity"], "issues": graph["issues"],
                          "records": len(graph["nodes"]), "runs": len(graph["runs"]),
                          "explanations": graph.get("explanations", []),
                          "decision_provenance": [{"decision_ref": n["key"], **n["provenance"]}
                                                  for n in graph["nodes"] if n["kind"] == "decision"],
                          "view": str(pathlib.Path(args.trace_dir).resolve() / "index.html")}
        if args.action == "inspect":
            response.update(coverage_gaps=graph["coverage_gaps"], explanation_gaps=graph["explanation_gaps"],
                            review_queue=graph["review_queue"], basis_links=graph["basis_links"],
                            requirement_provenance=[{"requirement_ref": n["key"], "text": n["text"],
                                                     "context": n.get("context", {}), "basis_refs": n.get("basis_refs", []),
                                                     **n["provenance"]}
                                                    for n in graph["nodes"] if n["kind"] == "requirement"],
                            run_contexts=[{k: r.get(k) for k in ("id", "context_refs", "decision_refs", "context_selection",
                                                                "started_event_ref", "finished_event_ref")}
                                          for r in graph["runs"]])
        print(json.dumps(response, ensure_ascii=False))
        return 2 if errors else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("TRACE_INCOMPLETE: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
