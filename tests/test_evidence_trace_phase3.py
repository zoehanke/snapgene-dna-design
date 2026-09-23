"""Change provenance, conservative judgments and non-interference."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evidence_trace.recorder import Recorder, project
from evidence_trace.chain import build_chains
from evidence_trace.impact import JUDGMENTS, ACTIONS, run_changes, comparison_identity, assess_impacts
from evidence_trace.runtime import traced_run, observe


class ChangeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.r = Recorder(self.path)
        self.r.ingest({"nodes": [
            {"id": "R", "kind": "requirement", "text": "Reporter design"},
            {"id": "S", "kind": "source", "title": "Supplied test material", "source_type": "user-material"},
            {"id": "E", "kind": "statement", "text": "Test observation", "source_id": "S", "context": {"host": "E. coli"}},
            {"id": "C", "kind": "claim", "text": "Proposed reporter use", "context": {"host": "E. coli"}},
            {"id": "D", "kind": "decision", "text": "Select reporter", "rationale": "Recorded choice", "responds_to": ["R"], "claim_ids": ["C"]},
            {"id": "U", "kind": "claim", "text": "Unlinked and unspecified"},
            {"id": "I", "kind": "claim", "text": "Scoped sequence-only claim", "depends_on_fields": ["sequence"], "dependency_scope_complete": True}]})
        self.r.link({"statement_id": "E", "claim_id": "C", "relation": "support"})

    def test_revision_is_append_only_and_never_rewrites_claim_or_validation(self):
        self.r.record({"id": "V", "kind": "validation", "check": "fixture context check", "result": True,
                       "decision_ids": ["D"], "depends_on_fields": ["host"]}, runtime=True)
        before = (self.path / "events.jsonl").read_bytes()
        old = copy.deepcopy(project(self.r.events)["nodes"])
        self.r.record({"id": "C", "kind": "claim", "text": "Proposed reporter use", "context": {"host": "S. cerevisiae"}})
        graph = build_chains(project(self.r.events))
        change = graph["changes"][0]
        self.assertEqual((change["from_revision"], change["to_revision"], change["changed_field"]), ("C@1", "C@2", "context.host"))
        self.assertEqual((change["old_value"], change["new_value"]), ("E. coli", "S. cerevisiae"))
        self.assertTrue(change["recorded_at"])
        self.assertTrue((self.path / "events.jsonl").read_bytes().startswith(before))
        by = {n["key"]: n for n in graph["nodes"]}
        for n in old:
            self.assertEqual(by[n["key"]], n)
        results = {i["target"]: i for i in graph["impacts"]}
        self.assertEqual(results["D@1"]["judgment"], "AFFECTED")
        self.assertIn("REASSESS", results["D@1"]["actions"])
        self.assertIn("RERUN", results["V@1"]["actions"])
        self.assertIs(by["V@1"]["result"], True)
        self.assertEqual(results["U@1"]["judgment"], "UNKNOWN")
        self.assertEqual(results["I@1"]["judgment"], "UNAFFECTED")
        ap = next(i for i in graph["impacts"] if i["target_kind"] == "applicability")
        self.assertIn("RECHECK", ap["actions"])
        self.assertTrue(all(i["judgment"] in JUDGMENTS and set(i["actions"]) <= ACTIONS for i in graph["impacts"]))

    def test_run_association_only_is_possible_dependency(self):
        self.r.record({"id": "V", "kind": "validation", "check": "unknown-scope check", "result": True, "decision_ids": ["D"]}, runtime=True)
        self.r.record({"id": "C", "kind": "claim", "text": "Proposed reporter use", "context": {"host": "other"}})
        results = {i["target"]: i for i in build_chains(project(self.r.events))["impacts"]}
        self.assertEqual(results["V@1"]["judgment"], "NEEDS REVIEW")
        self.assertNotIn("RERUN", results["V@1"]["actions"])

    def test_complete_scope_must_not_hide_contradictory_edges(self):
        self.r.record({"id": "X", "kind": "decision", "text": "Declared independent", "claim_ids": ["C"],
                       "depends_on_fields": ["sequence"], "dependency_scope_complete": True})
        self.r.record({"id": "C", "kind": "claim", "text": "Proposed reporter use", "context": {"host": "other"}})
        x = next(i for i in build_chains(project(self.r.events))["impacts"] if i["target"] == "X@1")
        self.assertEqual(x["judgment"], "NEEDS REVIEW")

    def test_missing_vs_null_and_text_changes_keep_values(self):
        self.r.record({"id": "C", "kind": "claim", "text": "Updated statement", "context": {"host": "E. coli", "medium": None}})
        changes = project(self.r.events)["changes"]
        medium = next(c for c in changes if c["changed_field"] == "context.medium")
        self.assertFalse(medium["old_present"])
        self.assertTrue(medium["new_present"])
        self.assertIsNone(medium["new_value"])
        self.assertTrue(any(c["changed_field"] == "text" for c in changes))

    def test_run_comparison_is_explicit_idempotent_and_directional(self):
        for rid, end in [("first", 720), ("second", 723)]:
            self.r.run_id = rid
            self.r.append("run_started", {"route": "pipeline", "context_refs": ["D@1", "R@1"], "decision_refs": ["D@1"]})
            self.r.append("design_choice_observed", {"choice": {"id": "o"+rid, "subject": "step:pcr", "input_path": "params.end", "parameter": "end", "value": end}})
            self.r.append("run_finished", {"status": "delivered"})
        self.assertEqual(len(self.r.compare_runs("first", "second")), 1)
        before = (self.path / "events.jsonl").read_bytes()
        self.assertEqual(self.r.compare_runs("first", "second"), [])
        self.assertEqual(before, (self.path / "events.jsonl").read_bytes())
        with self.assertRaises(ValueError):
            self.r.compare_runs("second", "first")

    def test_legacy_events_render_without_backfilled_changes(self):
        before = (self.path / "events.jsonl").read_bytes()
        self.r.render()
        self.assertEqual(build_chains(project(self.r.events))["changes"], [])
        self.assertEqual(before, (self.path / "events.jsonl").read_bytes())

    def test_observed_product_change_reuses_existing_anchors(self):
        before = {"id": "first", "stages": [{"event_type": "stage_completed", "stage": "execute",
                   "result": {"product_sequence_sha256": "old-recorded-anchor", "topology": "linear"}}]}
        after = {"id": "second", "stages": []}
        self.assertEqual(run_changes(before, after), [])
        after["stages"] = [{"event_type": "stage_completed", "stage": "execute",
                            "result": {"product_sequence_sha256": "new-recorded-anchor", "topology": "linear"}}]
        changes = run_changes(before, after)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["changed_field"], "product.sequence")
        self.assertEqual(changes[0]["old_value"], "old-recorded-anchor")

    def test_automatic_baseline_distinguishes_tasks(self):
        def run(task_id):
            return {"stages": [{"event_type": "stage_completed", "stage": "task",
                    "result": {"task_id": task_id, "task_kind": "composite_pipeline"}}]}
        self.assertNotEqual(comparison_identity(run("a")), comparison_identity(run("b")))
        self.assertIsNone(comparison_identity({"stages": []}))

    def test_missing_observation_does_not_prove_a_design_change(self):
        before = {"id": "a", "stages": []}
        after = {"id": "b", "stages": [{"event_type": "design_choice_observed", "choice": {
            "id": "o", "subject": "task", "input_path": "host", "parameter": "host", "value": "E. coli"}}]}
        changes = run_changes(before, after)
        self.assertEqual(changes[0]["basis"], "observation_coverage")
        graph = project(self.r.events)
        graph["changes"] = changes
        self.assertTrue(all(i["judgment"] == "UNKNOWN" for i in assess_impacts(graph)))

    def test_normal_impact_failure_does_not_change_task(self):
        calls = []
        @traced_run("test")
        def run(out_dir):
            calls.append(1)
            return observe("execute", lambda: {"status": "original"})
        with patch("evidence_trace.impact.assess_impacts", side_effect=ValueError("impact failed")):
            self.assertEqual(run(self.path / "out", trace=True), {"status": "original"})
        self.assertEqual(calls, [1])

    def test_impact_failure_preserves_real_authoritative_files(self):
        from agent.pipeline_agent import execute_agent_pipeline
        template = Path(__file__).resolve().parents[1] / "fixtures/synthetic/pSynthetic-GFP.gb"
        def run(out, **options):
            return execute_agent_pipeline("impact-fault", [
                {"step_id": "reverse", "tool": "reverse_complement", "params": {"seq": "$src"}},
                {"step_id": "restore", "tool": "reverse_complement", "params": {"seq": "$reverse"}}],
                [{"source_id": "src", "path": str(template)}], product_topology="circular",
                out_dir=out, user_confirmed=True, **options)
        off, on = self.path / "off", self.path / "on"
        with patch("evidence_trace.runtime.get_level", return_value="off"):
            self.assertEqual(run(off)["status"], "delivered")
        with patch("evidence_trace.impact.assess_impacts", side_effect=ValueError("impact failure")):
            self.assertEqual(run(on, trace=True)["status"], "delivered")
        for ext in ("gb", "dna", "fasta"):
            self.assertEqual((off / f"authoritative/construct.{ext}").read_bytes(), (on / f"authoritative/construct.{ext}").read_bytes())


if __name__ == "__main__":
    unittest.main()
