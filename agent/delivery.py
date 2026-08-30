# -*- coding: utf-8 -*-
"""agent/delivery.py - unified delivery package writer.

Writes DESIGN-SPEC.json, hash files, plan/evidence/validation reports,
assumptions-and-decisions.md, primers.csv, materials.csv, construct files
and DELIVERY-MANIFEST.json. .dna is omitted with an explicit reason when the
source construct is not core-safe.
"""
from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from design.spec import canonical_json, now_iso, spec_sha256  # noqa: E402
from provenance import read_version  # noqa: E402


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
    for artifact in artifacts or []:
        if artifact.get("stdout"):
            text = artifact["stdout"]
            # plan_assembly JSON output contains primers inside plan.json;
            # primers.csv is populated from plan file when present.
    plan = pathlib.Path(path).parent / "construction-plan.json"
    if plan.exists():
        try:
            data = json.loads(plan.read_text(encoding="utf-8"))
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
        except Exception:
            pass
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
    rows.append({"category": "primer-polymerase",
                 "item": spec.get("constraints", {}).get(
                     "polymerase_preference", "high-fidelity polymerase"),
                 "source": "NEB polymerase selection guidance"})
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["category", "item", "source"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return str(path)


def write_delivery(spec, session, directory, construct_gb=None,
                   artifacts=None, force_dna=False):
    directory = pathlib.Path(directory) / "preview"
    directory.mkdir(parents=True, exist_ok=True)
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
        "delivery_flags": {
            "delivery_grade": "legacy-preview",
            "ready_to_order": False,
            "ready_for_wet_lab": False,
            "reason": ("v0.9.1: the legacy keyword-parser path never produces "
                       "authoritative, orderable or wet-lab products; use "
                       "core.run_construction_task for formal construction"),
        },
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

    construct = pathlib.Path(construct_gb) if construct_gb else None
    files = []
    if construct and construct.exists():
        shutil.copyfile(construct, directory / "construct.preview.gb")
        files.append(directory / "construct.preview.gb")
        fasta = pathlib.Path(str(construct).replace(".gb", ".fa"))
        if fasta.exists():
            shutil.copyfile(fasta, directory / "construct.fasta")
            files.append(directory / "construct.fasta")
        dna = pathlib.Path(str(construct).replace(".gb", ".dna"))
        if dna.exists() and force_dna:
            shutil.copyfile(dna, directory / "construct.dna")
            files.append(directory / "construct.dna")
        elif dna.exists():
            spec.setdefault("outputs", {})["dna_note"] = (
                "construct.dna available but omitted: native .dna may lose "
                "qualifiers/notes; authoritative GenBank is the canonical "
                "delivery format")
        else:
            spec.setdefault("outputs", {})["dna_note"] = (
                "construct.dna omitted: source construct has no .dna "
                "artifact; authoritative GenBank remains available")
    else:
        spec.setdefault("outputs", {})["construct_note"] = (
            "no construct.gb available at delivery time")

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
        import primer3_core_backend
        probe = primer3_core_backend.probe_primer3_core()
        return {"status": probe.get("status"),
                "version": probe.get("version"),
                "path": probe.get("path")}
    except Exception:
        return {"status": "unavailable"}
