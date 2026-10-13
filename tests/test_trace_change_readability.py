"""Change/impact wording must keep the facts that identify what changed.

Inputs below independently construct source changes, omitted-sequence summaries
and declared/program file relations. Names, lengths and repeated-character digests
are synthetic constants; expected strings follow those constructions.
"""
import json
import hashlib
import io
import os
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from repository_paths import PROJECT_ROOT, SKILL_ROOT
from evidence_trace.report import readable_changes, markdown
from evidence_trace.recorder import Recorder, load_events
from evidence_trace.process import assemble
from evidence_trace.runtime import traced_run, observe_files


def change(cid, field, old, new, **extra):
    return {"id": cid, "changed_field": field, "old_value": old, "new_value": new,
            "old_present": True, "new_present": True, "recorded_at": "2026-10-02T00:00:00+00:00", **extra}


def impact(cid, target, judgment, actions=("NEEDS REVIEW",), reason="没有足够依赖信息；未找到关系不等于无关"):
    return {"change_id": cid, "target": target, "judgment": judgment, "actions": list(actions), "reason": reason}


class ChangeValueTests(unittest.TestCase):
    def render(self, old, new, field="sources.0.path"):
        graph = {"changes": [change("C1", field, old, new)], "impacts": []}
        return readable_changes(graph, {})[0]

    def test_replaced_material_file_shows_name_and_hash_not_a_placeholder(self):
        # Deliberate fictional Windows paths exercise cross-platform basename handling.
        old = {"source_path": "C:\\synthetic-fixture\\inputs\\template_alpha.gb", "source_sha256": "1" * 64}
        new = {"source_path": "C:\\synthetic-fixture\\build\\template_beta.gb", "source_sha256": "2" * 64}
        row = self.render(old, new)
        self.assertEqual(row["before"], "template_alpha.gb · sha256 11111111")
        self.assertEqual(row["after"], "template_beta.gb · sha256 22222222")
        self.assertNotEqual(row["before"], row["after"])
        self.assertNotIn("synthetic-fixture", row["before"])

    def test_omitted_sequence_shows_length_and_hash(self):
        old = {"omitted": "sequence", "length": 1001, "sha256": "3" * 64}
        new = {"omitted": "sequence", "length": 1103, "sha256": "4" * 64}
        row = self.render(old, new, "product.sequence")
        self.assertEqual(row["before"], "序列 1001 bp · sha256 33333333")
        self.assertEqual(row["after"], "序列 1103 bp · sha256 44444444")

    def test_scalars_lists_and_flat_dicts_stay_readable(self):
        self.assertEqual(self.render(4879, 5077, "fragments.1.end")["after"], "5077")
        self.assertEqual(self.render(["a", "b"], ["a", "c"], "x.items")["after"], "a, c")
        self.assertEqual(self.render({"value": 30, "unit": "C"}, {"value": 37, "unit": "C"}, "x.temperature")["after"], "37 C")
        self.assertEqual(self.render({"k": "v", "n": 2}, {"k": "w", "n": 2}, "x.map")["after"], "k=w；n=2")

    def test_long_text_is_cut_and_says_how_long_it_was(self):
        text = "x" * 400
        shown = self.render("short", text, "x.text")["after"]
        self.assertTrue(shown.endswith("（共 400 字符）"))
        self.assertLess(len(shown), 200)

    def test_unrecognised_nested_structure_still_falls_back(self):
        nested = {"a": {"b": [1, 2, {"c": 3}]}}
        self.assertIn("完整值见技术记录", self.render(nested, {"a": {}}, "x.deep")["before"])


class ImpactReportTests(unittest.TestCase):
    def minimal_report(self, details):
        return {"title": "t", "outcome_summary": None, "snapshot": {"organization_status": "current"},
                "context": None, "requirements": [], "stages": [], "steps": [], "artifacts": [], "checks": [],
                "unverified_scope": [], "review": [], "handoff": None, "recording_gaps": [],
                "change_details": details, "sources": {}}

    def test_impacts_carry_their_code_for_the_reader(self):
        graph = {"changes": [change("C1", "x.method", "a", "b")],
                 "impacts": [impact("C1", "R1@1", "UNKNOWN"), impact("C1", "R2@1", "AFFECTED", ("RERUN", "STALE"))]}
        impacts = readable_changes(graph, {})[0]["impacts"]
        self.assertEqual([i["code"] for i in impacts], ["UNKNOWN", "AFFECTED"])

    def test_markdown_lists_one_line_per_judgment_not_per_target(self):
        graph = {"changes": [change("C1", "x.method", "quikchange", "inverse_pcr")],
                 "impacts": [impact("C1", "R%d@1" % n, "UNKNOWN") for n in range(1, 5)]
                 + [impact("C1", "D9@1", "AFFECTED", ("RERUN",), "依赖该选择")]}
        sources = {"R%d@1" % n: {"title": "要求%d" % n} for n in range(1, 5)}
        sources["D9@1"] = {"title": "方案"}
        text = markdown(self.minimal_report(readable_changes(graph, sources)))
        self.assertIn("· 4 项：", text)
        for n in range(1, 5):
            self.assertIn("要求%d" % n, text)
        self.assertEqual(text.count("信息不足，影响未知"), 1)   # four unknown impacts share one line
        self.assertIn("明确受到影响", text)

    def test_original_records_are_not_altered_by_reporting(self):
        graph = {"changes": [change("C1", "x.method", "a", "b")], "impacts": [impact("C1", "R1@1", "UNKNOWN")]}
        before = repr(graph)
        readable_changes(graph, {})
        self.assertEqual(repr(graph), before)


class RelationStandingTests(unittest.TestCase):
    def renderer_edges(self, report):
        source = (SKILL_ROOT / "evidence_trace/view.js").read_text(encoding="utf-8")
        functions = []
        for name in ("relationStanding", "flowGraph"):
            match = re.search(r"function " + name + r"\([^\n]*\) \{[\s\S]*?(?=\nfunction )", source)
            if match:
                functions.append(match.group(0))
        code = ("const data=JSON.parse(require('fs').readFileSync(0,'utf8'));"
                "const flowOrder=()=>data.steps.map(s=>s.id); const laneOf=()=> 'program';"
                "const stepById=Object.fromEntries(data.steps.map(s=>[s.id,s]));\n"
                + "\n".join(functions) + "\nprocess.stdout.write(JSON.stringify(flowGraph().edges));")
        result = subprocess.run([shutil.which("node"), "-e", code], input=json.dumps(report),
                                capture_output=True, encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    @unittest.skipUnless(shutil.which("node"), "JavaScript relation semantics require Node.js; browser checks are separate")
    def test_choice_lane_does_not_label_user_or_unknown_choices_as_ai(self):
        source = (SKILL_ROOT / "evidence_trace/view.js").read_text(encoding="utf-8")
        declarations = re.search(r"const LANES = [\s\S]*?\nconst laneOf = [^\n]*", source).group(0)
        code = declarations + "\nprocess.stdout.write(JSON.stringify(['用户选择','选择者未记录'].map(label=>LANES.find(l=>l.key===laneOf({kind:'choice',label})).label)));"
        result = subprocess.run([shutil.which("node"), "-e", code], capture_output=True,
                                encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(all("AI" not in label for label in json.loads(result.stdout)))

    @unittest.skipUnless(shutil.which("node"), "JavaScript relation semantics require Node.js; browser checks are separate")
    def test_actual_renderer_requires_a_computed_file_fact_not_only_an_existing_id(self):
        facts = [
            {"id": "declared", "kind": "responds_to", "origin": "declared"},
            {"id": "file", "kind": "input_reference", "origin": "program_derived",
             "scope": "same_file_content", "verification_method": "sha256_equality", "sha256": "a" * 64},
            {"id": "declared-file", "kind": "input_reference", "origin": "declared",
             "scope": "same_file_content", "verification_method": "sha256_equality", "sha256": "b" * 64},
            {"id": "bad-digest", "kind": "input_reference", "origin": "program_derived",
             "scope": "same_file_content", "verification_method": "sha256_equality", "sha256": "not-a-digest"},
            {"id": "structural", "kind": "stage_result", "origin": "program_derived"},
        ]
        cases = [("declared", False), ("file", True), ("declared-file", False),
                 ("bad-digest", False), ("structural", False), ("missing", False)]
        report = {"steps": [{"id": "first", "title": "Write synthetic file", "source_refs": []},
                            {"id": "second", "title": "Declare synthetic input", "source_refs": []}],
                  "diagram": {"short_labels": {}}, "fact_relations": facts,
                  "relations": [{"id": name, "from": "first", "to": "second", "kind": "grouped_with",
                                 "meaning": "Content association", "fact_relation_ids": [name]}
                                for name, _ in cases]}
        edges = self.renderer_edges(report)
        self.assertEqual([(row["id"], row["backed"]) for row in edges], cases)
        self.assertIn("不证明科学支持、物理使用或因果", edges[1]["standing"])

    @unittest.skipUnless(shutil.which("node"), "JavaScript relation semantics require Node.js; browser checks are separate")
    def test_public_export_declared_fact_id_stays_dashed_in_saved_report(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-declared-relation-") as temporary:
            root = Path(temporary)
            trace = root / "trace"
            recorder = Recorder(trace)
            recorder.record({"id": "request", "kind": "requirement", "text": "Preserve the supplied sequence"})
            recorder.record({"id": "choice", "kind": "decision", "text": "Keep this supplied material",
                             "responds_to": ["request"]})
            facts = assemble(recorder.events)
            declared = next(fact for fact in facts["fact_relations"] if fact["kind"] == "responds_to")
            packet = {"schema_version": "trace-organization-v1", "id": "synthetic-organization",
                      "basis": {key: facts["snapshot"][key] for key in ("trace_id", "through_sequence")},
                      "design_process": {"stages": [{"id": "stage", "title": "Declared choice",
                          "purpose": "Retain the submitted statement", "step_ids": ["first", "second"],
                          "source_refs": ["request@1", "choice@1"]}],
                          "steps": {"first": {"kind": "requirement", "content": "Supplied requirement",
                                     "source_refs": ["request@1"]},
                                    "second": {"kind": "choice", "content": "Submitted choice",
                                     "source_refs": ["choice@1"]}},
                          "relations": [{"id": "declared-link", "from": "first", "to": "second",
                              "kind": "grouped_with", "meaning": "Submitted association",
                              "source_refs": ["request@1", "choice@1"], "fact_relation_ids": [declared["id"]]}],
                          "paths": [], "unresolved": [], "detail_refs": []},
                      "report_plan": {"profile": "research-report-v1", "title": "Synthetic declared relation",
                          "sections": [], "diagram": {"reading_order": ["first", "second"],
                              "relation_refs": ["declared-link"], "short_labels": {}}}}
            submitted = root / "organization.json"
            submitted.write_text(json.dumps(packet), encoding="utf-8")
            exported = subprocess.run([sys.executable, "-X", "utf8", "-B",
                str(SKILL_ROOT / "scripts/trace_design.py"), "organize", "--input", str(submitted),
                "--trace-dir", str(trace)], capture_output=True, encoding="utf-8", errors="replace")
            self.assertEqual(exported.returncode, 0, exported.stdout + exported.stderr)
            saved = json.loads((trace / "graph.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["report"]["relations"][0]["fact_relation_ids"], [declared["id"]])
            self.assertTrue((trace / "index.html").is_file())
            self.assertFalse(self.renderer_edges(saved["report"])[0]["backed"])

    @unittest.skipUnless(shutil.which("node"), "JavaScript relation semantics require Node.js; browser checks are separate")
    def test_observed_file_equality_is_solid_in_the_new_public_report(self):
        sys.path.insert(0, str(PROJECT_ROOT / "genome-revival-toolkit"))
        from revival.reporting import _workflow_packet
        with tempfile.TemporaryDirectory(prefix="synthetic-file-relation-") as temporary:
            root = Path(temporary)
            settings = root / "settings.json"
            settings.write_text('{"trace_level":"full"}', encoding="utf-8")
            trace = root / "trace"
            def writer(path, content):
                path.write_text(content, encoding="utf-8")
                return {"paths": [str(path)], "write_receipts": [{"path": str(path),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]}
            @traced_run("genome-revival-toolkit")
            def workflow(out_dir):
                original = out_dir / "first.tsv"
                observe_files("synthetic.export", writer, args=(original, "independent fixture bytes"),
                              output_paths=lambda value: value["paths"], output_directories=[out_dir])
                observe_files("toolkit.export", writer, args=(out_dir / "second.tsv", "separate result"),
                              input_paths=[original], output_paths=lambda value: value["paths"],
                              output_directories=[out_dir])
            with patch.dict(os.environ, {"SNAPGENE_TRACE_CONFIG": str(settings)}), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                workflow(root, trace_dir=trace)
            packet = _workflow_packet(assemble(load_events(trace)[0]))
            submitted = root / "organization.json"
            submitted.write_text(json.dumps(packet), encoding="utf-8")
            exported = subprocess.run([sys.executable, "-X", "utf8", "-B",
                str(SKILL_ROOT / "scripts/trace_design.py"), "organize", "--input", str(submitted),
                "--trace-dir", str(trace)], capture_output=True, encoding="utf-8", errors="replace")
            self.assertEqual(exported.returncode, 0, exported.stdout + exported.stderr)
            saved = json.loads((trace / "graph.json").read_text(encoding="utf-8"))
            edges = self.renderer_edges(saved["report"])
            self.assertEqual(len(edges), 1)  # One written file declared by one later input.
            self.assertTrue(edges[0]["backed"])
            self.assertIn("SHA-256相等", edges[0]["standing"])


if __name__ == "__main__":
    unittest.main()
