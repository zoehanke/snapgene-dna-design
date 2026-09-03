# -*- coding: utf-8 -*-
"""Unit tests for atomic biological tools (core/tools/)."""
from __future__ import annotations

import pathlib
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
        template = "A" * 20 + "GATTACA" * 4 + "C" * 20
        f_primer = "GAATTC" + "A" * 18
        r_primer = "GCGGCCGC" + "G" * 18

        res = simulate_pcr(template, f_primer, r_primer)
        amplicon = res["amplicon"]
        self.assertTrue(amplicon.startswith("GAATTC"))
        self.assertTrue(amplicon.endswith("GCGGCCGC"))
        self.assertIn("GATTACA", amplicon)

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
        self.assertGreaterEqual(len(defs), 12)
        for d in defs:
            self.assertIn("name", d)
            self.assertIn("description", d)
            self.assertIn("parameters", d)


if __name__ == "__main__":
    unittest.main()
