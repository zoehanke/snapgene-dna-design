"""Actual standalone package/CLI checks; source archive and worktree are not equivalent."""
from repository_paths import PROJECT_ROOT
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

sys.path.insert(0, str(PROJECT_ROOT / 'tools'))
from build_toolkit import build_toolkit, _reviewed, PREFIX
from verify_toolkit_kits import verify as verify_all_kits


class GenomeRevivalPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='toolkit-package-regression-')
        cls.root = Path(cls.temp.name)
        cls.repository = cls.root / 'source-repository'
        cls.repository.mkdir()
        for name, vendor in (('genome-revival-toolkit', False), ('snapgene-dna-design', True)):
            original = PROJECT_ROOT / name
            destination = cls.repository / name
            for entry in _reviewed(original, vendor=vendor):
                path = destination / entry['path']
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original / entry['path'], path)
        cls.git('init', '-b', 'codex/package-fixture')
        cls.git('config', 'user.name', 'Local packaging regression')
        cls.git('config', 'user.email', 'packaging@example.invalid')
        cls.git('add', '.')
        cls.git('commit', '-m', 'Freeze actual Toolkit and Core source for independent package verification')
        cls.commit = cls.git('rev-parse', 'HEAD').strip()
        # A valid source snapshot must not consume this later worktree change.
        changed = cls.repository / 'genome-revival-toolkit/revival/evidence.py'
        changed.write_text(changed.read_text(encoding='utf-8') + '\n# UNCOMMITTED_PACKAGE_SENTINEL\n', encoding='utf-8')
        cls.build = build_toolkit(cls.repository, cls.root / 'formal', source_commit=cls.commit)
        cls.unpacked = cls.root / 'unpacked'
        with zipfile.ZipFile(cls.build['archive']) as archive:
            if archive.testzip() is not None:
                raise AssertionError('Actual standalone ZIP CRC failed')
            archive.extractall(cls.unpacked)
        cls.skill = cls.unpacked / 'genome-revival-toolkit'

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def git(cls, *args):
        return subprocess.run(['git', '-C', str(cls.repository), *args], check=True,
                              capture_output=True, encoding='utf-8', errors='replace').stdout

    def test_manifest_single_entry_and_payload_identity_from_exact_archive(self):
        manifest = json.loads((self.skill / 'TOOLKIT-MANIFEST.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['source_commit'], self.commit)
        self.assertEqual(manifest['package_class'], 'frozen-source-candidate')
        self.assertTrue(manifest['git_archive'])
        with zipfile.ZipFile(self.build['archive']) as archive:
            # One installed root, with manifest-defined sub-Skills underneath.
            # A basename-only count incorrectly classified a nested Kit as a
            # second installation after the explicit Kit/sub-Skill contract.
            skill_entries=[name for name in archive.namelist() if Path(name).name.lower()=='skill.md']
            self.assertEqual(skill_entries.count(PREFIX+'SKILL.md'),1)
            for name in skill_entries:
                if name==PREFIX+'SKILL.md':continue
                relative=Path(name.removeprefix(PREFIX))
                self.assertEqual(relative.parts[0],'kits')
                self.assertEqual(len(relative.parts),3)
                self.assertIn(PREFIX+str(relative.parent/'kit.json').replace('\\','/'),archive.namelist())
            self.assertFalse(any('/agents/' in name or '/fixtures/' in name for name in archive.namelist()))
            self.assertFalse(any(Path(name).suffix.lower() in ('.dna', '.gb', '.fasta', '.fa') for name in archive.namelist()))
            for entry in manifest['entries']:
                self.assertEqual(hashlib.sha256(archive.read(PREFIX + entry['path'])).hexdigest().upper(), entry['sha256'])
        self.assertNotIn('UNCOMMITTED_PACKAGE_SENTINEL', (self.skill / 'revival/evidence.py').read_text(encoding='utf-8'))
        sidecar = json.loads(Path(self.build['manifest']).read_text(encoding='utf-8'))
        self.assertEqual(manifest, sidecar)

    def test_working_tree_package_is_explicitly_diagnostic(self):
        diagnostic = build_toolkit(self.repository, self.root / 'diagnostic', working_tree=True)
        self.assertIsNone(diagnostic['source_commit'])
        self.assertEqual(diagnostic['package_class'], 'working-tree-diagnostic')
        self.assertIn('-working-tree.zip', diagnostic['archive'])
        with zipfile.ZipFile(diagnostic['archive']) as archive:
            self.assertIn(b'UNCOMMITTED_PACKAGE_SENTINEL', archive.read(PREFIX + 'revival/evidence.py'))

    def test_all_four_kits_run_from_one_independent_installation(self):
        receipt = verify_all_kits(self.build['archive'], self.root / 'all-kits-installed',
                                 source_commit=self.commit, repository=self.repository)
        self.assertEqual(receipt['status'], 'PASSED')
        self.assertEqual(len(receipt['kits']), 4)
        for row in receipt['kits']:
            self.assertEqual(row['independent_oracle'], 'PASSED')
            self.assertEqual(row['receipt'], 'verified')
            self.assertEqual(row['trace'], 'complete')
            self.assertEqual(row['report_language'], 'en')
        self.assertEqual(receipt['source_verification']['status'], 'VERIFIED')

    def test_valid_payload_hash_cannot_replace_missing_source_mapping(self):
        altered = self.root / 'unmapped-source.zip'
        with zipfile.ZipFile(self.build['archive']) as original, zipfile.ZipFile(altered, 'w') as destination:
            for name in original.namelist():
                data = original.read(name)
                if name == PREFIX + 'TOOLKIT-MANIFEST.json':
                    manifest = json.loads(data)
                    manifest['entries'][0]['source_path'] = 'unregistered-source'
                    data = json.dumps(manifest).encode('utf-8')
                destination.writestr(name, data)
        with self.assertRaisesRegex(ValueError, 'no committed source mapping'):
            verify_all_kits(altered, self.root / 'rejected-unmapped-source',
                            source_commit=self.commit, repository=self.repository)

    def test_unlisted_archive_file_is_rejected_before_kit_execution(self):
        altered = self.root / 'extra-member.zip'
        with zipfile.ZipFile(self.build['archive']) as original, zipfile.ZipFile(altered, 'w') as destination:
            for name in original.namelist():
                destination.writestr(name, original.read(name))
            destination.writestr(PREFIX + 'kits/unlisted/README.md', 'Unregistered synthetic test file')
        with self.assertRaisesRegex(ValueError, 'Archive membership'):
            verify_all_kits(altered, self.root / 'rejected-extra-member',
                            source_commit=self.commit, repository=self.repository)

    def test_standalone_cli_uses_vendor_and_completes_actual_pcr_donor(self):
        environment = dict(os.environ)
        environment.pop('PYTHONPATH', None)
        environment['SNAPGENE_TRACE_CONFIG'] = str(self.root / 'isolated-trace-settings.json')
        Path(environment['SNAPGENE_TRACE_CONFIG']).write_text('{"trace_level":"off"}\n', encoding='utf-8')
        imported = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c',
            'import sys,json;sys.path.insert(0,sys.argv[1]);from revival.bootstrap import CORE_ROOT,CORE_VERSION;import evidence_trace;'
            'print(json.dumps({"core_root":str(CORE_ROOT),"core_version":CORE_VERSION,"trace_version":evidence_trace.__version__}))', str(self.skill)],
            cwd=self.root, env=environment, check=True, capture_output=True, encoding='utf-8', errors='replace')
        actual_import = json.loads(imported.stdout)
        self.assertEqual(Path(actual_import['core_root']).resolve(), (self.skill / 'vendor/dna-design-core').resolve())
        manifest = json.loads((self.skill / 'TOOLKIT-MANIFEST.json').read_text(encoding='utf-8'))
        self.assertEqual(actual_import['core_version'], manifest['core_version'])
        self.assertEqual(actual_import['trace_version'], manifest['trace_version'])
        materials = self.root / 'independent-materials'
        materials.mkdir()
        rng = random.Random(681120)
        reference = ''.join(rng.choices('ACGT', k=2000))
        cargo = ''.join(rng.choices('ACGT', k=900))
        expected = reference[600:800] + cargo[200:440] + reference[810:1010]
        references = {}
        for name, sequence in (('target', reference), ('cargo', cargo), ('donor', expected)):
            path = materials / (name + '.gb')
            record = SeqRecord(Seq(sequence), id=name, annotations={'molecule_type': 'DNA', 'topology': 'linear'})
            with path.open('w', encoding='utf-8') as handle:
                SeqIO.write(record, handle, 'genbank')
            references[name] = {'path': str(path), 'source': 'independent synthetic input, not a packaged fixture'}
        context_path = materials / 'context.json'
        context_path.write_text(json.dumps({'references': references}), encoding='utf-8')
        request_path = materials / 'request.json'
        request = {'method': 'integration_donor', 'original_request': 'Prepare and check this donor from the actual supplied templates.',
                   'target_reference': 'target', 'cargo_reference': 'cargo',
                   'target_interval': {'start0': 800, 'end0': 810}, 'cargo_interval': {'start0': 200, 'end0': 440},
                   'arm_length': 200, 'preparation_method': 'pcr', 'donor_template_reference': 'donor',
                   'donor_interval': {'start0': 0, 'end0': 640}}
        request_path.write_text(json.dumps(request), encoding='utf-8')
        output = self.root / 'actual-cli-output'
        completed = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(self.skill / 'scripts/run_toolkit.py'),
            'construct', '--context', str(context_path), '--request', str(request_path), '--out-dir', str(output)],
            cwd=self.root, env=environment, capture_output=True, encoding='utf-8', errors='replace', timeout=180)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        result = json.loads((output / 'result.json').read_text(encoding='utf-8'))
        self.assertEqual(result['status'], 'delivered', result)
        actual = Path(result['delivery']['directory'])
        with (actual / 'construct.gb').open(encoding='utf-8') as handle:
            record = SeqIO.read(handle, 'genbank')
        self.assertEqual(str(record.seq), expected)
        self.assertEqual(result['delivery_receipt']['status'], 'verified')
        for scope in ('sequence_model', 'preparation_model', 'file', 'user_goal'):
            self.assertEqual(result['delivery']['validation']['scope_results'][scope]['status'], 'PASSED')
        self.assertTrue((output / 'summary.md').is_file())


if __name__ == '__main__':
    unittest.main()
