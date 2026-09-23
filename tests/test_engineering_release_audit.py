"""Release source boundaries and honest required-runtime reporting."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import build_release
import check_env
import run_scenario_suite


class ReleaseAuditTests(unittest.TestCase):
    def test_inspect_missing_input_is_a_command_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'scripts/inspect_plasmid.py'),
                                     str(Path(temp)/'missing.gb'),'--json'],capture_output=True,
                                    encoding='utf-8',errors='replace')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('error',json.loads(result.stdout))

    def test_scenario_command_does_not_return_success_for_a_failed_or_empty_suite(self):
        for rows, code in (([{'status':'FAIL'}],1),([],1),([{'status':'PASS'}],0)):
            with self.subTest(rows=rows), patch.object(run_scenario_suite,'run_all',return_value=rows), \
                 patch.object(sys,'argv',['run_scenario_suite.py']):
                self.assertEqual(run_scenario_suite.main(),code)

    def test_git_release_excludes_untracked_local_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            subprocess.run(['git','init','-q',str(root)],check=True)
            (root/'VERSION').write_text('1.0.1',encoding='utf-8')
            (root/'source.py').write_text('print(1)',encoding='utf-8')
            subprocess.run(['git','-C',str(root),'add','VERSION','source.py'],check=True)
            (root/'.env').write_text('DUMMY=not-a-secret',encoding='utf-8')
            (root/'private.gb').write_text('local user material',encoding='utf-8')
            self.assertEqual({e['path'] for e in build_release._collect(root)}, {'VERSION','source.py'})

    def test_non_git_build_requires_reviewed_sources_and_rejects_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'source.py').write_text('print(1)',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'source'):
                build_release._collect(root)
            rows=build_release._collect(root,source_files=['source.py'])
            self.assertEqual([e['path'] for e in rows],['source.py'])
            for invalid in ('../outside.txt', '.env', 'C:/outside.txt'):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    build_release._collect(root,source_files=[invalid])

    def test_missing_required_primer_runtime_makes_environment_fail(self):
        with patch.object(check_env,'probe',return_value={'module':'fake','dist':'fake','status':'ok','version':'test'}), \
             patch.object(check_env,'probe_model_artifacts',return_value=[]), \
             patch('primer3_core_backend.probe_primer3_core',return_value={'status':'unavailable'}), \
             patch('cas_offinder_adapter.detect',return_value={'installed':False,'executable':None,'version':None,'opencl_detected':None}), \
             patch.object(check_env,'probe_snapgene',return_value={'status':'missing'}), \
             patch.object(check_env,'probe_online',return_value={'status':'offline'}), \
             patch.object(sys,'argv',['check_env.py','--json']), contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as stop:
                check_env.main()
        self.assertEqual(stop.exception.code,1)
        self.assertFalse(json.loads(output.getvalue())['core_ok'])


if __name__=='__main__':unittest.main()
