"""Check the exact official commit and every declared source file's raw bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True,
                                   encoding='utf-8', errors='strict').strip()


def inspect(root, commit):
    actual = git(root, 'rev-parse', 'HEAD')
    if actual != commit:
        raise ValueError('Checkout does not identify the required official commit')
    manifest_raw = (root / 'FILE-LIST.json').read_bytes()
    committed_manifest = subprocess.check_output(
        ['git', '-C', str(root), 'show', 'HEAD:FILE-LIST.json'])
    if manifest_raw != committed_manifest:
        raise ValueError('Manifest differs from its committed raw bytes')
    manifest = json.loads(manifest_raw.decode('utf-8'))
    rows = []
    for item in manifest['entries']:
        name = item['destination']
        original = root / name
        path = original.resolve()
        if not path.is_relative_to(root.resolve()) or original.is_symlink():
            raise ValueError('Source manifest path escapes its checkout or is a symlink')
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        rows.append({'file': name, 'expected_sha256': item['sha256'].lower(),
                     'actual_sha256': digest, 'expected_bytes': item['size'],
                     'actual_bytes': len(raw),
                     'matches': digest == item['sha256'].lower() and len(raw) == item['size']})
    tracked = set(git(root, 'ls-files').splitlines())
    declared = {row['file'] for row in rows}
    if len(declared) != len(rows) or tracked != declared | {'FILE-LIST.json'}:
        raise ValueError('Manifest omits or duplicates tracked source files')
    declared_count = len(rows)
    rows.append({'file': 'FILE-LIST.json',
                 'expected_sha256': hashlib.sha256(committed_manifest).hexdigest(),
                 'actual_sha256': hashlib.sha256(manifest_raw).hexdigest(),
                 'expected_bytes': len(committed_manifest), 'actual_bytes': len(manifest_raw),
                 'matches': manifest_raw == committed_manifest})
    return {'tested_commit': actual, 'declared_files': declared_count, 'verified_files': len(rows),
            'all_match': all(row['matches'] for row in rows), 'files': rows,
            'manifest_binding': 'FILE-LIST.json is compared with its Git blob; all other files use its declared hashes',
            'interpretation': 'Raw file consistency, not scientific correctness or wet-lab validation'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--report-json', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.commit):
        parser.error('commit must be an exact lowercase Git SHA')
    result = inspect(args.source_dir.resolve(), args.commit)
    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}))
    return 0 if result['all_match'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
