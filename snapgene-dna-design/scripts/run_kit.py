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
    args = parser.parse_args()
    try:
        if args.command == 'run':
            inputs = json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
            result = execute(args.name, inputs, args.out_dir, args.kit_dir, **trace_options(args))
        else:
            result = KitCatalog(args.kit_dir).describe(args.name if args.command == 'describe' else None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('status') == 'failed' or result.get('result', {}).get('status') in ('failed', 'incomplete') else 0
    except Exception as error:
        print(json.dumps({'status':'failed','error':error.to_dict() if isinstance(error,CoreError)
                          else {'code':'KIT_EXECUTION_FAILED','message':str(error)}},ensure_ascii=False,indent=2))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
