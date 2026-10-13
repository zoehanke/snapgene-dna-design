"""Independent source-selection fixtures; no user DNA or official publication."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from repository_paths import PROJECT_ROOT
sys.path.insert(0, str(PROJECT_ROOT / 'tools'))
from build_official_candidate import build_candidate, CandidateError, safe_name


def command(directory, *args, input=None):
    result = subprocess.run(['git', *args], cwd=directory, input=input,
                            capture_output=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise AssertionError('Synthetic fixture Git operation failed: ' + args[0])
    return result.stdout.strip()


def write(directory, name, value):
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else value.encode('utf-8'))


def initialize(directory):
    directory.mkdir()
    command(directory, 'init', '-b', 'codex/synthetic-selection')
    command(directory, 'config', 'user.name', 'Synthetic selection fixture')
    command(directory, 'config', 'user.email', 'fixture@example.invalid')
    command(directory, 'config', 'core.autocrlf', 'false')


def commit(directory):
    command(directory, 'add', '.')
    command(directory, 'commit', '-m', 'Freeze independently constructed source-selection input')
    return command(directory, 'rev-parse', 'HEAD')


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory(prefix='source-selection-fixture-') as temporary:
        root = Path(temporary)
        repo = root / 'development'
        base = root / 'official'
        initialize(repo)
        initialize(base)
        files = {
            'LICENSE': 'Synthetic project license notice\n',
            'THIRD_PARTY_NOTICE.md': 'Synthetic attribution notice\n',
            '.gitlab-ci.yml': 'test:\n  script: python tools/run_test_suite.py\n',
            'snapgene-dna-design/VERSION': '1.2.3\n',
            'snapgene-dna-design/evidence_trace/__init__.py': '__version__ = "0.4.5"\n',
            'snapgene-dna-design/README.md': '[Contract](../specs/core.md)\n',
            'snapgene-dna-design/core/example.py': 'VALUE = 17\n',
            'snapgene-dna-design/fixtures/synthetic/fixture.gb': 'Independently constructed synthetic stand-in\n',
            'genome-revival-toolkit/VERSION': '0.6.7\n',
            'genome-revival-toolkit/README.md': 'Public Toolkit usage\n',
            'tests/test_public.py': 'from tools.required_check import check\n',
            'tools/run_test_suite.py': 'from project_paths import ROOT\n',
            'tools/build_toolkit.py': 'from build_release import build\n',
            'tools/build_release.py': 'from check_redistributable import check\n',
            'tools/check_redistributable.py': 'def check(): return True\n',
            'tools/project_paths.py': 'ROOT = None\n',
            'tools/required_check.py': '"""Mentioning unused_tool.py is not a dependency."""\ndef check(): return True\n',
            'tools/unused_tool.py': 'raise RuntimeError("not a runtime dependency")\n',
            'tools/build_official_candidate.py': 'Development selector stand-in\n',
            'tests/test_official_candidate_selection.py': 'Development selector test stand-in\n',
            'specs/core.md': 'Development contract\n',
            'docs/development-plans/plan.md': 'Development plan\n',
            'docs/archive/old.md': 'Historical development record\n',
            'docs/question-bank/answer.md': 'Published answer excluded from software source\n',
            'results/run.json': '{}\n',
            'AGENTS.md': 'Development rules\n',
            'CLAUDE.md': 'Development instructions, not the official template\n',
            'tests/data/unreviewed.gb': 'Opaque nonpublished material stand-in\n',
            'snapgene-dna-design/dist/stale.txt': 'Generated release output\n',
        }
        for name, value in files.items():
            write(repo, name, value)
        official = {'CLAUDE.md': b'Official template instructions\r\n',
                    '.claude/RESPONSIBLE_AI_USE.md': b'Official responsible-use template\r\n',
                    'LICENSES/TEMPLATE.txt': b'Official template licensing\r\n',
                    'README.md': ('# Official public source\n\n'
                                  'DNA Design Core 0.1.0 and Evidence Trace 0.2.0.\n\n'
                                  '## Install from source\n\ngit clone --branch main https://example.invalid/repo.git\n\n'
                                  '## Run a complete example\n\n'
                                  'python examples/run_demo.py --out-dir output/demo\n\n'
                                  '## Validation and limits\n\nOriginal public validation.\n'),
                    'examples/run_demo.py': 'print("independently constructed complete example stand-in")\n',
                    'examples/unused.py': 'print("not selected")\n'}
        for name, value in official.items():
            write(base, name, value)
        frozen = commit(repo)
        commit(base)
        yield root, repo, base, frozen, files, official


class OfficialCandidateSelectionTests(unittest.TestCase):
    def test_exact_commit_tools_closure_template_example_and_manifest(self):
        with fixture() as (root, repo, base, frozen, files, official):
            write(repo, 'snapgene-dna-design/core/uncommitted.py', 'NOT_FROZEN = True\n')
            out = root / 'candidate'
            receipt = build_candidate(repo, out, source_commit=frozen, official_base_dir=base)
            selected = out / 'source'
            self.assertFalse((selected / 'snapgene-dna-design/core/uncommitted.py').exists())
            self.assertFalse((selected / 'tools/unused_tool.py').exists())
            self.assertFalse((selected / 'tools/build_official_candidate.py').exists())
            self.assertFalse((selected / 'tests/test_official_candidate_selection.py').exists())
            self.assertTrue((selected / 'tools/required_check.py').is_file())
            self.assertTrue((selected / 'tests/test_public.py').is_file())
            self.assertFalse((selected / 'docs').exists())
            self.assertFalse((selected / 'specs').exists())
            self.assertFalse((selected / 'AGENTS.md').exists())
            for name in ('CLAUDE.md', '.claude/RESPONSIBLE_AI_USE.md', 'LICENSES/TEMPLATE.txt'):
                expected = official[name] if isinstance(official[name], bytes) else official[name].encode('utf-8')
                self.assertEqual((selected / name).read_bytes(), expected)
            self.assertFalse((selected / 'examples/unused.py').exists())
            example = (selected / 'examples/run_demo.py').read_text(encoding='utf-8')
            self.assertIn("materials = out / 'materials'", example)
            self.assertIn('target[600:800] + cargo[200:440] + target[810:1010]', example)
            self.assertIn("actual != expected", example)
            self.assertIn("call(['verify'", example)
            manifest = json.loads((selected / 'FILE-LIST.json').read_text(encoding='utf-8'))
            by_name = {row['destination']: row for row in manifest['entries']}
            self.assertEqual(by_name['snapgene-dna-design/core/example.py']['sha256'],
                             hashlib.sha256(files['snapgene-dna-design/core/example.py'].encode('utf-8')).hexdigest())
            self.assertIn('Explicit outer exception', by_name['examples/run_demo.py']['reason'])
            self.assertIn('official-template:', by_name['CLAUDE.md']['source'])
            link = (selected / 'snapgene-dna-design/README.md').read_text(encoding='utf-8')
            self.assertIn('/blob/' + frozen + '/specs/core.md', link)
            self.assertEqual(receipt['source_commit'], frozen)
            self.assertEqual(receipt['source_tree_bytes'], sum(path.stat().st_size for path in selected.rglob('*') if path.is_file()))
            self.assertEqual(receipt['official_repository_quota_status'], 'UNVERIFIED')
            excluded = (out / 'EXCLUDED-FILES.json').read_text(encoding='utf-8')
            self.assertNotIn('unreviewed.gb', excluded)
            self.assertNotIn(files['tests/data/unreviewed.gb'].strip(), excluded)
            readme = (selected / 'README.md').read_text(encoding='utf-8')
            self.assertIn('examples/run_demo.py', readme)
            self.assertIn('historical', readme.lower())

    def test_diagnostic_worktree_has_no_frozen_claim_and_cannot_mix_flags(self):
        with fixture() as (root, repo, base, frozen, _, _):
            write(repo, 'snapgene-dna-design/core/diagnostic.py', 'VALUE = 19\n')
            receipt = build_candidate(repo, root / 'diagnostic', working_tree=True, official_base_dir=base)
            self.assertIsNone(receipt['source_commit'])
            self.assertEqual(receipt['selection_class'], 'working-tree-diagnostic')
            self.assertTrue((root / 'diagnostic/source/snapgene-dna-design/core/diagnostic.py').is_file())
            with self.assertRaisesRegex(CandidateError, 'cannot claim'):
                build_candidate(repo, root / 'mixed', source_commit=frozen, working_tree=True, official_base_dir=base)
            self.assertFalse((root / 'mixed').exists())

    def test_public_cli_and_retained_example_files_are_inspected(self):
        with fixture() as (root, repo, base, frozen, _, _):
            # The actual CLI module's repository is explicit through its project_paths constant.
            code = ('import sys;sys.path.insert(0,sys.argv[1]);import build_official_candidate as tool;'
                    'from pathlib import Path;tool.PROJECT_ROOT=Path(sys.argv[2]);raise SystemExit(tool.main(sys.argv[3:]))')
            result = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', code, str(PROJECT_ROOT / 'tools'),
                str(repo), '--source-commit', frozen, '--official-base-dir', str(base), '--out-dir', str(root / 'cli')],
                capture_output=True, encoding='utf-8', errors='replace')
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(json.loads(result.stdout)['selection_class'], 'frozen-source-candidate')
            self.assertTrue((root / 'cli/source/examples/run_demo.py').is_file())
            self.assertNotIn(str(root), result.stdout)

    def test_existing_output_dirty_base_and_oversize_fail_before_writing(self):
        with fixture() as (root, repo, base, frozen, _, _):
            existing = root / 'existing'
            existing.mkdir()
            write(existing, 'keep.txt', 'retain original evidence')
            with self.assertRaisesRegex(CandidateError, 'new directory'):
                build_candidate(repo, existing, source_commit=frozen, official_base_dir=base)
            self.assertEqual((existing / 'keep.txt').read_text(), 'retain original evidence')
            with patch('build_official_candidate.LIMIT_BYTES', 1):
                with self.assertRaisesRegex(CandidateError, '50 MB'):
                    build_candidate(repo, root / 'too-large', source_commit=frozen, official_base_dir=base)
            self.assertFalse((root / 'too-large').exists())
            write(base, 'README.md', 'not a clean base anymore')
            with self.assertRaisesRegex(CandidateError, 'clean'):
                build_candidate(repo, root / 'dirty-base', source_commit=frozen, official_base_dir=base)
            self.assertFalse((root / 'dirty-base').exists())

    def test_git_symlink_member_and_unsafe_paths_are_rejected(self):
        with fixture() as (root, repo, base, _, _, _):
            blob = command(repo, 'hash-object', '-w', '--stdin', input='outside-directory')
            command(repo, 'update-index', '--add', '--cacheinfo', '120000,' + blob + ',snapgene-dna-design/link')
            command(repo, 'commit', '-m', 'Construct symbolic-link boundary without filesystem privileges')
            frozen = command(repo, 'rev-parse', 'HEAD')
            with self.assertRaisesRegex(CandidateError, 'Nonregular'):
                build_candidate(repo, root / 'symlink', source_commit=frozen, official_base_dir=base)
            self.assertFalse((root / 'symlink').exists())
        for name in ('../outside', '/absolute', 'Z:/outside', 'folder\\outside'):
            with self.subTest(name=name), self.assertRaises(CandidateError):
                safe_name(name)

    def test_selected_credential_and_missing_complete_example_are_rejected(self):
        with fixture() as (root, repo, base, _, _, _):
            value = 'gh' + 'p_' + 'x' * 40
            write(repo, 'snapgene-dna-design/core/unsafe.py', 'VALUE = ' + repr(value) + '\n')
            frozen = commit(repo)
            with self.assertRaisesRegex(CandidateError, 'credential'):
                build_candidate(repo, root / 'credential', source_commit=frozen, official_base_dir=base)
            self.assertFalse((root / 'credential').exists())
        with fixture() as (root, repo, base, frozen, _, _):
            command(base, 'rm', 'examples/run_demo.py')
            command(base, 'commit', '-m', 'Construct missing reviewed example boundary')
            with self.assertRaisesRegex(CandidateError, 'complete public example'):
                build_candidate(repo, root / 'missing-example', source_commit=frozen, official_base_dir=base)
            self.assertFalse((root / 'missing-example').exists())

    def test_excluded_authentication_name_and_unavailable_link_are_not_published(self):
        with fixture() as (root, repo, base, _, _, _):
            synthetic_token = 'gh' + 'p_' + 'z' * 40
            write(repo, 'private/' + synthetic_token + '.txt', 'Synthetic excluded authentication marker\n')
            write(repo, 'snapgene-dna-design/README.md', '[Unavailable reference](../docs/missing.md)\n')
            frozen = commit(repo)
            out = root / 'redacted'
            build_candidate(repo, out, source_commit=frozen, official_base_dir=base)
            excluded = (out / 'EXCLUDED-FILES.json').read_text(encoding='utf-8')
            self.assertNotIn(synthetic_token, excluded)
            text = (out / 'source/snapgene-dna-design/README.md').read_text(encoding='utf-8')
            self.assertIn('Unavailable reference (reference unavailable', text)
            self.assertNotIn('](', text)

    def test_candidate_install_branch_is_explicit_and_never_main(self):
        with fixture() as (root, repo, base, frozen, _, _):
            branch = 'codex/synthetic-candidate'
            receipt = build_candidate(repo, root / 'branched', source_commit=frozen,
                                      official_base_dir=base, candidate_branch=branch)
            text = (root / 'branched/source/README.md').read_text(encoding='utf-8')
            self.assertIn('git clone --branch ' + branch, text)
            self.assertNotIn('git clone --branch main ', text)
            self.assertEqual(receipt['candidate_branch'], branch)
            with self.assertRaisesRegex(CandidateError, 'non-main'):
                build_candidate(repo, root / 'main', source_commit=frozen,
                                official_base_dir=base, candidate_branch='main')
            self.assertFalse((root / 'main').exists())

    def test_conventional_windows_placeholders_are_kept_but_real_shapes_reject(self):
        accepted = ['C:/Users/example/tool.exe', 'C:/Users/path/to/tool.exe',
                    'C:/Users/.../.../tool.exe', 'C:/Users/<name>/tool.exe',
                    'D:/codex_project/path/to/tool.exe', 'D:/codex_project/.../tool.exe',
                    'D:/workspace-example/tool.exe', 'C:/Program Files/Tool/tool.exe']
        rejected = ['C:/Users/actual-profile/private/tool.exe',
                    'C:/Users/actual-profile/example/tool.exe',
                    'D:/codex_project/private/tool.exe']
        with fixture() as (root, repo, base, _, _, _):
            # Different arbitrary source filenames rule out a file-specific exception.
            for index, value in enumerate(accepted):
                write(repo, 'snapgene-dna-design/core/placeholder_' + str(index) + '.py',
                      'EXAMPLE = ' + repr(value) + '\n')
            frozen = commit(repo)
            out = root / 'placeholders'
            build_candidate(repo, out, source_commit=frozen, official_base_dir=base)
            self.assertEqual((out / 'source/snapgene-dna-design/core/placeholder_0.py').read_text(encoding='utf-8'),
                             'EXAMPLE = ' + repr(accepted[0]) + '\n')
            rows = json.loads((out / 'source/FILE-LIST.json').read_text(encoding='utf-8'))['entries']
            self.assertTrue(next(row for row in rows if row['destination'].endswith('placeholder_0.py'))['review_notes'])
        for index, value in enumerate(rejected):
            with self.subTest(index=index), fixture() as (root, repo, base, _, _, _):
                write(repo, 'snapgene-dna-design/core/arbitrary_boundary.py', 'VALUE = ' + repr(value) + '\n')
                frozen = commit(repo)
                with self.assertRaisesRegex(CandidateError, 'Nonplaceholder'):
                    build_candidate(repo, root / 'private-shape', source_commit=frozen, official_base_dir=base)
                self.assertFalse((root / 'private-shape').exists())


if __name__ == '__main__':
    unittest.main()
