"""Retained public CLI captures for Kit migration; input oracles are constructed."""
import argparse
import copy
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord
from compare_kit_compatibility import compare, save, LAUNCHER

BASELINE = '484b13f6682386e8285c608a02f94d110eb8486a'


def record(path, sequence, features=()):
    value = SeqRecord(Seq(sequence), id=path.stem, features=list(features),
        annotations={'molecule_type':'DNA','topology':'linear','date':'01-JAN-2000'})
    with path.open('w',encoding='utf-8') as handle:
        SeqIO.write(value,handle,'genbank')


def prepare(root, kit, repository):
    root.mkdir(parents=True,exist_ok=False)
    inputs=root/'inputs';inputs.mkdir()
    if kit=='construct':
        rng=random.Random(681120)
        target=''.join(rng.choices('ACGT',k=2000));cargo=''.join(rng.choices('ACGT',k=900))
        donor=target[600:800]+cargo[200:440]+target[810:1010]
        feature=SeqFeature(FeatureLocation(200,440,strand=1),type='misc_feature',qualifiers={'label':['independent_cargo']})
        for name,sequence in [('target',target),('cargo',cargo),('donor',donor)]:
            record(inputs/(name+'.gb'),sequence,[] if name=='target' else [feature])
        context={'references':{name:{'path':name+'.gb','source':'Fixed-seed software vector, no experimental claim.'} for name in ('target','cargo','donor')}}
        request={'original_request':'Prepare the explicit 200+240+200 bp donor from the supplied complete template and check both interfaces.',
            'method':'integration_donor','target_reference':'target','cargo_reference':'cargo',
            'target_interval':{'start0':800,'end0':810},'cargo_interval':{'start0':200,'end0':440},'arm_length':200,
            'preparation_method':'pcr','donor_template_reference':'donor','donor_interval':{'start0':0,'end0':640}}
        negative=copy.deepcopy(request);negative['donor_interval']['start0']=1
        save(inputs/'negative.json',negative)
        expectations={'length':640,'sequence':donor,'negative_domain_status':'failed'}
    elif kit=='evidence':
        context={'references':{}}
        request={'original_request':'Compare these synthetic count records and retain unknown experimental authenticity.',
            'observations':[{'id':'e1','group':'experiment','colonies':30,'plated_cells':50},
                            {'id':'c1','group':'control','colonies':5,'plated_cells':50}],
            'comparisons':[{'experiment_group':'experiment','control_group':'control'}]}
        negative=copy.deepcopy(request);negative['observations'][1]['id']='e1'
        save(inputs/'negative.json',negative)
        unknown=copy.deepcopy(request);unknown['observations'][0].pop('plated_cells')
        save(inputs/'unknown.json',unknown)
        expectations={'difference':0.5,'negative_error':'Observation IDs must be unique','unknown_difference':None}
    else:
        sys.path.insert(0,str(repository/'tests'))
        from test_crispr_kit import fixture
        request,expected=fixture(inputs,17011,replace=True)
        context=json.loads((inputs/'context.json').read_text(encoding='utf-8'))
        check=copy.deepcopy(request);check.pop('spacer_seq');check['operation']='check'
        save(inputs/'check.json',check)
        negative=copy.deepcopy(check)
        with (inputs/'target.gb').open(encoding='utf-8') as handle:target=SeqIO.read(handle,'genbank')
        from crispr_synthetic_fixture import build_cases
        start=build_cases(17011)['control'].target_start
        # Give the original spacer an independently constructed invalid PAM.
        target.seq=Seq(str(target.seq[:start])+build_cases(17011)['control'].intended_spacer+'CAA'+str(target.seq[start+23:]))
        with (inputs/'negative-target.gb').open('w',encoding='utf-8') as handle:SeqIO.write(target,handle,'genbank')
        negative_context=copy.deepcopy(context);negative_context['references']['target']['path']='negative-target.gb'
        save(inputs/'negative-context.json',negative_context);save(inputs/'negative.json',negative)
        expectations={'sequence':expected,'length':len(expected),'negative_direction':'INVALID_PAM'}
    save(inputs/'context.json',context);save(inputs/'positive.json',request)
    bad=copy.deepcopy(request);bad['unsupported_parameter']=True;save(inputs/'error.json',bad)
    cases=[{'id':'positive-'+level+'-'+lang,'request':'positive.json','level':level,'language':lang,'exit':0}
           for level,lang in [('off','en'),('observed','en'),('full','en'),('full','zh')]]
    cases += [{'id':'negative','request':'negative.json','level':'observed','language':'en','exit':2},
              {'id':'error','request':'error.json','level':'observed','language':'en','exit':2}]
    if kit=='evidence':cases.append({'id':'unknown','request':'unknown.json','level':'observed','language':'en','exit':0})
    if kit=='crispr':cases[-2]['context']='negative-context.json'
    save(root/'CONDITIONS.json',{'kit':kit,'cases':cases,'expectations':expectations,
        'metadata_control':'UUID and Trace clock are fixed. Only output-directory temporary basenames are deterministic. No molecular function is replaced.',
        'normalization':'Code checkout prefix and JSON object key order only; no ignored biological/check/error fields.'})
    temporary='''
import tempfile
original_mkdtemp=tempfile.mkdtemp
counter_dirs=itertools.count(1)
controlled_root=Path(sys.argv[2]).resolve()
def stable_mkdtemp(suffix=None,prefix=None,dir=None):
    base=Path(dir).resolve() if dir else None
    if base and base.is_relative_to(controlled_root):
        target=base/((prefix or 'tmp')+'controlled-'+str(next(counter_dirs))+(suffix or ''))
        target.mkdir();return str(target)
    return original_mkdtemp(suffix=suffix,prefix=prefix,dir=dir)
tempfile.mkdtemp=stable_mkdtemp
sys.argv.pop(2)
'''
    launcher=LAUNCHER.replace("entry=repository/",temporary+"\nentry=repository/")
    (root/'launch_public_cli.py').write_text(launcher,encoding='utf-8')


def capture(repository,root,label):
    target=root/label;target.mkdir(exist_ok=False)
    conditions=json.loads((root/'CONDITIONS.json').read_text(encoding='utf-8'));kit=conditions['kit']
    records=[]
    for args,name in [(['describe',kit],'describe.json'),(['--help'],'help.txt')]:
        p=subprocess.run([sys.executable,'-X','utf8','-B',str(root/'launch_public_cli.py'),str(repository),str(root/'live'),*args],capture_output=True,encoding='utf-8',timeout=60)
        assert p.returncode==0,p.stderr
        (target/name).write_text(p.stdout,encoding='utf-8')
    for case in conditions['cases']:
        live=root/'live'/case['id'];live.parent.mkdir(exist_ok=True)
        if live.exists():
            assert live.resolve().is_relative_to((root/'live').resolve());shutil.rmtree(live)
        settings=root/'settings.json';save(settings,{'trace_level':case['level']})
        env=dict(os.environ,SNAPGENE_TRACE_CONFIG=str(settings),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
        command=[sys.executable,'-X','utf8','-B',str(root/'launch_public_cli.py'),str(repository),str(root/'live'),kit,
            '--context',str(root/'inputs'/case.get('context','context.json')),'--request',str(root/'inputs'/case['request']),
            '--out-dir',str(live),'--language',case['language']]
        p=subprocess.run(command,capture_output=True,encoding='utf-8',env=env,timeout=360)
        output=target/case['id'];output.mkdir();(output/'stdout.json').write_text(p.stdout,encoding='utf-8')
        (output/'stderr.txt').write_text(p.stderr,encoding='utf-8')
        if live.exists():shutil.copytree(live,output/'files')
        assert p.returncode==case['exit'],(case,p.stdout,p.stderr)
        data=json.loads(p.stdout)
        domain_path=live/'result.json'
        if case['id'].startswith('positive'):
            result=json.loads(domain_path.read_text(encoding='utf-8'))
            if kit in ('construct','crispr'):
                with (Path(result['delivery']['directory'])/'construct.gb').open(encoding='utf-8') as handle:actual=SeqIO.read(handle,'genbank')
                assert str(actual.seq)==conditions['expectations']['sequence']
            else:assert result['comparisons'][0]['normalised_difference']==0.5
            verify=subprocess.run([sys.executable,'-X','utf8','-B',str(repository/'genome-revival-toolkit/scripts/run_toolkit.py'),'verify','--out-dir',str(live)],capture_output=True,encoding='utf-8',env=env,timeout=60)
            assert json.loads(verify.stdout)['status']=='verified',verify.stdout
            (output/'verify.json').write_text(verify.stdout,encoding='utf-8')
        elif case['id']=='negative' and domain_path.exists():
            result=json.loads(domain_path.read_text(encoding='utf-8'))
            if kit=='construct':assert result['status']=='failed'
            if kit=='crispr':assert result['grna']['direction_status']=='INVALID_PAM'
        elif case['id']=='unknown':
            result=json.loads(domain_path.read_text(encoding='utf-8'));assert result['comparisons'][0]['normalised_difference'] is None
        records.append({'case':case['id'],'exit_code':p.returncode,'construction_oracles':'PASSED'})
    save(target/'CAPTURE.json',{'records':records,'repository_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repository,text=True,encoding='utf-8').strip()})


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--kit',choices=('construct','evidence','crispr'),required=True)
    parser.add_argument('--baseline',type=Path,required=True);parser.add_argument('--current',type=Path,required=True)
    parser.add_argument('--out-dir',type=Path,required=True);parser.add_argument('--capture-baseline',action='store_true');parser.add_argument('--attempt',default='after-01')
    args=parser.parse_args();root=args.out_dir.resolve();baseline=args.baseline.resolve();current=args.current.resolve()
    if args.capture_baseline:prepare(root,args.kit,baseline);capture(baseline,root,'before');return 0
    capture(current,root,args.attempt);return 0 if compare(root,baseline,current,args.attempt) else 2


if __name__=='__main__':raise SystemExit(main())
