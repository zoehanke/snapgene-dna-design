# -*- coding: utf-8 -*-
"""SnapGene official roundtrip gate for authoritative constructs.

Builds a construct from a named-feature record through the public seams,
finalizes it, and verifies the official SnapGene roundtrip grade of the
authoritative .gb and .dna files.  Also records the roundtrip grades of
the four known-scenario authoritative constructs, whose unnamed-feature
sources are normalized by SnapGene (declared level: core-compatible with
manual review).
"""
import json
import pathlib
import subprocess
import sys
import tempfile

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from core import execute, finalize, plan, validate  # noqa: E402

from core.tools.snapgene_io import find_snapgene_executable

SNAPGENE = str(find_snapgene_executable() or "SnapGene")


def roundtrip(path, fmt="snapgene-gb"):
    cp = subprocess.run(
        [sys.executable, "-X", "utf8", "-B",
         str(ROOT / "scripts" / "validate_roundtrip.py"), str(path),
         "--format", fmt, "--snapgene-exe", SNAPGENE, "--require-snapgene", "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(cp.stdout)["data"]
    except Exception:
        return {"raw_rc": cp.returncode,
                "raw_out": (cp.stdout or "")[-400:]}


def main():
    report = {"gate": "snapgene-official-roundtrip", "cases": {}}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        seq = ("ATGAAATTTGGGTAA" + "CCCCGGGGAAAATTTT" +
               "GGGGCCCC" + "TTTTAAGGGCCTTAA")
        rec = SeqRecord(Seq(seq), id="demo", name="demo")
        rec.annotations["molecule_type"] = "DNA"
        rec.annotations["topology"] = "circular"
        rec.features.append(SeqFeature(
            FeatureLocation(0, 15, strand=1), type="CDS",
            qualifiers={"gene": ["demo_gene"], "label": ["demo_gene"],
                        "translation": ["MKFG*"]}))
        rec.features.append(SeqFeature(
            FeatureLocation(15, 27, strand=1), type="misc_feature",
            qualifiers={"label": ["demo_promo"],
                        "note": ["demo promoter"]}))
        src = tmp / "demo.gb"
        SeqIO.write(rec, src, "genbank")
        task = {
            "schema_version": "construction-task-v1",
            "task_id": "task-rt-named", "revision": 1,
            "mode": "formal", "task_kind": "point_mutation",
            "sources": [{"source_id": "demo", "path": str(src),
                         "role": "template",
                         "annotation_status": "reviewed",
                         "evidence": {
                             "source_evidence_class": "synthetic-fixture"}}],
            "operation": {"mutations": [
                {"position_1based": 16, "ref": "C", "alt": "A"}]},
            "target": {"source_id": "demo"},
            "product": {"topology": "circular",
                        "formats": ["gb", "fasta", "dna"],
                        "name": "rt-named"},
            "method_constraints": {},
            "approvals": {"user_confirmed_task": {"value": True}},
            "assumptions": [], "provenance": [],
            "host": "Escherichia coli",
        }
        task, p = plan(task)
        ex = execute(task, p, tmp / "out")
        v = validate(task, p, ex)
        report["named_pipeline"] = {
            "validation_overall": v["overall"],
            "error_codes": v["error_codes"],
        }
        delivery = finalize(task, p, ex, v, tmp / "out")
        auth = pathlib.Path(delivery["directory"])
        report["cases"]["named_construct.gb"] = roundtrip(
            auth / "construct.gb", "snapgene-gb")
        report["cases"]["named_construct.dna"] = roundtrip(
            auth / "construct.dna", "snapgene-gb")
    e2e_root = (ROOT / "reports" / "v0.9.1-architecture-recovery" /
                "e2e-rerun")
    for scenario in ("S01", "S05", "S06", "S08pos"):
        gb = e2e_root / scenario / "run2" / "authoritative" / \
            "construct.gb"
        if gb.exists():
            report["cases"]["%s_construct.gb" % scenario] = roundtrip(
                gb, "snapgene-gb")
        dna = e2e_root / scenario / "run2" / "authoritative" / \
            "construct.dna"
        if dna.exists():
            report["cases"]["%s_construct.dna" % scenario] = roundtrip(
                dna, "snapgene-gb")
    out = (ROOT / "reports" / "v0.9.1-architecture-recovery" / "gates" /
           "snapgene_official_roundtrip.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(json.dumps({
        k: {"core_passed": v.get("core_passed"),
            "strict_passed": v.get("strict_passed")}
        for k, v in report["cases"].items()}, ensure_ascii=False, indent=1))
    return 0 if report['cases'] and all(case.get('core_passed') is True
                                        for case in report['cases'].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
