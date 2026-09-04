# -*- coding: utf-8 -*-
"""tests/test_cli_scenarios.py - Automated regression tests for Host LLM CLI entrypoints."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "fixtures"


class TestCLIScenarios(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_inspect_plasmid_cli(self):
        pentr = FIXTURES / "golden" / "pENTR-EmGFP.gb"
        self.assertTrue(pentr.exists(), f"Fixture missing: {pentr}")

        cmd = [
            sys.executable,
            "-X", "utf8", "-B",
            str(SCRIPTS / "inspect_plasmid.py"),
            str(pentr),
            "--json",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, f"inspect_plasmid failed: {res.stderr}")

        data = json.loads(res.stdout)
        self.assertEqual(data["file_name"], "pENTR-EmGFP.gb")
        self.assertEqual(data["length_bp"], 2977)
        self.assertEqual(data["topology"], "circular")
        self.assertGreater(len(data["origin_of_replication"]), 0)
        self.assertGreater(len(data["selection_markers"]), 0)
        self.assertGreater(len(data["cds_features"]), 0)
        self.assertTrue(data["cds_features"][0]["in_frame"])

        # Also verify Markdown text output mode
        cmd_md = [
            sys.executable,
            "-X", "utf8", "-B",
            str(SCRIPTS / "inspect_plasmid.py"),
            str(pentr),
        ]
        res_md = subprocess.run(cmd_md, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res_md.returncode, 0)
        self.assertIn("Plasmid Inspection:", res_md.stdout)
        self.assertIn("Annotated CDS:", res_md.stdout)

    def test_run_recipe_protein_tagging_cli(self):
        params = {
            "target_cds_seq_or_file": "ATGAAACCCGGGTTTTAA",
            "tag_name_or_seq": "6xHis",
            "tag_position": "C-terminal",
            "linker_type": "flexible_G4S_x1",
            "protease_site": "TEV",
        }
        params_file = self.tmp / "tag_params.json"
        params_file.write_text(json.dumps(params), encoding="utf-8")

        out_dir = self.tmp / "tag_out"
        cmd = [
            sys.executable,
            "-X", "utf8", "-B",
            str(SCRIPTS / "run_recipe.py"),
            "--recipe", "recipe_protein_tagging",
            "--params-json", str(params_file),
            "--out-dir", str(out_dir),
            "--json",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, f"run_recipe failed: {res.stderr}")

        data = json.loads(res.stdout)
        self.assertEqual(data["recipe"], "recipe_protein_tagging")
        self.assertEqual(data["result_kind"], "component")
        self.assertEqual(data["completeness"], "component_only")
        self.assertGreater(data["product_length"], 0)

        # Check candidate files
        cand_dir = pathlib.Path(data["candidate_directory"])
        self.assertTrue(cand_dir.exists())
        self.assertTrue((cand_dir / "recipe_protein_tagging.fasta").exists())
        self.assertTrue((cand_dir / "recipe_protein_tagging_result.json").exists())

        # Check guardrails
        sanity = data["sanity_check"]
        self.assertTrue(sanity["all_applicable_pass"])
        self.assertEqual(sanity["guardrail_status_table"]["BIO-01-FRAME"]["status"], "PASS")
        self.assertEqual(sanity["guardrail_status_table"]["BIO-02-STOP"]["status"], "PASS")

    def test_run_pipeline_cli_end_to_end(self):
        pentr = FIXTURES / "golden" / "pENTR-EmGFP.gb"
        pipe_def = {
            "task_id": "test_e2e_pipeline",
            "topology": "linear",
            "sources": [str(pentr)],
            "steps": [
                {
                    "step_id": "slice_gfp",
                    "tool": "extract_subsequence",
                    "params": {
                        "file_path_or_record": str(pentr),
                        "start": 431,
                        "end": 1151,
                        "strand": 1,
                        "topology": "circular",
                    },
                },
                {
                    "step_id": "reverse_comp",
                    "tool": "reverse_complement",
                    "params": {"seq": "$slice_gfp"},
                },
            ],
        }
        pipe_file = self.tmp / "pipeline.json"
        pipe_file.write_text(json.dumps(pipe_def), encoding="utf-8")

        out_dir = self.tmp / "pipeline_out"
        cmd = [
            sys.executable,
            "-X", "utf8", "-B",
            str(SCRIPTS / "run_pipeline.py"),
            "--pipeline", str(pipe_file),
            "--out-dir", str(out_dir),
            "--confirmed",
            "--json",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, f"run_pipeline failed: {res.stderr}")

        data = json.loads(res.stdout)
        self.assertEqual(data["status"], "delivered")
        self.assertEqual(data["product_length"], 720)
        self.assertTrue(data["validation_report"]["artifact_valid"])
        self.assertTrue(data["validation_report"]["computation_valid"])
        self.assertTrue(data["validation_report"]["goal_valid"])

        # Check authoritative delivery
        deliv = data["delivery"]
        self.assertIsNotNone(deliv)
        auth_dir = pathlib.Path(deliv["directory"])
        self.assertTrue((auth_dir / "construct.dna").exists())
        self.assertTrue((auth_dir / "construct.gb").exists())
        self.assertTrue((auth_dir / "construct.fasta").exists())
        self.assertTrue((auth_dir / "DELIVERY-MANIFEST.json").exists())


if __name__ == "__main__":
    unittest.main()
