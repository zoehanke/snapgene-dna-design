"""Public callers cannot edit returned data to change another judgment or report."""
from repository_paths import PROJECT_ROOT, SKILL_ROOT
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord
from test_kit_contributions import toy


class KitResultOwnershipTests(unittest.TestCase):
    def test_editing_returned_gate_errors_cannot_promote_failed_scope(self):
        with tempfile.TemporaryDirectory(prefix='kit-gate-ownership-') as temporary:
            root=Path(temporary)
            folder,manifest=toy(root)
            entry=folder/'scripts/entry.py'
            entry.write_text(entry.read_text(encoding='utf-8')+'''
def edit_receipt(inputs,out_dir):
    from core.kit_contributions import evaluate_active_gates
    candidate=as_molecule(inputs['template'],default_topology='linear')
    results=evaluate_active_gates(candidate=candidate,sources={'template':candidate})
    for result in results:
        result['errors'].clear()
    return {'status':'completed'}
''',encoding='utf-8')
            manifest['entrypoint']='scripts/entry.py:edit_receipt'
            (folder/'kit.json').write_text(json.dumps(manifest),encoding='utf-8')
            inputs=root/'input.json'
            inputs.write_text('{"template":"ACG"}',encoding='utf-8')
            # Literal length 3 is below the toy's declared minimum 7.
            result=subprocess.run([sys.executable,'-X','utf8','-B',str(SKILL_ROOT/'scripts/run_kit.py'),
                'run','toy-seams','--kit-dir',str(root),'--input',str(inputs),'--out-dir',str(root/'output')],
                capture_output=True,encoding='utf-8',errors='strict',timeout=90)
            self.assertEqual(result.returncode,2,result.stdout+result.stderr)
            self.assertEqual(json.loads(result.stdout)['error']['error_code'],'TOY_TOO_SHORT')

    def test_editing_one_selection_report_cannot_change_later_source(self):
        sys.path.insert(0,str(PROJECT_ROOT/'genome-revival-toolkit'))
        from revival.selection import selection_report
        vector=SeqRecord(Seq('ATG'+'GCT'*98+'TAA'),id='constructed-marker',
            annotations={'molecule_type':'DNA','topology':'circular'},
            features=[SeqFeature(FeatureLocation(0,300,strand=1),type='CDS',qualifiers={'label':['URA3']})])
        genotype={'organism':'S. cerevisiae','existing_markers':[],'auxotrophies':['ura3']}
        first=selection_report(vector,genotype)
        changed='https://invalid.example/report-only-change'
        first['markers'][0]['plate_options'][0]['source']['url']=changed
        second=selection_report(vector,genotype)
        self.assertNotEqual(second['markers'][0]['plate_options'][0]['source']['url'],changed)


if __name__=='__main__':
    unittest.main()
