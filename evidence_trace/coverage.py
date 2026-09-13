"""Observe explicit design inputs and match targets; never infer rationale."""
from __future__ import annotations

import json
import os

from evidence_trace.models import digest

FIELDS = {
    "host": "context", "chassis": "context", "organism": "context", "strain": "context",
    "source_id": "source", "replacement_source_id": "source", "insert_source_id": "source",
    "vector_source_id": "source", "donor_source_id": "source", "entry_source_id": "source", "destination_source_id": "source",
    "template_seq_or_file": "source", "target_cds_seq_or_file": "source", "template": "source",
    "vector_source": "source", "insert_template": "source", "source": "source", "path": "source",
    "start": "boundary", "end": "boundary", "start_0based": "boundary", "end_0based": "boundary",
    "insert_start": "boundary", "insert_end": "boundary", "interval_0based": "boundary", "boundary_0based": "boundary",
    "strand": "orientation", "orientation": "orientation", "tag_position": "orientation",
    "stop_policy": "stop_policy", "method": "method", "task_kind": "method", "tool": "method",
    "topology": "topology", "circular": "topology", "circular_product": "topology",
    "alt_seq": "mutation", "mutations": "mutation", "position_1based": "mutation", "ref": "mutation", "alt": "mutation",
    "tag_name_or_seq": "component", "feature": "component", "name_or_type": "component", "name_or_label": "component",
    "order": "order", "recipe_name": "method", "target_flank_bp": "parameter", "overlap_length": "parameter", "enzyme": "parameter", "enzyme5": "parameter", "enzyme3": "parameter",
    "vector_enzymes": "parameter", "insert_enzymes": "parameter", "target_tm": "parameter", "nuclease": "parameter"
}
TECHNICAL_TOOLS = {"calc_primer_tm", "check_primer_dimers", "inspect_dna", "find_open_reading_frames", "check_reading_frame"}


def extract_choices(design, prefix="", subject="design"):
    choices = []
    def walk(value, path, scope):
        if isinstance(value, dict):
            if value.get("tool") in TECHNICAL_TOOLS:
                return
            if value.get("step_id"):
                scope = "step:" + str(value["step_id"])
            elif value.get("source_id") and any(k in value for k in ("path", "_resolved_path")):
                scope = "source:" + str(value["source_id"])
            for key, item in value.items():
                pointer = path + "." + key if path else key
                if key.startswith("_") or key in {"approvals", "provenance", "evidence", "features", "annotations"}:
                    continue
                if key in FIELDS and item is not None:
                    row = {"parameter": key, "value": item, "subject": scope, "input_path": pointer, "choice_kind": FIELDS[key]}
                    row["id"] = "O-" + digest(row)[:16]
                    choices.append(row)
                if key not in {"mutations", "interval_0based"}:
                    walk(item, pointer, scope)
        elif isinstance(value, list):
            if path.endswith(("steps", "fragments")) and value:
                order = [v.get("step_id", v.get("source_id", str(i))) if isinstance(v, dict) else str(i) for i, v in enumerate(value)
                         if not isinstance(v, dict) or v.get("tool") not in TECHNICAL_TOOLS]
                row = {"parameter": "fragment_order" if path.endswith("fragments") else "step_order",
                       "value": order, "subject": scope, "input_path": path, "choice_kind": "order"}
                row["id"] = "O-" + digest(row)[:16]
                choices.append(row)
            for i, item in enumerate(value):
                walk(item, path + "." + str(i), scope)
    walk(design, prefix, subject)
    return choices


def normalize(value):
    if isinstance(value, dict) and "source_path" in value:
        value = value["source_path"]
    if isinstance(value, str) and ("/" in value or "\\" in value):
        return os.path.normcase(os.path.normpath(value)).replace("\\", "/")
    return value


def match_choices(choices, decisions):
    from evidence_trace.provenance import decision_provenance
    output = []
    for choice in choices:
        candidates = []
        for decision in decisions:
            target = decision.get("targets") or {}
            targets = target if isinstance(target, list) else [target]
            for t in targets:
                if not isinstance(t, dict):
                    continue
                scope = t.get("step_id") or t.get("subject")
                if scope and str(scope) not in {choice["subject"], choice["subject"].split(":", 1)[-1]}:
                    continue
                parameter = t.get("parameter")
                field = choice["parameter"]
                matches_field = parameter in {field, choice["input_path"]} or field in t
                if not matches_field:
                    continue
                expected = t.get("value", t.get(field, t.get("file") if choice["choice_kind"] == "source" else None))
                exact = expected is not None and normalize(expected) == normalize(choice["value"])
                if expected is not None and not exact:
                    continue
                ambiguous_scope = not scope and sum(c["parameter"] == field and normalize(c["value"]) == normalize(choice["value"]) for c in choices) > 1 and parameter != choice["input_path"]
                candidates.append((decision, exact and not ambiguous_scope))
        matched = [d for d, ok in candidates if ok]
        exact = [d for d in matched if str(d.get("rationale") or "").strip()]
        associated = list(dict.fromkeys(d["key"] for d, _ in candidates))
        status = "explained" if exact else "needs review" if candidates else "unexplained design choice"
        provenance = [{"decision_ref": d["key"], **decision_provenance(d)} for d in matched]
        output.append({**choice, "status": status, "decision_refs": associated,
                       "target_match": "matched" if matched else "ambiguous" if candidates else "unmatched",
                       "matched_decision_refs": list(dict.fromkeys(d["key"] for d in matched)),
                       "explanation_provenance": provenance,
                       "original_explanation_recorded": any(p["original_explanation_recorded"] for p in provenance),
                       "reason": "明确目标和值匹配且有已提交说明；来源另列" if exact else "仅字段关联、作用域含糊或缺 rationale" if candidates else "没有可可靠关联的 Decision.targets；未补造解释"})
    return output


def choices_for_run(run):
    # New events are explicit observations. Older Phase 1 logs can be projected from saved inputs.
    observed = [{**s["choice"], "observed_stage": s.get("stage"), "observation_basis": s.get("observation"),
                 "stage_ref": s.get("stage_ref"), "observation_event_ref": s.get("event_id"),
                 "observation_phase": s.get("observation_phase", "unknown"),
                 "recorded_at": s.get("recorded_at"), "recorded_sequence": s.get("recorded_sequence"),
                 "run_outcome": run.get("status")} for s in run.get("stages", []) if s.get("event_type") == "design_choice_observed"]
    if not observed:
        for s in run.get("stages", []):
            if s.get("event_type") != "stage_started":
                continue
            data = s.get("input", {})
            if s.get("stage") == "task" and data.get("args"):
                observed.extend(extract_choices(data["args"][0], subject="task"))
            elif s.get("stage") == "recipe_execute":
                observed.extend(extract_choices(data.get("kwargs", {}), subject="recipe"))
    unique = {}
    for choice in observed:
        choice = {"observation_basis": "Saved submitted input; execution is not inferred", "run_outcome": run.get("status"), **choice}
        unique[choice["id"]] = choice
    return list(unique.values())
