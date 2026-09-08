# -*- coding: utf-8 -*-
"""Unittest wrapper for synthetic workflow smoke cases."""
import unittest
import pathlib
import subprocess
import sys

class TestWorkflowSmoke(unittest.TestCase):
    def test_run_all_10_benchmarks(self):
        script = pathlib.Path(__file__).resolve().parent.parent / 'scripts' / 'run_10_acceptance_benchmarks.py'
        res = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(res.returncode, 0, f'Workflow smoke failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}')
        self.assertIn('SYNTHETIC WORKFLOW SMOKE COMPLETED', res.stdout)
        self.assertNotIn('v1.0-READY', res.stdout)
