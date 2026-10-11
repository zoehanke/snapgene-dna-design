# -*- coding: utf-8 -*-
"""run_test_suite.py - Run the full unittest suite from a plain file.

``coverage run -m unittest`` fails on interpreters where the unittest module
lives inside a zip archive (e.g. ``python310.zip``), so the coverage gate
executes this file instead::

    python -X utf8 tools/run_test_suite.py

Exit code is 0 only when every test passes.
"""

from project_paths import PROJECT_ROOT as REPOSITORY_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS, TESTS_ROOT
import argparse
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = SKILL_ROOT


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-primer3-skip", action="store_true",
                        help="allow real-primer3 tests to skip (not release evidence)")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(HERE))
    loader = unittest.TestLoader()
    suite = loader.discover(str(TESTS_ROOT))
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    primer3_skips = []
    for skipped in result.skipped:
        test, reason = skipped if isinstance(skipped, tuple) else (skipped, "")
        test_id = getattr(test, "id", lambda: str(test))()
        if "primer3" in test_id.lower() or "primer3" in str(test).lower():
            primer3_skips.append(test_id)
    if primer3_skips and not args.allow_primer3_skip:
        print("REAL-PRIMER3-GATE: skipped primer3 tests are not release evidence")
        for test_id in primer3_skips:
            print("  skipped: %s" % test_id)
        return 1
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
