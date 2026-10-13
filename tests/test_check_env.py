
from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
# -*- coding: utf-8 -*-
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = SKILL_ROOT
SCRIPTS = ROOT / "scripts"


class CheckEnvTests(unittest.TestCase):
    def test_core_report_json_is_parseable_and_artifacts_checked(self):
        completed = subprocess.run(
            [sys.executable, "-X", "utf8", "-B",
             str(SCRIPTS / "check_env.py"), "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(completed.returncode, 0)
        report = json.loads(completed.stdout)
        self.assertTrue(report["core_ok"])
        self.assertGreaterEqual(len(report["model_artifacts"]), 3)
        self.assertTrue(all(item["status"] == "ok"
                            for item in report["model_artifacts"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
