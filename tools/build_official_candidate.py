"""Select an auditable official source candidate. Never commits, pushes or publishes."""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import posixpath
import re
import subprocess
from urllib.parse import quote, urlsplit
import zipfile

from project_paths import PROJECT_ROOT

LIMIT_BYTES = 50_000_000
GITHUB_SOURCE = 'https://github.com/zoehanke/snapgene-dna-design'
INNER = ('snapgene-dna-design/', 'genome-revival-toolkit/')
ROOT_SOURCE = {'.gitlab-ci.yml': 'Required official CI entry',
               'LICENSE': 'Project source license',
               'THIRD_PARTY_NOTICE.md': 'Dependency and inherited-template license attribution'}
DNA_SUFFIXES = {'.dna', '.gb', '.gbk', '.gbff', '.fa', '.fasta', '.fna', '.ab1'}
EXCLUDED_SUFFIXES = {'.pyc', '.log', '.jsonl', '.zip', '.gz', '.tar', '.bz2', '.xz',
                     '.exe', '.dll', '.so', '.dylib', '.png', '.jpg', '.jpeg', '.gif',
                     '.pdf', '.mp4', '.mov', '.webm', '.wav', '.mp3'}
DEVELOPMENT_PARTS = {'.git', '.venv', '__pycache__', '.pytest_cache', '.codex',
                     'dist', 'output', 'build', 'reports', 'results', 'question-bank'}
DEVELOPMENT_TEST = 'tests/test_official_candidate_selection.py'
PRIVATE_PATH = re.compile(r'[A-Za-z]:[\\/]+(?:codex_project[^\\/]*[\\/]|Users[\\/]+([^\\/\s\"\']+)[\\/])', re.I)
PLACEHOLDER_USERS = {'public', 'default', 'someone', 'placeholder', 'test-user', 'example',
                     'user', 'username', '<user>', '<username>'}
TOKEN = re.compile(rb'(?<![A-Za-z0-9])(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{24,})')
PRIVATE_KEY = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----')
PUBLIC_DOC_ROUTES = {'docs/evidence-trace.md': 'snapgene-dna-design/references/evidence-trace.md',
                     'docs/installation.md': 'genome-revival-toolkit/README.md',
                     'docs/validation.md': 'docs/testing.md',
                     'docs/contributing.md': 'docs/developer-guide.md'}
PUBLIC_EXAMPLE = '''"""Reproduce the public synthetic donor workflow with independent local inputs."""
from pathlib import Path
import argparse
import json
import os
import random
import subprocess
import sys
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out-dir', type=Path, required=True)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[1]
out = args.out_dir.resolve()
out.mkdir(parents=True, exist_ok=False)
materials = out / 'materials'
materials.mkdir()
# Fixed seed chooses independent synthetic bases. The desired 640 bp donor
# follows these original-template slices, before any tested tool is called.
rng = random.Random(681120)
target = ''.join(rng.choices('ACGT', k=2000))
cargo = ''.join(rng.choices('ACGT', k=900))
expected = target[600:800] + cargo[200:440] + target[810:1010]
references = {}
for name, sequence in (('target', target), ('cargo', cargo), ('donor', expected)):
    path = materials / (name + '.gb')
    record = SeqRecord(Seq(sequence), id=name,
        description='Program-generated synthetic input; seed 681120; not a laboratory strain',
        annotations={'molecule_type': 'DNA', 'topology': 'linear'})
    with path.open('w', encoding='utf-8') as handle:
        SeqIO.write(record, handle, 'genbank')
    references[name] = {'path': path.name, 'source': 'Independent synthetic construction; seed 681120'}
context = materials / 'context.json'
context.write_text(json.dumps({'references': references}, indent=2), encoding='utf-8')
request = materials / 'request.json'
request.write_text(json.dumps({'original_request': 'Prepare this explicit synthetic donor and check both boundaries.',
    'title': 'Public synthetic donor workflow', 'method': 'integration_donor',
    'target_reference': 'target', 'cargo_reference': 'cargo',
    'target_interval': {'start0': 800, 'end0': 810}, 'cargo_interval': {'start0': 200, 'end0': 440},
    'arm_length': 200, 'preparation_method': 'pcr', 'donor_template_reference': 'donor',
    'donor_interval': {'start0': 0, 'end0': 640}}, indent=2), encoding='utf-8')
config = out / 'trace-settings.json'
config.write_text('{"trace_level":"full"}\\n', encoding='utf-8')
env = dict(os.environ)
env.pop('PYTHONPATH', None)
env['SNAPGENE_TRACE_CONFIG'] = str(config)
cli = repo / 'genome-revival-toolkit/scripts/run_toolkit.py'
results = out / 'results'
def call(arguments):
    returned = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(cli), *arguments],
        cwd=repo, env=env, capture_output=True, encoding='utf-8', errors='replace')
    if returned.returncode:
        # Actual Core/Toolkit outputs retain failure evidence. Do not copy raw
        # local paths from subprocess streams into another public log.
        print(json.dumps({'status': 'FAILED', 'stage': arguments[0], 'returncode': returned.returncode}))
        raise SystemExit(returned.returncode)
    return json.loads(returned.stdout)
result = call(['construct', '--context', str(context), '--request', str(request), '--out-dir', str(results)])
verified = call(['verify', '--out-dir', str(results), '--receipt-sha256', result['receipt_sha256']])
details = json.loads((results / 'result.json').read_text(encoding='utf-8'))
with (Path(details['delivery']['directory']) / 'construct.gb').open(encoding='utf-8') as handle:
    actual = str(SeqIO.read(handle, 'genbank').seq)
if result['status'] != 'delivered' or verified['status'] != 'verified' or actual != expected:
    raise SystemExit('Independent saved-file validation failed')
proof = {'status': 'PASSED_IN_SILICO', 'construction_seed': 681120,
    'expected_length_bp': 640, 'actual_length_bp': len(actual),
    'independent_saved_sequence_equality': True, 'public_receipt_verified': True,
    'toolkit_version': result['toolkit_version'], 'core_version': result['core_version'],
    'wet_experiments': 'NOT_PERFORMED',
    'scope': 'Synthetic engineering regression; not autonomous heldout or experimental validation'}
(out / 'DEMO-VALIDATION.json').write_text(json.dumps(proof, indent=2) + '\\n', encoding='utf-8')
print(json.dumps(proof))
'''


class CandidateError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git(repository, *args, binary=False):
    result = subprocess.run(['git', '--no-optional-locks', *args], cwd=repository,
                            capture_output=True, env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})
    if result.returncode:
        raise CandidateError('Read-only Git operation failed: ' + args[0])
    return result.stdout if binary else result.stdout.decode('utf-8', errors='strict')


def safe_name(name):
    path = PurePosixPath(name)
    if (not name or '\\' in name or path.is_absolute() or PureWindowsPath(name).drive
            or '..' in path.parts or any(part in ('', '.') for part in name.split('/'))):
        raise CandidateError('Unsafe source member rejected')
    return name


def reject_link(path):
    if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
        raise CandidateError('Symbolic link or junction rejected')


def snapshot(repository, source_commit, working_tree):
    reject_link(Path(repository))
    repository = Path(repository).resolve()
    if working_tree:
        if source_commit:
            raise CandidateError('Diagnostic worktree cannot claim a frozen source commit')
        names = git(repository, 'ls-files', '--cached', '--others', '--exclude-standard', '-z').split('\0')
        files = {}
        for name in sorted(set(filter(None, names))):
            safe_name(name)
            path = repository / name
            for parent in [path, *path.parents]:
                if parent == repository:
                    break
                reject_link(parent)
            files[name] = path.read_bytes() if path.is_file() else None
        return files, None, git(repository, 'rev-parse', 'HEAD').strip()
    if not source_commit or not re.fullmatch(r'[a-fA-F0-9]{7,40}', source_commit):
        raise CandidateError('Provide an explicit Git source commit')
    commit = git(repository, 'rev-parse', '--verify', source_commit + '^{commit}').strip()
    files = {}
    with zipfile.ZipFile(io.BytesIO(git(repository, 'archive', '--format=zip', commit, binary=True))) as archive:
        for row in archive.infolist():
            if row.is_dir():
                continue
            name = safe_name(row.filename)
            mode = (row.external_attr >> 16) & 0o170000
            if mode not in (0, 0o100000):
                raise CandidateError('Nonregular Git archive member rejected')
            files[name] = archive.read(row)
    return files, commit, None


def tool_closure(files, tests):
    modules = {PurePosixPath(name).stem: name for name in files
               if name.startswith('tools/') and name.count('/') == 1 and name.endswith('.py')}
    pending = {'tools/run_test_suite.py', 'tools/build_toolkit.py'}
    ci = (files.get('.gitlab-ci.yml') or b'').decode('utf-8')
    pending.update(re.findall(r'tools/[A-Za-z_][A-Za-z0-9_]*\.py', ci))
    scan = list(tests)
    selected = {}
    while scan or pending:
        if pending:
            name = sorted(pending)[0]
            pending.remove(name)
            if name in selected:
                continue
            if name not in files or files[name] is None:
                raise CandidateError('Required CI/test tool is absent: ' + name)
            selected[name] = 'Required by official CI or retained test dependency closure'
        else:
            name = scan.pop()
        text = files[name].decode('utf-8-sig')
        tree = ast.parse(text, filename=name)
        strings = []
        # Docstrings explain behavior; a mention there is not an executable dependency.
        docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                      if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                      and node.body and isinstance(node.body[0], ast.Expr)
                      and isinstance(node.body[0].value, ast.Constant)
                      and isinstance(node.body[0].value.value, str)}
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module == 'tools':
                    names.extend(alias.name for alias in node.names)
                elif node.module:
                    names.append(node.module)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                strings.append(node.value)
        for value in strings:
            names.extend(re.findall(r'\b(?:import|from)\s+((?:tools\.)?[A-Za-z_][A-Za-z0-9_]*)', value))
            names.extend(re.findall(r'([A-Za-z_][A-Za-z0-9_]*)\.py\b', value))
        for module in names:
            stem = module.split('.')[1] if module.startswith('tools.') else module.split('.')[0]
            target = modules.get(stem)
            if target and target not in selected:
                pending.add(target)
    return selected


def exclusion(name, data):
    parts = PurePosixPath(name).parts
    if data is None:
        return 'Missing from diagnostic worktree; no frozen-source claim'
    if any(part in DEVELOPMENT_PARTS for part in parts):
        return 'Development records, generated output or assessment material excluded'
    if PurePosixPath(name).name in {'AGENTS.md', 'CLAUDE.md', 'INSTALL-SOURCE.json',
            'RELEASE-MANIFEST.json', 'DEVELOPMENT-MANIFEST.json', 'TOOLKIT-MANIFEST.json'}:
        return 'Development instructions or stale generated installation/package record excluded'
    if PurePosixPath(name).name.startswith('.env') or PurePosixPath(name).name.lower() in {'auth.json', 'credentials.json', '.netrc'}:
        return 'Potential authentication material excluded'
    suffix = PurePosixPath(name).suffix.lower()
    if suffix in DNA_SUFFIXES:
        if not (name.startswith('snapgene-dna-design/fixtures/synthetic/')
                or name.startswith('snapgene-dna-design/fixtures/rich/')):
            return 'DNA without reviewed program-generated synthetic provenance excluded'
    if suffix in EXCLUDED_SUFFIXES:
        return 'Media, archive, compiled executable or generated log excluded'
    return None


def conventional_private_path(text, match):
    token = re.match(r'[^\s\"\'`)>]*', text[match.start():]).group(0)
    parts = [part.lower() for part in re.split(r'[\\/]+', token) if part]
    user = match.group(1)
    if user:
        user = user.lower()
        if (user in PLACEHOLDER_USERS or re.fullmatch(r'%[a-z_][a-z0-9_]*%', user)
                or re.fullmatch(r'<[^<>/\\]+>', user) or user in {'...', '…'}):
            return True
        # A complete path/to pair can replace the username slot. An actual
        # username followed later by example/path/to never becomes anonymous.
        return user == 'path' and len(parts) > 3 and parts[3] == 'to'
    remainder = parts[2:]
    return (len(parts) > 1 and parts[1].endswith('-example')) or any(
        part in {'example', '...', '…', '<workspace>', '<project>', '<path>'} for part in remainder
    ) or any(remainder[index:index + 2] == ['path', 'to'] for index in range(len(remainder) - 1))


def screen(name, data):
    if TOKEN.search(name.encode('utf-8')):
        raise CandidateError('Potential credential-bearing selected source filename rejected')
    if TOKEN.search(data) or PRIVATE_KEY.search(data):
        raise CandidateError('Potential credential in selected public source: ' + name)
    notes = set()
    if PurePosixPath(name).suffix.lower() in ({'.py', '.md', '.txt', '.json', '.yml', '.yaml', '.html', '.svg', '.js'} | DNA_SUFFIXES):
        text = data.decode('utf-8-sig', errors='replace')
        for match in PRIVATE_PATH.finditer(text):
            if not conventional_private_path(text, match):
                raise CandidateError('Nonplaceholder personal/workspace path in selected source: ' + name)
            notes.add('Conventional invented Windows placeholder retained; no source-file identity exemption')
        if re.search(r'[A-Za-z]:[\\/]+(?:path[\\/]+to|workspace-example|example)[\\/]', text, re.I):
            notes.add('Explicit invented Windows path components retained as portable example/test data')
        if re.search(r'[A-Za-z]:[\\/]+Program Files(?:\s*\(x86\))?[\\/]', text, re.I):
            notes.add('Generic Windows system discovery path retained; not a personal directory')
    return sorted(notes)


def versions(files):
    def version(path):
        value = files[path].decode('utf-8').strip()
        if not re.fullmatch(r'\d+\.\d+\.\d+(?:[A-Za-z0-9.\-]*)?', value):
            raise CandidateError('Missing or invalid software version')
        return value
    trace = ast.parse(files['snapgene-dna-design/evidence_trace/__init__.py'].decode('utf-8'))
    value = next((ast.literal_eval(node.value) for node in trace.body if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == '__version__' for t in node.targets)), None)
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise CandidateError('Missing or invalid Trace version')
    return {'toolkit': version('genome-revival-toolkit/VERSION'),
            'core': version('snapgene-dna-design/VERSION'), 'evidence_trace': value}


def project_links(name, data, selected, files, commit):
    text = data.decode('utf-8')
    changed = []
    def destination(target):
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or target.startswith('#'):
            return target
        relative = posixpath.normpath(posixpath.join(posixpath.dirname(name), parsed.path))
        if name == 'README.md' and relative in PUBLIC_DOC_ROUTES:
            routed = PUBLIC_DOC_ROUTES[relative]
            changed.append('Official public document link routed to the corresponding selected Skill or current source-document owner')
            if routed in selected:
                return routed + (('#' + parsed.fragment) if parsed.fragment else '')
            relative = routed
        if relative in selected or any(item.startswith(relative.rstrip('/') + '/') for item in selected):
            return target
        suffix = ('#' + parsed.fragment) if parsed.fragment else ''
        if relative in files and files[relative] is not None:
            changed.append('Unbundled relative reference projected to exact public source commit')
            return GITHUB_SOURCE + '/blob/' + commit + '/' + quote(relative, safe='/') + suffix
        if any(item.startswith(relative.rstrip('/') + '/') for item in files):
            changed.append('Unbundled relative directory projected to exact public source commit')
            return GITHUB_SOURCE + '/tree/' + commit + '/' + quote(relative, safe='/') + suffix
        changed.append('Unavailable original relative reference kept as labeled nonclickable text; no invented target')
        return None
    def inline(match):
        target = destination(match[2])
        return match[1] + target + match[3] if target else match[1][1:-2] + ' (reference unavailable in this source snapshot)'
    text = re.sub(r'(?<!!)(\[[^\]\n]+\]\()([^\s)]+)(\))', inline, text)
    def reference(match):
        target = destination(match[2])
        return match[1] + target if target else match[1] + 'reference unavailable in this source snapshot'
    text = re.sub(r'(?m)^(\[[^\]\n]+\]:\s*)(\S+)', reference, text)
    return text.encode('utf-8'), sorted(set(changed))


def public_readme(data, values, candidate_branch=None, *, source_files=()):
    text = data.decode('utf-8')
    text = re.sub(r'DNA Design Core \d+\.\d+\.\d+', 'DNA Design Core ' + values['core'], text)
    text = re.sub(r'Evidence Trace \d+\.\d+\.\d+', 'Evidence Trace ' + values['evidence_trace'], text)
    if 'genome-revival-toolkit/revival/crispr.py' in source_files:
        text = text.replace('One Skill contains all three Kits.', 'One Skill contains all four Kits.')
        row = '| CRISPR | Replace or check a supplied guide plasmid | Candidate factors, sequence direction/PAM, supplied-vector self-targeting, conditional selection and a planned inverse-PCR route |\n'
        if '| CRISPR |' not in text:
            text = text.replace('\n\nOne Skill contains', '\n' + row + '\nOne Skill contains')
    if candidate_branch:
        text = re.sub(r'git clone --branch \S+ ', 'git clone --branch ' + candidate_branch + ' ', text)
    elif 'git clone --branch main ' in text:
        text = text.replace('## Install from source\n', '## Install from source\n\n'
            'Public main remains the earlier published snapshot. To install this candidate, '
            'check out its separately reported candidate branch after cloning; these version labels do not update main.\n')
    text = text.replace('## Validation and limits\n', '## Validation and limits\n\n'
        'Toolkit version ' + values['toolkit'] + '. Official GitLab CI for this candidate has not been executed. '
        'GitHub tests, local tests and official file-byte readback must be identified separately; none is GitLab CI.\n\n'
        'Historical validation below belongs to the earlier public source snapshot. '
        'The implementation versions in VERSIONS.json do not transfer those results to this candidate; '
        'candidate test, package and CI results must be recorded separately.\n')
    if all(name in source_files for name in ('examples/generate_evidence_inputs.py','examples/run_evidence_example.py')):
        text = text.replace('## Use your materials\n', '## Reproduce correction reports\n\n'
            'These source-only scripts independently construct synthetic expected sequences, preserve the rejected attempt, '
            'invoke public entries and read actual file bytes to check hash relationships. They are scripted examples, '
            'not autonomous host evaluations or wet experiments. Use a fresh output directory.\n\n'
            '```sh\npython -X utf8 -B examples/generate_evidence_inputs.py --out-dir output/synthetic-corrections\n'
            'python -X utf8 -B examples/run_evidence_example.py --case core-guide --inputs output/synthetic-corrections\n'
            'python -X utf8 -B examples/run_evidence_example.py --case kit-construct --inputs output/synthetic-corrections\n'
            'python -X utf8 -B examples/run_evidence_example.py --case kit-guide --inputs output/synthetic-corrections\n'
            'python -X utf8 -B examples/run_evidence_example.py --case kit-identity --inputs output/synthetic-corrections\n'
            'python -X utf8 -B examples/run_evidence_example.py --case kit-evidence --inputs output/synthetic-corrections\n```\n\n'
            '## Use your materials\n')
    return text.encode('utf-8')


def new_output(value):
    path = Path(value).absolute()
    if path.exists() or path.is_symlink():
        raise CandidateError('Output must be a new directory; previous evidence is retained')
    for parent in path.parents:
        reject_link(parent)
    if not path.parent.is_dir():
        raise CandidateError('Output parent must already exist')
    return path


def object_metrics(repository):
    common = Path(git(repository, 'rev-parse', '--git-common-dir').strip())
    if not common.is_absolute():
        common = Path(repository) / common
    objects = common / 'objects'
    return {'pack_bytes': sum(path.stat().st_size for path in (objects / 'pack').glob('*.pack')),
            'object_storage_bytes': sum(path.stat().st_size for path in objects.rglob('*') if path.is_file())}


def build_candidate(repository, out_dir, *, source_commit=None, working_tree=False, official_base_dir, candidate_branch=None):
    out = new_output(out_dir)
    base = Path(official_base_dir).resolve()
    reject_link(Path(official_base_dir))
    if git(base, 'status', '--porcelain').strip():
        raise CandidateError('Official base clone must be clean')
    base_commit = git(base, 'rev-parse', 'HEAD').strip()
    if candidate_branch:
        if (candidate_branch in {'main', 'master'} or '..' in candidate_branch or '//' in candidate_branch
                or candidate_branch.endswith(('/', '.lock')) or TOKEN.search(candidate_branch.encode('utf-8'))
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,127}', candidate_branch)):
            raise CandidateError('Provide a valid non-main candidate branch name')
    files, commit, baseline = snapshot(repository, source_commit, working_tree)
    values = versions(files)
    tests = [name for name in files if name.startswith('tests/') and name.endswith('.py')
             and name != DEVELOPMENT_TEST and not exclusion(name, files[name])]
    tools = tool_closure(files, tests)
    chosen, omitted = {}, []
    for name, data in sorted(files.items()):
        reason = exclusion(name, data)
        if name == DEVELOPMENT_TEST or name == 'tools/build_official_candidate.py':
            reason = 'Development-only source-selection tool/test; not a software runtime or official CI dependency'
        if not reason:
            if name.startswith(INNER):
                reason = 'Same-commit program source, runtime documentation or licensed dependency'
                if PurePosixPath(name).suffix.lower() in DNA_SUFFIXES:
                    reason = ('Program-generated synthetic regression fixture; construction described in fixtures/README.md '
                              'and tools/build_rich_fixtures.py, without user-material identity')
            elif name.startswith('tests/'):
                reason = 'Retained public regression input/helper/test; no failure-based exclusions'
            elif name in tools:
                reason = tools[name]
            elif name in ROOT_SOURCE:
                reason = ROOT_SOURCE[name]
            else:
                reason = None
            if reason:
                notes = screen(name, data)
                chosen[name] = {'data': data, 'source': 'source:' + name, 'reason': reason,
                                'review_notes': notes}
                continue
            reason = 'Outside reviewed program and minimum CI/license/version source allowlist'
        sensitive_name = (PurePosixPath(name).suffix.lower() in DNA_SUFFIXES
                          or TOKEN.search(name.encode('utf-8'))
                          or PurePosixPath(name).name.startswith('.env')
                          or PurePosixPath(name).name.lower() in {'auth.json', 'credentials.json', '.netrc'})
        source = 'redacted-sensitive-item-' + str(len(omitted) + 1) if sensitive_name else name
        omitted.append({'source': source, 'reason': reason, 'size': len(data) if data is not None else None,
                        'sha256': None, 'note': 'Excluded material content is not hashed or copied'})
    for name in ROOT_SOURCE:
        if name not in chosen:
            raise CandidateError('Required source entry missing: ' + name)
    for name in ['CLAUDE.md', 'README.md', '.gitattributes']:
        reject_link(base / name)
        if not (base / name).is_file():
            raise CandidateError('Official template/public README is absent')
    inherited = ['CLAUDE.md', '.gitattributes']
    for directory in ('.claude', 'LICENSES'):
        reject_link(base / directory)
        if not (base / directory).is_dir():
            raise CandidateError('Required official template/license directory is absent')
        for path in sorted((base / directory).rglob('*')):
            reject_link(path)
            if path.is_file():
                inherited.append(path.relative_to(base).as_posix())
    for name in inherited:
        data = (base / name).read_bytes()
        screen(name, data)
        chosen[name] = {'data': data, 'source': 'official-template:' + name,
                        'reason': 'Inherited unchanged official template/configuration or template license; not development import'}
        if name == '.gitattributes':
            chosen[name]['reason'] = ('Explicit outer exception: inherit official checkout byte-stability policy unchanged; '
                'LF source and declared binary files must retain FILE-LIST bytes even when core.autocrlf=true')
    if any(b'\r\n' in chosen[name]['data'] for name in inherited if name != '.gitattributes'):
        # Existing official blobs may intentionally contain CRLF despite their
        # broad LF policy. Preserve all inherited template/license bytes rather
        # than normalising their source text or exempting their manifest hashes.
        policy = chosen['.gitattributes']
        original = policy['data']
        policy['data'] = original + (b'' if original.endswith(b'\n') else b'\n') + (
            b'\n# Preserve inherited official template and license bytes.\n'
            b'CLAUDE.md -text\n.claude/** -text\nLICENSES/** -text\n')
        policy['source'] = 'projection-of-official-byte-policy:.gitattributes'
        policy['reason'] = ('Explicit outer exception: preserve original official LF/binary rules and append '
            'no-normalisation rules for inherited templates/licenses because their source blobs contain CRLF')
        policy['transformations'] = ['Append byte-preservation rules; inherited template/license payloads remain unchanged']
        policy['original_source_sha256'] = digest(original)
    example = 'examples/run_demo.py'
    reject_link(base / example)
    if not (base / example).is_file():
        raise CandidateError('Reviewed complete public example is absent from official base')
    original_example = (base / example).read_bytes()
    screen(example, original_example)
    chosen[example] = {'data': PUBLIC_EXAMPLE.encode('utf-8'), 'source': 'projection-of-official-reviewed-example:' + example,
                      'reason': 'Explicit outer exception: reproduce the complete 640 bp public synthetic workflow through actual Toolkit CLI and verify; generate independent local templates instead of importing outer DNA',
                      'transformations': ['Replace unbundled material dependencies with documented fixed-seed/slice construction and an independent saved-sequence check'],
                      'original_source_sha256': digest(original_example)}
    for name in ('examples/generate_evidence_inputs.py', 'examples/run_evidence_example.py'):
        if name not in files:
            continue
        data = files[name]
        screen(name, data)
        chosen[name] = {'data': data, 'source': name,
            'reason': 'Explicit outer exception: source-only reproducible synthetic correction examples through public Core/Toolkit entries; no reader questions/answers, user material or generated report artifacts'}
    chosen['README.md'] = {'data': public_readme((base / 'README.md').read_bytes(), values, candidate_branch, source_files=files),
        'source': 'official-public:README.md',
        'reason': 'Official public README projected to selected entry points and current implementation versions; historical evidence retains its scope'}
    for name, row in list(chosen.items()):
        if name.endswith('.md') and name not in inherited:
            row['data'], changes = project_links(name, row['data'], chosen, files, commit or baseline)
            row['transformations'] = changes
            screen(name, row['data'])
    provenance = {'schema_version': 'official-source-selection-v1', 'source_commit': commit,
        'diagnostic_baseline_commit': baseline, 'official_template_commit': base_commit,
        'source_repository': GITHUB_SOURCE, 'candidate_branch': candidate_branch,
        'selection_class': 'working-tree-diagnostic' if working_tree else 'frozen-source-candidate',
        'limits': 'Selection and content screening do not certify material rights, wet experiments, host autonomy or official quota.'}
    generated = {'SOURCE.json': provenance, 'VERSIONS.json': values}
    for name, value in generated.items():
        chosen[name] = {'data': (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'),
                        'source': 'generated:software-version/provenance', 'reason': 'Software version and source/template provenance audit'}
    chosen['VERSION'] = {'data': (values['toolkit'] + '\n').encode('utf-8'),
                         'source': 'generated:Toolkit-version', 'reason': 'Public top-level implementation version'}
    entries = [{'source': row['source'], 'destination': name, 'reason': row['reason'],
                'transformations': row.get('transformations', []), 'sha256': digest(row['data']), 'size': len(row['data']),
                'review_notes': row.get('review_notes', []),
                **({'original_source_sha256': row['original_source_sha256']} if 'original_source_sha256' in row else {})}
               for name, row in sorted(chosen.items())]
    manifest = {'schema_version': 'official-file-selection-v1', 'source_commit': commit,
                'official_template_commit': base_commit, 'versions': values,
                'scope': 'Every selected source-tree file except FILE-LIST.json itself; its hash is in the outside selection receipt.',
                'entries': entries}
    chosen['FILE-LIST.json'] = {'data': (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')}
    tree_bytes = sum(len(row['data']) for row in chosen.values())
    if tree_bytes > LIMIT_BYTES:
        raise CandidateError('Selected source-tree exceeds 50 MB')
    out.mkdir()
    source = out / 'source'
    source.mkdir()
    for name, row in sorted(chosen.items()):
        target = source / safe_name(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.resolve().is_relative_to(source.resolve()):
            raise CandidateError('Output path escaped selected source tree')
        for parent in [target, *target.parents]:
            reject_link(parent)
            if parent == source:
                break
        target.write_bytes(row['data'])
    receipt = {**provenance, 'versions': values, 'selected_files': len(chosen), 'excluded_source_items': len(omitted),
        'source_tree_bytes': tree_bytes, 'source_tree_limit_bytes': LIMIT_BYTES, 'source_tree_within_limit': True,
        'official_base_clone_objects': object_metrics(base), 'candidate_clone_pack_status': 'NOT_MEASURED',
        'official_repository_quota_status': 'UNVERIFIED', 'file_list_sha256': digest(chosen['FILE-LIST.json']['data']),
        'scope': 'Physical source-tree bytes and separately measured base-clone object bytes; neither is official repository quota.'}
    (out / 'EXCLUDED-FILES.json').write_text(json.dumps(omitted, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'selection-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit')
    parser.add_argument('--working-tree', action='store_true')
    parser.add_argument('--official-base-dir', required=True)
    parser.add_argument('--candidate-branch', help='Project the public install command to the authorized non-main branch')
    parser.add_argument('--out-dir', required=True)
    args = parser.parse_args(argv)
    try:
        result = build_candidate(PROJECT_ROOT, args.out_dir, source_commit=args.source_commit,
                                 working_tree=args.working_tree, official_base_dir=args.official_base_dir,
                                 candidate_branch=args.candidate_branch)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (CandidateError, OSError, KeyError, SyntaxError, UnicodeError, zipfile.BadZipFile) as exc:
        # Filesystem exception strings may expose user paths; only emit safe policy messages.
        message = str(exc) if isinstance(exc, CandidateError) else 'Candidate source preparation failed; no publication performed'
        print(json.dumps({'status': 'FAILED', 'message': message}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
