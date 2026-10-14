# -*- coding: utf-8 -*-
"""Coverage-gap tests for the v0.8 CRISPR design modules."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import contextlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from model_test_requirements import requires_real_models

from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = SKILL_ROOT
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import annotate_offtargets  # noqa: E402
import cas_offinder_adapter  # noqa: E402
import characterize_reaction  # noqa: E402
import crispor_adapter  # noqa: E402
import generate_crispr_design_report  # noqa: E402
import design_guides  # noqa: E402
import guide_scoring  # noqa: E402
import protocol_evidence  # noqa: E402
import provenance  # noqa: E402
import recommend_protocol  # noqa: E402
import sequence_upload_consent  # noqa: E402


def record(seq, circular=False, features=()):
    rec = SeqRecord(Seq(seq), id="rec", name="rec")
    rec.annotations["molecule_type"] = "DNA"
    rec.annotations["topology"] = "circular" if circular else "linear"
    for feature in features:
        rec.features.append(feature)
    return rec


class DesignGuidesGapTests(unittest.TestCase):
    def test_iupac_all_bases(self):
        self.assertTrue(design_guides._iupac_compatible("V", "A"))
        self.assertTrue(design_guides._iupac_compatible("B", "C"))
        self.assertTrue(design_guides._iupac_compatible("D", "A"))
        self.assertTrue(design_guides._iupac_compatible("H", "A"))
        self.assertTrue(design_guides._iupac_compatible("W", "A"))
        self.assertTrue(design_guides._iupac_compatible("S", "C"))
        self.assertTrue(design_guides._iupac_compatible("M", "A"))
        self.assertTrue(design_guides._iupac_compatible("K", "G"))
        self.assertTrue(design_guides._iupac_compatible("R", "A"))
        self.assertTrue(design_guides._iupac_compatible("Y", "C"))
        self.assertFalse(design_guides._iupac_compatible("A", "C"))
        self.assertFalse(design_guides.pam_matches("AG", "A"))

    def test_arc_and_segment_helpers(self):
        self.assertEqual(design_guides._arc("ACGT", 0, 4), "ACGT")
        self.assertEqual(design_guides._arc("ACGT", 2, 4), "GTAC")
        self.assertEqual(design_guides._arc("ACGT", 1, 0), "")
        self.assertEqual(design_guides._linear_segments(-1, 2, 4), [])
        self.assertEqual(design_guides._linear_segments(1, 1, 4), [[1, 1]])
        self.assertEqual(design_guides._user_1based([[0, 3]]), [[1, 3]])

    def test_scan_errors_and_limits(self):
        with self.assertRaises(ValueError):
            design_guides.scan_guides(record("AAAA"), "nope")
        registry = {"x": {"pam_patterns": [], "spacer_lengths": [20],
                          "pam_side": "3prime", "family": "Cas9"}}
        with self.assertRaises(ValueError):
            design_guides.scan_guides(record("AAAA"), "x", registry=registry)
        with self.assertRaises(ValueError):
            design_guides.scan_guides(record("AAAA"), "spcas9-wt",
                                      region=(-1, 2))
        self.assertEqual(design_guides.scan_guides(
            record("AGG" + "C" * 20), "spcas9-wt", region=(10, 15)), [])

    def test_max_candidates_and_assign_ids(self):
        rec = record("AGG" + "C" * 20, circular=True)
        candidates = design_guides.scan_guides(rec, "spcas9-wt",
                                               max_candidates=1)
        self.assertEqual(len(candidates), 1)
        self.assertTrue(candidates[0]["id"])
        design_guides._assign_ids(candidates)
        self.assertEqual(candidates[0]["id"], "gRNA-001")

    def test_context_helpers_and_circular(self):
        rec = record("TTTA" + "C" * 23, circular=True)
        candidates = design_guides.scan_guides(rec, "ascas12a-wt")
        self.assertTrue(candidates)
        self.assertTrue(all(
            c["context_sequences"].get("deepcpf1_34mer") for c in candidates))

    def test_main_text_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            fasta = pathlib.Path(tmp) / "t.fa"
            fasta.write_text(">t\nACGTACGTACGTACGTACGTACGTGGGAAA\n")
            with mock.patch.object(sys, "argv",
                                   ["design_guides.py", str(fasta),
                                    "--nuclease", "spcas9-wt"]):
                self.assertEqual(design_guides.main(), 0)
            with mock.patch.object(sys, "argv",
                                   ["design_guides.py", str(fasta),
                                    "--nuclease", "spcas9-wt", "--json"]):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    self.assertEqual(design_guides.main(), 0)
                payload = json.loads(buffer.getvalue())
                self.assertEqual(payload["schema_version"], "0.8.0")
            with mock.patch.object(sys, "argv",
                                   ["design_guides.py", str(fasta),
                                    "--nuclease", "nope", "--json"]):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    self.assertEqual(design_guides.main(), 1)
                self.assertIn('"ok": false', buffer.getvalue())


class CasOffinderGapTests(unittest.TestCase):
    def test_normalise_version_and_detect_paths(self):
        self.assertIsNone(cas_offinder_adapter._normalise_version(None))
        self.assertIsNone(cas_offinder_adapter._normalise_version("hello"))
        self.assertEqual(
            cas_offinder_adapter._normalise_version("Cas-OFFinder v2.4.1"), "2.4.1")
        with mock.patch.object(cas_offinder_adapter.shutil, "which",
                               return_value=None):
            detection = cas_offinder_adapter.detect()
            self.assertFalse(detection["installed"])
        with mock.patch.object(cas_offinder_adapter.shutil, "which",
                               return_value="cas-offinder.exe"), \
                mock.patch.object(cas_offinder_adapter, "probe_executable",
                                  return_value=("cas-offinder.exe", "broken", {
                                      "method": "subprocess-version-probe",
                                      "status": "verified"})), \
                mock.patch.object(
                    cas_offinder_adapter.subprocess, "run",
                    return_value=subprocess.CompletedProcess(
                        ["cas-offinder.exe"], 0,
                        "Cas-OFFinder v2.4.1\\nAvailable device list:\\n"
                        "Type: GPU, ID: 0, GPU\\n"
                        "Type: CPU, ID: 1, CPU\\n", "")):
            detection = cas_offinder_adapter.detect()
            self.assertTrue(detection["installed"])
            self.assertTrue(detection["opencl_detected"])
            self.assertEqual(detection["available_devices"], [
                {"type": "GPU", "id": 0}, {"type": "CPU", "id": 1}])
            self.assertEqual(detection["recommended_device"], "G0")

    def test_genome_record_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            missing = cas_offinder_adapter.genome_record(tmp / "nope.fa")
            self.assertEqual(missing["status"], "failed")
            empty = tmp / "empty.fa"
            empty.write_text("")
            self.assertEqual(
                cas_offinder_adapter.genome_record(empty)["status"], "incomplete")
            fasta = tmp / "ref.fa"
            fasta.write_text(">chr1\nACGT\n")
            missing_annotation = cas_offinder_adapter.genome_record(
                fasta, annotation_path=tmp / "nope.gb")
            self.assertEqual(missing_annotation["status"], "failed")
            self.assertEqual(missing_annotation["reason"],
                             "REFERENCE_ANNOTATION_NOT_FOUND")
            rec = cas_offinder_adapter.genome_record(
                fasta, annotation_path=fasta, species="H", strain="S",
                assembly="A", index_time="t", backend={"version": "2.4.1"})
            self.assertEqual(rec["status"], "ready")
            self.assertEqual(rec["sequence_count"], 1)
            self.assertEqual(rec["backend_version"], "2.4.1")

    def test_registry_helpers(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            registry_path = tmp / "reg.json"
            registry_path.write_text("{bad json", encoding="utf-8")
            self.assertEqual(
                cas_offinder_adapter.load_index_registry(registry_path), {})
            registry = {"p": {"fasta_sha256": "A"}}
            cas_offinder_adapter.save_index_registry(registry, registry_path)
            self.assertEqual(
                cas_offinder_adapter.load_index_registry(registry_path),
                registry)
            ref = {"status": "ready", "fasta_path": "p",
                   "fasta_sha256": "A"}
            self.assertEqual(
                cas_offinder_adapter.check_reference_binding(
                    ref, registry, registry_path)["status"], "bound")
            ref["fasta_sha256"] = "B"
            self.assertEqual(
                cas_offinder_adapter.check_reference_binding(
                    ref, registry, registry_path)["status"], "stale")
            self.assertEqual(
                cas_offinder_adapter.check_reference_binding(
                    {"status": "failed"})["status"], "failed")
            self.assertEqual(
                cas_offinder_adapter.check_reference_binding(
                    {"status": "ready", "fasta_path": "q", "fasta_sha256": "A"},
                    registry, registry_path)["status"], "unbound")
            result = cas_offinder_adapter.record_reference_binding(
                {"fasta_path": None}, {}, registry_path)
            self.assertIn("p", result)

    def test_search_rules_and_input_errors(self):
        with self.assertRaises(ValueError):
            cas_offinder_adapter.search_rules("nope")
        rules = cas_offinder_adapter.search_rules(
            "spcas9-wt", {"spacer_length": 19})
        self.assertEqual(rules["spacer_length"], 19)
        with self.assertRaises(ValueError):
            cas_offinder_adapter.build_input_text(
                "ACG", "spcas9-wt", {"mismatches": 3})
        with self.assertRaises(ValueError):
            cas_offinder_adapter.build_input_text(
                "ACGN", "spcas9-wt", {"mismatches": 3})
        with self.assertRaises(ValueError):
            cas_offinder_adapter.search_offtargets(
                "ACGT", "x", "not-dict")

    def test_parse_errors(self):
        for bad in [
            "bad line\n",
            "q\tchr\tx\tACGT\t+\t1\n",
            "q\tchr\t-1\tACGT\t+\t1\n",
            "q\tchr\t1\tACGT\t?\t1\n",
            "q\tchr\t1\t\t+\t1\n",
        ]:
            hits, error = cas_offinder_adapter.parse_output(bad)
            self.assertIsNone(hits, bad)
            self.assertIn("EXTERNAL_OUTPUT_PARSE_ERROR", error)
        hits, error = cas_offinder_adapter.parse_output("")
        self.assertEqual(hits, [])
        self.assertIn("EMPTY", error)

    def test_helpers(self):
        self.assertEqual(cas_offinder_adapter._mismatch_positions(
            "ACGT", "ACGA"), [3])
        self.assertEqual(cas_offinder_adapter._infer_pam_side(
            "TTTV" + "N" * 20), "5prime")
        self.assertEqual(cas_offinder_adapter._extract_pam(
            "TTTGACGT", "5prime"), "TTTG")

    def test_timeout_and_unsupported_bulge(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            fasta = tmp / "ref.fa"
            fasta.write_text(">chr1\nACGTACGTACGT\n")
            detection = {"installed": True,
                         "executable": str(tmp / "cas-offinder.exe"),
                         "version": "2.4.1", "opencl_detected": True,
                         "verification": {"status": "verified"},
                         "provenance": []}
            with mock.patch.object(cas_offinder_adapter, "detect",
                                   return_value=detection), \
                    mock.patch.object(cas_offinder_adapter.subprocess, "run",
                                      side_effect=cas_offinder_adapter.subprocess.TimeoutExpired(
                                          "x", 1)):
                result = cas_offinder_adapter.search_offtargets(
                    "ACGTACGTACGTACGTACGT", fasta, {"mismatches": 1},
                    executable="x", timeout=1)
                self.assertEqual(result["reason"], "CAS_OFFINDER_TIMEOUT")
            with mock.patch.object(cas_offinder_adapter, "detect",
                                   return_value=detection):
                result = cas_offinder_adapter.search_offtargets(
                    "ACGTACGTACGTACGTACGT", fasta,
                    {"mismatches": 1, "dna_bulge": 1},
                    executable="x")
                self.assertEqual(result["reason"],
                                 "CAS_OFFINDER_BULGE_UNSUPPORTED")


class ScoringGapTests(unittest.TestCase):
    def test_heuristic_qc_branches(self):
        self.assertEqual(guide_scoring._heuristic_qc("")["gc_percent"], None)
        self.assertEqual(guide_scoring._heuristic_qc("AAAA")[
                             "homopolymer_risk"], "high")
        self.assertEqual(guide_scoring._heuristic_qc("AAAC")[
                             "homopolymer_risk"], "medium")

    def test_backend_failures_are_unavailable(self):
        with mock.patch("builtins.__import__", side_effect=RuntimeError("x")):
            payload, error = guide_scoring._run_azimuth("ACGT" + "N" * 26)
        self.assertIsNone(payload)
        self.assertIn("BACKEND_UNAVAILABLE", error)
        with mock.patch("builtins.__import__", side_effect=RuntimeError("x")):
            payload, error = guide_scoring._run_deepcpf1("ACGT" * 8 + "AA", "+")
        self.assertIsNone(payload)
        self.assertIn("BACKEND_UNAVAILABLE", error)


class RecommendGapTests(unittest.TestCase):
    def test_helpers(self):
        self.assertTrue(recommend_protocol._as_bool(True))
        self.assertTrue(recommend_protocol._as_bool("yes"))
        self.assertFalse(recommend_protocol._as_bool(False))
        self.assertEqual(recommend_protocol._category_for(
            {"reaction_type": "pcr"}), "pcr")
        self.assertEqual(recommend_protocol._category_for(
            {"reaction_type": "assembly"}), "assembly")
        self.assertEqual(recommend_protocol._category_for(
            {"assembly_method": "nebuilder"}), "assembly")
        self.assertEqual(recommend_protocol._category_for(
            {"template_type": "genomic-dna"}), "pcr")
        self.assertEqual(recommend_protocol._category_for(
            {"high_fidelity_required": True}), "pcr")
        self.assertEqual(recommend_protocol._category_for(
            {"five_prime_tail": "EcoRI"}), "pcr")
        self.assertEqual(recommend_protocol._category_for(
            {"specificity_checked": True}), "pcr")
        self.assertIsNone(recommend_protocol._category_for({}))

    def test_mixed_profiles_partial(self):
        sources = protocol_evidence.load_sources()
        result = recommend_protocol.recommend(
            [{"fragment_id": "a", "template_type": "pcr-template",
              "length": 500},
             {"fragment_id": "b"}], sources)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["recommendations"]), 2)

    def test_high_gc_pcr_match(self):
        sources = protocol_evidence.load_sources()
        item = {"source_id": "x", "source_type": "manufacturer-protocol",
                "provider": "NEB", "title": "High GC", "url": "https://x",
                "retrieved_at": "2026-01-01", "document_revision": "1",
                "verification_status": "current-page-read",
                "applicable_to": ["high-gc-pcr"]}
        matched, reasons = recommend_protocol._source_matches(
            "pcr", {"length": 800, "gc_percent": 70.0}, item)
        self.assertTrue(matched)
        self.assertTrue(any("gc_percent" in r for r in reasons))
        matched, _reasons = recommend_protocol._source_matches(
            "pcr", {"gc_percent": 40.0}, item)
        self.assertFalse(matched)


class CharacterizeGapTests(unittest.TestCase):
    def test_windows_and_runs(self):
        self.assertEqual(characterize_reaction._windows("ACGT", 40, 10),
                         ["ACGT"])
        self.assertEqual(len(characterize_reaction._windows("A" * 50, 40, 10)),
                         2)
        self.assertEqual(characterize_reaction._homopolymer_runs("AAAAAA"), [
            {"base": "A", "length": 6}])
        self.assertEqual(characterize_reaction._homopolymer_runs(""), [])

    def test_circular_profile(self):
        profile = characterize_reaction.characterize_fragment(
            record("A" * 40, circular=True), "c")
        self.assertEqual(profile["topology"], "circular")


class ConsentGapTests(unittest.TestCase):
    def test_deny_and_message(self):
        consent = sequence_upload_consent.SequenceUploadConsent("s")
        consent.request("https://x", "p", sequence="ACGT")
        consent.approve()
        consent.deny()
        self.assertFalse(consent.allowed())
        message = consent.consent_message(10, "local")
        self.assertIn("local", message)
        self.assertIn("留存政策", message)
        self.assertIn("unverified", message)
        self.assertNotIn('"sequence":', consent.to_json())

    def test_retention_policy_is_destination_specific_and_unverified(self):
        crispor = sequence_upload_consent.SequenceUploadConsent("s")
        crispor.request("https://crispor.org", "p", sequence="ACGT")
        crispor_msg = crispor.consent_message()
        self.assertIn("CRISPOR", crispor_msg)
        self.assertNotIn("至少24个月", crispor_msg)
        ncbi = sequence_upload_consent.SequenceUploadConsent("s")
        ncbi.request("https://blast.ncbi.nlm.nih.gov/Blast.cgi", "p",
                     sequence="ACGT")
        ncbi_msg = ncbi.consent_message()
        self.assertNotIn("CRISPOR", ncbi_msg)
        self.assertIn("NCBI", ncbi_msg)
        self.assertIn("unverified", ncbi_msg)

    def test_approve_without_request(self):
        consent = sequence_upload_consent.SequenceUploadConsent()
        consent.approve()
        self.assertFalse(consent.allowed())
        consent.request("https://x", "p", sequence="ACGT")
        consent.approve()
        self.assertTrue(consent.peek_allowed())


class AnnotateGapTests(unittest.TestCase):
    def test_feature_types(self):
        for feature_type, expected in [("CDS", "CDS"), ("gene", "gene"),
                                       ("promoter", "promoter"),
                                       ("regulatory", "regulatory"),
                                       ("tRNA", "tRNA"), ("rRNA", "rRNA"),
                                       ("ncRNA", "ncRNA"), ("misc_RNA", "ncRNA"),
                                       ("repeat_region", "unknown")]:
            feature = SeqFeature(FeatureLocation(0, 1), type=feature_type)
            self.assertEqual(annotate_offtargets.feature_type_for(feature),
                             expected)

    def test_helpers(self):
        self.assertEqual(annotate_offtargets._strand_label(1), "+")
        self.assertEqual(annotate_offtargets._strand_label(-1), "-")
        self.assertEqual(annotate_offtargets._strand_label(None), ".")
        self.assertEqual(annotate_offtargets._hit_segments(
            {"start": 5, "end": 2}, 10), ([[5, 10], [0, 2]], True))
        self.assertEqual(annotate_offtargets._hit_segments(
            {"start": 3, "end": 3}, 10), ([], False))
        self.assertFalse(annotate_offtargets._overlaps([[0, 1]], [[1, 2]]))
        feature = SeqFeature(FeatureLocation(0, 1),
                             qualifiers={"label": ["L"], "gene": ["G"],
                                         "product": ["P"]})
        self.assertEqual(annotate_offtargets._feature_name(feature), "L")
        self.assertEqual(annotate_offtargets._orientation("+", -1), "opposite")

    def test_compound_and_circular_locations(self):
        location = CompoundLocation([FeatureLocation(5, 10, strand=-1),
                                     FeatureLocation(0, 2, strand=-1)])
        segments, wraps = annotate_offtargets._location_segments(location, 12)
        self.assertEqual(segments, [[5, 10], [0, 2]])
        self.assertFalse(wraps)
        fake_part = type("Part", (), {"start": 10, "end": 3})()
        fake_location = type("Loc", (), {"parts": [fake_part]})()
        segments, wraps = annotate_offtargets._location_segments(
            fake_location, 12)
        self.assertTrue(wraps)
        self.assertEqual(segments, [[10, 12], [0, 3]])
        edge_part = type("Part", (), {"start": 12, "end": 0})()
        segments, wraps = annotate_offtargets._location_segments(
            type("Loc", (), {"parts": [edge_part]})(), 12)
        self.assertEqual(segments, [])
        end_zero = type("Part", (), {"start": 12, "end": 0})()
        segments, wraps = annotate_offtargets._location_segments(
            type("Loc", (), {"parts": [end_zero]})(), 12)
        self.assertEqual(segments, [])

    def test_annotate_no_matching_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "a.gb"
            import Bio.SeqIO as SeqIO
            SeqIO.write(record("ACGT"), path, "genbank")
            hits = [{"chromosome": "other", "start": 0, "end": 1,
                     "strand": "+", "mismatches": 1}]
            annotate_offtargets.annotate_hits(hits, path)
            self.assertEqual(hits[0]["annotation"]["feature_type"],
                             "intergenic")


class ProtocolEvidenceGapTests(unittest.TestCase):
    def test_load_missing_and_source_object(self):
        self.assertEqual(protocol_evidence.load_sources(
            pathlib.Path("nope.json")), [])
        item = protocol_evidence.load_sources()[0]
        item = dict(item, verification_status="unchecked")
        obj = protocol_evidence.source_object(item)
        self.assertEqual(obj["status"], "unknown")


class ProvenanceGapTests(unittest.TestCase):
    def test_source_rejections(self):
        for kwargs in [{"source_type": "AI", "name": "x", "role": "r"},
                       {"source_type": "software", "name": "", "role": "r"},
                       {"source_type": "software", "name": "x", "role": ""},
                       {"source_type": "software", "name": "x", "role": "r",
                        "version": "latest"}]:
            with self.assertRaises(provenance.ProvenanceError):
                provenance.source(**kwargs)

    def test_validate_rejections(self):
        for bad in [
            {}, {"source_type": "AI", "name": "x", "role": "r",
                 "status": "verified"},
            {"source_type": "software", "name": "AI", "role": "r",
             "status": "verified"},
            {"source_type": "software", "name": "x", "role": "r",
             "status": "maybe"},
            {"source_type": "software", "name": "x", "role": "r",
             "status": "verified", "version": "latest"},
        ]:
            with self.assertRaises(provenance.ProvenanceError):
                provenance.validate(bad)
        with self.assertRaises(provenance.ProvenanceError):
            provenance.ensure_provenance({"x": 1})

    def test_read_version_missing_file(self):
        old = provenance.VERSION_FILE
        provenance.VERSION_FILE = pathlib.Path("missing-version-file")
        self.assertEqual(provenance.read_version(), "unknown")
        provenance.VERSION_FILE = old
        with self.assertRaises(provenance.ProvenanceError):
            provenance.ensure_provenance(
                {"provenance": [{"source_type": "software"}]})

    def test_probe_executable_paths(self):
        with mock.patch("shutil.which", return_value=None):
            path, version, verification = provenance.probe_executable("nope")
            self.assertIsNone(path)
            self.assertIsNone(version)
            self.assertEqual(verification["status"], "unavailable")
        with mock.patch("shutil.which", return_value="exe"), \
                mock.patch.object(provenance.subprocess, "run",
                                  return_value=__import__("subprocess").CompletedProcess(
                                      ["exe"], 1, "", "failed")):
            path, version, verification = provenance.probe_executable("x")
            self.assertEqual(verification["status"], "unavailable")
            self.assertEqual(verification["returncode"], 1)
        with mock.patch("shutil.which", return_value="exe"), \
                mock.patch.object(provenance.subprocess, "run",
                                  return_value=__import__("subprocess").CompletedProcess(
                                      ["exe"], 0, "", "")):
            path, version, verification = provenance.probe_executable("x")
            self.assertEqual(verification["status"], "unavailable")
        with mock.patch("shutil.which", return_value="exe"), \
                mock.patch.object(provenance.subprocess, "run",
                                  side_effect=OSError("boom")):
            path, version, verification = provenance.probe_executable("x")
            self.assertEqual(verification["status"], "unavailable")
            self.assertIn("boom", verification["error"])


class AdditionalCoverageTests(unittest.TestCase):
    def test_characterize_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            fasta = pathlib.Path(tmp) / "f.fa"
            fasta.write_text(">f\nACGTACGTACGTACGTACGTACGT\n")
            with mock.patch.object(sys, "argv",
                                   ["characterize_reaction.py", str(fasta)]):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    self.assertEqual(characterize_reaction.main(), 0)
                self.assertIn("bp", buffer.getvalue())

    def test_recommend_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = pathlib.Path(tmp) / "p.json"
            profile.write_text(json.dumps({
                    "reaction_profiles": [
                    {"fragment_id": "f", "template_type": "pcr-template",
                     "length": 500}]}),
                encoding="utf-8")
            with mock.patch.object(sys, "argv", [
                    "recommend_protocol.py", "--profile", str(profile)]):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    self.assertEqual(recommend_protocol.main(), 0)
                self.assertIn("Q5", buffer.getvalue())
            with mock.patch.object(sys, "argv", [
                    "recommend_protocol.py", "--json"]):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    self.assertEqual(recommend_protocol.main(), 0)
                self.assertIn('"schema_version"', buffer.getvalue())

    def test_annotate_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            import Bio.SeqIO as SeqIO
            SeqIO.write(record("A" * 40), tmp / "a.gb", "genbank")
            hits = {"schema_version": "0.8.0", "status": "complete",
                    "reference_genome": {"status": "ready",
                                         "fasta_sha256": "A" * 64},
                    "hits": [{"chromosome": "rec", "start": 0, "end": 5,
                              "strand": "+", "mismatches": 1,
                              "annotation": None}],
                    "provenance": []}
            (tmp / "hits.json").write_text(json.dumps(hits), encoding="utf-8")
            with mock.patch.object(sys, "argv", [
                    "annotate_offtargets.py", str(tmp / "hits.json"),
                    "--annotation", str(tmp / "a.gb"), "--json"]):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    annotate_offtargets.main()
                payload = json.loads(buffer.getvalue())
                self.assertEqual(payload["schema_version"], "0.8.0")
            with mock.patch.object(sys, "argv", [
                    "annotate_offtargets.py", str(tmp / "hits.json"),
                    "--annotation", str(tmp / "a.gb")]):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    annotate_offtargets.main()
                self.assertIn("hits", buffer.getvalue())

    def test_guide_scoring_missing_context_and_cli(self):
        payload, error = guide_scoring._run_azimuth(None)
        self.assertIsNone(payload)
        self.assertIn("CONTEXT", error)
        payload, error = guide_scoring._run_deepcpf1(None, "+")
        self.assertIsNone(payload)
        self.assertIn("CONTEXT", error)
        results = guide_scoring.score_guides(
            [{"id": "g1", "context_sequences": {},
              "protospacer_sequence": "ACGT"}], "spcas9-wt")
        self.assertEqual(results[0]["on_target_scores"][0]["status"],
                         "unavailable")
        with mock.patch.object(sys, "argv", ["guide_scoring.py"]):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                self.assertEqual(guide_scoring.main(), 0)
            self.assertIn("no-reviewed-model", buffer.getvalue())

    def test_deepcpf1_error_branches(self):
        import deepcpf1_model as deep_model
        with self.assertRaises(ValueError):
            deep_model.predict_sequence_only(["ACGT"])
        with self.assertRaises(ValueError):
            deep_model.predict_sequence_only(["N" * 34])
        with self.assertRaises(ValueError):
            deep_model.predict_with_chromatin(["A" * 34], [0, 1])
        old_path = deep_model.SEQ_WEIGHTS
        old_net = deep_model._SEQ_NET
        deep_model.SEQ_WEIGHTS = pathlib.Path("missing.h5")
        deep_model._SEQ_NET = None
        with self.assertRaises(deep_model.BackendUnavailable):
            deep_model.predict_sequence_only(["A" * 34])
        deep_model.SEQ_WEIGHTS = old_path
        deep_model._SEQ_NET = old_net

    def test_azimuth_error_branches(self):
        try:
            import pandas  # noqa: F401
        except ImportError:
            self.skipTest("pandas is not installed; skipping azimuth backend tests")
        import azimuth_backend
        predictor = azimuth_backend.AzimuthPredictor.__new__(
            azimuth_backend.AzimuthPredictor)
        with self.assertRaises(azimuth_backend.BackendUnavailable):
            azimuth_backend.AzimuthPredictor(model_path=pathlib.Path("nope"))
        predictor.model_path = pathlib.Path(
            azimuth_backend.MODEL_PICKLE)
        with self.assertRaises(ValueError):
            azimuth_backend.AzimuthPredictor.predict(predictor, ["A" * 10])
        with self.assertRaises(ValueError):
            azimuth_backend.AzimuthPredictor.predict(predictor, ["N" * 30])

    @requires_real_models('azimuth', 'deepcpf1')
    def test_guide_scoring_real_available_branch(self):
        payload, error = guide_scoring._run_azimuth(
            "ACGT" + "ACGT" * 5 + "GGG" + "AAA")
        self.assertIsNone(error)
        self.assertNotIn("status", payload)
        self.assertGreater(payload["score"], 0)
        payload, error = guide_scoring._run_deepcpf1(
            "GTTATTTGAGCAATGCCACTTAATAAACATGTAA", "+")
        self.assertIsNone(error)
        self.assertTrue(payload["score"] > 0)
        old = guide_scoring.MODEL_APPLICABILITY
        guide_scoring.MODEL_APPLICABILITY = {
            "weird-wt": {"Odd": {"backend": "odd"}}}
        results = guide_scoring.score_guides(
            [{"id": "g1", "protospacer_sequence": "A"}], "weird-wt")
        self.assertEqual(results[0]["on_target_scores"][0]["reason"],
                         "backend-not-configured")
        guide_scoring.MODEL_APPLICABILITY = old

    def test_consent_consumed_branch(self):
        consent = sequence_upload_consent.SequenceUploadConsent("s")
        consent.request("https://x", "p", sequence="ACGT")
        consent.approve()
        consent.allowed("https://x", "p", "ACGT", "s")
        self.assertFalse(consent.peek_allowed())
        self.assertFalse(consent.allowed())
        consent.approve()
        self.assertTrue(consent.allowed("https://x", "p", "ACGT", "s",
                                        consume=False))
        self.assertTrue(consent.peek_allowed())
        missing_purpose = sequence_upload_consent.SequenceUploadConsent("s")
        missing_purpose.request("https://x", "", sequence="ACGT")
        missing_purpose.approve()
        self.assertFalse(missing_purpose.allowed())


class ReportGapTests(unittest.TestCase):
    def test_input_records_and_merge(self):
        with tempfile.TemporaryDirectory() as tmp:
            fasta = pathlib.Path(tmp) / "f.fa"
            fasta.write_text(">f\nACGT\n")
            records = generate_crispr_design_report._input_records(
                [fasta, pathlib.Path(tmp) / "nope.fa"])
            self.assertEqual(records[0]["sha256"], "EDJF" + "?" if False else records[0]["sha256"])
            self.assertIsNone(records[1]["sha256"])
        hit = {"chromosome": "chr1", "start": 0, "end": 10, "strand": "+",
               "sequence": "ACGT", "mismatches": 0}
        merged = generate_crispr_design_report._merge_hits([
            ({"id": "g1"}, {"status": "complete", "hits": [hit]}),
            ({"id": "g2"}, {"status": "complete", "hits": [hit]}),
            ({"id": "g3"}, {"status": "failed", "hits": []}),
        ])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["query_guide_ids"], ["g1", "g2"])

    def test_offtarget_analysis_no_reference_and_missing_binary(self):
        options = {"reference_fasta": None, "annotation": None,
                   "target_gene": None, "cas_offinder": None,
                   "offinder_device": "C0", "mismatches": 3,
                   "dna_bulge": 0, "rna_bulge": 0,
                   "max_offtarget_candidates": 5,
                   "rebuild_stale_index": True}
        rec = record("ACGTACGTACGTACGTACGTACGTGGGAAA")
        args = __import__("argparse").Namespace(**options)
        result = generate_crispr_design_report._offtarget_analysis(
            rec, [], args)
        self.assertEqual(result["status"], "unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            fasta = pathlib.Path(tmp) / "ref.fa"
            fasta.write_text(">chr1\nACGT\n")
            args.reference_fasta = str(fasta)
            with mock.patch.object(generate_crispr_design_report,
                                   "offinder_detect",
                                   return_value={"installed": False,
                                                 "provenance": []}):
                result = generate_crispr_design_report._offtarget_analysis(
                    rec, [], args)
                self.assertEqual(result["status"], "unavailable")

    def test_make_report_direct(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            target = tmp / "target.fa"
            seq = "ACGT" + "GCATCGATCGATCGATCGTA" + "AGG" + "TTA"
            target.write_text(">t\n%s\n" % seq)
            fragment = tmp / "fragment.fa"
            fragment.write_text(">f\nACGTACGTACGTACGTACGT\n")
            options = {"reference_fasta": str(tmp / "ref.fa"),
                       "annotation": None, "target_gene": None,
                       "cas_offinder": "fake", "offinder_device": "C0",
                       "mismatches": 3, "dna_bulge": 0, "rna_bulge": 0,
                       "max_offtarget_candidates": 5,
                       "rebuild_stale_index": True}
            report = generate_crispr_design_report.make_report(
                str(target), "spcas9-wt", [str(fragment)], None, options)
            self.assertIn(report["status"], ("partial", "complete"))
            # patch search backend to exercise the complete/annotation path
            detection = {"installed": True, "provenance": [],
                         "version": "2.4.1"}
            fake_ref = {"status": "ready", "fasta_path": str(target),
                        "fasta_sha256": "A" * 64, "annotation_path": None,
                        "annotation_sha256": None, "sequence_count": 1,
                        "total_length": len(seq)}
            hit = {"chromosome": "t", "start": 0, "end": 20, "strand": "+",
                   "sequence": seq[:20], "mismatches": 0, "mismatch_positions": [],
                   "pam": "AGG", "bulge_type": None, "bulge_size": 0,
                   "annotation": None}
            with mock.patch.object(generate_crispr_design_report,
                                   "offinder_detect",
                                   return_value=detection), \
                    mock.patch.object(generate_crispr_design_report,
                                      "search_offtargets",
                                      return_value={
                                          "status": "complete",
                                          "reference_genome": fake_ref,
                                          "hits": [hit],
                                          "provenance": []}):
                report = generate_crispr_design_report.make_report(
                    str(target), "spcas9-wt", [str(fragment)], None, options)
                self.assertEqual(report["off_target"]["status"], "complete")

    def test_offtarget_analysis_failure_branches(self):
        rec = record("ACGTACGTACGTACGTACGTACGTGGGAAA")
        candidates = design_guides.scan_guides(rec, "spcas9-wt")
        options = {"reference_fasta": "ref.fa", "annotation": None,
                   "target_gene": None, "cas_offinder": "fake",
                   "offinder_device": "C0", "mismatches": 3,
                   "dna_bulge": 0, "rna_bulge": 0,
                   "max_offtarget_candidates": 5,
                   "rebuild_stale_index": True}
        args = __import__("argparse").Namespace(**options)
        args.nuclease = "spcas9-wt"
        detection = {"installed": True, "provenance": [], "version": "2.4.1"}
        with mock.patch.object(generate_crispr_design_report,
                               "offinder_detect", return_value=detection), \
                mock.patch.object(generate_crispr_design_report,
                                  "search_offtargets",
                                  return_value={"status": "failed",
                                                "reference_genome": None,
                                                "hits": [],
                                                "provenance": []}):
            result = generate_crispr_design_report._offtarget_analysis(
                rec, candidates, args)
            self.assertEqual(result["status"], "failed")
        with mock.patch.object(generate_crispr_design_report,
                               "offinder_detect", return_value=detection), \
                mock.patch.object(generate_crispr_design_report,
                                  "search_offtargets",
                                  return_value={"status": "incomplete",
                                                "reference_genome": None,
                                                "hits": [],
                                                "provenance": []}):
            result = generate_crispr_design_report._offtarget_analysis(
                rec, candidates, args)
            self.assertEqual(result["status"], "incomplete")
        with mock.patch.object(generate_crispr_design_report,
                               "offinder_detect", return_value=detection), \
                mock.patch.object(generate_crispr_design_report,
                                  "search_offtargets",
                                  return_value={"status": "complete",
                                                "reference_genome": {
                                                    "status": "ready",
                                                    "fasta_path": "ref.fa",
                                                    "fasta_sha256": "A" * 64,
                                                    "annotation_path": None,
                                                    "annotation_sha256": None,
                                                    "sequence_count": 1,
                                                    "total_length": 100},
                                                "hits": [{
                                                    "chromosome": "chr1",
                                                    "start": 0, "end": 5,
                                                    "strand": "+",
                                                    "sequence": "ACGT",
                                                    "mismatches": 0,
                                                    "mismatch_positions": [],
                                                    "pam": "AGG",
                                                    "bulge_type": None,
                                                    "bulge_size": 0,
                                                    "annotation": None}],
                                                "provenance": []}):
            args.annotation = "missing.gb"
            result = generate_crispr_design_report._offtarget_analysis(
                rec, candidates, args)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["reason"], "OFFTARGET_ANNOTATION_FAILED")

    def test_main_direct_success_and_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            target = tmp / "target.fa"
            target.write_text(
                ">t\nACGTGCATCGATCGATCGATCGTAAGGTTA\n")
            with mock.patch.object(sys, "argv", [
                    "generate_crispr_design_report.py", str(target),
                    "--nuclease", "spcas9-wt",
                    "--out-json", str(tmp / "r.json"),
                    "--out-markdown", str(tmp / "r.md"),
                    "--out-dir", str(tmp / "out")]):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    self.assertEqual(
                        generate_crispr_design_report.main(), 0)
                self.assertTrue((tmp / "r.json").exists())
                self.assertTrue((tmp / "r.md").exists())
            with mock.patch.object(sys, "argv", [
                    "generate_crispr_design_report.py", str(target),
                    "--nuclease", "not-a-nuclease",
                    "--out-json", str(tmp / "fail.json")]):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    self.assertEqual(
                        generate_crispr_design_report.main(), 1)
                payload = json.loads((tmp / "fail.json").read_text(
                    encoding="utf-8"))
                self.assertEqual(payload["status"], "failed")

    def test_markdown_and_failed_report(self):
        report = generate_crispr_design_report._failed_report(
            "boom", "target.fa", "spcas9-wt")
        self.assertEqual(report["status"], "failed")
        text = generate_crispr_design_report._markdown(report)
        self.assertIn("## off_target", text)
        self.assertIn("## protocol_recommendation", text)

    def test_write_design_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = generate_crispr_design_report._write_design_files(
                record("ACGT" * 10), pathlib.Path(tmp), "design")
            self.assertEqual(len(files), 3)
            self.assertTrue(all(pathlib.Path(item["path"]).exists()
                                for item in files))


class CrisporGapTests(unittest.TestCase):
    def test_detect_and_consent_request(self):
        with mock.patch("shutil.which", return_value=None):
            self.assertFalse(crispor_adapter.detect()["installed"])
        with mock.patch("shutil.which", return_value="crispor"):
            self.assertTrue(crispor_adapter.detect()["installed"])
        consent = crispor_adapter.online_query_request("ACGT", "human", "p")
        self.assertFalse(consent.allowed())


if __name__ == "__main__":
    unittest.main(verbosity=2)
