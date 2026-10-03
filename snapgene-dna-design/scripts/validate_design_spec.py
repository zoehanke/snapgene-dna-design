# -*- coding: utf-8 -*-
"""validate_design_spec.py - DesignSpec v1 schema + state-machine validator."""
import argparse
import json
import pathlib
import sys

from jsonschema import Draft202012Validator

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from design.spec import (  # noqa: E402
    SCHEMA_VERSION, STATUSES, TRANSITIONS, DesignSpecError, formal_blockers,
)


def _load_schema():
    path = ROOT / "schemas" / "design-spec-v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def validate_design_spec(spec, require_schema_version=None):
    """Return {'ok': bool, 'errors': [...], 'warnings': [...]}.

    Checks: JSON Schema, status known, revision positive integer, state
    provenance (only a rough check that status is legal; the full transition
    path is enforced live by design.spec.set_status), formal blockers when
    mode == formal.
    """
    errors = []
    warnings = []
    if not isinstance(spec, dict):
        return {"ok": False, "errors": ["not a JSON object"], "warnings": []}
    try:
        schema = _load_schema()
        validator = Draft202012Validator(schema)
        errors.extend(
            "%s: %s" % (".".join(str(p) for p in list(error.path) or ["$"]),
                         error.message)
            for error in validator.iter_errors(spec))
    except Exception as exc:  # noqa: BLE001
        errors.append("schema-load-error: %s" % exc)
    if spec.get("schema_version") != (require_schema_version or SCHEMA_VERSION):
        errors.append("schema_version must be %s"
                      % (require_schema_version or SCHEMA_VERSION))
    if spec.get("status") not in STATUSES:
        errors.append("unknown status: %r" % spec.get("status"))
    if not isinstance(spec.get("revision"), int) or spec.get("revision", 0) < 1:
        errors.append("revision must be a positive integer")
    if spec.get("mode") not in ("exploration", "formal"):
        errors.append("mode must be exploration or formal")
    if spec.get("mode") == "exploration":
        outputs = spec.get("outputs") or {}
        if outputs.get("ready_to_order") or outputs.get("ready_for_wet_lab"):
            errors.append(
                "exploration spec must not set ready_to_order or "
                "ready_for_wet_lab to true")
    if spec.get("mode") == "formal":
        for blocker in formal_blockers(spec):
            errors.append("formal-blocker: %s" % blocker)
    if spec.get("status") == "delivered" and spec.get("mode") == "formal":
        flags = spec.get("outputs", {}).get("delivery_flags") or {}
        if not flags.get("ready_to_order") or not flags.get("ready_for_wet_lab"):
            warnings.append(
                "delivered formal spec lacks positive delivery_flags")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", help="path to DESIGN-SPEC.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        spec = json.loads(pathlib.Path(args.spec).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        if args.json:
            print(json.dumps({"ok": False, "errors": [str(error)],
                              "warnings": []}, ensure_ascii=False, indent=2))
        else:
            print("ERROR: %s" % error)
        return 2
    result = validate_design_spec(spec)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("ok=%s" % result["ok"])
        for error in result["errors"]:
            print("ERROR: %s" % error)
        for warning in result["warnings"]:
            print("WARNING: %s" % warning)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
