# -*- coding: utf-8 -*-
"""Academic-only smoke wrapper. Skipped when SnapGene fixtures are absent."""
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
FIXTURE = os.path.abspath(os.path.join(HERE, "..", "fixtures", "pDONR201.dna"))


@unittest.skipUnless(os.path.exists(FIXTURE),
                     "academic SnapGene fixtures are not present")
class SmokeAcademicTests(unittest.TestCase):
    def test_smoke_academic_passes(self):
        completed = subprocess.run(
            [sys.executable, "-X", "utf8",
             os.path.join(SCRIPTS, "smoke_academic.py")],
            cwd=SCRIPTS, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        self.assertEqual(
            completed.returncode, 0,
            completed.stdout[-2000:] + completed.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
