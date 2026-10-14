"""Independent inputs and arithmetic for given-reference Identity, not task answers."""
from repository_paths import PROJECT_ROOT
import copy
import gzip
import hashlib
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

sys.path.insert(0, str(PROJECT_ROOT / 'genome-revival-toolkit'))
from revival.context import ProjectContext
from revival.identity import run_identity
from core.tools.snapgene_io import export_snapgene
from core.tools.primer3_backend import Primer3CoreError


class GenomeRevivalIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_record(self, name, sequence, format='genbank'):
        path = self.root / (name + ('.gb' if format == 'genbank' else '.fasta'))
        record = SeqRecord(Seq(sequence), id=name, annotations={'molecule_type': 'DNA', 'topology': 'linear'})
        with path.open('w', encoding='utf-8') as handle:
            SeqIO.write(record, handle, format)
        return path

    def make_context(self, records, **extra):
        refs = {key: {'path': str(self.write_record(key, seq)), 'source': 'independent synthetic material'}
                for key, seq in records.items()}
        return ProjectContext({'references': refs, **extra}, self.root)

    def assay_fixture(self):
        # Purine-only full oligos cannot form Watson-Crick self or pair duplexes.
        # They still have distinct, uniquely placed 3prime matches in the input.
        forward = 'AGAGGAGAAAGAGGGAAGAGGA'
        reverse = 'AAGGAAGAGAGGAGAGGAGAAG'
        rng = random.Random(271104)
        insert = ''.join(rng.choices('ACGT', k=120))
        prefix = 'TCGTACCGTATCGACTACGT'
        suffix = 'GCATCGTAGCATACGTCGAT'
        a = prefix + forward + insert + str(Seq(reverse).reverse_complement()) + suffix
        b = prefix + forward + insert[:45] + insert[68:] + str(Seq(reverse).reverse_complement()) + suffix
        negative = a[:len(prefix) + len(forward) - 1] + 'C' + a[len(prefix) + len(forward):]
        self.assertEqual(a.count(forward), 1)
        self.assertEqual(negative.count(forward), 0)
        return {'a': a, 'b': b, 'negative': negative}, forward, reverse

    def assay_request(self, forward, reverse, **fields):
        return {'compare_regions': False, 'assays': [dict(id='independent_pair',
                forward=forward, reverse=reverse, **fields)]}

    def test_native_record_id_selects_actual_format_not_text_fasta(self):
        # Core export creates a file fixture. Expected DNA/id remain original input,
        # not a result calculated by ProjectContext or Identity under test.
        sequence = 'ACGTAGCTGACATGCGATCAGTACGATCGACT'
        record = SeqRecord(Seq(sequence), id='native_reference',
                           annotations={'molecule_type': 'DNA', 'topology': 'linear'})
        path = self.root / '材料.dna'
        export_snapgene(record, self.root, filename_base='材料')
        context = ProjectContext({'references': {'x': {'path': str(path), 'record_id': record.id}}})
        actual = context.material('x')
        self.assertEqual(str(actual.seq), sequence)
        self.assertEqual(actual.id, record.id)

    def test_given_regions_show_actual_lengths_not_genome_identity(self):
        records, _, _ = self.assay_fixture()
        ctx = self.make_context({'a': records['a'], 'b': records['b']})
        result = run_identity({'compare_regions': True}, ctx, self.root / 'comparison')
        analysis = result['comparisons'][0]['analysis']
        self.assertEqual(analysis['query_length'], len(records['a']))
        self.assertEqual(analysis['reference_length'], len(records['b']))
        self.assertIn('not unique', result['checked_scope'])
        self.assertIn('Whole-host-genome', ' '.join(result['unverified']))

    def test_current_exact_pcr_and_actual_full_quality(self):
        records, f, r = self.assay_fixture()
        ctx = self.make_context(records)
        result = run_identity(self.assay_request(f, r, size_resolution_bp=20), ctx, self.root)
        assay = result['assays'][0]
        self.assertEqual(assay['quality_status'], 'PASSED', assay['quality'])
        predictions = {p['reference']: p for p in assay['predictions']}
        self.assertEqual(predictions['a']['amplicon_length_bp'], len(f) + 120 + len(r))
        self.assertEqual(predictions['b']['amplicon_length_bp'], len(f) + 97 + len(r))
        self.assertEqual(predictions['negative']['prediction'], 'NO_EXACT_PRODUCT')
        self.assertNotEqual(predictions['a']['template_version'], predictions['b']['template_version'])

    def test_size_resolution_is_an_explicit_condition(self):
        records, f, r = self.assay_fixture()
        ctx = self.make_context({k: records[k] for k in ('a', 'b')})
        small = run_identity(self.assay_request(f, r, size_resolution_bp=20), ctx, self.root)['assays'][0]
        large = run_identity(self.assay_request(f, r, size_resolution_bp=30), ctx, self.root)['assays'][0]
        no_resolution = run_identity(self.assay_request(f, r), ctx, self.root)['assays'][0]
        self.assertEqual(small['discrimination']['status'], 'PREDICTED_DIFFERENT')
        self.assertEqual(large['discrimination']['status'], 'NOT_DISCRIMINATING')
        self.assertEqual(no_resolution['discrimination']['status'], 'NEEDS_REVIEW')
        self.assertEqual(no_resolution['discrimination']['minimum_size_difference_bp'], 23)

    def test_same_band_and_length_do_not_identify_two_backgrounds(self):
        records, f, r = self.assay_fixture()
        ctx = self.make_context({'a': records['a'], 'copy': records['a']})
        result = run_identity(self.assay_request(f, r, size_resolution_bp=1), ctx, self.root)
        self.assertEqual(result['assays'][0]['discrimination']['status'], 'NOT_DISCRIMINATING')

    def test_multiple_forward_sites_remain_ambiguous(self):
        records, f, r = self.assay_fixture()
        duplicated = records['a'][:20] + f + 'TACG' + records['a'][20:]
        ctx = self.make_context({'ambiguous': duplicated, 'a': records['a']})
        result = run_identity(self.assay_request(f, r, size_resolution_bp=1), ctx, self.root)
        by_ref = {p['reference']: p for p in result['assays'][0]['predictions']}
        self.assertEqual(by_ref['ambiguous']['prediction'], 'AMBIGUOUS')
        self.assertEqual(result['assays'][0]['discrimination']['status'], 'UNKNOWN')
        self.assertEqual(result['checks'][0]['status'], 'INCOMPLETE')

    def test_wrong_expectation_is_not_a_successful_check(self):
        records, f, r = self.assay_fixture()
        ctx = self.make_context({'negative': records['negative']})
        result = run_identity(self.assay_request(f, r, expected={'negative': 'AMPLICON'}), ctx, self.root)
        self.assertEqual(result['checks'][0]['status'], 'FAILED')
        self.assertEqual(result['checks'][0]['details']['expected_mismatches'], ['negative'])

    def test_complete_tail_changes_quality_but_pcr_keeps_tail(self):
        records, f, r = self.assay_fixture()
        ctx = self.make_context({'a': records['a']})
        full_forward = 'GCGCGCGCGCGCGCGCGCGCGCGC' + f
        request = self.assay_request(full_forward, r, forward_binding_core_length=len(f))
        result = run_identity(request, ctx, self.root)
        assay = result['assays'][0]
        self.assertEqual(assay['predictions'][0]['amplicon_length_bp'], len(full_forward) + 120 + len(r))
        self.assertIn(assay['quality_status'], ('FAILED', 'INCOMPLETE'))
        self.assertNotEqual(result['status'], 'analysed')

    def test_unavailable_backend_is_incomplete_not_pass(self):
        records, f, r = self.assay_fixture()
        ctx = self.make_context({'a': records['a']})
        with patch('revival.identity.check_complete_oligo_pair',
                   side_effect=Primer3CoreError('independent unavailable backend', 'BACKEND_UNAVAILABLE')):
            result = run_identity(self.assay_request(f, r), ctx, self.root)
        self.assertEqual(result['assays'][0]['quality_status'], 'INCOMPLETE')
        self.assertEqual(result['checks'][0]['status'], 'INCOMPLETE')

    def test_invalid_assay_parameters_are_not_silently_defaulted(self):
        records, f, r = self.assay_fixture()
        ctx = self.make_context({'a': records['a']})
        for changes in ({'size_resolution_bp': 0}, {'size_resolution_bp': True},
                        {'annealing_temperature_C': float('nan')}, {'forward': f+'N'},
                        {'forward': f[:10]}):
            with self.subTest(changes=changes):
                req = self.assay_request(f, r)
                req['assays'][0].update(changes)
                with self.assertRaises(ValueError):
                    run_identity(req, ctx, self.root)

    def test_multirecord_requires_actual_selection_and_duplicate_ids_reject(self):
        path = self.root / 'multiple.fasta'
        path.write_text('>first\nACGTACGTACGTACGT\n>second\nGATTACAGATTACAGATTACA\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'multiple records'):
            ProjectContext({'references': {'x': {'path': str(path)}}}).material('x')
        ctx = ProjectContext({'references': {'x': {'path': str(path), 'record_id': 'second', 'topology': 'linear'}}})
        self.assertEqual(str(ctx.material('x').seq), 'GATTACAGATTACAGATTACA')
        path.write_text('>same\nACGTACGTACGTACGT\n>same\nGATTACAGATTACAGATTACA\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'duplicate record_id'):
            ProjectContext({'references': {'x': {'path': str(path), 'record_id': 'same'}}}).material('x')

    def test_gzip_and_reverse_region_keep_original_identity(self):
        sequence = 'ACGTCAGTACGATCGTAGCACTAGCATGCATGACGT'
        path = self.root / 'reference.fasta.gz'
        with gzip.open(path, 'wt', encoding='utf-8') as h:
            h.write('>ref_original.3\n'+sequence+'\n')
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        ctx = ProjectContext({'references': {'x': {'path': str(path), 'record_id': 'ref_original.3',
                'declared_version': 'ref_original.3', 'sha256': sha, 'topology': 'linear',
                'region': {'start0': 6, 'end0': 29, 'strand': -1}}}})
        self.assertEqual(str(ctx.material('x').seq), str(Seq(sequence[6:29]).reverse_complement()))
        info = ctx.reference_info('x')
        self.assertEqual(info['record_id'], 'ref_original.3')
        self.assertEqual(info['file_sha256'].lower(), sha)
        self.assertEqual(info['declared_version'], 'ref_original.3')
        self.assertNotEqual(info['parent_record_version'], info['record_version'])

    def test_actual_source_change_rejects_old_context(self):
        ctx = self.make_context({'x': 'ACGTACGTACGTACGTACGTACGT'})
        ctx.material('x')
        path = Path(ctx.references['x']['path'])
        path.write_text(path.read_text(encoding='utf-8')+'\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed during'):
            run_identity({'references': ['x']}, ctx, self.root)

    def test_changed_context_file_cannot_anchor_stale_region_data(self):
        path = self.write_record('reference', 'ACGTAGCTGATCGACTAGCATGACTGACGTAG')
        data = {'references': {'x': {'path': str(path), 'region': {'start0': 2, 'end0': 18}}}}
        context_path = self.root/'project-context.json'
        context_path.write_text(json.dumps(data), encoding='utf-8')
        original_sha = hashlib.sha256(context_path.read_bytes()).hexdigest()
        ctx = ProjectContext.load(context_path)
        ctx.material('x')
        data['references']['x']['region'] = {'start0': 7, 'end0': 26}
        context_path.write_text(json.dumps(data), encoding='utf-8')
        try:
            description = ctx.describe()
        except ValueError:
            return  # Explicit rejection and reload is also a valid contract.
        self.assertEqual(description['context_file_sha256'].lower(), original_sha,
                         'An old parsed context must not be given the new file fingerprint.')
        self.assertEqual(description['references'][0]['region'], {'start0': 2, 'end0': 18})

    def test_bad_sha_unknown_strain_and_bounds_remain_explicit_errors(self):
        path = self.write_record('ref', 'ACGT'*20)
        bad_entries = ({'sha256': '0'*64}, {'record_id': 'other'},
                       {'region': {'start0': 0, 'end0': 1000}},
                       {'region': {'start0': True, 'end0': 10}},
                       {'topology': 'circular'})
        for entry in bad_entries:
            with self.subTest(entry=entry):
                with self.assertRaises(ValueError):
                    ProjectContext({'references': {'x': {'path': str(path), **entry}}}).material('x')
        with self.assertRaisesRegex(ValueError, 'strain_id'):
            ProjectContext({'references': {'x': {'path': str(path), 'strain_id': 'undeclared'}}})


if __name__ == '__main__':
    unittest.main()
