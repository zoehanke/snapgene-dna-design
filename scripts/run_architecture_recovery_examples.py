# -*- coding: utf-8 -*-
"""Post-fix example evidence for S01/S05/S06/S08 through the public seams.

Reads public/frozen v0.9.0 audit inputs (read-only), builds explicit
ConstructionTask JSONs, and records either the authoritative delivery or
the structured refusal.  Outputs land under
reports/v0.9.1-architecture-recovery/example-outputs/.
"""
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import (execute, finalize, plan, validate,
                  validate_construction_task)
from core.errors import CoreError
OUT = ROOT / "reports" / "v0.9.1-architecture-recovery" / "example-outputs"
OUT.mkdir(parents=True, exist_ok=True)
AUDIT = pathlib.Path(r"D:\codex_project\audit\snapgene-dna-design-v0.9.0-real-construction-complex-audit")
SKILL = pathlib.Path(r"D:\skilltest")

results = {}


def source(sid, path, role, evidence="user-provided"):
    return {"source_id": sid, "path": str(path), "role": role,
            "evidence": {"source_evidence_class": evidence},
            "annotation_status": "reviewed"}


def base(kind, sources, **overrides):
    task = {
        "schema_version": "construction-task-v1",
        "task_id": "task-%s" % kind,
        "revision": 1,
        "mode": "formal",
        "task_kind": kind,
        "sources": sources,
        "operation": {},
        "target": {"source_id": sources[0]["source_id"]},
        "product": {"topology": "circular",
                    "formats": ["gb", "fasta", "dna"]},
        "method_constraints": {},
        "approvals": {"user_confirmed_task": {"value": True}},
        "assumptions": [],
        "provenance": [],
    }
    task.update(overrides)
    return task


def run(name, task):
    out = OUT / name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        task = validate_construction_task(task)
        task, p = plan(task)
        ex = execute(task, p, out)
        report = validate(task, p, ex)
        delivery = finalize(task, p, ex, report, out) \
            if report["overall"] == "verified" else None
        results[name] = {
            "status": "delivered" if delivery else report["overall"],
            "validation": report,
            "delivery": delivery,
            "product_length": len(ex["product_sequence"]),
            "task_kind": task["task_kind"],
        }
    except CoreError as exc:
        results[name] = {"status": exc.status,
                         "error": exc.to_dict()}
    (out / "result.json").write_text(
        json.dumps(results[name], ensure_ascii=False, indent=2),
        encoding="utf-8")


# ---- S06 positive: explicit cassette interval + 45 bp arms ---------------
s06_tmpl = OUT / "S06-template.gb"
shutil.copyfile(SKILL / "S06-yeast-tagging-donor" / "inputs" /
                "HQ154040-pFA6a-URA3-kanMX6.gb", s06_tmpl)
run("S06-cassette-positive", base(
    "component_amplification",
    [source("template-1", s06_tmpl, "template")],
    operation={"homology_arms": {"left_arm": "T" * 45,
                                 "right_arm": "A" * 45}},
    target={"source_id": "template-1",
            "selection": {"kind": "interval",
                          "interval_0based": [41, 2687],
                          "resolution_status": "resolved",
                          "resolution_evidence": [{"kind": "user-interval"}]}},
    product={"topology": "linear", "formats": ["gb", "fasta", "dna"]}))

# ---- S05 positive: explicit MCS replace interval -------------------------
s05_vec = OUT / "S05-backbone.gb"
shutil.copyfile(SKILL / "S05-gibson-3frag" / "inputs" / "M77789-pUC19.gb",
                s05_vec)
ins1 = (SKILL / "S05-gibson-3frag" / "inputs" / "ins1.fa").read_text(
    encoding="utf-8")
ins2 = (SKILL / "S05-gibson-3frag" / "inputs" / "ins2.fa").read_text(
    encoding="utf-8")
def fasta_seq(text):
    return "".join(line.strip() for line in text.splitlines()
                   if line and not line.startswith(">"))
s05_repl = OUT / "S05-replacement.fa"
s05_repl.write_text(">replacement\n" + fasta_seq(ins1)[25:] +
                    fasta_seq(ins2)[25:] + "\n", encoding="utf-8")
run("S05-replace-positive", base(
    "plasmid_replace",
    [source("backbone-1", s05_vec, "backbone"),
     source("replacement-1", s05_repl, "replacement")],
    operation={"replace": {
        "interval_0based": [233, 284],
        "replacement_source_id": "replacement-1",
        "replacement_interval_0based": [0, 275 + 350]}},
    target={"source_id": "backbone-1",
            "selection": {"kind": "interval",
                          "interval_0based": [233, 284],
                          "resolution_status": "resolved",
                          "resolution_evidence": [{"kind": "user-interval"}]}},
    product={"topology": "circular", "formats": ["gb", "fasta", "dna"]}))

# ---- S01 positive: explicit nucleotide mutations with ref check ----------
s01_tmpl = OUT / "S01-template.gb"
shutil.copyfile(SKILL / "S01-tdt-sdm" / "inputs" / "OL989372.gb", s01_tmpl)
run("S01-mutation-positive", base(
    "point_mutation",
    [source("template-1", s01_tmpl, "template")],
    operation={"mutations": [
        {"position_1based": 6134, "ref": "G", "alt": "T"},
        {"position_1based": 6135, "ref": "T", "alt": "A"},
        {"position_1based": 6139, "ref": "A", "alt": "G"},
        {"position_1based": 6140, "ref": "A", "alt": "G"},
        {"position_1based": 6141, "ref": "A", "alt": "T"}]},
    product={"topology": "circular", "formats": ["gb", "fasta"]}))

# ---- S08 negative: reproduction without replace interval is refused ------
s08_vec = OUT / "S08-backbone.gb"
shutil.copyfile(SKILL / "S08-dual-luciferase" / "inputs" /
                "U47295-pGL3-Basic.gb", s08_vec)
s08_prom = OUT / "S08-promoter.fa"
s08_prom.write_text(">AePUb\n" + "N" * 967 + "\n", encoding="utf-8")
run("S08-replace-missing-interval", base(
    "plasmid_replace",
    [source("backbone-1", s08_vec, "backbone"),
     source("replacement-1", s08_prom, "replacement")],
    operation={"replace": {"replacement_source_id": "replacement-1"}},
    target={"source_id": "backbone-1",
            "selection": {"kind": "interval",
                          "resolution_status": "unresolved"}},
    product={"topology": "circular", "formats": ["gb"]}))

summary = OUT / "post-fix-examples-summary.json"
summary.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                   encoding="utf-8")
print(json.dumps({k: {"status": v.get("status"),
                      "length": v.get("product_length"),
                      "error": (v.get("error") or {}).get("error_code")}
                  for k, v in results.items()},
                 ensure_ascii=False, indent=2))
