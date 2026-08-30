# -*- coding: utf-8 -*-
"""Contract and real-integration tests for the external Primer3 backend."""
import json
import os
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import primer3_core_backend as backend
from primer3_core_backend import (Primer3CoreError, design_anchored_pairs,
                                  encode_boulder, parse_boulder,
                                  probe_primer3_core)


REAL_SEQUENCE = (
    "GCTAAAGACAATTACATAACATACACGTCAGCACGAAACTTGTTGGCCCAGTGTGAATCGCTTA"
    "AGGGTTAAGTAAGTGTGATGCATACGCCTTTACTTGCTGTGTCCACCCCATCGGACTGGCATTT"
    "TTATTACACTCAGAAACAGAACTCGGGTAATTTTGACAGGTCACGCAGAGGCGCGCCCTCCTGA"
    "AGTGCGTGGACACTCGCTATGAATCTCTGATTTACCCACTCTGCCAAACTCCAGCGCGGTCAGT"
    "TCCATCACCCTAAGTAACCGAATAATGCGTTCGCTCTATTGACT"
)


class BoulderContractTests(unittest.TestCase):
    def test_encode_and_parse(self):
        text = encode_boulder({"SEQUENCE_ID": "x", "PRIMER_NUM_RETURN": 5})
        self.assertTrue(text.endswith("=\n"))
        self.assertEqual(parse_boulder(text)["SEQUENCE_ID"], "x")

    def test_rejects_newline_in_value(self):
        with self.assertRaises(ValueError):
            encode_boulder({"SEQUENCE_ID": "x\ny"})

    def test_rejects_invalid_tag(self):
        with self.assertRaises(ValueError):
            encode_boulder({"bad-tag": "x"})

    def test_invalid_explicit_path_does_not_fall_through(self):
        info = probe_primer3_core(str(ROOT / "definitely-missing.exe"))
        self.assertEqual(info["status"], "unavailable")
        self.assertIn("explicit", info["detail"])

    def test_probe_timeout_start_error_and_bad_output(self):
        with mock.patch.object(backend, "discover_primer3_core",
                               return_value="primer3_core.exe"), \
                mock.patch.object(backend.subprocess, "run",
                                  side_effect=subprocess.TimeoutExpired(
                                      "primer3_core", 1)):
            self.assertEqual(probe_primer3_core()["status"], "probe-error")
        with mock.patch.object(backend, "discover_primer3_core",
                               return_value="primer3_core.exe"), \
                mock.patch.object(backend.subprocess, "run",
                                  side_effect=OSError("cannot start")):
            self.assertIn("could not start", probe_primer3_core()["detail"])
        with mock.patch.object(backend, "discover_primer3_core",
                               return_value="primer3_core.exe"), \
                mock.patch.object(backend.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=1, stdout="bad", stderr="")
            self.assertIn("--about failed", probe_primer3_core()["detail"])

    def test_run_boulder_failure_contracts(self):
        with mock.patch.object(backend.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired("p3", 1)):
            with self.assertRaisesRegex(Primer3CoreError, "timed out"):
                backend.run_boulder("p3", {"SEQUENCE_ID": "x"}, timeout=1)
        with mock.patch.object(backend.subprocess, "run",
                               side_effect=OSError("broken")):
            with self.assertRaisesRegex(Primer3CoreError, "could not start"):
                backend.run_boulder("p3", {"SEQUENCE_ID": "x"})
        with mock.patch.object(backend.subprocess, "run") as run:
            run.return_value = mock.Mock(
                returncode=0, stdout="PRIMER_ERROR=bad input\n=\n", stderr="")
            with self.assertRaisesRegex(Primer3CoreError, "bad input"):
                backend.run_boulder("p3", {"SEQUENCE_ID": "x"})
            run.return_value = mock.Mock(returncode=0, stdout="", stderr="empty")
            with self.assertRaisesRegex(Primer3CoreError, "no Boulder"):
                backend.run_boulder("p3", {"SEQUENCE_ID": "x"})

    def test_mapping_rejects_invalid_engine_output(self):
        self.assertIsNone(backend._float({}, "x"))
        self.assertEqual(backend._float({"x": "bad"}, "x", 7), 7)
        self.assertEqual(backend._int({"x": "bad"}, "x", 9), 9)
        with self.assertRaisesRegex(Primer3CoreError, "invalid Primer3 location"):
            backend._location("bad")
        tags = {
            "PRIMER_LEFT_0": "0,4",
            "PRIMER_LEFT_0_SEQUENCE": "TTTT",
        }
        with self.assertRaisesRegex(Primer3CoreError, "does not contain"):
            backend._candidate(tags, "PRIMER_LEFT", 0, "AAAA", 1, 4,
                               "forward")
        tags["PRIMER_LEFT_0_SEQUENCE"] = "AAAAAAA"
        with self.assertRaisesRegex(Primer3CoreError, "length mismatch"):
            backend._candidate(tags, "PRIMER_LEFT", 0, "AAAA", 1, 4,
                               "forward")

    def test_empty_sequence_fails(self):
        with self.assertRaisesRegex(Primer3CoreError, "empty region"):
            design_anchored_pairs("p3", "", 1, 60.0, 18, 30, 5)


class RealPrimer3IntegrationTests(unittest.TestCase):
    """These tests must run (not skip) in the release-promotion gate."""

    @classmethod
    def setUpClass(cls):
        cls.info = probe_primer3_core(os.environ.get("PRIMER3_CORE"))
        if cls.info["status"] != "available":
            raise unittest.SkipTest(
                "real primer3_core unavailable: %s" % cls.info["detail"])

    def test_real_core_selects_ranked_pairs(self):
        designed = design_anchored_pairs(
            self.info["path"], REAL_SEQUENCE, 1, 60.0, 18, 30, 3)
        self.assertEqual(designed["returned_pairs"], 3)
        self.assertEqual(designed["pairs"][0]["rank"], 1)
        self.assertEqual(designed["pairs"][0]["product_size"], 300)
        self.assertEqual(designed["forward_candidates"][0]["bind_start"], 1)
        self.assertEqual(designed["reverse_candidates"][0]["bind_end"], 300)
        self.assertEqual(designed["forward_candidates"][0]["hairpin"]["source"],
                         "primer3-core")
        self.assertIsNotNone(designed["pairs"][0]["primer3_penalty"])

    def test_real_core_separates_gibson_tail_and_binding(self):
        fwd_tail = "ACGTACGT"
        rev_tail = "TGCATGCA"
        designed = design_anchored_pairs(
            self.info["path"], REAL_SEQUENCE, 1, 60.0, 18, 30, 1,
            fwd_tail=fwd_tail, rev_tail=rev_tail)
        self.assertEqual(designed["returned_pairs"], 1)
        fwd = designed["forward_candidates"][0]
        rev = designed["reverse_candidates"][0]
        self.assertEqual(fwd["tail"], fwd_tail)
        self.assertEqual(fwd["sequence"], fwd_tail + fwd["binding"])
        self.assertEqual(rev["sequence"], rev_tail + rev["binding"])
        self.assertEqual(
            designed["pairs"][0]["primer3_product_size_with_overhangs"],
            300 + len(fwd_tail) + len(rev_tail))

    def test_cli_require_primer3_reports_real_engine(self):
        completed = subprocess.run(
            [sys.executable, "-X", "utf8", str(SCRIPTS / "design_primers.py"),
             REAL_SEQUENCE, "--end", "300", "--top-n", "2",
             "--require-primer3", "--primer3-core", self.info["path"],
             "--json", "--consent", "auto"], capture_output=True,
            text=True, encoding="utf-8", errors="replace")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)["data"]
        self.assertEqual(payload["design_engine"]["selected"], "primer3-core")
        self.assertEqual(payload["design_engine"]["verification"],
                         "real-external-engine")
        self.assertEqual(payload["quality"]["source"], "legacy-heuristic")
        self.assertTrue(all(pair["primer3_penalty"] is not None
                            for pair in payload["pairs"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
