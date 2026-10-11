"""Reader mapping contracts; simulated facts here, actual DNA A/B in capture tests."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import copy
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
from evidence_trace.reader import reader_for_run
from evidence_trace.runtime import observe, traced_run

ROOT = SKILL_ROOT


class ReaderTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)
        env = patch.dict(os.environ, {"SNAPGENE_TRACE_CONFIG": str(self.path / "config.json")})
        env.start()
        self.addCleanup(env.stop)
        self.r = Recorder(self.path / "trace")

    def request(self):
        return self.r.record({"id": "R", "kind": "requirement", "text": "比较候选",
            "requirement_source": {"reference": "message-1", "form": "verbatim", "excerpt": "比较候选"},
            "context": {"research_question": "研究问题原文", "task_goal": "制备比较材料"}})

    def decision(self, name="D", **extra):
        return self.r.record({"id": name, "kind": "decision", "text": "采用记录中的制备路线", "responds_to": ["R"], **extra})

    def begin(self, rid):
        context = self.r.select_context()
        nodes = project(self.r.events)["nodes"]
        self.r.run_id = rid
        self.r.append("run_started", {"decision_refs": [n["key"] for n in nodes if n["key"] in context and n["kind"] == "decision"],
            "context_refs": context, "event_count_at_start": len(self.r.events), "route": "test"})

    def end(self, status="finished"):
        self.r.append("run_finished", {"status": status})
        self.r.run_id = None

    def check(self, name, value, event=None):
        event = event or self.r.append("stage_completed", {"stage": "validate", "result": {name: value}})
        return self.r.record({"id": name + str(len(self.r.events)), "kind": "validation", "check": name,
            "result": value, "result_event_ref": event["event_id"], "association_scope": "same_run"}, runtime=True)

    def artifact(self, name, path, event, role="authoritative", content="recorded-content"):
        return self.r.record({"id": name, "kind": "artifact", "path": str(path), "relative_path": "authoritative/" + Path(path).name,
            "sha256": content, "role": role, "result_event_ref": event["event_id"]}, runtime=True)

    def reader(self):
        return build_chains(project(self.r.events))["reader"]

    def test_source_types_and_empty_sections_are_not_fabricated(self):
        self.request()
        self.decision("AI", decision_actor="ai", decision_source={"reference": "response-1"},
                      rationale="公开原始理由", explanation_origin="ai_concurrent")
        self.decision("U", decision_actor="user", decision_source={"reference": "message-2"})
        self.decision("unknown")
        reader = self.reader()
        steps = {s["id"]: s for s in reader["steps"]}
        self.assertEqual(steps["record:R@1"]["kind"], "requirement")
        self.assertEqual(steps["record:AI@1"]["label"], "AI 选择")
        self.assertEqual(steps["record:U@1"]["label"], "用户选择")
        self.assertEqual(steps["record:unknown@1"]["label"], "选择者未记录")
        self.assertNotIn("reason", steps["record:unknown@1"].get("branches", {}))
        self.assertFalse(reader["review"])
        self.assertFalse(reader["runs"])
        self.assertEqual(reader["context"][0]["background"]["research_question"], "研究问题原文")
        self.assertFalse(any(e["kind"] == "causes" for e in reader["relations"]))

    def test_user_change_links_exact_old_requirement(self):
        self.request()
        self.r.record({"id": "R", "kind": "requirement", "text": "更新后的要求", "request_action": "change",
            "requirement_source": {"reference": "message-2", "form": "summary"}, "basis_refs": ["R@1"]})
        reader = self.reader()
        self.assertEqual(len(reader["steps"]), 2)
        self.assertTrue(any(e["kind"] == "revision" and e["from"] == "record:R@1" and e["to"] == "record:R@2"
                            for e in reader["relations"]))

    def test_declared_user_basis_does_not_require_an_extra_paper_chain(self):
        self.request()
        self.r.record({"id": "C", "kind": "claim", "text": "用户明确限定了比较对象", "basis_refs": ["R@1"]})
        self.decision(claim_ids=["C"])
        reader = self.reader()
        self.assertFalse(reader["review"])
        decision = next(s for s in reader["steps"] if s["id"] == "record:D@1")
        self.assertIn("C@1", decision["branches"]["basis_refs"])

    def test_observed_no_decision_has_inputs_checks_and_output_without_forced_review(self):
        from evidence_trace.settings import set_level
        set_level("observed")
        @traced_run("test")
        def run(out_dir):
            def prepare(method="inverse_pcr"):
                return {"status": "calculated"}
            observe("recipe_execute", prepare)
            observe("validate", lambda: {"goal_valid": True})
            output = out_dir / "authoritative/construct.dna"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"reader test artifact")
            return {"status": "delivered", "delivery": {"file": str(output)}}
        run(self.path / "out", trace_dir=self.r.directory)
        self.r = Recorder(self.r.directory)
        reader = self.reader()
        self.assertFalse(any(s["kind"] == "choice" for s in reader["steps"]))
        self.assertTrue(any(s.get("phase") == "submitted_inputs" for s in reader["steps"]))
        self.assertTrue(any(s.get("checks") for s in reader["steps"]))
        # Original bytes and caller status stay unchanged. A filename and a
        # simulated "delivered" return do not establish a Core-checked DNA file.
        # Actual receipt-backed nested delivery is tested independently in
        # test_toolkit_trace_boundaries; this fixture remains the negative case.
        self.assertFalse(any(s.get("role") == "authoritative" for s in reader["steps"]))
        self.assertTrue(any(s.get("role") == "intermediate-or-candidate" for s in reader["steps"]))
        self.assertFalse(reader["review"])
        self.assertEqual(reader["runs"][0]["context"], [])
        self.assertTrue(reader["diagnostics"]["coverage_gaps"])

    def test_repeated_identical_calls_have_separate_input_anchors(self):
        @traced_run("test")
        def run(out_dir):
            def prepare(method="inverse_pcr"):
                return {"status": "calculated"}
            observe("recipe_execute", prepare)
            observe("recipe_execute", prepare)
        run(self.path / "out", trace_dir=self.r.directory)
        self.r = Recorder(self.r.directory)
        reader = self.reader()
        inputs = [s for s in reader["steps"] if s.get("phase") == "submitted_inputs"]
        self.assertEqual(len(inputs), 2)
        self.assertNotEqual(inputs[0]["id"], inputs[1]["id"])
        self.assertTrue(all(s["position"]["basis"] == "stage_reference" for s in inputs))
        self.assertEqual(len([e for e in reader["relations"] if e["kind"] == "stage_result"]), 2)

    def test_partial_decision_capture_does_not_hide_other_observed_inputs(self):
        self.request()
        self.decision(targets={"method": "inverse_pcr"})
        @traced_run("test")
        def run(out_dir):
            def prepare(method="inverse_pcr", start=6):
                return {"status": "calculated"}
            return observe("recipe_execute", prepare)
        run(self.path / "out", trace_dir=self.r.directory)
        self.r = Recorder(self.r.directory)
        reader = self.reader()
        inputs = [o for s in reader["steps"] for o in s.get("details", {}).get("observations", [])]
        self.assertTrue(any(o["parameter"] == "start" for o in inputs))
        self.assertFalse(any(o["parameter"] == "method" for o in inputs))
        self.assertTrue(reader["diagnostics"]["association_gaps"])

    def test_checks_are_grouped_once_and_not_requested_check_is_details_only(self):
        self.request()
        self.decision("D1")
        self.decision("D2")
        self.begin("a")
        event = self.r.append("stage_completed", {"stage": "validate", "result": {}})
        self.check("goal_valid", True, event)
        self.check("artifact_valid", False, event)
        omitted = self.check("requested_components", "not_requested")
        self.end()
        reader = self.reader()
        checks = [s for s in reader["steps"] if s.get("checks")]
        self.assertEqual(len(checks), 1)
        self.assertEqual(len(checks[0]["checks"]), 2)
        self.assertFalse(any(omitted in s["record_refs"] for s in reader["steps"]))
        self.assertEqual(len(reader["review"]), 1)
        self.assertEqual(reader["review"][0]["step_id"], checks[0]["id"])
        self.assertFalse(any(e["kind"] == "proves" for e in reader["relations"]))

    def test_late_evidence_and_supplement_do_not_rewrite_old_run_view(self):
        self.request()
        self.r.record({"id": "C", "kind": "claim", "text": "候选判断"})
        self.decision(claim_ids=["C"], targets={"method": "inverse_pcr"})
        self.begin("old")
        self.check("goal_valid", True)
        self.end()
        self.r.record({"id": "S", "kind": "source", "title": "材料", "source_type": "user-material"})
        self.r.record({"id": "E", "kind": "statement", "text": "有限依据", "source_id": "S"})
        self.r.link({"statement_id": "E", "claim_id": "C", "relation": "support"})
        self.r.explain({"decision_ref": "D@1", "basis_refs": ["C@1"], "text": "事后辅助说明"})
        self.begin("new")
        start = self.r.append("stage_started", {"stage": "recipe_execute", "input": {"kwargs": {"method": "inverse_pcr"}}})
        self.r.append("stage_completed", {"stage": "recipe_execute", "stage_ref": start["event_id"], "result": {}})
        self.check("goal_valid", True)
        self.end()
        reader = self.reader()
        old, new = (reader_for_run(reader, rid) for rid in ("old", "new"))
        before = next(s for s in old["steps"] if s["id"] == "record:D@1")
        after = next(s for s in new["steps"] if s["id"] == "record:D@1")
        self.assertNotIn("evidence", before["branches"])
        self.assertNotIn("supplements", before["branches"])
        self.assertNotIn("observed_inputs", before["branches"])
        self.assertTrue(after["branches"]["observed_inputs"])
        self.assertNotIn("reason", after["branches"])
        self.assertEqual(after["branches"]["supplements"][0]["label"], "事后辅助解释")
        self.assertTrue(old["review"])
        self.assertFalse(new["review"])

    def test_later_change_is_history_not_old_run_knowledge(self):
        self.request()
        self.decision()
        self.begin("old")
        self.check("goal_valid", True)
        self.end()
        self.r.record({"id": "R", "kind": "requirement", "text": "新要求", "context": {"host": "new host"}})
        self.begin("new")
        self.check("goal_valid", True)
        self.end()
        reader = self.reader()
        before = reader_for_run(reader, "old")
        self.assertFalse(any(s.get("branches", {}).get("changes") for s in before["steps"]))
        self.assertFalse(any(item["category"] == "change" for group in before["review"] for item in group["items"]))
        self.assertTrue(any(s.get("branches", {}).get("changes") for s in reader["steps"]))

    def test_twenty_conditional_links_keep_aspects_and_one_review_group(self):
        self.request()
        self.r.record({"id": "S", "kind": "source", "title": "原始来源", "source_type": "paper"})
        self.r.record({"id": "E", "kind": "statement", "text": "报告结果", "source_id": "S"})
        self.r.record({"id": "C", "kind": "claim", "text": "当前判断"})
        self.decision(claim_ids=["C"])
        for i in range(20):
            self.r.link({"statement_id": "E", "claim_id": "C", "relation": "oppose" if i % 2 else "support",
                         "aspect": f"方面{i}", "limitations": [f"限制{i}"]})
        reader = self.reader()
        d = next(s for s in reader["steps"] if s["id"] == "record:D@1")
        self.assertEqual(len(d["branches"]["evidence"]), 20)
        self.assertEqual(len({b["aspect"] for b in d["branches"]["evidence"]}), 20)
        self.assertEqual(len(reader["review"]), 1)
        self.assertFalse(any(s["kind"] in {"source", "claim", "statement"} for s in reader["steps"]))

    def test_file_formats_group_but_runs_and_generations_never_merge(self):
        for rid in ("a", "b"):
            self.begin(rid)
            event = self.r.append("stage_completed", {"stage": "finalize", "result": {}})
            for ext in ("dna", "gb", "fasta"):
                self.artifact(rid + ext, self.path / rid / f"construct.{ext}", event)
            self.end("delivered")
        reader = self.reader()
        artifacts = [s for s in reader["steps"] if s["kind"] == "artifact"]
        self.assertEqual(len(artifacts), 2)
        self.assertTrue(all(len(s["files"]) == 3 for s in artifacts))
        self.assertNotEqual(artifacts[0]["title"], artifacts[1]["title"])
        self.assertFalse(any(e["kind"] == "produced" and e["from"] == artifacts[0]["id"] for e in reader["relations"]))

    def test_same_filename_new_generation_in_one_run_is_distinguishable(self):
        self.begin("a")
        for i in range(2):
            event = self.r.append("stage_completed", {"stage": "finalize", "result": {}})
            self.artifact(str(i), self.path / "construct.dna", event, content=str(i))
        self.end("delivered")
        artifacts = [s for s in self.reader()["steps"] if s["kind"] == "artifact"]
        self.assertEqual(len(artifacts), 2)
        self.assertNotEqual(artifacts[0]["title"], artifacts[1]["title"])

    def test_ambiguous_material_record_is_not_resolved_by_guessing(self):
        self.begin("a")
        for i in range(2):
            event = self.r.append("stage_completed", {"stage": "execute", "result": {}})
            self.artifact(str(i), self.path / "same.gb", event, role="intermediate-or-candidate")
        self.end()
        self.begin("b")
        start = self.r.append("stage_started", {"stage": "recipe_execute", "input": {
            "template": {"source_path": str(self.path / "same.gb"), "source_sha256": "recorded-content"}}})
        self.r.append("stage_completed", {"stage": "recipe_execute", "stage_ref": start["event_id"], "result": {}})
        self.end()
        reader = self.reader()
        self.assertFalse(any(e["kind"] == "input_reference" for e in reader["relations"]))
        self.assertEqual(len(reader["diagnostics"]["material_reference_gaps"]), 1)

    def test_candidate_is_visible_but_does_not_become_formal_delivery(self):
        self.begin("a")
        event = self.r.append("stage_completed", {"stage": "execute", "result": {}})
        self.r.record({"id": "candidate", "kind": "artifact", "path": str(self.path / "candidate/construct.dna"),
            "relative_path": "candidate/construct.dna", "sha256": "recorded-content", "role": "intermediate-or-candidate",
            "result_event_ref": event["event_id"]}, runtime=True)
        self.end("candidate")
        reader = self.reader()
        self.assertEqual(next(s for s in reader["steps"] if s["kind"] == "artifact")["delivery_state"], "not_authoritative")
        self.assertFalse(reader["runs"][0]["authoritative_output_recorded"])

    def test_late_conflict_does_not_leak_through_grouped_review_refs(self):
        self.request()
        self.r.record({"id": "S", "kind": "source", "title": "source", "source_type": "paper"})
        self.r.record({"id": "E", "kind": "statement", "source_id": "S", "text": "statement"})
        self.r.record({"id": "C", "kind": "claim", "text": "claim"})
        self.decision(claim_ids=["C"])
        self.r.link({"statement_id": "E", "claim_id": "C", "relation": "support"})
        self.begin("a")
        self.end()
        self.r.link({"statement_id": "E", "claim_id": "C", "relation": "oppose", "aspect": "later evidence"})
        self.begin("b")
        self.end()
        reader = self.reader()
        self.assertFalse(reader_for_run(reader, "a")["review"])
        self.assertEqual(len(reader_for_run(reader, "b")["review"]), 1)

    def test_intermediate_material_is_promoted_only_with_a_known_reference(self):
        self.begin("a")
        event = self.r.append("stage_completed", {"stage": "execute", "result": {}})
        used = self.artifact("used", self.path / "used.gb", event, role="intermediate-or-candidate")
        unused = self.artifact("unused", self.path / "unused.gb", event, role="intermediate-or-candidate")
        self.end("candidate")
        self.begin("b")
        start = self.r.append("stage_started", {"stage": "recipe_execute", "input": {
            "template": {"source_path": str(self.path / "used.gb"), "source_sha256": "recorded-content"}}})
        self.r.append("stage_completed", {"stage": "recipe_execute", "stage_ref": start["event_id"], "result": {}})
        self.end()
        reader = self.reader()
        self.assertTrue(any(used in s["record_refs"] for s in reader["steps"]))
        self.assertFalse(any(unused in s["record_refs"] for s in reader["steps"]))
        self.assertTrue(any(e["kind"] == "input_reference" for e in reader["relations"]))
        selected = reader_for_run(reader, "b")
        self.assertTrue(any(used in s["record_refs"] and s["reference_only"] for s in selected["related_steps"]))
        self.assertFalse(any(used in s["record_refs"] for s in selected["steps"]))

    def test_orphan_runtime_records_remain_visible_without_inventing_run(self):
        self.check("goal_valid", True)
        reader = self.reader()
        self.assertFalse(reader["runs"])
        self.assertEqual(len(reader["steps"]), 1)
        self.assertEqual(reader["steps"][0]["association_scope"], "unscoped")

    def test_projection_is_deterministic_and_does_not_modify_facts(self):
        self.request()
        self.decision()
        before_events = copy.deepcopy(self.r.events)
        before_bytes = (self.r.directory / "events.jsonl").read_bytes()
        first, second = self.reader(), self.reader()
        self.assertEqual(first, second)
        first["steps"][0]["title"] = "only mutate returned view"
        self.assertEqual(self.r.events, before_events)
        self.assertEqual((self.r.directory / "events.jsonl").read_bytes(), before_bytes)

    def test_cli_reader_is_read_only_and_run_filter_rejects_unknown(self):
        self.request()
        self.begin("a")
        self.check("goal_valid", True)
        self.end()
        before = (self.r.directory / "events.jsonl").read_bytes()
        args = [sys.executable, "-X", "utf8", "-B", str(ROOT / "scripts/trace_design.py"), "reader",
                "--trace-dir", str(self.r.directory), "--run-id", "a"]
        done = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)["runs"][0]["id"], "a")
        self.assertEqual((self.r.directory / "events.jsonl").read_bytes(), before)
        self.assertFalse((self.r.directory / "index.html").exists())
        with self.assertRaises(ValueError):
            reader_for_run(self.reader(), "missing")

    def test_reader_failure_does_not_block_real_core_or_change_artifacts(self):
        from agent.pipeline_agent import execute_agent_pipeline
        template = ROOT / "fixtures/synthetic/pSynthetic-GFP.gb"
        def run(out):
            return execute_agent_pipeline("reader-fault", [
                {"step_id": "reverse", "tool": "reverse_complement", "params": {"seq": "$src"}},
                {"step_id": "restore", "tool": "reverse_complement", "params": {"seq": "$reverse"}}],
                [{"source_id": "src", "path": str(template)}], out_dir=out, product_topology="circular", user_confirmed=True)
        off, on = self.path / "off", self.path / "on"
        with patch("evidence_trace.runtime.get_level", return_value="off"):
            self.assertEqual(run(off)["status"], "delivered")
        with patch("evidence_trace.reader.build_reader", side_effect=ValueError("reader fault")):
            self.assertEqual(run(on)["status"], "delivered")
        for ext in ("dna", "gb", "fasta"):
            self.assertEqual((off / f"authoritative/construct.{ext}").read_bytes(), (on / f"authoritative/construct.{ext}").read_bytes())


if __name__ == "__main__":
    unittest.main()
