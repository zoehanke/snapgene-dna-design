# -*- coding: utf-8 -*-
"""run_test_suite.py - Run the full unittest suite from a plain file.

``coverage run -m unittest`` fails on interpreters where the unittest module
lives inside a zip archive (e.g. ``python310.zip``), so the coverage gate
executes this file instead::

    python -X utf8 tools/run_test_suite.py

Exit code is 0 when executed tests and the required Primer3 gate pass.
Optional skips remain explicit non-pass outcomes in stdout/JSON.
"""

from project_paths import PROJECT_ROOT as REPOSITORY_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS, TESTS_ROOT
import argparse
import json
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = SKILL_ROOT


class OutcomeResult(unittest.TextTestResult):
    """Count actual successful cases, never skipped/partial/failed subtests."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed_count = 0

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed_count += 1


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-primer3-skip", action="store_true",
                        help="allow real-primer3 tests to skip (not release evidence)")
    parser.add_argument("--report-json", type=pathlib.Path,
                        help="write UTF-8 per-test skips/reasons and separate outcome counts")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(HERE))
    loader = unittest.TestLoader()
    suite = loader.discover(str(TESTS_ROOT))
    runner = unittest.TextTestRunner(verbosity=1, resultclass=OutcomeResult)
    result = runner.run(suite)
    primer3_skips = []
    for skipped in result.skipped:
        test, reason = skipped if isinstance(skipped, tuple) else (skipped, "")
        test_id = getattr(test, "id", lambda: str(test))()
        if "primer3" in test_id.lower() or "primer3" in str(test).lower():
            primer3_skips.append(test_id)
    gate_failed = bool(primer3_skips) and not args.allow_primer3_skip
    counts = {'run': result.testsRun,
              'passed': result.passed_count,
              'skipped': len(result.skipped), 'failures': len(result.failures), 'errors': len(result.errors),
              'expected_failures': len(result.expectedFailures), 'unexpected_successes': len(result.unexpectedSuccesses)}
    successful = result.wasSuccessful() and not gate_failed
    report = {'status': ('PASSED_WITH_SKIPS' if result.skipped else 'PASSED') if successful else 'FAILED',
              'counts': counts, 'primer3_gate_enforced': not args.allow_primer3_skip,
              'counting': 'run/passed count test cases; other counts are unittest outcome records, including subtests/class setup errors',
              'primer3_skips': primer3_skips,
              'skipped': [{'test_id': getattr(test,'id',lambda: str(test))(), 'reason': str(reason)}
                          for test,reason in result.skipped],
              'failures': [{'test_id': test.id(), 'detail': detail} for test,detail in result.failures],
              'errors': [{'test_id': test.id(), 'detail': detail} for test,detail in result.errors]}
    print('TEST-COUNTS: ' + ', '.join(f'{name}={count}' for name,count in counts.items()))
    for skipped in report['skipped']:
        print(f"SKIPPED: {skipped['test_id']}: {skipped['reason']}")
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if gate_failed:
        print("REAL-PRIMER3-GATE: skipped primer3 tests are not release evidence")
        for test_id in primer3_skips:
            print("  skipped: %s" % test_id)
        return 1
    return 0 if successful else 1


if __name__ == "__main__":
    sys.exit(main())
