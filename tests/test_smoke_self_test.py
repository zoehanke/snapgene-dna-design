# -*- coding: utf-8 -*-
"""Proves smoke failure reporting is real, not only happy-path output."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import os
import subprocess
import sys
import textwrap
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = str(TOOLS_ROOT)


class SmokeFailureSelfTests(unittest.TestCase):
    def test_check_false_marks_failure(self):
        wrapper = os.path.join(tempfile.gettempdir(), "smoke_forced_failure.py")
        wrapper_code = (
            "import sys\n"
            "sys.path.insert(0, " + repr(SCRIPTS) + ")\n"
            "import smoke_core\n"
            "smoke_core.PASS[:] = []\n"
            "smoke_core.FAIL[:] = []\n"
            "smoke_core.check('forced failure', False, 'on purpose')\n"
            "print('===== %d passed, %d failed =====' % (len(smoke_core.PASS), len(smoke_core.FAIL)))\n"
            "sys.exit(1 if smoke_core.FAIL else 0)\n"
        )
        with open(wrapper, "w", encoding="utf-8") as handle:
            handle.write(wrapper_code)
        completed = subprocess.run(
            [sys.executable, "-X", "utf8", wrapper],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("FAIL  forced failure", completed.stdout)
        self.assertRegex(completed.stdout, r"0 passed, 1 failed")


if __name__ == "__main__":
    unittest.main()
