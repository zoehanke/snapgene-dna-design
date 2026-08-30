# -*- coding: utf-8 -*-
"""Evidence stamps: source evidence class and method maturity.

The two dimensions are deliberately independent:
- ``source_evidence_class`` says where a sequence came from.
- ``method_maturity`` says how much the algorithm can promise.

A derived product's evidence class may never exceed its weakest critical
source, so an internal fixture can never silently become a public-record
reproduction.
"""
from __future__ import annotations

SOURCE_EVIDENCE_CLASSES = (
    "user-provided",
    "public-record",
    "internal-fixture",
    "synthetic-fixture",
    "heuristic",
)

METHOD_MATURITY_VALUES = (
    "validated",
    "experimental",
)

ARTIFACT_CLASSES = (
    "intermediate",
    "preview",
    "experimental-preview",
    "authoritative",
)

# Higher is stronger evidence.
_CLASS_RANK = {
    "heuristic": 0,
    "synthetic-fixture": 1,
    "internal-fixture": 2,
    "user-provided": 3,
    "public-record": 4,
}


def normalize_evidence_class(value):
    if value not in SOURCE_EVIDENCE_CLASSES:
        raise ValueError("unknown source_evidence_class: %r" % value)
    return value


def normalize_method_maturity(value):
    if value not in METHOD_MATURITY_VALUES:
        raise ValueError("unknown method_maturity: %r" % value)
    return value


def weakest_evidence_class(values):
    classes = [normalize_evidence_class(v) for v in values if v]
    if not classes:
        return "heuristic"
    return min(classes, key=lambda v: _CLASS_RANK[v])


def stamp_source(source_id, evidence, sha256=None, path=None, topology=None,
                 annotation_status="unreviewed"):
    return {
        "source_id": source_id,
        "evidence": {
            "source_evidence_class": normalize_evidence_class(
                evidence.get("source_evidence_class", "user-provided")),
            "accession": evidence.get("accession"),
            "version": evidence.get("version"),
            "citation": evidence.get("citation"),
            "retrieved_at": evidence.get("retrieved_at"),
        },
        "sha256": sha256,
        "path": path,
        "topology": topology,
        "annotation_status": annotation_status,
    }


def stamp_product(task, plan, source_stamps, method_maturity="validated",
                  artifact_class="preview", execution=None,
                  validation=None, software=None):
    """Build the evidence stamp recorded in the delivery manifest.

    The stamp carries the weakest-source evidence class, the full
    transformation chain, software identity, validation scope and parent
    artifact hashes so a delivered product can always be traced back to
    concrete inputs.
    """
    if not software:
        try:
            from provenance import read_version
            software = {"name": "snapgene-dna-design",
                        "version": read_version()}
        except Exception:  # noqa: BLE001
            software = {"name": "snapgene-dna-design", "version": "unknown"}
    import sys
    software["python"] = sys.version.split()[0]
    source_rows = []
    for s in source_stamps:
        row = {
            "source_id": s.get("source_id"),
            "role": s.get("role"),
            "source_evidence_class": (s.get("evidence") or {}).get(
                "source_evidence_class"),
            "source_class": (s.get("evidence") or {}).get(
                "source_evidence_class"),
            "source_version": (s.get("evidence") or {}).get("version"),
            "source_hash": s.get("sha256"),
            "record_id": s.get("record_id"),
            "topology": s.get("topology"),
            "annotation_status": s.get("annotation_status"),
        }
        for key in ("accession", "citation", "retrieved_at"):
            value = (s.get("evidence") or {}).get(key)
            if value:
                row[key] = value
        source_rows.append(row)
    transformations = []
    for step in plan.get("steps", []):
        transformations.append({
            "step": step.get("step"),
            "source_id": step.get("source_id"),
            "interval_0based": step.get("interval_0based"),
            "strand": step.get("strand"),
            "parameters": {k: v for k, v in step.items()
                           if k not in ("step", "source_id",
                                        "interval_0based", "strand")},
        })
    selected = plan.get("selection") or {}
    product_stamp = {
        "artifact_class": artifact_class,
        "method_maturity": normalize_method_maturity(method_maturity),
        "source_evidence_class": weakest_evidence_class(
            [s["evidence"]["source_evidence_class"] for s in source_stamps]),
        "task_id": task.get("task_id"),
        "task_revision": task.get("revision"),
        "plan_id": plan.get("plan_id"),
        "sources": source_rows,
        "selected_interval": selected.get("interval_0based"),
        "selected_strand": selected.get("strand"),
        "transformations": transformations,
        "software": software,
        "validation_scope": (validation or {}).get("artifact_hashes") and {
            "artifact_valid": validation.get("artifact_valid"),
            "computation_valid": validation.get("computation_valid"),
            "goal_valid": validation.get("goal_valid"),
            "overall": validation.get("overall"),
        } or None,
        "parent_artifact_hashes": (execution or {}).get("artifact_hashes"),
    }
    return product_stamp
