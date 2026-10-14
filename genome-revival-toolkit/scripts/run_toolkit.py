"""Public Toolkit entry. Scientific computation stays in the shared Core."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from revival.bootstrap import CORE_VERSION
from revival import __version__
from revival.context import ProjectContext, read_json
from revival.runner import run, verify_outputs
from evidence_trace.settings import set_level

EXAMPLES = {
    'construct': {'original_request': 'Prepare the specified donor from my actual templates and verify both donor interfaces.',
                  'method': 'integration_donor', 'target_reference': 'genomic_region', 'cargo_reference': 'marker_template',
                  'target_interval': {'start0': 800, 'end0': 850}, 'cargo_interval': {'start0': 100, 'end0': 900},
                  'arm_length': 200, 'preparation_method': 'gibson'},
    'identity': {'original_request': 'Compare these supplied regions and test whether my candidate PCR distinguishes them.',
                 'references': ['recipient_region', 'donor_region'], 'compare_regions': True,
                 'design_assays': [{'id': 'regional_test', 'target_reference': 'recipient_region',
                                    'interval': {'start0': 100, 'end0': 700}, 'size_resolution_bp': 20}]},
    'evidence': {'original_request': 'Compare the submitted observations and state their genetic-evidence limits.',
                 'observations': [], 'comparisons': [], 'genotype_results': []},
    'crispr': {'original_request': 'Replace the guide using my supplied vector/target, check direction/PAM and self-targets, and provide a planned construction route.',
               'operation': 'replace', 'vector_reference': 'guide_vector', 'target_reference': 'target_region',
               'spacer_seq': 'SUPPLY_EXPLICIT_20_NT_ACGT',
               'strain_genotype': {'description': 'Provide actual strain genotype', 'organism': 'Supply organism',
                                   'existing_markers': [], 'auxotrophies': []}},
}


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description='Genome Revival Toolkit: construct, given-region identity, evidence records and CRISPR plasmid preparation.')
    commands = parser.add_subparsers(dest='command', required=True)
    describe = commands.add_parser('describe', help='Show a minimal input shape; example coordinates are not project answers.')
    describe.add_argument('kit', choices=EXAMPLES)
    inspect = commands.add_parser('inspect', help='Inspect actual context files and declared identities.')
    inspect.add_argument('--context', required=True)
    for kit in EXAMPLES:
        command = commands.add_parser(kit, help='Execute the supported ' + kit + ' workflow.')
        command.add_argument('--context', required=True)
        command.add_argument('--request', required=True)
        command.add_argument('--out-dir', required=True)
        command.add_argument('--trace-dir')
        command.add_argument('--trace-mode', choices=('normal', 'strict'), default='normal')
        command.add_argument('--language', choices=('zh', 'en'), default='zh', help='Report language; captured statements remain original')
    verify = commands.add_parser('verify', help='Check actual output/input versions and the existing Core receipt.')
    verify.add_argument('--out-dir', required=True)
    verify.add_argument('--receipt-sha256')
    level = commands.add_parser('trace-level', help='Set the global collection level for subsequent calls.')
    level.add_argument('level', choices=('off', 'observed', 'full'))
    report = commands.add_parser('rebuild-report', help='Rebuild saved Trace reports; retain stale/missing records.')
    report.add_argument('--trace-dir', required=True)
    report.add_argument('--language', choices=('zh', 'en'), default='zh')
    args = parser.parse_args()
    try:
        if args.command == 'describe':
            result = {'toolkit_version': __version__, 'core_version': CORE_VERSION, 'example_only': True,
                      'request': EXAMPLES[args.kit], 'coordinate_system': '0-based half-open on selected context records',
                      'context': 'references map IDs to actual file paths; use inspect before selecting intervals.'}
        elif args.command == 'inspect':
            result = ProjectContext.load(args.context).describe()
        elif args.command == 'verify':
            result = verify_outputs(args.out_dir, args.receipt_sha256)
        elif args.command == 'trace-level':
            result = {'trace_level': args.level, 'settings': str(set_level(args.level))}
        elif args.command == 'rebuild-report':
            from revival.reporting import rebuild
            from revival.localization import language_scope
            with language_scope(args.language):
                result = rebuild(args.trace_dir)
        else:
            result = run(args.command, args.request, args.context, args.out_dir,
                         trace_mode=args.trace_mode, trace_dir=args.trace_dir, language=args.language)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get('status') not in ('failed', 'incomplete') else 2
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc), 'exception': type(exc).__name__,
                          'recovery': 'Inspect actual inputs and saved steps. Keep current materials; change explicit parameters, not goals or checks.'}, ensure_ascii=False, indent=2))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
