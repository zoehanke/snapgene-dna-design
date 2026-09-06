# -*- coding: utf-8 -*-
"""tests/test_annotate_primers.py - Regression test suite for in-place primer editing.

Validates that primer add, remove, replace, and clear operations on existing
.dna and .gb files strictly preserve sequence integrity and non-primer annotations.
"""
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord
from sgffp import SgffFeature, SgffObject, SgffReader, SgffSegment, SgffWriter

from scripts.annotate_primers import (
    annotate_primers_dna,
    annotate_primers_gb,
    find_unique_binding_site,
)


class TestAnnotatePrimers(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_primers_")
        self.pdonr_fixture = Path("fixtures/pDONR201.dna")
        self.assertTrue(self.pdonr_fixture.exists(), "fixtures/pDONR201.dna must exist")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dna_add_preserves_construct(self):
        """Test 1: Adding primer on .dna preserves sequence, all 9 features, and major blocks."""
        src_obj = SgffReader.from_file(str(self.pdonr_fixture))
        orig_seq = str(src_obj.sequence.data.value).upper()
        orig_hash = hashlib.sha256(orig_seq.encode("ascii")).hexdigest()
        orig_feat_names = [f.name for f in src_obj.features]
        self.assertEqual(len(orig_feat_names), 9, "pDONR201 should have 9 features")
        orig_blocks = set(src_obj.blocks.keys())

        # Select a unique 20-mer from the sequence for forward binding
        primer_seq = orig_seq[100:120]
        out_dna = Path(self.temp_dir) / "pdonr_annotated.dna"

        result = annotate_primers_dna(
            source_path=self.pdonr_fixture,
            out_path=out_dna,
            op="add",
            primers_to_add=[{"name": "test_fwd", "sequence": primer_seq}],
        )

        self.assertEqual(result["status"], "success")
        self.assertTrue(out_dna.exists())

        # Re-read and verify preservation
        new_obj = SgffReader.from_file(str(out_dna))
        new_seq = str(new_obj.sequence.data.value).upper()
        self.assertEqual(
            hashlib.sha256(new_seq.encode("ascii")).hexdigest(),
            orig_hash,
            "Sequence hash must remain strictly unchanged",
        )

        # Verify features are completely intact
        new_feat_names = [f.name for f in new_obj.features]
        self.assertEqual(new_feat_names, orig_feat_names)

        # Verify major blocks remain
        new_blocks = set(new_obj.blocks.keys())
        for b in [0, 10, 6, 8]:
            if b in orig_blocks:
                self.assertIn(b, new_blocks, f"Major block {b} must be retained")

        # Verify primer was added
        self.assertEqual(len(new_obj.primers), 1)
        self.assertEqual(new_obj.primers[0].name, "test_fwd")
        self.assertEqual(new_obj.primers[0].sequence, primer_seq)

    def test_dna_remove_replace_clear(self):
        """Test 2: Basic functionality of remove, replace, and clear operations on .dna."""
        # Create a test .dna with 2 primers
        tpl_seq = "ATGCGATCGATCGATCGATCGATCGAACCTTGGCCAATTGG"
        sg = SgffObject.new(tpl_seq, topology="circular")
        sg.features.add(
            SgffFeature(name="geneA", type="CDS", strand="+", segments=[SgffSegment(0, 20)])
        )
        sg.add_primer("p1", "ATGCGATCGATC", bind_position=0, bind_strand="+")
        sg.add_primer("p2", "CCAATTGG", bind_position=34, bind_strand="+")

        step0 = Path(self.temp_dir) / "step0.dna"
        SgffWriter.to_file(sg, str(step0))

        # 1. Replace p1 with p1_v2
        step1 = Path(self.temp_dir) / "step1_replace.dna"
        res_rep = annotate_primers_dna(
            source_path=step0,
            out_path=step1,
            op="replace",
            primers_to_add=[],
            target_name="p1",
            new_primer={"name": "p1_v2", "sequence": "ATGCGATC", "bind_position": 0, "strand": "+"},
        )
        self.assertEqual(res_rep["primers_count"], 2)
        rep_obj = SgffReader.from_file(str(step1))
        p_names = [p.name for p in rep_obj.primers]
        self.assertIn("p1_v2", p_names)
        self.assertNotIn("p1", p_names)
        self.assertEqual(len(rep_obj.features), 1)

        # 2. Remove p2
        step2 = Path(self.temp_dir) / "step2_remove.dna"
        res_rem = annotate_primers_dna(
            source_path=step1,
            out_path=step2,
            op="remove",
            primers_to_add=[],
            target_name="p2",
        )
        self.assertEqual(res_rem["primers_count"], 1)
        rem_obj = SgffReader.from_file(str(step2))
        self.assertEqual([p.name for p in rem_obj.primers], ["p1_v2"])
        self.assertEqual(len(rem_obj.features), 1)

        # 3. Clear all primers
        step3 = Path(self.temp_dir) / "step3_clear.dna"
        res_clr = annotate_primers_dna(
            source_path=step2,
            out_path=step3,
            op="clear",
            primers_to_add=[],
        )
        self.assertEqual(res_clr["primers_count"], 0)
        clr_obj = SgffReader.from_file(str(step3))
        self.assertEqual(len(clr_obj.primers), 0)
        self.assertEqual(len(clr_obj.features), 1)
        self.assertEqual(str(clr_obj.sequence.data.value).upper(), tpl_seq)

    def test_auto_binding_unique_forward_reverse_and_ambiguous(self):
        """Test 3: Auto-binding strictly resolves unique matches across strands and fails closed on 0 or >1 matches."""
        template = "ATGCGTAGCTAGCTAGCTGATCGATCGATCGATCGATCGTCGAACCTT"

        # Unique forward match
        p_fwd = "ATGCGTAGCTAG"
        pos_fwd, st_fwd = find_unique_binding_site(template, p_fwd)
        self.assertEqual(pos_fwd, 0)
        self.assertEqual(st_fwd, "+")

        # Unique reverse complement match (reverse complement of TCGAACCTT is AAGGTTCGA)
        p_rev = "AAGGTTCGA"
        pos_rev, st_rev = find_unique_binding_site(template, p_rev)
        self.assertEqual(pos_rev, 39)
        self.assertEqual(st_rev, "-")

        # Ambiguous match ("GATC" occurs multiple times)
        with self.assertRaises(ValueError) as ctx:
            find_unique_binding_site(template, "GATC")
        self.assertIn("Ambiguous binding", str(ctx.exception))

        # No match
        with self.assertRaises(ValueError) as ctx:
            find_unique_binding_site(template, "TTTTTTTT")
        self.assertIn("0 binding sites", str(ctx.exception))

    def test_strict_name_matching(self):
        """Test 4: Strict unique name matching fails closed on missing (0) or duplicate (>1) primer names."""
        sg = SgffObject.new("ATGCGATCGATCGATCGATC", topology="linear")
        sg.add_primer("dup_primer", "ATGC", bind_position=0, bind_strand="+")
        sg.add_primer("dup_primer", "GATC", bind_position=4, bind_strand="+")
        src = Path(self.temp_dir) / "dup.dna"
        SgffWriter.to_file(sg, str(src))

        # Missing name on remove -> fails
        with self.assertRaises(ValueError) as ctx:
            annotate_primers_dna(
                source_path=src,
                out_path=Path(self.temp_dir) / "out.dna",
                op="remove",
                primers_to_add=[],
                target_name="non_existent",
            )
        self.assertIn("not found", str(ctx.exception))

        # Ambiguous name on remove -> fails
        with self.assertRaises(ValueError) as ctx:
            annotate_primers_dna(
                source_path=src,
                out_path=Path(self.temp_dir) / "out.dna",
                op="remove",
                primers_to_add=[],
                target_name="dup_primer",
            )
        self.assertIn("Ambiguous primer name", str(ctx.exception))

        # Ambiguous name on replace -> fails
        with self.assertRaises(ValueError) as ctx:
            annotate_primers_dna(
                source_path=src,
                out_path=Path(self.temp_dir) / "out.dna",
                op="replace",
                primers_to_add=[],
                target_name="dup_primer",
                new_primer={"name": "new_p", "sequence": "ATGC", "bind_position": 0},
            )
        self.assertIn("Ambiguous primer name", str(ctx.exception))

    def test_genbank_primer_editing(self):
        """Test 5: GenBank in-place primer add, replace, remove, and clear smoke test."""
        seq = Seq("ATGCGTAGCTAGCTAGCTGATCGATCGATCGATCGATCGTCGAACCTT")
        rec = SeqRecord(seq, id="test_plasmid", name="test_plasmid")
        rec.features.append(
            SeqFeature(FeatureLocation(0, 15), type="CDS", qualifiers={"label": ["cds1"]})
        )
        rec.features.append(
            SeqFeature(FeatureLocation(39, 48), type="primer_bind", qualifiers={"label": ["orig_p"]})
        )
        rec.annotations["molecule_type"] = "DNA"

        gb_file = Path(self.temp_dir) / "test.gb"
        with open(gb_file, "w", encoding="utf-8") as fh:
            SeqIO.write(rec, fh, "genbank")

        # 1. Add primer (forward auto-bind)
        gb_add = Path(self.temp_dir) / "gb_add.gb"
        res_add = annotate_primers_gb(
            source_path=gb_file,
            out_path=gb_add,
            op="add",
            primers_to_add=[{"name": "p_new", "sequence": "ATGCGTAGCTAG"}],
        )
        self.assertEqual(res_add["primers_count"], 2)
        rec_add = SeqIO.read(str(gb_add), "genbank")
        self.assertEqual(str(rec_add.seq), str(seq))
        self.assertTrue(any(f.type == "CDS" and f.qualifiers["label"][0] == "cds1" for f in rec_add.features))

        # 2. Replace primer
        gb_rep = Path(self.temp_dir) / "gb_rep.gb"
        res_rep = annotate_primers_gb(
            source_path=gb_add,
            out_path=gb_rep,
            op="replace",
            primers_to_add=[],
            target_name="orig_p",
            new_primer={"name": "orig_p_mod", "sequence": "AAGGTTCGA"},
        )
        rec_rep = SeqIO.read(str(gb_rep), "genbank")
        p_labels = [f.qualifiers["label"][0] for f in rec_rep.features if f.type == "primer_bind"]
        self.assertIn("orig_p_mod", p_labels)
        self.assertNotIn("orig_p", p_labels)

        # 3. Remove primer
        gb_rem = Path(self.temp_dir) / "gb_rem.gb"
        res_rem = annotate_primers_gb(
            source_path=gb_rep,
            out_path=gb_rem,
            op="remove",
            primers_to_add=[],
            target_name="p_new",
        )
        self.assertEqual(res_rem["primers_count"], 1)

        # 4. Clear primers
        gb_clr = Path(self.temp_dir) / "gb_clr.gb"
        res_clr = annotate_primers_gb(
            source_path=gb_rem,
            out_path=gb_clr,
            op="clear",
            primers_to_add=[],
        )
        self.assertEqual(res_clr["primers_count"], 0)
        rec_clr = SeqIO.read(str(gb_clr), "genbank")
        self.assertEqual(len(rec_clr.features), 1)
        self.assertEqual(rec_clr.features[0].type, "CDS")

    def test_output_protection_and_sequence_invariant(self):
        """Test 6: Overwrite protection and sequence invariant failure on tampering."""
        src = Path(self.temp_dir) / "protect.dna"
        sg = SgffObject.new("ATGCGATCGATCGATC", topology="circular")
        SgffWriter.to_file(sg, str(src))

        # CLI-level overwrite check
        from scripts.annotate_primers import main
        import sys
        from unittest.mock import patch

        old_argv = sys.argv
        try:
            # Overwriting without --allow-overwrite should exit with code 2
            sys.argv = [
                "annotate_primers.py",
                str(src),
                "--out",
                str(src),
                "--op",
                "clear",
            ]
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertNotEqual(ctx.exception.code, 0)
        finally:
            sys.argv = old_argv

        # Simulate tampering with SgffWriter output to test sequence invariant fail-closed
        orig_to_file = SgffWriter.to_file
        def tamper_to_file(obj, path, **kwargs):
            obj.sequence.data.value = "TTTTTTTTTTTTTTTT"
            obj.sequence._sync()
            orig_to_file(obj, path, **kwargs)

        with patch("sgffp.writer.SgffWriter.to_file", side_effect=tamper_to_file):
            tamper_out = Path(self.temp_dir) / "tamper_out.dna"
            with self.assertRaises(RuntimeError) as ctx:
                annotate_primers_dna(
                    source_path=src,
                    out_path=tamper_out,
                    op="clear",
                    primers_to_add=[],
                )
            self.assertIn("Hard invariant violated", str(ctx.exception))
            self.assertFalse(tamper_out.exists(), "Tampered output file must be cleaned up")


if __name__ == "__main__":
    unittest.main()
