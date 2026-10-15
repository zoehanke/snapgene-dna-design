# -*- coding: utf-8 -*-
"""Regression tests for the 2026-08-20 biological-correctness audit fixes."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import sys
import unittest
from unittest import mock

from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = SKILL_ROOT
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

from Bio.Restriction import BstYI  # noqa: E402
from Bio.Seq import Seq  # noqa: E402

import cas_offinder_adapter  # noqa: E402
import guide_scoring  # noqa: E402
import online_sources  # noqa: E402
import primer_qc  # noqa: E402
import provenance  # noqa: E402
import sg_common  # noqa: E402
import validation_crosscheck as vc  # noqa: E402


class AuditRegressionTests(unittest.TestCase):
    def test_fusion_frame_uses_addition_not_subtraction(self):
        from planning.planner import _check_fusion_frame
        fragments = [{"name": "a", "sequence": "A" * 300},
                     {"name": "b", "sequence": "C" * 100}]
        result = _check_fusion_frame(fragments, {
            "junction_after": 0, "upstream_cds_end": 299,
            "downstream_cds_start": 1, "expected_frame": 0})
        self.assertTrue(result["in_frame"], result)
        self.assertEqual(result["frame_offset_mod3"], 0)

    def test_circular_restriction_crosscheck_handles_wrap(self):
        result = vc.restriction_site_crosscheck(
            "TCTC" + "A" * 20 + "GG", "BsaI", circular=True)
        self.assertTrue(result["consistent_count"], result)
        self.assertEqual(result["direct_motif_count"], 1)

    def test_degenerate_restriction_site_matches_iupac(self):
        hits = sg_common.restriction_hits(
            Seq("AAAAAAGATCTAAAA"), BstYI, circular=False)
        self.assertTrue(hits)
        self.assertEqual(hits[0]["strand"], 1)
        self.assertEqual(hits[0]["start"], 6)
        self.assertEqual(hits[0]["top_cut_boundary_0based"], 6)

    def test_provenance_validate_rejects_lowercase_ai(self):
        with self.assertRaises(provenance.ProvenanceError):
            provenance.validate({"source_type": "software", "name": "ai",
                                 "role": "x", "status": "verified"})

    def test_consent_hash_matches_normalized_transmitted_sequence(self):
        raw = "acgt  ACGT"
        request = online_sources.ncbi_blast_consent_request(
            raw, purpose="audit", scope="test")
        request["consent"].approve()
        result = online_sources.authorized_blast_url(
            request["consent"], raw, purpose="audit", scope="test")
        self.assertEqual(result["status"], "authorized", result)
        self.assertEqual(request["request"]["sequence_sha256"],
                         request["consent"].state["sequence_upload"]
                         ["sequence_sha256"])

    def test_short_raw_oligo_is_refused_before_network(self):
        with mock.patch.object(online_sources, "_get") as get:
            result = online_sources.ncbi_search("ACGTACG")
        self.assertFalse(get.called)
        self.assertEqual(result["status"], "refused-consent-required")

    def test_self_dimer_detects_reverse_complement(self):
        score_aatt = primer_qc.score_self_dimer("AATT")[0]
        score_pal = primer_qc.score_self_dimer("ACGTACGT")[0]
        self.assertGreater(score_aatt, 0)
        self.assertGreater(score_pal, 0)

    def test_v3_bulge_end_excludes_gap_bases(self):
        row = ("q1\tDNA\tACGTACGTACGTACGTACGTANN\t"
               "ACGTACG-TACGTACGTACGAGG\tchr1\t11\t+\t0\t1\n")
        hits, error = cas_offinder_adapter.parse_output(row)
        self.assertIsNone(error)
        self.assertEqual(hits[0]["reference_span"],
                         len(hits[0]["sequence"].replace("-", "")))
        self.assertEqual(hits[0]["end"], hits[0]["start"] + hits[0]["reference_span"])

    def test_scoring_payloads_carry_applicability_warnings(self):
        results = guide_scoring.score_guides([{"id": "g1"}], "lbcas12a-wt")
        self.assertTrue(results[0]["applicability_warnings"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
