# -*- coding: utf-8 -*-
"""Independent numerical cross-validation tests."""
import pathlib
import sys
import unittest

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))

import validation_crosscheck as vc  # noqa: E402


class TmCrosscheckTests(unittest.TestCase):
    def test_primer3_bio_nn_agree_within_tolerance(self):
        # Primer3 default salt: 50 mM Na, 1.5 mM Mg.  Bio NN with the same
        # salt should agree within ~1 C.
        result = vc.primer_tm_crosscheck("AAAGCGGCACTTGTGAAGT", 58.2)
        self.assertEqual(result["status"], "consistent")
        self.assertLess(result["delta_primary_bio_c"], 2.0)

    def test_wrong_primary_tm_flags_conflict(self):
        result = vc.primer_tm_crosscheck("AAAGCGGCACTTGTGAAGT", 40.0)
        self.assertIn("tm_method_disagreement",
                      [c["kind"] for c in result["conflicts"]])
        self.assertIn("tm_outside_52_72",
                      [c["kind"] for c in result["conflicts"]])
        self.assertEqual(result["status"], "conflict-error")

    def test_wallace_formula_is_short_oligo_approximation(self):
        result = vc.wallace_tm("ACGTACGT")
        self.assertEqual(result["tm"], 24.0)
        self.assertIn("Wallace", result["source"])

    def test_empty_and_non_iupac(self):
        empty = vc.primer_tm_crosscheck("", 0.0)
        self.assertIsNone(empty["bio_nn_tm"])
        weird = vc.primer_tm_crosscheck("ACGTN", 50.0)
        self.assertIn("other", vc.manual_gc_percent("ACGTN")["counts"])


class GcCrosscheckTests(unittest.TestCase):
    def test_manual_and_biopython_agree(self):
        result = vc.overlap_crosscheck("GCGCATATGCGCATAT")
        self.assertEqual(result["status"], "consistent")
        self.assertAlmostEqual(result["gc_manual"]["gc_percent"],
                               result["gc_biopython"]["gc_percent"], places=2)
        self.assertEqual(result["overlap"], "GCGCATATGCGCATAT")

    def test_empty_overlap(self):
        result = vc.overlap_crosscheck("")
        self.assertIsNone(result["gc_manual"]["gc_percent"])
        self.assertIsNone(result["gc_biopython"]["gc_percent"])


class RestrictionCrosscheckTests(unittest.TestCase):
    def test_ecoRI_counts_agree(self):
        result = vc.restriction_site_crosscheck(
            "A" * 10 + "GAATTC" + "C" * 10, "EcoRI")
        self.assertTrue(result["consistent_count"])
        self.assertEqual(result["direct_motif_count"], 1)
        self.assertEqual(result["bio_hit_count"], 1)

    def test_non_palindromic_site_both_orientations(self):
        # BsaI recognition GGTCTC; reverse-complement GAGACC also searched.
        result = vc.restriction_site_crosscheck(
            "GGTCTC" + "A" * 10 + "GAGACC", "BsaI")
        self.assertEqual(result["direct_motif_count"], 2)
        self.assertTrue(result["consistent_count"])

    def test_unknown_enzyme_fails_structured(self):
        with self.assertRaises(ValueError):
            vc.restriction_site_crosscheck("ACGT", "NOT_AN_ENZYME")


if __name__ == "__main__":
    unittest.main(verbosity=2)
