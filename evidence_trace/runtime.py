"""Observe application-boundary calls without changing Core inputs or results."""
from __future__ import annotations

import contextvars
import functools
import inspect
import json
import pathlib
import sys
import uuid

from evidence_trace.models import file_digest, snapshot
from evidence_trace.recorder import Recorder, project

_CURRENT = contextvars.ContextVar("evidence_trace_run", default=None)


def input_snapshot(value, key=""):
    """Bind actual source files, including Recipe inputs without Core task hashes."""
    if any(x in key.lower() for x in ("password", "credential", "api_key", "token")):
        return "[omitted]"
    if isinstance(value, dict):
        return {str(k): input_snapshot(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [input_snapshot(v, key) for v in value]
    if isinstance(value, (str, pathlib.Path)) and len(str(value)) < 1024 and "\n" not in str(value):
        p = pathlib.Path(value)
        if p.suffix.lower() in {".gb", ".gbk", ".dna", ".fasta", ".fa"} and p.is_file():
            return {"source_path": str(p.resolve()), "source_sha256": file_digest(p)}
    return snapshot(value)


class TraceStopped(RuntimeError):
    """Explicit strict-mode stop, never a biological validation result."""


def add_trace_arguments(parser):
    parser.add_argument("--trace", action="store_true", help="Record design provenance (normal mode)")
    parser.add_argument("--trace-dir", help="Shared Evidence Trace directory; implies --trace")
    parser.add_argument("--trace-input", help="JSON containing decision/evidence records; implies --trace")
    parser.add_argument("--trace-mode", choices=["normal", "strict"], default="normal")


def trace_options(args):
    return {"trace": args.trace, "trace_dir": args.trace_dir,
            "trace_input": args.trace_input, "trace_mode": args.trace_mode}


class TraceRun:
    def __init__(self, out_dir, route, directory=None, bundle=None, mode="normal"):
        self.out = pathlib.Path(out_dir).resolve()
        self.directory = pathlib.Path(directory).resolve() if directory else self.out / "evidence-trace"
        self.route, self.mode = route, mode
        self.run_id = uuid.uuid4().hex
        self.errors, self.decisions, self.validations = [], [], []
        self.artifacts = set()
        self.recorder = None
        self.outcome = "unfinished"
        self.closed = False
        self.core_version = "unknown"
        if mode not in {"normal", "strict"}:
            raise ValueError("trace_mode must be normal or strict")
        def start():
            self.core_version = (pathlib.Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()
            reserved = [self.out / x for x in ("candidate", "intermediate", "intermediates", "authoritative", "annotated_sources")]
            if self.directory == self.out or any(self.directory.is_relative_to(p) for p in reserved):
                raise ValueError("Trace directory overlaps design artifact directories")
            self.recorder = Recorder(self.directory)
            if bundle:
                data = json.loads(pathlib.Path(bundle).read_text(encoding="utf-8-sig")) if isinstance(bundle, (str, pathlib.Path)) else bundle
                self.recorder.ingest(data)
            graph = project(self.recorder.events)
            current = [n for n in graph["nodes"] if graph["latest"][n["id"]] == n["key"] and n["kind"] not in {"validation", "artifact"}]
            self.decisions = [n["key"] for n in current if n["kind"] == "decision"]
            self.recorder.run_id = self.run_id
            self.recorder.append("run_started", {"route": route, "output_directory": str(self.out),
                "decision_refs": self.decisions, "context_refs": [n["key"] for n in current],
                "event_count_at_start": len(self.recorder.events), "trace_mode": mode})
            # A stopped process must not leave the previous run's "complete" view current.
            self.recorder.render()
        self.safe(start)

    def safe(self, action, *, may_stop=True):
        try:
            return action()
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            if message not in self.errors:
                self.errors.append(message)
                print("TRACE_INCOMPLETE: " + message, file=sys.stderr)
            if self.mode == "strict" and may_stop:
                raise TraceStopped("TRACE_INCOMPLETE: " + message) from exc
            return None

    def event(self, kind, payload):
        if self.recorder:
            self.recorder.append(kind, payload)

    def validation(self, name, result, details):
        dependencies = {
            "artifact_valid": ["sequence", "topology", "features"],
            "computation_valid": ["source", "sequence", "boundary", "orientation", "component", "method", "mutation", "order", "topology"],
            "goal_valid": ["sequence", "component", "boundary", "orientation"],
            "biological_sanity": ["sequence", "topology", "features"],
            "requested_components": ["sequence", "component", "orientation"],
        }
        key = self.recorder.record({"id": f"V-{self.run_id}-{len(self.validations)+1}", "kind": "validation",
            "check": name, "result": result, "details": snapshot(details),
            "tool": "snapgene-dna-design", "tool_version": self.core_version,
            "decision_ids": self.decisions, "depends_on_fields": dependencies.get(name, []),
            "dependency_scope_complete": False}, runtime=True, actor="runtime")
        self.validations.append(key)

    def capture(self, stage, value):
        if not self.recorder:
            return
        summary = snapshot(value)
        self.event("stage_completed", {"stage": stage, "result": summary})
        if stage == "validate":
            for field in ("artifact_valid", "computation_valid", "goal_valid"):
                if field in value:
                    self.validation(field, value[field], {"validation_sha256": value.get("validation_sha256"),
                        "task_sha256": value.get("task_sha256"), "errors": value.get("errors", []),
                        "evidence_traces": value.get("evidence_traces", [])})
        elif stage == "sanity":
            self.validation("biological_sanity", value.get("all_applicable_pass"), value)
        elif stage == "goal_check":
            self.validation("requested_components", value.get("status", "unknown"), value)
        elif stage == "outcome":
            self.outcome = value.get("status", "finished")
        if stage in {"recipe_result", "outcome"}:
            # A failure result may list historical files and a task may list inputs.
            # Neither is a newly produced artifact of this run.
            for key in ("delivery", "authoritative_delivery", "preparation_files", "candidate_files"):
                self.capture_files(value.get(key))
        elif stage in {"execute", "preparation", "finalize"}:
            self.capture_files(value)
        if stage in {"execute", "recipe_result"}:
            self.compare_previous()

    def capture_choices(self, stage, fn, args, kwargs, result):
        from evidence_trace.coverage import extract_choices
        if stage == "task":
            data, subject = input_snapshot(result), "task"
        elif stage == "recipe_execute":
            bound = inspect.signature(fn).bind(*args, **kwargs)
            bound.apply_defaults()
            data = input_snapshot(dict(bound.arguments))
            data["recipe_name"] = fn.__name__
            subject = "recipe"
        else:
            return
        for choice in extract_choices(data, subject=subject):
            self.event("design_choice_observed", {"stage": stage, "choice": choice,
                "observation": "Actual accepted call inputs; no rationale inferred."})
        self.compare_previous()

    def compare_previous(self):
        from evidence_trace.impact import comparison_identity
        if self.recorder:
            runs = project(self.recorder.events)["runs"]
            current = next((r for r in runs if r["id"] == self.run_id), None)
            identity = comparison_identity(current) if current else None
            previous = [r for r in runs if r["id"] != self.run_id and identity is not None and comparison_identity(r) == identity]
            if previous:
                self.recorder.compare_runs(previous[-1]["id"], self.run_id)

    def capture_files(self, value):
        if isinstance(value, dict):
            if value.get("directory") and isinstance(value.get("files"), list):
                for name in value["files"]:
                    self.capture_files(pathlib.Path(value["directory"]) / name)
            for item in value.values():
                self.capture_files(item)
        elif isinstance(value, (tuple, list)):
            for item in value:
                self.capture_files(item)
        elif isinstance(value, (str, pathlib.Path)):
            if len(str(value)) > 1024 or "\n" in str(value):
                return
            path = pathlib.Path(value)
            if path.suffix.lower() not in {".gb", ".dna", ".fasta", ".fa", ".json", ".tsv"}:
                return
            path = path.resolve()
            if not path.is_relative_to(self.out) or path.is_relative_to(self.directory) or not path.is_file():
                return
            sha = file_digest(path)
            stamp = (str(path), sha)
            if stamp in self.artifacts:
                return
            self.artifacts.add(stamp)
            relative = path.relative_to(self.out).as_posix()
            self.recorder.record({"id": f"A-{self.run_id}-{len(self.artifacts)}", "kind": "artifact",
                "path": str(path), "relative_path": relative, "sha256": sha,
                "role": "authoritative" if relative.startswith("authoritative/") else "intermediate-or-candidate",
                "decision_ids": self.decisions, "validated_by": self.validations,
                "validation_scope": "Run-level association; inspect each check's actual scope."}, runtime=True, actor="runtime")

    def close(self, error=None):
        if self.closed:
            return
        self.closed = True
        if error:
            self.outcome = "trace-stopped" if isinstance(error, TraceStopped) else "failed"
        def finish():
            if not self.recorder:
                return
            for message in self.errors:
                self.event("trace_error", {"message": message})
            self.event("run_finished", {"status": self.outcome,
                "error": str(error) if error else None, "trace_errors": list(self.errors)})
            self.recorder.render()
        # Never replace a Core exception, or roll back a completed delivery.
        self.safe(finish, may_stop=error is None)
        print(f"Evidence Trace: {self.directory / 'index.html'}" if not self.errors else
              "TRACE_INCOMPLETE: DNA outcome retained; trace has missing records or views", file=sys.stderr)


def observe(stage, fn, *args, **kwargs):
    run = _CURRENT.get()
    if run is None:
        return fn(*args, **kwargs)
    run.safe(lambda: run.event("stage_started", {"stage": stage,
        "input": input_snapshot({"args": args, "kwargs": kwargs})}))
    try:
        value = fn(*args, **kwargs)
    except Exception as exc:
        run.safe(lambda: run.event("stage_failed", {"stage": stage, "error": str(exc)}), may_stop=False)
        raise
    run.safe(lambda: run.capture(stage, value))
    run.safe(lambda: run.capture_choices(stage, fn, args, kwargs, value))
    return value


def observe_value(stage, value):
    run = _CURRENT.get()
    if run:
        run.safe(lambda: run.capture(stage, value))
    return value


def traced_run(route):
    """Optional wrapper. Existing calls and returned DNA results remain unchanged."""
    def decorate(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            enabled = kwargs.pop("trace", False)
            directory = kwargs.pop("trace_dir", None)
            bundle = kwargs.pop("trace_input", None)
            mode = kwargs.pop("trace_mode", "normal")
            if not (enabled or directory or bundle or mode == "strict") or _CURRENT.get() is not None:
                return fn(*args, **kwargs)
            bound = inspect.signature(fn).bind(*args, **kwargs)
            bound.apply_defaults()
            out = bound.arguments.get("out_dir", bound.arguments.get("out"))
            run = TraceRun(out, route, directory, bundle, mode)
            token = _CURRENT.set(run)
            error = None
            try:
                value = fn(*args, **kwargs)
                if isinstance(value, dict):
                    observe_value("outcome", value)
                    if "recipe_result" in value:
                        run.outcome = "delivered" if value.get("authoritative_delivery") else "candidate"
                        observe_value("recipe_result", value)
                return value
            except Exception as exc:
                error = exc
                raise
            finally:
                try:
                    run.close(error)
                finally:
                    _CURRENT.reset(token)
        return wrapped
    return decorate
