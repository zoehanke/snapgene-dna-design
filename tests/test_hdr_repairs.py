# -*- coding: utf-8 -*-
"""Focused regressions for explicit HDR replacement and short dsDNA donors."""
import unittest

from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.recipes.crispr_hdr import recipe_crispr_hdr_donor
from core.tools.crispr import design_hdr_donor


GUIDE = "TAACAATTTACGTATTAGGC"
GUIDE_RC = str(Seq(GUIDE).reverse_complement())


def _negative_strand_target():
    """Return a small record with a real reverse-strand SpCas9 site."""
    sequence = "A" * 80 + "CCA" + GUIDE_RC + "T" * 97
    record = SeqRecord(Seq(sequence), id="negative_hdr")
    record.annotations.update({"molecule_type": "DNA", "topology": "linear"})
    record.features.append(
        SeqFeature(
            FeatureLocation(0, len(sequence), strand=-1),
            type="CDS",
            qualifiers={"label": ["negative_cds"], "codon_start": ["1"]},
        )
    )
    return record


def _negative_cds_with_pam_codon():
    """Construct a negative CDS whose PAM overlaps a CTG codon."""
    sequence = "A" * 101 + "CCA" + GUIDE_RC + "T" * 176
    record = SeqRecord(Seq(sequence), id="negative_cds_pam")
    record.annotations.update({"molecule_type": "DNA", "topology": "linear"})
    record.features.append(
        SeqFeature(
            FeatureLocation(0, len(sequence), strand=-1),
            type="CDS",
            qualifiers={"label": ["negative_cds"], "codon_start": ["1"]},
        )
    )
    return record


class HDRRepairTests(unittest.TestCase):
    def test_replacement_arms_surround_payload_and_prefer_non_nag_pam(self):
        record = _negative_cds_with_pam_codon()
        result = design_hdr_donor(
            record,
            cut_position_0based=107,
            edit_dna="TCC",
            edit_start_0based=120,
            edit_end_0based=123,
            left_arm_length=43,
            right_arm_length=44,
            grna_seq=GUIDE,
            grna_strand=-1,
            donor_type="dsDNA",
        )

        self.assertEqual(result["total_length"], 90)
        self.assertEqual(result["left_arm_length"], 43)
        self.assertEqual(result["right_arm_length"], 44)
        self.assertEqual(result["donor_edit_interval_0based"], [43, 46])
        self.assertEqual(result["donor_sequence"][43:46], "TCC")
        self.assertEqual(result["guide"]["edited_pam_sequence"], "TCG")
        self.assertEqual(result["mutations_applied"][0]["alt_codon"], "CTC")
        self.assertNotEqual(result["guide"]["edited_pam_sequence"], "TAG")

    def test_replacement_is_computed_once_from_original_negative_target(self):
        record = _negative_strand_target()
        result = design_hdr_donor(
            record,
            cut_position_0based=86,
            edit_dna="CGAGCC",
            edit_start_0based=80,
            edit_end_0based=86,
            left_arm_length=42,
            right_arm_length=42,
            grna_seq=GUIDE,
            grna_strand=-1,
            donor_type="dsDNA",
        )

        self.assertEqual(result["edit_mode"], "replace")
        self.assertEqual(len(result["edited_target_sequence"]), len(record))
        self.assertEqual(result["total_length"], 90)
        self.assertEqual(result["left_arm_length"], 42)
        self.assertEqual(result["right_arm_length"], 42)
        self.assertEqual(result["guide"]["pam_sequence"], "TGG")
        self.assertEqual(result["guide"]["edited_pam_sequence"], "TCG")
        self.assertTrue(result["pam_silenced_in_donor"])
        self.assertEqual(result["donor_sequence"].count("CGAGCC"), 1)

    def test_wrong_guide_and_cut_are_rejected(self):
        record = _negative_strand_target()
        common = dict(
            target_seq_or_file=record,
            cut_position_0based=86,
            edit_dna="CGAGCC",
            edit_start_0based=80,
            edit_end_0based=86,
            left_arm_length=45,
            right_arm_length=45,
            grna_strand=-1,
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            design_hdr_donor(grna_seq="A" * 20, **common)
        with self.assertRaisesRegex(ValueError, "no SpCas9 cut"):
            design_hdr_donor(grna_seq=GUIDE, cut_position_0based=85, **{k: v for k, v in common.items() if k != "cut_position_0based"})

    def test_short_dsdna_emits_complete_duplex_and_uses_actual_arms(self):
        record = _negative_strand_target()
        result = recipe_crispr_hdr_donor(
            record,
            cut_position_0based=86,
            edit_dna="CGAGCC",
            edit_start_0based=80,
            edit_end_0based=86,
            donor_type="dsDNA",
            custom_arm_length=42,
            grna_seq=GUIDE,
            grna_strand=-1,
        )

        self.assertEqual(result["donor_type"], "dsDNA")
        self.assertEqual(len(result["top_oligo"]), 90)
        self.assertEqual(result["bottom_oligo"], str(Seq(result["top_oligo"]).reverse_complement()))
        self.assertEqual(result["left_arm_length"], 42)
        self.assertEqual(result["right_arm_length"], 42)
        self.assertEqual(result["protocol_mode"], "short_dsDNA_annealed")
        self.assertNotIn("ssODN", " ".join(step["action"] for step in result["protocol_steps"]))
        self.assertTrue(result["quality_checks"]["standard_arm_length_conforming"])

    def test_insertion_api_remains_single_payload(self):
        target = "A" * 50 + "C" * 40
        result = design_hdr_donor(
            target,
            cut_position_0based=50,
            edit_dna="ATG",
            left_arm_length=10,
            right_arm_length=10,
        )
        self.assertEqual(result["edit_mode"], "insert")
        self.assertEqual(result["donor_sequence"], "A" * 10 + "ATG" + "C" * 10)
        self.assertEqual(result["donor_sequence"].count("ATG"), 1)


if __name__ == "__main__":
    unittest.main()
