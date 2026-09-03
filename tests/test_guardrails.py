# -*- coding: utf-8 -*-
"""tests/test_guardrails.py - Rigorous unit tests for Tier 3 Biological Guardrails."""
import unittest

from core.guardrails import (
    FOUNDATIONAL_CHECKLIST,
    get_biological_self_audit_checklist,
    quick_biological_sanity_check,
    scan_crispr_recleavage_risk,
    scan_u6_pol3_termination,
)


class TestBiologicalGuardrails(unittest.TestCase):

    def test_foundational_checklist(self):
        items = get_biological_self_audit_checklist()
        self.assertEqual(len(items), 7)
        ids = [it["id"] for it in items]
        self.assertIn("BIO-01-FRAME", ids)
        self.assertIn("BIO-02-STOP", ids)
        self.assertIn("BIO-03-ENZYME", ids)
        self.assertIn("BIO-04-STRAND", ids)
        self.assertIn("BIO-05-RECLEAVAGE", ids)
        self.assertIn("BIO-06-POL3_TERMINATION", ids)
        self.assertIn("BIO-07-PRIMER_DIMER", ids)

    def test_bio01_and_bio02_reading_frame(self):
        # 1. Clean CDS: multiple of 3, ATG start, TAA stop, no premature stop
        clean_cds = "ATG" + "GCT" * 10 + "TAA"
        res = quick_biological_sanity_check(clean_cds)
        self.assertTrue(res["is_multiple_of_three"])
        self.assertFalse(res["has_premature_stop"])
        self.assertTrue(res["terminal_stop_present"])
        self.assertTrue(res["clean_for_expression"])

        # 2. Frameshift (+1 bp)
        frameshift = "ATG" + "GCT" * 10 + "A" + "TAA"
        res_fs = quick_biological_sanity_check(frameshift)
        self.assertFalse(res_fs["is_multiple_of_three"])
        self.assertFalse(res_fs["clean_for_expression"])
        self.assertTrue(any("BIO-01" in issue for issue in res_fs["issues_found"]))

        # 3. Premature stop inside
        premature = "ATG" + "GCT" * 3 + "TAA" + "GCT" * 5 + "TGA"
        res_pre = quick_biological_sanity_check(premature)
        self.assertTrue(res_pre["has_premature_stop"])
        self.assertEqual(len(res_pre["premature_stop_positions"]), 1)
        self.assertTrue(any("BIO-01" in issue for issue in res_pre["issues_found"]))

    def test_bio03_internal_enzyme_conflict(self):
        # Sequence containing EcoRI (GAATTC)
        seq_with_ecori = "ATG" + "GAATTC" + "TAA"
        res = quick_biological_sanity_check(seq_with_ecori, cloning_enzymes=["EcoRI", "BamHI"])
        self.assertEqual(len(res["internal_enzyme_conflicts"]), 1)
        self.assertEqual(res["internal_enzyme_conflicts"][0]["enzyme"], "EcoRI")
        self.assertTrue(any("BIO-03" in issue for issue in res["issues_found"]))

    def test_bio05_crispr_recleavage_scan(self):
        grna = "ACGTACGTACGTACGTACGT"  # 20 nt
        # Donor with intact target and PAM (AGG)
        donor_intact = "A" * 30 + grna + "AGG" + "C" * 30
        res_intact = scan_crispr_recleavage_risk(donor_intact, grna)
        self.assertTrue(res_intact["recleavage_risk"])
        self.assertTrue(res_intact["intact_spacer_found"])
        self.assertTrue(res_intact["intact_seed_pam_found"])

        # Donor with mutated PAM (AGA instead of AGG)
        donor_mutated = "A" * 30 + grna + "AGA" + "C" * 30
        res_mutated = scan_crispr_recleavage_risk(donor_mutated, grna)
        self.assertFalse(res_mutated["intact_seed_pam_found"])

        # Integrated in quick_biological_sanity_check
        res_check = quick_biological_sanity_check(donor_intact, crispr_grna_seq=grna)
        self.assertTrue(any("BIO-05" in issue for issue in res_check["issues_found"]))

    def test_bio06_u6_pol3_termination_scan(self):
        # Spacer with TTTT
        spacer_bad = "ACGT" + "TTTT" + "ACGTACGTACGT"
        res_bad = scan_u6_pol3_termination(spacer_bad)
        self.assertTrue(res_bad["has_poly_t_terminator"])
        self.assertEqual(res_bad["terminator_count"], 1)

        # Spacer without TTTT
        spacer_good = "ACGT" + "TTAT" + "ACGTACGTACGT"
        res_good = scan_u6_pol3_termination(spacer_good)
        self.assertFalse(res_good["has_poly_t_terminator"])

        # Integrated in quick_biological_sanity_check
        res_check = quick_biological_sanity_check(spacer_bad, check_u6_termination=True)
        self.assertTrue(any("BIO-06" in issue for issue in res_check["issues_found"]))

    def test_bio07_primer_dimer_scan(self):
        # Primers with complementary 3' ends: Fwd ends in GGCC, Rev ends in GGCC (binds each other)
        fwd_dimer = "ATGCATGCATGCATGCGGCC"
        rev_dimer = "TACGTACGTACGTACGGGCC"
        res_check = quick_biological_sanity_check("ATGTAA", primers=[fwd_dimer, rev_dimer])
        self.assertIsNotNone(res_check["primer_dimer_audit"])
        self.assertTrue(res_check["primer_dimer_audit"]["high_dimer_risk"])
        self.assertGreaterEqual(res_check["primer_dimer_audit"]["max_3prime_complementarity"], 4)
        self.assertTrue(any("BIO-07" in issue for issue in res_check["issues_found"]))

        # Primers without complementary 3' ends
        fwd_clean = "ATGCATGCATGCATGCATGC"
        rev_clean = "TACGTACGTACGTACGTACG"
        res_clean = quick_biological_sanity_check("ATGTAA", primers=[fwd_clean, rev_clean])
        self.assertFalse(res_clean["primer_dimer_audit"]["high_dimer_risk"])

    def test_all_clean_flag(self):
        clean_cds = "ATG" + "GCT" * 10 + "TAA"
        res = quick_biological_sanity_check(
            clean_cds,
            cloning_enzymes=["EcoRI"],
            primers=["ATGCATGCATGCATGCATGC", "TACGTACGTACGTACGTACG"],
        )
        self.assertTrue(res["all_clean"])
        self.assertEqual(len(res["issues_found"]), 0)


if __name__ == "__main__":
    unittest.main()
