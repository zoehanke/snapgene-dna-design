"""Execute one tool/Recipe and save replayable facts; no planned route is required."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.workflow import run_step, StepExecution, product_summaries, step_summary, read_workflow_record
from core.errors import CoreError, ValidationError
from core.tools.result import ToolResult
from core.models.molecule import as_molecule
from evidence_trace.runtime import traced_run, add_trace_arguments, trace_options


def restore(data):
    from core.workflow_validation import _step
    return _step(data)


@traced_run('step')
def execute(config,out_dir):
    if config.get('history_file'):
        history=read_workflow_record(config['history_file'])
        extra=config.get('sources',{})
        if not isinstance(extra,dict):
            raise ValidationError('WORKFLOW_RECORD_INVALID','sources must be an object keyed by material ids')
        config={**config,'previous':history['steps'],'sources':{**history.get('sources',{}),**extra}}
    previous=[restore(row) for row in config.get('previous',[])]
    history=[row.to_dict() for row in previous]
    # run_step replays imported histories once before resolving their products.
    record=run_step(config['method'],config.get('params',{}),step_id=config.get('step_id','step'),
                    sources=config.get('sources',{}),previous=previous,requirements=config.get('requirements'))
    out=Path(out_dir)
    out.mkdir(parents=True,exist_ok=True)
    histories=history+[record.to_dict()]
    payload={'status':record.status,'steps':histories,'sources':config.get('sources',{}),
             'requirements':record.requirements,'goal_coverage':record.goal_coverage,'task_completion':record.task_completion,
             'products':product_summaries(record.result,record.step_id) if record.result else [],'error':record.error,
             'summary':step_summary(record)}
    selectable=[row for row in histories if row.get('result') and not row.get('error')
                and row['result']['products'] and row['result']['analysis'].get('result_kind') not in ('verification','primers','protocol')]
    payload['selected_product_ref']=f'${selectable[-1]["step_id"]}.products.0' if selectable and len(selectable[-1]['result']['products'])==1 else None
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
    parser.add_argument('--input',help='One step JSON: method, params, optional original sources/goals')
    parser.add_argument('--out-dir')
    parser.add_argument('--workspace',help='Keep executed steps.json and reuse its actual products automatically')
    parser.add_argument('--status',action='store_true',help='Show current materials, last checks and product references')
    parser.add_argument('--full',action='store_true',help='Include complete stored step facts instead of the concise summary')
    add_trace_arguments(parser)
    args=parser.parse_args()
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    try:
        workspace=Path(args.workspace).resolve() if args.workspace else None
        if args.status:
            if workspace is None:raise ValidationError('WORKSPACE_REQUIRED','--status requires --workspace')
            current=read_workflow_record(workspace/'steps.json')
            result={'status':current['status'],'selected_product_ref':current.get('selected_product_ref'),
                    'sources':list(current['sources']),'products':[p for row in current['steps'] if row.get('result') and not row.get('error')
                    for p in product_summaries(restore(row).result,row['step_id'])],
                    'summary':current.get('summary'),'record_file':str(workspace/'steps.json'),'error':current.get('error')}
            print(json.dumps(result,ensure_ascii=False,indent=2));return 0
        if not args.input or not (args.out_dir or workspace):
            raise ValidationError('STEP_CONFIG_REQUIRED','Use --input plus --workspace or --out-dir')
        config=json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
        if not isinstance(config,dict):raise ValidationError('STEP_CONFIG_INVALID','Step input must be an object with method and params')
        if workspace and (workspace/'steps.json').is_file() and not config.get('history_file'):
            config['history_file']=str(workspace/'steps.json')
        prior=read_workflow_record(config['history_file']) if config.get('history_file') else {'steps':[]}
        count=len(prior['steps'])
        config.setdefault('step_id',f'step_{count+1:03d}')
        destination=Path(args.out_dir) if args.out_dir else workspace/'steps'/f'{count+1:03d}'
        result=execute(config,destination,**trace_options(args))
        result['record_file']=str((destination/'steps.json').resolve())
        if workspace:
            workspace.mkdir(parents=True,exist_ok=True)
            pending=workspace/'steps.json.tmp'
            pending.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            pending.replace(workspace/'steps.json')
            result['record_file']=str(workspace/'steps.json')
    except Exception as exc:
        result={'status':'failed','error':exc.to_dict() if isinstance(exc,CoreError) else {'message':str(exc),'write_authoritative_artifact':False}}
    if args.full:
        payload=result
    else:
        payload={**result.get('summary',{}),**{key:result[key] for key in ('status','products','material_files','error','goal_coverage','task_completion','selected_product_ref') if key in result}}
        payload['completed_prefix']=[row['step_id'] for row in result.get('steps',[]) if row['status']=='completed']
        if result.get('record_file'):payload['record_file']=result['record_file']
    print(json.dumps(payload,ensure_ascii=False,indent=2))
    return 1 if result['status']=='failed' else 0

if __name__=='__main__':sys.exit(main())
