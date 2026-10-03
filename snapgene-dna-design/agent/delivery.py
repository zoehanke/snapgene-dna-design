# -*- coding: utf-8 -*-
"""agent/delivery.py - unified delivery package writer.

Writes DESIGN-SPEC.json, hash files, plan/evidence/validation reports,
assumptions-and-decisions.md, primers.csv, materials.csv, construct files
and DELIVERY-MANIFEST.json. .dna is omitted with an explicit reason when the
source construct is not core-safe.
"""
from __future__ import annotations

import csv
import copy
import hashlib
import json
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from design.spec import DesignSpecError, now_iso, spec_sha256  # noqa: E402
from scripts.provenance import read_version  # noqa: E402


def sha256_file(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest().upper()


def _write_text(path, text):
    pathlib.Path(path).write_text(text, encoding="utf-8")
    return str(path)


def _write_json(path, obj):
    pathlib.Path(path).write_text(
        json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _primers_csv(path, artifacts):
    primers = []
    plan = pathlib.Path(path).parent / "construction-plan.json"
    data = json.loads(plan.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Construction plan must be a JSON object")
    for item in data.get("primers", []):
        for side in ("forward", "reverse"):
            primer = item.get(side) or {}
            if primer.get("sequence"):
                primers.append({
                    "name": primer.get("name", ""),
                    "fragment": item.get("fragment", ""),
                    "side": side,
                    "sequence": primer.get("sequence", ""),
                    "tm": primer.get("tm", ""),
                    "gc": primer.get("gc", ""),
                    "tail": primer.get("tail", ""),
                })
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "name", "fragment", "side", "sequence", "tm", "gc", "tail"])
        writer.writeheader()
        for row in primers:
            writer.writerow(row)
    return str(path)


def _materials_csv(path, spec):
    rows = []
    selection = spec.get("constraints", {}).get("method_selection", {})
    chosen = selection.get("selected") or {}
    if chosen:
        for material in chosen.get("required_materials", []):
            rows.append({"category": "method", "item": material,
                         "source": "; ".join(chosen.get("source_evidence", []))})
    polymerase = spec.get("constraints", {}).get("polymerase_preference")
    if polymerase:
        rows.append({"category": "primer-polymerase", "item": polymerase,
                     "source": "declared design constraint"})
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["category", "item", "source"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return str(path)


def write_delivery(spec, session, directory, construct_gb=None,
                   artifacts=None, force_dna=False):
    """Publish an immutable preview snapshot separately from working files."""
    if spec.get("mode") != "exploration":
        raise DesignSpecError("LEGACY_AGENT_FORMAL_DEPRECATED")
    if construct_gb and spec.get("status") != "verified":
        raise DesignSpecError("PREVIEW_VERIFICATION_REQUIRED")
    parent = pathlib.Path(directory) / "preview"
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / "delivery"
    if target.exists():
        raise FileExistsError(f"Preview delivery already exists: {target}; use a new output directory")
    stage = pathlib.Path(tempfile.mkdtemp(prefix=".delivery-", dir=parent))
    try:
        result = _write_snapshot(copy.deepcopy(spec), session, stage,
                                 construct_gb, artifacts, force_dna)
        stage.rename(target)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    result["directory"] = str(target)
    return result


def _write_snapshot(spec, session, directory, construct_gb, artifacts, force_dna):
    construct = pathlib.Path(construct_gb) if construct_gb else None
    if construct is not None and not construct.is_file():
        raise FileNotFoundError(f"Preview candidate not found: {construct}")
    flags = {"delivery_grade": "legacy-preview", "ready_to_order": False,
             "ready_for_wet_lab": False,
             "reason": "Legacy sequence preview; formal construction uses the ConstructionTask runtime."}
    spec.setdefault("outputs", {})["delivery_flags"] = flags
    if construct is None:
        spec["outputs"]["construct_note"] = "No construct was provided; this package contains reports only."
    elif not construct.with_suffix('.dna').is_file():
        spec["outputs"]["dna_note"] = "No native DNA artifact was provided; the GenBank preview is included."
    elif not force_dna:
        spec["outputs"]["dna_note"] = "Native DNA preview omitted by the export option; the GenBank preview is included."
    spec_path = _write_json(directory / "DESIGN-SPEC.json", spec)
    spec_hash = spec_sha256(spec)
    _write_text(directory / "DESIGN-SPEC-SHA256.txt", spec_hash + "\n")

    plan_src = None
    for artifact in artifacts or []:
        cmd = artifact.get("command", [])
        if "--out-json" in cmd:
            idx = cmd.index("--out-json")
            plan_src = pathlib.Path(cmd[idx + 1])
    if plan_src and plan_src.exists():
        shutil.copyfile(plan_src, directory / "construction-plan.json")
    else:
        _write_json(directory / "construction-plan.json", {
            "schema_version": "0.9.0", "status": "unavailable",
            "reason": "no construction plan produced"})

    if pathlib.Path(directory / "construction-plan.json").exists():
        # plan_assembly also writes a Markdown plan; copy it when available.
        md_src = pathlib.Path(str(plan_src).replace(".json", ".md")) \
            if plan_src else None
        if md_src and md_src.exists():
            shutil.copyfile(md_src, directory / "construction-plan.md")
        else:
            _write_text(directory / "construction-plan.md",
                        "# construction plan\n\nSee construction-plan.json.\n")

    evidence = {
        "schema_version": "1.0.0",
        "spec_id": spec["spec_id"],
        "revision": spec["revision"],
        "spec_sha256": spec_hash,
        "sources": spec.get("sources", []),
        "assumptions": spec.get("assumptions", []),
        "derived_facts": spec.get("derived_facts", []),
        "approvals": spec.get("approvals", {}),
        "delivery_flags": flags,
    }
    _write_json(directory / "evidence-report.json", evidence)

    validation = spec.get("outputs", {}).get("validation", {
        "status": "unavailable", "reason": "no validation recorded"})
    _write_json(directory / "validation-report.json", validation)

    decisions = ["# assumptions and decisions\n",
                 "- mode: %s" % spec.get("mode"),
                 "- status: %s" % spec.get("status"),
                 "- method selection: %s" % json.dumps(
                     spec.get("constraints", {}).get("method_selection", {}),
                     ensure_ascii=False)[:3000]]
    for item in spec.get("assumptions", []):
        decisions.append("- [%s] %s" % (
            item.get("evidence_layer"), item.get("description")))
    _write_text(directory / "assumptions-and-decisions.md",
                "\n".join(decisions) + "\n")

    _primers_csv(directory / "primers.csv", artifacts or [])
    _materials_csv(directory / "materials.csv", spec)

    files = []
    if construct:
        shutil.copyfile(construct, directory / "construct.preview.gb")
        files.append(directory / "construct.preview.gb")
        fasta = construct.with_suffix('.fa')
        if fasta.exists():
            shutil.copyfile(fasta, directory / "construct.fasta")
            files.append(directory / "construct.fasta")
        dna = construct.with_suffix('.dna')
        if dna.exists() and force_dna:
            shutil.copyfile(dna, directory / "construct.dna")
            files.append(directory / "construct.dna")

    manifest_files = {
        "DESIGN-SPEC.json": sha256_file(directory / "DESIGN-SPEC.json"),
        "DESIGN-SPEC-SHA256.txt": sha256_file(
            directory / "DESIGN-SPEC-SHA256.txt"),
        "construction-plan.json": sha256_file(
            directory / "construction-plan.json"),
        "construction-plan.md": sha256_file(
            directory / "construction-plan.md"),
        "evidence-report.json": sha256_file(
            directory / "evidence-report.json"),
        "validation-report.json": sha256_file(
            directory / "validation-report.json"),
        "assumptions-and-decisions.md": sha256_file(
            directory / "assumptions-and-decisions.md"),
        "primers.csv": sha256_file(directory / "primers.csv"),
        "materials.csv": sha256_file(directory / "materials.csv"),
    }
    for path in files:
        manifest_files[path.name] = sha256_file(path)

    manifest = {
        "schema_version": "1.0.0",
        "spec_id": spec["spec_id"],
        "spec_revision": spec["revision"],
        "spec_sha256": spec_hash,
        "input_files": {
            str(path): summary.get("sha256")
            for path, summary in session.file_summaries.items()
            if summary.get("sha256")},
        "output_files": manifest_files,
        "software": {
            "tool_version": read_version(),
            "python": sys.version.split()[0],
        },
        "backends": {
            "primer3_core": os_probe_summary(),
        },
        "generated_at": now_iso(),
        "verification_level": "legacy-exploration-preview",
        "artifact_class": "preview",
    }
    manifest_path = _write_json(directory / "DELIVERY-MANIFEST.json", manifest)
    return {
        "directory": str(directory),
        "manifest": manifest,
        "manifest_sha": sha256_file(manifest_path),
        "files": sorted(str(path.name) for path in directory.iterdir()),
    }


def os_probe_summary():
    try:
        from scripts import primer3_core_backend
        probe = primer3_core_backend.probe_primer3_core()
        return {"status": probe.get("status"),
                "version": probe.get("version"),
                "path": probe.get("path")}
    except Exception:
        return {"status": "unavailable"}
