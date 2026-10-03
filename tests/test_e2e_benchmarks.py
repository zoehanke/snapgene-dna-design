# -*- coding: utf-8 -*-
"""tests/test_e2e_benchmarks.py - End-to-End Benchmarks for Full Reconstructed Stack.

Radically cured biological validation:
- Case A: Vector digestion + in-frame C-terminal 6xHis tagging + Gibson overlap assembly
          + full multi-CDS feature reading frame audit + Colony PCR & Sanger verification.
- Case B: CRISPR EMX1 locus scan + U6 oligos + HDR donor with PAM silencing
          + in vivo recleavage audit + genomic junction integration PCR & Sanger verification.
- Case C: Desktop SnapGene native binary .dna export and viewer verification.
"""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import os
import pathlib
import shutil
import tempfile
import unittest
import itertools
from unittest.mock import Mock, patch

from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.guardrails import quick_biological_sanity_check, scan_crispr_recleavage_risk
from core.recipes.crispr_hdr import recipe_crispr_hdr_donor
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
from core.tools.snapgene_io import export_snapgene, open_in_snapgene
from core.io.input_resolution import resolve_sequence_record
from core.tools.amplification import design_overhang_primers


class TestE2EBenchmarks(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = pathlib.Path(tempfile.mkdtemp(prefix="snapgene_e2e_"))

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_synthetic_repeated_flanks_cannot_fake_valid_cloning_primers(self):
        """Keep the original synthetic inputs; distinguish tag preparation from an invalid cloning-primer route."""
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

        # 3. Real source template: untagged GFP CDS (the tag is introduced by
        # the cloning PCR below, never treated as an inventory template).
        sense_codons = [
            "".join(codon)
            for codon in itertools.product("ACGT", repeat=3)
            if "".join(codon) not in {"TAA", "TAG", "TGA"}
        ]
        state = 17
        body = []
        for _ in range(147):
            state = (1103515245 * state + 12345) & 0x7FFFFFFF
            body.append(sense_codons[state % len(sense_codons)])
        gfp_cds = "ATG" + "".join(body) + "TAA"
        gfp_template = SeqRecord(
            Seq(gfp_cds), id="gfp_source",
            annotations={"molecule_type": "DNA", "topology": "linear"},
        )

        # 4. Protein tagging supplies target design only.  The actual linker,
        # tag, and stop enter the product through a reverse-primer 5' tail.
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
        insert_end = len(gfp_cds) - 3
        self.assertTrue(tagged_insert_seq.startswith(gfp_cds[:insert_end]))
        tag_cassette = tagged_insert_seq[insert_end:]

        # Tag introduction itself is a real, feasible two-PCR preparation.
        # The old test then attached both vector homologies and called an
        # unexamined 66 C full-primer hairpin a successful cloning design.
        from core.tools.amplification import prepare_pcr_fragment
        tagged = prepare_pcr_fragment(gfp_template, 0, insert_end, "",
                                      str(Seq(tag_cassette).reverse_complement()))
        self.assertEqual(tagged["pcr"]["amplicon"], tagged_insert_seq)
        self.assertGreater(len(tagged["preparation"]),1)
        fwd_tail = vector_backbone_seq[-22:]
        reverse_tail = str(Seq(tag_cassette+vector_backbone_seq[:22]).reverse_complement())
        with self.assertRaisesRegex(ValueError, "NO_VALID_PRIMER_PAIR"):
            prepare_pcr_fragment(gfp_template, 0, insert_end, fwd_tail, reverse_tail)

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
        # The short HA insert cannot supply a 60 C internal primer. Both
        # actual cores must fit the existing 52-72 C range and share a usable
        # annealing temperature, without moving the reverse primer outside HA.
        self.assertTrue(52 <= junction_primers["forward_tm"] <= 72)
        self.assertTrue(52 <= junction_primers["reverse_tm"] <= 72)
        self.assertLessEqual(abs(junction_primers["forward_tm"]-junction_primers["reverse_tm"]),3)
        r_start, r_end = junction_primers["reverse_interval_0based"]
        self.assertTrue(cut_pos <= r_start < r_end <= cut_pos+len(ha_payload))
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

        # 3. Verify launcher wiring without starting the desktop GUI.  Official
        # SnapGene conversion is covered by a separate integration sample.
        fake_exe = self.tmp_dir / "SnapGene.exe"
        fake_exe.write_text("test launcher seam", encoding="utf-8")
        with patch("core.tools.snapgene_io.find_snapgene_executable", return_value=fake_exe), \
                patch("core.tools.snapgene_io.subprocess.Popen", return_value=Mock(pid=12345)) as popen:
            launch_res = open_in_snapgene(dna_file)
        self.assertTrue(launch_res["success"])
        popen.assert_called_once_with([str(fake_exe), str(pathlib.Path(dna_file).resolve())])


if __name__ == "__main__":
    unittest.main()
