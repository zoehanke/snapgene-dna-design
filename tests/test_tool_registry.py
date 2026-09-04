# -*- coding: utf-8 -*-
"""Unit tests for unified Tool Registry and dynamic CompositePipeline execution."""
from __future__ import annotations

import pathlib
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.tools.registry import (
    TOOL_REGISTRY,
    get_tool,
    list_tool_definitions,
)
from core.handlers.composite_pipeline import run_pipeline_steps


def _write_gb(path: pathlib.Path, seq: str, name: str = "pTest", topology: str = "circular") -> str:
    rec = SeqRecord(Seq(seq), id=name, name=name)
    rec.annotations["molecule_type"] = "DNA"
    rec.annotations["topology"] = topology
    with open(path, "w", encoding="utf-8") as fh:
        SeqIO.write(rec, fh, "genbank")
    return str(path)


class ToolRegistryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)
        self.src1 = self.tmp / "plasmidA.gb"
        self.src2 = self.tmp / "plasmidB.gb"
        self.src3 = self.tmp / "plasmidC.gb"

        _write_gb(self.src1, "A" * 30 + "GAATTC" + "C" * 40 + "T" * 74, "plasmidA", "circular")
        _write_gb(self.src2, "G" * 30 + "GGATCC" + "A" * 40 + "C" * 44, "plasmidB", "circular")
        _write_gb(self.src3, "T" * 30 + "AAGCTT" + "G" * 40 + "A" * 44, "plasmidC", "circular")

    def tearDown(self):
        self._tmp.cleanup()

    def test_registry_populated(self):
        """Verify registry contains >= 28 atomic tools and valid schemas."""
        self.assertGreaterEqual(len(TOOL_REGISTRY), 28)
        defs = list_tool_definitions()
        self.assertEqual(len(defs), len(TOOL_REGISTRY))
        for d in defs:
            self.assertIn("name", d)
            self.assertIn("category", d)
            self.assertIn(d["category"], ("compute", "inspect", "write", "external", "network"))
            self.assertIn("parameters", d)

    def test_dynamic_pipeline_dispatch(self):
        """Verify CompositePipelineHandler executes tools dynamically via TOOL_REGISTRY."""
        sources = {
            "pA": str(self.src1),
            "pB": str(self.src2),
            "pC": str(self.src3),
        }
        steps = [
            {
                "step_id": "slice_a",
                "tool": "extract_subsequence",
                "params": {"source": "$pA", "start": 0, "end": 40, "strand": 1},
            },
            {
                "step_id": "rc_a",
                "tool": "reverse_complement",
                "params": {"seq": "$slice_a"},
            },
            {
                "step_id": "get_tag",
                "tool": "get_standard_element",
                "params": {"name": "6xHis"},
            },
            {
                "step_id": "fuse_tag",
                "tool": "fuse_in_frame",
                "params": {
                    "partner5": "ATGGCTAGCATGACTGGTGGACAGCAAATGGGT",  # 33 bp CDS
                    "partner3": "$get_tag",
                    "linker": "GGTGGC",
                },
            },
        ]
        final_seq, step_records, env = run_pipeline_steps(steps, sources)
        self.assertEqual(len(step_records), 4)
        self.assertIn("get_tag", env)
        self.assertIn("fuse_tag", env)
        self.assertTrue(final_seq.startswith("ATGGCTAGCATGACTGGTGGACAGCAAATGGGT"))
        # Verify 6xHis appended at end with stop codon (TAA)
        self.assertTrue(final_seq.endswith("CATCATCATCATCATCATTAA"))

    def test_tool_adapter_filtering(self):
        """Verify ToolSpec adapts params and ignores irrelevant keys gracefully."""
        spec = get_tool("calc_primer_tm")
        self.assertIsNotNone(spec)
        res = spec.execute(primer_seq="ATGCGATCGATCGATCGATC", unused_extra_param=12345)
        self.assertIn("tm", res)
        self.assertGreater(res["tm"], 40.0)
