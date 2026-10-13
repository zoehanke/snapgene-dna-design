"""Independent record arithmetic and scientific-scope checks for Evidence Kit."""
from repository_paths import PROJECT_ROOT
import csv
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

sys.path.insert(0, str(PROJECT_ROOT / 'genome-revival-toolkit'))
from revival.context import ProjectContext
from revival.evidence import run_evidence


class RevivalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        record = SeqRecord(Seq('ACTG'*20), id='provided_locus.2',
                           annotations={'molecule_type': 'DNA', 'topology': 'linear'})
        path = self.root/'区域.gb'
        with path.open('w', encoding='utf-8') as handle:
            SeqIO.write(record, handle, 'genbank')
        self.context = ProjectContext({'references': {'locus': {'path': str(path),
                    'declared_version': 'provided_locus.2', 'region': {'start0': 4, 'end0': 60}}}}, self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def run_case(self, request):
        return run_evidence(request, self.context, self.root/'result')

    def test_pooled_colony_yield_and_difference_have_independent_arithmetic(self):
        request = {'observations': [
            {'id': 'e1', 'group': 'experiment', 'colonies': 20, 'plated_cells': 1000},
            {'id': 'e2', 'group': 'experiment', 'colonies': 10, 'plated_cells': 500},
            {'id': 'c1', 'group': 'control', 'colonies': 4, 'plated_cells': 2000},
            {'id': 'c2', 'group': 'control', 'colonies': 2, 'plated_cells': 1000}],
            'comparisons': [{'experiment_group': 'experiment', 'control_group': 'control'}]}
        result = self.run_case(request)
        groups = {g['group']: g for g in result['groups']}
        self.assertEqual(groups['experiment']['colonies'], 30)
        self.assertEqual(groups['experiment']['plated_cells'], 1500)
        self.assertAlmostEqual(groups['experiment']['colony_yield_per_reported_cell'], 0.02)
        self.assertAlmostEqual(groups['control']['colony_yield_per_reported_cell'], 0.002)
        self.assertAlmostEqual(result['comparisons'][0]['normalised_difference'], 0.018)
        self.assertEqual(result['conclusions'][0]['status'], 'INSUFFICIENT')
        self.assertIn('not independently measured', groups['experiment']['records'][0]['observation_origin'])

    def test_missing_count_or_denominator_does_not_become_zero(self):
        result = self.run_case({'observations': [
            {'id': 'a', 'group': 'partial', 'colonies': 7, 'plated_cells': 100},
            {'id': 'b', 'group': 'partial', 'colonies': None, 'plated_cells': 200},
            {'id': 'c', 'group': 'other', 'colonies': 3}],
            'comparisons': [{'experiment_group': 'partial', 'control_group': 'other'}]})
        groups = {g['group']: g for g in result['groups']}
        self.assertIsNone(groups['partial']['colonies'])
        self.assertEqual(groups['partial']['plated_cells'], 300)
        self.assertIsNone(groups['partial']['colony_yield_per_reported_cell'])
        self.assertIsNone(groups['other']['plated_cells'])
        self.assertIsNone(result['comparisons'][0]['normalised_difference'])
        self.assertEqual(groups['partial']['records'][0]['colonies'], 7)

    def test_zero_colonies_do_not_support_growth_or_prove_death(self):
        result = self.run_case({'observations': [{'id': 'zero', 'group': 'treated',
                       'colonies': 0, 'plated_cells': 1000, 'role': 'inactivated_donor_control'}]})
        group = result['groups'][0]
        self.assertEqual(group['colonies'], 0)
        self.assertEqual(group['colony_yield_per_reported_cell'], 0)
        self.assertNotEqual(group['growth_assessment'], 'SUPPORTED')
        self.assertIn('not proof', group['growth_statement'])
        self.assertFalse(result['findings'])

    def test_outgrowth_in_inactivated_control_is_preserved_as_counterevidence(self):
        result = self.run_case({'observations': [{'id': 'survivors', 'group': 'treated',
                            'colonies': 2, 'role': 'inactivated_donor_control'}]})
        self.assertEqual(result['findings'][0]['status'], 'CONTRADICTED')
        self.assertEqual(result['findings'][0]['sample_id'], 'survivors')
        self.assertNotEqual(result['conclusions'][0]['status'], 'SUPPORTED')

    def test_only_not_tested_genotypes_keep_conclusions_not_tested(self):
        result = self.run_case({'genotype_results': [{'sample_id': 'a', 'reference_id': 'locus',
                                                     'result': 'not_tested'}]})
        self.assertEqual(result['genotype_results'][0]['assessment'], 'NOT_TESTED')
        self.assertTrue(all(c['status'] == 'NOT_TESTED' for c in result['conclusions']))

    def test_negative_local_result_does_not_establish_whole_genome_loss(self):
        result = self.run_case({'genotype_results': [{'sample_id': 'clone', 'reference_id': 'locus',
                                      'result': 'negative', 'control_status': 'passed'}]})
        genotype = result['genotype_results'][0]
        self.assertEqual(genotype['assessment'], 'SUPPORTED')
        self.assertEqual(genotype['reference']['region'], {'start0': 4, 'end0': 60})
        self.assertEqual(result['conclusions'][1]['status'], 'INSUFFICIENT')
        self.assertIn('complete genome', result['conclusions'][1]['reason'])

    def test_unknown_or_failed_controls_prevent_supported_genotypes(self):
        result = self.run_case({'genotype_results': [
            {'sample_id': 'a', 'reference_id': 'locus', 'result': 'positive', 'control_status': 'failed'},
            {'sample_id': 'b', 'reference_id': 'locus', 'result': 'negative'},
            {'sample_id': 'c', 'reference_id': 'locus', 'result': 'indeterminate', 'control_status': 'passed'}]})
        self.assertTrue(all(g['assessment'] == 'INSUFFICIENT' for g in result['genotype_results']))

    def test_conflicting_results_remain_counterevidence(self):
        result = self.run_case({'genotype_results': [
            {'sample_id': 'clone', 'reference_id': 'locus', 'result': 'positive', 'control_status': 'passed'},
            {'sample_id': 'clone', 'reference_id': 'locus', 'result': 'negative', 'control_status': 'passed'}]})
        self.assertEqual(result['findings'][0]['status'], 'CONTRADICTED')
        self.assertEqual(len(result['genotype_results']), 2)

    def test_empty_or_uncounted_records_remain_unmeasured(self):
        empty = self.run_case({})
        self.assertEqual(empty['status'], 'incomplete')
        self.assertEqual(empty['checks'][0]['status'], 'INCOMPLETE')
        self.assertTrue(all(c['status'] == 'NOT_TESTED' for c in empty['conclusions']))
        unknown = self.run_case({'observations': [{'id': 'placeholder', 'group': 'no-data'}]})
        self.assertIsNone(unknown['groups'][0]['colonies'])
        self.assertEqual(unknown['groups'][0]['growth_assessment'], 'NOT_TESTED')

    def test_malformed_records_counts_and_duplicate_ids_reject(self):
        for colonies in (-1, 2.5, True, 'NaN', 'not a count'):
            with self.subTest(colonies=colonies):
                with self.assertRaises(ValueError):
                    self.run_case({'observations': [{'id': 'a', 'group': 'x', 'colonies': colonies}]})
        with self.assertRaises(ValueError):
            self.run_case({'observations': [{'id': 'same', 'group': 'a'}, {'id': 'same', 'group': 'b'}]})
        with self.assertRaises(ValueError):
            self.run_case({'genotype_results': [{'sample_id': 'a', 'reference_id': 'missing', 'result': 'positive'}]})

    def test_csv_current_source_counts_and_hash_are_reread(self):
        path = self.root/'原始记录.csv'
        path.write_text('id,group,colonies,plated_cells,role\nsource,control,4,100,inactivated_donor_control\n', encoding='utf-8-sig')
        request = {'observations_file': path.name}
        first = self.run_case(request)
        self.assertEqual(first['groups'][0]['colonies'], 4)
        self.assertEqual(first['input_files'][0]['sha256'].lower(), hashlib.sha256(path.read_bytes()).hexdigest())
        path.write_text('id,group,colonies,plated_cells,role\nsource,control,6,100,inactivated_donor_control\n', encoding='utf-8-sig')
        second = self.run_case(request)
        self.assertEqual(second['groups'][0]['colonies'], 6)
        self.assertNotEqual(first['input_files'][0]['sha256'], second['input_files'][0]['sha256'])

    def test_changed_reference_cannot_reuse_previous_genotype_binding(self):
        request = {'genotype_results': [{'sample_id': 'a', 'reference_id': 'locus',
                                        'result': 'negative', 'control_status': 'passed'}]}
        self.run_case(request)
        path = Path(self.context.references['locus']['path'])
        path.write_text(path.read_text(encoding='utf-8')+'\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed during'):
            self.run_case(request)


if __name__ == '__main__':
    unittest.main()
