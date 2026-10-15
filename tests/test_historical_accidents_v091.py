# -*- coding: utf-8 -*-
"""Historical accident regressions S01 / S05 / S06 / S08 (v0.9.1).

Each test reproduces the exact class of error from the v0.9.0 real
construction audit and asserts the new runtime refuses it with a stable
error code before any authoritative product is written.
"""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import pathlib
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core import (execute, plan, validate, validate_construction_task)
from core.errors import (CoreError, PlanningError, TaskValidationError)


def _record(seq, name, topology="circular", features=()):
    rec = SeqRecord(Seq(seq), id=name, name=name)
    rec.annotations["molecule_type"] = "DNA"
    rec.annotations["topology"] = topology
    for feature in features:
        rec.features.append(feature)
    return rec


def _misc(label, start, end, strand=1):
    return SeqFeature(FeatureLocation(start, end, strand=strand),
                      type="misc_feature",
                      qualifiers={"label": [label]})


class HistoricalAccidentTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _base(self, kind, sources, **overrides):
        task = {
            "schema_version": "construction-task-v1",
            "task_id": "task-" + kind,
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

    def _source(self, sid, path, role, evidence="user-provided"):
        return {"source_id": sid, "path": path, "role": role,
                "evidence": {"source_evidence_class": evidence},
                "annotation_status": "reviewed"}

    def _write(self, name, rec):
        path = self.tmp / name
        SeqIO.write(rec, path, "genbank")
        return str(path)

    def test_S01_point_mutation_without_spec_is_refused(self):
        template = _record("A" * 60, "template", "circular")
        path = self._write("template.gb", template)
        task = self._base("point_mutation",
                          [self._source("template-1", path, "template")])
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code, "MUTATION_SPEC_REQUIRED")

    def test_S05_replace_without_interval_is_refused(self):
        backbone = _record("A" * 20 + "GGATCC" + "C" * 40, "backbone",
                           "circular")
        replacement = _record("T" * 20, "replacement", "linear")
        bpath = self._write("backbone.gb", backbone)
        rpath = self._write("replacement.gb", replacement)
        task = self._base(
            "plasmid_replace",
            [self._source("backbone-1", bpath, "backbone"),
             self._source("replacement-1", rpath, "replacement")],
            operation={"replace": {
                "replacement_source_id": "replacement-1"}})
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code, "REPLACE_INTERVAL_REQUIRED")

    def test_S06_whole_template_cassette_is_refused(self):
        # pFA6a-like template: cassette + outside vector backbone features
        template = _record("A" * 20 + "GGATCC" + "C" * 40, "pFA6a",
                           "circular",
                           features=[_misc("URA3-Kan-cassette", 20, 26),
                                     _misc("bla", 30, 40),
                                     _misc("ori", 5, 10)])
        path = self._write("template.gb", template)
        task = self._base(
            "component_amplification",
            [self._source("template-1", path, "template")],
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": [0, 68],
                                  "resolution_status": "resolved"}},
            product={"topology": "linear", "formats": ["gb"]})
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code,
                         "WHOLE_TEMPLATE_SELECTED_FOR_COMPONENT")

    def test_S06_correct_cassette_passes_contamination_check(self):
        template = _record("A" * 20 + "GGATCC" + "C" * 40, "pFA6a",
                           "circular",
                           features=[_misc("URA3-Kan-cassette", 20, 26),
                                     _misc("bla", 30, 40),
                                     _misc("ori", 5, 10)])
        path = self._write("template.gb", template)
        task = self._base(
            "component_amplification",
            [self._source("template-1", path, "template")],
            operation={"homology_arms": {"left_arm": "T" * 45,
                                         "right_arm": "A" * 45}},
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "interval_0based": [20, 26],
                                  "resolution_status": "resolved",
                                  "resolution_evidence": [
                                      {"kind": "user-interval"}]}},
            product={"topology": "linear", "formats": ["gb"]})
        task, p = plan(task)
        self.assertEqual(p["component_length"], 6)
        ex = execute(task, p, self.tmp / "out")
        report = validate(task, p, ex)
        self.assertEqual(report["overall"], "verified", report["error_codes"])

    def test_S08_mcs_insert_must_not_claim_replace(self):
        # Reproduction-style task without an explicit replace interval is
        # refused as plasmid_replace; it cannot silently become insert.
        backbone = _record("A" * 12 + "MCSMCS" + "C" * 40, "pGL3-Basic",
                           "circular")
        replacement = _record("P" * 30, "promoter", "linear")
        bpath = self._write("backbone.gb", backbone)
        rpath = self._write("promoter.gb", replacement)
        task = self._base(
            "plasmid_replace",
            [self._source("backbone-1", bpath, "backbone"),
             self._source("replacement-1", rpath, "replacement")],
            operation={"replace": {
                "replacement_source_id": "replacement-1"}})
        with self.assertRaises(TaskValidationError) as cm:
            validate_construction_task(task)
        self.assertEqual(cm.exception.error_code, "REPLACE_INTERVAL_REQUIRED")


if __name__ == "__main__":
    unittest.main()
