"""Source assertions, phase anchors and scoped associations; no reader implementation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from evidence_trace.chain import build_chains
from evidence_trace.recorder import Recorder, load_events, project
from evidence_trace.runtime import observe, traced_run, TraceStopped
from evidence_trace.settings import set_level

ROOT = Path(__file__).resolve().parents[1]


class ContextTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)
        config = patch.dict(os.environ, {"SNAPGENE_TRACE_CONFIG": str(self.path / "config.json")})
        config.start()
        self.addCleanup(config.stop)
        self.r = Recorder(self.path / "trace")

    def requirement(self, **kwargs):
        return {"id": "R", "kind": "requirement", "text": "保留相同表达背景",
                "requirement_source": {"reference": "user-message-1", "form": "verbatim", "excerpt": "保留相同表达背景"},
                "context": {"research_question": "比较候选", "task_goal": "生成可比较构建"}, **kwargs}

    def decision(self, **kwargs):
        return {"id": "D", "kind": "decision", "text": "采用顺序制备", "responds_to": ["R"],
                "targets": {"method": "inverse_pcr"}, **kwargs}

    def test_user_requirement_and_intervention_keep_submitter_and_old_reference(self):
        self.r.record(self.requirement(), actor="host-assistant")
        original = (self.r.directory / "events.jsonl").read_bytes()
        self.r.record(self.requirement(id="U", text="确认这一要求", request_action="confirm", basis_refs=["R@1"],
                         requirement_source={"reference": "user-message-2", "form": "summary"}), actor="host-assistant")
        g = project(self.r.events)
        request, intervention = g["nodes"]
        self.assertEqual(request["actor"], "host-assistant")
        self.assertEqual(request["provenance"]["origin"], "supplied_user_source")
        self.assertEqual(request["context"]["task_goal"], "生成可比较构建")
        self.assertEqual(intervention["basis_refs"], ["R@1"])
        self.assertEqual(g["basis_links"][0]["from"], "R@1")
        self.assertTrue((self.r.directory / "events.jsonl").read_bytes().startswith(original))

    def test_intervention_requires_source_and_exact_existing_basis(self):
        self.r.record(self.requirement())
        for fields in ({"basis_refs": ["R"]}, {"basis_refs": ["future@1"]}, {"basis_refs": []},
                       {"basis_refs": ["R@1"], "requirement_source": None}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.r.record(self.requirement(id="U", request_action="change", **fields))
        with self.assertRaises(ValueError):
            self.r.record(self.requirement(text="偷偷修改引文"))

    def test_decision_and_later_assistance_can_reference_a_program_event(self):
        self.r.record(self.requirement())
        event = self.r.append("stage_completed", {"stage": "inspect", "result": {"topology": "circular"}})
        self.r.record(self.decision(basis_refs=[event["event_id"]]))
        self.r.explain({"decision_ref": "D@1", "basis_refs": [event["event_id"]], "text": "仅根据已记录结果补充。"})
        g = project(self.r.events)
        self.assertEqual(g["basis_links"][0]["from"], event["event_id"])
        self.assertNotIn("rationale", g["nodes"][-1])
        self.assertTrue(g["explanation_gaps"])
        self.assertEqual(g["explanations"][0]["basis_refs"], [event["event_id"]])

    def test_observed_matching_without_extra_reason_is_not_a_review_item(self):
        set_level("observed")
        r = Recorder(self.r.directory)
        r.record(self.requirement())
        r.record(self.decision())
        @traced_run("test")
        def run(out_dir):
            def prepare(method="inverse_pcr"):
                return {"status": "candidate"}
            return observe("recipe_execute", prepare)
        run(self.path / "out", trace_dir=r.directory)
        g = build_chains(project(load_events(r.directory)[0]))
        self.assertFalse(g["review_queue"])
        self.assertFalse(g["explanation_gaps"])
        self.assertFalse(g["chain_views"][0]["chains"][0]["review"])
        method = next(o for o in g["chain_views"][0]["choices"] if o["parameter"] == "method")
        self.assertEqual(method["target_match"], "matched")
        self.assertFalse(method["original_explanation_recorded"])
        self.assertNotIn(method, g["chain_views"][0]["association_gaps"])

    def test_missing_requirements_decisions_are_coverage_not_log_failure(self):
        @traced_run("test")
        def run(out_dir):
            return observe("execute", lambda: {"status": "delivered"})
        run(self.path / "out")
        g = project(load_events(self.path / "out/evidence-trace")[0])
        self.assertEqual(g["integrity"], "complete")
        self.assertEqual(len(g["coverage_gaps"]), 2)
        self.assertFalse(g["issues"])
        self.assertFalse(g["review_queue"])
        unfinished = [e for e in g["audit_events"] if e["event_type"] != "run_finished"]
        self.assertEqual(project(unfinished)["integrity"], "incomplete")

    def test_one_matching_decision_does_not_promote_another_weak_association(self):
        self.r.record(self.requirement())
        self.r.record(self.decision())
        self.r.record(self.decision(id="weak", targets={"parameter": "method"}))
        self.r.run_id = "run"
        self.r.append("run_started", {"decision_refs": ["D@1", "weak@1"], "context_refs": ["R@1", "D@1", "weak@1"],
                                      "event_count_at_start": len(self.r.events)})
        self.r.append("stage_started", {"stage": "recipe_execute", "input": {"kwargs": {"method": "inverse_pcr"}}})
        self.r.append("run_finished", {"status": "finished"})
        view = build_chains(project(self.r.events))["chain_views"][0]
        self.assertFalse(view["association_gaps"])
        self.assertFalse(view["chains"][0]["association_gaps"])
        self.assertEqual(len(view["chains"][1]["association_gaps"]), 1)

    def test_not_requested_check_is_not_failure_and_false_is_not_hidden(self):
        self.r.record({"id": "N", "kind": "validation", "result": "not_requested"}, runtime=True)
        self.r.record({"id": "F", "kind": "validation", "result": False}, runtime=True)
        g = project(self.r.events)
        self.assertEqual([q["node"] for q in g["review_queue"]], ["F@1"])

    def test_stage_references_disambiguate_repeated_calls_and_bind_checks(self):
        @traced_run("test")
        def run(out_dir):
            def prepare(method="inverse_pcr"):
                return {"value": 1}
            observe("recipe_execute", prepare)
            observe("validate", lambda: {"goal_valid": True})
            observe("validate", lambda: {"goal_valid": False})
            return {"status": "finished"}
        run(self.path / "out")
        events, _ = load_events(self.path / "out/evidence-trace")
        by_id = {e["event_id"]: e for e in events}
        g = build_chains(project(events))
        validations = [n for n in g["nodes"] if n["kind"] == "validation"]
        self.assertEqual(len({n["result_event_ref"] for n in validations}), 2)
        for n in validations:
            result = by_id[n["result_event_ref"]]
            start = by_id[result["payload"]["stage_ref"]]
            self.assertEqual(start["event_type"], "stage_started")
            self.assertEqual(result["run_id"], n["run_id"])
            self.assertEqual(result["payload"]["result"]["goal_valid"], n["result"])
        observation = next(o for o in g["chain_views"][0]["choices"] if o["parameter"] == "method")
        self.assertEqual(observation["observation_phase"], "accepted_inputs_after_call")
        start = by_id[observation["stage_ref"]]
        self.assertLess(start["sequence"], observation["recorded_sequence"])
        self.assertEqual(start["payload"]["stage"], "recipe_execute")

    def test_failed_stage_keeps_actual_start_and_core_exception(self):
        @traced_run("test")
        def run(out_dir):
            return observe("execute", lambda: (_ for _ in ()).throw(ValueError("original failure")))
        with self.assertRaisesRegex(ValueError, "original failure"):
            run(self.path / "out")
        events, _ = load_events(self.path / "out/evidence-trace")
        failed = next(e for e in events if e["event_type"] == "stage_failed")
        start = next(e for e in events if e["event_id"] == failed["payload"]["stage_ref"])
        self.assertEqual(start["event_type"], "stage_started")
        self.assertEqual(project(events)["runs"][0]["status"], "failed")

    def test_explicit_scope_freezes_only_selected_decision_and_its_evidence(self):
        self.r.record(self.requirement())
        self.r.record({"id": "S", "kind": "source", "title": "supplied source", "source_type": "user-material"})
        self.r.record({"id": "E", "kind": "statement", "source_id": "S", "text": "reported context"})
        self.r.record({"id": "C", "kind": "claim", "text": "candidate basis"})
        self.r.link({"statement_id": "E", "claim_id": "C", "relation": "support"})
        self.r.record(self.decision(claim_ids=["C"]))
        self.r.record(self.decision(text="newer alternative"))
        @traced_run("test")
        def run(out_dir):
            return observe("validate", lambda: {"goal_valid": True})
        run(self.path / "out", trace_dir=self.r.directory, trace_input={"context_refs": ["D@1"]})
        g = project(load_events(self.r.directory)[0])
        self.assertEqual(g["runs"][0]["decision_refs"], ["D@1"])
        self.assertEqual(set(g["runs"][0]["context_refs"]), {"D@1", "R@1", "C@1", "E@1", "S@1"})
        v = next(n for n in g["nodes"] if n["kind"] == "validation")
        self.assertEqual(v["references"]["decision_ids"], ["D@1"])
        self.assertEqual(v["association_scope"], "same_run")
        with self.assertRaises(TraceStopped):
            run(self.path / "bad", trace_dir=self.r.directory, trace_input={"context_refs": ["D"]}, trace_mode="strict")

    def test_missing_scope_anchor_in_normal_mode_does_not_block_the_core(self):
        @traced_run("test")
        def run(out_dir):
            return {"status": "original"}
        result = run(self.path / "out", trace_input={"context_refs": ["absent@1"]})
        self.assertEqual(result, {"status": "original"})

    def test_legacy_projection_retains_unknown_source_and_original_bytes(self):
        self.r.record({"id": "R", "kind": "requirement", "text": "legacy"}, actor="user")
        self.r.run_id = "old-run"
        self.r.append("run_started", {"context_refs": ["R@1"], "decision_refs": [], "event_count_at_start": 1})
        self.r.append("stage_completed", {"stage": "execute", "result": {"status": "finished"}})
        self.r.append("run_finished", {"status": "finished"})
        old_bytes = (self.r.directory / "events.jsonl").read_bytes()
        g = build_chains(project(self.r.events))
        self.assertEqual(g["nodes"][0]["provenance"]["origin"], "unknown")
        self.assertNotIn("stage_ref", g["runs"][0]["stages"][0])
        self.assertEqual((self.r.directory / "events.jsonl").read_bytes(), old_bytes)

    def test_cli_inspect_exposes_source_context_and_separate_gaps(self):
        bundle = self.path / "要求.json"
        bundle.write_text(json.dumps({"actor": "host-assistant", "nodes": [self.requirement(), self.decision()]},
                                     ensure_ascii=False), encoding="utf-8")
        for action in ("record", "inspect"):
            args = [sys.executable, "-X", "utf8", "-B", str(ROOT / "scripts/trace_design.py"), action,
                    "--trace-dir", str(self.r.directory)]
            if action == "record":
                args += ["--input", str(bundle)]
            done = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT)
            self.assertEqual(done.returncode, 0, done.stderr)
        result = json.loads(done.stdout)
        self.assertEqual(result["requirement_provenance"][0]["origin"], "supplied_user_source")
        self.assertEqual(result["requirement_provenance"][0]["context"]["research_question"], "比较候选")
        self.assertTrue(result["explanation_gaps"])
        self.assertFalse(result["review_queue"])


if __name__ == "__main__":
    unittest.main()
