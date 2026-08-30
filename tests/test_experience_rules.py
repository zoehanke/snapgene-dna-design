# -*- coding: utf-8 -*-
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from agent.rule_capture import (
    compile_candidate, evaluate_experience, export_rule_list,
    handle_rule_request, load_preloaded_experience, render_rule_list,
)
from rules.experience import (
    ALLOWED_TRIGGERS, KNOWN_FIELDS, ExperienceRuleStore,
    RuleValidationError, condition_matches,
    validate_rule,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SafeConditionTests(unittest.TestCase):
    def test_schema_trigger_and_field_registry_match_runtime(self):
        schema = json.loads((ROOT / "schemas" /
                             "experience-rule-v1.json").read_text(
                                 encoding="utf-8"))
        schema_triggers = set(schema["properties"]["trigger"]["enum"])
        condition_options = schema["$defs"]["condition"]["oneOf"]
        atomic = next(option for option in condition_options
                      if "field" in option.get("properties", {}))
        schema_fields = set(atomic["properties"]["field"]["enum"])
        self.assertEqual(schema_triggers, ALLOWED_TRIGGERS)
        self.assertEqual(schema_fields, KNOWN_FIELDS)

    def test_nested_declarative_condition(self):
        condition = {"all": [
            {"field": "pcr.type", "operator": "eq", "value": "colony"},
            {"field": "pcr.amplicon_bp", "operator": "gt", "value": 1000},
        ]}
        self.assertTrue(condition_matches(
            condition, {"pcr": {"type": "colony", "amplicon_bp": 1001}}))
        self.assertFalse(condition_matches(
            condition, {"pcr": {"type": "colony", "amplicon_bp": 1000}}))

    def test_executable_check_is_rejected(self):
        compiled = compile_candidate(
            "以后菌落 PCR 超过 1000 bp 时提醒并询问我")
        rule = compiled["rule"]
        rule["check"] = "__import__('os').system('bad')"
        self.assertTrue(any("check expressions" in item
                            for item in validate_rule(rule)))

    def test_executable_eval_is_rejected(self):
        compiled = compile_candidate(
            "以后菌落 PCR 超过 1000 bp 时提醒并询问我")
        rule = compiled["rule"]
        rule["eval"] = "__import__('os').system('bad')"
        self.assertTrue(any("eval expressions" in item
                            for item in validate_rule(rule)))

    def test_experience_schema_rejects_executable_and_unknown_condition_keys(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema is not installed")
        schema = json.loads((ROOT / "schemas" /
                             "experience-rule-v1.json").read_text(
                                 encoding="utf-8"))
        rule = compile_candidate(
            "以后菌落 PCR 超过 1000 bp 时提醒并询问我")["rule"]
        rule["eval"] = "PAYLOAD"
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(rule)))
        rule.pop("eval")
        rule["when"] = {"field": "pcr.amplicon_bp",
                         "operator": "gt", "value": 1000,
                         "unknown": True}
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(rule)))


class ExperienceStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ExperienceRuleStore(self.temp.name)
        self.preloaded = load_preloaded_experience(
            ROOT / "rules" / "preloaded_experience_rules.json")

    def tearDown(self):
        self.temp.cleanup()

    def _propose_and_confirm(self, text):
        first = handle_rule_request(
            text, self.store, project_id="demo", out_dir=self.temp.name,
            preloaded_rules=self.preloaded)
        self.assertEqual(first["status"], "awaiting-confirmation")
        second = handle_rule_request(
            "确认保存", self.store, project_id="demo",
            out_dir=self.temp.name, preloaded_rules=self.preloaded)
        self.assertEqual(second["status"], "confirmed")
        return second["rule"]

    def test_natural_language_candidate_requires_confirmation(self):
        result = handle_rule_request(
            "以后菌落 PCR 超过 1000 bp 时提醒并询问我",
            self.store, project_id="demo", out_dir=self.temp.name,
            preloaded_rules=self.preloaded)
        self.assertEqual(result["status"], "awaiting-confirmation")
        self.assertEqual(
            {item["source"]["type"] for item in self.store.read_rules()["rules"]},
            {"preloaded"})
        self.assertIn("1000 bp", result["candidate"]["preview"])

    def test_confirmation_persists_version_and_history(self):
        rule = self._propose_and_confirm(
            "以后菌落 PCR 超过 1000 bp 时提醒并询问我")
        self.assertEqual(rule["version"], 2)
        self.assertEqual(rule["status"], "active")
        self.assertTrue(rule["sha256"])
        self.assertEqual(len(list(self.store.history_dir.glob("*.json"))), 1)

    def test_revision_increments_version(self):
        self._propose_and_confirm(
            "以后菌落 PCR 超过 1000 bp 时提醒并询问我")
        revised = self._propose_and_confirm(
            "以后菌落 PCR 超过 1200 bp 时提醒并询问我")
        self.assertEqual(revised["version"], 3)
        threshold = revised["when"]["all"][1]["value"]
        self.assertEqual(threshold, 1200)

    def test_scope_clarification_is_resolved_naturally(self):
        result = handle_rule_request(
            "菌落 PCR 超过 1000 bp 时提醒我", self.store,
            project_id="demo", out_dir=self.temp.name,
            preloaded_rules=self.preloaded)
        self.assertEqual(result["status"], "needs-clarification")
        resolved = handle_rule_request(
            "当前项目", self.store, project_id="demo",
            out_dir=self.temp.name, preloaded_rules=self.preloaded)
        self.assertEqual(resolved["status"], "awaiting-confirmation")
        self.assertEqual(
            resolved["candidate"]["rule"]["scope"],
            {"type": "project", "project_id": "demo"})

    def test_rule_list_and_markdown_export_have_fixed_fields(self):
        self._propose_and_confirm(
            "以后菌落 PCR 超过 1000 bp 时提醒并询问我")
        markdown = render_rule_list(self.store.read_rules()["rules"], "demo")
        for label in ("ID：", "状态：", "范围：", "触发：", "条件：",
                      "动作：", "来源：", "版本：", "校验："):
            self.assertIn(label, markdown)
        output = pathlib.Path(self.temp.name) / "rules.md"
        exported = export_rule_list(self.store, output, project_id="demo")
        self.assertEqual(exported["status"], "exported")
        self.assertIn("snapshot_sha256", output.read_text(encoding="utf-8"))

    def test_preloaded_validation_primer_and_colony_pcr_rules_fire(self):
        primer = evaluate_experience(
            "before_validation_primer_design",
            {"primer": {"role": "validation", "request_explicit": False,
                        "user_supplied": False}},
            self.store, preloaded_rules=self.preloaded)
        self.assertEqual(
            primer["hits"][0]["rule_id"],
            "primer.validation.confirm-before-design")
        pcr = evaluate_experience(
            "after_pcr_plan",
            {"pcr": {"type": "boiled_colony", "amplicon_bp": 1001}},
            self.store, preloaded_rules=self.preloaded)
        self.assertEqual(
            pcr["hits"][0]["action"]["type"], "warn_and_confirm")

    def test_all_33_human_reviewed_preloaded_rules_are_unique_and_valid(self):
        self.assertEqual(len(self.preloaded), 33)
        self.assertEqual(len({rule["id"] for rule in self.preloaded}), 33)
        source_ids = {rule["source"]["source_id"] for rule in self.preloaded}
        self.assertEqual(
            source_ids,
            {"E-01", "E-02"} | {"C-%02d" % index for index in range(1, 32)})
        for rule in self.preloaded:
            self.assertEqual(validate_rule(rule, persistent=True), [], rule["id"])
            self.assertTrue(rule["source"]["verification"]["human_reviewed"])
            self.assertIn(rule["source"]["verification"]["review_decision"],
                          ("接受", "修改后接受"))

    def test_representative_new_preloaded_rules_match_and_have_negative_cases(self):
        cases = [
            ("before_pcr_plan",
             {"pcr": {"purpose": "formal_cloning"}},
             "pcr.high-fidelity-purpose.prompt"),
            ("after_primer_design",
             {"primer": {"has_5p_nonbinding_tail": True,
                         "tail_binds_initial_template": False}},
             "primer.nonbinding-tail-tm-separation"),
            ("assembly_feasibility",
             {"method": "golden_gate", "fragment_count": 11},
             "assembly.golden-gate-many-fragments-warning"),
            ("after_validation_plan",
             {"validation": {"junction_count": 2,
                             "junctions_covered": False,
                             "uncut_control_planned": True,
                             "min_band_separation_percent": 20,
                             "min_visible_fragment_bp": 300,
                             "clone_count": 5}},
             "validation.cover-all-assembly-junctions"),
            ("after_pcr_plan",
             {"pcr": {"template_type": "plasmid",
                      "template_dam_methylated": True,
                      "parental_template_removed": False,
                      "direct_downstream_use": True}},
             "pcr.plasmid-template-dpni-background"),
        ]
        for trigger, context, expected_id in cases:
            result = evaluate_experience(
                trigger, context, ExperienceRuleStore(self.temp.name),
                preloaded_rules=self.preloaded)
            self.assertIn(expected_id, {hit["rule_id"] for hit in result["hits"]})
        negative = evaluate_experience(
            "after_primer_design",
            {"primer": {"has_5p_nonbinding_tail": True,
                        "tail_binds_initial_template": True}},
            ExperienceRuleStore(self.temp.name), preloaded_rules=self.preloaded)
        self.assertNotIn(
            "primer.nonbinding-tail-tm-separation",
            {hit["rule_id"] for hit in negative["hits"]})

    def test_upgrade_seeds_only_new_presets_without_resurrecting_deleted_rule(self):
        initial = self.preloaded[:2]
        self.store.ensure_preloaded(initial)
        pending = self.store.propose_status(
            "primer.validation.confirm-before-design", "deleted")
        self.store.confirm_status(pending["candidate_id"], "确认删除")
        upgraded = self.store.ensure_preloaded(self.preloaded)
        self.assertEqual(len(upgraded["rules"]), 33)
        self.assertEqual(len(upgraded["preloaded_rule_ids"]), 33)
        deleted = next(
            rule for rule in upgraded["rules"]
            if rule["id"] == "primer.validation.confirm-before-design")
        self.assertEqual(deleted["status"], "deleted")

    def test_status_change_requires_second_confirmation(self):
        rule = self._propose_and_confirm(
            "以后菌落 PCR 超过 1000 bp 时提醒并询问我")
        pending = self.store.propose_status(rule["id"], "disabled")
        current = next(item for item in self.store.read_rules()["rules"]
                       if item["id"] == rule["id"])
        self.assertEqual(current["status"], "active")
        changed = self.store.confirm_status(pending["candidate_id"], "确认停用")
        self.assertEqual(changed["status"], "disabled")
        events = [json.loads(path.read_text(encoding="utf-8"))
                  for path in self.store.history_dir.glob("*.json")]
        self.assertIn("disable", [item["operation"] for item in events])

    def test_rollback_creates_a_new_version(self):
        self._propose_and_confirm(
            "以后菌落 PCR 超过 1000 bp 时提醒并询问我")
        self._propose_and_confirm(
            "以后菌落 PCR 超过 1200 bp 时提醒并询问我")
        candidate = self.store.propose_rollback(
            "pcr.colony.preferred-amplicon-length", 1)
        restored = self.store.confirm(candidate["candidate_id"], "确认回滚")
        self.assertEqual(restored["version"], 4)
        self.assertEqual(restored["when"]["all"][1]["value"], 1000)

    def test_structured_agent_candidate_is_not_active_before_confirmation(self):
        rule = {
            "id": "delivery.long-amplicon-note",
            "name": "交付时标注长扩增片段",
            "trigger": "before_delivery",
            "scope": {"type": "global"},
            "when": {
                "field": "pcr.amplicon_bp", "operator": "gt", "value": 1500,
            },
            "action": {
                "type": "warn",
                "message": "交付时标明扩增片段超过 1500 bp。",
            },
            "source": {"type": "user_experience", "text": "长片段要标明"},
        }
        candidate = self.store.add_candidate(rule)
        self.assertEqual(candidate["status"], "awaiting-confirmation")
        self.assertEqual(self.store.read_rules()["rules"], [])
        saved = self.store.confirm(candidate["candidate_id"], "确认保存")
        self.assertEqual(saved["id"], rule["id"])

    def test_preloaded_rule_can_be_deleted_without_resurrection(self):
        self.store.ensure_preloaded(self.preloaded)
        proposed = self.store.propose_status(
            "pcr.colony.preferred-amplicon-length", "deleted")
        deleted = self.store.confirm_status(
            proposed["candidate_id"], "确认删除")
        self.assertEqual(deleted["status"], "deleted")

        result = evaluate_experience(
            "after_pcr_plan",
            {"pcr": {"type": "colony", "amplicon_bp": 1500}},
            ExperienceRuleStore(self.temp.name),
            preloaded_rules=self.preloaded)
        self.assertNotIn(
            "pcr.colony.preferred-amplicon-length",
            {hit["rule_id"] for hit in result["hits"]})
        stored = ExperienceRuleStore(self.temp.name).read_rules()
        target = next(item for item in stored["rules"]
                      if item["id"] == "pcr.colony.preferred-amplicon-length")
        self.assertEqual(target["status"], "deleted")
        events = [json.loads(path.read_text(encoding="utf-8"))
                  for path in self.store.history_dir.glob("*.json")]
        self.assertIn("delete", [item["operation"] for item in events])

    def test_ambiguous_colony_rule_delete_requires_selection(self):
        proposed = handle_rule_request(
            "删除菌落 PCR 规则", self.store, project_id="demo",
            out_dir=self.temp.name, preloaded_rules=self.preloaded)
        self.assertEqual(proposed["status"], "needs-selection")
        self.assertGreater(len(proposed["matches"]), 1)


class ExperienceTriggerCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.python = sys.executable

    def tearDown(self):
        self.temp.cleanup()

    def test_validation_primer_design_fails_closed_without_explicit_request(self):
        command = [
            self.python, str(ROOT / "scripts" / "design_primers.py"),
            "ACGT" * 100,
            "--primer-role", "validation", "--json",
            "--user-rules-dir", self.temp.name,
        ]
        result = subprocess.run(
            command, cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("VALIDATION_PRIMER_CONFIRMATION_REQUIRED", result.stdout)

    def test_colony_pcr_long_amplicon_warns_before_writing(self):
        forward = "ACGTTGCAACGTTGCAACGT"
        reverse = "GCTAGCTAGCTAGCTAGCTA"
        complement = str.maketrans("ACGT", "TGCA")
        reverse_site = reverse.translate(complement)[::-1]
        template = forward + ("A" * 1100) + reverse_site
        fasta = pathlib.Path(self.temp.name) / "template.fasta"
        fasta.write_text(">template\n%s\n" % template, encoding="utf-8")
        output = pathlib.Path(self.temp.name) / "amplicon.gb"
        base = [
            self.python, str(ROOT / "scripts" / "simulate_pcr.py"),
            str(fasta), "--fwd", forward,
            "--rev", reverse, "--pcr-type", "boiled_colony",
            "--out", str(output), "--json",
            "--user-rules-dir", self.temp.name,
        ]
        first = subprocess.run(
            base, cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        self.assertEqual(first.returncode, 0, first.stderr)
        payload = json.loads(first.stdout)["data"]
        self.assertTrue(payload["experience_warning"]["requires_confirmation"])
        self.assertGreater(payload["experience_warning"]["actual_amplicon_bp"], 1000)
        self.assertFalse(output.exists())
        second = subprocess.run(
            base + ["--acknowledge-experience-warning"], cwd=str(ROOT),
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertTrue(output.exists())

    def test_colony_pcr_block_cannot_be_overridden_by_acknowledgement(self):
        fwd = "ACGTTGCAACGTTGCAACGT"
        rev = "GCTAGCTAGCTAGCTAGCTA"
        complement = str.maketrans("ACGT", "TGCA")
        reverse_site = rev.translate(complement)[::-1]
        template = pathlib.Path(self.temp.name) / "block-template.fasta"
        template.write_text(
            ">template\n%s%s%s\n" % (fwd, "A" * 1100, reverse_site),
            encoding="utf-8")
        rules = {
            "schema_version": "1.0.0",
            "preloaded_initialized": True,
            "preloaded_rule_ids": [],
            "rules": [{
                "schema_version": "1.0.0",
                "id": "test.hard-block",
                "name": "硬阻止测试",
                "version": 1,
                "status": "active",
                "scope": {"type": "global"},
                "trigger": "after_pcr_plan",
                "when": {"all": [
                    {"field": "pcr.type", "operator": "in",
                     "value": ["colony", "boiled_colony"]},
                    {"field": "pcr.amplicon_bp", "operator": "gt",
                     "value": 1000},
                ]},
                "action": {"type": "block", "message": "不得绕过"},
                "source": {"type": "test"},
            }],
        }
        (pathlib.Path(self.temp.name) / "rules.json").write_text(
            json.dumps(rules, ensure_ascii=False), encoding="utf-8")
        common = [
            self.python, str(ROOT / "scripts" / "simulate_pcr.py"),
            str(template), "--fwd", fwd, "--rev", rev,
            "--pcr-type", "boiled_colony", "--json",
            "--user-rules-dir", self.temp.name,
        ]
        blocked_output = pathlib.Path(self.temp.name) / "blocked.fa"
        blocked = subprocess.run(
            common + ["--out", str(blocked_output),
                      "--acknowledge-experience-warning"],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        self.assertNotEqual(blocked.returncode, 0)
        payload = json.loads(blocked.stdout)["data"]
        self.assertTrue(payload["experience_warning"]["blocked"])
        self.assertFalse(blocked_output.exists())


if __name__ == "__main__":
    unittest.main()
