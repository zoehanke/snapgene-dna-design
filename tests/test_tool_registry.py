# -*- coding: utf-8 -*-
"""Unit tests for unified Tool Registry and dynamic CompositePipeline execution."""
from __future__ import annotations

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS

import inspect
import pathlib
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.tools.registry import (
    TOOL_REGISTRY,
    DuplicateToolRegistration,
    ToolSpec,
    get_tool,
    list_tool_definitions,
    register_tool,
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

    def test_registry_size_and_schema_definitions(self):
        """Verify registry contains the current tools with no duplicate definitions."""
        self.assertEqual(len(TOOL_REGISTRY), 43)
        defs = list_tool_definitions()
        self.assertEqual(len(defs), 43)
        self.assertIn("prepare_pcr_fragment", TOOL_REGISTRY)
        names = [d["name"] for d in defs]
        self.assertIn("prepare_pml104_guide", TOOL_REGISTRY)
        self.assertIn("prepare_pml104_guide", names)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), set(TOOL_REGISTRY))
        for d in defs:
            self.assertIn("name", d)
            self.assertIn("category", d)
            self.assertIn(d["category"], ("compute", "inspect", "write", "external", "network"))
            self.assertIn("parameters", d)

    def test_duplicate_registration_raises_error(self):
        """Verify registering an existing tool name raises DuplicateToolRegistration."""
        existing = next(iter(TOOL_REGISTRY.values()))
        dup = ToolSpec(
            name=existing.name,
            callable=existing.callable,
            category=existing.category,
            description="Duplicate attempt",
            parameters_schema={"type": "object"},
        )
        with self.assertRaises(DuplicateToolRegistration):
            register_tool(dup)

    def test_all_tools_signature_contract(self):
        """Verify for every tool in registry that schema matches underlying callable signature."""
        for name, spec in TOOL_REGISTRY.items():
            sig = inspect.signature(spec.callable)
            schema = spec.parameters_schema
            props = schema.get("properties", {})
            reqs = set(schema.get("required", []))
            aliases = spec.param_aliases

            # 1. All required schema parameters must map to a callable parameter
            for r in reqs:
                mapped_name = aliases.get(r, r)
                self.assertIn(
                    mapped_name,
                    sig.parameters,
                    f"Tool '{name}': required schema property '{r}' (mapped to '{mapped_name}') not found in callable signature {sig}",
                )

            # 2. All required callable parameters (without default) must be accounted for in schema
            for p_name, p in sig.parameters.items():
                if p.default == inspect.Parameter.empty and p.kind in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                ):
                    # Check if p_name is in schema props or mapped via alias
                    in_schema = (p_name in props) or any(target == p_name for target in aliases.values())
                    self.assertTrue(
                        in_schema,
                        f"Tool '{name}': callable parameter '{p_name}' has no default but is missing from parameters_schema properties or aliases",
                    )

    def test_tool_execution_with_aliases(self):
        """Verify ToolSpec executes correctly with aliases and rejects unknown parameters."""
        spec = get_tool("calc_primer_tm")
        self.assertIsNotNone(spec)
        res = spec.execute(primer_seq="ATGCGATCGATCGATCGATC")
        self.assertIn("tm", res.analysis)
        self.assertGreater(res.analysis["tm"], 40.0)

        # Unknown arguments must NOT be silently dropped; inspect.signature.bind must raise TypeError
        from core.errors import ToolExecutionError
        with self.assertRaises(ToolExecutionError):
            spec.execute(primer_seq="ATGCGATCGATCGATCGATC", unknown_unexpected_arg=999)

    def test_get_feature_tool_contract(self):
        """Verify get_feature accepts file_path_or_record and aliases."""
        tool = get_tool("get_feature")
        self.assertIsNotNone(tool)
        # Execute on a test file
        with self.assertRaisesRegex(ValueError,'not found'):
            tool.execute(file_path_or_record=str(self.src1), name_or_type="misc_feature")
        self.assertEqual(tool.execute(file_path_or_record=str(self.src1),name_or_type='misc_feature',return_all=True).products,[])

    def test_strip_terminal_codons_tool_contract(self):
        """Verify strip_terminal_codons works with schema."""
        tool = get_tool("strip_terminal_codons")
        self.assertIsNotNone(tool)
        res = tool.execute(cds_seq="ATGAAATGA", strip_start=True, strip_stop=True)
        self.assertEqual(str(res.only_product().seq), "AAA")

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
        self.assertTrue(str(final_seq.seq).startswith("ATGGCTAGCATGACTGGTGGACAGCAAATGGGT"))
        self.assertTrue(str(final_seq.seq).endswith("CATCATCATCATCATCATTAA"))


if __name__ == "__main__":
    unittest.main()
