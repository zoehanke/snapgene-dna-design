# -*- coding: utf-8 -*-
"""Clarification loop and CLI entry tests (AC-2 / AC-13)."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core import ConstructionTaskSession, collect_task_questions

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _record(seq, name="record", topology="circular"):
    rec = SeqRecord(Seq(seq), id=name, name=name)
    rec.annotations["molecule_type"] = "DNA"
    rec.annotations["topology"] = topology
    return rec


def _draft(kind, sources, **overrides):
    task = {
        "schema_version": "construction-task-v1",
        "task_id": "task-session",
        "revision": 1,
        "mode": "formal",
        "task_kind": kind,
        "sources": sources,
        "operation": {},
        "target": {},
        "product": {"topology": "linear" if kind ==
                    "component_amplification" else "circular",
                    "formats": ["gb", "fasta", "dna"]},
        "method_constraints": {},
        "approvals": {"user_confirmed_task": {"value": True}},
        "assumptions": [],
        "provenance": [],
    }
    task.update(overrides)
    return task


class SessionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name, rec):
        path = self.tmp / name
        SeqIO.write(rec, path, "genbank")
        return str(path)

    def test_missing_component_boundary_becomes_question(self):
        path = self._write("template.gb", _record("A" * 20 + "G" * 30))
        draft = _draft(
            "component_amplification",
            [{"source_id": "template-1", "path": path,
              "role": "template",
              "evidence": {"source_evidence_class": "user-provided"}}],
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "resolution_status": "unresolved"}})
        session = ConstructionTaskSession(draft)
        ids = [q["question_id"] for q in session.questions]
        self.assertIn("component-boundary", ids)

    def test_answer_writes_selection_and_revisions(self):
        path = self._write("template.gb", _record("A" * 20 + "G" * 30))
        draft = _draft(
            "component_amplification",
            [{"source_id": "template-1", "path": path,
              "role": "template",
              "evidence": {"source_evidence_class": "user-provided"}}],
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "resolution_status": "unresolved"}})
        session = ConstructionTaskSession(draft)
        before = session.task["revision"]
        session.answer("component-boundary", "interval:20:26")
        selection = session.task["target"]["selection"]
        self.assertEqual(selection["interval_0based"], [20, 26])
        self.assertEqual(selection["resolution_status"], "resolved")
        self.assertGreater(session.task["revision"], before)
        self.assertTrue(any("target.selection" in str(c["field"])
                            for d in session.diffs for c in d["changes"]))

    def test_auto_confirm_rejected_for_biology(self):
        path = self._write("template.gb", _record("A" * 40))
        draft = _draft(
            "component_amplification",
            [{"source_id": "template-1", "path": path,
              "role": "template",
              "evidence": {"source_evidence_class": "user-provided"}}])
        session = ConstructionTaskSession(draft)
        with self.assertRaises(ValueError):
            session.answer("component-boundary", "auto-confirmed")

    def test_mutation_answer(self):
        path = self._write("template.gb", _record("A" * 60))
        draft = _draft(
            "point_mutation",
            [{"source_id": "template-1", "path": path,
              "role": "template",
              "evidence": {"source_evidence_class": "user-provided"}}])
        session = ConstructionTaskSession(draft)
        self.assertIn("mutation-spec",
                      [q["question_id"] for q in session.questions])
        session.answer("mutation-spec",
                       [{"position_1based": 5, "ref": "A", "alt": "T"}])
        self.assertEqual(session.task["operation"]["mutations"][0]["alt"],
                         "T")

    def test_new_kind_questions_and_answers(self):
        path = self._write("ref.gb", _record("A" * 60))
        source = {"source_id": "ref-1", "path": path, "role": "reference",
                  "evidence": {"source_evidence_class": "user-provided"}}
        # protein_fusion questions
        fusion = _draft("protein_fusion", [source])
        ids = [q["question_id"]
               for q in ConstructionTaskSession(fusion).questions]
        self.assertIn("fusion-partner5", ids)
        self.assertIn("fusion-stop-policy", ids)
        # gateway questions
        gateway = _draft("gateway_recombination", [source])
        ids = [q["question_id"]
               for q in ConstructionTaskSession(gateway).questions]
        self.assertIn("gateway-reaction", ids)
        # restriction questions and answer
        restriction = _draft("restriction_ligation", [source])
        session = ConstructionTaskSession(restriction)
        ids = [q["question_id"] for q in session.questions]
        self.assertIn("restriction-spec", ids)
        session.answer("restriction-spec", {
            "vector_source_id": "ref-1", "insert_source_id": "ref-1",
            "vector_enzymes": ["EcoRI", "HindIII"],
            "orientation": "forward"})
        self.assertEqual(
            session.task["operation"]["vector_enzymes"],
            ["EcoRI", "HindIII"])
        # hierarchical and crispr questions
        hier = _draft("hierarchical_assembly", [source])
        ids = [q["question_id"]
               for q in ConstructionTaskSession(hier).questions]
        self.assertIn("hierarchical-stages", ids)
        crispr = _draft("crispr_editing", [source])
        ids = [q["question_id"]
               for q in ConstructionTaskSession(crispr).questions]
        self.assertIn("crispr-nuclease", ids)
        self.assertIn("crispr-target-interval", ids)
        # integration donor questions
        donor = _draft("integration_donor", [source])
        ids = [q["question_id"]
               for q in ConstructionTaskSession(donor).questions]
        self.assertIn("donor-arms", ids)
        self.assertIn("integration-locus", ids)


class ConstructionTaskCliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name, rec):
        path = self.tmp / name
        SeqIO.write(rec, path, "genbank")
        return str(path)

    def test_cli_needs_clarification_then_delivers(self):
        template_path = self._write(
            "template.gb", _record("A" * 20 + "GGATCC" + "C" * 40))
        task_path = self.tmp / "task.json"
        task_path.write_text(json.dumps(_draft(
            "component_amplification",
            [{"source_id": "template-1", "path": template_path,
              "role": "template",
              "evidence": {"source_evidence_class": "user-provided"}}],
            target={"source_id": "template-1",
                    "selection": {"kind": "interval",
                                  "resolution_status": "unresolved"}}),
            ensure_ascii=False), encoding="utf-8")
        out = self.tmp / "out"
        first = subprocess.run(
            [sys.executable, "-X", "utf8", "-B",
             str(ROOT / "scripts" / "run_construction_task.py"),
             "--task-json", str(task_path), "--out-dir", str(out), "--json"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=180)
        self.assertEqual(first.returncode, 3, first.stdout + first.stderr)
        payload = json.loads(first.stdout)
        self.assertEqual(payload["status"], "needs-clarification")
        self.assertFalse((out / "authoritative").exists())

        answers = self.tmp / "answers.json"
        answers.write_text(json.dumps(
            {"component-boundary": "interval:20:26",
             "host": "E. coli"},
            ensure_ascii=False), encoding="utf-8")
        second = subprocess.run(
            [sys.executable, "-X", "utf8", "-B",
             str(ROOT / "scripts" / "run_construction_task.py"),
             "--task-json", str(task_path), "--answers-json", str(answers),
             "--out-dir", str(out), "--json"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=180)
        self.assertEqual(second.returncode, 0,
                         second.stdout + second.stderr)
        payload = json.loads(second.stdout)
        self.assertEqual(payload["status"], "delivered")
        self.assertTrue((out / "authoritative" /
                         "DELIVERY-MANIFEST.json").exists())


if __name__ == "__main__":
    unittest.main()
