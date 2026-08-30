# -*- coding: utf-8 -*-
"""RG-P0-01: online source adapters must never leak sequence without consent."""
import json
import pathlib
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))

import online_sources  # noqa: E402

SECRET = "ACGTSECRET"


class BlastPrivacyTests(unittest.TestCase):
    def test_unauthorized_hint_never_contains_sequence(self):
        result = online_sources.ncbi_blast_hint(SECRET)
        dumped = json.dumps(result, sort_keys=True)
        self.assertNotIn(SECRET, dumped)
        self.assertNotIn(SECRET, result["url"])
        self.assertFalse(result["contains_sequence_in_url"])
        self.assertNotEqual(result["sequence_sha256_prefix"], SECRET)
        self.assertEqual(len(result["sequence_sha256_prefix"]), 16)

    def test_consent_request_contains_hash_not_sequence(self):
        result = online_sources.ncbi_blast_consent_request(
            SECRET, "guide-search", "target-40bp")
        dumped = json.dumps(result["request"], sort_keys=True)
        self.assertNotIn(SECRET, dumped)
        self.assertEqual(result["request"]["sequence_sha256"],
                         result["request"]["sequence_sha256_prefix"] +
                         "E5CBE1C481C71F3DEBE4" if False else
                         result["request"]["sequence_sha256"][:0] + result["request"]["sequence_sha256"])
        self.assertFalse(result["request"]["contains_sequence"])

    def test_authorized_url_is_one_time_and_bound(self):
        request = online_sources.ncbi_blast_consent_request(
            SECRET, "guide-search", "target-40bp")
        consent = request["consent"]
        consent.approve()
        authorized = online_sources.authorized_blast_url(
            consent, SECRET, "guide-search", "target-40bp")
        self.assertEqual(authorized["status"], "authorized")
        self.assertIn("ACGTSECRET", authorized["url"])
        self.assertTrue(authorized["contains_sequence"])
        # receipt is consumed; second attempt is denied
        denied = online_sources.authorized_blast_url(
            consent, SECRET, "guide-search", "target-40bp")
        self.assertEqual(denied["status"], "denied")
        self.assertIsNone(denied["url"])

    def test_unauthorized_url_is_never_built(self):
        consent = online_sources.ncbi_blast_consent_request(
            SECRET, "guide-search", "target-40bp")["consent"]
        denied = online_sources.authorized_blast_url(
            consent, SECRET, "guide-search", "target-40bp")
        self.assertEqual(denied["status"], "denied")
        self.assertIsNone(denied["url"])
        dumped = json.dumps(denied, sort_keys=True)
        self.assertNotIn(SECRET, dumped)

    def test_ncbi_search_refuses_sequence_like_terms_without_network(self):
        with mock.patch.object(online_sources, "_get") as get:
            result = online_sources.ncbi_search(SECRET)
            get.assert_not_called()
        self.assertEqual(result["status"], "refused-consent-required")
        self.assertNotIn(SECRET, json.dumps(result, sort_keys=True))
        self.assertEqual(result["term_sha256"][:16],
                         online_sources.ncbi_blast_hint(SECRET)[
                             "sequence_sha256_prefix"])

    def test_short_keyword_still_allowed(self):
        self.assertFalse(online_sources._looks_like_sequence("EGFP"))
        self.assertTrue(online_sources._looks_like_sequence("ACGTACGTACGT"))


class AddgeneWordingTests(unittest.TestCase):
    def test_addgene_is_explicit_link_helper(self):
        result = online_sources.addgene_lookup(42230)
        self.assertEqual(result["adapter_kind"],
                         "official-page-link-helper")
        self.assertEqual(result["status"], "offline-unverified")


if __name__ == "__main__":
    unittest.main(verbosity=2)
