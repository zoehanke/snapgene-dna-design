"""Real public Kit commands with failing, counted Python socket entry points."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from repository_paths import PROJECT_ROOT

LAUNCHER = '''import json, runpy, socket, sys
from pathlib import Path
counter=Path(sys.argv[1]); entry=Path(sys.argv[2]); attempts=[]
sys.path.insert(0,str(entry.parent))
def blocked(*args,**kwargs):
    attempts.append('socket connection attempted')
    raise OSError('Network blocked and counted by offline Kit verification')
socket.socket.connect=blocked
socket.socket.connect_ex=blocked
socket.create_connection=blocked
socket.getaddrinfo=blocked
sys.argv=[str(entry),*sys.argv[3:]]
try:runpy.run_path(str(entry),run_name='__main__')
finally:counter.write_text(json.dumps({'connection_attempts':len(attempts)}),encoding='utf-8')
'''


def generator(repository, kit):
    path=repository/'genome-revival-toolkit/kits'/kit/'examples/generate_inputs.py'
    spec=importlib.util.spec_from_file_location('offline_example_'+kit,path)
    module=importlib.util.module_from_spec(spec)
    sys.path.insert(0,str(path.parent))
    try:spec.loader.exec_module(module)
    finally:sys.path.remove(str(path.parent))
    return module


def run_cases(repository, root):
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    launcher=root/'blocked-network-cli.py'; launcher.write_text(LAUNCHER,encoding='utf-8')
    config=root/'trace-config.json'; config.write_text('{"trace_level":"observed"}',encoding='utf-8')
    environment=dict(os.environ,SNAPGENE_TRACE_CONFIG=str(config),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
    cli=repository/'genome-revival-toolkit/scripts/run_toolkit.py'
    records=[]
    def command(label,args,expected=None):
        counter=root/(label+'-network.json')
        result=subprocess.run([sys.executable,'-X','utf8','-B',str(launcher),str(counter),str(cli),*map(str,args)],
            capture_output=True,encoding='utf-8',env=environment,timeout=360)
        (root/(label+'.stdout.txt')).write_text(result.stdout,encoding='utf-8')
        (root/(label+'.stderr.txt')).write_text(result.stderr,encoding='utf-8')
        calls=json.loads(counter.read_text(encoding='utf-8'))['connection_attempts']
        assert calls==0,(label,calls)
        assert result.returncode in (0,2),(label,result.stdout,result.stderr)
        if expected is not None:assert result.returncode==expected,(label,result.stdout,result.stderr)
        value=json.loads(result.stdout)
        records.append({'operation':label,'exit_code':result.returncode,'status':value.get('status'),
                        'connection_attempts':calls,'stdout':label+'.stdout.txt'})
        return value
    inputs={}
    for kit in ('construct','identity','evidence','crispr'):
        directory=root/('input-'+kit)
        generator(repository,kit).generate(directory)
        inputs[kit]=directory
        command('describe-'+kit,['describe',kit],0)
    def run(kit,label,request=None,context=None,expected=None):
        directory=inputs[kit]
        request_path=directory/'request.json'
        context_path=directory/'context.json'
        if request is not None:
            request_path=root/(label+'-request.json')
            request_path.write_text(json.dumps(request),encoding='utf-8')
        if context is not None:
            context_path=root/(label+'-context.json')
            context_path.write_text(json.dumps(context),encoding='utf-8')
        output=root/('output-'+label)
        value=command(label,[kit,'--request',request_path,'--context',context_path,'--out-dir',output,'--language','en'],expected)
        assert (output/'result.json').is_file(),label
        checked=command('verify-'+label,['verify','--out-dir',output],0)
        assert checked['status']=='verified',checked
        return value
    def request(kit):return json.loads((inputs[kit]/'request.json').read_text(encoding='utf-8'))
    run('construct','construct-pcr',expected=0)
    altered=request('construct'); altered['preparation_method']='gibson'
    altered.pop('donor_template_reference'); altered.pop('donor_interval')
    run('construct','construct-gibson-rejection',altered,expected=2)
    run('identity','identity-provided-assays',expected=0)
    altered=request('identity'); altered.pop('assays'); altered['compare_regions']=True
    run('identity','identity-region-comparison',altered,expected=0)
    # Exercise actual primer design; its scientific quality verdict is recorded,
    # not predetermined or relabelled as success by this network-only test.
    context=json.loads((inputs['construct']/'context.json').read_text(encoding='utf-8'))
    context['references']={key:dict(row,path=str((inputs['construct']/row['path']).resolve())) for key,row in context['references'].items()}
    altered={'original_request':'Synthetic local assay design, no experimental claim.', 'references':['target'],
             'compare_regions':False,'design_assays':[{'id':'designed','target_reference':'target',
                'interval':{'start0':100,'end0':700}}]}
    run('identity','identity-designed-assay',altered,context)
    run('evidence','evidence-inline-counts',expected=0)
    altered=request('evidence'); altered.pop('observations')
    csv=inputs['evidence']/'observations.csv'
    csv.write_text('id,group,colonies,plated_cells\ne1,experiment,30,50\nc1,control,5,50\n',encoding='utf-8')
    altered['observations_file']=str(csv)
    run('evidence','evidence-csv-counts',altered,expected=0)
    identity_context=json.loads((inputs['identity']/'context.json').read_text(encoding='utf-8'))
    altered={'original_request':'Synthetic submitted local test; authenticity not established.',
             'genotype_results':[{'sample_id':'s','reference_id':'a','result':'positive','control_status':'passed'}]}
    run('evidence','evidence-genotype-record',altered,identity_context,0)
    run('evidence','evidence-no-observations',{'original_request':'Report absent observations.'},expected=2)
    run('crispr','crispr-replace',expected=0)
    check_root=root/'input-crispr-check'; check_root.mkdir()
    module=generator(repository,'crispr'); module.fixture(check_root,42043,replace=False)
    altered=json.loads((check_root/'request.json').read_text(encoding='utf-8'))
    check_context=json.loads((check_root/'context.json').read_text(encoding='utf-8'))
    check_context['references']={key:dict(row,path=str((check_root/row['path']).resolve())) for key,row in check_context['references'].items()}
    run('crispr','crispr-check',altered,check_context,0)
    report={'status':'PASSED','scope':'Actual public CLI operations; Python socket/DNS attempts blocked and counted. Domain verdicts retained.',
            'cases':records,'connection_attempts':sum(row['connection_attempts'] for row in records),
            'official_ci':'官方 GitLab CI 未执行','wet_lab':'NOT_PERFORMED'}
    (root/'network-report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return report


class KitDefaultNetworkTests(unittest.TestCase):
    def test_all_current_public_operation_paths_do_not_connect(self):
        with tempfile.TemporaryDirectory(prefix='offline-kits-') as temp:
            report=run_cases(PROJECT_ROOT,Path(temp))
        self.assertEqual(report['connection_attempts'],0)
        self.assertEqual(len(report['cases']),26)


if __name__=='__main__':unittest.main()
