"""Validate or deliver an actual locally recorded workflow using shared Core checks."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.workflow_validation import validate_candidate
from core.workflow_delivery import deliver_result
from core.errors import CoreError, ValidationError
from core.workflow import read_workflow_record
from evidence_trace.runtime import traced_run, add_trace_arguments, trace_options


@traced_run('workflow')
def execute(config,out_dir,deliver):
    allowed = {'record_file', 'sources', 'steps', 'candidate', 'requirements', 'primers', 'files',
               'result_kind', 'required_scopes', 'output_step', 'product_index', 'validation', 'sanity_context','report_notes'}
    if not isinstance(config, dict) or set(config) - allowed:
        raise ValidationError('WORKFLOW_CONFIG_INVALID', 'Unknown or invalid workflow configuration fields',
                              details={'supported_fields': sorted(allowed)})
    history=read_workflow_record(config['record_file'] if config.get('record_file') else config)
    sources=config.get('sources',history.get('sources',{}))
    steps=history['steps']
    options={key:config[key] for key in ('primers','result_kind','required_scopes','output_step','product_index','sanity_context','report_notes') if key in config}
    reference=config.get('candidate') or history.get('selected_product_ref')
    candidate=reference
    if isinstance(reference,str) and reference.startswith('$'):
        from core.handlers.composite_pipeline import _resolve_param_val,_resolve_source_records
        from core.workflow_validation import _step
        records=[_step(s) for s in steps]
        candidate=_resolve_param_val(reference,{s.step_id:s.result for s in records if not s.error},_resolve_source_records(sources))
        selected=reference[1:].split('.')
        options.setdefault('output_step',selected[0])
        if len(selected)==3 and selected[1]=='products':options.setdefault('product_index',int(selected[2]))
    if candidate is None:raise ValidationError('EXPLICIT_PRODUCT_REQUIRED','Select an actual product_ref; multiple products cannot be selected implicitly')
    if deliver:
        return deliver_result(config.get('requirements',{}),sources,steps,candidate,out_dir,
                              validation=config.get('validation'),**options)
    report=validate_candidate(config.get('requirements',{}),sources,steps,candidate,files=config.get('files'),**options)
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    (out/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'status':report['overall'],'validation_file':str((out/'validation.json').resolve()),
            'scope_results':{key:value['status'] for key,value in report['scope_results'].items()},'errors':report['errors'],
            'goal_coverage': report['goal_coverage'], 'task_completion':report['task_completion'],
            'preparation_quality': report['preparation_quality'],'verification_quality':report['verification_quality']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input')
    parser.add_argument('--workspace',help='Finalize current executed state without copying DNA or record paths')
    parser.add_argument('--candidate-ref',help='Choose the actual $step.products.N or verification subject reference')
    parser.add_argument('--result-kind',choices=['construct','component','verification','primers','protocol'])
    parser.add_argument('--out-dir',required=True)
    parser.add_argument('--deliver',action='store_true')
    parser.add_argument('--confirmed',action='store_true',help='Use existing user authorization for delivery')
    add_trace_arguments(parser)
    args=parser.parse_args()
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    try:
        if args.deliver and not args.confirmed:
            raise ValueError('Delivery requires the existing authorization flag --confirmed')
        if not args.input and not args.workspace:raise ValidationError('WORKSPACE_REQUIRED','Use --input or --workspace')
        config=json.loads(Path(args.input).read_text(encoding='utf-8-sig')) if args.input else {}
        if args.workspace:config.setdefault('record_file',str(Path(args.workspace)/'steps.json'))
        if args.candidate_ref:config['candidate']=args.candidate_ref
        if args.result_kind:config['result_kind']=args.result_kind
        result=execute(config,args.out_dir,args.deliver,**trace_options(args))
    except Exception as exc:
        result={'status':'failed','error':exc.to_dict() if isinstance(exc,CoreError) else {'message':str(exc)}}
    if result.get('status')=='delivered':
        result={key:result[key] for key in ('status','directory','files','manifest_sha256','present_files','goal_coverage','task_completion')}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result.get('status') in ('verified','delivered') else 1

if __name__=='__main__':sys.exit(main())
