# -*- coding: utf-8 -*-
"""v0.4 golden-fixture tests for advanced cloning simulations.

These tests use committed real-vector fixtures (see fixtures/golden/README.md)
instead of generating inputs and expected outputs from the package's own att
constants. Expected Gateway and TA products are committed GenBank files.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "fixtures"
GOLDEN = FIXTURES / "golden"
sys.path.insert(0, str(SCRIPTS))

from validate_roundtrip import compare_records  # noqa: E402


def run_script(name, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name)] + list(args),
        cwd=str(SCRIPTS), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def error_of(testcase, completed):
    testcase.assertNotEqual(completed.returncode, 0, completed.stdout + completed.stderr)
    payload = parsed(completed)
    testcase.assertFalse(payload["ok"])
    testcase.assertIn("code", payload["error"])
    testcase.assertIn("message", payload["error"])
    return payload["error"]



class EnvelopeData(dict):
    def __init__(self, data, envelope):
        super().__init__(data)
        self.envelope = envelope

    def __getitem__(self, key):
        if key in self:
            return dict.__getitem__(self, key)
        return self.envelope[key]


def parsed(completed):
    payload = json.loads(completed.stdout)
    if payload.get("data") is None:
        return payload
    return EnvelopeData(payload["data"], payload)

class FailureContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v04-")
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = pathlib.Path(self.tmp.name)

    def test_gibson_mismatch_is_structured_failure_and_writes_nothing(self):
        a = self.tmp_path / "a.fa"
        b = self.tmp_path / "b.fa"
        out = self.tmp_path / "out.gb"
        a.write_text(">a\nAAAACCCCCCCCCCCC\n")
        b.write_text(">b\nGGGGGGGGGGGGTTTT\n")
        completed = run_script(
            "simulate_cloning.py", "--method", "gibson",
            "--parts", str(a), str(b), "--overlap", "12",
            "--out", str(out), "--json")
        error = error_of(self, completed)
        self.assertEqual(error["code"], "OVERLAP_MISMATCH")
        self.assertFalse(out.exists())

    def test_infusion_mismatch_is_structured_failure(self):
        a = self.tmp_path / "a.fa"
        b = self.tmp_path / "b.fa"
        a.write_text(">a\nAAAACCCCCCCCCCCC\n")
        b.write_text(">b\nGGGGGGGGGGGGTTTT\n")
        completed = run_script(
            "simulate_advanced.py", "--method", "infusion",
            "--parts", str(a), str(b), "--overlap", "12", "--json")
        error = error_of(self, completed)
        self.assertEqual(error["code"], "OVERLAP_MISMATCH")

    def test_failure_envelope_matches_success_shape(self):
        a = self.tmp_path / "a.fa"
        b = self.tmp_path / "b.fa"
        a.write_text(">a\nAAAACCCCCCCCCCCC\n")
        b.write_text(">b\nGGGGGGGGGGGGTTTT\n")
        completed = run_script(
            "simulate_cloning.py", "--method", "gibson",
            "--parts", str(a), str(b), "--overlap", "12", "--json")
        self.assertNotEqual(completed.returncode, 0)
        payload = parsed(completed)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["schema_version"], "0.5.0")
        self.assertEqual(payload["command"], "simulate_cloning.py")
        self.assertIn("warnings", payload)
        self.assertIsNone(payload["data"])
        self.assertEqual(payload["error"]["code"], "OVERLAP_MISMATCH")

    def _featured_fragment(self, name, sequence, feature_label="feat",
                           circular=False, start=0, end=None):
        if end is None:
            end = len(sequence)
        record = SeqRecord(
            Seq(sequence), id=name, name=name,
            annotations={"molecule_type": "DNA",
                         "topology": "circular" if circular else "linear"})
        record.features.append(SeqFeature(
            FeatureLocation(start, end, strand=1), type="misc_feature",
            qualifiers={"label": [feature_label]}))
        path = self.tmp_path / (name + ".gb")
        with open(path, "w", encoding="utf-8") as handle:
            SeqIO.write(record, handle, "genbank")
        return path

    def test_linear_gibson_origins_and_feature_coordinates(self):
        overlap = "ACGTACGTACGT"
        a = self._featured_fragment("gib_a", "AAAA" + overlap, "featA")
        b = self._featured_fragment("gib_b", overlap + "GGGG", "featB",
                                    start=12, end=16)
        out = self.tmp_path / "linear.gb"
        completed = run_script(
            "simulate_cloning.py", "--method", "gibson",
            "--parts", str(a), str(b), "--overlap", "12",
            "--out", str(out), "--json")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = parsed(completed)
        self.assertEqual(payload["product_length"], 20)
        self.assertEqual(payload["origins"][0]["start"], 1)
        self.assertEqual(payload["origins"][0]["end"], 16)
        self.assertEqual(payload["origins"][1]["start"], 17)
        self.assertEqual(payload["origins"][1]["end"], 20)
        self.assertEqual(payload["origins"][-1]["end"], payload["product_length"])
        record = SeqIO.read(str(out), "genbank")
        labels = {}
        for feature in record.features:
            labels[str(feature.qualifiers["label"][0])] = (
                int(feature.location.start), int(feature.location.end))
        self.assertEqual(labels["featA"], (0, 16))
        self.assertEqual(labels["featB"], (16, 20))

    def test_linear_gibson_drops_feature_in_removed_overlap_with_warning(self):
        overlap = "ACGTACGTACGT"
        a = self._featured_fragment("gib_a2", "AAAA" + overlap, "featA")
        b = self._featured_fragment("gib_b2", overlap + "GGGG", "featB",
                                    start=0, end=8)
        completed = run_script(
            "simulate_cloning.py", "--method", "gibson",
            "--parts", str(a), str(b), "--overlap", "12", "--json")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = parsed(completed)
        self.assertTrue(any("partially dropped" in w for w in payload["warnings"]),
                        str(payload["warnings"]))
        self.assertEqual(payload["feature_count"], 1)

    def test_circular_gibson_feature_maps_across_closing_overlap(self):
        overlap = "ACGTACGTACGT"
        a = self._featured_fragment("circ_a", overlap + "AAAA" + overlap,
                                    "featA")
        b = self._featured_fragment("circ_b", overlap + "GGGG" + overlap,
                                    "featB")
        out = self.tmp_path / "circ.gb"
        completed = run_script(
            "simulate_cloning.py", "--method", "gibson",
            "--parts", str(a), str(b), "--overlap", "12",
            "--topology", "circular", "--out", str(out), "--json")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = parsed(completed)
        self.assertEqual(payload["product_sequence"], "AAAA" + overlap + "GGGG" + overlap)
        record = SeqIO.read(str(out), "genbank")
        labels = {}
        for feature in record.features:
            labels[str(feature.qualifiers["label"][0])] = (
                int(feature.location.start), int(feature.location.end))
        # A full-length feature on the first circular fragment spans the whole
        # product (the trimmed left overlap is mapped to the closing region).
        self.assertEqual(labels["featA"], (0, 32))

    def test_circular_infusion_feature_maps_across_closing_overlap(self):
        overlap = "ACGTACGTACGT"
        a = self._featured_fragment("inf_a", overlap + "AAAA" + overlap,
                                    "featA", circular=True)
        b = self._featured_fragment("inf_b", overlap + "GGGG" + overlap,
                                    "featB", circular=False)
        completed = run_script(
            "simulate_advanced.py", "--method", "infusion",
            "--parts", str(a), str(b), "--overlap", "12", "--json")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = parsed(completed)
        self.assertEqual(payload["topology"], "circular")
        self.assertEqual(payload["product_sequence"], "AAAA" + overlap + "GGGG" + overlap)
        self.assertEqual(payload["feature_count"], 2)

    def test_roundtrip_reports_and_can_require_qualifier_equality(self):
        if not (FIXTURES / "pDONR201.dna").exists():
            self.skipTest("fixtures/pDONR201.dna not present (academic-only)")
        completed = run_script(
            "validate_roundtrip.py", str(FIXTURES / "pDONR201.dna"),
            "--format", "dna", "--json")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = parsed(completed)
        self.assertTrue(payload["core_passed"])
        self.assertFalse(payload["strict_passed"])
        self.assertTrue(any("qualifiers differ" in w for w in payload["warnings"]))

        completed = run_script(
            "validate_roundtrip.py", str(FIXTURES / "pDONR201.dna"),
            "--format", "dna", "--strict", "--json")
        self.assertNotEqual(completed.returncode, 0)
        payload = parsed(completed)
        self.assertFalse(payload["ok"])
        self.assertFalse(payload["strict_passed"])

    def test_circular_gibson_validates_and_trims_closing_overlap(self):
        a = self.tmp_path / "a.fa"
        b = self.tmp_path / "b.fa"
        overlap = "ACGTACGTACGT"
        a.write_text(">a\n" + overlap + "AAAA" + overlap + "\n")
        b.write_text(">b\n" + overlap + "GGGG" + overlap + "\n")
        completed = run_script(
            "simulate_cloning.py", "--method", "gibson",
            "--parts", str(a), str(b), "--overlap", "12",
            "--topology", "circular", "--json")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = parsed(completed)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["product_length"], 32)
        self.assertEqual(payload["product_sequence"], "AAAA" + overlap + "GGGG" + overlap)
        self.assertEqual(payload["topology"], "circular")

        b.write_text(">b\nTGCATGCATGCA" + "TTTT" + overlap + "\n")
        completed = run_script(
            "simulate_cloning.py", "--method", "gibson",
            "--parts", str(a), str(b), "--overlap", "12",
            "--topology", "circular", "--json")
        error = error_of(self, completed)
        self.assertEqual(error["code"], "OVERLAP_MISMATCH")


class GoldenGatewayTests(unittest.TestCase):
    def setUp(self):
        if not (FIXTURES / "pDONR201.dna").exists() or not (GOLDEN / "attB-EmGFP.gb").exists():
            self.skipTest("Academic golden fixtures not present")
        self.tmp = tempfile.TemporaryDirectory(prefix="v04-gw-")
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = pathlib.Path(self.tmp.name)

    def test_bp_matches_committed_pENTR_EmGFP_fixture(self):
        out = self.tmp_path / "bp.gb"
        completed = run_script(
            "simulate_advanced.py", "--method", "gateway-bp",
            "--vector", str(FIXTURES / "pDONR201.dna"),
            "--insert", str(GOLDEN / "attB-EmGFP.gb"),
            "--out", str(out), "--json")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = parsed(completed)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["topology"], "circular")
        observed = SeqIO.read(str(out), "genbank")
        expected = SeqIO.read(str(GOLDEN / "pENTR-EmGFP.gb"), "genbank")
        comparison = compare_records(expected, observed)
        self.assertTrue(comparison["passed"], comparison)
        self.assertTrue(comparison["qualifiers_equal"])

    def test_lr_matches_committed_pDEST_EmGFP_fixture(self):
        out = self.tmp_path / "lr.gb"
        completed = run_script(
            "simulate_advanced.py", "--method", "gateway-lr",
            "--entry", str(GOLDEN / "pENTR-EmGFP.gb"),
            "--destination", str(GOLDEN / "pDEST40.dna"),
            "--out", str(out), "--json")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        observed = SeqIO.read(str(out), "genbank")
        expected = SeqIO.read(str(GOLDEN / "pDEST-EmGFP.gb"), "genbank")
        comparison = compare_records(expected, observed)
        self.assertTrue(comparison["passed"], comparison)
        self.assertTrue(comparison["qualifiers_equal"])

    def test_gateway_requires_explicit_topology(self):
        donor = self.tmp_path / "donor.fa"
        donor.write_text(">donor\nAAAACCCCGGGG\n")
        completed = run_script(
            "simulate_advanced.py", "--method", "gateway-bp",
            "--vector", str(donor),
            "--insert", str(GOLDEN / "attB-EmGFP.gb"), "--json")
        error = error_of(self, completed)
        self.assertEqual(error["code"], "MISSING_TOPOLOGY")

        # Real pENTR D-TOPO file is linearized: must be rejected for LR.
        completed = run_script(
            "simulate_advanced.py", "--method", "gateway-lr",
            "--entry", str(GOLDEN / "pENTR-D-TOPO.dna"),
            "--destination", str(GOLDEN / "pDEST40.dna"), "--json")
        error = error_of(self, completed)
        self.assertEqual(error["code"], "INVALID_TOPOLOGY")

    def test_gateway_rejects_misordered_att_pair_instead_of_find_first(self):
        # pENTR-D-TOPO is linear with attL1 near the end and attL2 near the
        # start. Re-annotating it circular must not make .find() silently
        # pick the first site; the pair is mis-ordered and must fail.
        record = SeqIO.read(str(GOLDEN / "pENTR-D-TOPO.dna"), "snapgene")
        record.annotations["topology"] = "circular"
        misordered = self.tmp_path / "misordered.gb"
        with open(misordered, "w", encoding="utf-8") as handle:
            SeqIO.write(record, handle, "genbank")
        completed = run_script(
            "simulate_advanced.py", "--method", "gateway-lr",
            "--entry", str(misordered),
            "--destination", str(GOLDEN / "pDEST40.dna"), "--json")
        error = error_of(self, completed)
        self.assertEqual(error["code"], "ATT_SITE_ORDER")

    def test_gateway_duplicate_att_site_is_rejected(self):
        entry = SeqIO.read(str(GOLDEN / "pENTR-EmGFP.gb"), "genbank")
        # duplicate the attL1 feature sequence once, then shrink it so the
        # duplicated region remains a valid circular record
        seq = str(entry.seq)
        attl1 = next(
            str(f.extract(entry.seq))
            for f in entry.features
            if "attL1" in str(f.qualifiers.get("label", ""))
        )
        duplicated = SeqRecord(
            Seq(seq + attl1), id="dup", name="dup",
            annotations={"molecule_type": "DNA", "topology": "circular"})
        dup_file = self.tmp_path / "dup.gb"
        with open(dup_file, "w", encoding="utf-8") as handle:
            SeqIO.write(duplicated, handle, "genbank")
        completed = run_script(
            "simulate_advanced.py", "--method", "gateway-lr",
            "--entry", str(dup_file),
            "--destination", str(GOLDEN / "pDEST40.dna"), "--json")
        error = error_of(self, completed)
        self.assertEqual(error["code"], "ATT_SITE_NOT_UNIQUE")


class DigestLigateEndModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v04-digest-")
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = pathlib.Path(self.tmp.name)

    def _write_gb(self, name, sequence, circular=True):
        path = self.tmp_path / name
        record = SeqRecord(
            Seq(sequence), id=name, name=name,
            annotations={"molecule_type": "DNA",
                         "topology": "circular" if circular else "linear"})
        with open(path, "w", encoding="utf-8") as handle:
            SeqIO.write(record, handle, "genbank")
        return path

    def _run_digest(self, enzyme):
        vector = self._write_gb(
            enzyme + "_vector.gb", "AAAA" + enzyme_site(enzyme) + "CCCC")
        insert = self._write_gb(
            enzyme + "_insert.gb",
            enzyme_site(enzyme) + "TTTT" + enzyme_site(enzyme), circular=False)
        return run_script(
            "simulate_cloning.py", "--method", "digest-ligate",
            "--vector", str(vector), "--insert", str(insert),
            "--enzyme", enzyme, "--json")

    def test_ecori_psti_smai_end_kinds_and_linear_vector_fragment(self):
        expected = {"EcoRI": "5'-overhang", "PstI": "3'-overhang", "SmaI": "blunt"}
        for enzyme, kind in expected.items():
            completed = self._run_digest(enzyme)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            payload = parsed(completed)
            self.assertTrue(payload["ok"])
            vector_frag = payload["fragments"][0]
            insert_frag = payload["fragments"][1]
            self.assertEqual(vector_frag["topology"], "linear")
            self.assertEqual(payload["topology"], "circular")
            self.assertEqual(vector_frag["left_end"]["kind"], kind)
            self.assertEqual(insert_frag["left_end"]["kind"], kind)
            if kind != "blunt":
                self.assertEqual(
                    len(insert_frag["left_end"]["overhang_sequence"]), 4)


def enzyme_site(enzyme):
    return {"EcoRI": "GAATTC", "PstI": "CTGCAG", "SmaI": "CCCGGG"}[enzyme]


class GoldenTATests(unittest.TestCase):
    def setUp(self):
        if not (GOLDEN / "pGEM-T-linearized.dna").exists() or not (GOLDEN / "ta-insert.fa").exists():
            self.skipTest("Academic golden fixtures not present")
        self.tmp = tempfile.TemporaryDirectory(prefix="v04-ta-")
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = pathlib.Path(self.tmp.name)

    def test_ta_matches_committed_pGEM_T_fixture_with_explicit_premises(self):
        out = self.tmp_path / "ta.gb"
        completed = run_script(
            "simulate_advanced.py", "--method", "ta",
            "--vector", str(GOLDEN / "pGEM-T-linearized.dna"),
            "--insert", str(GOLDEN / "ta-insert.fa"),
            "--vector-cut", "0",
            "--vector-end", "t-tailed",
            "--insert-end", "a-tailed",
            "--allow-experimental-output",
            "--out", str(out), "--json")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        payload = parsed(completed)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["topology"], "circular")
        vector_frag = payload["fragments"][0]
        self.assertEqual(vector_frag["topology"], "linear")
        self.assertEqual(vector_frag["left_end"]["cut_boundary"], 0)
        self.assertEqual(vector_frag["right_end"]["cut_boundary"], len(vector_frag["sequence"]))
        self.assertEqual(vector_frag["left_end"]["source_cut_boundary"], 0)
        self.assertEqual(vector_frag["right_end"]["source_cut_boundary"], 0)
        observed = SeqIO.read(str(out), "genbank")
        expected = SeqIO.read(str(GOLDEN / "pGEM-T-insert.gb"), "genbank")
        comparison = compare_records(expected, observed)
        self.assertTrue(comparison["passed"], comparison)
        self.assertTrue(comparison["qualifiers_equal"])

    def test_ta_requires_explicit_end_premises(self):
        completed = run_script(
            "simulate_advanced.py", "--method", "ta",
            "--vector", str(GOLDEN / "pGEM-T-linearized.dna"),
            "--insert", str(GOLDEN / "ta-insert.fa"),
            "--vector-cut", "0", "--json")
        error = error_of(self, completed)
        self.assertEqual(error["code"], "END_TYPE_MISMATCH")

    def test_ta_requires_vector_cut(self):
        completed = run_script(
            "simulate_advanced.py", "--method", "ta",
            "--vector", str(GOLDEN / "pGEM-T-linearized.dna"),
            "--insert", str(GOLDEN / "ta-insert.fa"),
            "--vector-end", "t-tailed",
            "--insert-end", "a-tailed", "--json")
        error = error_of(self, completed)
        self.assertEqual(error["code"], "MISSING_VECTOR_CUT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
