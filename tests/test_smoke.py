# -*- coding: utf-8 -*-
"""unittest discovery wrapper for the core synthetic smoke suite.

Runs ``scripts/smoke_core.py`` so the redistributable package does not depend
on academic-only SnapGene fixtures.
"""
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))


class SmokeCoreTests(unittest.TestCase):
    def test_smoke_core_passes(self):
        completed = subprocess.run(
            [sys.executable, "-X", "utf8",
             os.path.join(SCRIPTS, "smoke_core.py")],
            cwd=SCRIPTS, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        self.assertEqual(
            completed.returncode, 0,
            completed.stdout[-2000:] + completed.stderr[-2000:])
        self.assertNotIn("\nFAIL  ", completed.stdout)
        self.assertRegex(completed.stdout, r"\d+ passed, 0 failed")


if __name__ == "__main__":
    unittest.main()
