"""Complete captured facts, independent of authored scientific organization."""
from __future__ import annotations

import copy
import re

from evidence_trace.recorder import project
from evidence_trace.chain import build_chains

AUTHORED_EVENTS = {"organization_recorded", "report_plan_recorded"}
TECHNICAL_EVENTS = {"run_started", "run_finished"}


def _file_hash_relations(records):
    """Match observed outputs to declared input bytes, independent of path/order of artifact recording."""
    from evidence_trace.reader import file_inputs
    def digest(value):
        return value.lower() if isinstance(value,str) and re.fullmatch(r'[0-9a-fA-F]{64}',value) else None
    outputs = {}
    for key,node in records.items():
        if node.get('kind') != 'artifact' or node.get('generation_observation') not in ('created','modified','rewritten_same_content'):
            continue
        value=digest(node.get('sha256')); producer=records.get(node.get('result_event_ref'),{})
        if value and producer.get('event_type') in ('stage_completed','file_operation_completed'):
            outputs.setdefault(value,[]).append((key,producer))
    result=[]
    for key,event in records.items():
        if event.get('event_type') != 'stage_started':
            continue
        payload=event['payload']
        inputs=list(file_inputs(payload.get('input',{})))
        inputs.extend((row.get('path'),row.get('sha256')) for row in payload.get('input_files',[]) if isinstance(row,dict))
        for value in dict.fromkeys(digest(value) for _,value in inputs):
            if value is None:
                continue
            for artifact,producer in outputs.get(value,[]):
                if producer['sequence'] >= event['sequence']:
                    continue
                result.append({'id':'file-input:'+artifact+':'+key,'from':artifact,'to':key,
                    'kind':'input_reference','origin':'program_derived','scope':'same_file_content',
                    'verification_method':'sha256_equality','sha256':value,
                    'source_refs':[artifact,producer['event_id'],key]})
    return result


def build_facts(events, errors=(), *, through_sequence=None):
    end = events[-1]["sequence"] if events else 0
    if through_sequence is None:
        through_sequence = end
    if type(through_sequence) is not int or not 0 <= through_sequence <= end:
        raise ValueError("through_sequence must identify an existing event prefix")
    prefix = [e for e in events if e["sequence"] <= through_sequence]
    design = [e for e in prefix if e["event_type"] not in AUTHORED_EVENTS]
    graph = build_chains(project(design, errors))
    records = {n["key"]: copy.deepcopy(n) for n in graph["nodes"]}
    canonical, technical = list(records), []
    for event in design:
        records[event["event_id"]] = copy.deepcopy(event)
        # A node and its journal envelope are two addresses of the same fact.
        if event["event_type"] != "node_recorded":
            canonical.append(event["event_id"])
            if event["event_type"] in TECHNICAL_EVENTS:
                technical.append(event["event_id"])
    relations = []
    for event in design:
        p, key = event["payload"], event["event_id"]
        if p.get("stage_ref") in records:
            relations.append({"id": "stage:" + key, "from": p["stage_ref"], "to": key,
                              "kind": "stage_result", "source_refs": [p["stage_ref"], key],
                              "origin": "program_derived"})
    for node in graph["nodes"]:
        if node.get("observed_quote_ref") in records:
            ref = node["observed_quote_ref"]
            relations.append({"id": "quote:" + node["key"], "from": ref, "to": node["key"],
                              "kind": "quotes_from", "source_refs": [ref, node["key"]],
                              "scope": "Exact text occurrence; no authentication of author or scientific support",
                              "origin": "program_derived"})
        ref = node.get("result_event_ref")
        if ref in records:
            relations.append({"id": "result:" + node["key"], "from": ref, "to": node["key"],
                              "kind": ("observed_file" if node.get("generation_observation") == "presence_only" else "produced_by") if node["kind"] == "artifact" else "stage_result",
                              "source_refs": [ref, node["key"]], "origin": "program_derived"})
        for ref in node.get("input_artifact_refs", []):
            if ref in records:
                relations.append({"id": "input:" + ref + ":" + node["key"], "from": ref,
                                  "to": node["key"], "kind": "input_reference",
                                  "source_refs": [ref, node["key"]], "origin": "program_derived"})
    for edge in graph["reader"]["relations"]:
        relations.append({"id": "reader:" + str(len(relations)), **copy.deepcopy(edge),
                          "source_refs": edge.get("refs", []),
                          "origin": "declared" if edge.get("scope") == "declared" else "program_derived"})
    for view in graph.get("chain_views", []):
        for choice in view["choices"]:
            observed = choice.get("observation_event_ref")
            if observed in records:
                for decision in choice.get("matched_decision_refs", []):
                    relations.append({"id": "target:" + decision + ":" + observed,
                                      "from": decision, "to": observed, "kind": "target_matches_input",
                                      "source_refs": [decision, observed], "origin": "program_derived",
                                      "scope": "Declared target value matches observed input; not proof of rationale or success"})
    relations.extend(_file_hash_relations(records))
    requirements = [n for n in graph["nodes"] if n["kind"] == "requirement"
                    and graph["latest"].get(n["id"]) == n["key"]]
    handoffs = [e for e in design if e["event_type"] == "handoff_recorded"]
    findings = [{"category": "capture", "text": str(e)} for e in errors]
    findings.extend({"category": "capture", "text": str(e)} for e in graph["issues"] if e not in errors)
    for group in graph["reader"]["review"]:
        findings.extend({**copy.deepcopy(item), "domain": "review"} for item in group["items"])
    if handoffs:
        findings.extend({"category": "handoff", "text": item["status"], **copy.deepcopy(item)}
                        for item in handoffs[-1]["payload"]["files"] if item["status"] != "linked")
    return {"snapshot": {"trace_id": events[0]["trace_id"] if events else None,
                         "through_sequence": through_sequence,
                         "last_design_sequence": design[-1]["sequence"] if design else 0},
            "task": {"goal": requirements[0]["text"] if len(requirements) == 1 else None,
                     "requirements": copy.deepcopy(requirements),
                     "source_refs": [n["key"] for n in requirements]},
            "source_records": records, "fact_relations": relations,
            "canonical_record_refs": canonical, "technical_refs": technical,
            "handoff": copy.deepcopy(handoffs[-1]["payload"]) if handoffs else None,
            "findings": findings, "legacy_graph": graph}
