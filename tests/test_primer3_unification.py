# -*- coding: utf-8 -*-
"""tests/test_primer3_unification.py - Tests for unified Primer3 integration in core tools."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import unittest

from core.tools.amplification import design_overhang_primers
from scripts.primer3_core_backend import discover_primer3_core


class TestPrimer3Unification(unittest.TestCase):
    def test_discover_primer3_core_found(self):
        core_path = discover_primer3_core()
        self.assertIsNotNone(core_path, "primer3_core should be discovered on this machine")

    def test_design_overhang_primers_uses_primer3(self):
        seq = (
            "G" * 30
            + "ATGGCTAGCAAAGGAGAAGAACTTTTCACTGGAGTTGTCCCAATTCTTGTTGAATTAGATGGTGATGTTAATGGGCACAAATTTTCTGTCCGTGGAGAGGGTGAAGGTGATGCTACAAACGGAAAACTCACCC"
            + "C" * 30
        )
        res = design_overhang_primers(
            seq,
            start=30,
            end=155,
            fwd_5prime_overhang="GAATTC",
            rev_5prime_overhang="GGATCC",
            target_tm=60.0,
            prefer_primer3=True,
        )
        self.assertIn("primer3", res.analysis['engine'].lower())
        self.assertIn("primer3_metrics", res.analysis)
        self.assertIsNotNone(res.analysis['primer3_metrics']["penalty"])
        self.assertIsNotNone(res.analysis['primer3_metrics']["heterodimer_tm"])
        self.assertTrue(res.analysis['forward_primer']["full_sequence"].startswith("GAATTC"))
        self.assertTrue(res.analysis['reverse_primer']["full_sequence"].startswith("GGATCC"))
        self.assertLessEqual(res.analysis['binding_core_delta_tm'], 3.0)

    def test_design_overhang_primers_biopython_core_with_full_structure_qc(self):
        seq = (
            "G" * 30
            + "ATGGCTAGCAAAGGAGAAGAACTTTTCACTGGAGTTGTCCCAATTCTTGTTGAATTAGATGGTGATGTTAATGGGCACAAATTTTCTGTCCGTGGAGAGGGTGAAGGTGATGCTACAAACGGAAAACTCACCC"
            + "C" * 30
        )
        res = design_overhang_primers(
            seq,
            start=30,
            end=155,
            fwd_5prime_overhang="GAATTC",
            rev_5prime_overhang="GGATCC",
            target_tm=60.0,
            prefer_primer3=False,
        )
        self.assertEqual(res.analysis['engine'], "Biopython NN core search + Primer3 structure")
        self.assertTrue(res.analysis['forward_primer']["full_sequence"].startswith("GAATTC"))
        self.assertTrue(res.analysis['reverse_primer']["full_sequence"].startswith("GGATCC"))
        structure = res.analysis['primer3_metrics']["selected_pair_quality"]["complete_oligo_structure"]
        self.assertTrue(structure["passed"])
        self.assertEqual(structure["scope"], "complete oligos including all 5prime tails")
        self.assertEqual(structure["engine"], "Primer3 check_primers")
        self.assertEqual(structure["conditions"]["monovalent_mM"], 50)

    def test_ensure_primer3_core(self):
        from scripts.primer3_core_backend import ensure_primer3_core
        # When already installed, ensure_primer3_core returns path
        core_path = ensure_primer3_core(auto_install=False, verbose=False)
        self.assertIsNotNone(core_path)

        # When an explicit non-existent path is requested without auto_install, returns None safely
        res_nonexistent = ensure_primer3_core(explicit="non_existent_primer3_path", auto_install=False, verbose=False)
        self.assertIsNone(res_nonexistent)

    def test_install_primer3_script_json_mode(self):
        import subprocess
        import sys
        import json
        proc = subprocess.run(
            [sys.executable, str(RUNTIME_SCRIPTS / "install_primer3.py"), "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, f"install_primer3.py exited with {proc.returncode}: {proc.stderr}")
        data = json.loads(proc.stdout)
        self.assertTrue(data.get("ok"))
        self.assertIn("path", data)
        self.assertEqual(data.get("verification", {}).get("status"), "verified")


if __name__ == "__main__":
    unittest.main()
