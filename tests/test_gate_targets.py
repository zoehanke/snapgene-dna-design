# -*- coding: utf-8 -*-
"""Coverage-gate target tests.

Exercises the core modules systematically so the coverage gate
(scripts/coverage_gate.py) can reach line >= 90% / branch >= 85% on:

    sg_common, assembly_model, construct_model, simulate_cloning,
    simulate_advanced, golden_gate, write_dna, validate_roundtrip,
    validate_construct, edit_plasmid

These tests are synthetic and run in both release packages.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, Reference, SeqFeature
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "fixtures" / "rich"
sys.path.insert(0, str(SCRIPTS))

import construct_model  # noqa: E402
import edit_plasmid  # noqa: E402
import golden_gate  # noqa: E402
import sg_common  # noqa: E402
import simulate_advanced  # noqa: E402
import simulate_cloning  # noqa: E402
import validate_construct  # noqa: E402
import validate_roundtrip  # noqa: E402
import write_dna  # noqa: E402
from assembly_model import AssemblyError, AssemblyFragment, overhang_end  # noqa: E402
from construct_model import ConstructModel  # noqa: E402


def run_cli(name, *args, expect_fail=False):
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / name)] + list(args),
        cwd=str(SCRIPTS), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    if expect_fail:
        if completed.returncode == 0:
            raise AssertionError("%s unexpectedly succeeded" % name)
    else:
        if completed.returncode != 0:
            raise AssertionError(
                "%s failed: %s" % (name, (completed.stderr + completed.stdout)[-800:]))
    return completed


def record(sequence, name="rec", circular=False, features=()):
    rec = SeqRecord(Seq(sequence), id=name, name=name)
    rec.annotations = {"molecule_type": "DNA",
                       "topology": "circular" if circular else "linear"}
    for feature in features:
        rec.features.append(feature)
    return rec


def label_feature(start, end, label, strand=1, ftype="misc_feature",
                  qualifiers=None):
    return SeqFeature(FeatureLocation(start, end, strand=strand), type=ftype,
                      qualifiers=qualifiers or {"label": [label]})


def write_gb(rec, directory, name):
    path = pathlib.Path(directory) / name
    with open(path, "w", encoding="utf-8") as handle:
        SeqIO.write(rec, handle, "genbank")
    return path


def write_fa(sequence, directory, name="seq.fa"):
    path = pathlib.Path(directory) / name
    path.write_text(">%s\n%s\n" % (name, sequence), encoding="utf-8")
    return path


class DefaultOutputFormatTests(unittest.TestCase):
    def test_write_dna_default_is_native_dna(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "default.dna"
            completed = run_cli("write_dna.py", "ATGCATGCATGC",
                                "--out", str(out), "--json")
            self.assertTrue(out.exists())
            reread = SeqIO.read(out, "snapgene")
            self.assertEqual(str(reread.seq), "ATGCATGCATGC")


class ConstructModelTests(unittest.TestCase):
    def test_rotate_wraps_parts_and_rotates_letter_annotations(self):
        rec = record("AAAACCCCGGGGTTTT", circular=True,
                     features=[label_feature(10, 14, "cross")])
        rec.letter_annotations["phred_quality"] = [30] * 16
        model = ConstructModel(rec)
        out = model.rotate(4).to_record()
        self.assertEqual(str(out.seq), "CCCCGGGGTTTTAAAA")
        feature = out.features[0]
        self.assertEqual(
            [(int(p.start), int(p.end)) for p in feature.location.parts],
            [(6, 10)])
        self.assertEqual(out.letter_annotations["phred_quality"][:4], [30] * 4)
        self.assertEqual(model.length, 16)

    def test_rotate_splits_part_that_crosses_new_origin(self):
        rec = record("AAAACCCCGGGGTTTT", circular=True,
                     features=[label_feature(10, 16, "crossA"),
                               label_feature(0, 2, "crossB")])
        out = ConstructModel(rec).rotate(14).to_record()
        feature_a = next(f for f in out.features
                         if "crossA" in f.qualifiers.get("label", []))
        parts_a = [(int(p.start), int(p.end)) for p in feature_a.location.parts]
        self.assertEqual(parts_a, [(12, 16), (0, 2)])

    def test_rotate_zero_origin_is_noop_with_topology(self):
        rec = record("AAAACCCC", circular=True)
        out = ConstructModel(rec).rotate(0, topology="circular").to_record()
        self.assertEqual(str(out.seq), "AAAACCCC")
        self.assertEqual(out.annotations["topology"], "circular")

    def test_rotate_out_of_range_raises(self):
        rec = record("AAAACCCC", circular=True)
        with self.assertRaises(ValueError):
            ConstructModel(rec).rotate(8)
        with self.assertRaises(ValueError):
            ConstructModel(rec).rotate(-1)

    def test_delete_maps_boundaries_and_drops_emptied_features(self):
        rec = record("AAAACCCCGGGG", features=[label_feature(6, 8, "f")])
        out = ConstructModel(rec).delete(2, 6).to_record()
        self.assertEqual(str(out.seq), "AACCGGGG")
        feature = out.features[0]
        self.assertEqual((int(feature.location.start), int(feature.location.end)),
                         (2, 4))

    def test_indel_inside_cds_marks_feature_partial_with_reason(self):
        cds = label_feature(0, 9, "lacZalpha", ftype="CDS",
                            qualifiers={"label": ["lacZalpha"]})
        inserted = ConstructModel(record("ATGAAATAA", features=[cds])).insert(
            3, "CC").to_record()
        feature = inserted.features[0]
        self.assertEqual(feature.qualifiers["partial"], ["true"])
        self.assertIn("CDS interrupted by insertion",
                      feature.qualifiers["note"][0])

        deleted = ConstructModel(record("ATGAAATAA", features=[cds])).delete(
            3, 5).to_record()
        feature = deleted.features[0]
        self.assertEqual(feature.qualifiers["partial"], ["true"])
        self.assertIn("CDS interrupted by deletion",
                      feature.qualifiers["note"][0])

    def test_indel_at_cds_boundary_does_not_mark_partial(self):
        cds = label_feature(2, 8, "boundary-cds", ftype="CDS",
                            qualifiers={"label": ["boundary-cds"]})
        out = ConstructModel(record("AAAACCCCGG", features=[cds])).insert(
            2, "TT").to_record()
        self.assertNotIn("partial", out.features[0].qualifiers)

    def test_mutate_and_errors(self):
        rec = record("AAAACCCC")
        out = ConstructModel(rec).mutate([(1, "T")]).to_record()
        self.assertEqual(str(out.seq), "ATAACCCC")
        with self.assertRaises(ValueError):
            ConstructModel(rec).mutate([(9, "T")])

    def test_insert_delete_replace_boundary_errors(self):
        rec = record("AAAACCCC")
        with self.assertRaises(ValueError):
            ConstructModel(rec).insert(9, "T")
        with self.assertRaises(ValueError):
            ConstructModel(rec).insert(-1, "T")
        with self.assertRaises(ValueError):
            ConstructModel(rec).insert(1, "")
        with self.assertRaises(ValueError):
            ConstructModel(rec).delete(4, 4)
        with self.assertRaises(ValueError):
            ConstructModel(rec).delete(-1, 2)
        with self.assertRaises(ValueError):
            ConstructModel(rec).delete(3, 9)
        replaced = ConstructModel(rec).replace(1, 3, "GG").to_record()
        self.assertEqual(str(replaced.seq), "AGGACCCC")

    def test_letter_annotations_cleared_on_insert(self):
        rec = record("AAAACCCC")
        rec.letter_annotations["phred_quality"] = [30] * 8
        model = ConstructModel(rec)
        out = model.insert(2, "T").to_record()
        self.assertEqual(out.letter_annotations, {})
        self.assertIn("per-letter annotations removed", model.warnings[0])

    def test_set_topology_and_to_dict(self):
        rec = record("AAAACCCC")
        model = ConstructModel(rec)
        self.assertEqual(model.to_dict()["topology"], "linear")
        model.set_topology("circular")
        self.assertEqual(model.to_dict()["topology"], "circular")
        with self.assertRaises(ValueError):
            model.set_topology("torus")

    def test_feature_to_dict_preserves_refs_compound_and_id(self):
        parts = [
            FeatureLocation(4, 8, strand=1, ref="X", ref_db="GenBank"),
            FeatureLocation(0, 2, strand=1),
        ]
        location = CompoundLocation(parts, operator="order")
        feature = SeqFeature(location, type="misc_feature",
                             qualifiers={"label": ["compound"], "note": ["a", "b"]})
        feature.id = "abc123"
        d = construct_model.feature_to_dict(feature, 16)
        self.assertEqual(d["location"]["operator"], "order")
        self.assertEqual(len(d["segments"]), 2)
        self.assertEqual(d["location"]["parts"][0]["strand"], 1)
        self.assertEqual(d["location"]["wraps_origin"], True)
        self.assertEqual(d["id"], "abc123")
        self.assertEqual(d["qualifiers"]["note"], ["a", "b"])

    def test_feature_to_dict_single_part_and_no_id(self):
        feature = SeqFeature(FeatureLocation(0, 4, strand=-1),
                             type="gene", qualifiers={"gene": ["g"]})
        d = construct_model.feature_to_dict(feature, 16)
        self.assertEqual(d["strand"], -1)
        self.assertNotIn("id", d)
        self.assertEqual(d["name"], "g")
        self.assertEqual(d["location"]["parts"][0]["start0"], 0)

    def test_parts_merge_contiguous_and_location_helper(self):
        parts = [
            FeatureLocation(0, 2, strand=1),
            FeatureLocation(2, 4, strand=1),
        ]
        loc = construct_model._location(parts, "join")
        self.assertIsInstance(loc, CompoundLocation)
        self.assertEqual(len(loc.parts), 2)
        self.assertIsNone(construct_model._location([], "join"))
        self.assertEqual(construct_model._location([parts[0]], "join"), parts[0])
        self.assertIsInstance(
            construct_model._location([parts[0], parts[1]], "order"),
            CompoundLocation)


class SgCommonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sgcommon-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def test_load_seq_variants(self):
        rec, fmt = sg_common.load_seq("ATGC")
        self.assertEqual(fmt, "raw")
        self.assertEqual(str(rec.seq), "ATGC")
        path = write_fa("ACGTACGT", self.dir, "s.fa")
        rec, fmt = sg_common.load_seq(str(path))
        self.assertEqual(fmt, "fasta")
        fasta_text = ">inline\nAACCGGTT\n"
        rec, fmt = sg_common.load_seq(fasta_text)
        self.assertEqual(fmt, "raw-fasta")
        with self.assertRaises(FileNotFoundError):
            sg_common.load_seq(str(self.dir / "missing.gb"))
        with self.assertRaises(ValueError):
            sg_common.load_seq("")
        with self.assertRaises(ValueError):
            sg_common.load_seq("ATGX")
        bad_fasta = ">a\nACGT\n>b\nTGCA\n"
        with self.assertRaises(ValueError):
            sg_common.load_seq(bad_fasta)

    def test_normalize_and_looks_like_path(self):
        self.assertEqual(sg_common.normalize_dna("a c g t"), "ACGT")
        with self.assertRaises(ValueError):
            sg_common.normalize_dna("")
        with self.assertRaises(ValueError):
            sg_common.normalize_dna("ACGTZ")
        self.assertTrue(sg_common.looks_like_path("a/b.gb"))
        self.assertTrue(sg_common.looks_like_path("C:\\x\\y.dna"))
        self.assertTrue(sg_common.looks_like_path("file.fa"))
        self.assertFalse(sg_common.looks_like_path("ATGCAT"))

    def test_jprint_envelope_and_warnings_coercion(self):
        import io
        from contextlib import redirect_stdout
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            sg_common.jprint({"warnings": "not-a-list", "x": 1})
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["schema_version"], "0.5.0")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["warnings"], ["not-a-list"])
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            sg_common.jprint(["legacy", "array"])
        self.assertEqual(json.loads(buffer.getvalue()), ["legacy", "array"])

    def test_jfail_envelope(self):
        import io
        from contextlib import redirect_stdout
        buffer = io.StringIO()
        with self.assertRaises(SystemExit) as ctx:
            with redirect_stdout(buffer):
                sg_common.jfail("CODE_X", "boom", details={"a": 1},
                                warnings=["w"])
        self.assertEqual(ctx.exception.code, 1)
        payload = json.loads(buffer.getvalue())
        self.assertFalse(payload["ok"])
        self.assertIsNone(payload["data"])
        self.assertEqual(payload["error"]["code"], "CODE_X")
        self.assertEqual(payload["error"]["details"], {"a": 1})

    def test_gc_percent_and_topology(self):
        self.assertAlmostEqual(sg_common.gc_percent("GCGCAT"), 2 / 3 * 100)
        self.assertEqual(sg_common.gc_percent(""), 0.0)
        rec = record("AAAA")
        self.assertEqual(sg_common.topology(rec), "linear")
        rec.annotations["topology"] = "circular"
        self.assertEqual(sg_common.topology(rec), "circular")
        rec.annotations["topology"] = "mobius"
        self.assertEqual(sg_common.topology(rec), "linear")

    def test_get_enzyme_and_enzyme_sites(self):
        eco = sg_common.get_enzyme("ecori")
        self.assertEqual(str(eco.site), "GAATTC")
        with self.assertRaises(ValueError):
            sg_common.get_enzyme("NotARealEnzyme999")
        rec_seq = "GGAATTCC"
        sites = sg_common.enzyme_sites(rec_seq, eco, circular=False)
        self.assertEqual(sites, [3])
        self.assertEqual(sg_common.enzyme_sites("AAAA", eco), [])
        circular_sites = sg_common.enzyme_sites("TTGGAATTCC", eco, circular=True)
        self.assertEqual(len(circular_sites), 1)

    def test_restriction_hits_behaviors(self):
        class FakeEnzyme:
            site = "GTGG"
            fst5 = 1
            fst3 = 1

        hits = sg_common.restriction_hits("GGGACGT", FakeEnzyme, circular=True)
        self.assertTrue(any(h["wraps_origin"] for h in hits))
        self.assertTrue(all(h["cuts_within_sequence"] for h in hits))
        self.assertEqual(sg_common.restriction_hits("TTTT", FakeEnzyme), [])
        self.assertEqual(sg_common.restriction_hits("", FakeEnzyme), [])

        class NonPalindrome:
            site = "AACC"
            fst5 = 2
            fst3 = 1

        hits = sg_common.restriction_hits("AACCGGTT", NonPalindrome)
        strands = {h["strand"] for h in hits}
        self.assertEqual(strands, {1, -1})

    def test_features_to_dict(self):
        rec = record("AAAACCCC", features=[label_feature(0, 4, "f")])
        d = sg_common.features_to_dict(rec)
        self.assertEqual(d[0]["name"], "f")


class ValidateConstructTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="vconstruct-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def test_valid_circular_construct_passes(self):
        cds = SeqFeature(FeatureLocation(0, 12, strand=1), type="CDS",
                         qualifiers={"label": ["cds"], "codon_start": ["1"],
                                     "translation": [str(Seq("ATGGCTAAATGA").translate())]})
        rec = record("ATGGCTAAATGAGGAATTCC", circular=True, features=[cds])
        result = validate_construct.validate(rec)
        self.assertTrue(result["summary"]["pass"])
        self.assertEqual(result["topology"], "circular")
        cutters = [c for c in result["checks"] if c["check"] == "unique_cutter"
                   and c["status"] == "ok"]
        self.assertTrue(cutters)

    def test_premature_stop_is_error(self):
        cds = SeqFeature(FeatureLocation(0, 12, strand=1), type="CDS",
                         qualifiers={"label": ["cds"]})
        rec = record("ATGTAAATGGCT", features=[cds])
        result = validate_construct.validate(rec)
        self.assertFalse(result["summary"]["pass"])
        codes = {c["check"] for c in result["checks"] if c["status"] == "error"}
        self.assertIn("cds_premature_stop", codes)

    def test_frame_error_and_out_of_bounds(self):
        cds = SeqFeature(FeatureLocation(0, 10, strand=1), type="CDS",
                         qualifiers={"label": ["cds"]})
        rec = record("ATGGCTAAATT", features=[cds])
        result = validate_construct.validate(rec)
        codes = {c["check"] for c in result["checks"] if c["status"] == "error"}
        self.assertIn("cds_frame", codes)

        bad = SeqFeature(FeatureLocation(5, 20, strand=1), type="misc_feature",
                         qualifiers={"label": ["bad"]})
        rec = record("AAAACCCC", features=[bad])
        result = validate_construct.validate(rec)
        codes = {c["check"] for c in result["checks"] if c["status"] == "error"}
        self.assertIn("feature_coordinates", codes)

    def test_reverse_cds_with_translation_table(self):
        cds = SeqFeature(FeatureLocation(0, 12, strand=-1), type="CDS",
                         qualifiers={"label": ["rev"], "transl_table": ["1"]})
        rec = record("TCATTTAGCCAT", features=[cds])
        result = validate_construct.validate(rec)
        self.assertTrue(result["summary"]["pass"])

    def test_empty_and_primer_and_junction_checks(self):
        rec = record("", "empty")
        result = validate_construct.validate(rec)
        codes = {c["check"] for c in result["checks"] if c["status"] == "error"}
        self.assertIn("length", codes)

        primer = SeqFeature(FeatureLocation(0, 5, strand=1), type="primer_bind",
                            qualifiers={"label": ["p1"]})
        compound = SeqFeature(
            CompoundLocation([FeatureLocation(0, 2, strand=1),
                              FeatureLocation(4, 6, strand=1)]),
            type="misc_feature", qualifiers={"label": ["j"]})
        rec = record("AAAACCCCGGGG", features=[primer, compound])
        result = validate_construct.validate(rec)
        primer_check = next(c for c in result["checks"] if c["check"] == "primers")
        self.assertEqual(primer_check["status"], "ok")
        junction = next(c for c in result["checks"] if c["check"] == "junction")
        self.assertIn("1 multi-segment", junction["detail"])

    def test_cli_pass_and_fail(self):
        path = write_gb(record("ATGGCTAAAGGAATTCC", "ok"), self.dir, "ok.gb")
        completed = run_cli("validate_construct.py", str(path), "--json")
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["data"]["summary"]["pass"])

        bad_cds = SeqFeature(FeatureLocation(0, 12, strand=1), type="CDS",
                             qualifiers={"label": ["cds"]})
        bad = write_gb(record("ATGTAAATGGCT", "bad", features=[bad_cds]),
                       self.dir, "bad.gb")
        completed = run_cli("validate_construct.py", str(bad), "--json",
                            expect_fail=True)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload["data"]["summary"]["pass"])


class EditPlasmidTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="editplasmid-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def _rec(self, circular=False):
        feature = label_feature(2, 8, "f")
        return record("AAAACCCCGGGG", "p", circular=circular, features=[feature])

    def test_all_operations(self):
        out = edit_plasmid.op_insert(self._rec(), 3, "TT")
        self.assertEqual(str(out.seq), "AATTAACCCCGGGG")
        out = edit_plasmid.op_delete(self._rec(), 3, 6)
        self.assertEqual(str(out.seq), "AACCGGGG")
        out = edit_plasmid.op_replace(self._rec(), 3, 6, "G")
        self.assertEqual(str(out.seq), "AAGCCGGGG")
        out = edit_plasmid.op_mutate(self._rec(), ["1:T", "4:G"])
        self.assertEqual(str(out.seq), "TAAGCCCCGGGG")
        out = edit_plasmid.op_linearize(self._rec(circular=True), 5)
        self.assertEqual(out.annotations["topology"], "linear")
        self.assertEqual(str(out.seq), "CCCCGGGGAAAA")
        out = edit_plasmid.op_circularize(self._rec())
        self.assertEqual(out.annotations["topology"], "circular")
        out = edit_plasmid.op_rotate(self._rec(circular=True), 3)
        self.assertEqual(str(out.seq), "AACCCCGGGGAA")
        self.assertEqual(out.annotations["topology"], "circular")

    def test_operation_errors(self):
        rec = self._rec()
        with self.assertRaises(ValueError):
            edit_plasmid.op_insert(rec, 0, "T")
        with self.assertRaises(ValueError):
            edit_plasmid.op_insert(rec, 99, "T")
        with self.assertRaises(ValueError):
            edit_plasmid.op_insert(rec, 1, "ACGTX")
        with self.assertRaises(ValueError):
            edit_plasmid.op_delete(rec, 0, 2)
        with self.assertRaises(ValueError):
            edit_plasmid.op_delete(rec, 3, 99)
        with self.assertRaises(ValueError):
            edit_plasmid.op_replace(rec, 0, 2, "T")
        with self.assertRaises(ValueError):
            edit_plasmid.op_mutate(rec, ["bad"])
        with self.assertRaises(ValueError):
            edit_plasmid.op_mutate(rec, ["1:ZZ"])
        with self.assertRaises(ValueError):
            edit_plasmid.op_mutate(rec, ["99:T"])
        with self.assertRaises(ValueError):
            edit_plasmid.op_linearize(rec, 1)  # not circular
        with self.assertRaises(ValueError):
            edit_plasmid.op_rotate(rec, 1)  # not circular
        with self.assertRaises(ValueError):
            edit_plasmid.op_rotate(self._rec(circular=True), 99)

    def test_cli_ops_and_errors(self):
        src = write_gb(self._rec(), self.dir, "p.gb")
        out = self.dir / "out.gb"
        run_cli("edit_plasmid.py", str(src), "--op", "insert", "--pos", "3",
                "--seq", "TT", "--out", str(out), "--json")
        reread = SeqIO.read(str(out), "genbank")
        self.assertEqual(str(reread.seq), "AATTAACCCCGGGG")
        run_cli("edit_plasmid.py", str(src), "--op", "mutate",
                "--mutation", "1:T", "--out", str(out), "--json")
        run_cli("edit_plasmid.py", str(src), "--op", "linearize", "--pos", "2",
                "--out", str(out), expect_fail=True)
        run_cli("edit_plasmid.py", str(src), "--op", "rotate", "--pos", "2",
                "--out", str(out), expect_fail=True)
        run_cli("edit_plasmid.py", str(src), "--op", "insert",
                "--out", str(out), expect_fail=True)
        run_cli("edit_plasmid.py", str(src), "--op", "mutate",
                "--out", str(out), expect_fail=True)
        run_cli("edit_plasmid.py", str(src), "--op", "delete",
                "--start", "0", "--end", "2", "--out", str(out),
                expect_fail=True)


class CloningCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cloningcli-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def test_gibson_cli_success_writes_product(self):
        a = write_fa("AAAA" + "C" * 12, self.dir, "a.fa")
        b = write_fa("C" * 12 + "GGGG", self.dir, "b.fa")
        out = self.dir / "p.gb"
        completed = run_cli("simulate_cloning.py", "--method", "gibson",
                            "--parts", str(a), str(b), "--overlap", "12",
                            "--topology", "linear", "--out", str(out), "--json")
        payload = json.loads(completed.stdout)["data"]
        self.assertEqual(payload["product_sequence"], "AAAA" + "C" * 12 + "GGGG")
        self.assertEqual(payload["topology"], "linear")
        self.assertTrue(out.exists())

    def test_gibson_cli_failures(self):
        a = write_fa("AAAA" + "C" * 12, self.dir, "a.fa")
        b = write_fa("G" * 12 + "AAAA", self.dir, "b.fa")
        out = self.dir / "p.gb"
        completed = run_cli("simulate_cloning.py", "--method", "gibson",
                            "--parts", str(a), str(b), "--overlap", "12",
                            "--out", str(out), "--json", expect_fail=True)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["error"]["code"], "OVERLAP_MISMATCH")
        self.assertFalse(out.exists())
        run_cli("simulate_cloning.py", "--method", "gibson",
                "--parts", str(a), "--overlap", "12", "--json", expect_fail=True)
        run_cli("simulate_cloning.py", "--method", "gibson",
                "--parts", str(a), str(b), "--overlap", "0", "--json",
                expect_fail=True)

    def test_circular_gibson_cli_origins(self):
        a = write_fa("A" * 12 + "C" * 12, self.dir, "ca.fa")
        b = write_fa("C" * 12 + "A" * 12, self.dir, "cb.fa")
        completed = run_cli("simulate_cloning.py", "--method", "gibson",
                            "--parts", str(a), str(b), "--overlap", "12",
                            "--topology", "circular", "--json")
        payload = json.loads(completed.stdout)["data"]
        self.assertEqual(payload["product_sequence"], "C" * 12 + "A" * 12)
        self.assertEqual(
            sum(o["length"] for o in payload["origins"]),
            payload["product_length"])
        self.assertTrue(payload["origins"][0]["source_mappings"][0]["wraps_origin"])
        self.assertFalse(payload["origins"][1]["source_mappings"][0]["wraps_origin"])

    def test_digest_ligate_cli(self):
        vector = write_gb(
            record("AAA" + "GAATTC" + "CCCCGGGG" + "TTT", "v", circular=True),
            self.dir, "v.gb")
        insert = write_gb(
            record("TTT" + "GAATTC" + "ACGTACGT" + "GAATTC" + "GGG", "i"),
            self.dir, "i.gb")
        out = self.dir / "p.gb"
        completed = run_cli("simulate_cloning.py", "--method", "digest-ligate",
                            "--vector", str(vector), "--insert", str(insert),
                            "--enzyme", "EcoRI", "--out", str(out), "--json")
        payload = json.loads(completed.stdout)["data"]
        self.assertEqual(payload["topology"], "circular")
        self.assertTrue(payload["experimental"])
        self.assertTrue(out.exists())
        # vector with two sites -> SITE_COUNT
        bad = write_gb(
            record("AAA" + "GAATTC" + "CCCC" + "GAATTC" + "TTT", "v2",
                   circular=True), self.dir, "v2.gb")
        run_cli("simulate_cloning.py", "--method", "digest-ligate",
                "--vector", str(bad), "--insert", str(insert),
                "--enzyme", "EcoRI", "--json", expect_fail=True)
        # linear vector -> INVALID_TOPOLOGY
        linear_v = write_gb(
            record("AAA" + "GAATTC" + "TTT", "v3"), self.dir, "v3.gb")
        run_cli("simulate_cloning.py", "--method", "digest-ligate",
                "--vector", str(linear_v), "--insert", str(insert),
                "--enzyme", "EcoRI", "--json", expect_fail=True)
        run_cli("simulate_cloning.py", "--method", "digest-ligate",
                "--json", expect_fail=True)


class AdvancedCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="advcli-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def test_infusion_cli(self):
        a = write_fa("CCCC" + "A" * 15, self.dir, "a.fa")
        b = write_fa("A" * 15 + "GGGG", self.dir, "b.fa")
        completed = run_cli("simulate_advanced.py", "--method", "infusion",
                            "--parts", str(a), str(b), "--overlap", "15", "--json")
        payload = json.loads(completed.stdout)["data"]
        self.assertTrue(payload["experimental"])
        self.assertEqual(payload["product_sequence"], "CCCC" + "A" * 15 + "GGGG")
        bad_b = write_fa("T" * 15 + "GGGG", self.dir, "bad.fa")
        run_cli("simulate_advanced.py", "--method", "infusion",
                "--parts", str(a), str(bad_b), "--overlap", "15", "--json",
                expect_fail=True)

    def test_ta_cli(self):
        vector = write_fa("A" * 30, self.dir, "tv.fa")
        insert = write_fa("G" * 10, self.dir, "ti.fa")
        out = self.dir / "p.gb"
        completed = run_cli("simulate_advanced.py", "--method", "ta",
                            "--vector", str(vector), "--insert", str(insert),
                            "--vector-cut", "10", "--vector-end", "t-tailed",
                            "--insert-end", "a-tailed", "--out", str(out),
                            "--allow-experimental-output", "--json")
        payload = json.loads(completed.stdout)["data"]
        self.assertEqual(len(payload["product_sequence"]), 40)
        # missing cut
        run_cli("simulate_advanced.py", "--method", "ta",
                "--vector", str(vector), "--insert", str(insert),
                "--vector-end", "t-tailed", "--insert-end", "a-tailed",
                "--json", expect_fail=True)
        # wrong end premises
        run_cli("simulate_advanced.py", "--method", "ta",
                "--vector", str(vector), "--insert", str(insert),
                "--vector-cut", "10", "--vector-end", "blunt",
                "--insert-end", "a-tailed", "--json", expect_fail=True)

    def test_gateway_cli(self):
        donor = write_gb(
            record(simulate_advanced.ATTP1 + "A" * 20
                   + str(Seq(simulate_advanced.ATTP2).reverse_complement()),
                   "donor", circular=True), self.dir, "donor.gb")
        insert = write_gb(
            record(simulate_advanced.ATTB1 + "CCCCCCCC" + simulate_advanced.ATTB2,
                   "insert"), self.dir, "ins.gb")
        completed = run_cli("simulate_advanced.py", "--method", "gateway-bp",
                            "--vector", str(donor), "--insert", str(insert),
                            "--json")
        payload = json.loads(completed.stdout)["data"]
        self.assertTrue(payload["product_sequence"].startswith(
            simulate_advanced.ATTL1))
        run_cli("simulate_advanced.py", "--method", "gateway-lr",
                "--json", expect_fail=True)
        run_cli("simulate_advanced.py", "--method", "gateway-bp",
                "--json", expect_fail=True)


class GoldenGateCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ggcli-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    @staticmethod
    def _gg_record(name, left, right, circular=False):
        seq = ("GGTCTC" + "A" + left + "A" * 30 + right + "A" + "GAGACC")
        return record(seq, name, circular=circular)

    def test_cli_success_with_reverse_insert(self):
        vector = write_gb(self._gg_record("v", "AAAA", "TTTT", circular=True),
                          self.dir, "v.gb")
        ins1 = write_gb(self._gg_record("i1", "TTTT", "CCCC"), self.dir, "i1.gb")
        ins2 = write_gb(self._gg_record("i2", "CCCC", "AAAA"), self.dir, "i2.gb")
        out = self.dir / "p.gb"
        completed = run_cli("golden_gate.py", "--parts", str(vector),
                            str(ins1), str(ins2), "--enzyme", "BsaI",
                            "--out", str(out), "--json")
        payload = json.loads(completed.stdout)["data"]
        self.assertEqual(payload["topology"], "circular")
        self.assertEqual(len(payload["parts"]), 3)
        self.assertTrue(out.exists())

    def test_cli_failures(self):
        vector = write_gb(self._gg_record("v", "AAAA", "TTTT", circular=True),
                          self.dir, "v.gb")
        bad = write_gb(self._gg_record("i", "GGGG", "CCCC"), self.dir, "bad.gb")
        out = self.dir / "p.gb"
        run_cli("golden_gate.py", "--parts", str(vector), str(bad),
                "--enzyme", "BsaI", "--out", str(out), "--json", expect_fail=True)
        self.assertFalse(out.exists())
        run_cli("golden_gate.py", "--parts", str(vector), "--enzyme", "BsaI",
                "--vector", "5", "--json", expect_fail=True)
        run_cli("golden_gate.py", "--parts", str(vector), "--enzyme", "BsaI",
                "--reverse", "5", "--json", expect_fail=True)
        linear = write_gb(self._gg_record("lin", "AAAA", "TTTT"), self.dir,
                          "lin.gb")
        run_cli("golden_gate.py", "--parts", str(linear), "--enzyme", "BsaI",
                "--json", expect_fail=True)


class WriteDnaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="writedna-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def test_attach_features_and_annotations(self):
        features = [{"type": "CDS", "name": "cds1", "start": 1, "end": 9,
                     "strand": -1}]
        path = self.dir / "feats.json"
        path.write_text(json.dumps(features), encoding="utf-8")
        rec = record("AAAACCCCGGGG")
        out = write_dna.attach_features(rec, str(path))
        self.assertEqual(len(out.features), 1)
        self.assertEqual(out.features[0].location.strand, -1)

        rec = record("AAAACCCC")
        rec.annotations.pop("topology", None)
        write_dna._ensure_annotations(rec)
        self.assertEqual(rec.annotations["topology"], "linear")
        snap = write_dna._snapgene_annotated(record("AAAACCCC"))
        self.assertEqual(snap.name, "Exported")
        self.assertTrue(snap.annotations["references"])

    def test_write_native_dna_with_primers_and_compound(self):
        primer = SeqFeature(FeatureLocation(0, 5, strand=1), type="primer_bind",
                            qualifiers={"label": ["p1"]})
        compound = SeqFeature(
            CompoundLocation([FeatureLocation(10, 14, strand=1),
                              FeatureLocation(0, 2, strand=1)]),
            type="misc_feature", qualifiers={"label": ["cross"]})
        rec = record("AAAACCCCGGGGTTTT", "p", circular=True,
                     features=[primer, compound])
        out = self.dir / "p.dna"
        write_dna.write_native_dna(rec, str(out))
        self.assertTrue(out.exists())

    def test_cli_all_formats(self):
        rec = record("AAAACCCCGGGG", "p")
        src = write_gb(rec, self.dir, "p.gb")
        for fmt in ("genbank", "snapgene-gb", "dna", "fasta"):
            out = self.dir / ("out." + ("gb" if fmt != "dna" and fmt != "fasta"
                                        else ("dna" if fmt == "dna" else "fa")))
            completed = run_cli("write_dna.py", str(src), "--out", str(out),
                                "--format", fmt, "--json")
            payload = json.loads(completed.stdout)["data"]
            self.assertEqual(payload["length"], 12)
            self.assertTrue(out.exists())
        feats = self.dir / "feats.json"
        feats.write_text(json.dumps([{"type": "gene", "name": "g",
                                      "start": 1, "end": 4}]), encoding="utf-8")
        out = self.dir / "withfeat.gb"
        run_cli("write_dna.py", str(src), "--out", str(out),
                "--format", "genbank", "--features-json", str(feats),
                "--name", "renamed", "--json")
        reread = SeqIO.read(str(out), "genbank")
        self.assertEqual(len(reread.features), 1)


class RoundTripEdgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="rtedge-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def test_compare_records_qualifier_differences(self):
        expected = record("AAAACCCCGGGG", features=[
            SeqFeature(FeatureLocation(0, 6, strand=1), type="CDS",
                       qualifiers={"label": ["cds"], "translation": ["MA"],
                                   "note": ["a"]})])
        observed = record("AAAACCCCGGGG", features=[
            SeqFeature(FeatureLocation(0, 6, strand=1), type="CDS",
                       qualifiers={"label": ["cds"], "gene": ["g"],
                                   "note": ["b"]})])
        comparison = validate_roundtrip.compare_records(expected, observed)
        self.assertTrue(comparison["passed"])
        self.assertFalse(comparison["qualifiers_equal"])
        self.assertEqual(comparison["qualifier_risk"], "important")
        diffs = comparison["qualifier_differences"]
        self.assertTrue(any("translation" in d.get("missing_keys", [])
                            for d in diffs))

    def test_missing_and_unexpected_features(self):
        expected = record("AAAACCCC", features=[label_feature(0, 4, "a")])
        observed = record("AAAACCCC", features=[label_feature(2, 6, "b")])
        comparison = validate_roundtrip.compare_records(expected, observed)
        self.assertFalse(comparison["passed"])
        self.assertTrue(any(d.get("missing_feature") for d in
                            comparison["qualifier_differences"]))
        self.assertTrue(any(d.get("unexpected_feature") for d in
                            comparison["qualifier_differences"]))

    def test_sequence_and_topology_mismatch(self):
        expected = record("AAAACCCC", circular=True)
        observed = record("AAAACCCT", circular=False)
        comparison = validate_roundtrip.compare_records(expected, observed)
        self.assertFalse(comparison["sequence_equal"])
        self.assertFalse(comparison["topology_equal"])
        self.assertFalse(comparison["passed"])

    def test_require_snapgene_without_executable_fails(self):
        if not FIXTURES.is_dir():
            self.skipTest("rich fixtures not present")
        fixture = FIXTURES / "rich_fwd_cds.gb"
        result = validate_roundtrip.validate(
            str(fixture), "snapgene-gb", snapgene_exe=None,
            require_snapgene=True, strict=True)
        self.assertFalse(result["passed"])
        self.assertEqual(
            result["official_snapgene_roundtrip"]["status"],
            "required_but_missing")

    def test_cli_json_envelope(self):
        if not FIXTURES.is_dir():
            self.skipTest("rich fixtures not present")
        fixture = FIXTURES / "rich_fwd_cds.gb"
        completed = run_cli("validate_roundtrip.py", str(fixture),
                            "--format", "snapgene-gb", "--json")
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["data"]["passed"])


class V06FeatureTests(unittest.TestCase):
    """v0.6 features: Gibson primer mode, gene replacement, design report."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v06feat-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def _template(self):
        seq = "A" * 50 + "ATGAAACCCGGGTAA" + "T" * 50
        rec = record(seq, "tmpl")
        rec.features.append(SeqFeature(
            FeatureLocation(50, 65, strand=1), type="CDS",
            qualifiers={"label": ["cdc15"], "gene": ["cdc15"]}))
        return rec

    def test_design_primers_gibson_mode(self):
        import design_primers
        template = write_gb(self._template(), self.dir, "t.gb")
        completed = run_cli(
            "design_primers.py", str(template), "--start", "51", "--end", "100",
            "--gibson", "--fwd-overlap", "ACGTACGTACGT",
            "--rev-overlap", "TGCATGCATGCA", "--json", "--consent", "auto")
        payload = json.loads(completed.stdout)["data"]
        self.assertEqual(payload["method"], "gibson")
        fwd = payload["forward"]
        self.assertTrue(fwd["sequence"].startswith("ACGTACGTACGT"))
        self.assertEqual(fwd["overlap"], "ACGTACGTACGT")
        self.assertEqual(fwd["overlap_length"], 12)
        self.assertTrue(fwd["binding"])
        rev = payload["reverse"]
        self.assertEqual(rev["overlap_tail"],
                         str(Seq("TGCATGCATGCA").reverse_complement()))
        # QC is computed on binding regions only.
        self.assertIn("quality", payload)
        # non-Gibson run keeps the legacy fields
        completed = run_cli(
            "design_primers.py", str(template), "--start", "51", "--end", "100",
            "--json", "--consent", "auto")
        payload = json.loads(completed.stdout)["data"]
        self.assertEqual(payload["method"], "pcr")
        self.assertIn("binding", payload["forward"])
        # gibson without overlaps fails
        run_cli("design_primers.py", str(template), "--gibson",
                "--json", expect_fail=True)
        # unknown site fails
        run_cli("design_primers.py", str(template), "--fwd-site", "NoSuchEnzyme",
                "--json", expect_fail=True)

    def test_design_gene_replacement_core(self):
        import design_gene_replacement as dgr
        rec = self._template()
        design = dgr.design_replacement(
            rec, "ATGAAAAAGGGGCCCAAATGA", flank=20,
            gene="cdc15")
        self.assertEqual(design["target"]["start"], 51)
        self.assertEqual(design["target"]["end"], 65)
        self.assertEqual(design["homology_arms"]["upstream_length"], 20)
        self.assertEqual(design["homology_arms"]["downstream_length"], 20)
        self.assertTrue(design["primers"]["forward"]["sequence"].startswith(
            design["homology_arms"]["upstream"]))
        self.assertEqual(design["primers"]["forward"]["overlap"],
                         design["homology_arms"]["upstream"])
        self.assertEqual(design["primers"]["reverse"]["overlap_tail"],
                         str(Seq(design["homology_arms"]["downstream"])
                             .reverse_complement()))
        self.assertEqual(design["qc"]["starts_with_atg"], True)
        self.assertEqual(design["qc"]["ends_with_stop"], True)
        cassette = (design["homology_arms"]["upstream"]
                    + design["replacement"]["sequence"]
                    + design["homology_arms"]["downstream"])
        self.assertEqual(design["cassette"]["sequence"], cassette)

    def test_design_gene_replacement_qc_risks_and_region(self):
        import design_gene_replacement as dgr
        rec = self._template()
        design = dgr.design_replacement(
            rec, "AAAAACCCGGG", flank=20, gene="cdc15")
        risk_text = " ".join(design["qc"]["risks"])
        self.assertIn("ATG", risk_text)
        self.assertIn("stop", risk_text)
        self.assertIn("multiple of 3", risk_text)
        design2 = dgr.design_replacement(
            rec, "ATGAAAAAGGGGCCCAAATGA", flank=20, region=(51, 65))
        self.assertEqual(design2["target"]["gene"], "region 51..65")
        with self.assertRaises(ValueError):
            dgr.design_replacement(rec, "ATG", flank=200, gene="cdc15")

    def test_design_gene_replacement_cli(self):
        import design_gene_replacement as dgr
        template = write_gb(self._template(), self.dir, "t.gb")
        rep = write_fa("ATGAAAAAGGGGCCCAAATGA", self.dir, "rep.fa")
        out = self.dir / "product.gb"
        design_json = self.dir / "design.json"
        completed = run_cli(
            "design_gene_replacement.py", "--template", str(template),
            "--target-gene", "cdc15", "--replacement", str(rep),
            "--flank-len", "20", "--out", str(out),
            "--design-json", str(design_json), "--json",
            "--host-species", "Saccharomyces cerevisiae",
            "--strain", "S288C", "--locus", "cdc15",
            "--ploidy", "haploid", "--essentiality-status", "nonessential",
            "--essentiality-evidence", "user-provided test record",
            "--not-complemented", "--complementation-strategy",
            "not-required-nonessential")
        payload = json.loads(completed.stdout)["data"]
        self.assertEqual(payload["product_length"], 50 + 21 + 50)
        self.assertTrue(out.exists())
        self.assertTrue(design_json.exists())
        # missing target gene fails
        run_cli("design_gene_replacement.py", "--template", str(template),
                "--target-gene", "nosuchgene", "--replacement", str(rep),
                "--json", expect_fail=True)
        # missing args fail
        run_cli("design_gene_replacement.py", "--template", str(template),
                "--replacement", str(rep), "--json", expect_fail=True)

    def test_generate_design_report(self):
        import generate_design_report as gdr
        template = write_gb(self._template(), self.dir, "t.gb")
        rep = write_fa("ATGAAAAAGGGGCCCAAATGA", self.dir, "rep.fa")
        design_json = self.dir / "design.json"
        run_cli("design_gene_replacement.py", "--template", str(template),
                "--target-gene", "cdc15", "--replacement", str(rep),
                "--flank-len", "20", "--design-json", str(design_json), "--json")
        report = gdr.build_report(
            "test report", [design_json], [], [template])
        self.assertEqual(report["summary"]["designs"], 2)
        self.assertEqual(report["summary"]["primers"], 2)
        self.assertEqual(report["summary"]["product_count"], 1)
        html_text = gdr.render_html(report)
        self.assertIn("<table>", html_text)
        self.assertIn("cdc15", html_text)
        # CLI smoke: needs at least one input
        run_cli("generate_design_report.py", "--json", expect_fail=True)
        out_html = self.dir / "r.html"
        out_json = self.dir / "r.json"
        completed = run_cli(
            "generate_design_report.py", "--title", "t",
            "--design-json", str(design_json),
            "--out", str(out_html), "--report-json", str(out_json), "--json")
        payload = json.loads(completed.stdout)["data"]
        self.assertTrue(out_html.exists())
        self.assertTrue(out_json.exists())
        self.assertEqual(payload["summary"]["primers"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
