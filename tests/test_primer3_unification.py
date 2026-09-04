# -*- coding: utf-8 -*-
"""tests/test_primer3_unification.py - Tests for unified Primer3 integration in core tools."""
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
        self.assertIn("primer3", res["engine"].lower())
        self.assertIn("primer3_metrics", res)
        self.assertIsNotNone(res["primer3_metrics"]["penalty"])
        self.assertIsNotNone(res["primer3_metrics"]["heterodimer_tm"])
        self.assertTrue(res["forward_primer"]["full_sequence"].startswith("GAATTC"))
        self.assertTrue(res["reverse_primer"]["full_sequence"].startswith("GGATCC"))
        self.assertLessEqual(res["binding_core_delta_tm"], 3.0)

    def test_design_overhang_primers_fallback_resilience(self):
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
        self.assertEqual(res["engine"], "SantaLucia-Heuristic [Fallback]")
        self.assertTrue(res["forward_primer"]["full_sequence"].startswith("GAATTC"))
        self.assertTrue(res["reverse_primer"]["full_sequence"].startswith("GGATCC"))


if __name__ == "__main__":
    unittest.main()
