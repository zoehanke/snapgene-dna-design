"""Small JSON contracts. These validate records, never biological choices."""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
from datetime import datetime, timezone

KINDS = {"requirement", "source", "statement", "claim", "decision", "validation", "artifact"}
REF_FIELDS = {"responds_to": "requirement", "source_id": "source", "claim_ids": "claim",
              "decision_ids": "decision", "validated_by": "validation"}


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(value, key=""):
    """Detached runtime summary: keep parameters, omit raw sequences/secrets."""
    if any(x in key.lower() for x in ("password", "credential", "api_key", "token")):
        return "[omitted]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, pathlib.Path):
        return str(value)
    if isinstance(value, str):
        if len(value) >= 12 and re.fullmatch(r"[ACGTRYSWKMBDHVNacgtryswkmbdhvn\s]+", value):
            return {"omitted": "sequence", "length": len(value),
                    "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest()}
        return value
    if isinstance(value, dict):
        return {str(k): snapshot(v, str(k)) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [snapshot(v, key) for v in value]
    if hasattr(value, "seq"):
        return {"record_id": value.id, "sequence": snapshot(str(value.seq)),
                "topology": value.annotations.get("topology"), "feature_count": len(value.features)}
    if hasattr(value, "to_dict"):
        return snapshot(value.to_dict())
    return {"python_type": type(value).__name__}


def validate_node(node, runtime=False):
    if not isinstance(node, dict) or node.get("kind") not in KINDS:
        raise ValueError("Unknown record kind")
    if not isinstance(node.get("id"), str) or not re.fullmatch(r"[\w.:-]+", node["id"]):
        raise ValueError("Record id must be a nonempty identifier")
    kind = node["kind"]
    if kind in {"validation", "artifact"} and not runtime:
        raise ValueError("Validation and Artifact records are reserved for runtime observations")
    if kind == "source":
        if not node.get("title") or not node.get("source_type"):
            raise ValueError("Source needs title and source_type")
        status = node.get("verification_status", "unverified")
        if status not in {"verified", "unverified"}:
            raise ValueError("Source verification_status must be verified or unverified")
        if status == "verified":
            receipt = node.get("verification", {})
            if not all(receipt.get(k) for k in ("verifier", "method", "checked_at", "locator", "scope")):
                raise ValueError("Verified source requires a scoped verification receipt")
            if node.get("source_type") == "model-inference":
                raise ValueError("Model inference cannot be an externally verified source")
    elif kind not in {"validation", "artifact"} and not node.get("text"):
        raise ValueError(f"{kind} needs text")
    # decision_kind deliberately has no enum: it classifies, never limits design.
    json.dumps(node, ensure_ascii=False, allow_nan=False)
