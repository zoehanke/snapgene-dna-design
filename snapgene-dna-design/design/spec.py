# -*- coding: utf-8 -*-
"""design/spec.py - DesignSpec v1 data model and state machine.

This module is intentionally free of molecular-biology algorithms. It only
manages the construction-design contract: what the user said, what was
assumed, what was computed, what was sourced, and which states the design
passed through. All actual primer/restriction/assembly/CRISPR work remains in
the existing scripts and is called by the orchestrator.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import uuid

SCHEMA_VERSION = "1.0.0"
STATUSES = (
    "draft",
    "needs-clarification",
    "user-confirmed",
    "evidence-resolved",
    "planned",
    "executed",
    "verified",
    "delivered",
    "blocked",
)

TRANSITIONS = {
    "draft": {"needs-clarification", "blocked"},
    "needs-clarification": {"user-confirmed", "draft", "blocked"},
    "user-confirmed": {"evidence-resolved", "needs-clarification", "blocked"},
    "evidence-resolved": {"planned", "needs-clarification", "blocked"},
    "planned": {"executed", "needs-clarification", "blocked"},
    "executed": {"verified", "blocked"},
    "verified": {"delivered", "blocked"},
    "delivered": {"blocked"},
    "blocked": {"draft", "needs-clarification", "user-confirmed",
                "evidence-resolved", "planned", "executed", "verified"},
}

EVIDENCE_LAYERS = (
    "user-provided",
    "assumption",
    "computed",
    "database-verified",
    "manufacturer-protocol",
    "published-evidence",
    "heuristic",
    "unverified",
)

TRACKED_KEYS = (
    "objective", "host", "sources", "target", "replacement",
    "constraints", "outputs",
)


class DesignSpecError(ValueError):
    """Raised for invalid DesignSpec operations."""


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def canonical_json(spec, indent=None):
    return json.dumps(spec, ensure_ascii=False, sort_keys=True,
                      separators=None if indent else (",", ":"),
                      indent=indent)


def sha256_text(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest().upper()


def spec_sha256(spec):
    """Canonical SHA-256 of the spec, excluding revision bookkeeping only.

    The revision and status intentionally participate: changing either
    changes the hash, which is what delivery manifests bind.
    """
    return sha256_text(canonical_json(spec))


def _evidence(evidence_layer, description, **extra):
    if evidence_layer not in EVIDENCE_LAYERS:
        raise DesignSpecError("unknown evidence_layer: %s" % evidence_layer)
    item = {"evidence_layer": evidence_layer, "description": description}
    item.update(extra)
    return item


def new_spec(raw_objective, mode="exploration", objective=None,
             host=None, constraints=None, outputs=None):
    if mode not in ("exploration", "formal"):
        raise DesignSpecError("mode must be exploration or formal")
    spec = {
        "schema_version": SCHEMA_VERSION,
        "spec_id": "design-" + uuid.uuid4().hex[:12],
        "revision": 1,
        "mode": mode,
        "status": "draft",
        "raw_objective": str(raw_objective or ""),
        "objective": copy.deepcopy(objective or {}),
        "host": copy.deepcopy(host or {}),
        "sources": [],
        "target": {},
        "replacement": {},
        "constraints": copy.deepcopy(constraints or {}),
        "outputs": copy.deepcopy(outputs or {
            "formats": ["gb", "fasta", "dna"],
            "include_primers": True,
            "include_materials": True,
        }),
        "assumptions": [],
        "derived_facts": [],
        "missing_information": [],
        "questions": [],
        "approvals": {},
        "provenance": [{
            "evidence_layer": "computed",
            "description": "DesignSpec created",
            "at": now_iso(),
        }],
    }
    return spec


def clone_spec(spec):
    return copy.deepcopy(spec)


def set_field(spec, path, value, evidence_layer="user-provided",
              description=None, force=False):
    """Set a nested field with evidence bookkeeping.

    Path elements are dict keys. User-provided/assumption facts are recorded
    in ``assumptions``; program-computed facts go to ``derived_facts``.
    """
    if len(path) < 1:
        raise DesignSpecError("empty field path")
    if spec["status"] in ("user-confirmed", "evidence-resolved", "planned",
                          "executed", "verified", "delivered") and not force:
        raise DesignSpecError(
            "confirmed spec cannot be silently modified; "
            "create a new revision first")
    record = _evidence(
        evidence_layer,
        description or "set %s" % ".".join(path),
        field=".".join(path), at=now_iso())
    container = spec
    for key in path[:-1]:
        if key not in container or not isinstance(container[key], dict):
            container[key] = {}
        container = container[key]
    container[path[-1]] = copy.deepcopy(value)
    if evidence_layer in ("computed", "database-verified"):
        spec["derived_facts"].append(record)
    else:
        spec["assumptions"].append(record)


def add_evidence(spec, layer, description, **extra):
    item = _evidence(layer, description, at=now_iso(), **extra)
    if layer in ("computed", "database-verified"):
        spec["derived_facts"].append(item)
    else:
        spec["assumptions"].append(item)
    return item


def add_question(spec, question_id, question, category="must-ask",
                 reason=None):
    item = {"question_id": question_id, "category": category,
            "question": question}
    if reason:
        item["reason"] = reason
    spec["questions"].append(item)
    return item


def add_missing(spec, key, reason):
    spec["missing_information"].append({"key": key, "reason": reason})
    return spec["missing_information"][-1]


_ANSWER_FIELD_MAP = {
    "clarify-backbone-file": "objective.backbone_source",
    "clarify-host": "host.organism",
    "clarify-method-preference": "constraints.method",
    "clarify-target-feature": "target.feature_name",
    "clarify-upload-permission": "approvals.sequence_upload",
}


def _set_dotted(spec, field, value):
    node = spec
    parts = field.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def record_answer(spec, question_id, value, evidence_layer="user-provided",
                  description=None):
    field = _ANSWER_FIELD_MAP.get(question_id)
    if evidence_layer not in EVIDENCE_LAYERS:
        raise DesignSpecError("unknown evidence_layer: %s" % evidence_layer)
    if field is not None and value != "auto-confirmed" and spec["status"] in (
            "user-confirmed", "evidence-resolved", "planned", "executed", "verified", "delivered"):
        current = spec
        for part in field.split("."):
            current = current.get(part) if isinstance(current, dict) else None
        if current != value:
            raise DesignSpecError("confirmed spec: changing an answer requires revision")
    if field is not None and value != "auto-confirmed":
        _set_dotted(spec, field, value)
    spec["approvals"][question_id] = {
        "value": copy.deepcopy(value),
        "evidence_layer": evidence_layer,
        "at": now_iso(),
        "description": description or "answer for %s" % question_id,
    }
    # Remove the question from open questions.
    spec["questions"] = [q for q in spec["questions"]
                         if q.get("question_id") != question_id]
    return spec["approvals"][question_id]


def set_status(spec, status, reason=None, force=False):
    """Enforce legal state transitions."""
    if status not in STATUSES:
        raise DesignSpecError("unknown status %r" % status)
    if not force and status not in TRANSITIONS.get(spec["status"], ()):
        raise DesignSpecError(
            "illegal DesignSpec transition %s -> %s" % (spec["status"], status))
    spec["status"] = status
    spec["provenance"].append(_evidence(
        "computed", "status -> %s" % status,
        reason=reason or "", at=now_iso()))
    return spec


def needs_clarification(spec, questions, missing, reason=""):
    for item in questions or []:
        add_question(spec, item["question_id"], item["question"],
                     item.get("category", "must-ask"),
                     item.get("reason"))
    for item in missing or []:
        add_missing(spec, item["key"], item["reason"])
    if spec["questions"] or spec["missing_information"]:
        set_status(spec, "needs-clarification", reason)
    return spec


def confirm_user(spec, require_questions_resolved=True):
    if require_questions_resolved:
        open_must = [q for q in spec["questions"]
                     if q.get("category") == "must-ask"]
        if open_must:
            raise DesignSpecError(
                "must-ask questions remain: %s"
                % ", ".join(q.get("question_id") for q in open_must))
    set_status(spec, "user-confirmed",
               "user confirmed key conditions")
    return spec


def revise(spec, reason, keep_id=True):
    """Create a new revision; never silently overwrite a confirmed spec."""
    new = clone_spec(spec)
    new["revision"] = int(spec["revision"]) + 1
    if not keep_id:
        new["spec_id"] = "design-" + uuid.uuid4().hex[:12]
    new["status"] = "draft"
    new["approvals"] = {}
    new["questions"] = []
    new["missing_information"] = []
    new["provenance"] = [{
        "evidence_layer": "computed",
        "description": "revision %d created from revision %d: %s"
                       % (new["revision"], spec["revision"], reason),
        "previous_spec_sha256": spec_sha256(spec),
        "at": now_iso(),
    }]
    return new


def diff_specs(old_spec, new_spec):
    """Return a structured diff; changed tracked fields are itemised."""
    changes = []
    for key in TRACKED_KEYS:
        if old_spec.get(key) != new_spec.get(key):
            changes.append({
                "field": key,
                "change_type": _change_type(key),
                "before": clone_spec(old_spec.get(key)),
                "after": clone_spec(new_spec.get(key)),
            })
    return {
        "from_spec_id": old_spec.get("spec_id"),
        "to_spec_id": new_spec.get("spec_id"),
        "from_revision": old_spec.get("revision"),
        "to_revision": new_spec.get("revision"),
        "from_sha256": spec_sha256(old_spec),
        "to_sha256": spec_sha256(new_spec),
        "changes": changes,
    }


def _change_type(field):
    return {
        "sources": "source-update",
        "target": "user-modification",
        "replacement": "user-modification",
        "constraints": "user-modification",
        "outputs": "auto-default-or-user-modification",
        "host": "user-modification",
        "objective": "user-modification",
    }.get(field, "calculated-change")


def make_sequence_source(source_id, source_type, sha256, source_path=None,
                         accession=None, interval_0based=None, strand=1,
                         transformations=None):
    if source_type not in ("user-file", "database-record",
                           "deterministic-transform", "manual-sequence"):
        raise DesignSpecError("invalid source_type: %s" % source_type)
    item = {
        "source_id": source_id,
        "source_type": source_type,
        "source_path": source_path,
        "accession": accession,
        "sha256": str(sha256).upper(),
        "interval_0based": interval_0based,
        "strand": strand,
        "transformations": list(transformations or []),
    }
    return item


def add_source(spec, source, force=False):
    if spec["status"] in ("user-confirmed", "evidence-resolved", "planned",
                          "executed", "verified", "delivered") and not force:
        raise DesignSpecError("confirmed spec: new source requires revision")
    spec["sources"].append(copy.deepcopy(source))
    return source


def formal_blockers(spec):
    """Return the list of blockers that keep a formal spec undeliverable."""
    blockers = []
    if spec.get("mode") != "formal":
        blockers.append("SPEC_NOT_FORMAL_MODE")
    if spec.get("status") not in ("verified", "delivered"):
        blockers.append("SPEC_NOT_VERIFIED")
    if not spec.get("raw_objective"):
        blockers.append("RAW_OBJECTIVE_MISSING")
    if not spec.get("host"):
        blockers.append("HOST_NOT_CONFIRMED")
    open_must = [q for q in spec.get("questions", [])
                 if q.get("category") == "must-ask"]
    if open_must:
        blockers.append("MUST_ASK_QUESTIONS_OPEN")
    if not spec.get("sources"):
        blockers.append("NO_SEQUENCE_SOURCES")
    for source in spec.get("sources", []):
        if not source.get("sha256"):
            blockers.append("SOURCE_HASH_MISSING:%s" % source.get("source_id"))
        if source.get("source_type") == "database-record" and \
                not source.get("accession"):
            blockers.append("DATABASE_SOURCE_WITHOUT_ACCESSION:%s"
                            % source.get("source_id"))
    approvals = spec.get("approvals", {})
    order_approval = approvals.get("primers-ready-to-order")
    if not isinstance(order_approval, dict) or order_approval.get("value") is not True:
        blockers.append("PRIMERS_NOT_APPROVED_FOR_ORDER")
    if spec.get("outputs", {}).get("roundtrip_verified") is not True:
        blockers.append("ROUNDTRIP_NOT_VERIFIED")
    return sorted(set(blockers))


def delivery_flags(spec):
    blockers = formal_blockers(spec)
    if spec.get("mode") == "exploration":
        return {
            "delivery_grade": "exploratory",
            "ready_to_order": False,
            "ready_for_wet_lab": False,
            "blockers": blockers,
        }
    if not blockers:
        return {
            "delivery_grade": "formal",
            "ready_to_order": True,
            "ready_for_wet_lab": True,
            "blockers": [],
        }
    return {
        "delivery_grade": "formal-incomplete",
        "ready_to_order": False,
        "ready_for_wet_lab": False,
        "blockers": blockers,
    }
