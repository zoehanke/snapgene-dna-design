"""Run a local command once, observing declared input/output files around execution."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evidence_trace.runtime import trace_file_call, TraceStopped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace-dir', required=True)
    parser.add_argument('--trace-mode', choices=['normal', 'strict'], default='normal')
    parser.add_argument('--input-file', action='append', default=[])
    parser.add_argument('--output-file', action='append', default=[])
    parser.add_argument('--role', choices=['derived', 'document', 'qc', 'preview'], default='derived')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('Provide a command after --')
    def execute(argv):
        # No shell interpolation. The command's own stdout/stderr remain visible.
        result = subprocess.run(argv, encoding='utf-8', errors='replace', check=True)
        return {'exit_code': result.returncode}
    try:
        trace_file_call('local_command', execute, args=(command,), trace_dir=args.trace_dir,
                        trace_mode=args.trace_mode, input_paths=args.input_file,
                        expected_paths=args.output_file, output_paths=lambda _: args.output_file,
                        artifact_role=args.role)
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    except (OSError, TraceStopped) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
