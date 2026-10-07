"""Independent regressions for goal parsing and actual presentation boundaries."""
from repository_paths import SKILL_ROOT
import tempfile
import unittest
from pathlib import Path
from Bio import SeqIO
from Bio.Seq import Seq
from core.errors import ValidationError
from core.workflow import run_step
from core.workflow_validation import validate_candidate


class GoalInputTests(unittest.TestCase):
    def setUp(self):
        self.sequence = 'ACGTTGCAACCGTTAAGCGT'
        self.step = run_step('anneal_oligos', {
            'top_oligo': self.sequence,
            'bottom_oligo': str(Seq(self.sequence).reverse_complement()),
        }, step_id='duplex', sources={})
        self.assertIsNone(self.step.error)
        self.product = self.step.result.only_product()

    def test_unknown_goal_fields_cannot_be_silently_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'component.fasta'
            with path.open('w', encoding='utf-8') as handle:
                SeqIO.write(self.product, handle, 'fasta')
            for field in ('requirements', 'requiremnts', 'required_components'):
                with self.subTest(field=field), self.assertRaises(ValidationError):
                    validate_candidate({'topology': 'linear', field: ['missing_marker']},
                        {}, [self.step], self.product, files={'component.fasta': path},
                        result_kind='component')

    def test_executable_missing_component_is_rejected(self):
        report = validate_candidate({
            'topology': 'linear',
            'expected_components': [{'name': 'missing_marker', 'expected_sequence': 'CCCCCCCC'}],
        }, {}, [self.step], self.product, result_kind='component')
        self.assertEqual(report['scope_results']['user_goal']['status'], 'FAILED')
        self.assertIn('REQUIRED_COMPONENT_MISSING', str(report['errors']))

    def test_empty_component_lists_do_not_establish_a_goal(self):
        report = validate_candidate({'expected_components': [], 'forbidden_components': []},
            {}, [self.step], self.product, result_kind='component')
        self.assertEqual(report['scope_results']['user_goal']['status'], 'INCOMPLETE')

    def test_nested_fields_types_and_options_are_checked(self):
        cases = [
            {'expected_components': 'marker'},
            {'expected_components': [{'name': 'marker', 'expected_sequence': self.sequence, 'count': 2}]},
            {'expected_components': [{'name': 'marker', 'expected_sequence': self.sequence, 'sourse_id': 's'}]},
            {'expected_components': [{'name': 'marker', 'strand': True}]},
            {'expected_components': [{'name': 'marker', 'interval_0based': [True, 5]}]},
            {'expected_components': [{'name': 'marker', 'sequence': 'AAAA', 'expected_sequence': 'CCCC'}]},
        ]
        for request in cases:
            with self.subTest(request=request), self.assertRaises(ValidationError):
                validate_candidate(request, {}, [self.step], self.product)
        for scopes in ([], 'sequence_model', ['sequence_model', 'sequence_model'], ['typo']):
            with self.subTest(scopes=scopes), self.assertRaises(ValidationError):
                validate_candidate({'topology': 'linear'}, {}, [self.step], self.product, required_scopes=scopes)

    def test_coverage_is_explicit_and_context_cannot_override_goal(self):
        report = validate_candidate({'topology': 'linear', 'original_request': 'Keep the original intended components'},
            {}, [self.step], self.product, result_kind='component')
        self.assertEqual(report['goal_coverage']['checked_fields'], ['topology'])
        self.assertEqual(report['goal_coverage']['unverified_text_fields'], ['original_request'])
        with self.assertRaises(ValidationError):
            validate_candidate({'topology': 'linear', 'is_cds': True}, {}, [self.step], self.product,
                               sanity_context={'is_cds': False})

    def test_source_selector_and_literal_cannot_describe_different_targets(self):
        from Bio.SeqRecord import SeqRecord
        from Bio.SeqFeature import SeqFeature, FeatureLocation
        from core.runtime_validate import _validate_requested_components
        source = SeqRecord(Seq(self.sequence), annotations={'molecule_type': 'DNA', 'topology': 'linear'})
        source.features = [SeqFeature(FeatureLocation(0, 8, strand=1), type='misc_feature', qualifiers={'label': ['marker']})]
        request = {'expected_components': [{'name': 'marker', 'source_id': 'original', 'expected_sequence': 'CCCCCCCC'}]}
        _, errors = _validate_requested_components(request, source, source_records={'original': source})
        self.assertIn('COMPONENT_DECLARATION_CONFLICT', str(errors))

    def test_original_source_identity_and_interval_are_checked(self):
        from Bio.SeqRecord import SeqRecord
        import json
        source = SeqRecord(Seq(self.sequence), annotations={'molecule_type': 'DNA', 'topology': 'linear'})
        sources = {'original': source}
        step = run_step('anneal_oligos', {'top_oligo': self.sequence,
            'bottom_oligo': str(Seq(self.sequence).reverse_complement())}, sources=sources)
        matching = {'topology': 'linear', 'expected_components': [{'name': 'interval-marker',
            'source_id': 'original', 'interval_0based': [0, 8], 'expected_sequence': self.sequence[:8]}]}
        report = validate_candidate(matching, sources, [step], step.result.only_product())
        self.assertEqual(report['scope_results']['user_goal']['status'], 'PASSED')
        unknown = {'expected_components': [{'name': 'marker', 'source_id': 'unavailable', 'sequence': self.sequence}]}
        report = validate_candidate(unknown, sources, [step], step.result.only_product())
        self.assertIn('COMPONENT_UNRESOLVED', str(report['errors']))
        with tempfile.TemporaryDirectory() as directory:
            wrong = Path(directory) / 'other.gb'
            other = SeqRecord(Seq('CCCCCCCCCCCCCCCCCCCC'), annotations={'molecule_type': 'DNA', 'topology': 'linear'})
            with wrong.open('w', encoding='utf-8') as handle: SeqIO.write(other, handle, 'genbank')
            with self.assertRaisesRegex(ValidationError, 'different original'):
                validate_candidate({'topology': 'linear', 'sources': [{'source_id': 'original', 'path': str(wrong)}]},
                                   sources, [step], step.result.only_product())
            report = validate_candidate({'topology': 'linear', 'sources': [{'source_id': 'missing', 'path': str(wrong)+'-missing'}]},
                                       sources, [step], step.result.only_product())
            self.assertIn('GOAL_SOURCE_UNAVAILABLE', str(report['errors']))


class PresentationTests(unittest.TestCase):
    setUp = GoalInputTests.setUp
    def test_main_links_are_current_and_changed_files_are_rejected(self):
        from core.workflow_delivery import deliver_result
        import core.runtime_gate as gate
        with tempfile.TemporaryDirectory() as directory:
            result = deliver_result({'topology': 'linear'}, {}, [self.step], self.product,
                                    directory, result_kind='component')
            self.assertTrue(result.get('present_files'), 'No directly usable validated presentation list')
            self.assertTrue(callable(getattr(gate, 'verify_delivery_files', None)))
            checked = gate.verify_delivery_files(result['directory'],
                presented_files=result['present_files'], expected_manifest_sha256=result['manifest_sha256'])
            self.assertEqual(checked['status'], 'verified')
            wrong = Path(directory) / 'wrong.gb'
            wrong.write_text('unvalidated alternative', encoding='utf-8')
            with self.assertRaises(ValidationError):
                gate.verify_delivery_files(result['directory'], presented_files=[str(wrong)])
            main = Path(result['present_files'][0]['path'])
            main.write_bytes(main.read_bytes() + b'changed')
            with self.assertRaises(ValidationError):
                gate.verify_delivery_files(result['directory'])

    def test_manifest_and_presentation_descriptors_cannot_change_meaning(self):
        import copy, json
        from core.workflow_delivery import deliver_result
        from core.runtime_gate import verify_delivery_files
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValidationError, 'manifest'):
                verify_delivery_files(directory)
            result = deliver_result({'topology': 'linear'}, {}, [self.step], self.product,
                                    directory, result_kind='component')
            root = Path(result['directory'])
            with self.assertRaisesRegex(ValidationError, 'manifest changed'):
                verify_delivery_files(root, expected_manifest_sha256='0'*64)
            for entries in ([], 'path', [{'description': 'missing path'}]):
                with self.subTest(entries=entries), self.assertRaises(ValidationError):
                    verify_delivery_files(root, presented_files=entries)
            item = copy.deepcopy(result['present_files'][0])
            item['sha256'] = '0'*64
            with self.assertRaisesRegex(ValidationError, 'older file'):
                verify_delivery_files(root, presented_files=[item])
            item = copy.deepcopy(result['present_files'][0])
            item['artifact'] = 'oligo_order_table.tsv'
            with self.assertRaisesRegex(ValidationError, 'declared artifact'):
                verify_delivery_files(root, presented_files=[item])
            manifest = root / 'DELIVERY-MANIFEST.json'
            original = manifest.read_text(encoding='utf-8')
            for malformed in ('{}', '{"files":{}}', '{"files":{"../outside.gb":{"sha256":"0"}}}'):
                manifest.write_text(malformed, encoding='utf-8')
                with self.subTest(malformed=malformed), self.assertRaises(ValidationError):
                    verify_delivery_files(root)
            manifest.write_text(original, encoding='utf-8')
            self.assertEqual(verify_delivery_files(root)['status'], 'verified')


class PreparationQualityTests(unittest.TestCase):
    def test_replay_success_does_not_hide_bad_complete_oligos(self):
        import random
        from Bio.SeqRecord import SeqRecord
        rng = random.Random(8031)
        template = ''.join(rng.choice('ACGT') for _ in range(320))
        source = SeqRecord(Seq(template), id='independent_template',
                           annotations={'molecule_type': 'DNA', 'topology': 'linear'})
        stem = 'GCGTACGCGCGTACGC'
        forward = stem + 'TTTT' + str(Seq(stem).reverse_complement()) + template[100:120]
        reverse = str(Seq(template[220:240]).reverse_complement())
        step = run_step('simulate_pcr', {'template': '$s', 'f_primer': forward, 'r_primer': reverse},
                        sources={'s': source}, step_id='prepared')
        self.assertIsNone(step.error)
        report = validate_candidate({'topology': 'linear'}, {'s': source}, [step],
            step.result.only_product(), required_scopes=['sequence_model', 'preparation_model', 'user_goal'])
        self.assertEqual(report['scope_results']['sequence_model']['status'], 'PASSED')
        self.assertEqual(report['scope_results']['preparation_model']['status'], 'FAILED')
        self.assertIn('OLIGO_QUALITY_FAILED', str(report['errors']))

    def test_quikchange_intentional_duplex_does_not_waive_individual_structure(self):
        from core.tools.primer3_backend import check_complete_oligo_pair
        forward = 'ATGGCTGACGTTACCAAGTTCTAA'
        reverse = str(Seq(forward).reverse_complement())
        with self.assertRaisesRegex(Exception, 'reverse complementary'):
            check_complete_oligo_pair(forward, reverse)
        mutation = check_complete_oligo_pair(forward, reverse, primer_method='quikchange')
        self.assertTrue(mutation['passed'])
        self.assertNotIn('pair', mutation['metrics'])
        self.assertTrue(mutation['excluded_metrics'])
        with self.assertRaisesRegex(Exception, 'complementary'):
            check_complete_oligo_pair(forward, 'AACCGTATGCTAGTCA', primer_method='quikchange')

    def test_unavailable_backend_is_incomplete_not_a_pass(self):
        from unittest.mock import patch
        from core.preparation import check_preparation_quality
        from core.tools.primer3_backend import Primer3CoreError
        product = run_step('anneal_oligos', {'top_oligo': 'ACGTACGT', 'bottom_oligo': 'ACGTACGT'}, sources={}).result.only_product()
        row = {'id': 'ordinary', 'method': 'PCR', 'product': product,
               'primers': [{'sequence': 'ACGTACGTACGTACGTACGT'}, {'sequence': 'TGCATGCATGCATGCATGCA'}]}
        with patch('core.tools.primer3_backend.check_complete_oligo_pair',
                   side_effect=Primer3CoreError('unavailable', 'BACKEND_UNAVAILABLE')):
            result = check_preparation_quality([row])
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertEqual(result['checks'][0]['error_code'], 'BACKEND_UNAVAILABLE')

    def test_unused_preparation_is_retained_but_does_not_change_selected_orders(self):
        import random
        from Bio.SeqRecord import SeqRecord
        from core.workflow_delivery import deliver_result
        rng = random.Random(8031)
        template = ''.join(rng.choice('ACGT') for _ in range(320))
        source = SeqRecord(Seq(template), id='source', annotations={'molecule_type': 'DNA', 'topology': 'linear'})
        sources = {'s': source}
        selected = 'ACGTTGCAACCGTTAAGCGT'
        good = run_step('anneal_oligos', {'top_oligo': selected, 'bottom_oligo': str(Seq(selected).reverse_complement())},
                        sources=sources, step_id='selected')
        stem = 'GCGTACGCGCGTACGC'
        unused = run_step('simulate_pcr', {'template': '$s',
            'f_primer': stem + 'TTTT' + str(Seq(stem).reverse_complement()) + template[100:120],
            'r_primer': str(Seq(template[220:240]).reverse_complement())},
            sources=sources, step_id='unused', previous=[good])
        self.assertIsNone(unused.error)
        with tempfile.TemporaryDirectory() as directory:
            result = deliver_result({'topology': 'linear'}, sources, [good, unused], good.result.only_product(),
                directory, result_kind='component', output_step='selected')
            self.assertEqual(result['validation']['preparation_quality']['status'], 'NOT_APPLICABLE')
            import json
            recorded = json.loads((Path(result['directory']) / 'execution.json').read_text(encoding='utf-8'))
            self.assertEqual(len(recorded), 2)
            orders = (Path(result['directory']) / 'oligo_order_table.tsv').read_text(encoding='utf-8')
            self.assertIn('synthesis', orders)
            self.assertNotIn('preparation', orders)


if __name__ == '__main__':
    unittest.main()
