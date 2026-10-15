"""Accept authored process organization; never invent scientific links or runtime facts."""
from __future__ import annotations

import copy
import re

from evidence_trace.projection import AUTHORED_EVENTS, build_facts

STEP_KINDS = {"requirement", "choice", "program_result", "artifact"}
RELATIONS = {"responds_to", "declared_reason_for_change", "supports", "opposes", "constrains",
             "contextualizes", "grouped_with", "part_of", "revises_plan"}
ORIGINS = {"original_statement", "organized_summary", "later_interpretation", "unknown"}


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + " must be nonempty text")


def _refs(values, known, label, required=False):
    if not isinstance(values, list) or (required and not values):
        raise ValueError(label + " must be " + ("a nonempty" if required else "a") + " reference list")
    if any(not isinstance(k, str) or k not in known for k in values):
        raise ValueError(label + " contains unknown or out-of-snapshot references")
    return values


def _keys(value, allowed, label):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError(label + " has unsupported fields")


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[\w.:-]+", value):
        raise ValueError("id must be a nonempty identifier")


def _source_texts(record):
    if "event_type" in record:
        record = record["payload"]
    return [record[k].replace("\r\n", "\n") for k in ("text", "rationale") if isinstance(record.get(k), str)]


def validate_organization(packet, facts):
    _keys(packet, {"schema_version", "id", "basis", "design_process", "report_plan"}, "organization")
    if packet.get("schema_version") != "trace-organization-v1":
        raise ValueError("Expected trace-organization-v1")
    _identifier(packet.get("id"))
    if packet.get("basis") != {k: facts["snapshot"][k] for k in ("trace_id", "through_sequence")}:
        raise ValueError("basis must match the inspected snapshot")
    p = copy.deepcopy(packet.get("design_process"))
    _keys(p, {"stages", "steps", "relations", "paths", "unresolved", "detail_refs"}, "design_process")
    for field in ("stages", "relations", "paths", "unresolved", "detail_refs"):
        if not isinstance(p.get(field), list):
            raise ValueError(field + " must be a list")
    if not p["stages"] or not isinstance(p.get("steps"), dict) or not p["steps"]:
        raise ValueError("Organization needs a purposeful stage and referenced steps")
    records, ids = facts["source_records"], set()
    def identity(key):
        _identifier(key)
        if key in ids or key in records:
            raise ValueError("Duplicate or colliding organization id: " + key)
        ids.add(key)
    for key, step in p["steps"].items():
        identity(key)
        _keys(step, {"kind", "content", "title", "subject_ref", "source_refs", "reason", "limitations", "input_refs", "outcome_refs"}, "step")
        if step.get("kind") not in STEP_KINDS:
            raise ValueError("Unknown step kind")
        _text(step.get("content"), "step content")
        if "title" in step:
            _text(step["title"], "step title")
        refs = _refs(step.get("source_refs"), records, "step source_refs", True)
        if step.get('subject_ref'):
            _refs([step['subject_ref']], records, 'step subject_ref', True)
            if step['subject_ref'] not in refs:
                raise ValueError('subject_ref must occur in source_refs')
            refs = [step['subject_ref']]
        kinds = {records[r].get("kind") for r in refs}
        events = {records[r].get("event_type") for r in refs}
        if step["kind"] == "artifact" and "artifact" not in kinds:
            raise ValueError("Artifact step must reference an actual runtime artifact")
        if step["kind"] == "program_result" and not ("validation" in kinds or events & {
                "stage_completed", "stage_failed", "file_operation_completed", "file_operation_failed", "design_choice_observed"}):
            raise ValueError("Program step must reference an actual program return")
        if step["kind"] == "choice" and "decision" not in kinds and not any(
                records[r].get("kind") == "requirement" and records[r].get("request_action") in {"confirm", "reject", "choose", "selection"} for r in refs):
            raise ValueError("Choice must reference a Decision or explicit user choice, not a plain requirement")
        if step["kind"] == "requirement" and "requirement" not in kinds:
            raise ValueError("Requirement step needs a recorded requirement")
        for field in ("input_refs", "outcome_refs"):
            _refs(step.get(field, []), records, field)
        reason = step.get("reason")
        if reason is not None:
            _keys(reason, {"text", "source_refs", "origin"}, "reason")
            _text(reason.get("text"), "reason text")
            if reason.get("origin") not in ORIGINS:
                raise ValueError("Reason needs explicit origin")
            rr = _refs(reason.get("source_refs"), records, "reason source_refs", True)
            if reason["origin"] == "original_statement" and not any(
                    reason["text"].replace("\r\n", "\n") in texts for r in rr for texts in [_source_texts(records[r])]):
                raise ValueError("Original statement must match recorded public text exactly")
        if not isinstance(step.get("limitations", []), list):
            raise ValueError("limitations must be a list")
        for item in step.get("limitations", []):
            _keys(item, {"text", "source_refs"}, "limitation")
            _text(item.get("text"), "limitation text")
            _refs(item.get("source_refs"), records, "limitation source_refs", True)
    for stage in p["stages"]:
        _keys(stage, {"id", "title", "purpose", "step_ids", "branches", "source_refs"}, "stage")
        identity(stage.get("id"))
        _text(stage.get("title"), "stage title")
        _text(stage.get("purpose"), "stage purpose")
        _refs(stage.get("step_ids"), p["steps"], "stage step_ids", True)
        _refs(stage.get("source_refs"), records, "stage source_refs", True)
        if not isinstance(stage.get("branches", []), list):
            raise ValueError("stage branches must be a list")
        for branch in stage.get("branches", []):
            _keys(branch, {"id", "label", "step_ids", "source_refs"}, "branch")
            identity(branch.get("id"))
            _text(branch.get("label"), "branch label")
            _refs(branch.get("step_ids"), stage["step_ids"], "branch step_ids", True)
            _refs(branch.get("source_refs"), records, "branch source_refs", True)
    for link in p["relations"]:
        _keys(link, {"id", "from", "to", "kind", "meaning", "source_refs", "fact_relation_ids"}, "relation")
        identity(link.get("id"))
        _refs([link.get("from"), link.get("to")], p["steps"], "relation endpoints", True)
        if link.get("kind") not in RELATIONS:
            raise ValueError("Semantic relation cannot impersonate a program relation")
        _text(link.get("meaning"), "relation meaning")
        _refs(link.get("source_refs"), records, "relation source_refs", True)
        _refs(link.get("fact_relation_ids", []), {r["id"] for r in facts["fact_relations"]}, "fact_relation_ids")
    for path in p["paths"]:
        _keys(path, {"id", "label", "step_ids", "source_refs", "order_kind"}, "path")
        identity(path.get("id"))
        _text(path.get("label"), "path label")
        _refs(path.get("step_ids"), p["steps"], "path step_ids", True)
        _refs(path.get("source_refs"), records, "path source_refs", True)
        if path.get("order_kind") not in {"logical_process", "planned", "recorded_order"}:
            raise ValueError("Path needs order_kind")
        if path["order_kind"] == "recorded_order":
            positions = []
            for key in path["step_ids"]:
                anchors = [records[r].get("sequence", records[r].get("recorded_sequence"))
                           for r in p["steps"][key]["source_refs"]]
                if not anchors or any(a is None for a in anchors):
                    raise ValueError("Recorded order lacks comparable anchors")
                positions.append(min(anchors))
            if positions != sorted(positions):
                raise ValueError("Recorded order contradicts journal anchors")
    for item in p["unresolved"]:
        _keys(item, {"id", "text", "source_refs", "step_refs"}, "unresolved")
        identity(item.get("id"))
        _text(item.get("text"), "unresolved text")
        _refs(item.get("source_refs"), records, "unresolved source_refs", True)
        _refs(item.get("step_refs"), p["steps"], "unresolved step_refs", True)
    _refs(p["detail_refs"], records, "detail_refs")
    if packet.get("report_plan") is not None:
        validate_report_plan(packet["report_plan"], p, facts)
    return p


def validate_report_plan(plan, process, facts):
    _keys(plan, {"profile", "title", "context", "sections", "diagram", "default_expanded_refs", "detail_refs"}, "report_plan")
    if plan.get("profile", "research-report-v1") != "research-report-v1":
        raise ValueError("Unsupported report profile")
    _text(plan.get("title"), "report title")
    records, steps = facts["source_records"], process["steps"]
    context = plan.get("context")
    if context is not None:
        _keys(context, {"text", "source_refs"}, "report context")
        _text(context.get("text"), "context text")
        _refs(context.get("source_refs"), records, "context source_refs", True)
    ids = set(steps) | {x["id"] for f in ("stages", "relations", "paths", "unresolved") for x in process[f]}
    if not isinstance(plan.get("sections", []), list):
        raise ValueError("report sections must be a list")
    for section in plan.get("sections", []):
        _keys(section, {"id", "title", "step_refs", "summary", "source_refs", "unresolved_refs"}, "section")
        _identifier(section.get("id"))
        if section["id"] in ids or section["id"] in records:
            raise ValueError("Duplicate section id")
        ids.add(section["id"])
        _text(section.get("title"), "section title")
        _refs(section.get("step_refs"), steps, "section step_refs", True)
        _refs(section.get("source_refs"), records, "section source_refs", True)
        if "summary" in section:
            _text(section["summary"], "section summary")
        _refs(section.get("unresolved_refs", []), {x["id"] for x in process["unresolved"]}, "unresolved_refs")
    diagram = plan.get("diagram", {})
    _keys(diagram, {"reading_order", "relation_refs", "short_labels"}, "diagram")
    _refs(diagram.get("reading_order", []), steps, "reading_order")
    _refs(diagram.get("relation_refs", []), {x["id"] for x in process["relations"]}, "relation_refs")
    if not isinstance(diagram.get("short_labels", {}), dict):
        raise ValueError("short_labels must map step IDs to text")
    for key, label in diagram.get("short_labels", {}).items():
        _refs([key], steps, "short_label")
        _text(label, "short_label text")
    _refs(plan.get("default_expanded_refs", []), ids | set(records), "default_expanded_refs")
    _refs(plan.get("detail_refs", []), set(records) | {x["id"] for x in facts["fact_relations"]}, "report detail_refs")
    return copy.deepcopy(plan)


def organize(recorder, packet, actor="host-assistant"):
    if not isinstance(packet, dict) or not isinstance(packet.get("basis"), dict):
        raise ValueError("organization must be an object with a basis object")
    with recorder.writing():
        facts = build_facts(recorder.events, through_sequence=packet.get("basis", {}).get("through_sequence"))
        process = validate_organization(packet, facts)
        prior = [e for e in recorder.events if e["event_type"] == "organization_recorded" and e["payload"]["id"] == packet["id"]]
        revision = len(prior) + 1
        payload = {"id": packet["id"], "revision": revision, "key": f"{packet['id']}@{revision}",
                   "basis": copy.deepcopy(packet["basis"]), "design_process": process,
                   "organization_origin": "later_organization"}
        recorder.append("organization_recorded", payload, actor)
        if packet.get("report_plan") is not None:
            save_report_plan(recorder, payload["key"], packet["report_plan"], actor)
        return payload["key"]


def save_report_plan(recorder, process_ref, plan, actor="host-assistant"):
    with recorder.writing():
        organization = next((e["payload"] for e in recorder.events if e["event_type"] == "organization_recorded"
                             and e["payload"]["key"] == process_ref), None)
        if organization is None:
            raise ValueError("Unknown exact process_ref")
        facts = build_facts(recorder.events, through_sequence=organization["basis"]["through_sequence"])
        value = validate_report_plan(plan, organization["design_process"], facts)
        revision = 1 + sum(e["event_type"] == "report_plan_recorded" and e["payload"]["process_ref"] == process_ref for e in recorder.events)
        key = f"report:{process_ref}:{revision}"
        recorder.append("report_plan_recorded", {"key": key, "revision": revision,
                        "process_ref": process_ref, "report_plan": value}, actor)
        return key


def _all_source_refs(value):
    if isinstance(value, dict):
        for k, v in value.items():
            if k in {"source_refs", "input_refs", "outcome_refs", "detail_refs"} and isinstance(v, list):
                yield from v
            else:
                yield from _all_source_refs(v)
    elif isinstance(value, list):
        for item in value:
            yield from _all_source_refs(item)


def build_process_result(facts, organization=None, report_plan=None):
    graph = copy.deepcopy(facts["legacy_graph"])
    process = copy.deepcopy(organization["design_process"]) if organization else None
    snapshot = copy.deepcopy(facts["snapshot"])
    state = "absent" if not organization else "current" if organization["basis"]["through_sequence"] >= snapshot["last_design_sequence"] else "stale"
    snapshot.update(organization_status=state, organization_ref=organization["key"] if organization else None,
                    organization_basis=organization["basis"] if organization else None,
                    report_plan_ref=report_plan["key"] if report_plan else None)
    represented = set(_all_source_refs(process))
    # References to node journal envelopes cover the same canonical record.
    represented.update(facts["source_records"][r]["payload"]["key"] for r in list(represented)
                       if facts["source_records"].get(r, {}).get("event_type") == "node_recorded")
    canonical = set(facts["canonical_record_refs"])
    technical = set(facts["technical_refs"])
    graph.update(schema_version="design-process-v1", snapshot=snapshot, task=copy.deepcopy(facts["task"]),
                 source_records=copy.deepcopy(facts["source_records"]), fact_relations=copy.deepcopy(facts["fact_relations"]),
                 design_process=process, report_plan=copy.deepcopy(report_plan["report_plan"]) if report_plan else None,
                 coverage={"record_count": len(canonical), "represented_refs": sorted(canonical & represented),
                           "technical_refs": sorted(technical - represented),
                           "unassigned_refs": sorted(canonical - represented - technical),
                           "scope": "Captured records only; neither complete host observation nor scientific proof."},
                 findings=copy.deepcopy(facts["findings"]), handoff=copy.deepcopy(facts["handoff"]))
    return graph


def assemble(events, errors=(), *, process_ref=None, through_sequence=None):
    facts = build_facts(events, errors, through_sequence=through_sequence)
    limit = facts["snapshot"]["through_sequence"]
    organizations = [e for e in events if e["event_type"] == "organization_recorded"
                     and e["payload"]["basis"]["through_sequence"] <= limit]
    if process_ref:
        organizations = [e for e in organizations if e["payload"]["key"] == process_ref]
        if not organizations:
            raise ValueError("Unknown process_ref in selected snapshot")
    # A later retrospective submission for an older basis must not displace a current one.
    selected = max(organizations, key=lambda e: (e["payload"]["basis"]["through_sequence"], e["sequence"]), default=None)
    org = selected["payload"] if selected else None
    plans = [e for e in events if e["event_type"] == "report_plan_recorded" and org and e["payload"]["process_ref"] == org["key"]]
    result = build_process_result(facts, org, plans[-1]["payload"] if plans else None)
    result["organization_history"] = [{"key": e["payload"]["key"], "basis": e["payload"]["basis"],
                                       "actor": e["actor"], "recorded_at": e["timestamp"]} for e in organizations]
    return result
