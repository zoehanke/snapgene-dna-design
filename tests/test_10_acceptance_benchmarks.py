# -*- coding: utf-8 -*-
"""tests/test_10_acceptance_benchmarks.py - Unittest wrapper for 10 Real Acceptance Benchmarks."""
import unittest
import pathlib
import subprocess
import sys

class Test10AcceptanceBenchmarks(unittest.TestCase):
    def test_run_all_10_benchmarks(self):
        script = pathlib.Path(__file__).resolve().parent.parent / 'scripts' / 'run_10_acceptance_benchmarks.py'
        res = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(res.returncode, 0, f'10 Acceptance Benchmarks failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}')
        self.assertIn('ALL 10 REAL ACCEPTANCE BENCHMARKS PASSED!', res.stdout)
