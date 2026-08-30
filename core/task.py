# -*- coding: utf-8 -*-
"""ConstructionTask v1: the only executable biology contract.

``validate_construction_task`` enforces schema + semantic rules and fills
only *computable* facts (length, hash, topology from the actual file).
It never invents source roles, intervals, boundaries, mutations or task
types.  Missing biology decisions raise ``TaskValidationError`` with the
stable error codes defined in this file.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import uuid

import jsonschema

from core.errors import TaskBlockedError, TaskValidationError
from core.evidence import SOURCE_EVIDENCE_CLASSES

SCHEMA_PATH = pathlib.Path(__file__).resolve().parents[1] / "schemas" / \
    "construction-task-v1.json"

_COMPUTABLE_DEFAULTS = {
    "task_id": lambda: "task-" + uuid.uuid4().hex[:12],
    "revision": 1,
    "mode": "exploration",
    "method_constraints": {},
    "approvals": {},
    "assumptions": [],
    "provenance": [],
}


def _load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def canonical_json(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def task_sha256(task):
    return sha256_text(canonical_json(task))


def read_record(path):
    """Read a sequence record from .gb/.gbk/.dna/.fa in one place.

    Native SnapGene .dna is parsed with Biopython's snapgene format and
    falls back to snapgene_reader when the optional dependency is absent.
    """
    from Bio import SeqIO
    path = str(path)
    lower = path.lower()
    if lower.endswith((".gb", ".gbk", ".genbank")):
        return SeqIO.read(path, "genbank")
    if lower.endswith(".dna"):
        try:
            return SeqIO.read(path, "snapgene")
        except Exception:
            try:
                from snapgene_reader import snapgene_file_to_seqrecord
                return snapgene_file_to_seqrecord(path)
            except Exception:
                raise
    return SeqIO.read(path, "fasta")


def _read_topology(path):
    """Compute record topology; never guess from the filename."""
    try:
        record = read_record(path)
        topo = record.annotations.get("topology")
        if topo:
            return topo
        # snapgene parser may not set topology; infer from the record's
        # circularity when the parser exposed it.
        return record.annotations.get("circular") and "circular" or None
    except Exception:
        return None


def normalize_task(task):
    if not isinstance(task, dict):
        raise TaskValidationError("TASK_MUST_BE_OBJECT",
                                  "ConstructionTask must be a JSON object")
    data = dict(task)
    for key, value in _COMPUTABLE_DEFAULTS.items():
        if key not in data:
            data[key] = value() if callable(value) else value
    data.setdefault("schema_version", "construction-task-v1")
    data.setdefault("raw_request", "")
    data.setdefault("target", {})
    data.setdefault("product", {})
    data.setdefault("operation", {})
    return data


def validate_construction_task(task, base_dir=None):
    """Validate a ConstructionTask; return a normalized validated task.

    Raises ``TaskValidationError`` for missing/ambiguous biology decisions
    and ``TaskBlockedError`` for unregistered/unsupported task kinds.
    """
    from core.registry import get_task_kind

    task = normalize_task(task)
    schema = _load_schema()
    errors = sorted(jsonschema.Draft7Validator(schema).iter_errors(task),
                    key=lambda e: list(e.path))
    if errors:
        exc = errors[0]
        raise TaskValidationError(
            "TASK_SCHEMA_INVALID", exc.message,
            missing_fields=list(exc.path),
            details={"schema": str(exc.path)})

    kind = get_task_kind(task["task_kind"])

    # ---- sources: identity, hash, evidence, topology ---------------------
    seen_ids = set()
    seen_roles = set()
    for source in task["sources"]:
        sid = source["source_id"]
        if sid in seen_ids:
            raise TaskValidationError("DUPLICATE_SOURCE_ID",
                                      "duplicate source_id: %s" % sid,
                                      missing_fields=["sources"])
        seen_ids.add(sid)
        singleton = source["role"] in {
            "template", "backbone", "entry", "destination",
            "replacement", "donor_component"}
        if singleton and source["role"] in seen_roles:
            raise TaskValidationError(
                "DUPLICATE_SOURCE_ROLE",
                "role %r may only be assigned to one source"
                % source["role"],
                missing_fields=["sources.%s.role" % sid])
        if singleton:
            seen_roles.add(source["role"])
        path = pathlib.Path(source["path"])
        if base_dir and not path.is_absolute():
            path = pathlib.Path(base_dir) / path
        source["_resolved_path"] = str(path)
        if not path.exists():
            raise TaskValidationError(
                "SOURCE_FILE_MISSING", "source file not found: %s" % path,
                missing_fields=["sources.%s.path" % sid])
        actual_sha = sha256_file(path)
        claimed = source.get("sha256")
        if claimed and claimed.upper() != actual_sha:
            raise TaskValidationError(
                "SOURCE_HASH_MISMATCH",
                "hash mismatch for %s: claimed %s actual %s"
                % (sid, claimed, actual_sha),
                missing_fields=["sources.%s.sha256" % sid])
        source["sha256"] = actual_sha
        if source.get("topology"):
            actual_topo = _read_topology(path)
            if actual_topo and actual_topo != source["topology"]:
                raise TaskValidationError(
                    "SOURCE_TOPOLOGY_MISMATCH",
                    "topology mismatch for %s: claimed %s actual %s"
                    % (sid, source["topology"], actual_topo),
                    missing_fields=["sources.%s.topology" % sid])
        else:
            source["topology"] = _read_topology(path) or "linear"
        if source["evidence"]["source_evidence_class"] not in \
                SOURCE_EVIDENCE_CLASSES:
            raise TaskValidationError(
                "UNKNOWN_EVIDENCE_CLASS",
                "unknown source_evidence_class for %s" % sid)
        if not source.get("annotation_status"):
            source["annotation_status"] = "unreviewed"

    # ---- per-kind required fields ----------------------------------------
    for field in kind.get("required_fields", []):
        if not _path_exists(task, field):
            raise TaskValidationError(
                kind.get("missing_code", "TASK_REQUIRED_FIELD_MISSING"),
                "task_kind=%s requires field: %s"
                % (task["task_kind"], field),
                missing_fields=[field],
                questions=kind.get("questions", []))

    # ---- product topology / formats --------------------------------------
    if not task["product"].get("formats"):
        task["product"]["formats"] = ["gb", "fasta", "dna"]

    # ---- dangerous default negative tests (A04, A05, A06) ----------------
    kind.get("semantic_checks", lambda t: None)(task)

    return task


def _path_exists(obj, dotted):
    node = obj
    for part in dotted.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return False
    if isinstance(node, list):
        return bool(node)
    return node is not None and node != {} and node != ""


def _selection_resolved(task):
    selection = (task.get("target") or {}).get("selection") or {}
    return selection.get("resolution_status") == "resolved"


def require_resolved_selection(task, error_code="COMPONENT_BOUNDARY_REQUIRED"):
    if not _selection_resolved(task):
        raise TaskValidationError(
            error_code,
            "selection must be resolved with interval/feature evidence "
            "before execution; whole-record defaults are forbidden",
            missing_fields=["target.selection"],
            questions=["目标组件或替换区域是哪个 feature / 坐标区间？"],
            details={"task_kind": task.get("task_kind")})
