# -*- coding: utf-8 -*-
"""RG-P1-04: README/SKILL command examples must be executable or removed."""
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


class ReadmeCommandTests(unittest.TestCase):
    def test_readme_has_no_known_bad_commands(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("primer3_probe.py [--json]", readme)
        self.assertIn("sys.path.insert(0, \"scripts\")", readme)
        self.assertNotIn(
            "--out-json report.json --out-markdown report.md --out-dir design-out] [--json]",
            readme)

    def test_skill_does_not_claim_every_script_has_json(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("所有脚本输出 JSON（`--json`）", skill)
        self.assertIn("大多数脚本", skill)

    def test_representative_readme_commands_run(self):
        commands = [
            [sys.executable, "-X", "utf8", "-B",
             str(SCRIPTS / "check_env.py"), "--json"],
            [sys.executable, "-X", "utf8", "-B",
             str(SCRIPTS / "parse_dna.py"), "--help"],
            [sys.executable, "-X", "utf8", "-B",
             str(SCRIPTS / "design_primers.py"), "--help"],
            [sys.executable, "-X", "utf8", "-B",
             str(SCRIPTS / "plan_assembly.py"), "--help"],
        ]
        for command in commands:
            completed = subprocess.run(
                command, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=120)
            self.assertEqual(completed.returncode, 0,
                             "%s failed: %s" % (
                                 " ".join(command),
                                 (completed.stderr + completed.stdout)[-500:]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
