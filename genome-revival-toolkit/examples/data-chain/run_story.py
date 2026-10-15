"""Run reproducible public commands; no developer helper or molecular algorithm."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from generate_inputs import generate
from independent_check import prepare_observations, check


def run(root, *, launcher=None):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=False)
    toolkit=Path(__file__).resolve().parents[2]
    generate(root/'inputs')
    settings=root/'trace-settings.json';settings.write_text('{"trace_level":"observed"}',encoding='utf-8')
    environment=dict(os.environ,SNAPGENE_TRACE_CONFIG=str(settings),PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
    records=[]
    def command(name,args,expected=0):
        command=[sys.executable,'-X','utf8','-B',str(toolkit/'scripts/run_toolkit.py'),*map(str,args)]
        actual=[sys.executable,'-X','utf8','-B',str(launcher),str(root/(name+'-network.json')),*command[4:]] if launcher else command
        process=subprocess.run(actual,capture_output=True,encoding='utf-8',env=environment,timeout=600)
        (root/(name+'.stdout.json')).write_text(process.stdout,encoding='utf-8')
        (root/(name+'.stderr.txt')).write_text(process.stderr,encoding='utf-8')
        records.append({'name':name,'command':command,'exit_code':process.returncode,'expected_exit_code':expected})
        (root/'COMMANDS.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
        if process.returncode!=expected:raise RuntimeError(name+' public command returned an unexpected exit; retained stdout/stderr describe it.')
        return json.loads(process.stdout)
    context=root/'inputs/context.json'; trace=root/'chain-trace'
    def kit(name,request,out,trace_dir=trace,expected=0):
        value=command(out,[name,'--request',request,'--context',context,'--out-dir',root/out,'--trace-dir',trace_dir,'--language','en'],expected)
        command('verify-'+out,['verify','--out-dir',root/out])
        return value
    kit('construct',root/'inputs/construct-request.json','construct')
    kit('identity',root/'construct/identity-request.json','identity')
    requests=prepare_observations(root/'inputs',root/'construct/identity-handoff.json',root/'identity/identity-expected-results.json',root/'observations')
    for name,path in requests.items():kit('evidence',path,'evidence-'+name)
    context=root/'inputs/crispr/context.json'; guide_trace=root/'crispr-trace'
    kit('crispr',root/'inputs/crispr/check-request.json','crispr-before',guide_trace,2)
    kit('crispr',root/'inputs/crispr/replace-request.json','crispr-after',guide_trace,2)
    report=check(root)
    # View-only publication disclosure; no event or organization is altered.
    sys.path.insert(0,str(toolkit))
    import revival.bootstrap
    from evidence_trace.recorder import load_events
    from evidence_trace.process import assemble
    from evidence_trace.render import render
    for directory in (trace,guide_trace):
        before=(directory/'events.jsonl').read_bytes()
        render(directory,assemble(load_events(directory)[0]),language='en',notes=['Official GitLab CI was not executed.'])
        assert (directory/'events.jsonl').read_bytes()==before
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out-dir',type=Path,required=True)
    print(json.dumps(run(parser.parse_args().out_dir),ensure_ascii=False,indent=2))
