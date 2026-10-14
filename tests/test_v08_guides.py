# -*- coding: utf-8 -*-
"""v0.8 guide scanning, provenance, consent and reaction profile tests."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import json
import pathlib
import sys
import unittest

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = SKILL_ROOT
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import characterize_reaction  # noqa: E402
import design_guides  # noqa: E402
import provenance  # noqa: E402
import recommend_protocol  # noqa: E402
import sequence_upload_consent  # noqa: E402


class NucleaseRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = design_guides.load_registry()

    def test_spcas9_has_ngg_3prime(self):
        self.assertEqual(self.registry["spcas9-wt"]["pam_side"], "3prime")
        self.assertIn("NGG", self.registry["spcas9-wt"]["pam_patterns"])

    def test_ascas12a_and_lbcas12a_are_separate(self):
        self.assertIn("ascas12a-wt", self.registry)
        self.assertIn("lbcas12a-wt", self.registry)
        self.assertEqual(self.registry["ascas12a-wt"]["pam_side"], "5prime")
        self.assertEqual(self.registry["lbcas12a-wt"]["pam_side"], "5prime")

    def test_lbcas12a_has_no_on_target_models(self):
        self.assertEqual(self.registry["lbcas12a-wt"]["on_target_models"], [])


class GuideScannerTests(unittest.TestCase):
    def _record(self, seq, circular=False):
        rec = SeqRecord(Seq(seq), id="guide-test")
        rec.annotations["molecule_type"] = "DNA"
        rec.annotations["topology"] = "circular" if circular else "linear"
        return rec

    def test_spcas9_forward_and_reverse(self):
        rec = self._record("AAAAA" + "CGTACGATCGATCGATCGAT" + "AGG" + "TTTTT")
        forward = [c for c in design_guides.scan_guides(rec, "spcas9-wt")
                   if c["strand"] == "forward"]
        reverse = [c for c in design_guides.scan_guides(rec, "spcas9-wt")
                   if c["strand"] == "reverse"]
        self.assertGreaterEqual(len(forward) + len(reverse), 1)

    def test_circular_wrap_is_preserved(self):
        rec = self._record("AGG" + "C" * 20, circular=True)
        candidates = design_guides.scan_guides(rec, "spcas9-wt")
        self.assertTrue(candidates)
        self.assertTrue(any(c["coordinates"]["wraps_origin"] for c in candidates))

    def test_ambiguous_protospacer_warns(self):
        rec = self._record("AAAAA" + "CGNACGATCGATCGATCGAT" + "AGG" + "TTTTT")
        candidates = design_guides.scan_guides(rec, "spcas9-wt")
        self.assertTrue(any(c.get("warning") for c in candidates))

    def test_unknown_nuclease_fails(self):
        with self.assertRaises(ValueError):
            design_guides.scan_guides(self._record("AAAA"), "not-a-nuclease")


class ProvenanceTests(unittest.TestCase):
    def test_valid_source(self):
        src = provenance.source("software", "PAM Scanner", "scanning",
                                version=provenance.read_version(), status="verified")
        provenance.validate(src)

    def test_forbidden_sources_rejected(self):
        with self.assertRaises(provenance.ProvenanceError):
            provenance.source("software", "latest", "role")
        with self.assertRaises(provenance.ProvenanceError):
            provenance.source("software", "PAM Scanner", "role", version="latest")

    def test_missing_provenance_fails(self):
        with self.assertRaises(provenance.ProvenanceError):
            provenance.ensure_provenance({"sequence": "ACGT"})


class UploadConsentTests(unittest.TestCase):
    def test_default_is_denied(self):
        consent = sequence_upload_consent.SequenceUploadConsent("target-40bp")
        consent.request("https://crispor.org", "guide-search", sequence="ACGT")
        self.assertFalse(consent.allowed())

    def test_approve_changes_state_once(self):
        consent = sequence_upload_consent.SequenceUploadConsent("target-40bp")
        consent.request("https://crispor.org", "guide-search", sequence="ACGT")
        consent.approve()
        self.assertFalse(consent.allowed())
        self.assertTrue(consent.peek_allowed())
        state = consent.state["sequence_upload"]
        self.assertTrue(state["approved_at"])
        self.assertNotIn("sequence", state)


class ReactionProfileTests(unittest.TestCase):
    def test_profile_contains_required_fields(self):
        rec = SeqRecord(Seq("A" * 20 + "C" * 20 + "G" * 20), id="frag")
        rec.annotations["molecule_type"] = "DNA"
        rec.annotations["topology"] = "linear"
        profile = characterize_reaction.characterize_fragment(rec, "frag-1")
        self.assertEqual(profile["length"], 60)
        self.assertIn("provenance", profile)
        self.assertEqual(profile["specificity_checked"], False)


class ProtocolRecommendationTests(unittest.TestCase):
    def test_without_sources_is_unavailable(self):
        result = recommend_protocol.recommend([{"fragment_id": "frag-1"}])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["reason"], "PROTOCOL_SOURCE_NOT_FOUND")
        self.assertEqual(result["recommendations"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
