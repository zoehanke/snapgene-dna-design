# -*- coding: utf-8 -*-
"""tests/test_experience_helper.py - Unit tests for Tier 4 Lab Experience Rules Helper."""
import unittest

from core.tools.experience_helper import (
    get_experience_categories,
    get_experience_rule_by_id,
    list_all_experience_rules,
    query_lab_experience,
)


class TestExperienceHelper(unittest.TestCase):

    def test_get_experience_categories(self):
        cats = get_experience_categories()
        self.assertGreaterEqual(len(cats), 5)
        self.assertIn("菌落PCR", cats)
        self.assertIn("Gibson", cats)
        self.assertIn("质粒稳定性", cats)

    def test_get_experience_rule_by_id(self):
        # 1. Existing rule
        rule = get_experience_rule_by_id("primer.validation.confirm-before-design")
        self.assertIsNotNone(rule)
        self.assertEqual(rule["id"], "primer.validation.confirm-before-design")
        self.assertIn("验证引物", rule["name"])
        self.assertIn("验证引物", rule["advice"])

        # 2. Non-existent rule
        none_rule = get_experience_rule_by_id("non.existent.rule.id")
        self.assertIsNone(none_rule)

    def test_list_all_experience_rules(self):
        all_rules = list_all_experience_rules()
        self.assertEqual(len(all_rules), 33)

        # Filter by category
        gibson_rules = list_all_experience_rules(category="Gibson")
        self.assertGreaterEqual(len(gibson_rules), 2)
        for r in gibson_rules:
            self.assertEqual(r["category"], "Gibson")

    def test_query_lab_experience_keywords(self):
        # 1. Query "Gibson"
        res_gibson = query_lab_experience(query="Gibson")
        self.assertGreaterEqual(res_gibson["total_matched"], 1)
        top = res_gibson["results"][0]
        self.assertIn("gibson", top["id"].lower() + top["name"].lower() + top["advice"].lower())

        # 2. Query "DpnI"
        res_dpni = query_lab_experience(query="DpnI")
        self.assertGreaterEqual(res_dpni["total_matched"], 1)
        self.assertTrue(any("dpni" in r["id"].lower() or "dpni" in r["advice"].lower() for r in res_dpni["results"]))

        # 3. Query "菌落 PCR"
        res_colony = query_lab_experience(query="菌落 PCR")
        self.assertGreaterEqual(res_colony["total_matched"], 1)

        # 4. Query "二聚体"
        res_dimer = query_lab_experience(query="二聚体")
        self.assertGreaterEqual(res_dimer["total_matched"], 1)

        # 5. Query "Stbl3" or "不稳定质粒"
        res_unstable = query_lab_experience(query="不稳定质粒")
        self.assertGreaterEqual(res_unstable["total_matched"], 1)


if __name__ == "__main__":
    unittest.main()
