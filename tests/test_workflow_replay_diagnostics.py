"""Public history continuation: altered facts fail; diagnostics reveal no values."""
from repository_paths import SKILL_ROOT
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord


class WorkflowReplayDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='replay-诊断-')
        cls.root = Path(cls.temporary.name)
        # A literal synthetic source; expected reverse complement is independent.
        cls.sequence = 'AGTC' * 17 + 'GAA'
        source = cls.root / 'source.gb'
        with source.open('w', encoding='utf-8') as handle:
            SeqIO.write(SeqRecord(Seq(cls.sequence), id='constructed-source',
                annotations={'molecule_type': 'DNA', 'topology': 'linear'}), handle, 'genbank')
        config = {'method': 'reverse_complement', 'step_id': 'initial',
                  'params': {'seq': '$source'}, 'sources': {'source': str(source)}}
        process, payload, out = cls.call(config, 'original')
        if process.returncode:
            raise AssertionError(process.stdout + process.stderr)
        cls.record = json.loads((out / 'steps.json').read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    @classmethod
    def call(cls, config, name):
        path = cls.root / (name + '.json')
        path.write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
        out = cls.root / name
        process = subprocess.run([sys.executable, '-X', 'utf8', '-B',
            str(SKILL_ROOT / 'scripts/run_step.py'), '--input', str(path), '--out-dir', str(out)],
            capture_output=True, text=True, encoding='utf-8', timeout=90)
        return process, json.loads(process.stdout), out

    def continuation(self):
        return {'method': 'reverse_complement', 'step_id': 'continued',
                'params': {'seq': '$initial.products.0'},
                'sources': copy.deepcopy(self.record['sources']),
                'previous': copy.deepcopy(self.record['steps'])}

    @staticmethod
    def digest(value):
        # Independent public wire-format canonical SHA-256, no Core hash helper.
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
            separators=(',', ':')).encode('utf-8')).hexdigest()

    def check_failure(self, config, name):
        process, payload, out = self.call(config, name)
        self.assertNotEqual(process.returncode, 0)
        error = payload['error']
        self.assertEqual(error['error_code'], 'EXECUTION_RESULT_CHANGED')
        self.assertFalse(error['write_authoritative_artifact'])
        details = error['details']
        self.assertEqual(details['recorded_input_versions'], config['previous'][0]['input_versions'])
        self.assertEqual(details['replayed_input_versions'], self.record['steps'][0]['input_versions'])
        self.assertEqual(details['recorded_result_sha256'], self.digest(config['previous'][0]['result']))
        self.assertEqual(details['replayed_result_sha256'], self.digest(self.record['steps'][0]['result']))
        for field in ('recorded_input_versions', 'replayed_input_versions',
                      'recorded_result_sha256', 'replayed_result_sha256', 'differing_fields'):
            self.assertIn(field, error['message'])
        # Public run_step preserves a failed attempt, never a selectable product.
        saved = json.loads((out / 'steps.json').read_text(encoding='utf-8'))
        self.assertIsNone(saved['steps'][-1]['result'])
        self.assertEqual(saved['steps'][-1]['error']['error_code'], 'EXECUTION_RESULT_CHANGED')
        self.assertIsNone(saved['error'].get('result'))
        self.assertNotIn(self.sequence, json.dumps(error))
        self.assertNotIn(str(Seq(self.sequence).reverse_complement()), json.dumps(error))
        return details

    def test_untouched_history_still_replays_and_roundtrips_exactly(self):
        process, payload, out = self.call(self.continuation(), 'unchanged')
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        record = json.loads((out / 'steps.json').read_text(encoding='utf-8'))
        self.assertEqual(record['steps'][-1]['result']['products'][0]['sequence'], self.sequence)
        self.assertIsNone(payload['error'])

    def test_changed_reaction_record_keeps_its_distinct_rejection_code(self):
        config = self.continuation()
        config['previous'][0]['operations'].append({'method': 'unexecuted-reaction'})
        process, payload, out = self.call(config, 'reaction-mismatch')
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(payload['error']['error_code'], 'REACTION_RECORD_CHANGED')
        self.assertNotIn('recorded_result_sha256', payload['error']['details'])

    def test_changed_input_version_is_rejected_with_both_result_hashes(self):
        config = self.continuation()
        config['previous'][0]['input_versions'][0] = '0' * 64
        details = self.check_failure(config, 'input-mismatch')
        self.assertEqual(details['differing_fields'], ['input_versions[0]'])
        self.assertEqual(details['recorded_result_sha256'], details['replayed_result_sha256'])

    def test_changed_result_is_rejected_without_disclosing_its_value(self):
        config = self.continuation()
        config['previous'][0]['result']['analysis']['untrusted_note'] = self.sequence
        details = self.check_failure(config, 'result-mismatch')
        self.assertEqual(details['differing_fields'], ['result.analysis.untrusted_note'])
        self.assertNotEqual(details['recorded_result_sha256'], details['replayed_result_sha256'])

    def test_simultaneous_mismatches_are_both_reported(self):
        config = self.continuation()
        config['previous'][0]['input_versions'].append('0' * 64)
        config['previous'][0]['result']['checks'].append({'status': 'PASSED'})
        details = self.check_failure(config, 'both-mismatch')
        self.assertEqual(details['differing_fields'], ['input_versions.length', 'result.checks.length'])

    def test_malformed_version_and_dna_dictionary_key_are_not_disclosed(self):
        for index,version in enumerate((self.sequence,'C'*64)):
            with self.subTest(kind=index):
                config = self.continuation()
                config['previous'][0]['input_versions'][0] = version
                config['previous'][0]['result']['analysis'][self.sequence] = self.sequence
                process, payload, out = self.call(config, f'redacted-mismatch-{index}')
                self.assertNotEqual(process.returncode, 0)
                error = payload['error']
                self.assertEqual(error['error_code'], 'EXECUTION_RESULT_CHANGED')
                self.assertNotIn(self.sequence, json.dumps(error))
                self.assertNotIn(version, json.dumps(error))
                self.assertEqual(error['details']['recorded_input_versions'],
                                 [{'invalid_version_sha256': self.digest(version)}])
                self.assertIn('result.analysis.[redacted-field]', error['details']['differing_fields'])

    def test_many_differences_are_bounded_without_changing_rejection(self):
        config = self.continuation()
        config['previous'][0]['result']['analysis'].update({f'field_{i:02d}': i for i in range(40)})
        details = self.check_failure(config, 'bounded-mismatch')
        self.assertEqual(len(details['differing_fields']), 32)
        self.assertTrue(details['differing_fields_truncated'])

    def test_dna_inside_prefixed_field_name_is_not_disclosed(self):
        config = self.continuation()
        config['previous'][0]['result']['analysis']['guide_' + self.sequence] = 1
        details = self.check_failure(config, 'prefixed-dna-key')
        self.assertEqual(details['differing_fields'], ['result.analysis.[redacted-field]'])

    def test_unserializable_record_diagnostics_cannot_replace_original_rejection(self):
        # Original comparison short-circuits on input versions. Computing extra
        # diagnostics must not turn that refusal into a serialization error.
        script = '''
import json, sys
sys.path.insert(0, sys.argv[1])
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from core.models.molecule import as_molecule
from core.workflow import run_step
source = as_molecule(SeqRecord(Seq('AGTCAGAA'), id='constructed',
    annotations={'molecule_type': 'DNA', 'topology': 'linear'}))
first = run_step('reverse_complement', {'seq': '$source'}, step_id='initial', sources={'source': source})
assert first.error is None
first.input_versions = ['0' * 64]
first.result.analysis['opaque'] = object()
continued = run_step('reverse_complement', {'seq': '$source'}, step_id='continued',
    sources={'source': source}, previous=[first])
print(json.dumps(continued.error))
'''
        process = subprocess.run([sys.executable, '-X', 'utf8', '-B', '-c', script, str(SKILL_ROOT)],
            capture_output=True, text=True, encoding='utf-8', timeout=90)
        self.assertEqual(process.returncode, 0, process.stderr)
        error = json.loads(process.stdout)
        self.assertEqual(error['error_code'], 'EXECUTION_RESULT_CHANGED')
        self.assertFalse(error['write_authoritative_artifact'])
        self.assertIsNone(error['details']['recorded_result_sha256'])
        self.assertEqual(len(error['details']['replayed_result_sha256']), 64)
        self.assertEqual(error['details']['diagnostics_unavailable'], 'TypeError')


if __name__ == '__main__':
    unittest.main()
