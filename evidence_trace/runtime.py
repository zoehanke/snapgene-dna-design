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
from evidence_trace.settings import get_level

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
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser.add_argument("--trace", action="store_true", help="Legacy flag; global trace_level controls collection")
    parser.add_argument("--trace-dir", help="Shared Evidence Trace directory; does not override global off")
    parser.add_argument("--trace-input", help="JSON decision/evidence records; ignored when global trace_level is off")
    parser.add_argument("--trace-mode", choices=["normal", "strict"], default="normal")


def trace_options(args):
    return {"trace": args.trace, "trace_dir": args.trace_dir,
            "trace_input": args.trace_input, "trace_mode": args.trace_mode}


class TraceRun:
    def __init__(self, out_dir, route, directory=None, bundle=None, mode="normal", level=None):
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
            recorder = Recorder(self.directory, mode_at_capture=level)
            recorder.acquire()
            self.recorder = recorder
            data = {}
            if bundle:
                data = json.loads(pathlib.Path(bundle).read_text(encoding="utf-8-sig")) if isinstance(bundle, (str, pathlib.Path)) else bundle
                self.recorder.ingest(data)
            graph = project(self.recorder.events)
            if "context_refs" in data and data["context_refs"] is None:
                raise ValueError("Explicit context_refs must be a list")
            context = self.recorder.select_context(data.get("context_refs"))
            active = set(data.get("context_refs", context))
            self.decisions = [n["key"] for n in graph["nodes"] if n["key"] in active and n["kind"] == "decision"]
            self.recorder.run_id = self.run_id
            self.recorder.append("run_started", {"route": route, "output_directory": str(self.out),
                "decision_refs": self.decisions, "context_refs": context,
                "context_selection": "explicit" if "context_refs" in data else "latest_records",
                "event_count_at_start": len(self.recorder.events), "trace_mode": mode})
            # A stopped process must not leave the previous run's "complete" view current.
            self.recorder.render()
        try:
            self.safe(start)
        except Exception:
            if self.recorder:
                self.recorder.release()
            raise

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
            return self.recorder.append(kind, payload)

    def validation(self, name, result, details, result_event_ref=None):
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
            "result_event_ref": result_event_ref, "association_scope": "same_run",
            "dependency_scope_complete": False}, runtime=True, actor="runtime")
        self.validations.append(key)

    def capture(self, stage, value, stage_ref=None):
        if not self.recorder:
            return
        summary = snapshot(value)
        result_event = self.event("stage_completed", {"stage": stage, "stage_ref": stage_ref,
                                                      "result": summary, "observation_phase": "returned_value"})
        result_ref = result_event["event_id"]
        if stage == "validate":
            for field in ("artifact_valid", "computation_valid", "goal_valid"):
                if field in value:
                    self.validation(field, value[field], {"validation_sha256": value.get("validation_sha256"),
                        "task_sha256": value.get("task_sha256"), "errors": value.get("errors", []),
                        "evidence_traces": value.get("evidence_traces", [])}, result_ref)
        elif stage == "sanity":
            self.validation("biological_sanity", value.get("all_applicable_pass"), value, result_ref)
        elif stage == "goal_check":
            self.validation("requested_components", value.get("status", "unknown"), value, result_ref)
        elif stage == "outcome":
            self.outcome = value.get("status", "finished")
        if stage in {"recipe_result", "outcome"}:
            # A failure result may list historical files and a task may list inputs.
            # Neither is a newly produced artifact of this run.
            for key in ("delivery", "authoritative_delivery", "preparation_files", "candidate_files"):
                self.capture_files(value.get(key), result_ref)
        elif stage in {"execute", "preparation", "finalize", "candidate_files"}:
            self.capture_files(value, result_ref)
        if stage in {"execute", "recipe_result"}:
            self.compare_previous()

    def capture_choices(self, stage, fn, args, kwargs, result, stage_ref=None):
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
                "stage_ref": stage_ref, "observation_phase": "accepted_inputs_after_call",
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

    def capture_files(self, value, result_event_ref=None):
        if isinstance(value, dict):
            if value.get("directory") and isinstance(value.get("files"), list):
                for name in value["files"]:
                    self.capture_files(pathlib.Path(value["directory"]) / name, result_event_ref)
            for item in value.values():
                self.capture_files(item, result_event_ref)
        elif isinstance(value, (tuple, list)):
            for item in value:
                self.capture_files(item, result_event_ref)
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
                "result_event_ref": result_event_ref, "association_scope": "same_run",
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
        try:
            self.safe(finish, may_stop=error is None)
        finally:
            if self.recorder:
                self.recorder.release()
        print(f"Evidence Trace: {self.directory / 'index.html'}" if not self.errors else
              "TRACE_INCOMPLETE: DNA outcome retained; trace has missing records or views", file=sys.stderr)


def observe(stage, fn, *args, **kwargs):
    run = _CURRENT.get()
    if run is None:
        return fn(*args, **kwargs)
    started = run.safe(lambda: run.event("stage_started", {"stage": stage,
        "observation_phase": "submitted_inputs", "input": input_snapshot({"args": args, "kwargs": kwargs})}))
    stage_ref = started["event_id"] if started else None
    try:
        value = fn(*args, **kwargs)
    except Exception as exc:
        run.safe(lambda: run.event("stage_failed", {"stage": stage, "stage_ref": stage_ref,
                                                   "error": str(exc)}), may_stop=False)
        raise
    run.safe(lambda: run.capture(stage, value, stage_ref))
    run.safe(lambda: run.capture_choices(stage, fn, args, kwargs, value, stage_ref))
    return value


def observe_value(stage, value):
    run = _CURRENT.get()
    if run:
        run.safe(lambda: run.capture(stage, value))
    return value


def observe_files(stage, fn, *, args=(), kwargs=None, input_paths=(), output_paths,
                  artifact_role="derived", expected_paths=()):
    """Observe one file operation. Preserve before/after identities, including in-place edits."""
    run = _CURRENT.get()
    if run is None or run.recorder is None:
        return fn(*args, **(kwargs or {}))
    def stamps(paths):
        return [{"path": str(pathlib.Path(p).resolve()),
                 "sha256": file_digest(p) if pathlib.Path(p).is_file() else None} for p in paths]
    before = run.safe(lambda: stamps([*input_paths, *expected_paths])) or []
    started = run.safe(lambda: run.event("stage_started", {"stage": stage,
        "input": input_snapshot({"args": args, "kwargs": kwargs or {}}),
        "input_files": before[:len(input_paths)], "observation_phase": "submitted_inputs"}))
    stage_ref = started["event_id"] if started else None
    try:
        result = fn(*args, **(kwargs or {}))
    except Exception as exc:
        run.safe(lambda: run.event("file_operation_failed", {"stage": stage, "stage_ref": stage_ref,
            "error": str(exc), "before": before, "residual_files": stamps(expected_paths)}), may_stop=False)
        raise
    def capture():
        paths = list(output_paths(result))
        after = stamps(paths)
        event = run.event("file_operation_completed", {"stage": stage, "stage_ref": stage_ref,
            "result": snapshot(result), "before": before, "after": after})
        previous = {x["path"]: x["sha256"] for x in before}
        graph = project(run.recorder.events)
        inputs = [n["key"] for n in graph["nodes"] if n["kind"] == "artifact" and any(
            n["path"] == stamp["path"] and n["sha256"] == stamp["sha256"] for stamp in before[:len(input_paths)])]
        for item in after:
            if item["sha256"] is None:
                continue
            path = pathlib.Path(item["path"])
            if path.is_relative_to(run.directory):
                continue
            status = "presence_only" if previous.get(item["path"]) == item["sha256"] else "modified" if previous.get(item["path"]) else "created"
            key = run.recorder.record({"id": "A-" + uuid.uuid4().hex, "kind": "artifact", **item,
                "role": artifact_role, "generation_observation": status, "input_artifact_refs": inputs,
                "input_files": before[:len(input_paths)], "result_event_ref": event["event_id"],
                "decision_ids": run.decisions, "validated_by": [], "association_scope": "file_operation"}, runtime=True)
            run.artifacts.add((str(path), item["sha256"]))
        run.outcome = "finished"
    run.safe(capture)
    return result


def trace_file_call(route, fn, *, args=(), kwargs=None, input_paths=(), output_paths=lambda result: (),
                    expected_paths=(), artifact_role="derived", trace_dir=None,
                    trace_input=None, trace_mode="normal", trace=False):
    """File CLIs opt into an explicit shared trace; nested calls reuse the active run."""
    if _CURRENT.get() is not None:
        return observe_files(route, fn, args=args, kwargs=kwargs, input_paths=input_paths,
                             output_paths=output_paths, expected_paths=expected_paths, artifact_role=artifact_role)
    if not trace_dir:
        return fn(*args, **(kwargs or {}))
    try:
        level = get_level()
    except (OSError, ValueError) as exc:
        if trace_mode == "strict":
            raise TraceStopped(str(exc)) from exc
        print("TRACE_INCOMPLETE: " + str(exc), file=sys.stderr)
        return fn(*args, **(kwargs or {}))
    if level == "off":
        return fn(*args, **(kwargs or {}))
    anchor = next(iter(expected_paths), next(iter(input_paths), pathlib.Path(trace_dir).parent / "operation"))
    run = TraceRun(pathlib.Path(anchor).resolve().parent, route, trace_dir, trace_input, trace_mode, level)
    token, error = _CURRENT.set(run), None
    try:
        return observe_files(route, fn, args=args, kwargs=kwargs, input_paths=input_paths,
                             output_paths=output_paths, expected_paths=expected_paths, artifact_role=artifact_role)
    except Exception as exc:
        error = exc
        raise
    finally:
        try:
            run.close(error)
        finally:
            _CURRENT.reset(token)


def traced_run(route):
    """Optional wrapper. Existing calls and returned DNA results remain unchanged."""
    def decorate(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            kwargs.pop("trace", None)  # Legacy collection flag; never a per-call level override.
            directory = kwargs.pop("trace_dir", None)
            bundle = kwargs.pop("trace_input", None)
            mode = kwargs.pop("trace_mode", "normal")
            if _CURRENT.get() is not None:
                return fn(*args, **kwargs)
            try:
                level = get_level()
            except (OSError, ValueError) as exc:
                if mode == "strict":
                    raise TraceStopped("TRACE_INCOMPLETE: " + str(exc)) from exc
                print("TRACE_INCOMPLETE: " + str(exc), file=sys.stderr)
                return fn(*args, **kwargs)
            if level == "off":
                return fn(*args, **kwargs)
            bound = inspect.signature(fn).bind(*args, **kwargs)
            bound.apply_defaults()
            out = bound.arguments.get("out_dir", bound.arguments.get("out"))
            run = TraceRun(out, route, directory, bundle, mode, level)
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
