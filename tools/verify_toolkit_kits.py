"""Install an exact Toolkit archive in an empty directory and run its four Kits.

This is an engineering verification tool, not host routing or wet-lab evidence.
Independent expectations come from the package's construction-only generators.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

from project_paths import PROJECT_ROOT


def digest(data):
    return hashlib.sha256(data).hexdigest().upper()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def verify(archive_path, out, *, source_commit=None, repository=PROJECT_ROOT):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    archive_path = Path(archive_path).resolve()
    install = out / 'installed'
    install.mkdir()
    with zipfile.ZipFile(archive_path) as archive:
        actual_members = {member.filename for member in archive.infolist() if not member.is_dir()}
        for member in archive.infolist():
            name = PurePosixPath(member.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in member.filename:
                raise ValueError('Unsafe archive member')
        archive.extractall(install)
    skill = install / 'genome-revival-toolkit'
    manifest = json.loads((skill / 'TOOLKIT-MANIFEST.json').read_text(encoding='utf-8'))
    declared_members = {'genome-revival-toolkit/' + row['path'] for row in manifest['entries']}
    declared_members.add('genome-revival-toolkit/TOOLKIT-MANIFEST.json')
    if actual_members != declared_members or len(declared_members) != len(manifest['entries']) + 1:
        raise ValueError('Archive membership differs from its complete payload manifest')
    if source_commit is not None and manifest['source_commit'] != source_commit:
        raise ValueError('Package does not identify the requested exact source commit')
    source = {}
    if source_commit is not None:
        archive_bytes = subprocess.run(['git', '-C', str(repository), 'archive', '--format=zip', source_commit],
            check=True, capture_output=True).stdout
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as committed:
            source = {name: committed.read(name) for name in committed.namelist() if not name.endswith('/')}
    rows = []
    for entry in manifest['entries']:
        data = (skill / entry['path']).read_bytes()
        if digest(data) != entry['sha256']:
            raise ValueError('Installed payload hash mismatch: ' + entry['path'])
        original = source.get(entry['source_path'])
        generated_notice = (entry['path'] == 'vendor/dna-design-core/THIRD_PARTY_NOTICE.md'
            and entry['source_path'] == 'generated from tools/build_release.py redistribution notice policy')
        if source_commit is not None and original is None and not generated_notice:
            raise ValueError('Installed payload has no committed source mapping: ' + entry['path'])
        if original is not None and original != data:
            raise ValueError('Installed payload differs from committed source: ' + entry['path'])
        rows.append({'file': entry['path'], 'sha256': digest(data), 'source': entry['source_path'],
                     'verdict': 'EXACT_SOURCE_BYTES' if original is not None else
                                ('GENERATED_NOTICE' if generated_notice else 'DIAGNOSTIC_MANIFEST_BYTES'),
                     'note': '' if original is not None else 'Diagnostic snapshot or explicitly generated redistribution notice.'})
    save(out / 'installed-source-hashes.json', rows)
    environment = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    environment.pop('PYTHONPATH', None)
    settings = out / 'trace-settings.json'
    save(settings, {'trace_level': 'observed'})
    environment['SNAPGENE_TRACE_CONFIG'] = str(settings)
    entry = skill / 'vendor/dna-design-core/scripts/run_kit.py'

    def call(label, script, *args):
        completed = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(script), *map(str, args)],
            cwd=install, env=environment, capture_output=True, encoding='utf-8', errors='strict', timeout=420)
        (out / (label + '.stdout.txt')).write_text(completed.stdout, encoding='utf-8')
        (out / (label + '.stderr.txt')).write_text(completed.stderr, encoding='utf-8')
        if completed.returncode:
            raise ValueError(label + ' public entry failed; retained stdout/stderr')
        return completed.stdout

    imported = json.loads(call('runtime-origin', '-c',
        'import sys,json;sys.path.insert(0,sys.argv[1]);from revival.bootstrap import CORE_ROOT;'
        'import core,evidence_trace;print(json.dumps({"core":str(CORE_ROOT),"trace":str(evidence_trace.__file__)}))',
        skill))
    if Path(imported['core']).resolve() != (skill / 'vendor/dna-design-core').resolve():
        raise ValueError('Installation borrowed an external Core')
    if not Path(imported['trace']).resolve().is_relative_to(skill.resolve()):
        raise ValueError('Installation borrowed an external Trace')
    listing = json.loads(call('list', entry, 'list', '--kit-dir', skill / 'kits'))
    save(out / 'catalog.json', listing)
    commands = ('construct', 'identity', 'evidence', 'crispr')
    declarations = {command: json.loads((skill / 'kits' / command / 'kit.json').read_text(encoding='utf-8'))
                    for command in commands}
    if (listing.get('diagnostics') or len(listing['kits']) != len(commands)
            or {row['name'] for row in listing['kits']} != {row['name'] for row in declarations.values()}):
        raise ValueError('Complete package must expose exactly its four declared application Kits')
    records = []
    for command in commands:
        kit = skill / 'kits' / command
        declaration = declarations[command]
        inputs = out / (command + '-inputs')
        call(command + '-generate', kit / 'examples/generate_inputs.py', '--out-dir', inputs)
        target = out / (command + '-output')
        result = json.loads(call(command + '-run', entry, 'run', declaration['name'],
            '--kit-dir', skill / 'kits', '--input', inputs / 'inputs.json', '--out-dir', target))
        actual = json.loads((target / 'result.json').read_text(encoding='utf-8'))
        if command in ('construct', 'crispr'):
            from Bio import SeqIO
            expected = json.loads((inputs / 'EXPECTED.json').read_text(encoding='utf-8'))
            with (Path(actual['delivery']['directory']) / 'construct.gb').open(encoding='utf-8') as handle:
                record = SeqIO.read(handle, 'genbank')
            if str(record.seq) != expected['sequence']:
                raise ValueError(command + ' DNA differs from construction-defined sequence')
        elif command == 'identity':
            expected = json.loads((inputs / 'construction-expected.json').read_text(encoding='utf-8'))
            predictions = {row['reference']: row.get('amplicon_length_bp') for row in actual['assays'][0]['predictions']}
            if predictions != expected:
                raise ValueError('Identity PCR lengths differ from construction-defined lengths')
        elif actual['comparisons'][0]['normalised_difference'] != 0.5:
            raise ValueError('Evidence difference differs from literal 30/50 minus 5/50')
        verified = json.loads(call(command + '-verify', skill / 'scripts/run_toolkit.py',
            'verify', '--out-dir', target))
        if verified['status'] != 'verified' or result['result']['trace']['status'] != 'complete':
            raise ValueError(command + ' file receipt or Trace incomplete')
        graph = json.loads((target / 'evidence-trace/graph.json').read_text(encoding='utf-8'))
        html = (target / 'evidence-trace/index.html').read_text(encoding='utf-8')
        if graph['report']['language'] != 'en' or '<html lang="en">' not in html:
            raise ValueError(command + ' saved Trace report is not in declared English mode')
        if not (target / 'evidence-trace/report.md').read_text(encoding='utf-8').startswith('# '):
            raise ValueError(command + ' saved Markdown report missing')
        loading = target / 'kit-loading/evidence-trace/events.jsonl'
        if 'kit.load' not in loading.read_text(encoding='utf-8'):
            raise ValueError(command + ' actual Kit loading not recorded')
        if command == 'crispr':
            gates = actual['kit_gate_results']
            scopes = {row['scope'] for gate in gates for row in gate['checks']}
            if scopes != {'direction', 'pam', 'vector_self_target'} or not all(gate['passed'] for gate in gates):
                raise ValueError('CRISPR required gates incomplete')
        hashes = [{'file': p.relative_to(target).as_posix(), 'sha256': digest(p.read_bytes()), 'size': p.stat().st_size}
                  for p in sorted(target.rglob('*')) if p.is_file()]
        save(out / (command + '-output-hashes.json'), hashes)
        records.append({'kit': declaration['name'], 'status': actual['status'], 'independent_oracle': 'PASSED',
                        'receipt': verified['status'], 'trace': result['result']['trace']['status'],
                        'report_language': graph['report']['language'], 'output_files': len(hashes)})
    receipt = {'source_commit': manifest['source_commit'], 'archive_sha256': digest(archive_path.read_bytes()),
        'installed_files': len(rows), 'runtime_origin': 'Installed vendored Core and Trace only',
        'kits': records, 'status': 'PASSED', 'official_gitlab_ci': 'NOT_EXECUTED',
        'source_verification': {'status': 'VERIFIED' if source_commit is not None else 'NOT_PERFORMED',
                                'expected_commit': source_commit,
                                'scope': 'All payload source bytes, except explicitly generated redistribution notice.'},
        'evaluation_class': 'Developer-organized known synthetic regression, not autonomous routing or wet experiments'}
    save(out / 'verification.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--source-commit')
    args = parser.parse_args()
    print(json.dumps(verify(args.archive, args.out_dir, source_commit=args.source_commit), indent=2))


if __name__ == '__main__':
    main()
