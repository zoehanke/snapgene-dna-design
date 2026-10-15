"""Public file/summary regression; expectations are independent arithmetic."""
from repository_paths import PROJECT_ROOT
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class EvidenceComparisonPublicTests(unittest.TestCase):
    def test_count_comparisons_write_both_languages_and_keep_unknowns(self):
        with tempfile.TemporaryDirectory(prefix='evidence-public-') as temporary:
            root=Path(temporary)
            context=root/'context.json'
            context.write_text('{"references":{}}',encoding='utf-8')
            settings=root/'trace-settings.json'
            settings.write_text('{"trace_level":"full"}',encoding='utf-8')
            env={**os.environ,'SNAPGENE_TRACE_CONFIG':str(settings)}
            for missing in (False,True):
                request={'original_request':'Audit constructed counts; these are not measured experiments.',
                    'observations':[{'id':'a','group':'test','colonies':30,'plated_cells':1500},
                        {'id':'b','group':'control','colonies':6,'plated_cells':None if missing else 3000}],
                    'comparisons':[{'experiment_group':'test','control_group':'control'}]}
                path=root/('missing.json' if missing else 'counts.json')
                path.write_text(json.dumps(request),encoding='utf-8')
                for language in ('zh','en'):
                    output=root/(str(missing)+'-'+language)
                    process=subprocess.run([sys.executable,'-X','utf8','-B',str(PROJECT_ROOT/'genome-revival-toolkit/scripts/run_toolkit.py'),
                        'evidence','--context',str(context),'--request',str(path),'--out-dir',str(output),
                        '--language',language],capture_output=True,encoding='utf-8',env=env)
                    self.assertEqual(process.returncode,0,process.stdout+process.stderr)
                    result=json.loads((output/'result.json').read_text(encoding='utf-8'))
                    difference=result['comparisons'][0]['normalised_difference']
                    if missing:self.assertIsNone(difference)
                    else:self.assertAlmostEqual(difference,30/1500-6/3000)
                    # Counts cannot test genome elimination without any genetic assay.
                    self.assertEqual([row['status'] for row in result['conclusions']],['INSUFFICIENT','NOT_TESTED'])
                    text=(output/'summary.md').read_text(encoding='utf-8')
                    self.assertIn('test / control',text)
                    self.assertIn('None' if missing else '0.018',text)
                    verified=subprocess.run([sys.executable,'-X','utf8','-B',str(PROJECT_ROOT/'genome-revival-toolkit/scripts/run_toolkit.py'),
                        'verify','--out-dir',str(output)],capture_output=True,encoding='utf-8',env=env)
                    self.assertEqual(verified.returncode,0,verified.stdout+verified.stderr)
                    self.assertEqual(json.loads(verified.stdout)['status'],'verified')


if __name__=='__main__':unittest.main()
