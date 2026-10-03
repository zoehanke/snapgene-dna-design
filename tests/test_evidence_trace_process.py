"""Actual public submission/capture paths, including adversarial organization and absent context."""

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

from evidence_trace.recorder import Recorder, load_events
from evidence_trace.projection import build_facts
from evidence_trace.process import organize, save_report_plan, assemble
from evidence_trace.intake import observe_material, record_handoff
from evidence_trace.runtime import trace_file_call, TraceStopped

ROOT = SKILL_ROOT


def packet(recorder):
    facts = build_facts(recorder.events)
    refs = list(facts["canonical_record_refs"])
    return {"schema_version": "trace-organization-v1", "id": "ORG", "basis": {
        k: facts["snapshot"][k] for k in ("trace_id", "through_sequence")},
        "design_process": {"stages": [{"id": "stage", "title": "准备构建", "purpose": "落实输入要求",
                            "step_ids": ["requirement"], "source_refs": ["R@1"]}],
            "steps": {"requirement": {"kind": "requirement", "content": "用户要求保留源序列",
                                      "source_refs": ["R@1"]}},
            "relations": [], "paths": [], "unresolved": [], "detail_refs": refs},
        "report_plan": {"profile": "research-report-v1", "title": "真实记录组织测试", "sections": [],
                        "diagram": {"reading_order": ["requirement"], "relation_refs": [], "short_labels": {}}}}


class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="trace-process-中文-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"SNAPGENE_TRACE_CONFIG": str(self.root / "settings.json")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.r = Recorder(self.root / "trace")
        self.r.record({"id": "R", "kind": "requirement", "text": "保留源序列"})

    def cli(self, *args, expected=0):
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(ROOT / "scripts/trace_design.py"),
                                 *args, "--trace-dir", str(self.r.directory)], cwd=ROOT,
                                capture_output=True, encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout) if result.stdout else None

    def test_cli_snapshot_organization_and_rebuild_are_bound_and_repeatable(self):
        data = self.cli("inspect", "--data")
        self.assertEqual(data["snapshot"]["trace_id"], self.r.trace_id)
        p = packet(self.r)
        path = self.root / "组织.json"
        path.write_text(json.dumps(p, ensure_ascii=False), encoding="utf-8")
        result = self.cli("organize", "--input", str(path))
        self.assertEqual(result["process_ref"], "ORG@1")
        log = (self.r.directory / "events.jsonl").read_bytes()
        html = (self.r.directory / "index.html").read_bytes()
        self.cli("render")
        self.assertEqual(log, (self.r.directory / "events.jsonl").read_bytes())
        self.assertEqual(html, (self.r.directory / "index.html").read_bytes())
        graph = json.loads((self.r.directory / "graph.json").read_text(encoding="utf-8"))
        self.assertEqual(graph["schema_version"], "design-process-v2")
        self.assertEqual(graph["snapshot"]["organization_status"], "current")
        self.assertFalse(graph["coverage"]["unassigned_refs"])
        self.assertTrue((self.r.directory / "report.md").is_file())

    def test_no_authored_result_is_honestly_absent(self):
        graph = self.r.render()
        self.assertIsNone(graph["design_process"])
        self.assertEqual(graph["snapshot"]["organization_status"], "absent")
        self.assertTrue(graph["report"]["steps"])
        self.assertNotIn("AI 的三项", (self.r.directory / "index.html").read_text(encoding="utf-8"))

    def test_missing_future_and_forged_runtime_values_rejected_without_append(self):
        for edit in (lambda p: p["design_process"]["steps"]["requirement"].update(source_refs=["unknown@1"]),
                     lambda p: p["design_process"]["steps"]["requirement"].update(kind="artifact"),
                     lambda p: p["design_process"]["steps"]["requirement"].update(kind="choice"),
                     lambda p: p["design_process"]["steps"]["requirement"].update(result="PASS"),
                     lambda p: p["basis"].update(through_sequence=100),
                     lambda p: p["design_process"].update(steps={}),
                     lambda p: p["design_process"]["stages"][0].update(branches={}),
                     lambda p: p["report_plan"].update(sections={}),
                     lambda p: p["report_plan"]["diagram"].update(short_labels=[]),
                     lambda p: p["report_plan"].update(profile="arbitrary-html")):
            with self.subTest(edit=edit):
                value = packet(self.r)
                edit(value)
                before = (self.r.directory / "events.jsonl").read_bytes()
                with self.assertRaises(ValueError):
                    organize(self.r, value)
                self.assertEqual(before, (self.r.directory / "events.jsonl").read_bytes())

    def test_new_facts_make_organization_stale_report_changes_do_not(self):
        old = packet(self.r)
        ref = organize(self.r, old)
        save_report_plan(self.r, ref, {"title": "另一种读法"})
        self.assertEqual(assemble(self.r.events)["snapshot"]["organization_status"], "current")
        self.r.record({"id": "R", "kind": "requirement", "text": "还要保留引物"})
        graph = self.r.render()
        self.assertEqual(graph["snapshot"]["organization_status"], "stale")
        self.assertIsNotNone(graph["report"]["historical_process"])
        self.assertTrue(all(not s["authored"] for s in graph["report"]["steps"]))
        newest = organize(self.r, packet(self.r))
        organize(self.r, old)
        self.assertEqual(assemble(self.r.events)["snapshot"]["organization_ref"], newest)

    def test_original_quote_vs_later_summary_and_unknown_event_preserved(self):
        note = self.root / "原文.txt"
        note.write_text("第一行\n保留源序列\n第三行\n", encoding="utf-8-sig")
        ref = observe_material(self.r, {"kind": "local_text", "path": str(note), "start_line": 2, "end_line": 2})
        with self.assertRaisesRegex(ValueError, "reserved"):
            self.r.record({"id": "forged", "kind": "requirement", "text": "不同的原话", "observed_quote_ref": ref})
        self.r.record({"id": "R2", "kind": "requirement", "text": "保留源序列",
                       "requirement_source": {"reference": ref, "form": "verbatim"}})
        with self.assertRaisesRegex(ValueError, "match"):
            self.r.record({"id": "R3", "kind": "requirement", "text": "删除源序列",
                           "requirement_source": {"reference": ref, "form": "verbatim"}})
        unknown = self.r.append("future_observation", {"custom": [1, 2, 3]})["event_id"]
        p = packet(self.r)
        p["design_process"]["detail_refs"] = []
        p["design_process"]["steps"]["requirement"]["reason"] = {
            "text": "事后新解释", "origin": "original_statement", "source_refs": [ref]}
        with self.assertRaisesRegex(ValueError, "match"):
            organize(self.r, p)
        p["design_process"]["steps"]["requirement"]["reason"]["origin"] = "later_interpretation"
        organize(self.r, p)
        graph = assemble(self.r.events)
        self.assertIn(unknown, graph["coverage"]["unassigned_refs"])
        self.assertEqual(graph["source_records"][unknown]["payload"]["custom"], [1, 2, 3])
        self.assertTrue(any(r["kind"] == "quotes_from" for r in graph["fact_relations"]))

    def test_file_operation_handoff_in_place_and_presence_only(self):
        source = self.root / "源.txt"
        source.write_text("before", encoding="utf-8")
        calls = []
        def edit():
            calls.append(1)
            source.write_text("after", encoding="utf-8")
            return str(source)
        value = trace_file_call("edit", edit, input_paths=[source], expected_paths=[source],
                               output_paths=lambda x: [x], trace_dir=self.r.directory)
        self.assertEqual(value, str(source))
        self.assertEqual(calls, [1])
        self.r = Recorder(self.r.directory)
        a = next(n for n in assemble(self.r.events)["nodes"] if n["kind"] == "artifact")
        self.assertEqual(a["generation_observation"], "modified")
        self.assertNotEqual(a["input_files"][0]["sha256"], a["sha256"])
        self.assertEqual(record_handoff(self.r, [{"path": str(source)}])["files"][0]["status"], "linked")
        source.write_text("outside change", encoding="utf-8")
        self.assertEqual(record_handoff(self.r, [{"path": str(source)}])["files"][0]["status"], "changed")
        other = self.root / "unchanged.txt"
        other.write_text("exists", encoding="utf-8")
        trace_file_call("no-edit", lambda: str(other), expected_paths=[other], output_paths=lambda x: [x], trace_dir=self.r.directory)
        self.r = Recorder(self.r.directory)
        self.assertEqual(record_handoff(self.r, [{"path": str(other)}])["files"][0]["status"], "untraced")

    def test_failed_file_operation_does_not_promote_residual(self):
        residual = self.root / "partial.txt"
        def fail():
            residual.write_text("partial", encoding="utf-8")
            raise RuntimeError("actual failure")
        with self.assertRaisesRegex(RuntimeError, "actual failure"):
            trace_file_call("failure", fail, expected_paths=[residual], output_paths=lambda x: [residual], trace_dir=self.r.directory)
        r = Recorder(self.r.directory)
        self.assertFalse([n for n in assemble(r.events)["nodes"] if n["kind"] == "artifact"])
        self.assertEqual(record_handoff(r, [{"path": str(residual)}])["files"][0]["status"], "untraced")

    def test_competing_writer_normal_continues_strict_stops_before_core(self):
        self.r.acquire()
        self.addCleanup(self.r.release)
        calls = []
        fn = lambda: calls.append(1) or "ok"
        self.assertEqual(trace_file_call("lock", fn, trace_dir=self.r.directory), "ok")
        with self.assertRaises(TraceStopped):
            trace_file_call("lock", fn, trace_dir=self.r.directory, trace_mode="strict")
        self.assertEqual(calls, [1])

    def test_focus_keeps_context_and_historical_cutoff_excludes_later_facts(self):
        old = packet(self.r)
        organize(self.r, old)
        self.r.record({"id": "R-new", "kind": "requirement", "text": "后来新增的要求"})
        graph = assemble(self.r.events, through_sequence=old["basis"]["through_sequence"])
        self.assertNotIn("R-new@1", graph["source_records"])
        self.assertEqual(graph["snapshot"]["organization_status"], "current")
        self.assertEqual(graph["design_process"]["steps"]["requirement"]["source_refs"], ["R@1"])
        self.r.run_id = "one"
        self.r.append("run_started", {"decision_refs": [], "context_refs": ["R@1"], "event_count_at_start": len(self.r.events)})
        self.r.append("run_finished", {"status": "finished"})
        focused = self.cli("reader", "--run-id", "one")
        self.assertIn("R-new@1", focused["source_records"])
        self.assertIn("R@1", focused["source_records"])
        self.assertEqual(focused["focus"]["run_id"], "one")

    def test_html_only_format_and_untrusted_text_do_not_create_active_markup(self):
        p = packet(self.r)
        p["report_plan"]["title"] = '</script><img src=x onerror="alert(1)">'
        organize(self.r, p)
        self.cli("render", "--format", "html")
        graph = json.loads((self.r.directory / "graph.json").read_text(encoding="utf-8"))
        self.assertEqual(graph["report"]["available_formats"], ["html"])
        html = (self.r.directory / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('</script><img', html)
        self.assertIn('\\u003c/script>', html)

    def test_declared_relationship_does_not_become_program_proof(self):
        self.r.record({"id": "D", "kind": "decision", "text": "保留输入", "responds_to": ["R"]})
        facts = build_facts(self.r.events)
        declared = [r for r in facts["fact_relations"] if r["kind"] == "responds_to"]
        self.assertTrue(declared)
        self.assertTrue(all(r["origin"] == "declared" for r in declared))


if __name__ == "__main__":
    unittest.main()
