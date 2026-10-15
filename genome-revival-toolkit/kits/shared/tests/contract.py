"""Public-entry checks with independently constructed example inputs."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from Bio import SeqIO


class KitContractCases(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='kit-migration-中文-')
        self.root=Path(self.temp.name);self.inputs=self.root/'inputs'
        self.toolkit=self.kit.parents[1];self.repository=self.toolkit.parent
        directory=self.kit/'examples';sys.path.insert(0,str(directory))
        spec=importlib.util.spec_from_file_location('constructed_'+self.command,directory/'generate_inputs.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.generate(self.inputs)
        self.config=self.root/'settings.json';self.config.write_text('{"trace_level":"observed"}',encoding='utf-8')
        self.env=dict(os.environ,PYTHONUTF8='1',SNAPGENE_TRACE_CONFIG=str(self.config),PYTHONDONTWRITEBYTECODE='1')
    def tearDown(self):self.temp.cleanup()
    def call(self,script,*args):
        process=subprocess.run([sys.executable,'-X','utf8','-B',str(script),*map(str,args)],capture_output=True,encoding='utf-8',env=self.env,timeout=360)
        return process,json.loads(process.stdout)
    def test_public_entry_files_and_independent_oracle(self):
        process,result=self.call(self.repository/'snapgene-dna-design/scripts/run_kit.py','run','genome-'+self.command,
            '--kit-dir',self.kit,'--input',self.inputs/'inputs.json','--out-dir',self.root/'output')
        self.assertEqual(process.returncode,0,process.stdout+process.stderr)
        actual=json.loads((self.root/'output/result.json').read_text(encoding='utf-8'))
        expected=json.loads((self.inputs/'EXPECTED.json').read_text(encoding='utf-8'))
        if 'sequence' in expected:
            with (Path(actual['delivery']['directory'])/'construct.gb').open(encoding='utf-8') as handle:record=SeqIO.read(handle,'genbank')
            self.assertEqual(str(record.seq),expected['sequence'])
        else:self.assertEqual(actual['comparisons'][0]['normalised_difference'],0.5)
        _,checked=self.call(self.toolkit/'scripts/run_toolkit.py','verify','--out-dir',self.root/'output')
        self.assertEqual(checked['status'],'verified')
        self.assertEqual(result['result']['trace']['status'],'complete')
        events=(self.root/'output/kit-loading/evidence-trace/events.jsonl').read_text(encoding='utf-8')
        self.assertIn('kit.load',events)
    def test_original_unsupported_parameter_error_remains(self):
        request=json.loads((self.inputs/'request.json').read_text(encoding='utf-8'));request['unsupported_parameter']=True
        (self.inputs/'request.json').write_text(json.dumps(request),encoding='utf-8')
        process,result=self.call(self.toolkit/'scripts/run_toolkit.py',self.command,'--context',self.inputs/'context.json',
            '--request',self.inputs/'request.json','--out-dir',self.root/'failed')
        self.assertEqual(process.returncode,2)
        self.assertEqual(result['error'],'Unsupported '+self.command+' fields: unsupported_parameter')
