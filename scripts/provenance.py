# -*- coding: utf-8 -*-
"""provenance.py - Structured source tracking for every computed result.

Every recommendation, score, primer pair, off-target search and protocol
suggestion must reference a Source object. ``source: AI``, ``source: internet``
and ``version: latest`` are rejected by the validator.
"""
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"


def read_version():
    """Single source of truth for the project version.

    All provenance objects and manifests must use this value; no script may
    hardcode a version string.
    """
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip() or "unknown"
    return "unknown"


ALLOWED_SOURCE_TYPES = {
    "software",
    "prediction-model",
    "reference-database",
    "manufacturer-protocol",
    "public-protocol",
    "published-paper",
    "heuristic",
    "user-input",
}
ALLOWED_STATUSES = {
    "verified", "partial", "unavailable", "unknown", "conflicting", "stale",
}


class ProvenanceError(ValueError):
    pass


def sha256_of_file(path):
    path = pathlib.Path(path)
    if not path.exists():
        raise FileNotFoundError("file not found for SHA-256 binding: %s" % path)
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def sha256_of_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest().upper()


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def source(source_type, name, role, url=None, version=None, license_value=None,
           status="unknown", verification=None, retrieved_at=None,
           additional=None):
    """Create a valid provenance source object.

    ``version`` must be a concrete detected/declared version, never
    ``"latest"``. ``status`` must be one of the ALLOWED_STATUSES values.
    """
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise ProvenanceError("invalid source_type: %s" % source_type)
    if status not in ALLOWED_STATUSES:
        raise ProvenanceError("invalid status: %s" % status)
    if not name or not name.strip() or name.strip().lower() in {"ai", "internet", "latest"}:
        raise ProvenanceError("source name is required and must not be AI, internet, or latest")
    if not role or not role.strip():
        raise ProvenanceError("source role is required")
    if version is not None and version.strip().lower() == "latest":
        raise ProvenanceError("version 'latest' is not a source")
    result = {
        "source_type": source_type,
        "name": name.strip(),
        "role": role.strip(),
        "status": status,
        "url": url,
        "version": version,
        "license": license_value,
        "verification": verification,
        "retrieved_at": retrieved_at,
    }
    if additional:
        result.update(additional)
    return {key: value for key, value in result.items() if value is not None}


def source_id(source_obj):
    """Stable local id for a source object."""
    payload = json.dumps(source_obj, sort_keys=True, default=str)
    return "src-" + sha256_of_text(payload)[:12]


CONDITIONAL_REQUIRED = {
    "manufacturer-protocol": ("url", "retrieved_at", "version"),
    "prediction-model": ("name", "version"),
    "public-protocol": ("url", "retrieved_at"),
}


def validate(source_obj):
    errors = []
    required = ("source_type", "name", "role", "status")
    for key in required:
        if key not in source_obj:
            errors.append("missing required key: %s" % key)
    source_type = source_obj.get("source_type")
    if source_type not in ALLOWED_SOURCE_TYPES:
        errors.append("invalid source_type")
    if source_obj.get("status") not in ALLOWED_STATUSES:
        errors.append("invalid status")
    if str(source_obj.get("version", "")).strip().lower() == "latest":
        errors.append("version must not be 'latest'")
    if str(source_obj.get("name") or "").strip().lower() in ("", "ai", "internet"):
        errors.append("source name must not be AI or internet")
    for key in CONDITIONAL_REQUIRED.get(source_type, ()):
        value = source_obj.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append("source_type %s requires %s" % (source_type, key))
    if errors:
        raise ProvenanceError("; ".join(errors))
    return True


def probe_executable(executable, version_args=None):
    """Return (path, version, verification) without crashing the caller."""
    import shutil as _shutil
    exe = _shutil.which(executable)
    if not exe:
        return None, None, {"method": "path-probe", "status": "unavailable"}
    try:
        completed = subprocess.run(
            [exe] + list(version_args or ["--version"]),
            capture_output=True, text=True, timeout=20,
            encoding="utf-8", errors="replace")
        if completed.returncode != 0:
            return exe, None, {
                "method": "subprocess-version-probe",
                "status": "unavailable",
                "returncode": completed.returncode,
                "error": (completed.stderr or completed.stdout).strip()[-300:],
            }
        output = (completed.stdout or completed.stderr).strip()
        version = output.splitlines()[0] if output else None
        if not version:
            return exe, None, {"method": "subprocess-version-probe",
                               "status": "unavailable",
                               "reason": "empty version output"}
        return exe, version, {"method": "subprocess-version-probe",
                              "status": "verified"}
    except Exception as error:  # noqa: BLE001 - external probes must not crash
        return exe, None, {"method": "subprocess-version-probe",
                           "status": "unavailable", "error": str(error)}


def ensure_provenance(result, label="result"):
    """Raise when a result object lacks a non-empty provenance section."""
    if not isinstance(result, dict) or not result.get("provenance"):
        raise ProvenanceError("%s is missing provenance" % label)
    for item in result["provenance"]:
        validate(item)
    return True


if __name__ == "__main__":
    # Minimal self-test used by smoke/property tests.
    example = source("software", "PAM Scanner", "guide-candidate-search",
                     version=read_version(), status="verified",
                     verification={"method": "unit-tests", "status": "verified"})
    validate(example)
    print(json.dumps({"ok": True, "source_id": source_id(example),
                      "source": example}, ensure_ascii=False, indent=2))
    sys.exit(0)
