# -*- coding: utf-8 -*-
"""Metadata checks for the 60-scenario literature suite."""
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS))

from scripts.run_scenario_suite import scenarios, run_verification  # noqa: E402


class ScenarioMetadataTests(unittest.TestCase):
    def test_at_least_50_real_sourced_scenarios(self):
        items = scenarios()
        self.assertGreaterEqual(len(items), 50)
        seen = set()
        for item in items:
            self.assertNotIn(item["id"], seen)
            seen.add(item["id"])
            self.assertTrue(item["source"])
            self.assertTrue(item["description"])
            self.assertIn(item["kind"], ("plan", "advanced", "mutagenesis",
                                         "golden_gate", "crispr", "pcr",
                                         "verification", "primer-retry",
                                         "real-vector"))

    def test_one_verification_smoke_run(self):
        scenario = [s for s in scenarios() if s["id"] == "S60"][0]
        with tempfile.TemporaryDirectory() as tmp:
            result = run_verification(scenario, pathlib.Path(tmp))
        self.assertEqual(result["plan_status"], "complete")


if __name__ == "__main__":
    unittest.main(verbosity=2)
