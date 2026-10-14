"""Public sub-Skill entry and contributed tool, using construction-defined inputs."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

KIT=Path(__file__).resolve().parents[1]
REPOSITORY=KIT.parents[2]
CORE=REPOSITORY/'snapgene-dna-design'


class IdentityKitContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='identity-subskill-')
        self.root=Path(self.temp.name)
        spec=importlib.util.spec_from_file_location('identity_input_constructor',KIT/'examples/generate_inputs.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.inputs=self.root/'inputs';module.generate(self.inputs)
        config=self.root/'trace-settings.json';config.write_text('{"trace_level":"observed"}',encoding='utf-8')
        self.env=dict(os.environ,SNAPGENE_TRACE_CONFIG=str(config),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
    def tearDown(self):self.temp.cleanup()
    def call(self,script,*args):
        p=subprocess.run([sys.executable,'-X','utf8','-B',str(script),*map(str,args)],capture_output=True,encoding='utf-8',env=self.env,timeout=120)
        return p,json.loads(p.stdout)
    def test_public_run_keeps_assay_scope_and_separate_loading_record(self):
        p,data=self.call(CORE/'scripts/run_kit.py','run','genome-identity','--kit-dir',KIT,
            '--input',self.inputs/'inputs.json','--out-dir',self.root/'output')
        self.assertEqual(p.returncode,0,p.stderr)
        result=json.loads((self.root/'output/result.json').read_text(encoding='utf-8'))
        predicted={r['reference']:r.get('amplicon_length_bp') for r in result['assays'][0]['predictions']}
        self.assertEqual(predicted,{'a':164,'b':141,'negative':None})
        self.assertIn('Whole-genome specificity',result['unverified'][0])
        self.assertEqual(data['result']['trace']['status'],'complete')
        self.assertIn('kit.load',(self.root/'output/kit-loading/evidence-trace/events.jsonl').read_text(encoding='utf-8'))
        p,check=self.call(REPOSITORY/'genome-revival-toolkit/scripts/run_toolkit.py','verify','--out-dir',self.root/'output')
        self.assertEqual(check['status'],'verified')
    def test_contributed_inspect_tool_runs_through_public_step(self):
        request=json.loads((self.inputs/'request.json').read_text(encoding='utf-8'))
        step=self.root/'step.json';step.write_text(json.dumps({'method':'kit.genome-identity.assess',
            'params':{'request':request,'context_uri':(self.inputs/'context.json').as_uri()}}),encoding='utf-8')
        p,data=self.call(CORE/'scripts/run_step.py','--kit-dir',KIT,'--input',step,'--out-dir',self.root/'step','--full')
        self.assertEqual(p.returncode,0,p.stderr+p.stdout)
        stored=json.loads((self.root/'step/steps.json').read_text(encoding='utf-8'))
        analysis=stored['steps'][0]['result']['analysis']
        self.assertEqual(analysis['assays'][0]['predictions'][0]['amplicon_length_bp'],164)
    def test_unsupported_field_remains_failure(self):
        request=json.loads((self.inputs/'request.json').read_text(encoding='utf-8'));request['unknown_field']=True
        (self.inputs/'request.json').write_text(json.dumps(request),encoding='utf-8')
        p,data=self.call(CORE/'scripts/run_kit.py','run','genome-identity','--kit-dir',KIT,
            '--input',self.inputs/'inputs.json','--out-dir',self.root/'rejected')
        self.assertNotEqual(p.returncode,0)
        self.assertIn('Unsupported identity fields: unknown_field',data['error']['message'])
