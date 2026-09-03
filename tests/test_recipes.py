# -*- coding: utf-8 -*-
"""tests/test_recipes.py - Rigorous unit tests for Tier 2 Standard Laboratory SOP Recipes."""
import unittest

from core.recipes import (
    GET_RECIPE_DEFINITIONS,
    get_recipe_sources,
    recipe_cloning_verification,
    recipe_crispr_hdr_donor,
    recipe_gibson_assembly,
    recipe_golden_gate,
    recipe_protein_tagging,
    recipe_restriction_cloning,
    recipe_site_directed_mutagenesis,
)


class TestStandardRecipes(unittest.TestCase):

    def test_recipe_crispr_hdr_donor(self):
        # Target with SpCas9 cut site at bp 60 (PAM is at 63-66)
        target = "A" * 60 + "TTT" + "AGG" + "C" * 50
        res = recipe_crispr_hdr_donor(
            target_seq_or_file=target,
            cut_position_0based=60,
            edit_dna="GAATTC",
            donor_type="ssODN",
            grna_seq="A" * 20,
            grna_strand=1,
        )
        self.assertEqual(res["donor_type"], "ssODN")
        self.assertEqual(res["left_arm_length"], 50)  # Standard 40-60 nt window
        self.assertEqual(res["right_arm_length"], 50)
        self.assertTrue(res["pam_silenced"])
        self.assertIn("Ran et al. (2013)", res["authoritative_sources"][0]["citation"])
        self.assertIn("Paquet et al. (2016)", res["authoritative_sources"][1]["citation"])
        self.assertTrue(res["quality_checks"]["standard_arm_length_conforming"])
        self.assertTrue(res["quality_checks"]["pam_recleavage_prevented"])

    def test_recipe_gibson_assembly(self):
        # Vector 100 bp, insert template 100 bp
        vector = "ACGT" * 25
        insert_template = "T" * 20 + "GCAT" * 20 + "A" * 20
        res = recipe_gibson_assembly(
            vector_linear_seq=vector,
            insert_template_seq=insert_template,
            insert_start=20,
            insert_end=60,
            overlap_length=22,  # Standard 20-25 bp
        )
        self.assertEqual(res["quality_checks"]["standard_overlap_length_bp"], 22)
        self.assertTrue(res["quality_checks"]["assembled_successfully"])
        self.assertIn("Gibson et al. (2009)", res["authoritative_sources"][0]["citation"])
        self.assertIn("NEBuilder", res["authoritative_sources"][1]["citation"])
        self.assertLessEqual(res["quality_checks"]["binding_core_delta_tm"], 3.0)

    def test_recipe_golden_gate(self):
        f1 = "GGTCTC" + "A" + "TGCA" + "A" * 8 + "ATGA" + "A" + "GAGACC"
        f2 = "GGTCTC" + "A" + "ATGA" + "C" * 8 + "TGCA" + "A" + "GAGACC"
        res = recipe_golden_gate(fragments=[f1, f2], enzyme="BsaI", circular=True)
        self.assertEqual(res["product_topology"], "circular")
        self.assertTrue(res["quality_checks"]["all_junctions_compatible"])
        self.assertTrue(res["quality_checks"]["recognition_sites_cleaved_from_product"])
        self.assertNotIn("GGTCTC", res["product_sequence"])
        self.assertIn("Engler et al. (2008)", res["authoritative_sources"][0]["citation"])
        self.assertIn("Potapov et al. (2018)", res["authoritative_sources"][1]["citation"])

    def test_recipe_restriction_cloning(self):
        # Mock vector with EcoRI (GAATTC) and BamHI (GGATCC)
        vector = "A" * 30 + "GAATTC" + "C" * 40 + "GGATCC" + "A" * 30
        insert_tpl = "G" * 30 + "ATGCATGCATGCATGCATGC" + "C" * 30
        res = recipe_restriction_cloning(
            vector_source=vector,
            insert_template=insert_tpl,
            insert_start=30,
            insert_end=50,
            enzyme5="EcoRI",
            enzyme3="BamHI",
        )
        self.assertTrue(res["quality_checks"]["assembled_successfully"])
        self.assertEqual(res["quality_checks"]["protective_bases_added"]["5prime"], "CGC")
        self.assertIn("Green, M.R. and Sambrook, J. (2012)", res["authoritative_sources"][0]["citation"])
        self.assertIn("Cleavage Close to the End", res["authoritative_sources"][1]["citation"])
        self.assertTrue(any("DPNI_DIGESTION" in r for r in res["sop_reminders"]))

    def test_recipe_site_directed_mutagenesis(self):
        # Template plasmid with single point mutation target at bp 40
        tpl = "G" * 20 + "ACGTACGTACGTACGTACGT" + "GATC" + "C" * 20
        res = recipe_site_directed_mutagenesis(
            template_seq_or_file=tpl,
            start_0based=30,
            end_0based=31,
            alt_seq="A",
            target_flank_bp=15,
        )
        self.assertEqual(res["mutation_type"], "substitution")
        self.assertEqual(len(res["mutated_sequence"]), len(tpl))
        self.assertEqual(res["mutated_sequence"][30], "A")
        self.assertIn("Zheng et al. (2004)", res["authoritative_sources"][0]["citation"])
        self.assertTrue(any("DPNI_DIGESTION" in r for r in res["sop_reminders"]))
        self.assertGreaterEqual(res["quality_checks"]["primer_length_nt"], 25)

    def test_recipe_protein_tagging(self):
        # Target CDS: ATG GCT AGC GGC GGT TAA (with stop codon TAA)
        target_cds = "ATGGCTAGCGGCGGGTAA"
        # C-terminal 6xHis tag with TEV cleavage site and Kozak
        res = recipe_protein_tagging(
            target_cds_seq_or_file=target_cds,
            tag_name_or_seq="6xHis",
            tag_position="C-terminal",
            linker_type="flexible_G4S_x1",
            protease_cleavage="TEV",
            include_kozak=True,
        )
        self.assertTrue(res["quality_checks"]["in_frame_fusion"])
        self.assertTrue(res["quality_checks"]["zero_internal_stop_codons"])
        self.assertTrue(res["quality_checks"]["terminal_stop_codon_present"])
        self.assertTrue(res["quality_checks"]["kozak_motif_included"])
        self.assertTrue(res["product_dna_sequence"].startswith("GCCACC"))
        self.assertIn("Terpe, K. (2003)", res["authoritative_sources"][0]["citation"])
        self.assertIn("Kozak, M. (1986)", res["authoritative_sources"][1]["citation"])

    def test_recipe_cloning_verification(self):
        # Recombinant plasmid of length 2000 bp, insert cloned at 500..1200
        plasmid = ("A" * 500) + ("C" * 700) + ("G" * 800)
        res = recipe_cloning_verification(
            recombinant_plasmid_seq_or_file=plasmid,
            insert_start_0based=500,
            insert_end_0based=1200,
        )
        self.assertEqual(res["quality_checks"]["sanger_distance_from_junction_bp"], 70)
        self.assertTrue(res["quality_checks"]["sanger_primer_avoids_dye_blob_zone"])
        self.assertTrue(res["quality_checks"]["colony_pcr_crosses_junction"])
        self.assertTrue(res["quality_checks"]["colony_pcr_amplicon_length_conforming"])
        self.assertIn("Green, M.R. and Sambrook, J. (2012)", res["authoritative_sources"][0]["citation"])
        self.assertIn("Sanger, F.", res["authoritative_sources"][1]["citation"])

    def test_get_recipe_sources_and_definitions(self):
        sources = get_recipe_sources("recipe_crispr_hdr_donor")
        self.assertGreater(len(sources), 0)
        self.assertEqual(sources[0]["doi"], "10.1038/nprot.2013.143")

        sources_sdm = get_recipe_sources("recipe_site_directed_mutagenesis")
        self.assertGreater(len(sources_sdm), 0)
        self.assertEqual(sources_sdm[0]["doi"], "10.1093/nar/gnh110")

        defs = GET_RECIPE_DEFINITIONS()
        self.assertEqual(len(defs), 7)
        names = [d["name"] for d in defs]
        self.assertIn("recipe_crispr_hdr_donor", names)
        self.assertIn("recipe_gibson_assembly", names)
        self.assertIn("recipe_golden_gate", names)
        self.assertIn("recipe_restriction_cloning", names)
        self.assertIn("recipe_site_directed_mutagenesis", names)
        self.assertIn("recipe_protein_tagging", names)
        self.assertIn("recipe_cloning_verification", names)


if __name__ == "__main__":
    unittest.main()
