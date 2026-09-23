"""Global collection and supplied explanation provenance through public entry points."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from Bio import SeqIO

from evidence_trace.settings import get_level, set_level, settings_path
from evidence_trace.recorder import Recorder, project, load_events
from evidence_trace.coverage import extract_choices, match_choices
from evidence_trace.runtime import traced_run, observe, TraceStopped

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "fixtures/synthetic/pSynthetic-GFP.gb"


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="trace-capture-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        env = patch.dict(os.environ, {"SNAPGENE_TRACE_CONFIG": str(self.path / "中文设置/trace.json")})
        env.start()
        self.addCleanup(env.stop)

    def cli(self, script, *args):
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(ROOT / "scripts" / script), *map(str, args)],
                                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def decision(self, **changes):
        return {"id": "D", "kind": "decision", "text": "换 PGK1", "targets": {"component": "PGK1"},
                "rationale": "TEF1 太强", "decision_actor": "user", "explanation_origin": "user_statement",
                "decision_source": {"reference": "supplied-message-1", "excerpt": "换 PGK1，因为 TEF1 太强"}, **changes}

    def test_global_config_cli_and_off_no_record_directory(self):
        self.assertEqual(get_level(), "full")
        self.assertFalse(settings_path().exists())
        result = self.cli("trace_design.py", "config", "--set-level", "off")
        self.assertEqual(json.loads(result.stdout)["trace_level"], "off")
        self.cli("trace_design.py", "record", "--trace-dir", self.path / "无记录", "--input", "missing.json")
        self.assertFalse((self.path / "无记录").exists())
        self.assertEqual(get_level(), "off")

    def test_off_wins_over_legacy_flags_and_invalid_bundle(self):
        set_level("off")
        @traced_run("test")
        def run(out_dir):
            return {"original": True}
        self.assertEqual(run(self.path, trace=True, trace_dir=self.path / "never", trace_input="absent.json",
                             trace_mode="strict"), {"original": True})
        self.assertFalse((self.path / "never").exists())

    def test_observed_keeps_real_reason_and_separates_actor(self):
        set_level("observed")
        r = Recorder(self.path / "trace")
        r.record(self.decision(), actor="host-assistant")
        node = project(r.events)["nodes"][0]
        self.assertEqual(node["actor"], "host-assistant")
        self.assertEqual(node["provenance"]["decision_actor"], "user")
        self.assertEqual(node["provenance"]["explanation_label"], "用户说明")
        self.assertEqual(node["rationale"], "TEF1 太强")
        self.assertTrue(all(e["mode_at_capture"] == "observed" for e in r.events))

    def test_observed_missing_extra_rationale_is_not_original_explanation_failure(self):
        set_level("observed")
        r = Recorder(self.path / "trace")
        r.record({"id": "D", "kind": "decision", "text": "PGK1", "targets": {"feature": "PGK1"}})
        graph = project(r.events)
        c = match_choices(extract_choices({"feature": "PGK1"}), graph["nodes"])[0]
        self.assertEqual(c["target_match"], "matched")
        self.assertFalse(c["original_explanation_recorded"])
        self.assertEqual(c["explanation_provenance"][0]["decision_actor"], "unknown")
        self.assertFalse(any(q["reason"] == "缺少决策说明" for q in graph["review_queue"]))

    def test_full_ai_concurrent_and_missing_source_rejected(self):
        r = Recorder(self.path / "trace")
        d = self.decision(decision_actor="ai", explanation_origin="ai_concurrent")
        r.record(d, actor="host-assistant")
        self.assertEqual(project(r.events)["nodes"][0]["provenance"]["explanation_label"], "AI 当时说明")
        with self.assertRaises(ValueError):
            r.record({**d, "decision_source": {}})
        with self.assertRaises(ValueError):
            r.record({**d, "explanation_origin": "post_hoc_assistance"})

    def test_assistance_keeps_exact_revision_and_does_not_fill_original_gap(self):
        r = Recorder(self.path / "trace")
        r.record({"id": "D", "kind": "decision", "text": "边界选择", "targets": {"start": 6}})
        before = (r.directory / "events.jsonl").read_bytes()
        r.explain({"decision_ref": "D@1", "basis_refs": ["D@1"], "text": "记录只显示选择了坐标 6，不能还原当时理由。"})
        r.record({"id": "D", "kind": "decision", "text": "新边界", "targets": {"start": 9}})
        graph = project(r.events)
        self.assertTrue((r.directory / "events.jsonl").read_bytes().startswith(before))
        self.assertNotIn("rationale", graph["nodes"][0])
        self.assertEqual(graph["explanations"][0]["decision_ref"], "D@1")
        self.assertEqual(graph["explanations"][0]["label"], "事后辅助解释")
        self.assertFalse(match_choices(extract_choices({"start": 6}), graph["nodes"])[0]["original_explanation_recorded"])
        with self.assertRaises(ValueError):
            r.explain({"decision_ref": "D", "basis_refs": ["D@1"], "text": "cannot bind latest implicitly"})

    def test_capture_freezes_level_and_legacy_stays_unknown(self):
        r = Recorder(self.path / "trace")
        r.record(self.decision())
        set_level("observed")
        r.record(self.decision(text="same running capture"))
        self.assertTrue(all(e["mode_at_capture"] == "full" for e in r.events))
        next_capture = Recorder(r.directory)
        next_capture.record(self.decision(text="subsequent capture"))
        self.assertEqual(next_capture.events[-1]["mode_at_capture"], "observed")
        legacy = copy.deepcopy(r.events)
        for e in legacy:
            e.pop("mode_at_capture")
            e["payload"].pop("decision_actor", None)
            e["payload"].pop("explanation_origin", None)
        old = project(legacy)["nodes"][0]["provenance"]
        self.assertEqual((old["mode_at_capture"], old["decision_actor"], old["explanation_origin"]),
                         ("unknown", "unknown", "unknown"))

    def test_global_change_during_run_only_affects_next_run(self):
        @traced_run("test")
        def run(out_dir):
            set_level("off")
            return observe("execute", lambda: {"original": True})
        self.assertEqual(run(self.path / "first"), {"original": True})
        events, errors = load_events(self.path / "first/evidence-trace")
        self.assertFalse(errors)
        self.assertEqual(events[-1]["event_type"], "run_finished")
        self.assertTrue(all(e["mode_at_capture"] == "full" for e in events))
        run(self.path / "next", trace=True)
        self.assertFalse((self.path / "next/evidence-trace").exists())

    def test_bad_config_normal_continues_strict_stops(self):
        settings_path().parent.mkdir(parents=True)
        settings_path().write_text('{"trace_level":"typo"}', encoding="utf-8")
        @traced_run("test")
        def run(out_dir):
            return {"original": True}
        self.assertEqual(run(self.path), {"original": True})
        with self.assertRaises(TraceStopped):
            run(self.path, trace_mode="strict")

    def test_three_levels_preserve_real_pipeline_recipe_and_task_artifacts(self):
        from agent.pipeline_agent import execute_agent_pipeline
        from scripts.run_recipe import run_recipe_cli
        outputs = {}
        for level in ("off", "observed", "full"):
            set_level(level)
            pipeline = self.path / level / "pipeline"
            result = execute_agent_pipeline("capture-pcr", [{"step_id": "pcr", "tool": "prepare_pcr_fragment",
                "params": {"template": "$src", "start": 6, "end": 723, "name": "trace_fragment"}}],
                [{"source_id": "src", "path": str(TEMPLATE)}], out_dir=pipeline,
                product_topology="linear", user_confirmed=True)
            self.assertEqual(result["status"], "delivered")
            expected_fragment = str(SeqIO.read(str(TEMPLATE), 'genbank').seq[6:723])
            self.assertEqual(str(SeqIO.read(str(pipeline / 'authoritative/construct.dna'), 'snapgene').seq), expected_fragment)
            recipe = self.path / level / "recipe"
            run_recipe_cli("site_directed_mutagenesis", {"template_seq_or_file": str(TEMPLATE),
                "start_0based": 198, "end_0based": 201, "alt_seq": "CAT", "method": "inverse_pcr", "target_flank_bp": 25},
                recipe, True, True)
            task = self.path / level / "task"
            # The structured entry requires an explicit host, unlike the Pipeline API.
            answers = self.path / "answers.json"
            answers.write_text(json.dumps({"host": "Escherichia coli"}), encoding="utf-8")
            self.cli("run_construction_task.py", "--task-json", pipeline / "task.json", "--out-dir", task,
                     "--answers-json", answers, "--json")
            for route, out in (("pipeline", pipeline), ("recipe", recipe), ("task", task)):
                outputs[level, route] = out
                self.assertEqual((out / "evidence-trace/events.jsonl").exists(), level != "off")
                if level != "off":
                    events, errors = load_events(out / "evidence-trace")
                    self.assertFalse(errors)
                    self.assertTrue(all(e["mode_at_capture"] == level for e in events))
                    self.assertTrue(any(n["kind"] == "validation" for n in project(events)["nodes"]))
                    reader = json.loads((out / "evidence-trace/graph.json").read_text(encoding="utf-8"))["reader"]
                    formal = [s for s in reader["steps"] if s.get("role") == "authoritative"]
                    self.assertEqual(len(formal), 1, route)
                    self.assertEqual({Path(f["path"]).suffix for f in formal[0]["files"]}, {".dna", ".gb", ".fasta"})
                    self.assertTrue(any(s.get("checks") for s in reader["steps"]))
                    self.assertFalse(any(s["kind"] == "choice" for s in reader["steps"]))
                    self.assertFalse(reader["review"])
                    by_event = {e["event_id"]: e for e in events}
                    for node in project(events)["nodes"]:
                        if node["kind"] in {"validation", "artifact"}:
                            observed = by_event[node["result_event_ref"]]
                            self.assertEqual(observed["event_type"], "stage_completed")
                            self.assertEqual(observed["run_id"], node["run_id"])
                            self.assertEqual(node["association_scope"], "same_run")
        for route in ("pipeline", "recipe", "task"):
            baseline = outputs["off", route]
            for level in ("observed", "full"):
                for ext in ("gb", "dna", "fasta"):
                    rel = f"authoritative/construct.{ext}"
                    self.assertEqual((baseline / rel).read_bytes(), (outputs[level, route] / rel).read_bytes(), (level, route, ext))
                if route == "task":
                    # This entry exposes preparation in plan steps, not a separate order table.
                    a = json.loads((baseline / "result.json").read_text(encoding="utf-8"))
                    b = json.loads((outputs[level, route] / "result.json").read_text(encoding="utf-8"))
                    self.assertEqual(a["plan_summary"]["steps"], b["plan_summary"]["steps"])
                    for field in ("artifact_valid", "computation_valid", "goal_valid"):
                        self.assertEqual(a["validation"][field], b["validation"][field])
                else:
                    self.assertEqual((baseline / "primer_order_table.tsv").read_bytes(),
                                     (outputs[level, route] / "primer_order_table.tsv").read_bytes())


if __name__ == "__main__":
    unittest.main()
