"""Construct tests use supplied independent records, public Context and current Core."""
from repository_paths import PROJECT_ROOT, SKILL_ROOT
import copy
import random
import sys
import tempfile
import unittest
from pathlib import Path
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import SeqFeature, FeatureLocation
from Bio.SeqRecord import SeqRecord

sys.path.insert(0, str(PROJECT_ROOT / 'genome-revival-toolkit'))
from revival.context import ProjectContext
from revival.construct import run_construct


class GenomeRevivalConstructTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        rng = random.Random(681120)
        self.reference = ''.join(rng.choices('ACGT', k=2000))
        self.cargo = ''.join(rng.choices('ACGT', k=900))
        self.expected = self.reference[600:800] + self.cargo[200:440] + self.reference[810:1010]
        references = {}
        for name, sequence in (('target', self.reference), ('cargo', self.cargo), ('donor', self.expected)):
            record = SeqRecord(Seq(sequence), id=name, annotations={'molecule_type': 'DNA', 'topology': 'linear'})
            if name == 'cargo':
                record.features = [SeqFeature(FeatureLocation(200, 440, strand=1), type='misc_feature',
                                               qualifiers={'label': ['independent_cargo']})]
            path = self.root / (name + '.gb')
            with path.open('w', encoding='utf-8') as handle:
                SeqIO.write(record, handle, 'genbank')
            references[name] = {'path': str(path), 'source': 'independent engineering fixture'}
        self.context = ProjectContext({'references': references}, self.root)
        self.request = {'method': 'integration_donor', 'original_request': 'From supplied templates prepare the specified donor and check its junctions.',
                        'target_reference': 'target', 'cargo_reference': 'cargo',
                        'target_interval': {'start0': 800, 'end0': 810},
                        'cargo_interval': {'start0': 200, 'end0': 440}, 'arm_length': 200,
                        'preparation_method': 'pcr', 'donor_template_reference': 'donor',
                        'donor_interval': {'start0': 0, 'end0': 640}}

    def tearDown(self):
        self.temp.cleanup()

    def test_current_pcr_template_delivers_the_source_bound_donor(self):
        result = run_construct(self.request, self.context, self.root / 'result')
        self.assertEqual(result['status'], 'delivered', result)
        self.assertEqual(result['delivery_receipt']['status'], 'verified')
        scopes = result['delivery']['validation']['scope_results']
        self.assertTrue(all(scopes[scope]['status'] == 'PASSED' for scope in ('sequence_model', 'preparation_model', 'file', 'user_goal')))
        with (Path(result['delivery']['directory']) / 'construct.gb').open(encoding='utf-8') as handle:
            actual = SeqIO.read(handle, 'genbank')
        self.assertEqual(str(actual.seq), self.expected)
        self.assertIn('whole-genome', ' '.join(result['not_checked']).lower())
        self.assertEqual([item['method'] for item in result['observations']],
                         ['prepare_pcr_fragment', 'recipe_cloning_verification', 'recipe_cloning_verification'])

    def test_wrong_current_donor_interval_cannot_use_the_expected_model_as_a_template(self):
        self.request['donor_interval']['start0'] = 1
        result = run_construct(self.request, self.context, self.root / 'wrong')
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['write_authoritative_artifact'])
        self.assertIn('differs', result['error']['message'])

    def test_gibson_structural_failure_keeps_the_original_request_and_does_not_switch_method(self):
        request = {k: v for k, v in self.request.items() if k not in ('donor_template_reference', 'donor_interval')}
        request['preparation_method'] = 'gibson'
        result = run_construct(request, self.context, self.root / 'gibson-negative')
        self.assertEqual(result['status'], 'failed')
        self.assertIn('NO_VALID_GIBSON_PRIMERS', result['error']['message'])
        self.assertEqual([item['method'] for item in result['observations']], ['recipe_gibson_assembly'])
        saved = Path(result['execution_record']).read_text(encoding='utf-8')
        self.assertIn(request['original_request'], saved)

    def test_gibson_uses_three_actual_pcr_products_and_delivers_independent_positive_material(self):
        rng = random.Random(420916)
        raw = {'target': ''.join(rng.choices('ACGT', k=2000)),
               'cargo': ''.join(rng.choices('ACGT', k=1200))}
        references = {}
        for name, sequence in raw.items():
            path = self.root / ('independent-positive-' + name + '.gb')
            record = SeqRecord(Seq(sequence), id=name, annotations={'molecule_type': 'DNA', 'topology': 'linear'})
            with path.open('w', encoding='utf-8') as handle:
                SeqIO.write(record, handle, 'genbank')
            references[name] = {'path': str(path), 'source': 'separate independent synthetic fixture'}
        context = ProjectContext({'references': references}, self.root)
        request = {'method': 'integration_donor', 'original_request': 'Prepare this explicit three-fragment donor and check both boundaries.',
                   'target_reference': 'target', 'cargo_reference': 'cargo', 'preparation_method': 'gibson',
                   'target_interval': {'start0': 900, 'end0': 925},
                   'cargo_interval': {'start0': 225, 'end0': 825}, 'arm_length': 240}
        result = run_construct(request, context, self.root / 'gibson-positive')
        self.assertEqual(result['status'], 'delivered', result)
        expected = raw['target'][660:900] + raw['cargo'][225:825] + raw['target'][925:1165]
        with (Path(result['delivery']['directory']) / 'construct.gb').open(encoding='utf-8') as handle:
            actual = SeqIO.read(handle, 'genbank')
        self.assertEqual(str(actual.seq), expected)
        import json
        records = json.loads(Path(result['execution_record']).read_text(encoding='utf-8'))
        preparation = records['steps'][0]['result']['analysis']['preparation']
        self.assertEqual(len(preparation), 3)
        self.assertTrue(all(row['method'] == 'PCR' and row['primers'] for row in preparation))

    def test_missing_bounds_and_length_remain_input_gaps(self):
        for field in ('target_interval', 'cargo_interval', 'arm_length'):
            with self.subTest(field=field):
                request = copy.deepcopy(self.request)
                request.pop(field)
                with self.assertRaises(ValueError):
                    run_construct(request, self.context, self.root / ('missing-' + field))

    def test_reference_change_is_not_authorized_by_old_context(self):
        self.context.material('target')
        path = Path(self.context.references['target']['path'])
        path.write_text(path.read_text(encoding='utf-8') + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed'):
            run_construct(self.request, self.context, self.root / 'changed')


if __name__ == '__main__':
    unittest.main()
