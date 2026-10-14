"""Actual runner, independent small suites with deliberately known outcomes."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

PROJECT = pathlib.Path(__file__).resolve().parents[1]


class SuiteReportingTests(unittest.TestCase):
    def run_probe(self, body, *args):
        with tempfile.TemporaryDirectory(prefix='测试统计-') as folder:
            folder = pathlib.Path(folder)
            cases = folder/'cases'
            cases.mkdir()
            (cases/'test_probe.py').write_text('import unittest\nclass ProbeTests(unittest.TestCase):\n' + body,encoding='utf-8')
            destination = folder/'检查清单.json'
            # Exercise public main with an independently created discovery root.
            code = ('import pathlib,sys; sys.path.insert(0,sys.argv[1]); import run_test_suite as runner; '
                    'runner.TESTS_ROOT=pathlib.Path(sys.argv[2]); '
                    'sys.argv=["run_test_suite.py","--report-json",sys.argv[3],*sys.argv[4:]]; '
                    'raise SystemExit(runner.main())')
            run = subprocess.run([sys.executable,'-X','utf8','-B','-c',code,str(PROJECT/'tools'),
                                  str(cases),str(destination),*args],capture_output=True,text=True,encoding='utf-8')
            self.assertTrue(destination.is_file(),run.stdout+run.stderr)
            return run,json.loads(destination.read_bytes().decode('utf-8'))

    def test_skip_is_separate_from_pass_and_utf8_reason_survives(self):
        run,report = self.run_probe('    def test_ok(self):\n        self.assertEqual(2+3,5)\n'
            '    @unittest.skip("外部材料未提供")\n    def test_external(self):\n        self.fail("must skip")\n')
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        self.assertEqual(report['counts'],{'run':2,'passed':1,'skipped':1,'failures':0,'errors':0,
                                         'expected_failures':0,'unexpected_successes':0})
        self.assertEqual(report['status'],'PASSED_WITH_SKIPS')
        self.assertEqual(report['skipped'][0]['reason'],'外部材料未提供')
        self.assertEqual(report['skipped'][0]['test_id'],'test_probe.ProbeTests.test_external')

    def test_failure_remains_failure_and_report_is_written(self):
        run,report = self.run_probe('    def test_ok(self):\n        self.assertTrue(True)\n'
            '    def test_bad(self):\n        for i in (1,2):\n'
            '            with self.subTest(i=i):\n                self.assertEqual(2+3,6)\n')
        self.assertEqual(run.returncode,1)
        self.assertEqual(report['status'],'FAILED')
        self.assertEqual(report['counts']['passed'],1)
        self.assertEqual(report['counts']['failures'],2)
        self.assertEqual(report['counts']['skipped'],0)
        self.assertTrue(report['failures'][0]['test_id'].startswith('test_probe.ProbeTests.test_bad '))
        run,report = self.run_probe('    @classmethod\n    def setUpClass(cls):\n'
            '        raise RuntimeError("setup failure")\n    def test_unused(self):\n        self.fail()\n')
        self.assertEqual(run.returncode,1)
        self.assertEqual(report['counts']['run'],0)
        self.assertEqual(report['counts']['passed'],0)
        self.assertEqual(report['counts']['errors'],1)

    def test_required_primer3_skip_still_blocks_and_optout_is_visible(self):
        body = ('    def test_ok(self):\n        self.assertTrue(True)\n'
                '    @unittest.skip("required backend absent")\n'
                '    def test_primer3_required(self):\n        self.fail("must skip")\n')
        run,report = self.run_probe(body)
        self.assertEqual(run.returncode,1)
        self.assertEqual(report['status'],'FAILED')
        self.assertEqual(report['counts']['passed'],1)

        self.assertEqual(report['counts']['skipped'],1)
        self.assertTrue(report['primer3_gate_enforced'])
        self.assertEqual(len(report['primer3_skips']),1)
        run,report = self.run_probe(body,'--allow-primer3-skip')
        self.assertEqual(run.returncode,0)
        self.assertEqual(report['status'],'PASSED_WITH_SKIPS')
        self.assertFalse(report['primer3_gate_enforced'])
        self.assertEqual(report['counts']['passed'],1)

    def test_external_file_gate_does_not_silence_invalid_available_inputs(self):
        from test_v04 import _requires_external_files
        with tempfile.TemporaryDirectory() as folder:
            folder = pathlib.Path(folder)
            left, right = folder/'left.gb', folder/'right.gb'
            left.write_text('unvalidated placeholder',encoding='utf-8')
            def invalid_input_check():
                self.fail('available inputs must still undergo assertions')
            missing = _requires_external_files(left,right)(invalid_input_check)
            result = unittest.TestResult()
            unittest.FunctionTestCase(missing).run(result)
            self.assertEqual(len(result.skipped),1)
            self.assertNotIn(str(left),result.skipped[0][1])
            self.assertIn(str(right),result.skipped[0][1])
            right.write_text('unvalidated placeholder',encoding='utf-8')
            available = _requires_external_files(left,right)(invalid_input_check)
            result = unittest.TestResult()
            unittest.FunctionTestCase(available).run(result)
            self.assertEqual(result.skipped,[])
            self.assertEqual(len(result.failures),1)

    def test_public_shards_cover_each_known_case_once_and_keep_skip_counts(self):
        body = ''.join('    def test_%s(self):\n        self.assertEqual(2+3,5)\n' % name
                       for name in ('a','b','c','d','e'))
        body += '    @unittest.skip("外部资源未提供")\n    def test_f(self):\n        self.fail()\n'
        expected = [('test_a','test_d'), ('test_b','test_e'), ('test_c','test_f')]
        selected = []
        for index, names in enumerate(expected, 1):
            run, report = self.run_probe(body,'--shard-count','3','--shard-index',str(index),'--verbose')
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertEqual(report['selection'],{'shard_count':3,'shard_index':index,'discovered_total':6})
            self.assertEqual(report['counts']['run'],2)
            self.assertEqual(report['counts']['passed'],1 if index == 3 else 2)
            self.assertEqual(report['counts']['skipped'],1 if index == 3 else 0)
            for name in names:
                self.assertIn(name+' (',run.stderr)
                selected.append(name)
            for other in set(('test_a','test_b','test_c','test_d','test_e','test_f')) - set(names):
                self.assertNotIn(other+' (',run.stderr)
        self.assertEqual(sorted(selected),['test_a','test_b','test_c','test_d','test_e','test_f'])

    def test_verbose_subtest_failure_streams_before_final_summary(self):
        body = '    def test_bad(self):\n        with self.subTest(case=1):\n            self.assertEqual(2+3,6)\n'
        run, report = self.run_probe(body,'--verbose')
        self.assertEqual(run.returncode,1)
        self.assertEqual(report['counts']['passed'],0)
        self.assertEqual(report['counts']['failures'],1)
        self.assertLess(run.stderr.index('Failure details:'),run.stderr.index('Ran 1 test'))

    def test_public_cli_rejects_invalid_shard_before_discovery(self):
        for options in (('--shard-count','0'),('--shard-count','2','--shard-index','3')):
            run = subprocess.run([sys.executable,'-X','utf8','-B',str(PROJECT/'tools/run_test_suite.py'),*options],
                                 capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(run.returncode,2)
            self.assertIn('shard count must be positive',run.stderr)


if __name__ == '__main__':
    unittest.main()
