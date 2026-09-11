"""Evidence Trace contracts, real entry-point A/B and failure isolation."""
import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from Bio import SeqIO
from agent.pipeline_agent import execute_agent_pipeline
from evidence_trace.models import file_digest
from evidence_trace.recorder import Recorder, load_events, project
from evidence_trace.runtime import TraceStopped, observe, traced_run
from scripts.run_recipe import run_recipe_cli

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "tests/data/pBP-eGFP.gb"


def context():
    return {"actor": "researcher", "nodes": [
        {"id": "R1", "kind": "requirement", "text": "保留完整质粒并记录设计选择"},
        {"id": "S1", "kind": "source", "title": "Source supplied for contract test", "source_type": "user-material"},
        {"id": "E1", "kind": "statement", "text": "来源包含完整骨架", "source_id": "S1"},
        {"id": "C1", "kind": "claim", "text": "当前选择保留骨架"},
        {"id": "D1", "kind": "decision", "text": "选择完整来源", "rationale": "避免丢失骨架", "responds_to": ["R1"], "claim_ids": ["C1"], "decision_kind": "custom-kind"}],
        "links": [{"statement_id": "E1", "claim_id": "C1", "relation": "support", "strength": "strong",
                   "applicability": "direct", "conditions": ["provided record"], "limitations": ["not a phenotype measurement"]},
                  {"statement_id": "E1", "claim_id": "C1", "relation": "constrain", "strength": "partial",
                   "applicability": "extrapolated", "aspect": "other host", "limitations": ["not covered"]}]}


def pipeline(out, **trace):
    return execute_agent_pipeline("trace-ab", [
        {"step_id": "reverse", "tool": "reverse_complement", "params": {"seq": "$source"}},
        {"step_id": "restore", "tool": "reverse_complement", "params": {"seq": "$reverse"}}],
        [{"source_id": "source", "path": str(TEMPLATE)}], out_dir=out,
        product_topology="circular", user_confirmed=True, **trace)


def read_graph(directory):
    events, errors = load_events(directory)
    return project(events, errors)


class TraceRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="trace-中文-")
        self.addCleanup(self.temp.cleanup)
        self.path = pathlib.Path(self.temp.name)

    def test_revisions_links_and_rebuild_do_not_rewrite_history(self):
        r = Recorder(self.path)
        r.ingest(context())
        before = (self.path / "events.jsonl").read_bytes()
        d = context()["nodes"][-1]
        r.record({**d, "text": "修改选择", "rationale": "changed"})
        g = r.render()
        self.assertEqual(g["latest"]["D1"], "D1@2")
        self.assertEqual(len([e for e in g["edges"] if "statement_id" in e]), 2)
        self.assertTrue((self.path / "events.jsonl").read_bytes().startswith(before))
        original = (self.path / "graph.json").read_bytes()
        (self.path / "graph.json").unlink()
        (self.path / "index.html").unlink()
        r.render()
        self.assertEqual(original, (self.path / "graph.json").read_bytes())

    def test_verified_source_requires_receipt_but_does_not_verify_claim(self):
        r = Recorder(self.path)
        source = context()["nodes"][1]
        with self.assertRaisesRegex(ValueError, "receipt"):
            r.record({**source, "verification_status": "verified"})
        receipt = {"verifier": "human", "method": "manual", "checked_at": "2026-09-10", "locator": "local note", "scope": "identity only"}
        r.record({**source, "verification_status": "verified", "verification": receipt})
        r.record(context()["nodes"][3])
        g = r.render()
        claim = next(n for n in g["nodes"] if n["kind"] == "claim")
        self.assertNotIn("verification_status", claim)
        self.assertTrue(any(q["node"] == "C1@1" for q in g["review_queue"]))

    def test_public_ingestion_cannot_forge_runtime_records(self):
        r = Recorder(self.path)
        for kind in ("validation", "artifact"):
            with self.assertRaisesRegex(ValueError, "reserved"):
                r.ingest({"nodes": [{"id": "fake", "kind": kind, "result": "PASS"}]})
        with self.assertRaisesRegex(ValueError, "missing"):
            r.record(context()["nodes"][-1])

    def test_truncated_log_is_visible_and_cannot_be_silently_appended(self):
        r = Recorder(self.path)
        r.ingest(context())
        with (self.path / "events.jsonl").open("ab") as h:
            h.write(b'{"partial":')
        g = read_graph(self.path)
        self.assertEqual(g["integrity"], "incomplete")
        with self.assertRaisesRegex(ValueError, "damaged"):
            Recorder(self.path)

    def test_untrusted_html_is_inert(self):
        r = Recorder(self.path)
        r.record({"id": "R", "kind": "requirement", "text": '</script><img src=x onerror="alert(1)">中文'})
        r.render()
        html = (self.path / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('</script><img', html)
        self.assertIn('\\u003c/script>', html)


class TraceRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="trace-runtime-")
        self.addCleanup(self.temp.cleanup)
        self.path = pathlib.Path(self.temp.name)

    def assert_artifacts_equal(self, a, b):
        for suffix in ("gb", "fasta", "dna"):
            self.assertEqual((a / "authoritative" / f"construct.{suffix}").read_bytes(),
                             (b / "authoritative" / f"construct.{suffix}").read_bytes(), suffix)

    def test_pipeline_ab_real_files_and_runtime_records(self):
        a, b = self.path / "off", self.path / "on"
        with mock.patch("evidence_trace.runtime.get_level", return_value="off"):
            untraced = pipeline(a)
        self.assertFalse((a / "evidence-trace").exists())
        traced = pipeline(b, trace=True, trace_input=context())
        self.assertEqual(untraced["status"], traced["status"])
        self.assert_artifacts_equal(a, b)
        g = read_graph(b / "evidence-trace")
        self.assertEqual(g["integrity"], "complete", g["issues"])
        nodes = {n["key"]: n for n in g["nodes"]}
        artifacts = [n for n in nodes.values() if n["kind"] == "artifact" and n["role"] == "authoritative"]
        self.assertGreaterEqual(len(artifacts), 3)
        for artifact in artifacts:
            self.assertEqual(file_digest(artifact["path"]), artifact["sha256"])
            self.assertEqual(artifact["references"]["decision_ids"], ["D1@1"])
            self.assertTrue(artifact["references"]["validated_by"])
            self.assertTrue(all(nodes[k]["actor"] == "runtime" for k in artifact["references"]["validated_by"]))

    def test_recipe_ab_full_template_actual_pcr(self):
        params = {"template_seq_or_file": str(TEMPLATE), "start_0based": 198,
                  "end_0based": 201, "alt_seq": "CAT", "method": "inverse_pcr", "target_flank_bp": 25}
        a, b = self.path / "off", self.path / "on"
        original = copy.deepcopy(params)
        with mock.patch("evidence_trace.runtime.get_level", return_value="off"):
            run_recipe_cli("site_directed_mutagenesis", params, a, True, True)
        run_recipe_cli("site_directed_mutagenesis", params, b, True, True, trace=True, trace_input=context())
        self.assertEqual(params, original)
        self.assert_artifacts_equal(a, b)
        self.assertEqual((a / "primer_order_table.tsv").read_bytes(), (b / "primer_order_table.tsv").read_bytes())
        g = read_graph(b / "evidence-trace")
        self.assertEqual(g["runs"][0]["status"], "delivered")
        self.assertTrue(any(n["kind"] == "validation" for n in g["nodes"]))
        self.assertFalse(any(s.get("stage") == "plan" for s in g["runs"][0]["stages"]))

    def test_runs_freeze_decision_revision(self):
        trace = self.path / "history"
        r = Recorder(trace)
        r.ingest(context())
        pipeline(self.path / "first", trace_dir=trace)
        r = Recorder(trace)
        r.record({**context()["nodes"][-1], "text": "第二次选择", "rationale": "new design choice"})
        pipeline(self.path / "second", trace_dir=trace)
        g = read_graph(trace)
        self.assertEqual([r["decision_refs"] for r in g["runs"]], [["D1@1"], ["D1@2"]])

    def test_initialization_failure_normal_continues_strict_stops(self):
        bad = self.path / "not-a-directory"
        bad.write_text("keep", encoding="utf-8")
        self.assertEqual(pipeline(self.path / "normal", trace_dir=bad)["status"], "delivered")
        with self.assertRaises(TraceStopped):
            pipeline(self.path / "strict", trace_dir=bad, trace_mode="strict")
        self.assertFalse((self.path / "strict/authoritative").exists())
        self.assertEqual(bad.read_text(), "keep")

    def test_append_and_render_failures_normal_preserve_core_result(self):
        for failure in ("append", "render"):
            with self.subTest(failure=failure), mock.patch.object(Recorder, failure, side_effect=OSError("disk unavailable")):
                result = pipeline(self.path / failure, trace=True)
                self.assertEqual(result["status"], "delivered")
                self.assertTrue((self.path / failure / "authoritative/construct.dna").exists())

    def test_strict_render_failure_preserves_already_delivered_files(self):
        with mock.patch.object(Recorder, "render", side_effect=[None, OSError("view failed")]):
            with self.assertRaises(TraceStopped):
                pipeline(self.path / "strict-render", trace=True, trace_input=context(), trace_mode="strict")
        self.assertTrue((self.path / "strict-render/authoritative/construct.dna").exists())

    def test_later_evidence_does_not_remove_old_run_review_gap(self):
        trace = self.path / "history"
        bundle = context()
        bundle["links"] = []
        r = Recorder(trace)
        r.ingest(bundle)
        pipeline(self.path / "first", trace_dir=trace)
        r = Recorder(trace)
        r.link(context()["links"][0])
        pipeline(self.path / "second", trace_dir=trace)
        g = read_graph(trace)
        self.assertTrue(any(q["reason"] == "判断缺少证据陈述" for q in g["runs"][0]["review_queue"]))
        self.assertFalse(any(q["reason"] == "判断缺少证据陈述" for q in g["runs"][1]["review_queue"]))

    def test_core_error_not_masked_and_trace_does_not_mutate_input(self):
        original = {"sequence": "ACGTACGTACGT", "nested": {"x": [1, 2]}}
        @traced_run("test")
        def action(out_dir):
            observe("test", lambda x: x, original)
            return observe("execute", lambda: (_ for _ in ()).throw(ValueError("core failure")))
        with mock.patch.object(Recorder, "append", side_effect=OSError("log failure")):
            with self.assertRaisesRegex(ValueError, "core failure"):
                action(self.path, trace=True)
        self.assertEqual(original, {"sequence": "ACGTACGTACGT", "nested": {"x": [1, 2]}})

    def test_failed_run_does_not_claim_historical_files_as_new_artifacts(self):
        historical = self.path / "authoritative/construct.gb"
        historical.parent.mkdir()
        historical.write_text("historical", encoding="utf-8")
        @traced_run("test-failure")
        def failed(out_dir):
            return {"status": "failed", "delivery": None,
                    "historical_outputs": [{"path": str(historical)}],
                    "task": {"sources": [{"path": str(historical)}]}}
        result = failed(self.path, trace=True, trace_input=context())
        self.assertEqual(result["status"], "failed")
        g = read_graph(self.path / "evidence-trace")
        self.assertFalse(any(n["kind"] == "artifact" for n in g["nodes"]))
        self.assertEqual(historical.read_text(), "historical")

    def test_trace_cli_records_and_renders_in_chinese_path(self):
        source = self.path / "输入.json"
        source.write_text(json.dumps(context(), ensure_ascii=False), encoding="utf-8")
        done = subprocess.run([sys.executable, "-X", "utf8", "-B", str(ROOT / "scripts/trace_design.py"),
                               "record", "--trace-dir", str(self.path / "记录"), "--input", str(source)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(pathlib.Path(json.loads(done.stdout)["view"]).exists())


if __name__ == "__main__":
    unittest.main()
