"""Independent public-entry regression for the omitted-arm defect."""
from repository_paths import SKILL_ROOT
import copy
import random
import tempfile
import unittest
from pathlib import Path
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from core import plan, execute, validate
from core.errors import CoreError


class IntegrationDonorArmDerivationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        rng = random.Random(651992)
        self.reference = ''.join(rng.choices('ACGT', k=1000))
        self.payload = ''.join(rng.choices('ACGT', k=200))
        sources = []
        for name, sequence, role in (('payload', self.payload, 'template'), ('reference', self.reference, 'reference')):
            path = self.root / (name + '.gb')
            record = SeqRecord(Seq(sequence), id=name, annotations={'molecule_type': 'DNA', 'topology': 'linear'})
            with path.open('w', encoding='utf-8') as handle:
                SeqIO.write(record, handle, 'genbank')
            sources.append({'source_id': name, 'path': str(path), 'role': role,
                            'annotation_status': 'reviewed', 'evidence': {'source_evidence_class': 'user-provided'}})
        self.task = {'schema_version': 'construction-task-v1', 'task_id': 'independent_donor',
                     'revision': 1, 'mode': 'formal', 'task_kind': 'integration_donor', 'sources': sources,
                     'target': {'source_id': 'payload', 'selection': {'kind': 'interval', 'interval_0based': [20, 180],
                        'resolution_status': 'resolved', 'resolution_evidence': [{'kind': 'user-interval'}]}},
                     'operation': {'homology_arms': {'arm_length': 100},
                                   'locus': {'source_id': 'reference', 'interval_0based': [450, 460], 'strand': 1}},
                     'product': {'topology': 'linear', 'formats': ['gb', 'dna', 'fasta']},
                     'approvals': {'user_confirmed_task': {'value': True}}, 'host': 'independent test chassis'}

    def tearDown(self):
        self.temp.cleanup()

    def test_length_only_uses_actual_reference_and_recomputes_same_donor(self):
        task, result = plan(self.task)
        expected = self.reference[350:450] + self.payload[20:180] + self.reference[460:560]
        self.assertEqual(result['product_sequence'], expected)
        self.assertEqual(result['steps'][1]['left_arm_length'], 100)
        self.assertEqual(result['steps'][1]['right_arm_length'], 100)
        execution = execute(task, result, self.root / 'output')
        report = validate(task, result, execution)
        self.assertEqual(report['overall'], 'verified', report['errors'])
        self.assertEqual(report['scope_results']['preparation_model']['status'], 'INCOMPLETE')

    def test_negative_strand_derives_biological_left_and_right(self):
        self.task['operation']['locus']['strand'] = -1
        _, result = plan(self.task)
        expected = str(Seq(self.reference[460:560]).reverse_complement()) + self.payload[20:180] + str(Seq(self.reference[350:450]).reverse_complement())
        self.assertEqual(result['product_sequence'], expected)

    def test_missing_one_arm_keeps_explicit_arm_and_derives_other(self):
        self.task['operation']['homology_arms']['left_arm'] = self.reference[400:450]
        _, result = plan(self.task)
        self.assertEqual(result['product_sequence'], self.reference[400:450] + self.payload[20:180] + self.reference[460:560])

    def test_insufficient_reference_flank_is_not_an_empty_arm(self):
        self.task['operation']['locus']['interval_0based'] = [50, 60]
        with self.assertRaises(CoreError) as caught:
            plan(self.task)
        self.assertEqual(caught.exception.error_code, 'INTEGRATION_LOCUS_OUT_OF_RANGE')

    def test_invalid_arm_length_does_not_become_a_planned_donor(self):
        for length in (True, -1, 1.5):
            with self.subTest(length=length):
                task = copy.deepcopy(self.task)
                task['operation']['homology_arms']['arm_length'] = length
                with self.assertRaises(CoreError):
                    plan(task)

    def test_strict_preparation_still_rejects_a_sequence_model(self):
        self.task['validation_requirements'] = ['sequence_model', 'preparation_model', 'file', 'user_goal']
        task, result = plan(self.task)
        execution = execute(task, result, self.root / 'strict')
        checked = validate(task, result, execution)
        self.assertEqual(checked['overall'], 'failed')
        self.assertEqual(checked['scope_results']['preparation_model']['status'], 'INCOMPLETE')


if __name__ == '__main__':
    unittest.main()
