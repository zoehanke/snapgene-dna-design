# -*- coding: utf-8 -*-
"""Release-iteration gates: layer-4 slide-retry, consent, transparency.

These tests implement the verification items of §8 in
release-iteration-requirements.md:

* informed-consent gate: no confirmation = no execution, confirmation
  executes;
* transparency gate: operation log carries backend / parameters / input SHA /
  retry path;
* slide-retry gate: A (tail), B (high-GC terminal), C (poly-G terminal
  alternative suggestions), with the real primer3_core when available.
"""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
ROOT = SKILL_ROOT
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

import primer_design_engine  # noqa: E402
from operation_consent import (  # noqa: E402
    ConsentBroker, ConsentRequiredError, TransparencyLog, make_request,
    operation_summary, sha256_prefix,
)

SLIDE_B_SEQUENCE = (
    "CACCCGGCCCGCGGCCGGGCCCCCTCACTGGCCGCCCGTCGCTCAGCGCGCCGCTCGGGGCGGCCA"
    "AGCCCGCCCGGGCCCCCGCGCCGCGGGCCTCGGCCGACCCGCGCGGGCGACCCGTGCTGCGCGGAG"
    "CGGCGGGCTGCCCGCGCGCGCCCCAGCCCCGGGTGGAGGCCAGCGGGGGGGGGGGGGGGGGGGCCG"
    "G")


def auto_consent():
    return ConsentBroker(policy="auto")


def slide_design_result():
    def cand(side, binding):
        return {
            "side": side, "binding": binding, "tail": "", "sequence": binding,
            "tm": 60.0, "gc": 50.0, "length": len(binding),
            "binding_length": len(binding), "bind_start": 0, "bind_end": 17,
            "boundary_offset": 2,
            "hairpin": {"tm": 0.0, "source": "primer3-core"},
            "self_dimer": {"tm_any": 0.0, "tm_3p": 0.0,
                           "source": "primer3-core"},
            "heterodimer": None,
            "end_stability_3p": {"value": 0.0, "source": "primer3-core"},
            "product_size": 100, "primer3_penalty": 0.0, "penalties": [],
            "recommended": "high",
        }
    fwd = cand("forward", "ACGTACGTACGTACGTAC")
    rev = cand("reverse", "TGCATGCATGCATGCATG")
    return {
        "forward_candidates": [fwd], "reverse_candidates": [rev],
        "pairs": [{
            "rank": 1, "forward_index": 0, "reverse_index": 0,
            "product_size": 100, "primer3_product_size_with_overhangs": 100,
            "actual_product_size": 100, "boundary_offset_5p": 2,
            "boundary_offset_3p": 3, "heterodimer": {"tm_any": 0.0},
            "weight": 0.0, "primer3_penalty": 0.0, "recommended": "high"}],
        "explain": {"left": "considered 3, ok 1",
                    "right": "considered 3, ok 1", "pair": "ok 1"},
        "returned_pairs": 1, "accepted_pairs": 1, "mode": "slide",
        "slide_budget": 25,
    }


def no_pair_design_result():
    return {"forward_candidates": [], "reverse_candidates": [], "pairs": [],
            "explain": {"left": "considered 10, GC content failed 10, ok 0",
                        "right": "considered 10, GC content failed 10, ok 0",
                        "pair": "considered 0, ok 0"},
            "returned_pairs": 0, "accepted_pairs": 0,
            "mode": "exact-boundary", "slide_budget": 0}


AVAILABLE_PROBE = {
    "status": "available", "backend": "primer3-core", "path": "p3",
    "version": "2.6.1", "detail": None}


class ConsentBrokerTests(unittest.TestCase):
    def test_ask_without_callback_or_tty_does_not_execute(self):
        broker = ConsentBroker(policy="ask")
        with self.assertRaises(ConsentRequiredError):
            broker.request(make_request("relax-gc", "relaxation", "放宽 GC"))
        self.assertEqual(broker.pending()[0]["operation"], "relax-gc")

    def test_deny_callback_blocks_execution(self):
        broker = ConsentBroker(policy="ask",
                               confirm_callback=lambda request: False)
        with self.assertRaises(ConsentRequiredError):
            broker.request(make_request("relax-gc", "relaxation", "放宽 GC"))
        self.assertTrue(any(entry["operation"] == "relax-gc"
                            and not entry["approved"]
                            for entry in broker.log.entries))

    def test_approve_callback_executes(self):
        broker = ConsentBroker(policy="ask",
                               confirm_callback=lambda request: True)
        decision = broker.request(make_request("relax-gc", "relaxation", "x"))
        self.assertTrue(decision["approved"])
        self.assertEqual(decision["source"], "programmable-callback")

    def test_auto_policy_is_explicit_and_recorded(self):
        broker = ConsentBroker(policy="auto")
        decision = broker.request(make_request("degrade", "degradation", "x"))
        self.assertTrue(decision["approved"])
        self.assertEqual(decision["source"], "auto-confirm")
        self.assertTrue(any(entry["operation"] == "degrade"
                            for entry in broker.log.entries))

    def test_invalid_policy_and_bytes_sha_and_pre_approved(self):
        with self.assertRaises(ValueError):
            ConsentBroker(policy="other")
        self.assertEqual(len(sha256_prefix(b"ACGT")), 16)
        broker = ConsentBroker(policy="ask",
                               pre_approved=("pre-ok",))
        decision = broker.request(make_request("pre-ok", "relaxation", "x"))
        self.assertEqual(decision["source"], "pre-approved")
        self.assertTrue(decision["approved"])
        self.assertEqual(operation_summary(broker.log.entries)[0].split()[0],
                         broker.log.entries[0]["timestamp"][11:19])
        self.assertEqual(operation_summary([]), [])


class PrimerEngineConsentGateTests(unittest.TestCase):
    def test_default_ask_blocks_before_any_design(self):
        with mock.patch.object(
                primer_design_engine, "probe_primer3_core",
                side_effect=AssertionError("probe must not run before consent")):
            with self.assertRaises(ConsentRequiredError) as caught:
                primer_design_engine.design_region_primers(
                    "ACGT" * 30, 0)
        self.assertEqual(
            caught.exception.request["operation"], "primer-design-parameters")

    def test_slide_relaxation_denied_means_no_slide_execution(self):
        calls = []

        def fake_design(core_path, sequence, region_start, target_tm, min_len,
                        max_len, top_n, fwd_tail="", rev_tail="", timeout=30,
                        tm_range=None, slide=False, slide_budget=None,
                        product_pad=100):
            calls.append(slide)
            return (slide_design_result() if slide
                    else no_pair_design_result())

        broker = ConsentBroker(
            policy="ask",
            confirm_callback=lambda request:
                request["operation"] != "slide-retry")
        with mock.patch.object(primer_design_engine, "probe_primer3_core",
                               return_value=AVAILABLE_PROBE), \
                mock.patch.object(primer_design_engine, "design_anchored_pairs",
                                  side_effect=fake_design):
            with self.assertRaises(ConsentRequiredError):
                primer_design_engine.design_region_primers(
                    "ACGT" * 60, 0, consent=broker)
        self.assertFalse(any(calls), "slide-retry must not execute after denial")

    def test_slide_relaxation_approved_executes_and_is_visible(self):
        broker = ConsentBroker(
            policy="ask",
            confirm_callback=lambda request:
                request["operation"] != "slide-retry" or True)
        with mock.patch.object(primer_design_engine, "probe_primer3_core",
                               return_value=AVAILABLE_PROBE), \
                mock.patch.object(
                    primer_design_engine, "design_anchored_pairs",
                    side_effect=lambda *a, **kw:
                        slide_design_result() if kw.get("slide")
                        else no_pair_design_result()):
            result = primer_design_engine.design_region_primers(
                "ACGT" * 60, 0, consent=broker)
        self.assertEqual(result["backend"], "primer3-core")
        self.assertIn("slide-retry", result["primer3_retry_note"])
        self.assertEqual(result["boundary_offsets"]["boundary_offset_5p"], 2)
        self.assertEqual(result["boundary_offsets"]["boundary_offset_3p"], 3)
        self.assertTrue(any(entry.get("operation") == "slide-retry"
                            and entry.get("approved")
                            for entry in result["operation_log"]))


class TransparencyGateTests(unittest.TestCase):
    def test_result_carries_backend_parameters_sha_and_retry_path(self):
        with mock.patch.object(primer_design_engine, "probe_primer3_core",
                               return_value=AVAILABLE_PROBE), \
                mock.patch.object(
                    primer_design_engine, "design_anchored_pairs",
                    side_effect=lambda *a, **kw:
                        slide_design_result() if kw.get("slide")
                        else no_pair_design_result()):
            result = primer_design_engine.design_region_primers(
                "ACGT" * 60, 0, consent=auto_consent())
        self.assertEqual(result["consent"]["broker_policy"], "auto")
        self.assertEqual(result["input_sequence"]["sha256_prefix"],
                         sha256_prefix("ACGT" * 60))
        ops = [entry.get("operation") for entry in result["operation_log"]]
        self.assertIn("backend-probe", ops)
        self.assertIn("primer3-attempt", ops)
        self.assertIn("primer3-attempt-success", ops)
        backend = next(entry for entry in result["operation_log"]
                       if entry.get("operation") == "backend-probe")
        self.assertEqual(backend["version"], "2.6.1")
        self.assertTrue(any(entry.get("attempt") == "slide-retry"
                            for entry in result["operation_log"]))

    def test_degradation_is_recorded_not_silent(self):
        with mock.patch.object(
                primer_design_engine, "probe_primer3_core",
                return_value={"status": "unavailable",
                              "backend": "primer3-core", "path": None,
                              "version": None, "detail": "no primer3"}):
            result = primer_design_engine.design_region_primers(
                "ACGT" * 60, 0, consent=auto_consent())
        self.assertEqual(result["backend"], "heuristic")
        self.assertIn("NOT Primer3",
                      result["forward_candidates"][0]["_backend_source"])
        self.assertTrue(any(entry.get("category") == "degradation"
                            for entry in result["operation_log"]))


class SlideRetryRealEngineTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("SNAPGENE_RUN_PRIMER3") == "1",
                         "set SNAPGENE_RUN_PRIMER3=1")
    def test_group_a_tail_case_binding_only(self):
        from Bio.Seq import Seq
        seq = ("AGAACGATTGCCCGCAACGC" + "ACGATCGTAGCT" * 100 +
               "TCGACGCAACCTTTCGTGCG")
        tail = str(Seq("TCGACGCAACCTTTCGTGCG").reverse_complement())
        result = primer_design_engine.design_region_primers(
            seq, 0, rev_tail=tail, top_n=1, consent=auto_consent())
        self.assertEqual(result["backend"], "primer3-core")
        self.assertIn("binding-only", result["primer3_retry_note"])
        self.assertEqual(result["reverse_candidates"][0]["sequence"][:len(tail)],
                         tail)

    @unittest.skipUnless(os.environ.get("SNAPGENE_RUN_PRIMER3") == "1",
                         "set SNAPGENE_RUN_PRIMER3=1")
    def test_group_b_high_gc_terminal_slide_retry(self):
        result = primer_design_engine.design_region_primers(
            SLIDE_B_SEQUENCE, 0, top_n=3, consent=auto_consent())
        self.assertEqual(result["backend"], "primer3-core")
        self.assertIn("slide-retry", result["primer3_retry_note"])
        self.assertTrue(0 <= result["boundary_offsets"]["boundary_offset_5p"] <= 25,
                        result["boundary_offsets"])
        self.assertTrue(0 <= result["boundary_offsets"]["boundary_offset_3p"] <= 25,
                        result["boundary_offsets"])
        for candidate in (result["forward_candidates"] +
                          result["reverse_candidates"]):
            self.assertLessEqual(candidate["boundary_offset"], 25)
            self.assertGreaterEqual(candidate["boundary_offset"], 0)
            self.assertTrue(20.0 <= candidate["gc"] <= 80.0,
                            "GC constraint must not be silently relaxed")

    @unittest.skipUnless(os.environ.get("SNAPGENE_RUN_PRIMER3") == "1",
                         "set SNAPGENE_RUN_PRIMER3=1")
    def test_group_c_poly_g_gives_actionable_alternatives(self):
        poly = "A" * 100 + "G" * 100
        result = primer_design_engine.design_region_primers(
            poly, 0, min_len=18, max_len=27, top_n=1,
            consent=auto_consent())
        self.assertTrue(result["primer3_failure"])
        actions = " | ".join(item["action"]
                             for item in result["alternatives"])
        self.assertIn("外扩 20-40", actions)
        self.assertIn("内部引物", actions)
        with self.assertRaises(primer_design_engine.Primer3CoreError) as caught:
            primer_design_engine.design_region_primers(
                poly, 0, min_len=18, max_len=27, top_n=1,
                require_primer3=True, consent=auto_consent())
        self.assertIn("alternatives=", str(caught.exception))


class CliConsentGateTests(unittest.TestCase):
    def _write_template(self, tmp):
        path = pathlib.Path(tmp) / "template.fa"
        seq = ("AGAACGATTGCCCGCAACGC" + "ACGATCGTAGCT" * 30 +
               "TCGACGCAACCTTTCGTGCG")
        path.write_text(">t\n%s\n" % seq, encoding="utf-8")
        return path

    def test_design_primers_ask_without_input_does_not_execute(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            template = self._write_template(tmp)
            completed = subprocess.run(
                [sys.executable, "-X", "utf8", "-B",
                 str(SCRIPTS / "design_primers.py"), str(template),
                 "--start", "1", "--end", "200", "--json",
                 "--consent", "ask"],
                input="", capture_output=True, text=True,
                encoding="utf-8", errors="replace")
        self.assertNotEqual(completed.returncode, 0)
        payload_text = (completed.stderr + completed.stdout)
        self.assertIn("CONSENT_REQUIRED", payload_text)
        self.assertIn("nothing was executed", payload_text)

    def test_plan_assembly_ask_blocks_construct_write_until_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            (tmp / "b.fa").write_text(
                ">b\n" + "ACGT" * 100 + "\n", encoding="utf-8")
            (tmp / "i.fa").write_text(
                ">i\n" + "TGCA" * 100 + "\n", encoding="utf-8")
            intent = tmp / "intent.json"
            intent.write_text(json.dumps({
                "backbone": {"source": 0},
                "fragments": [{"source": 1, "interval": [0, 200]}]}),
                encoding="utf-8")
            construct_stem = tmp / "construct"
            completed = subprocess.run(
                [sys.executable, "-X", "utf8", "-B",
                 str(SCRIPTS / "plan_assembly.py"), str(tmp / "b.fa"),
                 str(tmp / "i.fa"), "--intent-json", str(intent),
                 "--out-construct", str(construct_stem),
                 "--consent", "ask", "--json"],
                input="", capture_output=True, text=True,
                encoding="utf-8", errors="replace")
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(construct_stem.with_suffix(".gb").exists())
        self.assertIn("PENDING-CONFIRMATION",
                      (completed.stdout + completed.stderr))

    def test_design_primers_auto_consent_executes(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            template = self._write_template(tmp)
            completed = subprocess.run(
                [sys.executable, "-X", "utf8", "-B",
                 str(SCRIPTS / "design_primers.py"), str(template),
                 "--start", "1", "--end", "200", "--json",
                 "--consent", "auto"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)["data"]
        self.assertEqual(payload["consent"]["broker_policy"], "auto")
        self.assertTrue(payload["operation_log"])


class ScenarioCoverageGateTests(unittest.TestCase):
    def test_expanded_suite_meets_release_counts(self):
        sys.path.insert(0, str(SCRIPTS))
        from run_scenario_suite import scenarios as suite_scenarios
        items = suite_scenarios()
        counts = {}
        for item in items:
            key = None
            if item["kind"] == "plan":
                if item["intent"]["method"] == "gibson":
                    key = "gibson"
                elif item["intent"]["method"] == "overlap":
                    key = "overlap"
                elif item["intent"]["method"] == "digest-ligate":
                    key = "digest"
            elif item["kind"] == "golden_gate":
                key = "golden"
            elif item["kind"] == "pcr":
                if item.get("length", 0) > 5000:
                    key = "long"
                elif item.get("gc", 50) >= 70 or item.get("gc", 50) <= 30:
                    key = "high_gc_at"
            elif item["kind"] == "primer-retry":
                key = "retry"
            elif item["kind"] == "real-vector":
                key = "real"
            if key:
                counts[key] = counts.get(key, 0) + 1
        self.assertGreaterEqual(counts.get("gibson", 0), 3)
        self.assertGreaterEqual(counts.get("golden", 0), 3)
        self.assertGreaterEqual(counts.get("overlap", 0), 3)
        self.assertGreaterEqual(counts.get("high_gc_at", 0), 5)
        self.assertGreaterEqual(counts.get("long", 0), 3)
        self.assertGreaterEqual(counts.get("retry", 0), 10)
        self.assertGreaterEqual(counts.get("digest", 0), 3)
        self.assertGreaterEqual(counts.get("real", 0), 5)


class ParameterSourcesGateTests(unittest.TestCase):
    def test_parameter_source_file_covers_required_families(self):
        md = (ROOT / "references" /
              "biological-parameters-sources.md").read_text(encoding="utf-8")
        data = json.loads((ROOT / "references" /
                           "biological-parameters-sources.json").read_text(
                               encoding="utf-8"))
        for family in ("Tm", "primer-quality", "PCR", "assembly",
                       "restriction", "off-target", "feasibility"):
            self.assertTrue(any(item["family"] == family
                                for item in data["parameters"]))
            self.assertIn(family, md)
        for item in data["parameters"]:
            self.assertTrue(item["name"])
            self.assertTrue(item["default"])
            self.assertTrue(item["source"])
            self.assertTrue(item["source_url"])
            self.assertTrue(item["retrieved_at"])
            self.assertTrue(item["code_references"])
        p10 = next(x for x in data["parameters"] if x["id"] == "P10")
        self.assertIn("Q5", p10["default"])
        self.assertIn("Taq", p10["default"])
        self.assertNotIn("Tm - 3", p10["default"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
