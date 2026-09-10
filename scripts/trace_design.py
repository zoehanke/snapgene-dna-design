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


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["record", "render", "inspect", "coverage", "compare"])
    p.add_argument("--trace-dir", required=True)
    p.add_argument("--input", help="JSON bundle with nodes and links (record only)")
    p.add_argument("--design-json", help="Preflight task, pipeline or recipe parameter JSON; never executes it")
    p.add_argument("--from-run", help="Recorded baseline run for compare")
    p.add_argument("--to-run", help="Later recorded run for compare")
    args = p.parse_args()
    try:
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
        if args.action == "coverage":
            if not args.design_json:
                p.error("coverage requires --design-json")
            design = json.loads(pathlib.Path(args.design_json).read_text(encoding="utf-8-sig"))
            current = [n for n in graph["nodes"] if n["kind"] == "decision" and graph["latest"][n["id"]] == n["key"]]
            choices = match_choices(extract_choices(input_snapshot(design)), current)
            print(json.dumps({"mode": "preflight, not executed", "choices": choices,
                "observed": len(choices), "explained": sum(c["status"] == "explained" for c in choices)}, ensure_ascii=False, indent=2))
            return 0
        if args.action in {"record", "render", "compare"}:
            graph = render(pathlib.Path(args.trace_dir), graph)
        else:
            graph = build_chains(graph)
        print(json.dumps({"trace_integrity": graph["integrity"], "issues": graph["issues"],
                          "records": len(graph["nodes"]), "runs": len(graph["runs"]),
                          "view": str(pathlib.Path(args.trace_dir).resolve() / "index.html")}, ensure_ascii=False))
        return 2 if errors else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("TRACE_INCOMPLETE: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
