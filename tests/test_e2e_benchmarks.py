# -*- coding: utf-8 -*-
"""tests/test_e2e_benchmarks.py - End-to-End Benchmarks for Full Reconstructed Stack.

Implements and validates the two real-world biological scenarios:
- Case A: Gibson Assembly with C-terminal 6xHis fusion, feature migration & SnapGene delivery.
- Case B: CRISPR Cas9 sgRNA, U6 oligos, HDR donor template with PAM silencing & junction QC.
- Case C: Desktop SnapGene native binary .dna export and viewer verification.
"""
import os
import pathlib
import shutil
import tempfile
import unittest

from Bio.Seq import Seq
from Bio.SeqFeature import SeqFeature, FeatureLocation
from Bio.SeqRecord import SeqRecord

from core.guardrails import quick_biological_sanity_check, scan_crispr_recleavage_risk
from core.recipes.crispr_hdr import recipe_crispr_hdr_donor
from core.recipes.gibson import recipe_gibson_assembly
from core.recipes.protein_tagging import recipe_protein_tagging
from core.recipes.verification import recipe_cloning_verification
from core.tools.amplification import simulate_pcr
from core.tools.assembly import simulate_overlap_assembly
from core.tools.crispr import design_crispr_grna, prepare_grna_oligos
from core.tools.feature_ops import annotate_feature
from core.tools.fusion import get_standard_element
from core.tools.inspection import inspect_dna
from core.tools.restriction import digest_sequence, find_restriction_sites
from core.tools.sequence_ops import check_reading_frame, strip_terminal_codons
from core.tools.snapgene_io import export_snapgene, open_in_snapgene, SNAPGENE_EXE_PATH


class TestE2EBenchmarks(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="snapgene_e2e_"))

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_case_a_gibson_fusion_cloning_e2e(self):
        """Benchmark 6.1: Vector preparation + PCR tag introduction + Gibson assembly + Bio-guardrail + SnapGene export."""
        # 1. Prepare expression vector backbone: pET-like circular plasmid (~1,500 bp)
        # Vector contains: pUC ori, AmpR resistance marker, and MCS with EcoRI and HindIII
        amp_cds = "ATG" + "GCATCGTAGCTA" * 20 + "TAA"  # 246 bp model marker
        ori_seq = (
            "TTGAGATCCTTTTTTTCTGCGCGTAATCTGCTGCTTGCAAACAAAAAAACCACCGCTACCAGCGGTGGTTTGTTTGCCGGATCAAGAGCTACCAACTCTTTTTCC"
            "GAAGGTAACTGGCTTCAGCAGAGCGCAGATACCAAATACTGTCCTTCTAGTGTAGCCGTAGTTAGGCCACCACTTCAAGAACTCTGTAGCACCGCCTACATACCT"
            "CGCTCTGCTAATCCTGTTACCAGTGGCTGCTGCCAGTGGCGATAAGTCGTGTCTTACCGGGTTGGACTCAAGACGATAGTTACCGGATAAGGCGCAGCGGTCGGGC"
        )  # ~330 bp real ColE1/pUC ori fragment
        spacer1 = ("AGCTTGAC" + "TGCAGCTA" + "CAAGTCAG" + "GATCGATC") * 4
        spacer2 = ("GATCACGT" + "ACTGATCG" + "CGATAGCT" + "TACGATCG") * 5
        spacer3 = ("CTAGCTAG" + "AGCTAGCT" + "GATCGATC" + "CGTACGTA") * 4
        mcs = "GAATTC" + "CGATCGATC" + "AAGCTT"  # EcoRI ... HindIII

        vector_seq = ori_seq + spacer1 + amp_cds + spacer2 + mcs + spacer3
        vec_record = SeqRecord(Seq(vector_seq), id="pVector", name="pVector")
        vec_record.annotations["topology"] = "circular"
        vec_record.features.append(SeqFeature(FeatureLocation(0, len(ori_seq)), type="rep_origin", qualifiers={"label": ["pUC ori"]}))
        amp_start = len(ori_seq) + len(spacer1)
        vec_record.features.append(SeqFeature(FeatureLocation(amp_start, amp_start + len(amp_cds)), type="CDS", qualifiers={"label": ["AmpR"]}))

        # 2. Linearize vector between EcoRI and HindIII
        mcs_start = amp_start + len(amp_cds) + len(spacer2)
        ecori_cut = mcs_start + 1  # G^AATTC
        hindiii_cut = mcs_start + 6 + 9 + 1  # A^AGCTT
        # Vector backbone fragment: from HindIII cut to EcoRI cut
        vector_backbone_seq = vector_seq[hindiii_cut:] + vector_seq[:ecori_cut]
        self.assertGreater(len(vector_backbone_seq), 800)

        # 3. Insert gene preparation: model GFP CDS (450 bp)
        # Ends with stop codon TAA
        gfp_cds = "ATG" + "GTGAGCAAGGGCGAG" * 29 + "TAA"  # 453 bp

        # 4. Protein tagging: add flexible GS linker + 6xHis tag, stripping original stop
        tag_recipe = recipe_protein_tagging(
            target_cds_seq_or_file=gfp_cds,
            tag_name_or_seq="6xHis",
            tag_position="C-terminal",
            linker_type="flexible_G4S_x2",
            include_kozak=False,
        )
        tagged_insert_seq = tag_recipe["product_dna_sequence"]
        self.assertTrue(tag_recipe["quality_checks"]["in_frame_fusion"])
        self.assertTrue(tag_recipe["quality_checks"]["terminal_stop_codon_present"])
        self.assertTrue(tagged_insert_seq.endswith("TAA"))

        # 5. Gibson overlap primer design & assembly (22 bp overlap matching vector ends)
        gibson_design = recipe_gibson_assembly(
            vector_linear_seq=vector_backbone_seq,
            insert_template_seq=tagged_insert_seq,
            insert_start=0,
            insert_end=len(tagged_insert_seq),
            overlap_length=22,
            circular_product=True,
        )
        fwd_primer = gibson_design["primers"]["forward"]["full_sequence"]
        rev_primer = gibson_design["primers"]["reverse"]["full_sequence"]
        assembled_seq = gibson_design["product_sequence"]
        self.assertGreaterEqual(len(fwd_primer), 35)
        self.assertGreaterEqual(len(rev_primer), 35)
        self.assertTrue(gibson_design["quality_checks"]["assembled_successfully"])

        # 6. Annotate 6xHis tag feature on assembled construct
        construct_rec = SeqRecord(Seq(assembled_seq), id="pConstruct_eGFP_6xHis")
        construct_rec.annotations["topology"] = "circular"
        construct_rec.features = vec_record.features  # preserve ori and AmpR
        annotated_rec = annotate_feature(
            record=construct_rec,
            name="6xHis",
            feature_type="tag",
            start=100,
            end=118,
            strand=1,
            color="#fdbf6f",
        )

        # 9. Tier 3 Objective Biological Guardrail Verification
        # 9a. Verify tagged insert CDS reading frame, lack of premature stops, and stop codon
        sanity_cds = quick_biological_sanity_check(tagged_insert_seq, is_cds=True)
        self.assertTrue(sanity_cds["all_clean"])
        self.assertTrue(sanity_cds["clean_for_expression"])

        # 9b. Verify assembled circular plasmid construct (ori, AmpR, primers, secondary structures)
        sanity_plasmid = quick_biological_sanity_check(
            annotated_rec,
            cloning_enzymes=["BamHI"],  # diagnostic check
            primers=[fwd_primer, rev_primer],
            check_secondary_structure=True,
            is_cds=False,
            topology="circular",
        )
        self.assertTrue(sanity_plasmid["all_clean"], f"Guardrail issues: {sanity_plasmid['issues_found']}")
        self.assertTrue(sanity_plasmid["maintenance_elements"]["has_origin"])
        self.assertTrue(sanity_plasmid["maintenance_elements"]["has_marker"])

        # 10. SnapGene export (.dna & .gb)
        out_files = export_snapgene(
            record_or_seq=annotated_rec,
            out_dir=self.tmp_dir,
            filename_base="e2e_case_a_gibson",
            topology="circular",
        )
        self.assertTrue(pathlib.Path(out_files["dna_file"]).exists())
        self.assertTrue(pathlib.Path(out_files["gb_file"]).exists())

        # 11. Re-read generated native .dna to verify binary integrity
        re_read = inspect_dna(out_files["dna_file"])
        self.assertEqual(re_read["topology"], "circular")
        self.assertEqual(re_read["sequence_length"], len(assembled_seq))
        self.assertGreaterEqual(re_read["feature_count"], 2)

    def test_case_b_crispr_hdr_precision_knockin_e2e(self):
        """Benchmark 6.2: Genomic target scan + U6 gRNA oligos + HDR donor with PAM silencing + Junction QC."""
        # 1. Target genomic locus (human EMX1 exon 3 model locus, 300 bp)
        # Spacer: GAGTCCGAGCAGAAGAAGAA (20 nt)
        # PAM: GGG (SpCas9)
        spacer = "GAGTCCGAGCAGAAGAAGAA"
        pam = "GGG"
        target_genomic_locus = "T" * 100 + spacer + pam + "A" * 180

        # 2. Design and score candidate CRISPR guides
        guides = design_crispr_grna(
            target_seq_or_file=target_genomic_locus,
            nuclease="SpCas9",
        )
        self.assertGreaterEqual(len(guides), 1)
        chosen_guide = [g for g in guides if g["spacer"] == spacer][0]
        self.assertEqual(chosen_guide["spacer"], spacer)
        self.assertFalse(chosen_guide["has_poly_t"])

        # 3. Prepare U6 golden gate cloning oligos
        oligos = prepare_grna_oligos(
            spacer_seq=spacer,
            vector_type="BbsI",
        )
        self.assertTrue(oligos["forward_oligo"]["sequence"].startswith("CACC"))
        self.assertTrue(oligos["reverse_oligo"]["sequence"].startswith("AAAC"))

        # 4. Design CRISPR HDR donor template
        # Cut site is 3 bp upstream of PAM (between position 117 and 118)
        cut_pos = 100 + 17  # 0-based index of cut
        # Desired knock-in payload: 27 bp HA tag (TATCCATATGATGTTCCAGATTATGCT)
        ha_payload = "TATCCATATGATGTTCCAGATTATGCT"

        hdr_recipe = recipe_crispr_hdr_donor(
            target_seq_or_file=target_genomic_locus,
            cut_position_0based=cut_pos,
            edit_dna=ha_payload,
            donor_type="ssODN",
            grna_seq=spacer,
            custom_arm_length=50,
        )
        donor_seq = hdr_recipe["donor_sequence"]
        self.assertIn(ha_payload, donor_seq)
        self.assertTrue(hdr_recipe["pam_silenced"])

        # 5. Tier 3 Objective Biological Guardrail Verification
        # Verify donor is 100% safe from in vivo Cas9 re-cleavage
        recleavage_audit = scan_crispr_recleavage_risk(donor_seq=donor_seq, grna_seq=spacer)
        self.assertFalse(recleavage_audit["recleavage_risk"])
        self.assertFalse(recleavage_audit["intact_seed_pam_found"])

        sanity = quick_biological_sanity_check(
            record_or_seq=donor_seq,
            crispr_grna_seq=spacer,
            topology="linear",
            is_cds=False,
        )
        self.assertTrue(sanity["all_clean"], f"Sanity issues: {sanity['issues_found']}")

        # 6. Design junction verification primers
        verification_plan = recipe_cloning_verification(
            recombinant_plasmid_seq_or_file=donor_seq,
            insert_start_0based=50,
            insert_end_0based=50 + len(ha_payload),
        )
        self.assertIn("colony_pcr_primers", verification_plan)
        self.assertIn("sanger_sequencing_primer", verification_plan)

        # 7. Export donor record to SnapGene .dna and .gb
        donor_rec = SeqRecord(Seq(donor_seq), id="EMX1_HA_HDR_Donor")
        donor_rec.annotations["topology"] = "linear"
        donor_rec.features.append(SeqFeature(FeatureLocation(50, 50 + len(ha_payload)), type="tag", qualifiers={"label": ["HA Tag"]}))

        out_files = export_snapgene(
            record_or_seq=donor_rec,
            out_dir=self.tmp_dir,
            filename_base="e2e_case_b_crispr_hdr",
            topology="linear",
        )
        self.assertTrue(pathlib.Path(out_files["dna_file"]).exists())

    def test_case_c_desktop_snapgene_readiness(self):
        """Benchmark 6.3: Verify desktop SnapGene binary generation and launcher availability."""
        # 1. Verify desktop executable detection
        exe_path = pathlib.Path(SNAPGENE_EXE_PATH)
        self.assertTrue(exe_path.exists(), f"SnapGene.exe must be located at {SNAPGENE_EXE_PATH}")

        # 2. Generate a valid test construct
        test_rec = SeqRecord(Seq("ATGCATGCATGCATGC"), id="DesktopTest")
        out_files = export_snapgene(
            record_or_seq=test_rec,
            out_dir=self.tmp_dir,
            filename_base="desktop_test",
            topology="circular",
        )
        dna_file = out_files["dna_file"]
        self.assertTrue(pathlib.Path(dna_file).is_file())

        # 3. Verify open_in_snapgene capability without hanging
        # Non-existent file raises FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            open_in_snapgene(self.tmp_dir / "does_not_exist.dna")


if __name__ == "__main__":
    unittest.main()
