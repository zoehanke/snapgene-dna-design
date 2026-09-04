# -*- coding: utf-8 -*-
"""v0.8.0-dev3 regression tests for P0/P1 fixes and real backends."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"
SCHEMAS = ROOT / "schemas"
sys.path.insert(0, str(SCRIPTS))

import annotate_offtargets  # noqa: E402
import cas_offinder_adapter  # noqa: E402
import design_guides  # noqa: E402
import guide_scoring  # noqa: E402
import provenance  # noqa: E402
import recommend_protocol  # noqa: E402
import sequence_upload_consent  # noqa: E402


def make_record(seq, circular=False):
    rec = SeqRecord(Seq(seq), id="test")
    rec.annotations["molecule_type"] = "DNA"
    rec.annotations["topology"] = "circular" if circular else "linear"
    return rec


class P0CoordinateTests(unittest.TestCase):
    def test_reverse_strand_maps_to_reference_axis(self):
        seq = "A" * 10 + "CCG" + "GATCGATCGGATCGATCGT" + "A" * 6
        candidates = design_guides.scan_guides(make_record(seq), "spcas9-wt")
        reverse = [c for c in candidates if c["strand"] == "reverse"]
        self.assertTrue(reverse)
        coords = reverse[0]["coordinates"]
        self.assertEqual((coords["protospacer_start"], coords["protospacer_end"]),
                         (13, 33))
        self.assertEqual((coords["pam_start"], coords["pam_end"]), (10, 13))
        self.assertEqual(str(Seq(seq[13:33]).reverse_complement()),
                         reverse[0]["protospacer_sequence"])
        self.assertEqual(reverse[0]["protospacer_reference_sequence"], seq[13:33])

    def test_linear_end_pam_never_wraps(self):
        for seq in ("AGG" + "C" * 20, "GG" + "A" * 19 + "CG"):
            self.assertEqual(
                design_guides.scan_guides(make_record(seq), "spcas9-wt"), [])

    def test_circular_wrap_has_explicit_segments(self):
        candidates = design_guides.scan_guides(
            make_record("AAGG" + "G" * 20, circular=True), "spcas9-wt")
        self.assertTrue(candidates)
        self.assertTrue(any(
            len(c["coordinates"]["pam_segments"]) > 1
            or len(c["coordinates"]["protospacer_segments"]) > 1
            for c in candidates))

    def test_linear_cas12a_never_reports_wrap(self):
        rec = make_record("TTTA" + "C" * 23)
        candidates = design_guides.scan_guides(rec, "ascas12a-wt")
        self.assertTrue(candidates)
        self.assertFalse(any(c["coordinates"]["wraps_origin"]
                             for c in candidates))

    def test_linear_interval_ending_at_n_keeps_n_boundary(self):
        rec = make_record("TTTA" + "C" * 23)
        candidate = design_guides.scan_guides(rec, "ascas12a-wt")[0]
        coords = candidate["coordinates"]
        self.assertEqual((coords["protospacer_start"],
                          coords["protospacer_end"]), (4, 27))
        self.assertEqual(coords["protospacer_segments"], [[4, 27]])
        rec2 = make_record("C" * 20 + "AGG")
        candidate2 = design_guides.scan_guides(rec2, "spcas9-wt")[0]
        coords2 = candidate2["coordinates"]
        self.assertEqual((coords2["pam_start"], coords2["pam_end"]), (20, 23))
        self.assertEqual(coords2["pam_segments"], [[20, 23]])

    def test_circular_scalar_and_segments_agree_at_n(self):
        candidates = design_guides.scan_guides(
            make_record("AAGG" + "G" * 20, circular=True), "spcas9-wt")
        for candidate in candidates:
            coords = candidate["coordinates"]
            for start, end, segments in (
                    (coords["protospacer_start"], coords["protospacer_end"],
                     coords["protospacer_segments"]),
                    (coords["pam_start"], coords["pam_end"],
                     coords["pam_segments"])):
                if end == 24:
                    self.assertFalse(coords["wraps_origin"])
                    self.assertEqual(segments, [[start, 24]])
                else:
                    self.assertEqual(segments[-1][1], end)
        self.assertTrue(any(c["coordinates"]["pam_end"] == 24
                            for c in candidates))


class ConsentBindingTests(unittest.TestCase):
    def test_ten_interception_scenarios(self):
        consent = sequence_upload_consent.SequenceUploadConsent("target-40bp")
        self.assertFalse(consent.allowed())
        consent.request("https://crispor.org", "guide-search",
                        sequence="ACGTACGTACGT")
        consent.approve()
        self.assertFalse(consent.allowed())  # no-arg is a denial, not a peek
        self.assertTrue(consent.peek_allowed())
        # destination / purpose / sequence / scope mismatches all deny
        for kwargs in [
            {"destination": "https://elsewhere.example"},
            {"purpose": "other-purpose"},
            {"sequence": "TTTT"},
            {"scope": "other-scope"},
        ]:
            consent.request("https://crispor.org", "guide-search",
                            sequence="ACGTACGTACGT")
            consent.approve()
            self.assertFalse(consent.allowed(**kwargs),
                             "must deny for %s" % kwargs)
            self.assertFalse(consent.allowed())
        # one-time consumption
        consent.request("https://crispor.org", "guide-search",
                        sequence="ACGTACGTACGT")
        consent.approve()
        self.assertTrue(consent.allowed(
            "https://crispor.org", "guide-search", "ACGTACGTACGT",
            "target-40bp"))
        self.assertFalse(consent.allowed())
        # a new request supersedes an old receipt
        consent.request("https://crispor.org", "guide-search",
                        sequence="ACGTACGTACGT")
        consent.approve()
        consent.request("https://crispor.org", "guide-search",
                        sequence="TTTTTTTTTTTT")
        self.assertFalse(consent.allowed())
        # approve without request stays denied
        empty = sequence_upload_consent.SequenceUploadConsent()
        empty.approve()
        self.assertFalse(empty.allowed())


class ProvenanceVersionTests(unittest.TestCase):
    def test_conditional_required_fields(self):
        for source_type in ("manufacturer-protocol", "prediction-model"):
            base = {"source_type": source_type, "name": "X", "role": "r",
                    "status": "verified"}
            with self.assertRaises(provenance.ProvenanceError):
                provenance.validate(base)
        good = {"source_type": "manufacturer-protocol", "name": "X",
                "role": "r", "status": "verified", "url": "https://example.org",
                "retrieved_at": "2026-08-17", "version": "1.0"}
        self.assertTrue(provenance.validate(good))

    def test_schema_rejects_manufacturer_missing_required_fields(self):
        from jsonschema import Draft202012Validator
        schema = json.loads(
            (SCHEMAS / "provenance-v0.8.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        good = {"source_type": "manufacturer-protocol", "name": "X",
                "role": "r", "status": "verified", "url": "https://example.org",
                "retrieved_at": "2026-08-17", "version": "1.0"}
        self.assertEqual(list(validator.iter_errors(good)), [])
        for drop in ("version", "url", "retrieved_at"):
            bad = {k: v for k, v in good.items() if k != drop}
            self.assertTrue(list(validator.iter_errors(bad)),
                            "dropping %s must fail validation" % drop)

    def test_all_provenance_versions_come_from_version_file(self):
        expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(provenance.read_version(), expected)
        src = provenance.source("software", "PAM Scanner", "role",
                                version=provenance.read_version(),
                                status="verified")
        self.assertEqual(src["version"], expected)


class ProtocolRecommendationFeatureTests(unittest.TestCase):
    def test_pcr_profile_selects_q5(self):
        from protocol_evidence import load_sources
        result = recommend_protocol.recommend(
            [{"fragment_id": "f1", "template_type": "pcr-template",
              "length": 800, "gc_percent": 55.0}], load_sources())
        self.assertEqual(result["status"], "available")
        self.assertIn("Q5", result["recommendations"][0]["recommended_system"])

    def test_assembly_profile_selects_nebuilder(self):
        from protocol_evidence import load_sources
        result = recommend_protocol.recommend(
            [{"fragment_id": "f1", "assembly_method": "gibson",
              "fragment_count": 2, "overlap_length": 20}],
            load_sources())
        self.assertIn("NEBuilder",
                      result["recommendations"][0]["recommended_system"])

    def test_empty_profile_list_is_unavailable(self):
        from protocol_evidence import load_sources
        result = recommend_protocol.recommend([], load_sources())
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "NO_REACTION_PROFILES_PROVIDED")
        self.assertEqual(result["recommendations"], [])

    def test_unmatched_profile_is_unavailable_with_insufficient_evidence(self):
        from protocol_evidence import load_sources
        result = recommend_protocol.recommend(
            [{"fragment_id": "mystery"}], load_sources())
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(
            result["recommendations"][0]["status"], "insufficient_evidence")
        self.assertIsNone(result["recommendations"][0]["recommended_system"])


class OfftargetAnnotationTests(unittest.TestCase):
    def test_overlap_not_start_containment(self):
        with tempfile.TemporaryDirectory() as tmp:
            rec = SeqRecord(Seq("A" * 60), id="chr1", name="chr1")
            rec.annotations["molecule_type"] = "DNA"
            rec.annotations["topology"] = "linear"
            rec.features.append(SeqFeature(FeatureLocation(10, 30, strand=1),
                                           type="CDS",
                                           qualifiers={"gene": ["geneA"]}))
            rec.features.append(SeqFeature(FeatureLocation(20, 40, strand=1),
                                           type="gene",
                                           qualifiers={"gene": ["geneB"]}))
            path = pathlib.Path(tmp) / "ann.gb"
            SeqIO.write(rec, path, "genbank")
            hits = [
                {"chromosome": "chr1", "start": 5, "end": 15, "strand": "+",
                 "mismatches": 1},
                {"chromosome": "chr1", "start": 25, "end": 30, "strand": "+",
                 "mismatches": 2},
            ]
            annotate_offtargets.annotate_hits(hits, path)
            self.assertEqual(hits[0]["annotation"]["feature_type"], "CDS")
            second = hits[1]["annotation"]
            self.assertEqual(second["feature_type"], "gene")
            self.assertEqual(second["feature_name"], "geneB")
            self.assertEqual(
                {item["feature_name"] for item in second["overlapping_features"]},
                {"geneA", "geneB"})


class CasOffinderAdapterTests(unittest.TestCase):
    def test_registry_default_lives_outside_source_tree(self):
        import os as _os
        env = dict(_os.environ)
        env.pop("CAS_OFFINDER_REGISTRY", None)
        with mock.patch.dict(_os.environ, env, clear=True):
            default = cas_offinder_adapter.default_index_registry_path()
        self.assertNotIn(
            str(cas_offinder_adapter.ROOT).lower(),
            str(default).lower())
        self.assertTrue("snapgenednadesign" in str(default).lower() or "snapgene-dna-design" in str(default).lower())

    def test_build_input_contract(self):
        text = cas_offinder_adapter.build_input_text(
            "GCATCGATCGATCGATCGTA", "spcas9-wt", {"mismatches": 3})
        self.assertIn("NNNNNNNNNNNNNNNNNNNNNGG", text)
        self.assertIn("GCATCGATCGATCGATCGTA", text)
        self.assertIn(" 3 ", text)

    def test_missing_reference_is_structured(self):
        result = cas_offinder_adapter.search_offtargets(
            "ACGT", "Z:\\does-not-exist.fa", {"mismatches": 3})
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], "REFERENCE_FASTA_NOT_FOUND")

    def test_stale_index_blocks_without_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            fasta = tmp / "ref.fa"
            fasta.write_text(">chr1\nACGTACGTACGT\n")
            registry = {
                str(fasta): {
                    "fasta_sha256": "0" * 64,
                    "sequence_count": 1,
                    "total_length": 12,
                    "index_time": "2026-01-01",
                }}
            result = cas_offinder_adapter.search_offtargets(
                "ACGT", fasta, {"mismatches": 1}, executable="missing",
                nuclease_id="spcas9-wt",
                registry_path=tmp / "reg.json",
                rebuild_stale=False)
            cas_offinder_adapter.save_index_registry(
                registry, tmp / "reg.json")
            result = cas_offinder_adapter.search_offtargets(
                "ACGT", fasta, {"mismatches": 1}, executable="missing",
                nuclease_id="spcas9-wt",
                registry_path=tmp / "reg.json",
                rebuild_stale=False)
            self.assertEqual(result["status"], "failed")
            self.assertIn("STALE", result["reason"])

    def test_real_cli_contract_and_failure_paths_with_fake_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            fasta = tmp / "ref.fa"
            fasta.write_text(">chr1\n" + "A" * 100 + "GCATCGATCGATCGATCGTAAGG" + "C" * 50 + "\n")
            detection = {
                "installed": True,
                "executable": str(tmp / "cas-offinder.exe"),
                "version": "2.4.1",
                "opencl_detected": True,
                "available_devices": [{"type": "GPU", "id": 0}],
                "recommended_device": "G0",
                "verification": {"status": "verified"},
                "provenance": [],
            }

            mode = iter(["complete", "failed", "empty"])

            def fake_run(cmd, *args, **kwargs):
                # argv contract: exe <relative input> auto-selected G0
                # <relative output>,
                # cwd = FASTA directory (non-ASCII-path-safe form).
                self.assertEqual(len(cmd), 4)
                self.assertEqual(cmd[2], "G0")
                cwd = pathlib.Path(kwargs.get("cwd"))
                self.assertTrue(os.path.samefile(cwd, tmp))
                self.assertIn("in.txt", str(cmd[1]))
                self.assertIn("out.txt", str(cmd[3]))
                input_text = (cwd / str(cmd[1])).read_text(encoding="utf-8")
                self.assertTrue(input_text.startswith("ref.fa\n"))
                output = cwd / str(cmd[3])
                current = next(mode)
                if current == "failed":
                    output.write_text("", encoding="utf-8")
                    return subprocess.CompletedProcess(cmd, 3, "", "boom")
                if current == "empty":
                    output.write_text("", encoding="utf-8")
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                output.write_text(
                    "GCATCGATCGATCGATCGTAAGG\tchr1\t100\t"
                    "GCATCGATCGATCGATCGTAAGG\t+\t0\n",
                    encoding="utf-8")
                return subprocess.CompletedProcess(cmd, 0, "", "")

            with mock.patch.object(cas_offinder_adapter, "detect",
                                   return_value=detection), \
                    mock.patch.object(cas_offinder_adapter.subprocess, "run",
                                      side_effect=fake_run):
                ok = cas_offinder_adapter.search_offtargets(
                    "GCATCGATCGATCGATCGTA", fasta, {"mismatches": 3},
                    executable="ok", nuclease_id="spcas9-wt",
                    registry_path=tmp / "reg.json")
                self.assertEqual(ok["status"], "complete")
                self.assertEqual(ok["hits"][0]["start"], 100)
                fail = cas_offinder_adapter.search_offtargets(
                    "GCATCGATCGATCGATCGTA", fasta, {"mismatches": 3},
                    executable="fail", nuclease_id="spcas9-wt",
                    registry_path=tmp / "reg.json")
                self.assertEqual(fail["status"], "failed")
                empty = cas_offinder_adapter.search_offtargets(
                    "GCATCGATCGATCGATCGTA", fasta, {"mismatches": 3},
                    executable="empty", nuclease_id="spcas9-wt",
                    registry_path=tmp / "reg.json")
                self.assertEqual(empty["status"], "incomplete")
                self.assertIn("EMPTY", empty["reason"])


class RealModelTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("SNAPGENE_RUN_REAL_MODELS") == "1",
                         "set SNAPGENE_RUN_REAL_MODELS=1 for real model gates")
    def test_azimuth_real_prediction(self):
        from azimuth_backend import score_30mers
        score = score_30mers(["ACGT" + "ACGT" * 5 + "GGG" + "AAA"])[0]
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
        self.assertAlmostEqual(score, 0.31682680735151075, places=5)

    @unittest.skipUnless(os.environ.get("SNAPGENE_RUN_REAL_MODELS") == "1",
                         "set SNAPGENE_RUN_REAL_MODELS=1 for real model gates")
    def test_deepcpf1_matches_bioconductor_reference(self):
        from deepcpf1_model import (predict_sequence_only,
                                    predict_with_chromatin)
        seqs = ["GTTATTTGAGCAATGCCACTTAATAAACATGTAA",
                "TGACTTTGAATGGAGTCGTGAGCGCAAGAACGCT"]
        scores = predict_sequence_only(seqs * 2)
        self.assertEqual(len(scores), 4)
        self.assertAlmostEqual(scores[0], 0.5346983, places=5)
        self.assertAlmostEqual(scores[1], 0.5569931, places=5)
        ca = predict_with_chromatin(seqs * 2, [0, 1, 1, 0])
        for got, expected in zip(ca, [0.07932924, 0.46077484, 0.44095499,
                                      0.08181222]):
            self.assertAlmostEqual(got, expected, places=5)


class ReportAndOutputFormatTests(unittest.TestCase):
    def test_unknown_nuclease_is_structured_failed_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            fasta = tmp / "target.fa"
            fasta.write_text(">t\nACGTACGTACGTACGTACGTACGT\n")
            completed = subprocess.run(
                [sys.executable, "-X", "utf8", "-B",
                 str(SCRIPTS / "generate_crispr_design_report.py"),
                 str(fasta), "--nuclease", "not-a-nuclease",
                 "--out-json", str(tmp / "report.json")],
                capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(completed.returncode, 0)
            self.assertTrue((tmp / "report.json").exists())
            report = json.loads((tmp / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "failed")

    def test_output_formats_sequence_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            fasta = tmp / "target.fa"
            seq = "ACGT" + "GCATCGATCGATCGATCGTA" + "AGG" + "TTA"
            fasta.write_text(">t\n%s\n" % seq)
            completed = subprocess.run(
                [sys.executable, "-X", "utf8", "-B",
                 str(SCRIPTS / "generate_crispr_design_report.py"),
                 str(fasta), "--nuclease", "spcas9-wt",
                 "--out-json", str(tmp / "report.json"),
                 "--out-markdown", str(tmp / "report.md"),
                 "--out-dir", str(tmp / "out")],
                capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(completed.returncode, 0, completed.stdout[-500:])
            gb = SeqIO.read(tmp / "out" / "target.gb", "genbank")
            fa = SeqIO.read(tmp / "out" / "target.fa", "fasta")
            dna = SeqIO.read(tmp / "out" / "target.dna", "snapgene")
            self.assertEqual(str(gb.seq), seq)
            self.assertEqual(str(fa.seq), seq)
            self.assertEqual(str(dna.seq), seq)


class RealCasOffinderIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("CAS_OFFINDER_EXE"),
                         "set CAS_OFFINDER_EXE to a real cas-offinder binary")
    def test_real_binary_end_to_end_non_ascii_path(self):
        exe = os.environ["CAS_OFFINDER_EXE"]
        workdir = pathlib.Path(os.environ.get("CAS_OFFINDER_TMP")
                               or tempfile.gettempdir())
        workdir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(workdir)) as tmp:
            root = pathlib.Path(tmp) / "中文路径测试"
            root.mkdir()
            fasta = root / "ref.fa"
            fasta.write_text(
                ">chr1\n" + "A" * 50 + "GCATCGATCGATCGATCGTAAGG"
                + "C" * 50 + "\n", encoding="utf-8")
            result = cas_offinder_adapter.search_offtargets(
                "GCATCGATCGATCGATCGTA", fasta, {"mismatches": 3},
                executable=exe, nuclease_id="spcas9-wt")
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["hits"][0]["start"], 50)
            # helper files must not leak into the reference directory
            leftovers = [p.name for p in root.iterdir()
                         if p.name.startswith(".cas-offinder-")]
            self.assertEqual(leftovers, [])

    @unittest.skipUnless(os.environ.get("CAS_OFFINDER_EXE_V3"),
                         "set CAS_OFFINDER_EXE_V3 to Cas-OFFinder 3.x")
    def test_real_binary_v3_bulge(self):
        exe = os.environ["CAS_OFFINDER_EXE_V3"]
        workdir = pathlib.Path(os.environ.get("CAS_OFFINDER_TMP")
                               or tempfile.gettempdir())
        with tempfile.TemporaryDirectory(dir=str(workdir)) as tmp:
            tmp = pathlib.Path(tmp)
            fasta = tmp / "ref.fa"
            sp = "GCATCGATCGATCGATCGTA"
            inserted = sp[:10] + "AA" + sp[10:]
            fasta.write_text(">chr1\n" + "A" * 50 + inserted + "AGG"
                             + "C" * 50 + "\n", encoding="utf-8")
            result = cas_offinder_adapter.search_offtargets(
                sp, fasta, {"mismatches": 0, "dna_bulge": 2,
                            "rna_bulge": 0},
                executable=exe, nuclease_id="spcas9-wt")
            self.assertEqual(result["status"], "complete")
            self.assertTrue(result["experimental_backend"])
            self.assertFalse(result["production_ready"])
            self.assertIn("cross-check", result["backend_warning"])
            self.assertTrue(any(h["bulge_type"] == "DNA"
                                and h["bulge_size"] == 2
                                for h in result["hits"]))

    @unittest.skipUnless(os.environ.get("CAS_OFFINDER_EXE"),
                         "set CAS_OFFINDER_EXE to a real cas-offinder binary")
    def test_real_binary_end_to_end(self):
        exe = os.environ["CAS_OFFINDER_EXE"]
        workdir = os.environ.get("CAS_OFFINDER_TMP") or None
        with tempfile.TemporaryDirectory(dir=workdir) as tmp:
            tmp = pathlib.Path(tmp)
            fasta = tmp / "ref.fa"
            fasta.write_text(
                ">chr1\n" + "A" * 50 + "GCATCGATCGATCGATCGTAAGG" + "C" * 50 + "\n")
            result = cas_offinder_adapter.search_offtargets(
                "GCATCGATCGATCGATCGTA", fasta, {"mismatches": 3},
                executable=exe, nuclease_id="spcas9-wt")
            self.assertEqual(result["status"], "complete")
            self.assertGreaterEqual(len(result["hits"]), 1)
            self.assertEqual(result["hits"][0]["start"], 50)


if __name__ == "__main__":
    unittest.main(verbosity=2)
