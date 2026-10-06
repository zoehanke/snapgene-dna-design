"""Execute one tool/Recipe and save replayable facts; no planned route is required."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.workflow import run_step, StepExecution, product_summaries
from core.tools.result import ToolResult
from core.models.molecule import as_molecule
from evidence_trace.runtime import traced_run, add_trace_arguments, trace_options


def restore(data):
    result=data.get('result')
    if result is not None:
        result=ToolResult([as_molecule(p) for p in result['products']],result['analysis'],result['checks'])
    return StepExecution(data['step_id'],data['method'],data['params'],result,data.get('error'),
                         data.get('input_versions',[]),data.get('source_versions',{}),data.get('conditions',{}),data.get('operations',[]))


@traced_run('step')
def execute(config,out_dir):
    if config.get('history_file'):
        history=json.loads(Path(config['history_file']).read_text(encoding='utf-8'))
        config={**config,'previous':history['steps'],'sources':config.get('sources',history.get('sources',{}))}
    previous=[restore(row) for row in config.get('previous',[])]
    history=[row.to_dict() for row in previous]
    # Imported histories are replayed before they become referenceable results.
    if previous:
        from core.workflow_validation import replay_steps
        previous=replay_steps(previous,config.get('sources',{}))
    record=run_step(config['method'],config.get('params',{}),step_id=config.get('step_id','step'),
                    sources=config.get('sources',{}),previous=previous)
    out=Path(out_dir)
    out.mkdir(parents=True,exist_ok=True)
    histories=history+[record.to_dict()]
    payload={'status':record.status,'steps':histories,'sources':config.get('sources',{}),
             'products':product_summaries(record.result) if record.result else [],'error':record.error}
    (out/'steps.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    if record.result:
        from core.tools import export_snapgene
        saved={}
        for index,m in enumerate(record.result.products):
            if m.record_version not in saved:
                saved[m.record_version]=export_snapgene(m,out/'materials',filename_base='product_'+str(index)).analysis
        payload['material_files']=saved
    return payload


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True)
    parser.add_argument('--out-dir',required=True)
    parser.add_argument('--full',action='store_true',help='Include complete stored step facts instead of the concise summary')
    add_trace_arguments(parser)
    args=parser.parse_args()
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    try:
        config=json.loads(Path(args.input).read_text(encoding='utf-8'))
        result=execute(config,args.out_dir,**trace_options(args))
    except Exception as exc:
        result={'status':'failed','error':{'message':str(exc),'write_authoritative_artifact':False}}
    if args.full:
        payload=result
    else:
        payload={key:result[key] for key in ('status','products','material_files','error') if key in result}
        payload['completed_prefix']=[row['step_id'] for row in result.get('steps',[]) if row['status']=='completed']
        payload['record_file']=str((Path(args.out_dir)/'steps.json').resolve())
    print(json.dumps(payload,ensure_ascii=False,indent=2))
    return 1 if result['status']=='failed' else 0

if __name__=='__main__':sys.exit(main())
