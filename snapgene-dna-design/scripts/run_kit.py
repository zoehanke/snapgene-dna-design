"""Discover, describe or explicitly run a local manifest-defined Kit."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.kits import KitCatalog
from core.errors import CoreError
from evidence_trace.runtime import traced_run, add_trace_arguments, trace_options


@traced_run('kit.contribution')
def execute_contribution(command,name,contribution,inputs,out_dir,directories):
    catalog=KitCatalog(directories)
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    if command=='pipeline':
        from core.workflow import run_step
        row=next((r for r in catalog._require(name).manifest['contributions'] if r['target']=='pipeline' and r['name']==contribution),None)
        if row is None:raise ValueError('Requested Pipeline template is not declared.')
        catalog.load(name)
        with catalog.execution_scope(name,inputs):
            step=run_step(catalog.contribution_name(catalog._require(name),row),{'inputs':inputs})
        result=step.to_dict()
        filename='steps.json'
    elif command=='gate':
        result=catalog.gate(name,contribution,candidate=inputs['candidate'],sources=inputs.get('sources',{}),
            requirements=inputs.get('requirements'),steps=inputs.get('steps',[]),inputs=inputs.get('inputs',{}))
        filename='gate-result.json'
    else:
        catalog.load(name)
        result=catalog.evaluate_rules(name,contribution,inputs['trigger'],inputs['context'])
        filename='rule-result.json'
    (out/filename).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


@traced_run('kit.load')
def load(catalog, name, out_dir):
    catalog.load(name)
    return catalog.describe(name)


def execute(name, inputs, out_dir, directories, **options):
    catalog = KitCatalog(directories)
    catalog.validate_inputs(name, inputs)
    # Loading has its own facts. A Kit may retain an existing complete domain
    # Trace/receipt boundary, which must not nest in our loading recorder.
    loading = Path(out_dir) / 'kit-loading'
    if options.get('trace_dir'):
        options['trace_dir'] = str(Path(options['trace_dir']) / 'kit-loading')
    metadata = load(catalog, name, loading, **options)
    result = catalog.run(name, inputs, out_dir)
    return {'status': 'completed', 'kit': metadata, 'result': result,
            'loading_trace_directory': str(Path(options.get('trace_dir') or loading/'evidence-trace').resolve())}


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('list', 'describe', 'run'):
        sub = commands.add_parser(command)
        sub.add_argument('--kit-dir', action='append', default=[], help='Explicit local Kit or container directory; no remote search')
        if command != 'list':
            sub.add_argument('name')
        if command == 'run':
            sub.add_argument('--input', required=True)
            sub.add_argument('--out-dir', required=True)
            add_trace_arguments(sub)
    for command in ('pipeline','gate','rules'):
        sub=commands.add_parser(command)
        sub.add_argument('name');sub.add_argument('contribution')
        sub.add_argument('--kit-dir',action='append',default=[])
        sub.add_argument('--input',required=True);sub.add_argument('--out-dir',required=True)
        add_trace_arguments(sub)
    args = parser.parse_args()
    try:
        if args.command in ('pipeline','gate','rules'):
            inputs=json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
            result=execute_contribution(args.command,args.name,args.contribution,inputs,args.out_dir,args.kit_dir,**trace_options(args))
        elif args.command == 'run':
            inputs = json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
            result = execute(args.name, inputs, args.out_dir, args.kit_dir, **trace_options(args))
        else:
            result = KitCatalog(args.kit_dir).describe(args.name if args.command == 'describe' else None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('status') in ('failed','incomplete','blocked') or result.get('passed') is False or result.get('result', {}).get('status') in ('failed', 'incomplete','blocked') else 0
    except Exception as error:
        print(json.dumps({'status':'failed','error':error.to_dict() if isinstance(error,CoreError)
                          else {'code':'KIT_EXECUTION_FAILED','message':str(error)}},ensure_ascii=False,indent=2))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
