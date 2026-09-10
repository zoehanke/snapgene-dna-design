"""Append-only single-writer event store and reproducible graph projection."""
from __future__ import annotations

import json
import copy
import pathlib
import uuid

from evidence_trace.models import REF_FIELDS, now, validate_node


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
    problems = list(errors)
    for event in events:
        p = event["payload"]
        kind = event["event_type"]
        if kind == "node_recorded":
            node = {**p, "recorded_at": event["timestamp"], "actor": event["actor"],
                    "run_id": event.get("run_id"), "recorded_sequence": event["sequence"]}
            nodes[node["key"]] = node
            latest[node["id"]] = node["key"]
            for field, refs in node.get("references", {}).items():
                for ref in refs:
                    edges.append({"from": ref, "to": node["key"], "relation": field, "recorded_sequence": event["sequence"]})
            if node.get("previous"):
                edges.append({"from": node["previous"], "to": node["key"], "relation": "revised", "recorded_sequence": event["sequence"]})
            if node["kind"] == "source" and node.get("verification_status", "unverified") != "verified":
                queue.append({"node": node["key"], "reason": "来源未核验"})
            if node["kind"] == "decision":
                if not node.get("rationale"):
                    queue.append({"node": node["key"], "reason": "缺少决策说明"})
                if not node.get("references", {}).get("claim_ids"):
                    queue.append({"node": node["key"], "reason": "缺少判断依据"})
            if node["kind"] == "validation" and node.get("result") not in (True, "PASS", "passed", "verified"):
                queue.append({"node": node["key"], "reason": "程序检查未通过或未评估"})
        elif kind == "evidence_linked":
            edges.append({**p, "recorded_sequence": event["sequence"]})
            if p.get("relation") in {"oppose", "constrain", "unknown"} or p.get("applicability", "unknown") != "direct" or p.get("limitations"):
                queue.append({"node": p["to"], "reason": "依据有限制或适用性待复核", "link": p})
        elif kind == "change_recorded":
            changes.append({**p, "event_sequence": event["sequence"], "actor": event["actor"]})
        elif kind == "run_started":
            runs[event["run_id"]] = {**p, "id": event["run_id"], "stages": [], "status": "unfinished"}
        elif kind == "trace_error":
            problems.append(p["message"])
        elif event.get("run_id") in runs:
            run = runs[event["run_id"]]
            if kind == "run_finished":
                run.update(p)
            else:
                run["stages"].append({"event_type": kind, **p})
    for edge in edges:
        if edge["from"] not in nodes or edge["to"] not in nodes:
            problems.append(f"Unresolved reference: {edge['from']} → {edge['to']}")
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
            problems.append(f"{run['id']}: no recorded decisions")
        if not any(nodes.get(k, {}).get("kind") == "requirement" for k in run.get("context_refs", [])):
            problems.append(f"{run['id']}: no recorded user requirement")
        if run["status"] == "unfinished":
            problems.append(f"{run['id']}: run has no finish event")
    return {"schema_version": "evidence-trace-v0.1", "nodes": list(nodes.values()),
            "edges": edges, "runs": list(runs.values()), "latest": latest, "changes": changes,
            "audit_events": copy.deepcopy(events),
            "review_queue": queue, "issues": problems,
            "integrity": "incomplete" if problems else "complete",
            "coverage": "Submitted decisions and observed runtime stages only; not model internal reasoning."}


class Recorder:
    def __init__(self, directory):
        self.directory = pathlib.Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.events, errors = load_events(self.directory)
        if errors:
            raise ValueError("Refusing to append to damaged log: " + "; ".join(errors))
        self.trace_id = self.events[0]["trace_id"] if self.events else uuid.uuid4().hex
        self.run_id = None

    def append(self, event_type, payload, actor="runtime"):
        event = {"schema_version": "evidence-trace-v0.1", "event_id": uuid.uuid4().hex,
                 "trace_id": self.trace_id, "run_id": self.run_id,
                 "sequence": len(self.events) + 1, "timestamp": now(),
                 "actor": actor, "event_type": event_type, "payload": payload}
        # Serialize before writing; a bad record cannot create a half JSON line.
        line = json.dumps(event, ensure_ascii=False, allow_nan=False)
        with (self.directory / "events.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
        self.events.append(json.loads(line))
        return event

    def record(self, node, actor="user", *, runtime=False):
        node = json.loads(json.dumps(node, ensure_ascii=False, allow_nan=False))
        validate_node(node, runtime=runtime)
        graph = project(self.events)
        previous = graph["latest"].get(node["id"])
        by_key = {n["key"]: n for n in graph["nodes"]}
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

    def link(self, link, actor="user"):
        graph = project(self.events)
        by_key = {n["key"]: n for n in graph["nodes"]}
        p = json.loads(json.dumps(link, ensure_ascii=False))
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

    def ingest(self, bundle):
        for node in bundle.get("nodes", []):
            self.record(node, actor=bundle.get("actor", "host-assistant"))
        for link in bundle.get("links", []):
            self.link(link, actor=bundle.get("actor", "host-assistant"))

    def render(self):
        from evidence_trace.render import render
        events, errors = load_events(self.directory)
        graph = project(events, errors)
        render(self.directory, graph)
        return graph
