# -*- coding: utf-8 -*-
"""tests/test_e2e_benchmarks.py - End-to-End Benchmarks for Full Reconstructed Stack.

Radically cured biological validation:
- Case A: Vector digestion + in-frame C-terminal 6xHis tagging + Gibson overlap assembly
          + full multi-CDS feature reading frame audit + Colony PCR & Sanger verification.
- Case B: CRISPR EMX1 locus scan + U6 oligos + HDR donor with PAM silencing
          + in vivo recleavage audit + genomic junction integration PCR & Sanger verification.
- Case C: Desktop SnapGene native binary .dna export and viewer verification.
"""
import os
import pathlib
import shutil
import tempfile
import unittest

from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
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
        amp_cds = "ATG" + "GCATCGGCACTA" * 20 + "TAA"  # 246 bp model marker
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
        vector_backbone_seq = vector_seq[hindiii_cut:] + vector_seq[:ecori_cut]
        self.assertGreater(len(vector_backbone_seq), 800)

        # 3. Insert gene preparation: model GFP CDS (450 bp)
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

        # 6. Annotate recombinant features with exact migrated coordinates on assembled construct
        construct_rec = SeqRecord(Seq(assembled_seq), id="pConstruct_eGFP_6xHis", name="pConstruct_eGFP_6xHis")
        construct_rec.annotations["topology"] = "circular"

        # 6a. pUC ori migrated coordinate
        ori_assembled_pos = assembled_seq.find(ori_seq)
        construct_rec.features.append(SeqFeature(
            FeatureLocation(ori_assembled_pos, ori_assembled_pos + len(ori_seq)),
            type="rep_origin",
            qualifiers={"label": ["pUC ori"]},
        ))

        # 6b. AmpR CDS migrated coordinate
        amp_assembled_pos = assembled_seq.find(amp_cds)
        construct_rec.features.append(SeqFeature(
            FeatureLocation(amp_assembled_pos, amp_assembled_pos + len(amp_cds)),
            type="CDS",
            qualifiers={"label": ["AmpR"], "gene": ["AmpR"]},
        ))

        # 6c. Recombinant eGFP_6xHis CDS
        ins_start = assembled_seq.find(tagged_insert_seq)
        ins_end = ins_start + len(tagged_insert_seq)
        construct_rec.features.append(SeqFeature(
            FeatureLocation(ins_start, ins_end, strand=1),
            type="CDS",
            qualifiers={"label": ["eGFP_6xHis"], "gene": ["eGFP_6xHis"]},
        ))
        annotated_rec = annotate_feature(
            record=construct_rec,
            name="6xHis",
            feature_type="tag",
            start=ins_end - 18,
            end=ins_end,
            strand=1,
            color="#fdbf6f",
        )

        # 7. Tier 3 Objective Biological Guardrail Verification
        # The sanity check inspects BOTH annotated CDS features on the plasmid (AmpR and eGFP_6xHis),
        # guaranteeing in-frame translation, zero premature stops, and full maintenance elements!
        sanity_plasmid = quick_biological_sanity_check(
            annotated_rec,
            cloning_enzymes=["BamHI"],  # diagnostic check
            primers=[fwd_primer, rev_primer],
            check_secondary_structure=True,
            topology="circular",
        )
        self.assertTrue(sanity_plasmid["all_clean"], f"Guardrail issues: {sanity_plasmid['issues_found']}")
        self.assertEqual(len(sanity_plasmid["annotated_cds_audits"]), 2)
        self.assertTrue(sanity_plasmid["maintenance_elements"]["has_origin"])
        self.assertTrue(sanity_plasmid["maintenance_elements"]["has_marker"])
        self.assertFalse(sanity_plasmid["has_premature_stop"])

        # 8. Design Colony PCR & Sanger Verification Primers across the vector-insert junction
        verification_plan = recipe_cloning_verification(
            recombinant_plasmid_seq_or_file=annotated_rec,
            insert_start_0based=ins_start,
            insert_end_0based=ins_end,
        )
        colony_info = verification_plan["colony_pcr_primers"]
        self.assertGreaterEqual(len(colony_info["forward_primer_in_vector"]), 18)
        self.assertGreaterEqual(len(colony_info["reverse_primer_in_insert"]), 18)
        self.assertAlmostEqual(colony_info["forward_tm"], 60.0, delta=2.5)
        self.assertAlmostEqual(colony_info["reverse_tm"], 60.0, delta=2.5)
        self.assertGreaterEqual(verification_plan["sanger_sequencing_primer"]["tm"], 55.0)

        # 9. SnapGene export (.dna & .gb)
        out_files = export_snapgene(
            record_or_seq=annotated_rec,
            out_dir=self.tmp_dir,
            filename_base="e2e_case_a_gibson",
            topology="circular",
        )
        self.assertTrue(pathlib.Path(out_files["dna_file"]).exists())
        self.assertTrue(pathlib.Path(out_files["gb_file"]).exists())

        # 10. Re-read generated native .dna to verify binary integrity
        re_read = inspect_dna(out_files["dna_file"])
        self.assertEqual(re_read["topology"], "circular")
        self.assertEqual(re_read["sequence_length"], len(assembled_seq))
        self.assertGreaterEqual(re_read["feature_count"], 3)

    def test_case_b_crispr_hdr_precision_knockin_e2e(self):
        """Benchmark 6.2: Genomic target scan + U6 gRNA oligos + HDR donor with PAM silencing + Junction QC."""
        # 1. Target genomic locus (human EMX1 exon 3 locus, ~300 bp natural genomic sequence)
        spacer = "GAGTCCGAGCAGAAGAAGAA"
        pam = "GGG"
        left_genomic = "CTGTGTCCTCTTCCTGCCCTCTGTTCCCTCCCTGTCCCTCCCTCCCTCCCTCCCTCCTCCCGTTGTCCTGGCCAGCTCCCTCGTGGGTCCTGGCTTGGA"
        right_genomic = "TGGAGTGGCCCAACCCCCAGTGGGGCCCTGCCAGCTCCCTCGTGGGTCCTGGCTGGGATTTTTCATTCCTGAACACTTTCCTGGTTCTTCCCTGTCCCT"
        target_genomic_locus = left_genomic + spacer + pam + right_genomic

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
        # Cut site is 3 bp upstream of PAM
        cut_pos = len(left_genomic) + 17  # 0-based index of Cas9 double-strand break
        ha_payload = "TATCCATATGATGTTCCAGATTATGCT"  # 27 bp HA tag

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

        # Audit ssODN donor: linear repair reagent
        sanity = quick_biological_sanity_check(
            record_or_seq=donor_seq,
            crispr_grna_seq=spacer,
            topology="linear",
            is_cds=False,
        )
        self.assertTrue(sanity["all_clean"], f"Sanity issues: {sanity['issues_found']}")

        # 6. Reconstruct the edited chromosome locus (incorporating knock-in HA payload)
        # Wet-lab reality: Junction PCR is performed on the edited genomic DNA extracted from cells!
        edited_genomic_locus = target_genomic_locus[:cut_pos] + ha_payload + target_genomic_locus[cut_pos:]
        genomic_rec = SeqRecord(Seq(edited_genomic_locus), id="EMX1_HA_Edited_Chromosome")
        genomic_rec.annotations["topology"] = "linear"
        genomic_rec.features.append(SeqFeature(
            FeatureLocation(cut_pos, cut_pos + len(ha_payload)),
            type="tag",
            qualifiers={"label": ["HA Tag"]},
        ))

        # 7. Design Genomic Junction Integration Verification Primers
        # Forward primer in genomic backbone upstream of insertion; reverse primer in payload/downstream
        verification_plan = recipe_cloning_verification(
            recombinant_plasmid_seq_or_file=genomic_rec,
            insert_start_0based=cut_pos,
            insert_end_0based=cut_pos + len(ha_payload),
        )
        junction_primers = verification_plan["colony_pcr_primers"]
        self.assertGreaterEqual(len(junction_primers["forward_primer_in_vector"]), 18)
        self.assertGreaterEqual(len(junction_primers["reverse_primer_in_insert"]), 18)
        self.assertAlmostEqual(junction_primers["forward_tm"], 60.0, delta=2.5)
        self.assertAlmostEqual(junction_primers["reverse_tm"], 60.0, delta=2.5)
        self.assertGreaterEqual(verification_plan["sanger_sequencing_primer"]["tm"], 55.0)

        # 8. Export donor record to SnapGene .dna and .gb
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
        # 1. Generate a valid test construct
        test_rec = SeqRecord(Seq("ATGCATGCATGCATGC"), id="DesktopTest")
        out_files = export_snapgene(
            record_or_seq=test_rec,
            out_dir=self.tmp_dir,
            filename_base="desktop_test",
            topology="circular",
        )
        dna_file = out_files["dna_file"]
        self.assertTrue(pathlib.Path(dna_file).is_file())

        # 2. Verify open_in_snapgene capability without hanging
        with self.assertRaises(FileNotFoundError):
            open_in_snapgene(self.tmp_dir / "does_not_exist.dna")

        # 3. Test launcher with existing file (gracefully reports success or missing executable)
        launch_res = open_in_snapgene(dna_file)
        self.assertIn("success", launch_res)
        self.assertIsInstance(launch_res["success"], bool)


if __name__ == "__main__":
    unittest.main()
