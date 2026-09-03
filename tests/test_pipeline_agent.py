# -*- coding: utf-8 -*-
"""Unit tests for liberated pipeline agent (agent/pipeline_agent.py)."""
from __future__ import annotations

import pathlib
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from agent.pipeline_agent import build_agent_planning_prompt, execute_agent_pipeline


def _write_gb(path: pathlib.Path, seq: str, name: str = "pTest", topology: str = "circular") -> str:
    rec = SeqRecord(Seq(seq), id=name, name=name)
    rec.annotations["molecule_type"] = "DNA"
    rec.annotations["topology"] = topology
    with open(path, "w", encoding="utf-8") as fh:
        SeqIO.write(rec, fh, "genbank")
    return str(path)


class PipelineAgentTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)
        self.src1 = self.tmp / "plasmidA.gb"
        self.src2 = self.tmp / "plasmidB.gb"

        # plasmidA: 150 bp with EcoRI (GAATTC)
        _write_gb(self.src1, "A" * 30 + "GAATTC" + "C" * 40 + "T" * 74, "plasmidA", "circular")
        # plasmidB: 120 bp with BamHI (GGATCC)
        _write_gb(self.src2, "G" * 30 + "GGATCC" + "A" * 40 + "C" * 44, "plasmidB", "circular")

    def tearDown(self):
        self._tmp.cleanup()

    def test_build_agent_planning_prompt(self):
        prompt_data = build_agent_planning_prompt(
            user_request="Swap EcoRI site in plasmidA with BamHI region from plasmidB",
            file_paths=[self.src1, self.src2],
        )
        self.assertIn("plasmidA", str(prompt_data["file_inspections"]))
        self.assertIn("plasmidB", str(prompt_data["file_inspections"]))
        self.assertGreaterEqual(len(prompt_data["available_atomic_tools"]), 10)
        self.assertEqual(len(prompt_data["foundational_checklist"]), 5)

    def test_execute_agent_pipeline(self):
        # Define a 2-step composite pipeline
        steps = [
            {
                "step_id": "slice_a",
                "tool": "extract_subsequence",
                "params": {"source": str(self.src1), "start": 0, "end": 50, "strand": 1, "topology": "circular"},
            },
            {
                "step_id": "rc_slice",
                "tool": "reverse_complement",
                "params": {"seq": "$slice_a"},
            },
        ]

        out_dir = self.tmp / "build"
        result = execute_agent_pipeline(
            task_id="construct-agent-test",
            pipeline_steps=steps,
            source_files=[self.src1],
            product_topology="linear",
            out_dir=out_dir,
            auto_open_snapgene=False,
        )

        self.assertEqual(result["status"], "delivered")
        self.assertEqual(result["product_length"], 50)
        auth_dir = pathlib.Path(result["authoritative_dir"])
        self.assertTrue((auth_dir / "construct.dna").exists())
        self.assertTrue((auth_dir / "construct.gb").exists())


if __name__ == "__main__":
    unittest.main()
