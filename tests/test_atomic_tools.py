# -*- coding: utf-8 -*-
"""Unit tests for atomic biological tools (core/tools/)."""
from __future__ import annotations

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS

import pathlib
import random
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.tools import (
    GET_TOOL_DEFINITIONS,
    annotate_feature,
    check_reading_frame,
    export_snapgene,
    extract_subsequence,
    find_open_reading_frames,
    find_restriction_sites,
    fuse_in_frame,
    get_feature,
    inspect_dna,
    mutate_sequence,
    reverse_complement,
    silent_mutation_remove_site,
    simulate_overlap_assembly,
    simulate_pcr,
    translate_dna,
)


def _make_record(seq: str, name: str = "rec", topology: str = "circular", features: tuple = ()) -> SeqRecord:
    rec = SeqRecord(Seq(seq), id=name, name=name)
    rec.annotations["molecule_type"] = "DNA"
    rec.annotations["topology"] = topology
    for f in features:
        rec.features.append(f)
    return rec


class AtomicToolsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write_gb(self, rec: SeqRecord, filename: str) -> pathlib.Path:
        p = self.tmp / filename
        with open(p, "w", encoding="utf-8") as fh:
            SeqIO.write(rec, fh, "genbank")
        return p

    def test_inspect_dna(self):
        feat = SeqFeature(FeatureLocation(3, 15, strand=1), type="CDS", qualifiers={"gene": ["testGene"], "translation": ["MAAA"]})
        rec = _make_record("ATGATGGCTGCTGCTTAA", "pTest", "circular", features=(feat,))
        path = self._write_gb(rec, "pTest.gb")

        res = inspect_dna(path)
        self.assertEqual(res["sequence_length"], 18)
        self.assertEqual(res["topology"], "circular")
        self.assertEqual(res["feature_count"], 1)
        f0 = res["features"][0]
        self.assertEqual(f0["name"], "testGene")
        self.assertEqual(f0["interval_0based"], [3, 15])
        self.assertEqual(f0["translation"], "MAAA")

    def test_get_and_annotate_feature(self):
        rec = _make_record("ATGCATGCATGC", "rec", "circular")
        annotate_feature(rec, "GFP", "CDS", 0, 6, strand=1)
        path = self._write_gb(rec, "with_feat.gb")

        extracted = get_feature(path, "GFP")
        self.assertIsNotNone(extracted)
        self.assertEqual(extracted["name"], "GFP")
        self.assertEqual(extracted["sequence"], "ATGCAT")

    def test_find_restriction_sites(self):
        seq = "AAAAAGAATTCCCCCGGTCTCAGTGAGACCGGGGG"
        res = find_restriction_sites(seq, enzymes=["EcoRI", "BsaI", "BamHI"])
        self.assertEqual(res["enzymes"]["EcoRI"]["cut_count"], 1)
        self.assertTrue(res["enzymes"]["BsaI"]["is_type_iis"])
        self.assertEqual(res["enzymes"]["BamHI"]["cut_count"], 0)
        self.assertIn("EcoRI", res["unique_cutters"])
        self.assertIn("BamHI", res["non_cutters"])

    def test_extract_subsequence(self):
        rec = _make_record("ATGCATGCATGC", "test", "circular")
        path = self._write_gb(rec, "test.gb")
        fwd = extract_subsequence(path, 0, 4, strand=1)
        self.assertEqual(fwd["sequence"], "ATGC")
        rev = extract_subsequence(path, 0, 4, strand=-1)
        self.assertEqual(rev["sequence"], "GCAT")

    def test_reverse_complement_and_translate(self):
        self.assertEqual(reverse_complement("ATGC"), "GCAT")
        # ATG GCT GCT TAA -> MAA*
        self.assertEqual(translate_dna("ATGGCTGCTTAA", frame=1), "MAA*")
        self.assertEqual(translate_dna("AATGGCTGCTTAA", frame=2), "MAA*")

    def test_silent_mutation_remove_site(self):
        # EcoRI site: GAATTC in frame 0 (GAA TTC -> Glu Phe)
        # We want to mutate it so it's still Glu Phe, but GAATTC is gone!
        # Glu is GAA or GAG. If GAA -> GAG, the sequence becomes GAGTTC (no EcoRI, still Glu-Phe!)
        cds = "ATGGTTGAATTCAAGTAA"
        res = silent_mutation_remove_site(cds, "EcoRI", frame_offset=0)
        self.assertTrue(res["site_removed"])
        self.assertTrue(res["identical_translation"])
        self.assertNotIn("GAATTC", res["mutated_seq"])

    def test_fuse_in_frame(self):
        # Partner5: ATG GCT TAA (strips TAA)
        p5 = "ATGGCTTAA"
        # 6xHis tag: CAT CAT CAT CAT CAT CAT
        his_tag = "CATCATCATCATCATCAT"
        res = fuse_in_frame(p5, his_tag, linker_seq="GGA", add_terminal_stop=True)
        self.assertTrue(res["is_in_frame"])
        self.assertFalse(res["has_premature_stop"])
        self.assertTrue(res["terminal_stop"])
        # Translation should be: M A G H H H H H H *
        self.assertEqual(res["translation"], "MAGHHHHHH*")

    def test_check_reading_frame(self):
        in_frame = check_reading_frame("ATGGCTGCTTAA")
        self.assertTrue(in_frame["is_multiple_of_three"])
        self.assertFalse(in_frame["has_premature_stop"])
        self.assertTrue(in_frame["terminal_stop"])
        self.assertEqual(in_frame["translation"], "MAA*")

        shift = check_reading_frame("ATGGCTGCTTAAG")
        self.assertFalse(shift["is_multiple_of_three"])

        premature = check_reading_frame("ATGTAAGCTTAA")
        self.assertTrue(premature["has_premature_stop"])
        self.assertEqual(premature["premature_stop_positions"], [3])

    def test_simulate_pcr_with_overhangs(self):
        rng = random.Random(20260907)
        template = "".join(rng.choice("ACGT") for _ in range(180))
        f_primer = "GAATTC" + template[:20]
        r_primer = "GCGGCCGC" + str(Seq(template[-20:]).reverse_complement())

        res = simulate_pcr(template, f_primer, r_primer)
        amplicon = res["amplicon"]
        self.assertTrue(amplicon.startswith("GAATTC"))
        self.assertTrue(amplicon.endswith("GCGGCCGC"))
        self.assertIn(template[20:40], amplicon)

    def test_simulate_overlap_assembly(self):
        f1 = "A" * 40 + "TTTTTGGGGGAAAAACCCCC"
        f2 = "TTTTTGGGGGAAAAACCCCC" + "C" * 40 + "GGGGGCCCAAAAATTTTT"
        f3 = "GGGGGCCCAAAAATTTTT" + "G" * 40 + "A" * 20

        res = simulate_overlap_assembly([f1, f2, f3], min_overlap=15, circular=True)
        self.assertEqual(res["fragment_count"], 3)
        self.assertEqual(res["product_topology"], "circular")
        self.assertEqual(len(res["junctions"]), 3)

    def test_export_snapgene(self):
        rec = _make_record("ATGCATGCATGC" * 10, "myConstruct", "circular")
        res = export_snapgene(rec, self.tmp, filename_base="myConstruct")
        self.assertTrue(pathlib.Path(res["gb_file"]).exists())
        self.assertTrue(pathlib.Path(res["dna_file"]).exists())
        self.assertGreater(pathlib.Path(res["dna_file"]).stat().st_size, 0)

    def test_quick_biological_sanity_check(self):
        from core.guardrails import quick_biological_sanity_check
        # Clean CDS: ATG GCT TAA with EcoRI site
        cds = "ATGGCTGAATTCTAA"
        # Sanity check without enzyme conflict
        clean = quick_biological_sanity_check(cds, cloning_enzymes=["BamHI"])
        self.assertTrue(clean["clean_for_expression"])
        self.assertEqual(len(clean["internal_enzyme_conflicts"]), 0)

        # Sanity check with internal EcoRI conflict
        conflict = quick_biological_sanity_check(cds, cloning_enzymes=["EcoRI"])
        self.assertFalse(conflict["clean_for_expression"])
        self.assertEqual(len(conflict["internal_enzyme_conflicts"]), 1)

    def test_tool_definitions_schema(self):
        defs = GET_TOOL_DEFINITIONS()
        self.assertGreaterEqual(len(defs), 15)
        for d in defs:
            self.assertIn("name", d)
            self.assertIn("description", d)
            self.assertIn("parameters", d)

    def test_summarize_backbone(self):
        from core.tools import summarize_backbone
        f_ori = SeqFeature(FeatureLocation(10, 50, strand=1), type="rep_origin", qualifiers={"label": ["pUC_ori"]})
        f_amp = SeqFeature(FeatureLocation(60, 150, strand=1), type="CDS", qualifiers={"label": ["AmpR"]})
        rec = _make_record("A" * 200, "pUC19_mock", "circular", features=(f_ori, f_amp))
        p = self._write_gb(rec, "pUC19_mock.gb")

        summary = summarize_backbone(p)
        self.assertEqual(len(summary["origins_of_replication"]), 1)
        self.assertEqual(summary["origins_of_replication"][0]["name"], "pUC_ori")
        self.assertEqual(len(summary["selection_markers"]), 1)
        self.assertIn("Ampicillin", summary["selection_markers"][0]["marker_type"])

    def test_get_feature_aliases_and_return_all(self):
        f1 = SeqFeature(FeatureLocation(0, 30, strand=1), type="CDS", qualifiers={"gene": ["bla"]})
        f2 = SeqFeature(FeatureLocation(50, 80, strand=1), type="CDS", qualifiers={"gene": ["ampicillin_res"]})
        rec = _make_record("C" * 100, "pAmp", "circular", features=(f1, f2))
        p = self._write_gb(rec, "pAmp.gb")

        # Alias lookup for 'amp' should find 'bla'
        found = get_feature(p, "amp")
        self.assertIsNotNone(found)
        self.assertEqual(found["name"], "bla")

        # return_all=True should return both
        all_found = get_feature(p, "amp", return_all=True)
        self.assertEqual(len(all_found), 2)

    def test_migrate_features_after_assembly(self):
        from core.tools import migrate_features_after_assembly
        frags = [
            {
                "offset_in_product": 0,
                "length": 100,
                "strand": 1,
                "features": [{"name": "promoter", "type": "promoter", "interval_0based": [10, 40], "strand": 1}],
            },
            {
                "offset_in_product": 100,
                "length": 200,
                "strand": 1,
                "features": [{"name": "GFP", "type": "CDS", "interval_0based": [20, 180], "strand": 1}],
            },
        ]
        migrated = migrate_features_after_assembly(frags, total_length=300, circular=True)
        self.assertEqual(len(migrated), 2)
        # promoter stays at [10, 40]
        self.assertEqual(migrated[0]["interval_0based"], [10, 40])
        # GFP shifted by 100 -> [120, 280]
        self.assertEqual(migrated[1]["interval_0based"], [120, 280])

    def test_find_restriction_sites_methylation(self):
        # Sequence containing XbaI (TCTAGA) followed by TC to form Dam methylation motif GATC:
        # TCTAGATC: XbaI site overlapping Dam GATC!
        seq = "AAAAAAAAAATCTAGATCAAAAAAAAAA"
        res = find_restriction_sites(seq, enzymes=["XbaI"], topology="linear")
        xba_cuts = res["enzymes"]["XbaI"]["cuts"]
        self.assertEqual(len(xba_cuts), 1)
        self.assertTrue(len(xba_cuts[0]["methylation_warnings"]) > 0)
        self.assertIn("dam", xba_cuts[0]["methylation_warnings"][0])

    def test_check_overhang_compatibility(self):
        from core.tools import check_overhang_compatibility
        # EcoRI 5' overhang: AATT. Opposite strand 5' overhang must be AATT as well!
        res = check_overhang_compatibility("AATT", "AATT", type1="5prime", type2="5prime")
        self.assertTrue(res["compatible"])

        # Mismatched overhangs
        mismatch = check_overhang_compatibility("AATT", "GGCC", type1="5prime", type2="5prime")
        self.assertFalse(mismatch["compatible"])

        # Blunt ends
        blunt = check_overhang_compatibility("", "", type1="blunt", type2="blunt")
        self.assertTrue(blunt["compatible"])

    def test_calc_primer_tm_and_design_overhang(self):
        from core.tools import calc_primer_tm, design_overhang_primers
        tm_res = calc_primer_tm("ATGCGATCGATCGATCGATC")
        self.assertGreater(tm_res["tm"], 45.0)
        self.assertEqual(tm_res["length"], 20)

        # Design primers with 20 bp Gibson homology arms
        rng = random.Random(20260908)
        template = "".join(rng.choice("ACGT") for _ in range(180))
        pair = design_overhang_primers(
            template,
            start=10,
            end=100,
            fwd_5prime_overhang="GGATCCGATCGATC",
            rev_5prime_overhang="AAGCTTGATCGATC",
            target_tm=58.0,
        )
        self.assertTrue(pair["forward_primer"]["full_sequence"].startswith("GGATCCGATCGATC"))
        self.assertTrue(pair["reverse_primer"]["full_sequence"].startswith("AAGCTTGATCGATC"))
        self.assertLessEqual(pair["binding_core_delta_tm"], 5.0)

    def test_get_standard_element(self):
        from core.tools import get_standard_element
        his = get_standard_element("6xHis")
        self.assertEqual(his["aa"], "HHHHHH")
        self.assertEqual(his["category"], "tag")

        g4s = get_standard_element("(G4S)3")
        self.assertEqual(g4s["aa"], "GGGGSGGGGSGGGGS")
        self.assertEqual(len(g4s["dna"]) % 3, 0)

        tev = get_standard_element("TEV")
        self.assertEqual(tev["aa"], "ENLYFQG")

    def test_simulate_golden_gate(self):
        from core.tools import simulate_golden_gate
        # Fragment 1 flanked by BsaI (GGTCTC + 1bp spacer + 4bp overhang + core + 4bp overhang + 1bp spacer + GAGACC)
        f1 = "GGTCTC" + "A" + "TGCA" + "A" * 6 + "ATGA" + "A" + "GAGACC"
        # Fragment 2 (Left overhang ATGA, Right overhang TGCA for circular closure)
        f2 = "GGTCTC" + "A" + "ATGA" + "C" * 6 + "TGCA" + "A" + "GAGACC"

        res = simulate_golden_gate([f1, f2], enzyme="BsaI", circular=True)
        self.assertEqual(res["product_topology"], "circular")
        self.assertEqual(res["fragment_count"], 2)
        self.assertTrue(all(j["compatible"] for j in res["junctions"]))
        # No BsaI recognition sites left in the assembled product!
        self.assertNotIn("GGTCTC", res["product_sequence"])
        self.assertNotIn("GAGACC", res["product_sequence"])

    def test_crispr_grna_and_oligos(self):
        from core.tools import design_crispr_grna, prepare_grna_oligos
        # Target with SpCas9 site (20 nt spacer + TGG)
        target = "A" * 30 + "GCTGATCGATCGATCGATCA" + "TGG" + "C" * 30
        guides = design_crispr_grna(target, nuclease="SpCas9")
        self.assertGreater(len(guides), 0)
        g0 = guides[0]
        self.assertEqual(g0["pam"], "TGG")
        self.assertEqual(len(g0["spacer"]), 20)
        self.assertFalse(g0["has_poly_t"])

        # Prepare oligos for pX458 (BbsI)
        oligos = prepare_grna_oligos(g0["spacer"], vector_type="BbsI")
        self.assertTrue(oligos["forward_oligo"]["sequence"].startswith("CACC"))
        self.assertTrue(oligos["reverse_oligo"]["sequence"].startswith("AAAC"))

    def test_crispr_hdr_donor_design(self):
        from core.tools import design_hdr_donor
        # Cut position at bp 50; spacer starts at cut-17 and has a real CGG PAM.
        target = "A" * 53 + "CGG" + "C" * 44
        res = design_hdr_donor(
            target_seq_or_file=target,
            cut_position_0based=50,
            edit_dna="GAATTC",
            left_arm_length=40,
            right_arm_length=40,
            grna_seq="A" * 20,
            grna_strand=1,
        )
        self.assertEqual(res["donor_type"], "ssODN")
        self.assertIn("GAATTC", res["donor_sequence"])
        self.assertEqual(len(res["left_homology_arm"]), 40)
        self.assertEqual(len(res["right_homology_arm"]), 40)

    def test_strip_terminal_codons(self):
        from core.tools import strip_terminal_codons
        cds = "ATGGCCAAATAA"
        # Strip both start and stop
        res = strip_terminal_codons(cds, strip_start=True, strip_stop=True)
        self.assertEqual(res["sequence"], "GCCAAA")
        self.assertTrue(res["start_stripped"])
        self.assertTrue(res["stop_stripped"])

    def test_get_codon_synonyms(self):
        from core.tools import get_codon_synonyms
        res = get_codon_synonyms("CTG")
        self.assertEqual(res["amino_acid"], "L")
        self.assertIn("CTA", res["synonymous_codons"])
        self.assertIn("TTG", res["synonymous_codons"])
        self.assertEqual(res["synonym_count"], 5)

    def test_check_primer_dimers(self):
        from core.tools import check_primer_dimers
        # Primers with complementary 3' ends: ...GGCC and ...GGCC
        fwd = "ATGCATGCATGCGGCC"
        rev = "TTTTCCCCAAAAGGCC"
        res = check_primer_dimers(fwd, rev)
        self.assertTrue(res["high_dimer_risk"])
        self.assertGreaterEqual(res["max_3prime_complementarity"], 4)

    def test_anneal_oligos(self):
        from core.tools import anneal_oligos
        # Top has 5' CACC overhang, Bottom has 5' AAAC overhang
        # Core is 20 bp: GCTGATCGATCGATCGATCA
        # top: CACC + GCTGATCGATCGATCGATCA
        # bot: AAAC + TGATCGATCGATCGATCAGC
        core = "GCTGATCGATCGATCGATCA"
        core_rc = "TGATCGATCGATCGATCAGC"
        top = "CACC" + core
        bot = "AAAC" + core_rc
        res = anneal_oligos(top, bot)
        self.assertEqual(res["duplex_core_sequence"], core)
        self.assertEqual(res["left_overhang"]["sequence"], "CACC")
        self.assertEqual(res["right_overhang"]["sequence"], "AAAC")

    def test_digest_sequence(self):
        from core.tools import digest_sequence
        seq = "AAAAAGAATTCCCCCGGATCCAAAAA"
        # EcoRI (GAATTC) cuts at 7 (after G)
        # BamHI (GGATCC) cuts at 18 (after G)
        res = digest_sequence(seq, "EcoRI", circular=False)
        self.assertEqual(res["cut_count"], 1)
        self.assertEqual(res["fragment_count"], 2)
        self.assertEqual(res["fragments"][0]["right_overhang"], "AATT")

    def test_digest_type_iis(self):
        from core.tools import digest_type_iis
        # BsaI cuts outside recognition
        f = "GGTCTC" + "A" + "TGCA" + "AAAAAA" + "ATGA" + "A" + "GAGACC"
        res = digest_type_iis(f, enzyme="BsaI")
        self.assertEqual(res["left_overhang"], "TGCA")
        self.assertEqual(res["right_overhang"], "ATGA")
        self.assertNotIn("GGTCTC", res["insert_core"])

    def test_fill_or_chew_overhang(self):
        from core.tools import fill_or_chew_overhang
        # Fill in 5' AATT overhang
        res = fill_or_chew_overhang("CCCC", left_overhang="AATT", overhang_type="5prime", action="fill_in")
        self.assertEqual(res["end_type"], "blunt")
        self.assertTrue(res["blunted_sequence"].startswith("AATT"))

    def test_extract_homology_arms(self):
        from core.tools import extract_homology_arms
        seq = "A" * 60 + "C" * 60
        res = extract_homology_arms(seq, cut_position_0based=60, left_arm_length=30, right_arm_length=30)
        self.assertEqual(res["left_homology_arm"], "A" * 30)
        self.assertEqual(res["right_homology_arm"], "C" * 30)


if __name__ == "__main__":
    unittest.main()

