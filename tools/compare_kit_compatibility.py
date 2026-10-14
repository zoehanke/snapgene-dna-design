"""Public Toolkit compatibility snapshots using literal synthetic PCR expectations.

Only observation clocks/UUIDs are fixed for comparison; no DNA/Kit computation is
replaced. Preserve every raw attempt. Runtime never imports this development tool.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord


LAUNCHER = '''import itertools, runpy, sys, uuid
from pathlib import Path
repository=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(repository/'genome-revival-toolkit'))
from revival.bootstrap import CORE_ROOT
from evidence_trace import models
models.now=lambda: '2000-01-01T00:00:00+00:00'
counter=itertools.count(1)
uuid.uuid4=lambda: uuid.UUID(int=next(counter))
entry=repository/'genome-revival-toolkit/scripts/run_toolkit.py'
sys.argv=[str(entry),*sys.argv[2:]]
runpy.run_path(str(entry),run_name='__main__')
'''


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def prepare(root):
    root.mkdir(exist_ok=False,parents=True)
    fixtures=root/'inputs';fixtures.mkdir()
    forward='AGAGGAGAAAGAGGGAAGAGGA';reverse='AAGGAAGAGAGGAGAGGAGAAG'
    rng=random.Random(271104);insert=''.join(rng.choices('ACGT',k=120))
    rc=str(Seq(reverse).reverse_complement());prefix='TCGTACCGTATCGACTACGT';suffix='GCATCGTAGCATACGTCGAT'
    a=prefix+forward+insert+rc+suffix
    b=prefix+forward+insert[:45]+insert[68:]+rc+suffix
    negative=a[:len(prefix)+len(forward)-1]+'C'+a[len(prefix)+len(forward):]
    records={'a':a,'b':b,'negative':negative}
    refs={}
    for name,sequence in records.items():
        path=fixtures/(name+'.gb')
        record=SeqRecord(Seq(sequence),id=name,annotations={'molecule_type':'DNA','topology':'linear','date':'01-JAN-2000'})
        with path.open('w',encoding='utf-8') as handle:SeqIO.write(record,handle,'genbank')
        refs[name]={'path':str(path),'source':'Fixed-seed software compatibility input, no functional or experimental claim.'}
    save(fixtures/'context.json',{'references':refs})
    good={'original_request':'Assess these supplied regions and complete primers; report local predictions only.',
          'references':list(records),'compare_regions':True,
          'assays':[{'id':'regional_pair','forward':forward,'reverse':reverse,'size_resolution_bp':20}]}
    save(fixtures/'positive.json',good)
    unresolved={**good,'references':['a','b'],'assays':[{k:v for k,v in good['assays'][0].items() if k!='size_resolution_bp'}]}
    save(fixtures/'unresolved.json',unresolved)
    save(fixtures/'error.json',{'original_request':good['original_request'],'unknown_field':True})
    (root/'launch_public_cli.py').write_text(LAUNCHER,encoding='utf-8')
    save(root/'CONDITIONS.json',{'cases':[{'id':'positive-'+level+'-'+lang,'request':'positive.json','level':level,'language':lang}
            for level,lang in [('off','en'),('observed','en'),('full','en'),('full','zh')]]+
            [{'id':'unresolved','request':'unresolved.json','level':'observed','language':'en'},
             {'id':'error','request':'error.json','level':'observed','language':'en'}],
        'expectations':{'a':len(forward)+120+len(reverse),'b':len(forward)+97+len(reverse),'negative':None},
        'metadata_control':'Only UUID generation and Trace models.now are deterministic. Observation date is artificial, not experimental evidence.',
        'normalization':'Repository code-source prefix only; no biological value, check, error, report text or data-file identity ignored.'})


def capture(repository,root,label):
    target=root/label;target.mkdir(exist_ok=False)
    conditions=json.loads((root/'CONDITIONS.json').read_text(encoding='utf-8'))
    records=[]
    for kit in ('construct','identity','evidence','crispr'):
        process=subprocess.run([sys.executable,'-X','utf8','-B',str(root/'launch_public_cli.py'),str(repository),'describe',kit],
            capture_output=True,encoding='utf-8',env=dict(os.environ,PYTHONUTF8='1'),timeout=120)
        (target/('describe-'+kit+'.json')).write_text(process.stdout,encoding='utf-8')
        if process.returncode:raise RuntimeError('Baseline describe failed')
    help_process=subprocess.run([sys.executable,'-X','utf8','-B',str(root/'launch_public_cli.py'),str(repository),'--help'],capture_output=True,encoding='utf-8',timeout=120)
    (target/'help.txt').write_text(help_process.stdout,encoding='utf-8')
    for case in conditions['cases']:
        live=root/'live'/case['id'];live.parent.mkdir(exist_ok=True)
        if live.exists():
            assert live.resolve().is_relative_to((root/'live').resolve())
            shutil.rmtree(live)
        settings=root/'settings.json';save(settings,{'trace_level':case['level']})
        env=dict(os.environ,SNAPGENE_TRACE_CONFIG=str(settings),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
        command=[sys.executable,'-X','utf8','-B',str(root/'launch_public_cli.py'),str(repository),'identity',
            '--context',str(root/'inputs/context.json'),'--request',str(root/'inputs'/case['request']),
            '--out-dir',str(live),'--language',case['language']]
        process=subprocess.run(command,capture_output=True,encoding='utf-8',env=env,timeout=180)
        output=target/case['id'];output.mkdir()
        (output/'stdout.json').write_text(process.stdout,encoding='utf-8')
        (output/'stderr.txt').write_text(process.stderr.replace(str(Path.home()),'<USER_HOME>'),encoding='utf-8')
        if live.exists():shutil.copytree(live,output/'files')
        data=json.loads(process.stdout)
        if case['id']=='error':
            assert process.returncode==2 and data['error']=='Unsupported identity fields: unknown_field'
        else:
            assert process.returncode==0
            result=json.loads((live/'result.json').read_text(encoding='utf-8'))
            actual={row['reference']:row.get('amplicon_length_bp') for row in result['assays'][0]['predictions']}
            expected=conditions['expectations'] if case['id']!='unresolved' else {k:conditions['expectations'][k] for k in ('a','b')}
            assert actual==expected,(case['id'],actual)
            wanted='NEEDS_REVIEW' if case['id']=='unresolved' else 'PREDICTED_DIFFERENT'
            assert result['assays'][0]['discrimination']['status']==wanted
            verify=subprocess.run([sys.executable,'-X','utf8','-B',str(root/'launch_public_cli.py'),str(repository),'verify','--out-dir',str(live)],capture_output=True,encoding='utf-8',env=env,timeout=60)
            assert json.loads(verify.stdout)['status']=='verified'
            (output/'verify.json').write_text(verify.stdout,encoding='utf-8')
        records.append({'case':case['id'],'returncode':process.returncode,'independent_expectations':'PASSED'})
    save(target/'CAPTURE.json',{'records':records,'repository_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repository,text=True,encoding='utf-8').strip()})


def compare(root,baseline,current,label):
    before=root/'before';after=root/label
    a={p.relative_to(before).as_posix():p for p in before.rglob('*') if p.is_file() and p.name!='CAPTURE.json'}
    b={p.relative_to(after).as_posix():p for p in after.rglob('*') if p.is_file() and p.name!='CAPTURE.json'}
    rows=[]
    for name in sorted(set(a)|set(b)):
        exact=name in a and name in b and a[name].read_bytes()==b[name].read_bytes()
        normalized=False
        if name in a and name in b and not exact:
            try:
                x=a[name].read_text(encoding='utf-8');y=b[name].read_text(encoding='utf-8')
                for original in (str(baseline),baseline.as_uri(),str(current),current.as_uri()):
                    for form in (original,original.replace('\\','/'),original.replace('\\','\\\\')):
                        x=x.replace(form,'<CODE_SOURCE>');y=y.replace(form,'<CODE_SOURCE>')
                normalized=x==y
                if not normalized and name.endswith('.json'):
                    try:
                        normalized=json.dumps(json.loads(x),sort_keys=True,ensure_ascii=False)==json.dumps(json.loads(y),sort_keys=True,ensure_ascii=False)
                    except ValueError:pass
                if not normalized and name.endswith('.html'):
                    # Inert report JSON object's key order is not a field value.
                    # The entire remaining HTML/JS/CSS must still be identical.
                    pattern=r'(<script[^>]*type="application/json"[^>]*>)(.*?)(</script>)'
                    def ordered(match):
                        return match.group(1)+json.dumps(json.loads(match.group(2)),sort_keys=True,ensure_ascii=False)+match.group(3)
                    try:normalized=re.sub(pattern,ordered,x,flags=re.S)==re.sub(pattern,ordered,y,flags=re.S)
                    except ValueError:pass
            except UnicodeError:pass
        rows.append({'file':name,'before_sha256':digest(a[name]) if name in a else None,
                     'after_sha256':digest(b[name]) if name in b else None,'byte_equal':exact,
                     'structured_or_code_location_equal':normalized,'passed':exact or normalized})
    record={'baseline_commit':'e7b1f1629e9677ff04d9428c3fb7c2fa459cf375',
        'metadata_control':json.loads((root/'CONDITIONS.json').read_text(encoding='utf-8'))['metadata_control'],
        'ignored_fields':[], 'structural_equivalence':'JSON object key order only; every value/type and remaining HTML preserved',
        'rows':rows,'passed':all(r['passed'] for r in rows)}
    save(root/(label+'-comparison.json'),record)
    print(json.dumps({'files':len(rows),'passed':record['passed'],'mismatches':[r['file'] for r in rows if not r['passed']]}),flush=True)
    return record['passed']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',type=Path,required=True);parser.add_argument('--current',type=Path,required=True)
    parser.add_argument('--out-dir',type=Path,required=True);parser.add_argument('--capture-baseline',action='store_true');parser.add_argument('--attempt',default='after-01')
    args=parser.parse_args();baseline=args.baseline.resolve();current=args.current.resolve();root=args.out_dir.resolve()
    if args.capture_baseline:prepare(root);capture(baseline,root,'before')
    else:capture(current,root,args.attempt);return 0 if compare(root,baseline,current,args.attempt) else 2
    print('Baseline captured with independent literal PCR and error expectations.',flush=True)
    return 0
if __name__=='__main__':raise SystemExit(main())
