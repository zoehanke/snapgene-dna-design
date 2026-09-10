"""Append scientific decisions or rebuild offline Evidence Trace views."""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evidence_trace.recorder import Recorder, load_events, project
from evidence_trace.render import render


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["record", "render", "inspect"])
    p.add_argument("--trace-dir", required=True)
    p.add_argument("--input", help="JSON bundle with nodes and links (record only)")
    args = p.parse_args()
    try:
        if args.action == "record":
            if not args.input:
                p.error("record requires --input")
            Recorder(args.trace_dir).ingest(json.loads(pathlib.Path(args.input).read_text(encoding="utf-8-sig")))
        events, errors = load_events(args.trace_dir)
        if not events:
            raise ValueError("No trace events recorded")
        graph = project(events, errors)
        if args.action in {"record", "render"}:
            render(pathlib.Path(args.trace_dir), graph)
        print(json.dumps({"trace_integrity": graph["integrity"], "issues": graph["issues"],
                          "records": len(graph["nodes"]), "runs": len(graph["runs"]),
                          "view": str(pathlib.Path(args.trace_dir).resolve() / "index.html")}, ensure_ascii=False))
        return 2 if errors else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print("TRACE_INCOMPLETE: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
