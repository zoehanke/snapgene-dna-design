# -*- coding: utf-8 -*-
"""tests/test_guardrails.py - Rigorous unit tests for Tier 3 Biological Guardrails (BIO-01 through BIO-10)."""
import unittest

from Bio.Seq import Seq
from Bio.SeqFeature import SeqFeature, FeatureLocation
from Bio.SeqRecord import SeqRecord

from core.guardrails import (
    FOUNDATIONAL_CHECKLIST,
    get_biological_self_audit_checklist,
    quick_biological_sanity_check,
    scan_crispr_recleavage_risk,
    scan_inverted_repeats_and_hairpins,
    scan_methylation_blockade,
    scan_plasmid_maintenance_elements,
    scan_u6_pol3_termination,
)


class TestBiologicalGuardrails(unittest.TestCase):

    def test_foundational_checklist(self):
        items = get_biological_self_audit_checklist()
        self.assertEqual(len(items), 10)
        ids = [it["id"] for it in items]
        self.assertIn("BIO-01-FRAME", ids)
        self.assertIn("BIO-02-STOP", ids)
        self.assertIn("BIO-03-ENZYME", ids)
        self.assertIn("BIO-04-STRAND", ids)
        self.assertIn("BIO-05-RECLEAVAGE", ids)
        self.assertIn("BIO-06-POL3_TERMINATION", ids)
        self.assertIn("BIO-07-PRIMER_DIMER", ids)
        self.assertIn("BIO-08-REPLICON_MARKER", ids)
        self.assertIn("BIO-09-METHYLATION", ids)
        self.assertIn("BIO-10-HAIRPIN_REPEAT", ids)

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

    def test_bio08_plasmid_maintenance_elements(self):
        # 1. Circular record with both ori and AmpR
        rec = SeqRecord(Seq("ATGC" * 100), id="pGood")
        rec.annotations["topology"] = "circular"
        rec.features.append(SeqFeature(FeatureLocation(0, 100), type="rep_origin", qualifiers={"label": ["pUC ori"]}))
        rec.features.append(SeqFeature(FeatureLocation(150, 300), type="CDS", qualifiers={"label": ["AmpR"]}))

        res_good = scan_plasmid_maintenance_elements(rec)
        self.assertTrue(res_good["applicable"])
        self.assertTrue(res_good["has_origin"])
        self.assertTrue(res_good["has_marker"])
        self.assertFalse(res_good["missing_essential_maintenance"])

        # 2. Circular record lacking both ori and marker
        rec_empty = SeqRecord(Seq("ATGC" * 100), id="pEmpty")
        rec_empty.annotations["topology"] = "circular"
        res_bad = scan_plasmid_maintenance_elements(rec_empty)
        self.assertTrue(res_bad["applicable"])
        self.assertFalse(res_bad["has_origin"])
        self.assertFalse(res_bad["has_marker"])
        self.assertTrue(res_bad["missing_essential_maintenance"])

        # Integrated in quick_biological_sanity_check
        res_check = quick_biological_sanity_check(rec_empty)
        self.assertTrue(any("BIO-08" in issue for issue in res_check["issues_found"]))

        # Linear fragment should not be flagged
        res_linear = quick_biological_sanity_check("ATGC" * 100, topology="linear")
        self.assertFalse(any("BIO-08" in issue for issue in res_linear["issues_found"]))

    def test_bio09_methylation_blockade(self):
        # XbaI (TCTAGA) followed immediately by TC forms Dam overlap: TCTAGATC (Dam is GATC)
        seq_blocked = "AAAA" + "TCTAGATC" + "GGGG"
        res_blocked = scan_methylation_blockade(seq_blocked, cloning_enzymes=["XbaI"])
        self.assertTrue(res_blocked["has_methylation_blockade"])
        self.assertIn("XbaI", res_blocked["blocked_enzymes"])

        # XbaI not followed by TC: TCTAGACC (no Dam overlap)
        seq_clean = "AAAA" + "TCTAGACC" + "GGGG"
        res_clean = scan_methylation_blockade(seq_clean, cloning_enzymes=["XbaI"])
        self.assertFalse(res_clean["has_methylation_blockade"])

        # Integrated in quick_biological_sanity_check
        res_check = quick_biological_sanity_check(seq_blocked, cloning_enzymes=["XbaI"])
        self.assertTrue(any("BIO-09" in issue for issue in res_check["issues_found"]))

    def test_bio10_inverted_repeats_and_hairpins(self):
        # 16-bp inverted repeat forming strong hairpin: CGCGAATTCGCGAATT
        rep = "CGCGAATTCGCGAATT"
        rep_rc = str(Seq(rep).reverse_complement())
        seq_with_repeat = "AAAA" + rep + "TTTTTT" + rep_rc + "GGGG"

        res_rep = scan_inverted_repeats_and_hairpins(seq_with_repeat, min_repeat_len=14)
        self.assertTrue(res_rep["has_severe_secondary_structure"])
        self.assertTrue(res_rep["has_inverted_repeats"])
        self.assertGreaterEqual(res_rep["inverted_repeats"][0]["length"], 14)

        # Clean sequence without long inverted repeats
        seq_clean = "ATG" + "GCT" * 20 + "TAA"
        res_clean = scan_inverted_repeats_and_hairpins(seq_clean, min_repeat_len=14)
        self.assertFalse(res_clean["has_severe_secondary_structure"])

        # Integrated in quick_biological_sanity_check with check_secondary_structure=True
        res_check = quick_biological_sanity_check(seq_with_repeat, check_secondary_structure=True)
        self.assertTrue(any("BIO-10" in issue for issue in res_check["issues_found"]))

    def test_all_clean_flag(self):
        clean_cds = "ATG" + "GCT" * 10 + "TAA"
        res = quick_biological_sanity_check(
            clean_cds,
            cloning_enzymes=["EcoRI"],
            primers=["ATGCATGCATGCATGCATGC", "TACGTACGTACGTACGTACG"],
            check_secondary_structure=True,
        )
        self.assertTrue(res["all_clean"])
        self.assertEqual(len(res["issues_found"]), 0)


if __name__ == "__main__":
    unittest.main()
