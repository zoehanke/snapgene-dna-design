"""Phase 2: interpreted context stays separate from source/claim truth and Core."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from unittest import mock

from evidence_trace.applicability import assess, DIMENSIONS
from evidence_trace.chain import build_chains
from evidence_trace.coverage import extract_choices, match_choices
from evidence_trace.recorder import Recorder, project
from evidence_trace.runtime import observe, traced_run


FULL = {"organism": "Saccharomyces cerevisiae", "strain": "BY4741", "host": "S. cerevisiae",
        "construct_context": "episomal reporter", "temperature": "30 C", "medium": "YPD",
        "assay": "fluorescence", "intended_use": "laboratory expression"}


class ApplicabilityTests(unittest.TestCase):
    def test_direct_requires_declared_dimensions_not_verified_source(self):
        source, target = copy.deepcopy(FULL), copy.deepcopy(FULL)
        result = assess(source, target)
        self.assertEqual(result["status"], "direct")
        self.assertTrue(all(r["result"] == "MATCH" for r in result["dimensions"]))
        self.assertNotIn("verified", result)
        self.assertEqual(source, FULL)
        self.assertEqual(target, FULL)

    def test_partial_temperature_medium_missing_and_extrapolated_strain(self):
        for field, value, status in [("temperature", 37, "partial"), ("medium", "M9", "partial"),
                                     ("strain", None, "partial"), ("strain", "S288C", "extrapolated"),
                                     ("host", "E. coli", "extrapolated"), ("intended_use", "environmental use", "extrapolated")]:
            with self.subTest(field=field, value=value):
                result = assess(FULL, {**FULL, field: value})
                self.assertEqual(result["status"], status)
                self.assertTrue(result["needs_interpretation"])
                self.assertEqual(next(d for d in result["dimensions"] if d["dimension"] == field)["target"], value)

    def test_unknown_sparse_identity_and_invalid_temperature(self):
        self.assertEqual(assess({}, {})["status"], "unknown")
        self.assertEqual(assess({"temperature": 30}, {"temperature": 30})["status"], "unknown")
        for invalid in ("warm", float("nan"), {"min": 40, "max": 20}, {"value": 30, "unit": "K"}):
            result = assess(FULL, {**FULL, "temperature": invalid})
            self.assertEqual(next(r for r in result["dimensions"] if r["dimension"] == "temperature")["result"], "UNKNOWN")

    def test_ranges_units_and_alias_conflicts(self):
        self.assertEqual(assess(FULL, {**FULL, "host": "Saccharomyces cerevisiae"})["status"], "direct")
        self.assertEqual(assess(FULL, {**FULL, "temperature": "86°F"})["status"], "direct")
        result = assess({**FULL, "temperature": {"min": 25, "max": 32, "unit": "C"}}, FULL)
        self.assertEqual(result["status"], "partial")
        result = assess(FULL, {**FULL, "chassis": "contradictory host"})
        self.assertEqual(next(r for r in result["dimensions"] if r["dimension"] == "host")["result"], "UNKNOWN")

    def test_custom_relevance_scope_is_visible(self):
        result = assess(FULL, {**FULL, "medium": None}, ["host", "assay"])
        self.assertEqual(result["status"], "direct")
        self.assertEqual(result["required_dimensions"], ["host", "assay"])
        self.assertFalse(next(r for r in result["dimensions"] if r["dimension"] == "medium")["required"])


class CoverageTests(unittest.TestCase):
    def test_preflight_with_no_decisions_reports_gaps_without_writing_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            design = folder / "design.json"
            design.write_text(json.dumps({"method": "inverse_pcr", "start_0based": 198}), encoding="utf-8")
            done = subprocess.run([sys.executable, "-X", "utf8", "-B", str(Path(__file__).resolve().parents[1] / "scripts/trace_design.py"),
                "coverage", "--trace-dir", str(folder / "no-trace"), "--design-json", str(design)],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(done.returncode, 0, done.stderr)
            report = json.loads(done.stdout)
            self.assertEqual(report["explained"], 0)
            self.assertEqual(report["observed"], 2)
            self.assertFalse((folder / "no-trace").exists())

    def test_analysis_helper_is_not_a_scientific_design_choice(self):
        choices = extract_choices({"steps": [{"step_id": "stats", "tool": "calc_primer_tm", "params": {"primer_seq": "ACGT"}}]})
        self.assertFalse(any(c["parameter"] == "tool" for c in choices))

    def test_unexplained_does_not_create_decisions_or_rationale(self):
        design = {"pipeline": {"steps": [{"step_id": "pcr", "tool": "prepare_pcr_fragment",
                   "params": {"template": "source.gb", "start": 6, "end": 720}}]}, "product": {"topology": "linear"}}
        before = copy.deepcopy(design)
        result = match_choices(extract_choices(design), [])
        self.assertTrue(result)
        self.assertTrue(all(c["status"] == "unexplained design choice" for c in result))
        self.assertFalse(any("rationale" in c for c in result))
        self.assertEqual(design, before)

    def test_exact_weak_mismatch_and_custom_decision_kind(self):
        choices = extract_choices({"start_0based": 5, "end_0based": 20})
        decision = {"key": "D@1", "kind": "decision", "decision_kind": "arbitrary-new-kind",
                    "targets": {"start_0based": 5}, "rationale": "Recorded when selecting boundary"}
        result = match_choices(choices, [decision])
        self.assertEqual(result[0]["status"], "explained")
        self.assertEqual(result[1]["status"], "unexplained design choice")
        self.assertEqual(match_choices(choices, [{**decision, "targets": {"parameter": "start_0based"}}])[0]["status"], "needs review")
        self.assertEqual(match_choices(choices, [{**decision, "targets": {"start_0based": 6}}])[0]["status"], "unexplained design choice")
        self.assertEqual(match_choices(choices, [{**decision, "rationale": "  "}])[0]["status"], "needs review")

    def test_same_boundary_across_steps_requires_scope(self):
        choices = extract_choices({"steps": [{"step_id": "a", "params": {"start": 0}}, {"step_id": "b", "params": {"start": 0}}]})
        d = {"key": "D@1", "targets": {"start": 0}, "rationale": "real reason"}
        result = match_choices(choices, [d])
        self.assertTrue(all(c["status"] == "needs review" for c in result if c["parameter"] == "start"))
        result = match_choices(choices, [{**d, "targets": {"start": 0, "step_id": "a"}}])
        self.assertEqual(next(c for c in result if c["subject"] == "step:a")["status"], "explained")
        self.assertEqual(next(c for c in result if c["subject"] == "step:b")["status"], "unexplained design choice")


class ChainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.recorder = Recorder(self.path / "trace")
        self.recorder.ingest({"nodes": [
            {"id": "R", "kind": "requirement", "text": "GFP design"},
            {"id": "S", "kind": "source", "title": "Test-only source", "source_type": "user-material"},
            {"id": "E", "kind": "statement", "text": "Observed reporter", "source_id": "S", "context": FULL},
            {"id": "C", "kind": "claim", "text": "Proposed current expression", "context": {**FULL, "medium": "M9"}},
            {"id": "D", "kind": "decision", "text": "Choose candidate", "responds_to": ["R"], "claim_ids": ["C"], "rationale": "Actual recorded reason"}]})

    def test_twenty_conditional_links_remain_distinct_and_queue_groups_decision(self):
        for i in range(20):
            self.recorder.link({"statement_id": "E", "claim_id": "C", "relation": "support" if i % 2 else "constrain",
                                "aspect": f"aspect-{i}", "limitations": [f"limit-{i}"], "strength": "partial"})
        before = (self.path / "trace/events.jsonl").read_bytes()
        graph = build_chains(project(self.recorder.events))
        c = graph["chain_views"][0]["chains"][0]
        self.assertEqual(len(c["evidence"]), 20)
        self.assertTrue(all(e["assessment"]["status"] == "partial" for e in c["evidence"]))
        self.assertEqual(c["decision"], "D@1")
        from evidence_trace.render import render
        render(self.path / "trace", project(self.recorder.events))
        self.assertEqual(before, (self.path / "trace/events.jsonl").read_bytes())

    def test_phase2_projection_failure_is_sidecar_only(self):
        calls = []
        @traced_run("test")
        def work(out_dir):
            calls.append("ran")
            return observe("execute", lambda: {"status": "unchanged"})
        with mock.patch("evidence_trace.render.build_chains", side_effect=ValueError("chain error")):
            self.assertEqual(work(self.path / "out", trace_dir=self.path / "trace"), {"status": "unchanged"})
        self.assertEqual(calls, ["ran"])

    def test_legacy_log_projects_choices_without_rewriting_events(self):
        self.recorder.run_id = "old-run"
        self.recorder.append("run_started", {"decision_refs": ["D@1"], "context_refs": ["R@1", "C@1", "D@1"], "event_count_at_start": len(self.recorder.events)})
        self.recorder.append("stage_started", {"stage": "recipe_execute", "input": {"kwargs": {"method": "inverse_pcr", "start_0based": 198}}})
        self.recorder.append("run_finished", {"status": "candidate"})
        g = build_chains(project(self.recorder.events))
        self.assertEqual(g["chain_views"][0]["coverage"]["observed"], 2)
        self.assertEqual(g["chain_views"][0]["coverage"]["explained"], 0)

    def test_normal_phase2_failures_preserve_actual_authoritative_dna(self):
        from agent.pipeline_agent import execute_agent_pipeline
        template = Path(__file__).resolve().parent / "data/pBP-eGFP.gb"
        self.recorder.link({"statement_id": "E", "claim_id": "C", "relation": "support"})
        def run(out, **options):
            return execute_agent_pipeline("phase2-fault", [
                {"step_id": "reverse", "tool": "reverse_complement", "params": {"seq": "$src"}},
                {"step_id": "restore", "tool": "reverse_complement", "params": {"seq": "$reverse"}}],
                [{"source_id": "src", "path": str(template)}], out_dir=out,
                product_topology="circular", user_confirmed=True, **options)
        base = self.path / "off"
        with mock.patch("evidence_trace.runtime.get_level", return_value="off"):
            self.assertEqual(run(base)["status"], "delivered")
        for i, target in enumerate(("evidence_trace.coverage.extract_choices", "evidence_trace.chain.assess", "evidence_trace.render.build_chains")):
            with self.subTest(target=target), mock.patch(target, side_effect=RuntimeError("phase2 sidecar fault")) as patched:
                out = self.path / str(i)
                self.assertEqual(run(out, trace_dir=self.path / "trace")["status"], "delivered")
                self.assertTrue(patched.called)
                for ext in ("gb", "dna", "fasta"):
                    self.assertEqual((base / f"authoritative/construct.{ext}").read_bytes(), (out / f"authoritative/construct.{ext}").read_bytes())


if __name__ == "__main__":
    unittest.main()
