"""External temporary v2 toy: literal DNA/rule/gate oracles, real public entrypoints."""
from repository_paths import SKILL_ROOT
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from core.kits import KitCatalog
from core.tools.registry import TOOL_REGISTRY


def toy(root,name='toy-seams'):
    folder=root/name;(folder/'scripts').mkdir(parents=True);(folder/'rules').mkdir()
    (folder/'SKILL.md').write_text('---\nname: '+name+'\ndescription: Test local contribution seams with constructed software inputs.\n---\n',encoding='utf-8')
    code='''from core.models.molecule import as_molecule
from core.tools.result import check_result
from core.tools.registry import get_tool
import json
from pathlib import Path
def run(inputs,out_dir):
    name=json.loads((Path(__file__).resolve().parents[1]/'kit.json').read_text(encoding='utf-8'))['name']
    result=get_tool('kit.'+name+'.pipeline.trim_reverse').execute(inputs=inputs)
    value={'sequence':str(result.only_product().seq),'length':len(result.only_product())}
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/'run.json').write_text(json.dumps(value),encoding='utf-8')
    return value
def gate(*,candidate,sources,requirements,steps,inputs):
    source=as_molecule(sources['template'],default_topology='linear')
    inherited=source.annotations.get('comment')=='synthetic inherited warning'
    return [check_result('length',subject=candidate,status='PASSED' if len(candidate)>=7 else 'FAILED',scope='length'),
      check_result('source_note',subject=candidate,status='FAILED' if inherited else 'PASSED',scope='source_note',
         details={'inherited_from_source':'template','input_version':source.record_version})]
'''
    (folder/'scripts/entry.py').write_text(code,encoding='utf-8')
    rules={'schema_version':'1.0.0','rules':[{'id':'toy-length','name':'Constructed length boundary','version':1,'status':'active',
        'trigger':'before_culture_plan','scope':{'type':'project','project_id':name},
        'when':{'field':'template_length','operator':'gte','value':7},'action':{'type':'warn','message':'Constructed length is at least seven.'},
        'source':{'type':'constructed-test','description':'Literal arithmetic boundary seven; no laboratory guidance.'}}]}
    (folder/'rules/rules.json').write_text(json.dumps(rules),encoding='utf-8')
    manifest={'schema_version':'kit-v2','name':name,'version':'0.1.0','core_version':{'minimum':'2.2.5','maximum_exclusive':'3.0.0'},
        'input_schema':{'type':'object','required':['template'],'properties':{'template':{}},'additionalProperties':False},
        'input_example':{'template':'ACGTTGCAACGT'},'entrypoint':'scripts/entry.py:run','outputs':{'contract':'json-object','files':['run.json']},
        'contributions':[{'target':'pipeline','name':'trim_reverse','description':'Existing extraction and reverse complement only.',
          'source':'Constructed interval [2,9); existing Core tools, no new DNA algorithm.',
          'content':{'inputs_schema':{'type':'object','required':['template'],'properties':{'template':{}},'additionalProperties':False},
            'steps':[{'step_id':'trim','tool':'extract_subsequence','params':{'file_path_or_record':'$template','start':2,'end':9}},
                     {'step_id':'reverse','tool':'reverse_complement','params':{'seq':'$trim.products.0'}}],'output_step':'reverse'}},
          {'target':'gates','name':'scope','description':'Length and an explicit source-note finding.','source':'Independent constructed inputs.',
           'content':{'entrypoint':'scripts/entry.py:gate','required_scopes':[
              {'scope':'length','error_code':'TOY_TOO_SHORT','message':'Candidate must have at least seven bases.'},
              {'scope':'source_note','error_code':'TOY_INHERITED_NOTE','message':'The source carries the synthetic note.'}],
             'acceptances':[{'scope':'source_note','source':'Constructed test-policy declaration, not an experiment.',
                            'reason':'This exact input-note finding is accepted only for the toy scope; raw FAILED is retained.'}]}},
          {'target':'rules','name':'length','description':'Use existing sourced experience grammar.','source':'Literal constructed count.',
           'content':{'path':'rules/rules.json','fields':['template_length']}}]}
    (folder/'kit.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return folder,manifest


class ContributionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='kit-v2-中文-');self.root=Path(self.temp.name)
        self.folder,self.manifest=toy(self.root)
        config=self.root/'settings.json';config.write_text('{"trace_level":"observed"}',encoding='utf-8')
        self.env=dict(os.environ,SNAPGENE_TRACE_CONFIG=str(config),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
        self.catalogs=[]
    def tearDown(self):
        for catalog in self.catalogs:
            for name in catalog.kits:catalog.unload(name)
        self.temp.cleanup()
    def catalog(self):
        catalog=KitCatalog([self.root]);self.catalogs.append(catalog);return catalog
    def call(self,script,*args):
        p=subprocess.run([sys.executable,'-X','utf8','-B',str(SKILL_ROOT/'scripts'/script),*map(str,args)],capture_output=True,encoding='utf-8',env=self.env,timeout=90)
        return p,json.loads(p.stdout)
    def input(self,value):
        path=self.root/'input.json';path.write_text(json.dumps(value),encoding='utf-8');return path
    def test_v2_describe_and_pipeline_through_real_step(self):
        p,data=self.call('run_kit.py','describe','toy-seams','--kit-dir',self.root)
        self.assertEqual(p.returncode,0)
        self.assertTrue(all(data['extension_points'][key]=='IMPLEMENTED' for key in ('tools','pipeline','gates','rules')))
        p,data=self.call('describe_tools.py','kit.toy-seams.pipeline.trim_reverse','--kit-dir',self.root)
        self.assertEqual(p.returncode,0,p.stderr)
        step=self.input({'method':'kit.toy-seams.pipeline.trim_reverse','params':{'inputs':{'template':'ACGTTGCAACGT'}}})
        p,data=self.call('run_step.py','--kit-dir',self.root,'--input',step,'--out-dir',self.root/'step','--full')
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        actual=json.loads((self.root/'step/steps.json').read_text(encoding='utf-8'))
        self.assertEqual(actual['steps'][0]['result']['products'][0]['sequence'],'TTGCAAC')
    def test_public_pipeline_and_existing_rule_evaluation(self):
        p,data=self.call('run_kit.py','pipeline','toy-seams','trim_reverse','--kit-dir',self.root,
            '--input',self.input({'template':'ACGTTGCAACGT'}),'--out-dir',self.root/'pipeline')
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertEqual(data['result']['products'][0]['sequence'],'TTGCAAC')
        p,data=self.call('run_kit.py','rules','toy-seams','length','--kit-dir',self.root,
            '--input',self.input({'trigger':'before_culture_plan','context':{'template_length':12}}),'--out-dir',self.root/'rules')
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertEqual([row['rule_id'] for row in data['hits']],['toy-length'])
        self.assertEqual(data['diagnostics'],[])
        self.assertTrue((self.root/'rules/rule-result.json').is_file())
    def test_gate_blocks_and_declared_acceptance_is_visible(self):
        source={'sequence':'ACGTTGCAACGT','topology':'linear','annotations':{'comment':'synthetic inherited warning'}}
        for sequence,wanted in [('ACGTTGCAACGT',True),('AAA',False)]:
            out=self.root/('gate-'+str(wanted))
            p,data=self.call('run_kit.py','gate','toy-seams','scope','--kit-dir',self.root,
                '--input',self.input({'candidate':sequence,'sources':{'template':source}}),'--out-dir',out)
            self.assertEqual(data['passed'],wanted)
            self.assertEqual(p.returncode,0 if wanted else 2)
            accepted=next(row for row in data['checks'] if row['scope']=='source_note')
            self.assertEqual(accepted['status'],'FAILED')
            self.assertEqual(accepted['acceptance_notice'],'按 Kit 规则豁免')
            self.assertTrue(accepted['acceptance_reason']);self.assertTrue(accepted['acceptance_source'])
            self.assertIn('kit.gate',(out/'evidence-trace/events.jsonl').read_text(encoding='utf-8'))
            if not wanted:self.assertEqual(data['errors'][0]['error_code'],'TOY_TOO_SHORT')
    def test_missing_conflict_incompatibility_and_unsourced_rule_isolate(self):
        expected={'conflict':'KIT_TOOL_CONFLICT','missing':'KIT_MANIFEST_INVALID','incompatible':'KIT_CORE_INCOMPATIBLE','unsourced':'KIT_RULE_SOURCE_MISSING'}
        for name in expected:
            folder,manifest=toy(self.root,name)
            if name=='conflict':manifest['contributions'].append(copy.deepcopy(manifest['contributions'][0]))
            if name=='missing':manifest['contributions'][0]['content'].pop('steps')
            if name=='incompatible':manifest['core_version']={'minimum':'9.0.0','maximum_exclusive':'10.0.0'}
            if name=='unsourced':
                path=folder/'rules/rules.json';rules=json.loads(path.read_text(encoding='utf-8'));rules['rules'][0].pop('source');path.write_text(json.dumps(rules),encoding='utf-8')
            (folder/'kit.json').write_text(json.dumps(manifest),encoding='utf-8')
        catalog=self.catalog()
        self.assertEqual({Path(row['directory']).name:row['error_code'] for row in catalog.errors},expected)
        self.assertEqual(catalog.run('toy-seams',{'template':'ACGTTGCAACGT'},self.root/'entry')['sequence'],'TTGCAAC')
    def test_unload_restores_registry_rule_fields_and_gate_context(self):
        from core.kit_contributions import active_validation
        from rules.experience import validate_condition
        before=set(TOOL_REGISTRY);catalog=self.catalog();catalog.load('toy-seams')
        self.assertIn('kit.toy-seams.pipeline.trim_reverse',TOOL_REGISTRY)
        catalog.unload('toy-seams');self.assertEqual(set(TOOL_REGISTRY),before)
        self.assertIsNone(active_validation())
        self.assertTrue(validate_condition({'field':'template_length','operator':'gte','value':7}))
        self.folder.rename(self.root/'removed')
        p,data=self.call('run_kit.py','list','--kit-dir',self.folder)
        self.assertEqual(data['kits'],[])
    def test_declared_gate_cannot_be_ignored_by_entry(self):
        path=self.folder/'scripts/entry.py';path.write_text(path.read_text(encoding='utf-8').replace("result=get_tool('kit.'+name+'.pipeline.trim_reverse').execute(inputs=inputs)",
            "from core.tools.result import ToolResult\n    from core.models.molecule import as_molecule\n    result=ToolResult(products=[as_molecule(inputs['template'],default_topology='linear')])"),encoding='utf-8')
        p,data=self.call('run_kit.py','run','toy-seams','--kit-dir',self.root,
            '--input',self.input({'template':'ACGTTGCAACGT'}),'--out-dir',self.root/'skipped')
        self.assertEqual(p.returncode,2)
        self.assertEqual(data['error']['error_code'],'KIT_GATE_NOT_EXECUTED')
    def test_explicit_product_reference_retains_existing_selector(self):
        self.manifest['contributions'][0]['content']['output_step']='$reverse.products.0'
        (self.folder/'kit.json').write_text(json.dumps(self.manifest),encoding='utf-8')
        p,data=self.call('run_kit.py','pipeline','toy-seams','trim_reverse','--kit-dir',self.root,
            '--input',self.input({'template':'ACGTTGCAACGT'}),'--out-dir',self.root/'reference')
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertEqual(data['result']['products'][0]['sequence'],'TTGCAAC')
    def test_malformed_and_blank_rule_sources_leave_valid_neighbor(self):
        expected={'bad-json':'KIT_RULE_INVALID','bad-type':'KIT_RULE_INVALID','blank-source':'KIT_RULE_SOURCE_MISSING'}
        for name in expected:
            folder,_=toy(self.root,name);path=folder/'rules/rules.json'
            if name=='bad-json':path.write_text('{',encoding='utf-8')
            else:
                rules=json.loads(path.read_text(encoding='utf-8'))
                if name=='bad-type':rules['rules'][0]['when']['field']=[]
                else:rules['rules'][0]['source']={'type':' ','description':' '}
                path.write_text(json.dumps(rules),encoding='utf-8')
        p,data=self.call('run_kit.py','list','--kit-dir',self.root)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertEqual({Path(row['directory']).name:row['error_code'] for row in data['errors']},expected)
        self.assertEqual([row['name'] for row in data['kits']],['toy-seams'])
