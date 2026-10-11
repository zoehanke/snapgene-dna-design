"""Append-only single-writer event store and reproducible graph projection."""
from __future__ import annotations

import json
import copy
import pathlib
import uuid
from contextlib import contextmanager
from functools import wraps


def serialized(fn):
    @wraps(fn)
    def call(self, *args, **kwargs):
        with self.writing():
            return fn(self, *args, **kwargs)
    return call

from evidence_trace.models import REF_FIELDS, now, validate_node
from evidence_trace.settings import get_level, LEVELS
from evidence_trace.provenance import decision_provenance, requirement_provenance


def load_events(directory):
    path = pathlib.Path(directory) / "events.jsonl"
    if not path.exists():
        return [], []
    events, errors = [], []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            try:
                event = json.loads(line)
                if event["sequence"] != number or not line.endswith("\n"):
                    raise ValueError("nonsequential or truncated event")
                if not isinstance(event.get("payload"), dict):
                    raise ValueError("invalid payload")
                if events and event["trace_id"] != events[0]["trace_id"]:
                    raise ValueError("mixed trace identifiers")
                events.append(event)
            except (ValueError, KeyError, TypeError) as exc:
                errors.append(f"Line {number}: {exc}")
                break
    return events, errors


def project(events, errors=()):
    nodes, edges, runs, latest, queue, changes = {}, [], {}, {}, [], []
    explanations = []
    coverage_gaps, explanation_gaps, basis_links = [], [], []
    event_ids = {e["event_id"] for e in events}
    problems = list(errors)
    for event in events:
        p = event["payload"]
        kind = event["event_type"]
        if kind == "node_recorded":
            node = {**p, "recorded_at": event["timestamp"], "actor": event["actor"],
                    "run_id": event.get("run_id"), "recorded_sequence": event["sequence"],
                    "mode_at_capture": event.get("mode_at_capture", "unknown")}
            if node["kind"] == "decision":
                node["provenance"] = decision_provenance(node)
            elif node["kind"] == "requirement":
                node["provenance"] = requirement_provenance(node)
            nodes[node["key"]] = node
            latest[node["id"]] = node["key"]
            for field, refs in node.get("references", {}).items():
                for ref in refs:
                    edge = {"from": ref, "to": node["key"], "relation": field, "recorded_sequence": event["sequence"]}
                    if node["kind"] in {"validation", "artifact"} and field in {"decision_ids", "validated_by"}:
                        edge["association_scope"] = node.get("association_scope", "same_run")
                    edges.append(edge)
            for ref in node.get("basis_refs", []):
                basis_links.append({"from": ref, "to": node["key"], "recorded_sequence": event["sequence"],
                                    "relation": "declared_basis", "actor": event["actor"]})
            if node.get("previous"):
                edges.append({"from": node["previous"], "to": node["key"], "relation": "revised", "recorded_sequence": event["sequence"]})
            if node["kind"] == "source" and node.get("verification_status", "unverified") != "verified":
                queue.append({"node": node["key"], "reason": "来源未核验"})
            if node["kind"] == "decision":
                if not node.get("rationale") and node["mode_at_capture"] != "observed":
                    explanation_gaps.append({"node": node["key"], "reason": "缺少决策说明"})
                if not any(node.get("references", {}).get(f) for f in ("claim_ids", "responds_to", "validated_by")) and not node.get("basis_refs"):
                    coverage_gaps.append({"node": node["key"], "reason": "未关联选择依据"})
            if node["kind"] == "validation" and node.get("result") not in (True, "PASS", "PASSED", "passed", "verified", "not_requested", "N/A", "not_applicable", "NOT_APPLICABLE"):
                queue.append({"node": node["key"], "reason": "程序检查未通过或未评估"})
        elif kind == "evidence_linked":
            edges.append({**p, "recorded_sequence": event["sequence"]})
            if p.get("relation") in {"oppose", "constrain", "unknown"} or p.get("applicability", "unknown") != "direct" or p.get("limitations"):
                queue.append({"node": p["to"], "reason": "依据有限制或适用性待复核", "link": p})
        elif kind == "explanation_added":
            explanations.append({**p, "recorded_at": event["timestamp"], "actor": event["actor"],
                                 "recorded_sequence": event["sequence"],
                                 "mode_at_capture": event.get("mode_at_capture", "unknown")})
        elif kind == "change_recorded":
            changes.append({**p, "event_sequence": event["sequence"], "actor": event["actor"]})
        elif kind == "run_started":
            runs[event["run_id"]] = {**p, "id": event["run_id"], "stages": [], "status": "unfinished",
                                     "mode_at_capture": event.get("mode_at_capture", "unknown"),
                                     "started_event_ref": event["event_id"], "recorded_at": event["timestamp"]}
        elif kind == "trace_error":
            problems.append(p["message"])
        elif event.get("run_id") in runs:
            run = runs[event["run_id"]]
            if kind == "run_finished":
                run.update(p)
                run["finished_event_ref"] = event["event_id"]
                run["finished_at"] = event["timestamp"]
            else:
                run["stages"].append({**p, "event_type": kind, "event_id": event["event_id"],
                                      "recorded_at": event["timestamp"], "recorded_sequence": event["sequence"]})
    for edge in edges:
        if edge["from"] not in nodes or edge["to"] not in nodes:
            problems.append(f"Unresolved reference: {edge['from']} → {edge['to']}")
    for link in basis_links:
        if link["from"] not in nodes and link["from"] not in event_ids:
            problems.append(f"Unresolved basis reference: {link['from']}")
    for node in nodes.values():
        if node["kind"] == "claim" and not any(e["to"] == node["key"] and "statement_id" in e for e in edges):
            queue.append({"node": node["key"], "reason": "判断缺少证据陈述"})
    for run in runs.values():
        keys = set(run.get("context_refs", [])) | {n["key"] for n in nodes.values() if n.get("run_id") == run["id"]}
        scoped = [e for e in edges if e.get("recorded_sequence", 0) <= run.get("event_count_at_start", 0)
                  or nodes.get(e["to"], {}).get("run_id") == run["id"]]
        run["review_queue"] = [q for q in queue if q["node"] in keys and q["reason"] != "判断缺少证据陈述"
                               and (not q.get("link") or any(e.get("id") == q["link"]["id"] for e in scoped))]
        for key in sorted(keys):
            if nodes.get(key, {}).get("kind") == "claim" and not any(e["to"] == key and "statement_id" in e for e in scoped):
                run["review_queue"].append({"node": key, "reason": "判断缺少证据陈述"})
        if not run.get("decision_refs"):
            coverage_gaps.append({"run_id": run["id"], "reason": "未记录设计决定；已有程序观察不等于 AI 决策"})
        if not any(nodes.get(k, {}).get("kind") == "requirement" for k in run.get("context_refs", [])):
            coverage_gaps.append({"run_id": run["id"], "reason": "未提交用户要求来源"})
        if run["status"] == "unfinished":
            problems.append(f"{run['id']}: run has no finish event")
        run["coverage_gaps"] = [g for g in coverage_gaps if g.get("run_id") == run["id"] or g.get("node") in keys]
        run["explanation_gaps"] = [g for g in explanation_gaps if g["node"] in keys]
    return {"schema_version": "evidence-trace-v0.1", "nodes": list(nodes.values()),
            "edges": edges, "runs": list(runs.values()), "latest": latest, "changes": changes,
            "audit_events": copy.deepcopy(events), "explanations": explanations,
            "basis_links": basis_links, "coverage_gaps": coverage_gaps, "explanation_gaps": explanation_gaps,
            "review_queue": queue, "issues": problems,
            "integrity": "incomplete" if problems else "complete",
            "coverage": "Integrity covers recorded events only; coverage/explanation gaps are separate. Not model internal reasoning."}


class Recorder:
    def __init__(self, directory, *, mode_at_capture=None):
        self.mode_at_capture = get_level() if mode_at_capture is None else mode_at_capture
        if self.mode_at_capture not in LEVELS:
            raise ValueError("Unknown capture level")
        self.directory = pathlib.Path(directory).resolve()
        if self.mode_at_capture != "off":
            self.directory.mkdir(parents=True, exist_ok=True)
        self.events, errors = load_events(self.directory)
        if errors:
            raise ValueError("Refusing to append to damaged log: " + "; ".join(errors))
        self.trace_id = self.events[0]["trace_id"] if self.events else uuid.uuid4().hex
        self.run_id = None
        self._writer = None

    def acquire(self):
        if self._writer is not None:
            return
        if self.mode_at_capture == "off":
            raise ValueError("Trace collection is off; no event appended")
        handle = (self.directory / ".writer.lock").open("a+b")
        try:
            import os
            if os.name == "nt":
                import msvcrt
                if handle.seek(0, 2) == 0:
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.events, errors = load_events(self.directory)
            if errors:
                raise ValueError("Refusing damaged log: " + "; ".join(errors))
            self.trace_id = self.events[0]["trace_id"] if self.events else self.trace_id
            self._writer = handle
        except Exception:
            handle.close()
            raise

    def release(self):
        if self._writer is not None:
            self._writer.close()
            self._writer = None

    @contextmanager
    def writing(self):
        owned = self._writer is None
        if owned:
            self.acquire()
        try:
            yield self
        finally:
            if owned:
                self.release()

    @serialized
    def append(self, event_type, payload, actor="runtime"):
        if self.mode_at_capture == "off":
            raise ValueError("Trace collection is off; no event appended")
        event = {"schema_version": "evidence-trace-v0.2", "event_id": uuid.uuid4().hex,
                 "trace_id": self.trace_id, "run_id": self.run_id,
                 "sequence": len(self.events) + 1, "timestamp": now(),
                 "actor": actor, "event_type": event_type, "payload": payload,
                 "mode_at_capture": self.mode_at_capture}
        # Serialize before writing; a bad record cannot create a half JSON line.
        line = json.dumps(event, ensure_ascii=False, allow_nan=False)
        with (self.directory / "events.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
        self.events.append(json.loads(line))
        return event

    @serialized
    def record(self, node, actor="user", *, runtime=False):
        node = json.loads(json.dumps(node, ensure_ascii=False, allow_nan=False))
        if "observed_quote_ref" in node:
            raise ValueError("observed_quote_ref is reserved for program text matching")
        validate_node(node, runtime=runtime)
        graph = project(self.events)
        previous = graph["latest"].get(node["id"])
        by_key = {n["key"]: n for n in graph["nodes"]}
        basis = node.get("basis_refs", [])
        if not isinstance(basis, list) or any(not isinstance(ref, str) for ref in basis):
            raise ValueError("basis_refs must be a list of exact record revision keys or event IDs")
        known = set(by_key) | {e["event_id"] for e in self.events}
        if any(ref not in known for ref in basis):
            raise ValueError("basis_refs must refer to already recorded exact revisions or events")
        source = node.get("requirement_source") if node["kind"] == "requirement" else node.get("decision_source")
        if source:
            observed = next((e for e in self.events if e["event_id"] == source.get("reference")
                             and e["event_type"] == "material_observed"), None)
            if observed and source.get("form") == "verbatim":
                excerpt = source.get("excerpt", node.get("text", ""))
                original = observed["payload"].get("text")
                if not isinstance(excerpt, str) or not excerpt.strip() or not isinstance(original, str) or excerpt.replace("\r\n", "\n") not in original.replace("\r\n", "\n"):
                    raise ValueError("Verbatim excerpt does not match observed source text")
                node["observed_quote_ref"] = observed["event_id"]
        if previous and by_key[previous]["kind"] != node["kind"]:
            raise ValueError("A record revision cannot change kind")
        revision = by_key[previous]["revision"] + 1 if previous else 1
        refs = {}
        for field, expected_kind in REF_FIELDS.items():
            values = node.get(field, [])
            if isinstance(values, str):
                values = [values]
            refs[field] = []
            for value in values:
                key = graph["latest"].get(value, value)
                if key not in by_key or by_key[key]["kind"] != expected_kind:
                    raise ValueError(f"{field}: missing {expected_kind} {value}")
                refs[field].append(key)
        node.update(key=f"{node['id']}@{revision}", revision=revision, previous=previous, references=refs)
        self.append("node_recorded", node, actor)
        if previous:
            from evidence_trace.impact import revision_changes
            for change in revision_changes(by_key[previous], node):
                self.append("change_recorded", change, actor)
        return node["key"]

    def select_context(self, refs=None):
        """Freeze an explicit context and its existing evidence; legacy default is latest records."""
        graph = project(self.events)
        nodes = {n["key"]: n for n in graph["nodes"]}
        if refs is None:
            return [n["key"] for n in graph["nodes"] if graph["latest"][n["id"]] == n["key"]
                    and n["kind"] not in {"validation", "artifact"}]
        if not isinstance(refs, list) or any(not isinstance(ref, str) or ref not in nodes for ref in refs):
            raise ValueError("context_refs must contain exact recorded revision keys")
        selected, pending = set(), list(refs)
        while pending:
            key = pending.pop()
            if key in selected:
                continue
            selected.add(key)
            node = nodes[key]
            pending.extend(ref for values in node.get("references", {}).values() for ref in values)
            pending.extend(ref for ref in node.get("basis_refs", []) if ref in nodes)
            pending.extend(e["from"] for e in graph["edges"] if e["to"] == key and "statement_id" in e)
        return [n["key"] for n in graph["nodes"] if n["key"] in selected]

    @serialized
    def compare_runs(self, from_run, to_run):
        from evidence_trace.impact import run_changes
        graph = project(self.events)
        runs = {r["id"]: r for r in graph["runs"]}
        if from_run == to_run or from_run not in runs or to_run not in runs:
            raise ValueError("Choose two distinct recorded runs")
        if list(runs).index(from_run) >= list(runs).index(to_run):
            raise ValueError("Change direction must follow recorded run order")
        existing = {(c["from_revision"], c["to_revision"], c["changed_field"], c.get("subject")) for c in graph["changes"]}
        recorded = []
        for change in run_changes(runs[from_run], runs[to_run]):
            identity = (from_run, to_run, change["changed_field"], change.get("subject"))
            if identity not in existing:
                self.append("change_recorded", change)
                recorded.append(change["id"])
        return recorded

    @serialized
    def link(self, link, actor="user"):
        graph = project(self.events)
        by_key = {n["key"]: n for n in graph["nodes"]}
        p = json.loads(json.dumps(link, ensure_ascii=False))
        if 'required_dimensions' in p:
            from evidence_trace.applicability import DIMENSIONS
            dimensions = p['required_dimensions']
            if not isinstance(dimensions, list) or not dimensions or any(d not in DIMENSIONS for d in dimensions):
                raise ValueError('required_dimensions must name supported context dimensions')
        for field in ('conditions', 'limitations'):
            if field in p and (not isinstance(p[field], list) or any(not isinstance(v, str) for v in p[field])):
                raise ValueError(field + ' must be a list of text')
        for field, kind in (("statement_id", "statement"), ("claim_id", "claim")):
            key = graph["latest"].get(p[field], p[field])
            if key not in by_key or by_key[key]["kind"] != kind:
                raise ValueError(f"Missing {kind}: {p[field]}")
            p["from" if field == "statement_id" else "to"] = key
        p.setdefault("relation", "unknown")
        p.setdefault("applicability", "unknown")
        p.setdefault("strength", "unknown")
        p["declared_by"] = actor
        p["id"] = uuid.uuid4().hex
        self.append("evidence_linked", p, actor)

    @serialized
    def ingest(self, bundle):
        for node in bundle.get("nodes", []):
            self.record(node, actor=bundle.get("actor", "host-assistant"))
        for link in bundle.get("links", []):
            self.link(link, actor=bundle.get("actor", "host-assistant"))
        for explanation in bundle.get("explanations", []):
            self.explain(explanation, actor=bundle.get("actor", "host-assistant"))

    @serialized
    def explain(self, explanation, actor="host-assistant"):
        """Append supplied post-hoc assistance without modifying a Decision revision."""
        p = copy.deepcopy(explanation)
        graph = project(self.events)
        nodes = {n["key"]: n for n in graph["nodes"]}
        key = p.get("decision_ref")
        if key not in nodes or nodes[key]["kind"] != "decision":
            raise ValueError("Assistance needs an exact recorded decision_ref including revision")
        refs = p.get("basis_refs")
        known = set(nodes) | {e["event_id"] for e in self.events}
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in known for ref in refs):
            raise ValueError("Assistance needs exact existing record/event basis_refs")
        if not str(p.get("text") or "").strip():
            raise ValueError("Assistance needs text")
        p.update(id=uuid.uuid4().hex, explanation_origin="post_hoc_assistance", label="事后辅助解释")
        return self.append("explanation_added", p, actor)["payload"]["id"]

    def render(self):
        from evidence_trace.render import render
        events, errors = load_events(self.directory)
        graph = project(events, errors)
        return render(self.directory, graph)
