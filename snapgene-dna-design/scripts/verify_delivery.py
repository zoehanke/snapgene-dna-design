"""Check that current presentation paths belong to the unchanged delivered bundle."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.errors import CoreError
from core.runtime_gate import verify_delivery_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--presented-json', help='JSON path/descriptor list selected for presentation')
    parser.add_argument('--manifest-sha256', help='Expected manifest hash returned by delivery')
    args = parser.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    try:
        entries = json.loads(Path(args.presented_json).read_text(encoding='utf-8')) if args.presented_json else None
        result = verify_delivery_files(args.directory, presented_files=entries,
                                       expected_manifest_sha256=args.manifest_sha256)
    except Exception as exc:
        result = {'status': 'failed', 'error': exc.to_dict() if isinstance(exc, CoreError) else {'message': str(exc)}}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'verified' else 1


if __name__ == '__main__':
    sys.exit(main())
