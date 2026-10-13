"""Build one standalone Toolkit from an exact Git archive; worktree builds are diagnostics."""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import subprocess
import tempfile
import zipfile

from build_release import _collect, _entry, _third_party_notice
from check_redistributable import inspect_zip
from project_paths import PROJECT_ROOT

PREFIX = 'genome-revival-toolkit/'
CORE_PREFIXES = ('core/', 'evidence_trace/', 'schemas/', 'scripts/', 'planning/', 'rules/',
                 'references/', 'third_party/')
CORE_ROOT_FILES = {'VERSION', 'LICENSE', 'requirements.txt', 'requirements-tested.txt',
                   'requirements-optional.txt', 'THIRD_PARTY_NOTICE.md'}
DNA_SUFFIXES = {'.dna', '.gb', '.gbk', '.gbff', '.fa', '.fasta', '.fna', '.ab1'}
PRIVATE_PATH = re.compile(
    r"(?:\b[A-Za-z]:[\\/]"
    r"(?!(?:Program Files(?: \(x86\))?|Windows|Tools|SnapGene[ 0-9*_.-]*|Python[0-9*_.-]*|"
    r"Anaconda[0-9*_.-]*|Miniconda[0-9*_.-]*)[\\/])"
    r"(?!Users[\\/](?:\.{3}|<[^>]+>|%[^%]+%|\*)[\\/])"
    r"[^\s\\/\"'<>`]+[\\/]|/(?:Users|home)/[^/\s]+/)", re.IGNORECASE)
DEVELOPMENT_SOURCE = {'scripts/run_architecture_recovery_examples.py',
                      'references/architecture-decision-record-v091.md'}


def _git(repository, *args, text=True):
    return subprocess.run(['git', '-C', str(repository), *args], check=True, capture_output=True,
                          **({'encoding': 'utf-8', 'errors': 'replace'} if text else {})).stdout


def _commit(repository, value=None):
    value = value or 'HEAD'
    if value != 'HEAD' and not re.fullmatch(r'[0-9a-fA-F]{7,40}', value):
        raise ValueError('--source-commit must identify a commit by SHA.')
    return _git(repository, 'rev-parse', '--verify', value + '^{commit}').strip()


def _sources(root):
    return [p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()]


def _skip(relative, *, vendor):
    parts = PurePosixPath(relative).parts
    if any(p in ('__pycache__', 'vendor', '.git', '.claude', '.venv', 'dist', 'output', 'build', 'tests', 'fixtures') for p in parts):
        return True
    suffixes = ''.join(Path(relative).suffixes).lower()
    if (relative.endswith(('.pyc', '.log', '.jsonl')) or Path(relative).suffix.lower() in DNA_SUFFIXES
            or suffixes.endswith(('.gz', '.zip', '.tar', '.bz2', '.xz', '.bam', '.fastq', '.fq'))):
        return True
    if Path(relative).name in ('INSTALL-SOURCE.json', 'TOOLKIT-MANIFEST.json', 'RELEASE-MANIFEST.json', 'AGENTS.md', 'CLAUDE.md'):
        return True
    if vendor:
        if Path(relative).name.lower() == 'skill.md' or any(p in ('agents', 'agent', 'examples', 'docs') for p in parts):
            return True
        return (relative in DEVELOPMENT_SOURCE or
                not (relative in CORE_ROOT_FILES or relative.startswith(CORE_PREFIXES)))
    return False


def _reviewed(root, *, vendor):
    if not root.is_dir():
        raise ValueError('Source snapshot is missing ' + root.name)
    names = [name for name in _sources(root) if not _skip(name, vendor=vendor)]
    entries = [entry for entry in _collect(root, source_files=names) if entry['redistributable']]
    for entry in entries:
        path = root / entry['path']
        if path.suffix.lower() in ('.py', '.md', '.json', '.txt', '.yaml', '.yml'):
            content = path.read_text(encoding='utf-8', errors='replace')
            if PRIVATE_PATH.search(content.replace('\\\\', '\\')):
                raise ValueError('Private absolute development path in package source: ' + entry['path'])
    return entries


def _trace_version(core):
    module = ast.parse((core / 'evidence_trace/__init__.py').read_text(encoding='utf-8', errors='replace'))
    for node in module.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__version__' for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('Trace source does not declare its version.')


def _write_archive(out, snapshot, source_commit, *, diagnostic, baseline_commit=None):
    toolkit = snapshot / 'genome-revival-toolkit'
    core = snapshot / 'snapgene-dna-design'
    for name in ('SKILL.md', 'README.md', 'LICENSE', 'THIRD_PARTY_NOTICE.md', 'requirements.txt',
                 'VERSION', 'scripts/run_toolkit.py', 'revival/construct.py', 'revival/context.py',
                 'revival/identity.py', 'revival/evidence.py', 'revival/bootstrap.py'):
        if not (toolkit / name).is_file():
            raise ValueError('Toolkit source is not ready for packaging: ' + name)
    version = (toolkit / 'VERSION').read_text(encoding='utf-8', errors='replace').strip()
    core_version = (core / 'VERSION').read_text(encoding='utf-8', errors='replace').strip()
    trace_version = _trace_version(core)
    if not all(re.fullmatch(r'\d+\.\d+\.\d+(?:[a-zA-Z0-9.\-]*)?', str(v)) for v in (version, core_version, trace_version)):
        raise ValueError('Toolkit/Core/Trace versions must be explicit safe version identifiers.')
    files = {}
    entries = []
    for folder, vendored in ((toolkit, False), (core, True)):
        for entry in _reviewed(folder, vendor=vendored):
            source_rel = folder.name + '/' + entry['path']
            destination = ('vendor/dna-design-core/' if vendored else '') + entry['path']
            data = (folder / entry['path']).read_bytes()
            if vendored and entry['path'] == 'THIRD_PARTY_NOTICE.md':
                text = _third_party_notice(redistributable=True) + ('\nThis is the same-version upstream Core runtime subset bundled inside Genome Revival Toolkit. '
                     'It is not a separately installed Skill. User DNA, fixtures, developer records and the upstream Skill entry are excluded.\n')
                data = text.encode('utf-8')
                entry = _entry(entry['path'], text)
                source_rel = 'generated from tools/build_release.py redistribution notice policy'
            files[destination] = data
            entries.append({'path': destination, 'source_path': source_rel, 'sha256': hashlib.sha256(data).hexdigest().upper(),
                            'size': len(data), 'license': entry['license'], 'source_category': entry['source_category']})
    required_vendor = ('VERSION', 'LICENSE', 'THIRD_PARTY_NOTICE.md', 'requirements-tested.txt',
                       'core/__init__.py', 'core/workflow.py', 'core/runtime_gate.py', 'evidence_trace/__init__.py',
                       'schemas/construction-task-v1.json')
    for name in required_vendor:
        if 'vendor/dna-design-core/' + name not in files:
            raise ValueError('Required upstream runtime/license source omitted: ' + name)
    suffix = '-working-tree' if diagnostic else ''
    filename = f'genome-revival-toolkit-v{version}{suffix}.zip'
    manifest = {'schema_version': 'genome-revival-toolkit-package-v1', 'toolkit_version': version,
                'core_version': core_version, 'trace_version': trace_version, 'package': filename,
                'source_commit': source_commit, 'baseline_commit': baseline_commit,
                'package_class': 'working-tree-diagnostic' if diagnostic else 'frozen-source-candidate',
                'git_archive': not diagnostic, 'readiness': 'Packaging does not certify domain or experimental readiness.',
                'single_core_source': 'snapgene-dna-design at the same source snapshot; vendor is generated, not maintained separately',
                'file_count': len(entries), 'entries': sorted(entries, key=lambda e: e['path']),
                'manifest_scope': 'Every payload file; this manifest excludes itself.'}
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')
    files['TOOLKIT-MANIFEST.json'] = manifest_bytes
    out.mkdir(parents=True, exist_ok=True)
    archive_path = out / filename
    if archive_path.exists():
        raise FileExistsError('Preserve the previous package; choose a fresh out-dir: ' + filename)
    with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(PREFIX + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP CRC check failed.')
        if sum(Path(name).name.lower() == 'skill.md' for name in archive.namelist()) != 1:
            raise ValueError('Package must contain exactly one Skill entry.')
        for entry in manifest['entries']:
            if hashlib.sha256(archive.read(PREFIX + entry['path'])).hexdigest().upper() != entry['sha256']:
                raise ValueError('Package payload differs from manifest.')
    if inspect_zip(archive_path):
        raise ValueError('Known restricted material appeared in the Toolkit package.')
    sidecar = out / (filename[:-4] + '.TOOLKIT-MANIFEST.json')
    sidecar.write_bytes(manifest_bytes)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest().upper()
    (out / (filename + '.sha256')).write_text(digest + '  ' + filename + '\n', encoding='utf-8', errors='replace')
    return {'archive': str(archive_path), 'manifest': str(sidecar), 'sha256': digest,
            'source_commit': source_commit, 'package_class': manifest['package_class'],
            'file_count': manifest['file_count'], 'zip_crc': 'PASSED',
            'toolkit_version': version, 'core_version': core_version, 'trace_version': trace_version}


def build_toolkit(repository, out_dir, *, source_commit=None, working_tree=False):
    repository, out = Path(repository).resolve(), Path(out_dir).resolve()
    if working_tree:
        if source_commit is not None:
            raise ValueError('--working-tree cannot claim --source-commit.')
        return _write_archive(out, repository, None, diagnostic=True, baseline_commit=_commit(repository))
    commit = _commit(repository, source_commit)
    data = _git(repository, 'archive', '--format=zip', commit, 'genome-revival-toolkit', 'snapgene-dna-design', text=False)
    with tempfile.TemporaryDirectory(prefix='genome-toolkit-source-') as temp:
        snapshot = Path(temp)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                name = info.filename.replace('\\', '/')
                if (name.startswith('/') or '..' in PurePosixPath(name).parts or PureWindowsPath(name).drive or
                        (info.external_attr >> 16) & 0o170000 == 0o120000):
                    raise ValueError('Unsafe source archive member: ' + name)
            archive.extractall(snapshot)
        return _write_archive(out, snapshot, commit, diagnostic=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--source-commit')
    parser.add_argument('--working-tree', action='store_true', help='Diagnostic only; never a frozen source candidate.')
    args = parser.parse_args(argv)
    try:
        result = build_toolkit(PROJECT_ROOT, args.out_dir, source_commit=args.source_commit, working_tree=args.working_tree)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
