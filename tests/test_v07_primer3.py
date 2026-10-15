# -*- coding: utf-8 -*-
"""v0.7.0-dev tests: Primer3 integration, candidate ranking, Gibson split.

Coverage targets (first integration phase):

* heuristic fallback honesty: it must never claim Primer3 verification.
  The production process does not import primer3-py; real Primer3 coverage
  lives in test_primer3_core_backend.py.
* top-N candidate output with binding / tail / full sequence / Tm / GC /
  hairpin / self-dimer / heterodimer / 3' stability / product size /
  penalties / recommendation.
* candidate shortage (warning) and zero candidates (structured failure).
* Tm mismatch, hairpin, self-dimer and cross-dimer penalty detection.
* Gibson binding/tail separation: annealing parameters from binding,
  structural checks on the full primer.
"""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import contextlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

HERE = pathlib.Path(__file__).resolve().parent
ROOT = SKILL_ROOT
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import design_primers  # noqa: E402
import primer3_probe  # noqa: E402
from design_primers import ThermoEngine, scan_side, build_pairs  # noqa: E402
from primer3_core_backend import Primer3CoreError  # noqa: E402


def run_cli(*args, expect_fail=False):
    cli_args = list(args)
    # Legacy v0.7 tests exercise the deterministic heuristic contract. Real
    # Primer3 behavior has its own fail-closed integration suite.
    if not any(item in cli_args for item in
               ("--engine", "--primer3-core", "--require-primer3")):
        cli_args.extend(["--engine", "heuristic"])
    if "--consent" not in cli_args:
        cli_args.extend(["--consent", "auto"])
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "design_primers.py")] + cli_args,
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if expect_fail:
        if completed.returncode == 0:
            raise AssertionError("expected failure, got success")
    else:
        if completed.returncode != 0:
            raise AssertionError(
                "design_primers failed: %s" % (completed.stderr + completed.stdout)[-800:])
    return completed


def write_fa(sequence, directory, name="t.fa"):
    path = pathlib.Path(directory) / name
    path.write_text(">t\n%s\n" % sequence, encoding="utf-8")
    return path


class Primer3StatusTests(unittest.TestCase):
    def test_probe_reports_not_installed(self):
        primer3_probe._CACHE.clear()
        with mock.patch("primer3_probe.subprocess.run") as run:
            run.return_value = mock.Mock(
                returncode=3, stdout="P3_IMPORT_ERROR: No module named 'primer3'\n",
                stderr="")
            status, detail = primer3_probe.probe_primer3(python="py")
        self.assertEqual(status, "not-installed")
        self.assertIn("No module named", detail)

    def test_probe_reports_import_crash(self):
        primer3_probe._CACHE.clear()
        with mock.patch("primer3_probe.subprocess.run") as run:
            run.return_value = mock.Mock(
                returncode=3221225477, stdout="", stderr="boom")
            status, detail = primer3_probe.probe_primer3(python="py")
        self.assertEqual(status, "import-crash")
        self.assertIn("crash", detail)

    def test_probe_reports_available(self):
        primer3_probe._CACHE.clear()
        with mock.patch("primer3_probe.subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="P3_OK\n", stderr="")
            status, detail = primer3_probe.probe_primer3(python="py")
        self.assertEqual(status, "available")

    def test_cli_reports_unavailable_and_warns(self):
        with tempfile.TemporaryDirectory(prefix="v07-p3-") as td:
            template = write_fa("ATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGC", td)
            completed = run_cli(str(template), "--start", "1", "--end", "42", "--json")
        payload = json.loads(completed.stdout)["data"]
        self.assertEqual(payload["primer3_status"], "unavailable")
        self.assertEqual(payload["design_engine"]["verification"],
                         "unverified-heuristic")
        self.assertTrue(any("Primer3 design was NOT used" in warning
                            for warning in payload["warnings"]))
        self.assertIn("No Primer3 design or verification is claimed",
                      payload["primer3_note"])
        # structural scores must be labeled heuristic when unavailable
        self.assertEqual(payload["forward_candidates"][0]["hairpin"]["source"],
                         "heuristic")

    def test_fallback_engine_cannot_claim_primer3(self):
        engine = ThermoEngine("heuristic", None)
        self.assertFalse(engine.available)
        candidate = scan_side("ACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT",
                              60.0, 18, 30, engine, "fwd")[0]
        self.assertEqual(candidate["hairpin"]["source"], "heuristic")
        self.assertEqual(candidate["self_dimer"]["source"], "heuristic")
        self.assertEqual(candidate["end_stability_3p"]["source"], "heuristic")

    def _run_main_failure(self, argv, probe_result, design_result=None,
                          design_error=None):
        if "--consent" not in argv:
            argv = list(argv) + ["--consent", "auto"]
        output = io.StringIO()
        patches = [
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(design_primers, "probe_primer3_core",
                              return_value=probe_result),
        ]
        if design_error is not None:
            patches.append(mock.patch.object(
                design_primers, "design_anchored_pairs",
                side_effect=design_error))
        elif design_result is not None:
            patches.append(mock.patch.object(
                design_primers, "design_anchored_pairs",
                return_value=design_result))
        with patches[0], patches[1]:
            nested = patches[2] if len(patches) > 2 else contextlib.nullcontext()
            with nested, contextlib.redirect_stdout(output):
                with self.assertRaises(SystemExit) as caught:
                    design_primers.main()
        self.assertEqual(caught.exception.code, 1)
        return json.loads(output.getvalue())

    def test_require_primer3_fails_when_unavailable(self):
        payload = self._run_main_failure(
            ["design_primers.py", "ACGT" * 20, "--require-primer3", "--json"],
            {"status": "unavailable", "backend": "primer3-core",
             "path": None, "version": None, "detail": "missing"})
        self.assertEqual(payload["error"]["code"], "PRIMER3_REQUIRED")

    def test_require_primer3_fails_on_execution_error(self):
        payload = self._run_main_failure(
            ["design_primers.py", "ACGT" * 20, "--require-primer3", "--json"],
            {"status": "available", "backend": "primer3-core",
             "path": "p3", "version": "2.6.1", "detail": None},
            design_error=Primer3CoreError("forced crash"))
        self.assertEqual(payload["error"]["code"],
                         "PRIMER3_EXECUTION_FAILED")

    def test_require_primer3_fails_when_engine_returns_no_pair(self):
        payload = self._run_main_failure(
            ["design_primers.py", "ACGT" * 20, "--require-primer3", "--json"],
            {"status": "available", "backend": "primer3-core",
             "path": "p3", "version": "2.6.1", "detail": None},
            design_result={"forward_candidates": [], "reverse_candidates": [],
                           "pairs": [], "explain": {"pair": "ok 0"}})
        self.assertEqual(payload["error"]["code"], "PRIMER3_NO_CANDIDATES")


class CandidateOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v07-cand-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def test_default_top5_candidates_with_all_fields(self):
        template = write_fa("ATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGC", self.dir)
        completed = run_cli(str(template), "--start", "1", "--end", "42", "--json")
        payload = json.loads(completed.stdout)["data"]
        self.assertEqual(payload["top_n"], 5)
        self.assertEqual(len(payload["pairs"]), 5)
        required = {"binding", "tail", "sequence", "tm", "gc", "hairpin",
                    "self_dimer", "heterodimer", "end_stability_3p",
                    "product_size", "penalties", "recommended"}
        for candidate in payload["forward_candidates"][:5]:
            self.assertTrue(required.issubset(candidate))
        for pair in payload["pairs"]:
            self.assertIn("product_size", pair)
            self.assertEqual(pair["product_size"], 42)
            self.assertIn(pair["recommended"], ("high", "medium", "low"))

    def test_top_n_configurable(self):
        template = write_fa("ATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGC", self.dir)
        completed = run_cli(str(template), "--start", "1", "--end", "42",
                            "--top-n", "2", "--json")
        payload = json.loads(completed.stdout)["data"]
        self.assertEqual(len(payload["pairs"]), 2)

    def test_candidate_shortage_warns(self):
        # 20 bp region with min_len 18 -> only 3 candidate lengths.
        template = write_fa("A" * 20, self.dir)
        completed = run_cli(str(template), "--start", "1", "--end", "20", "--json")
        payload = json.loads(completed.stdout)["data"]
        self.assertLess(payload["candidate_count"]["forward"], 5)
        self.assertTrue(any("only 3 forward candidate" in w
                            for w in payload["warnings"]))

    def test_zero_candidates_is_structured_failure(self):
        template = write_fa("A" * 10, self.dir)
        completed = run_cli(str(template), "--start", "1", "--end", "10",
                            "--json", expect_fail=True)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "NO_PRIMER_CANDIDATES")


class PenaltyTests(unittest.TestCase):
    def test_tm_mismatch_penalty(self):
        engine = ThermoEngine(*primer3_probe.probe_primer3())
        candidates = scan_side("ATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGC",
                               85.0, 18, 30, engine, "fwd")
        self.assertTrue(any("Tm deviates" in p
                            for p in candidates[0]["penalties"]))

    def test_hairpin_and_self_dimer_penalties(self):
        engine = ThermoEngine(*primer3_probe.probe_primer3())
        # A self-folding stem-loop region (stem GCCGCC + loop TTT +
        # complement GGCGGC) forces strong hairpin and self-dimer scores.
        stem_loop = "GCCGCCTTTGGCGGC"
        candidates = scan_side(stem_loop + "AAAAA", 60.0, 18, 30, engine, "fwd")
        self.assertTrue(any(c["hairpin"]["score"] >= 40 for c in candidates))
        self.assertTrue(any("hairpin" in p
                            for c in candidates for p in c["penalties"]))
        self.assertTrue(any("self-dimer" in p
                            for c in candidates for p in c["penalties"]))

    def test_cross_dimer_penalty(self):
        engine = ThermoEngine(*primer3_probe.probe_primer3())
        pairs = build_pairs(
            [{"sequence": "ACGTACGTACGTACGT" + "GGGG", "penalties": [],
              "side": "forward"}],
            [{"sequence": "ACGTACGTACGTACGT" + "CCCC", "penalties": [],
              "side": "reverse"}],
            engine, product_size=100, top_n=5)
        self.assertTrue(pairs)
        self.assertTrue(pairs[0]["heterodimer"]["score"] >= 40)
        self.assertTrue(any("cross-dimer" in p for p in pairs[0]["penalties"]))
        self.assertEqual(pairs[0]["recommended"], "low")

    def test_recommendation_levels(self):
        engine = ThermoEngine(*primer3_probe.probe_primer3())
        good = scan_side("CGCGATATACGCGCGCGCCGCGCGCGCCGCGCGCGCCGCGCGCGC", 60.0,
                         18, 30, engine, "fwd")
        levels = {c["recommended"] for c in good}
        self.assertTrue(levels.issubset({"high", "medium", "low"}))
        # A perfectly balanced candidate should be high or medium, never
        # claim low without reasons.
        for candidate in good:
            if candidate["recommended"] == "low":
                self.assertTrue(candidate["penalties"])


class GibsonSeparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v07-gibson-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def test_binding_and_tail_separated(self):
        template = write_fa("CCCC" + "A" * 30 + "GGGG", self.dir)
        completed = run_cli(
            str(template), "--start", "1", "--end", "38",
            "--gibson", "--fwd-overlap", "ACGTACGTACGT",
            "--rev-overlap", "TGCATGCATGCA", "--json")
        payload = json.loads(completed.stdout)["data"]
        fwd = payload["forward"]
        self.assertTrue(fwd["sequence"].startswith("ACGTACGTACGT"))
        self.assertEqual(fwd["overlap"], "ACGTACGTACGT")
        self.assertEqual(fwd["overlap_length"], 12)
        self.assertEqual(fwd["binding"], fwd["sequence"][12:])
        rev = payload["reverse"]
        self.assertEqual(rev["overlap_tail"],
                         str(Seq("TGCATGCATGCA").reverse_complement()))
        # candidate-level fields carry tail/binding separation
        candidate = payload["forward_candidates"][0]
        self.assertEqual(candidate["tail"], "ACGTACGTACGT")
        self.assertEqual(candidate["sequence"], candidate["tail"] + candidate["binding"])

    def test_annealing_parameters_from_binding_not_tail(self):
        engine = ThermoEngine(*primer3_probe.probe_primer3())
        binding = "ATGCATGCATGCATGCATGCATG"
        plain = scan_side(binding, 60.0, 18, 30, engine, "fwd", tail="")
        tailed = scan_side(binding, 60.0, 18, 30, engine, "fwd",
                           tail="ACGTACGTACGT")
        self.assertEqual(plain[0]["tm"], tailed[0]["tm"])
        self.assertEqual(plain[0]["gc"], tailed[0]["gc"])
        self.assertEqual(plain[0]["end_stability_3p"],
                         tailed[0]["end_stability_3p"])

    def test_structural_checks_use_full_primer(self):
        engine = ThermoEngine(*primer3_probe.probe_primer3())
        binding = "ATGCATGCATGCATGCATGCATG"
        plain = scan_side(binding, 60.0, 18, 30, engine, "fwd", tail="")
        # A self-folding tail must change the full-primer structural scores
        # even though the binding region is identical.
        self_folding_tail = "GCCGCCTTTGGCGGC"
        tailed = scan_side(binding, 60.0, 18, 30, engine, "fwd",
                           tail=self_folding_tail)
        self.assertEqual(plain[0]["hairpin"]["score"], 0)
        self.assertGreaterEqual(tailed[0]["hairpin"]["score"], 40)
        self.assertNotEqual(plain[0]["self_dimer"]["score"],
                            tailed[0]["self_dimer"]["score"])

    def test_gibson_without_overlaps_fails(self):
        template = write_fa("CCCC" + "A" * 30 + "GGGG", self.dir)
        run_cli(str(template), "--gibson", "--json", expect_fail=True)
        run_cli(str(template), "--gibson", "--fwd-overlap", "ACGTACGTACGT",
                "--json", expect_fail=True)


class FailureAlarmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v07-fail-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = pathlib.Path(self.tmp.name)

    def test_invalid_region_fails(self):
        template = write_fa("ATGCATGCATGCATGCATGCATGC", self.dir)
        run_cli(str(template), "--start", "0", "--end", "10", "--json",
                expect_fail=True)
        run_cli(str(template), "--start", "20", "--end", "10", "--json",
                expect_fail=True)
        run_cli(str(template), "--start", "1", "--end", "999", "--json",
                expect_fail=True)

    def test_invalid_top_n_and_lengths_fail(self):
        template = write_fa("ATGCATGCATGCATGCATGCATGC", self.dir)
        run_cli(str(template), "--top-n", "0", "--json", expect_fail=True)
        run_cli(str(template), "--min-len", "30", "--max-len", "18", "--json",
                expect_fail=True)
        run_cli(str(template), "--primer3-timeout", "0", "--json",
                expect_fail=True)

    def test_unknown_site_fails(self):
        template = write_fa("ATGCATGCATGCATGCATGCATGC", self.dir)
        run_cli(str(template), "--fwd-site", "NoSuchEnzyme", "--json",
                expect_fail=True)

    def test_bad_overlap_bases_fail(self):
        template = write_fa("ATGCATGCATGCATGCATGCATGC", self.dir)
        run_cli(str(template), "--gibson", "--fwd-overlap", "ACGTACGTACGT",
                "--rev-overlap", "TGCATGCATZCA", "--json", expect_fail=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
