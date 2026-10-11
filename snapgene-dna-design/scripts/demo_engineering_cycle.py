"""Predesigned synthetic demo with real PCR execution, checks and Trace records."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from Bio import SeqIO
from core.tools.snapgene_io import read_native_dna_record
from evidence_trace.recorder import Recorder
from evidence_trace.intake import record_handoff
from evidence_trace.process import assemble, organize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', required=True, type=Path)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error('Use an empty output directory to preserve earlier demonstration evidence')
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT/'fixtures/synthetic/pSynthetic-GFP.gb'
    record = SeqIO.read(source, 'genbank')
    gfp = next(f for f in record.features if f.qualifiers.get('label') == ['GFP'])
    start = int(gfp.location.start)
    if str(record.seq[start:start+6]) != 'ATGAGT':
        raise ValueError('The demo source no longer contains the declared codon')
    expected = str(record.seq[:start+5]) + 'C' + str(record.seq[start+6:])
    params = {'template_seq_or_file': str(source), 'start_0based': start+5,
              'end_0based': start+6, 'alt_seq': 'C', 'method':'inverse_pcr',
              'expected_components':[{'name':'synonymous start','sequence':expected[start:start+30]}],
              'forbidden_components':[{'name':'parent start','sequence':str(record.seq[start:start+30])}]}
    (out/'params.json').write_text(json.dumps(params,indent=2),encoding='utf-8')
    (out/'trace-settings.json').write_text('{"trace_level":"full"}',encoding='utf-8')
    env=dict(os.environ,SNAPGENE_TRACE_CONFIG=str(out/'trace-settings.json'))
    context={'actor':'demo-author','nodes':[
        {'id':'R','kind':'requirement','text':'为同义密码子比较准备DNA对照：GFP第二密码子AGT改为AGC，其余DNA及蛋白序列不变。',
         'requirement_source':{'reference':'predefined-synthetic-demo','form':'summary'}},
        {'id':'D','kind':'decision','text':'演示预设使用完整源质粒的inverse PCR路线。',
         'rationale':'运行已有配方，随后独立核对真实产物与原模板；不把路线预设称为现场AI选择。',
         'responds_to':['R'],'decision_kind':'method_selection'}]}
    (out/'context.json').write_text(json.dumps(context,ensure_ascii=False,indent=2),encoding='utf-8')
    cmd=[sys.executable,'-X','utf8','-B',str(ROOT/'scripts/run_recipe.py'),'--recipe','recipe_site_directed_mutagenesis',
         '--params-json',str(out/'params.json'),'--out-dir',str(out),'--trace-dir',str(out/'trace'),
         '--trace-input',str(out/'context.json'),'--finalize','--confirmed','--json']
    run=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,encoding='utf-8',errors='replace')
    (out/'execution.json').write_text(run.stdout,encoding='utf-8')
    (out/'execution.stderr').write_text(run.stderr,encoding='utf-8')
    if run.returncode:
        print(run.stderr,file=sys.stderr)
        return run.returncode
    product=read_native_dna_record(out/'authoritative/construct.dna')
    actual_gfp=next(f for f in product.features if f.qualifiers.get('label') == ['GFP'])
    independent = {'exact_sequence':str(product.seq)==expected,
        'protein_unchanged':str(gfp.extract(record.seq).translate())==str(actual_gfp.extract(product.seq).translate()),
        'source_labels_retained':{f.qualifiers.get('label',[''])[0] for f in record.features} <= {f.qualifiers.get('label',[''])[0] for f in product.features}}
    if not all(independent.values()):
        raise ValueError('Independent product checks failed: ' + str(independent))
    r=Recorder(out/'trace',mode_at_capture='full')
    delivered=[out/'authoritative'/name for name in ('construct.gb','construct.dna','construct.fasta')]
    delivered.append(out/'primer_order_table.tsv')
    handoff=record_handoff(r,[{'path':str(p),'purpose':'同义突变设计文件或实际制备引物'} for p in delivered])
    independent['all_linked'] = all(f['status']=='linked' for f in handoff['files'])
    if not independent['all_linked']:
        raise ValueError('Some actual delivery files lack generation records')
    graph=assemble(r.events)
    checks=[n['key'] for n in graph['nodes'] if n['kind']=='validation']
    artifacts=[k for f in handoff['files'] for k in f['artifact_refs']]
    process={'stages':[{'id':'stage','title':'构建配对DNA','purpose':'计算和核对同义突变，不推断表达表现',
                       'step_ids':['request','route','checks','files'],'source_refs':['R@1']}],
             'steps':{'request':{'kind':'requirement','content':context['nodes'][0]['text'],'source_refs':['R@1']},
                      'route':{'kind':'choice','content':context['nodes'][1]['text'],'subject_ref':'D@1','source_refs':['D@1'],
                               'reason':{'origin':'original_statement','text':context['nodes'][1]['rationale'],'source_refs':['D@1']}},
                      'checks':{'kind':'program_result','content':'程序已实际检查本次保存产物；具体项目及范围见检查记录。','source_refs':checks},
                      'files':{'kind':'artifact','content':'交付同义突变设计文件与制备引物。','source_refs':artifacts}},
             'relations':[],'paths':[],'unresolved':[],'detail_refs':[]}
    organize(r,{'schema_version':'trace-organization-v1','id':'demo','basis':{k:graph['snapshot'][k] for k in ('trace_id','through_sequence')},
        'design_process':process,'report_plan':{'profile':'research-report-v1','title':'同义密码子对照：实际执行与证据',
        'context':{'text':'预设的合成演示任务和路线，实际运行程序并保留结果；不是现场AI盲测或湿实验。DNA及翻译核对不证明表达量相同。','source_refs':['R@1','D@1']}}})
    r.render()
    (out/'independent-checks.json').write_text(json.dumps({**independent,'handoff_files':len(delivered),
        'scope':'Synthetic engineering demonstration'},indent=2),encoding='utf-8')
    print(out/'trace/index.html')
    return 0


if __name__=='__main__':sys.exit(main())
