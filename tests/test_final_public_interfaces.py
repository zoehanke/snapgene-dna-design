# -*- coding: utf-8 -*-
"""Regression tests for the final release's public entry points."""
from __future__ import annotations

import inspect
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from core.tools.registry import TOOL_REGISTRY, get_tool


ROOT = pathlib.Path(__file__).resolve().parents[1]


class FinalPublicInterfaceTests(unittest.TestCase):
    def test_pipeline_accepts_root_steps_list_through_cli(self):
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = pathlib.Path(tmp_name)
            pipeline = tmp / "pipeline.json"
            source = tmp / "source.fa"
            out_dir = tmp / "out"
            pipeline.write_text(json.dumps([
                {
                    "step_id": "reverse",
                    "tool": "reverse_complement",
                    "params": {"seq": "ATGC"},
                },
            ]), encoding="utf-8")
            source.write_text(">source\nATGCATGCATGC\n", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    "-B",
                    str(ROOT / "scripts" / "run_pipeline.py"),
                    "--pipeline",
                    str(pipeline),
                    "--sources",
                    str(source),
                    "--topology",
                    "linear",
                    "--out-dir",
                    str(out_dir),
                    "--json",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )

            self.assertEqual(
                completed.returncode,
                0,
                (completed.stderr + completed.stdout)[-2000:],
            )
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["validation_report"]["overall"], "verified")
            self.assertEqual(payload["product_length"], 4)

    def test_failed_run_replaces_previous_result_and_keeps_history_marked(self):
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = pathlib.Path(tmp_name)
            out_dir = tmp / "out"
            authoritative = out_dir / "authoritative"
            authoritative.mkdir(parents=True)
            (authoritative / "construct.gb").write_text(
                "historical construct", encoding="utf-8"
            )
            (out_dir / "pipeline_result.json").write_text(
                json.dumps({"status": "delivered", "delivery": {"status": "delivered"}}),
                encoding="utf-8",
            )

            invalid_json = tmp / "invalid.json"
            invalid_json.write_text("{", encoding="utf-8")
            first = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    "-B",
                    str(ROOT / "scripts" / "run_pipeline.py"),
                    "--pipeline",
                    str(invalid_json),
                    "--out-dir",
                    str(out_dir),
                    "--json",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            self.assertEqual(first.returncode, 1, first.stderr)
            result = json.loads((out_dir / "pipeline_result.json").read_text(
                encoding="utf-8"
            ))
            self.assertEqual(result["status"], "failed")
            self.assertIsNone(result["delivery"])
            self.assertEqual(
                result["historical_outputs"],
                [{"path": "authoritative", "status": "historical-not-current"}],
            )
            self.assertEqual(result["error"]["type"], "JSONDecodeError")
            self.assertTrue((authoritative / "construct.gb").exists())

    def test_failed_execution_replaces_previous_result(self):
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = pathlib.Path(tmp_name)
            out_dir = tmp / "out"
            authoritative = out_dir / "authoritative"
            authoritative.mkdir(parents=True)
            (authoritative / "construct.gb").write_text(
                "historical construct", encoding="utf-8"
            )
            source = tmp / "source.fa"
            source.write_text(">source\nATGC\n", encoding="utf-8")
            pipeline = tmp / "unknown.json"
            pipeline.write_text(json.dumps({
                "task_id": "failed-rerun",
                "topology": "linear",
                "sources": [{
                    "source_id": "src",
                    "path": str(source),
                }],
                "steps": [{
                    "step_id": "broken",
                    "tool": "no_such_tool",
                    "params": {},
                }],
            }), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    "-B",
                    str(ROOT / "scripts" / "run_pipeline.py"),
                    "--pipeline",
                    str(pipeline),
                    "--out-dir",
                    str(out_dir),
                    "--confirmed",
                    "--json",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            result = json.loads((out_dir / "pipeline_result.json").read_text(
                encoding="utf-8"
            ))
            self.assertEqual(result["status"], "failed")
            self.assertIsNone(result["delivery"])
            self.assertIn("no_such_tool", result["error"]["message"])
            self.assertTrue((authoritative / "construct.gb").exists())

    def test_protein_and_analysis_results_are_not_pipeline_sequences(self):
        translate = get_tool("translate_dna")
        self.assertEqual(translate.result_type, "protein")
        protein = translate.execute(seq="ATG")
        self.assertEqual(protein, "M")
        self.assertEqual(translate.extract_sequence(protein), "")
        self.assertEqual(
            translate.extract_sequence({"protein_sequence": "M", "sequence": "ATGC"}),
            "",
        )

        analysis = get_tool("find_restriction_sites")
        self.assertEqual(analysis.extract_sequence({"sequence": "ATGC"}), "")

        sequence_tool = get_tool("extract_subsequence")
        self.assertEqual(
            sequence_tool.extract_sequence({"sequence": "ATGC"}),
            "ATGC",
        )

    def test_registered_schema_properties_map_to_callable_parameters(self):
        for name, spec in TOOL_REGISTRY.items():
            signature = inspect.signature(spec.callable)
            properties = spec.parameters_schema.get("properties", {})
            aliases = spec.param_aliases
            for property_name in properties:
                mapped_name = aliases.get(property_name, property_name)
                self.assertIn(
                    mapped_name,
                    signature.parameters,
                    f"Tool '{name}': schema property '{property_name}' does not map to {signature}",
                )

            required = set(spec.parameters_schema.get("required", []))
            for required_name in required:
                mapped_name = aliases.get(required_name, required_name)
                self.assertIn(
                    mapped_name,
                    signature.parameters,
                    f"Tool '{name}': required schema property '{required_name}' is not callable",
                )

    def test_design_overhang_schema_accepts_topology_and_circular(self):
        spec = get_tool("design_overhang_primers")
        self.assertIsNotNone(spec)
        properties = spec.parameters_schema["properties"]
        self.assertIn("circular", properties)
        self.assertIn("topology", properties)
        circular_type = properties["circular"].get("type")
        self.assertIn(
            "boolean",
            circular_type if isinstance(circular_type, list) else [circular_type],
        )
        self.assertEqual(
            set(properties["topology"]["enum"]),
            {"circular", "linear"},
        )

        sequence = (
            "ATGCGTACGATCGATCGGATCCGATGCTAGCTAGGCTAACGTTGACCTGATCGGCTACGATC"
            "GATGCGTACGCTAGCTGATCGGATCCGATGCTAACGTAGCTAGGCTAACGATCGTACGATCGG"
            "CTAGCTACGATCGATGCTAGCATCGGATCA"
        )
        # Keep the repetitive input. The aliases reach the solver, which now
        # rejects its unsuitable complete primers rather than a bind error.
        with self.assertRaisesRegex(ValueError, "NO_VALID_PRIMER_PAIR"):
            spec.execute(template_record_or_seq=sequence, start=0, end=100,
                         prefer_primer3=False, circular=False, topology="linear")


if __name__ == "__main__":
    unittest.main(verbosity=2)
