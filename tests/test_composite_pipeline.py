# -*- coding: utf-8 -*-
"""Unit tests for CompositePipelineHandler (Stage 0 liberation)."""
from __future__ import annotations

import pathlib
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core import execute, finalize, plan, validate, validate_construction_task


def _write_gb(path: pathlib.Path, seq: str, name: str = "pTest", topology: str = "circular") -> str:
    rec = SeqRecord(Seq(seq), id=name, name=name)
    rec.annotations["molecule_type"] = "DNA"
    rec.annotations["topology"] = topology
    with open(path, "w", encoding="utf-8") as fh:
        SeqIO.write(rec, fh, "genbank")
    return str(path)


class CompositePipelineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)
        self.out = self.tmp / "out"
        self.src_path = self.tmp / "template.gb"
        # 200 bp template sequence with EcoRI (GAATTC) at pos 20
        seq = "A" * 20 + "GAATTC" + "C" * 40 + "G" * 60 + "T" * 74
        _write_gb(self.src_path, seq, "template", "circular")

    def tearDown(self):
        self._tmp.cleanup()

    def test_composite_pipeline_extraction_and_assembly(self):
        task = {
            "schema_version": "construction-task-v1",
            "task_id": "test-pipeline-run",
            "revision": 1,
            "mode": "formal",
            "task_kind": "composite_pipeline",
            "pipeline": {
                "steps": [
                    {
                        "step_id": "frag1",
                        "tool": "extract_subsequence",
                        "params": {"source": str(self.src_path), "start": 0, "end": 80, "strand": 1, "topology": "circular"},
                    },
                    {
                        "step_id": "frag2",
                        "tool": "reverse_complement",
                        "params": {"seq": "$frag1"},
                    },
                ]
            },
            "sources": [
                {
                    "source_id": "src1",
                    "path": str(self.src_path),
                    "role": "template",
                    "evidence": {"source_evidence_class": "user-provided"},
                }
            ],
            "target": {},
            "operation": {},
            "product": {"topology": "linear", "formats": ["gb", "fasta", "dna"]},
            "method_constraints": {},
            "approvals": {"user_confirmed_task": {"value": True}},
            "assumptions": [],
            "provenance": [],
        }

        # 1. Validate
        vtask = validate_construction_task(task)
        self.assertEqual(vtask["task_kind"], "composite_pipeline")

        # 2. Plan
        vtask, plan_dict = plan(vtask)
        self.assertEqual(len(plan_dict["steps"]), 2)
        self.assertEqual(plan_dict["product_sequence_sha256"], plan_dict["steps"][1]["output_sha256"])

        # 3. Execute
        exec_res = execute(vtask, plan_dict, self.out)
        self.assertTrue(pathlib.Path(exec_res["product_gb"]).exists())
        self.assertTrue(pathlib.Path(exec_res["product_dna"]).exists())

        # 4. Validate
        report = validate(vtask, plan_dict, exec_res)
        self.assertEqual(report["overall"], "verified")
        self.assertTrue(report["artifact_valid"])
        self.assertTrue(report["computation_valid"])
        self.assertTrue(report["goal_valid"])

        # 5. Finalize
        delivery = finalize(vtask, plan_dict, exec_res, report, self.out)
        self.assertEqual(delivery["status"], "delivered")
        self.assertTrue((self.out / "authoritative" / "construct.dna").exists())
        self.assertTrue((self.out / "authoritative" / "construct.gb").exists())


if __name__ == "__main__":
    unittest.main()
