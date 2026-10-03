# -*- coding: utf-8 -*-
"""tests/test_cli_scenarios.py - Automated regression tests for Host LLM CLI entrypoints."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from Bio import SeqIO

ROOT = SKILL_ROOT
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "fixtures"


class TestCLIScenarios(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_synthetic_fixture_invariants(self):
        synth = FIXTURES / "synthetic" / "pSynthetic-GFP.gb"
        self.assertTrue(synth.exists(), f"Synthetic fixture missing: {synth}")

        rec = SeqIO.read(str(synth), "genbank")
        seq_str = str(rec.seq).upper()

        # Invariant 1: exact length 2500 bp
        self.assertEqual(len(seq_str), 2500)
        self.assertEqual(rec.annotations.get("topology"), "circular")

        # Invariant 2: fixed deterministic SHA256
        seq_sha = hashlib.sha256(seq_str.encode("utf-8")).hexdigest().upper()
        self.assertEqual(seq_sha, "21541EFEE3C76CBA0F574A6C29055E811F306B7C485132489F0F00247C6BF969")

        # Invariant 3: essential annotated biological features
        feature_types = [f.type for f in rec.features]
        self.assertIn("rep_origin", feature_types)
        self.assertIn("CDS", feature_types)

        # Check GFP and AmpR CDS features
        gfp_feats = [
            f for f in rec.features
            if f.type == "CDS" and any("gfp" in str(v).lower() for v in f.qualifiers.get("label", []) + f.qualifiers.get("gene", []))
        ]
        self.assertEqual(len(gfp_feats), 1)
        gfp_feat = gfp_feats[0]
        gfp_seq = str(gfp_feat.extract(rec.seq)).upper()
        self.assertEqual(len(gfp_seq) % 3, 0)
        self.assertTrue(gfp_seq.startswith("ATG"))
        self.assertTrue(gfp_seq.endswith(("TAA", "TAG", "TGA")))

        ampr_feats = [
            f for f in rec.features
            if f.type == "CDS" and any(("amp" in str(v).lower() or "bla" in str(v).lower()) for v in f.qualifiers.get("label", []) + f.qualifiers.get("gene", []))
        ]
        self.assertEqual(len(ampr_feats), 1)
        ampr_feat = ampr_feats[0]
        ampr_seq = str(ampr_feat.extract(rec.seq)).upper()
        self.assertEqual(len(ampr_seq) % 3, 0)
        self.assertTrue(ampr_seq.startswith("ATG"))
        self.assertTrue(ampr_seq.endswith(("TAA", "TAG", "TGA")))

    def test_inspect_plasmid_cli(self):
        synth = FIXTURES / "synthetic" / "pSynthetic-GFP.gb"
        self.assertTrue(synth.exists(), f"Fixture missing: {synth}")

        cmd = [
            sys.executable,
            "-X", "utf8", "-B",
            str(SCRIPTS / "inspect_plasmid.py"),
            str(synth),
            "--json",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res.returncode, 0, f"inspect_plasmid failed: {res.stderr}")

        data = json.loads(res.stdout)
        self.assertEqual(data["file_name"], "pSynthetic-GFP.gb")
        self.assertEqual(data["length_bp"], 2500)
        self.assertEqual(data["topology"], "circular")
        self.assertGreater(len(data["origin_of_replication"]), 0)
        self.assertGreater(len(data["selection_markers"]), 0)
        self.assertGreater(len(data["cds_features"]), 0)
        self.assertTrue(all(cds["in_frame"] for cds in data["cds_features"]))

        # Also verify Markdown text output mode
        cmd_md = [
            sys.executable,
            "-X", "utf8", "-B",
            str(SCRIPTS / "inspect_plasmid.py"),
            str(synth),
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
        synth = FIXTURES / "synthetic" / "pSynthetic-GFP.gb"
        pipe_def = {
            "task_id": "test_e2e_pipeline",
            "topology": "linear",
            "sources": [{"source_id": "plasmid", "path": str(synth)}],
            "steps": [
                {
                    "step_id": "slice_gfp",
                    "tool": "extract_subsequence",
                    "params": {
                        "file_path_or_record": "$plasmid",
                        "start": 171,
                        "end": 888,
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

        # 1. Unconfirmed execution -> verified-candidate, no authoritative directory
        cmd_unconf = [
            sys.executable,
            "-X", "utf8", "-B",
            str(SCRIPTS / "run_pipeline.py"),
            "--pipeline", str(pipe_file),
            "--out-dir", str(out_dir),
            "--json",
        ]
        res_unconf = subprocess.run(cmd_unconf, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res_unconf.returncode, 0, f"run_pipeline candidate failed: {res_unconf.stderr}")
        data_unconf = json.loads(res_unconf.stdout)
        self.assertEqual(data_unconf["status"], "verified-candidate")
        self.assertIsNone(data_unconf["delivery"])

        # 2. Confirmed execution -> delivered, authoritative directory created
        cmd_conf = [
            sys.executable,
            "-X", "utf8", "-B",
            str(SCRIPTS / "run_pipeline.py"),
            "--pipeline", str(pipe_file),
            "--out-dir", str(out_dir),
            "--confirmed",
            "--json",
        ]
        res_conf = subprocess.run(cmd_conf, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(res_conf.returncode, 0, f"run_pipeline confirmed failed: {res_conf.stderr}")

        data = json.loads(res_conf.stdout)
        self.assertEqual(data["status"], "delivered")
        self.assertEqual(data["product_length"], 717)
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
