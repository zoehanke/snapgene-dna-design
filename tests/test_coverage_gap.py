# -*- coding: utf-8 -*-
"""Coverage-gap tests: drive the remaining branches of the core modules.

These tests target specific lines/branches that the main suite does not
reach (error guards, fallback paths, human-readable CLI output, and the
official-SnapGene round-trip code path exercised through mocks). They are
synthetic and safe for both release packages.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "fixtures" / "rich"
sys.path.insert(0, str(SCRIPTS))

import assembly_model  # noqa: E402
import golden_gate  # noqa: E402
import simulate_advanced  # noqa: E402
import simulate_cloning  # noqa: E402
import validate_construct  # noqa: E402
import validate_roundtrip  # noqa: E402
import sg_common  # noqa: E402
from assembly_model import (  # noqa: E402
    AssemblyError, AssemblyFragment, check_gibson_overlaps,
    check_sticky_junctions, compatible_sticky, overhang_end,
    validate_unique_contributions,
)
from simulate_cloning import _merge_parts_in_biological_order, _shift_features


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


def write_gb(rec, directory, name):
    path = pathlib.Path(directory) / name
    with open(path, "w", encoding="utf-8") as handle:
        SeqIO.write(rec, handle, "genbank")
    return path


class SgCommonGapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sg-gap-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def test_jprint_warnings_none(self):
        import io
        from contextlib import redirect_stdout
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            sg_common.jprint({"warnings": None})
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["warnings"], [])

    def test_jfail_without_warnings(self):
        import io
        from contextlib import redirect_stdout
        buffer = io.StringIO()
        with self.assertRaises(SystemExit):
            with redirect_stdout(buffer):
                sg_common.jfail("CODE", "msg")
        self.assertFalse(json.loads(buffer.getvalue())["ok"])

    def test_read_one_latin1_fallback(self):
        # Build a standards-compliant GenBank file, then re-encode it as
        # latin-1 so the UTF-8 decode path fails and the latin-1 fallback is
        # exercised (the LOCUS line itself stays Biopython-standard).
        path = self.dir / "latin.gb"
        rec = record("AAAA", "x")
        rec.features.append(SeqFeature(
            FeatureLocation(0, 4, strand=1), type="misc_feature",
            qualifiers={"note": ["café"]}))
        utf8_path = self.dir / "latin_utf8.gb"
        with open(utf8_path, "w", encoding="utf-8") as handle:
            SeqIO.write(rec, handle, "genbank")
        text = utf8_path.read_text(encoding="utf-8")
        path.write_bytes(text.encode("latin-1"))
        rec2 = sg_common._read_one(str(path), "genbank")
        self.assertEqual(rec2.features[0].qualifiers["note"], ["café"])

    def test_load_seq_dna_fallback_failure(self):
        path = self.dir / "broken.dna"
        path.write_bytes(b"not a snapgene file at all")
        with self.assertRaises(ValueError):
            sg_common.load_seq(str(path))

    def test_load_seq_unknown_extension_and_embl(self):
        fasta = self.dir / "seq.xyz"
        fasta.write_text(">x\nACGTACGT\n", encoding="utf-8")
        rec, fmt = sg_common.load_seq(str(fasta))
        self.assertEqual(fmt, "fasta")
        embl = self.dir / "seq.embl"
        with open(embl, "w", encoding="utf-8") as handle:
            SeqIO.write(record("AAAACCCC", "e"), handle, "embl")
        rec, fmt = sg_common.load_seq(str(embl))
        self.assertEqual(fmt, "embl")

    def test_gc_percent_import_fallback(self):
        with mock.patch("Bio.SeqUtils.gc_fraction", side_effect=ImportError):
            self.assertAlmostEqual(sg_common.gc_percent("GCGCAT"), 2 / 3 * 100)

    def test_enzyme_sites_exception_fallback(self):
        eco = sg_common.get_enzyme("EcoRI")
        with mock.patch.object(eco, "search", side_effect=Exception("boom")):
            self.assertEqual(sg_common.enzyme_sites("GGAATTCC", eco), [])

    def test_load_seq_raw_with_spaces_and_unnormalized(self):
        rec, fmt = sg_common.load_seq("  a c g t  ")
        self.assertEqual(str(rec.seq), "ACGT")
        self.assertEqual(fmt, "raw")


class AssemblyModelGapTests(unittest.TestCase):
    def _frag(self, name, seq, left="", right="", topology="linear"):
        return assembly_model.gibson_fragment(name, seq, left, right, topology)

    def test_end_validation_errors(self):
        with self.assertRaises(ValueError):
            assembly_model.FragmentEnd("sticky")
        with self.assertRaises(ValueError):
            assembly_model.FragmentEnd("blunt", overhang_sequence="A")
        with self.assertRaises(ValueError):
            assembly_model.FragmentEnd("5'-overhang")
        with self.assertRaises(ValueError):
            AssemblyFragment("x", "ACGT", topology="torus")
        with self.assertRaises(ValueError):
            AssemblyFragment("x", "ACGT",
                             left_end=assembly_model.FragmentEnd(
                                 "blunt", cut_boundary=99))

    def test_product_shorter_than_overlap(self):
        f1 = self._frag("a", "AA" + "CCCCC")
        f2 = self._frag("b", "CCCCC" + "AA")
        with self.assertRaises(AssemblyError) as ctx:
            validate_unique_contributions([f1, f2], 5, circular=True)
        self.assertEqual(ctx.exception.code, "PRODUCT_SHORTER_THAN_OVERLAP")

    def test_check_gibson_overlaps_errors(self):
        f1 = self._frag("a", "AAAACCCC")
        f2 = self._frag("b", "CCCCGGGG")
        with self.assertRaises(AssemblyError) as ctx:
            check_gibson_overlaps([f1, f2], 0)
        self.assertEqual(ctx.exception.code, "INVALID_OVERLAP")
        with self.assertRaises(AssemblyError) as ctx:
            check_gibson_overlaps([f1], 4)
        self.assertEqual(ctx.exception.code, "INVALID_INPUT")

    def test_validate_origins_all_branches(self):
        base = {"name": "x", "length": 3, "start": 1, "end": 3,
                "contribution_segments": [], "source_mappings": []}
        cases = [
            (dict(base, length=2), "ORIGIN_LENGTH_MISMATCH"),
            (dict(base, length=0, start=0, end=0), "ORIGIN_COORDINATE_INVALID"),
            (dict(base, start=4, end=3), "ORIGIN_COORDINATE_INVALID"),
            (dict(base, contribution_segments=[{
                "source_start": 4, "source_end": 2,
                "product_start": 1, "product_end": 2}]),
             "SOURCE_MAPPING_INVALID"),
            (dict(base, contribution_segments=[{
                "source_start": 1, "source_end": 2,
                "product_start": 0, "product_end": 2}]),
             "ORIGIN_COORDINATE_INVALID"),
            (dict(base, source_mappings=[{
                "source_start": 1, "source_end": 2,
                "product_start": 1, "product_end": 2, "dropped": True}]),
             "SOURCE_MAPPING_INVALID"),
            (dict(base, source_mappings=[{
                "source_start": 3, "source_end": 2,
                "product_start": 1, "product_end": 2}]),
             "SOURCE_MAPPING_INVALID"),
            (dict(base, source_mappings=[{
                "source_start": 1, "source_end": 2,
                "product_start": 0, "product_end": 2}]),
             "ORIGIN_COORDINATE_INVALID"),
        ]
        for origins, code in cases:
            with self.assertRaises(AssemblyError) as ctx:
                assembly_model.validate_origins(
                    [origins], 3 if origins["length"] else 0)
            self.assertEqual(ctx.exception.code, code)
        # valid case passes
        good = dict(base)
        assembly_model.validate_origins([good], 3)

    def test_compatible_sticky_branches(self):
        left5 = overhang_end("5'-overhang", "AACC", 0)
        right_blunt = overhang_end("blunt", "", 0)
        self.assertFalse(compatible_sticky(left5, right_blunt))
        self.assertFalse(compatible_sticky(left5, overhang_end("5'-overhang", "AA", 0)))
        self.assertTrue(compatible_sticky(
            overhang_end("5'-overhang", "AACC", 0),
            overhang_end("5'-overhang", "GGTT", 0)))

    def test_check_sticky_junctions_empty(self):
        self.assertEqual(check_sticky_junctions([]), [])


class CloningGapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cloning-gap-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def test_merge_parts_empty_and_single(self):
        self.assertIsNone(_merge_parts_in_biological_order([], "join"))
        loc = FeatureLocation(0, 4, strand=1)
        self.assertEqual(_merge_parts_in_biological_order([loc], "join"), loc)
        merged = _merge_parts_in_biological_order([
            FeatureLocation(0, 2, strand=1),
            FeatureLocation(2, 4, strand=1),
        ], "join")
        self.assertIsInstance(merged, FeatureLocation)
        self.assertEqual((int(merged.start), int(merged.end)), (0, 4))
        # negative-strand contiguous merge
        merged = _merge_parts_in_biological_order([
            FeatureLocation(2, 4, strand=-1),
            FeatureLocation(0, 2, strand=-1),
        ], "join")
        self.assertEqual((int(merged.start), int(merged.end)), (0, 4))

    def test_shift_features_defaults_and_simple_location(self):
        rec = record("AAAACCCC", features=[label_feature(0, 4, "f")])
        features, warnings = _shift_features(
            rec, 0, trim_start=0, circular=False, is_first=True,
            product_length=8, product_seq="AAAACCCC")
        self.assertEqual(len(features), 1)
        self.assertEqual(warnings, [])

    def test_arc_edge_cases(self):
        self.assertEqual(simulate_cloning._arc("", 0, 0), "")
        self.assertEqual(simulate_cloning._arc("ACGT", 1, 1), "")
        self.assertEqual(simulate_cloning._arc("ACGT", 3, 2), "TAC")

    def test_digest_ligate_psti_three_prime_overhang(self):
        vector = record("AAA" + "CTGCAG" + "CCCCGGGG" + "TTT", "v", circular=True)
        insert = record("TTT" + "CTGCAG" + "ACGTACGT" + "CTGCAG" + "GGG", "i")
        v = write_gb(vector, self.dir, "v.gb")
        i = write_gb(insert, self.dir, "i.gb")
        out = self.dir / "p.gb"
        run_cli("simulate_cloning.py", "--method", "digest-ligate",
                "--vector", str(v), "--insert", str(i), "--enzyme", "PstI",
                "--out", str(out), "--json")
        self.assertTrue(out.exists())

    def test_insert_excision_failed_guard(self):
        vector = record("AAA" + "GAATTC" + "CCCC" + "TTT", "v", circular=True)
        insert = record("TTT" + "GAATTC" + "ACGT" + "GAATTC" + "GGG", "i")
        with mock.patch("simulate_cloning._arc", return_value="GAATTC"):
            with self.assertRaises(AssemblyError) as ctx:
                simulate_cloning.digest_ligate(vector, insert, "EcoRI")
        self.assertEqual(ctx.exception.code, "INSERT_EXCISION_FAILED")

    def test_sticky_end_mismatch_guard(self):
        vector = record("AAA" + "GAATTC" + "CCCC" + "TTT", "v", circular=True)
        insert = record("TTT" + "GAATTC" + "ACGT" + "GAATTC" + "GGG", "i")
        fake = [{"between": "v->i", "compatibility": "MISMATCH"}]
        with mock.patch("simulate_cloning.check_sticky_junctions",
                        return_value=fake):
            with self.assertRaises(AssemblyError) as ctx:
                simulate_cloning.digest_ligate(vector, insert, "EcoRI")
        self.assertEqual(ctx.exception.code, "STICKY_END_MISMATCH")

    def test_cli_human_output_and_invalid_input(self):
        a = self.dir / "a.fa"
        b = self.dir / "b.fa"
        overlap = "ACGTACGTACGT"
        a.write_text(">a\nAAAA" + overlap + "\n")
        b.write_text(">b\n" + overlap + "GGGG\n")
        run_cli("simulate_cloning.py", "--method", "gibson",
                "--parts", str(a), str(b), "--overlap", "12")
        corrupt = self.dir / "corrupt.gb"
        corrupt.write_text("this is not a genbank file\n", encoding="utf-8")
        run_cli("simulate_cloning.py", "--method", "gibson",
                "--parts", str(corrupt), str(b), "--overlap", "12", "--json",
                expect_fail=True)
        # non-json human output for digest-ligate
        v = write_gb(record("AAA" + "GAATTC" + "CCCC" + "TTT", "v", circular=True),
                     self.dir, "v.gb")
        i = write_gb(record("TTT" + "GAATTC" + "ACGT" + "GAATTC" + "GGG", "i"),
                     self.dir, "i.gb")
        run_cli("simulate_cloning.py", "--method", "digest-ligate",
                "--vector", str(v), "--insert", str(i), "--enzyme", "EcoRI")


def label_feature(start, end, label, strand=1, ftype="misc_feature"):
    return SeqFeature(FeatureLocation(start, end, strand=strand), type=ftype,
                      qualifiers={"label": [label]})


class AdvancedGapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="adv-gap-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def test_ta_sticky_mismatch_guard(self):
        vector = record("A" * 30, "v", circular=True)
        insert = record("G" * 10, "i")
        fake = [{"between": "v->i", "compatibility": "MISMATCH"}]
        with mock.patch("simulate_advanced.check_sticky_junctions",
                        return_value=fake):
            with self.assertRaises(AssemblyError) as ctx:
                simulate_advanced.ta_topo_clone(vector, insert, 5, method="ta")
        self.assertEqual(ctx.exception.code, "STICKY_END_MISMATCH")

    def test_gateway_feature_migration_compound(self):
        compound = SeqFeature(
            CompoundLocation([FeatureLocation(26, 29, strand=1),
                              FeatureLocation(30, 32, strand=1)]),
            type="misc_feature", qualifiers={"label": ["ins_feat"]})
        insert = record(simulate_advanced.ATTB1 + "AAACCCGGGTTT"
                        + simulate_advanced.ATTB2,
                        "ins", features=[compound])
        donor = record(simulate_advanced.ATTP1 + "A" * 20
                       + str(Seq(simulate_advanced.ATTP2).reverse_complement()),
                       "donor", circular=True)
        product, body, notes = simulate_advanced.gateway_bp(donor, insert)
        self.assertEqual(len(body), 12)
        labels = {f.qualifiers.get("label", [""])[0] for f in product.features}
        self.assertIn("ins_feat", labels)

    def test_replace_with_features_wrapped_rejected(self):
        donor = record("AAAACCCC", "d", circular=True)
        with self.assertRaises(AssemblyError) as ctx:
            simulate_advanced._replace_with_features(donor, 5, 2, "AA", [])
        self.assertEqual(ctx.exception.code, "ATT_SITE_ORDER")

    def test_cli_missing_args_and_human_output(self):
        run_cli("simulate_advanced.py", "--method", "infusion", "--json",
                expect_fail=True)
        a = self.dir / "a.fa"
        b = self.dir / "b.fa"
        a.write_text(">a\nCCCC" + "A" * 15 + "\n")
        b.write_text(">b\n" + "A" * 15 + "GGGG\n")
        run_cli("simulate_advanced.py", "--method", "infusion",
                "--parts", str(a), str(b), "--overlap", "15")
        run_cli("simulate_advanced.py", "--method", "ta", "--json",
                expect_fail=True)
        corrupt = self.dir / "corrupt.gb"
        corrupt.write_text("not genbank\n", encoding="utf-8")
        run_cli("simulate_advanced.py", "--method", "infusion",
                "--parts", str(corrupt), str(b), "--overlap", "15", "--json",
                expect_fail=True)
        vector = self.dir / "v.fa"
        vector.write_text(">v\n" + "A" * 30 + "\n")
        run_cli("simulate_advanced.py", "--method", "ta",
                "--vector", str(vector), "--insert", str(a),
                "--vector-cut", "5", "--vector-end", "t-tailed",
                "--insert-end", "a-tailed")


class GoldenGateGapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gg-gap-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def test_arc_and_contains_recognition(self):
        self.assertEqual(golden_gate._arc("ACGT", 2, 2), "")
        self.assertEqual(golden_gate._arc("", 0, 0), "")
        self.assertTrue(golden_gate._contains_recognition("AAGAGACCT", sg_common.get_enzyme("BsaI")))
        self.assertFalse(golden_gate._contains_recognition("AAAAAAAAAA", sg_common.get_enzyme("BsaI")))

    def test_part_fragment_wrap_rejection(self):
        # Forward site with a clean wrap-only candidate (linear -> rejected).
        seq = "AAA" + "GGTCTC" + "A" * 7
        rec = record(seq, "lin")
        fake_hits = [
            {"strand": 1, "top_cut_boundary_0based": 3,
             "bottom_cut_boundary_0based": 7, "cuts_within_sequence": True},
            {"strand": 1, "top_cut_boundary_0based": 16,
             "bottom_cut_boundary_0based": 20, "cuts_within_sequence": True},
        ]
        with mock.patch("golden_gate.restriction_hits", return_value=fake_hits):
            info = golden_gate.part_fragment(rec, sg_common.get_enzyme("BsaI"))
        self.assertFalse(info["ok"])
        self.assertIn("wrap-around", info["reason"])

    def test_part_fragment_fragment_shorter_than_overhang(self):
        rec = record("AAAACCCCGGGGTTTT", "r")
        fake_hits = [
            {"strand": 1, "top_cut_boundary_0based": 1,
             "bottom_cut_boundary_0based": 5, "cuts_within_sequence": True},
            {"strand": 1, "top_cut_boundary_0based": 4,
             "bottom_cut_boundary_0based": 8, "cuts_within_sequence": True},
        ]
        with mock.patch("golden_gate.restriction_hits", return_value=fake_hits):
            info = golden_gate.part_fragment(rec, sg_common.get_enzyme("BsaI"))
        self.assertFalse(info["ok"])
        self.assertIn("not longer than its overhang", info["reason"])

    def test_overhang_length_mismatch_guard(self):
        vector = record("GGTCTC" + "A" * 40 + "GAGACC", "v", circular=True)
        insert = record("A" * 60, "i")
        base = {"ok": True, "fragment": "A" * 20, "left_overhang": "AAAA",
                "right_overhang": "TTTT", "overhang_length": 4,
                "top_cut_start0": 0, "top_cut_end0": 20,
                "wraps_origin": False, "topology": "circular",
                "recognition_sites": []}
        def fake_part(rec, enzyme, topology_override=None):
            info = dict(base)
            if len(str(rec.seq)) < 50:
                info["overhang_length"] = 3
                info["left_overhang"] = "AAA"
            return info
        with mock.patch("golden_gate.part_fragment", side_effect=fake_part):
            import io
            from contextlib import redirect_stdout
            with self.assertRaises(SystemExit) as ctx:
                with redirect_stdout(io.StringIO()):
                    golden_gate.assemble([vector, insert],
                                         ["v", "i"],
                                         sg_common.get_enzyme("BsaI"),
                                         vector_topology="circular")
        self.assertEqual(ctx.exception.code, 1)

    def test_reverse_insert_cli_success(self):
        def gg(name, left, right, circular=False):
            return record("GGTCTC" + "A" + left + "A" * 30 + right + "A"
                          + "GAGACC", name, circular=circular)
        v = write_gb(gg("v", "ATAT", "ATAT", circular=True), self.dir, "v.gb")
        i1 = write_gb(gg("i1", "ATAT", "ATAT"), self.dir, "i1.gb")
        i2 = write_gb(gg("i2", "ATAT", "ATAT"), self.dir, "i2.gb")
        out = self.dir / "p.gb"
        run_cli("golden_gate.py", "--parts", str(v), str(i1), str(i2),
                "--enzyme", "BsaI", "--reverse", "1", "--out", str(out), "--json")
        self.assertTrue(out.exists())

    def test_cli_invalid_input_and_human_output(self):
        v = write_gb(record("GGTCTC" + "A" * 40 + "GAGACC", "v", circular=True),
                     self.dir, "v.gb")
        i = write_gb(record("GGTCTC" + "A" * 40 + "GAGACC", "i"), self.dir, "i.gb")
        run_cli("golden_gate.py", "--parts", str(v), str(i),
                "--enzyme", "BsaX", "--json", expect_fail=True)
        run_cli("golden_gate.py", "--parts", str(v), str(i), "--enzyme", "BsaI")
        corrupt = self.dir / "bad.gb"
        corrupt.write_text("nope\n", encoding="utf-8")
        run_cli("golden_gate.py", "--parts", str(corrupt), "--enzyme", "BsaI",
                "--json", expect_fail=True)


class ValidateConstructGapTests(unittest.TestCase):
    def test_cds_translation_helper(self):
        seq = "AAATTT"
        self.assertEqual(validate_construct._cds_translation(seq, 0, 3, 1), "K")
        self.assertEqual(validate_construct._cds_translation(seq, 0, 3, -1), "F")

    def test_codon_start_and_transl_table_fallbacks(self):
        cds = SeqFeature(FeatureLocation(0, 12, strand=1), type="CDS",
                         qualifiers={"label": ["c"],
                                     "codon_start": ["not-an-int"],
                                     "transl_table": ["not-an-int"]})
        result = validate_construct.validate(record("ATGGCTAAATAA", features=[cds]))
        self.assertTrue(result["summary"]["pass"])

    def test_terminal_stop_and_multicutter_and_unknown_enzyme(self):
        cds = SeqFeature(FeatureLocation(0, 12, strand=1), type="CDS",
                         qualifiers={"label": ["ok"]})
        result = validate_construct.validate(
            record("ATGGCTAAATAA" + "GAATTC" + "GAATTC", features=[cds]))
        codes = {c["check"]: c["status"] for c in result["checks"]}
        self.assertEqual(codes["cds_frame"], "ok")
        cutters = [c for c in result["checks"]
                   if c["check"] == "unique_cutter" and c["status"] == "warning"]
        self.assertTrue(any("EcoRI" in c["detail"] for c in cutters))
        # get_enzyme failure is skipped silently
        with mock.patch("validate_construct.get_enzyme",
                        side_effect=ValueError("no")):
            result = validate_construct.validate(record("AAAACCCC"))
        self.assertTrue(result["summary"]["pass"])

    def test_cli_human_output(self):
        with tempfile.TemporaryDirectory(prefix="vc-gap-") as td:
            path = write_gb(record("ATGGCTAAATAA", "ok"), pathlib.Path(td), "ok.gb")
            run_cli("validate_construct.py", str(path))


class RoundTripGapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="rt-gap-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def test_official_convert_success_and_errors(self):
        source = self.dir / "in.gb"
        source.write_text(">x\nACGTACGT\n", encoding="utf-8")
        output = self.dir / "out.gb"
        # success: subprocess creates the output file
        def fake_run(cmd, **kwargs):
            pathlib.Path(cmd[cmd.index("--output") + 1]).write_bytes(
                b"ACGTACGT")
            completed = mock.Mock(returncode=0, stderr="", stdout="")
            return completed
        with mock.patch("validate_roundtrip.subprocess.run", side_effect=fake_run):
            validate_roundtrip._official_convert(
                "C:\\fake\\SnapGene.exe", str(source), str(output),
                "GenBank - Standard")
        self.assertTrue(output.exists())
        # non-zero returncode -> RuntimeError
        def failing_run(cmd, **kwargs):
            return mock.Mock(returncode=2, stderr="boom", stdout="")
        with mock.patch("validate_roundtrip.subprocess.run", side_effect=failing_run):
            with self.assertRaises(RuntimeError):
                validate_roundtrip._official_convert(
                    "C:\\fake\\SnapGene.exe", str(source), str(output),
                    "GenBank - Standard")
        # rc 0 but no output -> RuntimeError
        output.unlink(missing_ok=True)
        def no_output(cmd, **kwargs):
            return mock.Mock(returncode=0, stderr="", stdout="")
        with mock.patch("validate_roundtrip.subprocess.run", side_effect=no_output):
            with self.assertRaises(RuntimeError):
                validate_roundtrip._official_convert(
                    "C:\\fake\\SnapGene.exe", str(source), str(output),
                    "GenBank - Standard")

    def test_validate_with_mocked_official_snapgene(self):
        if not FIXTURES.is_dir():
            self.skipTest("rich fixtures not present")
        fixture = FIXTURES / "rich_fwd_cds.gb"
        exported = self.dir / "exported.gb"

        def fake_convert(executable, input_path, output_path, target_format):
            # Simulate an official SnapGene conversion that drops a qualifier.
            from sg_common import load_seq
            rec, _fmt = load_seq(str(input_path))
            for feature in rec.features:
                feature.qualifiers.pop("db_xref", None)
            with open(output_path, "w", encoding="utf-8") as handle:
                SeqIO.write(rec, handle, "genbank")

        with mock.patch("validate_roundtrip._find_snapgene",
                        return_value="C:\\fake\\SnapGene.exe"), \
                mock.patch("validate_roundtrip._official_convert",
                           side_effect=fake_convert):
            result = validate_roundtrip.validate(
                str(fixture), "dna", snapgene_exe="C:\\fake\\SnapGene.exe",
                require_snapgene=True, strict=True)
        self.assertEqual(result["official_snapgene_roundtrip"]["status"],
                         "completed")
        self.assertTrue(result["core_passed"])
        self.assertFalse(result["strict_passed"])
        self.assertEqual(result["delivery_grade"],
                         "core-compatible-with-important-differences")
        self.assertTrue(any("SnapGene" in w for w in result["warnings"]))

    def test_cli_failures_and_human_output(self):
        if not FIXTURES.is_dir():
            self.skipTest("rich fixtures not present")
        fixture = FIXTURES / "rich_multivalue.gb"
        run_cli("validate_roundtrip.py", str(fixture), "--format", "snapgene-gb")
        run_cli("validate_roundtrip.py", str(fixture), "--format", "dna",
                "--strict", expect_fail=True)
        run_cli("validate_roundtrip.py", str(self.dir / "missing.gb"), "--json",
                expect_fail=True)


class EditPlasmidGapTests(unittest.TestCase):
    def test_linearize_out_of_range_and_cli_error_paths(self):
        rec = record("AAAACCCCGGGG", "p", circular=True)
        import edit_plasmid
        with self.assertRaises(ValueError):
            edit_plasmid.op_linearize(rec, 99)
        with tempfile.TemporaryDirectory(prefix="ep-gap-") as td:
            src = write_gb(rec, pathlib.Path(td), "p.gb")
            out = pathlib.Path(td) / "o.gb"
            run_cli("edit_plasmid.py", str(src), "--op", "insert", "--pos", "0",
                    "--seq", "A", "--out", str(out), expect_fail=True)
            run_cli("edit_plasmid.py", str(src), "--op", "replace",
                    "--start", "0", "--end", "2", "--seq", "A",
                    "--out", str(out), expect_fail=True)
            run_cli("edit_plasmid.py", str(src), "--op", "replace",
                    "--start", "1", "--end", "2",
                    "--out", str(out), expect_fail=True)
            run_cli("edit_plasmid.py", str(src), "--op", "mutate",
                    "--mutation", "1:ZZ", "--out", str(out), expect_fail=True)
            run_cli("edit_plasmid.py", str(src), "--op", "linearize",
                    "--out", str(out), expect_fail=True)
            run_cli("edit_plasmid.py", str(src), "--op", "rotate",
                    "--pos", "99", "--out", str(out), expect_fail=True)
            run_cli("edit_plasmid.py", str(src), "--op", "circularize",
                    "--out", str(out))
            run_cli("edit_plasmid.py", str(src), "--op", "rotate",
                    "--pos", "2", "--out", str(out))
            # human-readable output
            run_cli("edit_plasmid.py", str(src), "--op", "circularize",
                    "--out", str(out))


if __name__ == "__main__":
    unittest.main(verbosity=2)
