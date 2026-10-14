"""Literal external toy manifests and public CLI checks, not DNA task oracles."""
from repository_paths import PROJECT_ROOT, SKILL_ROOT
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from core.kits import KitCatalog, KitError
from core.tools.registry import TOOL_REGISTRY


def make_toy(root, name='toy-math'):
    folder=root/name
    (folder/'scripts').mkdir(parents=True)
    (folder/'SKILL.md').write_text('---\nname: '+name+'\ndescription: Double the supplied integer for a test-only arithmetic check.\n---\nUse the declared test entry.\n',encoding='utf-8')
    script='''from pathlib import Path
from core.tools.result import ToolResult
print("TOY_IMPORT_EXECUTED", file=__import__("sys").stderr)
def run(inputs, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    value={"doubled": inputs["number"] * 2}
    (out_dir/"answer.json").write_text(__import__("json").dumps(value), encoding="utf-8")
    return value
def double(number: int):
    return ToolResult(analysis={"doubled": number * 2})
def write_marker(path: str):
    Path(path).write_text("called", encoding="utf-8")
    return ToolResult(analysis={"written": True})
'''
    (folder/'scripts/entry.py').write_text(script,encoding='utf-8')
    manifest={'schema_version':'kit-v1','name':name,'version':'0.1.0',
        'core_version':{'minimum':'2.2.5','maximum_exclusive':'3.0.0'},
        'input_schema':{'type':'object','properties':{'number':{'type':'integer'}},'required':['number'],'additionalProperties':False},
        'input_example':{'number':7},'entrypoint':'scripts/entry.py:run',
        'outputs':{'contract':'json-object','files':['answer.json']},
        'contributions':[{'target':'tools','name':'double','description':'Double an integer.',
            'source':'Independent literal arithmetic: output is two times input.',
            'content':{'entrypoint':'scripts/entry.py:double','category':'compute','parameters_schema':{'type':'object','properties':{}}}},
            {'target':'tools','name':'write_marker','description':'Write a marker only through an explicit write boundary.',
            'source':'Independent side-effect sentinel.',
            'content':{'entrypoint':'scripts/entry.py:write_marker','category':'write','parameters_schema':{'type':'object','properties':{}}}}]}
    (folder/'kit.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return folder,manifest


class KitRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='kit-runtime-中文-')
        self.root=Path(self.temp.name)
        self.folder,self.manifest=make_toy(self.root)
        self.config=self.root/'trace-settings.json'
        self.config.write_text('{"trace_level":"observed"}',encoding='utf-8')
        self.env=dict(os.environ,SNAPGENE_TRACE_CONFIG=str(self.config),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
        self.catalogs=[]
    def tearDown(self):
        for catalog in self.catalogs:
            for name in list(catalog.kits):catalog.unload(name)
        self.temp.cleanup()
    def catalog(self):
        value=KitCatalog([self.root]);self.catalogs.append(value);return value
    def cli(self, script, *args):
        process=subprocess.run([sys.executable,'-X','utf8','-B',str(SKILL_ROOT/'scripts'/script),*map(str,args)],
            env=self.env,capture_output=True,encoding='utf-8',timeout=90)
        return process,json.loads(process.stdout)
    def test_metadata_only_describe_does_not_import(self):
        process,data=self.cli('run_kit.py','describe','toy-math','--kit-dir',self.root)
        self.assertEqual(process.returncode,0)
        self.assertNotIn('TOY_IMPORT_EXECUTED',process.stderr)
        self.assertEqual(data['manifest_sha256'],hashlib.sha256((self.folder/'kit.json').read_bytes()).hexdigest())
        self.assertEqual(data['extension_points']['pipeline'],'NOT_IMPLEMENTED')
        catalog=self.catalog()
        description=catalog.describe('toy-math')
        description['manifest']['name']='changed'
        self.assertEqual(catalog.describe('toy-math')['manifest']['name'],'toy-math')
    def test_three_bad_neighbors_are_isolated(self):
        expected={'missing':'KIT_MANIFEST_INVALID','incompatible':'KIT_CORE_INCOMPATIBLE','entry':'KIT_ENTRY_MISSING'}
        for label in expected:
            directory=self.root/label;directory.mkdir()
            (directory/'SKILL.md').write_text('test',encoding='utf-8')
            data=copy.deepcopy(self.manifest);data['name']=label
            if label=='missing':data.pop('version')
            if label=='incompatible':data['core_version']={'minimum':'9.0.0','maximum_exclusive':'10.0.0'}
            (directory/'kit.json').write_text(json.dumps(data),encoding='utf-8')
        process,data=self.cli('run_kit.py','list','--kit-dir',self.root)
        self.assertEqual(process.returncode,0)
        self.assertEqual([k['name'] for k in data['kits']],['toy-math'])
        self.assertEqual({Path(e['directory']).name:e['error_code'] for e in data['errors']},expected)
        process,result=self.cli('run_kit.py','run','toy-math','--kit-dir',self.root,'--input',self.write_input({'number':7}),'--out-dir',self.root/'run')
        self.assertEqual(result['result']['doubled'],14)
    def write_input(self, value):
        path=self.root/'input.json';path.write_text(json.dumps(value),encoding='utf-8');return path
    def test_public_tool_describe_and_real_step(self):
        process,data=self.cli('describe_tools.py','kit.toy-math.double','--kit-dir',self.root)
        self.assertEqual(data['category'],'compute')
        self.assertEqual(data['parameters']['required'],['number'])
        self.assertLess(process.stderr.index('External Kit'),process.stderr.index('TOY_IMPORT_EXECUTED'))
        input_file=self.write_input({'method':'kit.toy-math.double','params':{'number':7}})
        process,data=self.cli('run_step.py','--kit-dir',self.root,'--input',input_file,'--out-dir',self.root/'step','--full')
        self.assertEqual(process.returncode,0,process.stderr)
        stored=json.loads((self.root/'step/steps.json').read_text(encoding='utf-8'))
        self.assertEqual(stored['steps'][0]['result']['analysis']['doubled'],14)
        events=(self.root/'step/evidence-trace/events.jsonl').read_text(encoding='utf-8')
        self.assertIn('kit.load',events)
        self.assertIn(hashlib.sha256((self.folder/'kit.json').read_bytes()).hexdigest(),events)
    def test_write_category_refused_before_function(self):
        marker=self.root/'effect.txt'
        input_file=self.write_input({'method':'kit.toy-math.write_marker','params':{'path':str(marker)}})
        process,data=self.cli('run_step.py','--kit-dir',self.root,'--input',input_file,'--out-dir',self.root/'blocked','--full')
        self.assertNotEqual(process.returncode,0)
        self.assertEqual(data['error']['error_code'],'PIPELINE_SIDE_EFFECT')
        self.assertFalse(marker.exists())
    def test_run_entry_writes_actual_file_and_loaded_fact(self):
        process,data=self.cli('run_kit.py','run','toy-math','--kit-dir',self.root,'--input',self.write_input({'number':9}),'--out-dir',self.root/'entry')
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertEqual(json.loads((self.root/'entry/answer.json').read_text(encoding='utf-8')),{'doubled':18})
        events=(self.root/'entry/kit-loading/evidence-trace/events.jsonl').read_text(encoding='utf-8')
        self.assertIn('kit.load',events)
        self.assertIn('external',events)
    def test_unload_restores_registry_and_removed_directory_is_not_discovered(self):
        before=set(TOOL_REGISTRY)
        catalog=self.catalog();catalog.load('toy-math')
        self.assertEqual(set(TOOL_REGISTRY)-before,{'kit.toy-math.double','kit.toy-math.write_marker'})
        catalog.unload('toy-math');self.assertEqual(set(TOOL_REGISTRY),before)
        moved=self.root/'removed';self.folder.rename(moved)
        process,data=self.cli('run_kit.py','list','--kit-dir',self.folder)
        self.assertEqual(data['kits'],[])
        process,data=self.cli('describe_tools.py')
        self.assertNotIn('kit.toy-math.double',[t['name'] for t in data['tools']])
    def test_changed_manifest_and_unsupported_contribution_are_rejected(self):
        catalog=self.catalog()
        (self.folder/'kit.json').write_text('{}',encoding='utf-8')
        with self.assertRaises(KitError) as error:catalog.load('toy-math')
        self.assertEqual(error.exception.error_code,'KIT_MANIFEST_CHANGED')
        value=copy.deepcopy(self.manifest);value['contributions'][0]['target']='pipeline'
        (self.folder/'kit.json').write_text(json.dumps(value),encoding='utf-8')
        catalog=self.catalog()
        self.assertEqual(catalog.errors[0]['error_code'],'KIT_CONTRIBUTION_UNSUPPORTED')
    def test_reloading_records_one_operation_per_real_step(self):
        from core.workflow import run_step
        catalog=self.catalog()
        before=set(TOOL_REGISTRY)
        for _ in range(3):
            catalog.load('toy-math')
            step=run_step('kit.toy-math.double',{'number':13})
            self.assertIsNone(step.error)
            self.assertEqual(step.result.analysis,{'doubled':26})
            self.assertEqual(len(step.operations),1)
            catalog.unload('toy-math')
            self.assertEqual(set(TOOL_REGISTRY),before)
    def test_disappeared_manifest_and_import_exit_do_not_block_neighbor(self):
        gone,_=make_toy(self.root,'a-gone')
        exited,_=make_toy(self.root,'b-exit')
        catalog=self.catalog()
        (gone/'kit.json').unlink()
        path=exited/'scripts/entry.py'
        path.write_text('raise SystemExit(17)\n'+path.read_text(encoding='utf-8'),encoding='utf-8')
        data=catalog.load_tools()
        self.assertEqual({row['name']:row['error_code'] for row in data['errors']},
                         {'a-gone':'KIT_MANIFEST_INVALID','b-exit':'KIT_LOAD_FAILED'})
        self.assertEqual(TOOL_REGISTRY['kit.toy-math.double'].execute(number=7).analysis,{'doubled':14})
    def test_non_json_results_are_reported_through_public_cli(self):
        for index,literal in enumerate(('float("nan")','{1}','(1,2)')):
            folder,_=make_toy(self.root,'invalid-result-'+str(index))
            path=folder/'scripts/entry.py'
            path.write_text(path.read_text(encoding='utf-8').replace('value={"doubled": inputs["number"] * 2}',
                            'value={"invalid": '+literal+'}').replace('__import__("json").dumps(value)','"unverified result"'),encoding='utf-8')
            process,data=self.cli('run_kit.py','run','invalid-result-'+str(index),'--kit-dir',folder,
                '--input',self.write_input({'number':7}),'--out-dir',self.root/('invalid-result-output-'+str(index)))
            self.assertNotEqual(process.returncode,0)
            self.assertEqual(data['error']['error_code'],'KIT_RESULT_INVALID')
    def test_input_and_parameter_failures_preserve_contract(self):
        process,data=self.cli('run_kit.py','run','toy-math','--kit-dir',self.root,'--input',self.write_input({'number':'bad'}),'--out-dir',self.root/'invalid')
        self.assertEqual(data['error']['error_code'],'KIT_INPUT_INVALID')
        self.assertNotIn('TOY_IMPORT_EXECUTED',process.stderr)
        input_file=self.write_input({'method':'kit.toy-math.double','params':{'number':'bad'}})
        process,data=self.cli('run_step.py','--kit-dir',self.root,'--input',input_file,'--out-dir',self.root/'bad-step','--full')
        self.assertEqual(data['error']['error_code'],'TOOL_ARGUMENT_INVALID')
    def test_core_and_trace_have_no_concrete_project_dependencies(self):
        forbidden=('Genome Revival','genome-revival','revival.identity','revival.construct','revival.evidence','revival.crispr','genome-identity','revival-evidence')
        for folder in ('core','evidence_trace'):
            for path in (SKILL_ROOT/folder).rglob('*'):
                if path.suffix not in ('.py','.js','.css'):continue
                text=path.read_text(encoding='utf-8')
                for name in forbidden:self.assertNotIn(name,text,path.relative_to(SKILL_ROOT))
