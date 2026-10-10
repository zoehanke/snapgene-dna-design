"""Public regressions using independent material, not benchmark identities."""
from repository_paths import SKILL_ROOT
import csv
import json
import random
import tempfile
import unittest
from pathlib import Path
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from core.workflow import run_step
from core.workflow_delivery import deliver_result, order_rows
from core.workflow_validation import validate_candidate
from core.errors import ValidationError, GateRejected


def material(topology='circular'):
    rng = random.Random(405)
    return SeqRecord(Seq(''.join(rng.choices('ACGT', k=900))), id='independent',
                     annotations={'molecule_type': 'DNA', 'topology': topology})


class FinalQCDeliveryTests(unittest.TestCase):
    def test_motif_overlap_is_not_enzyme_blockade(self):
        from core.tools import find_restriction_sites
        from core.guardrails.checklist import scan_methylation_blockade
        # NEB: PvuI is dam/dcm-insensitive; BclI is dam-blocked.
        pvu = find_restriction_sites('AAAACGATCGTTTT', enzymes=['PvuI']).analysis['enzymes']['PvuI']['cuts'][0]
        self.assertEqual(pvu['methylation_warnings'], [])
        self.assertTrue(pvu['methylation_overlaps'])
        self.assertFalse(scan_methylation_blockade('AAAACGATCGTTTT', ['PvuI'])['has_methylation_blockade'])
        self.assertTrue(scan_methylation_blockade('AAAATGATCATTTT', ['BclI'])['has_methylation_blockade'])
        bam = find_restriction_sites('AAAAGGATCCTTTT', enzymes=['BamHI']).analysis['enzymes']['BamHI']['cuts'][0]
        self.assertEqual(bam['methylation_warnings'], [])
        unknown = find_restriction_sites('AAAAAGGATCACGTACGTACGTACGTAAAA', enzymes=['AlwI']).analysis['enzymes']['AlwI']['cuts'][0]
        self.assertEqual(unknown['methylation_status'], 'UNKNOWN')
        self.assertTrue(unknown['methylation_unresolved'])
        self.assertFalse(unknown['methylation_warnings'])

    def test_order_rejects_same_identifier_for_different_sequences(self):
        with self.assertRaises(ValidationError):
            order_rows([{'name': 'primer', 'sequence': 'ACGTACGT'},
                        {'name': 'primer', 'sequence': 'TGCATGCA'}])
        self.assertEqual(len(order_rows([{'name': 'primer', 'sequence': 'ACGTACGT'}] * 2)), 1)

    def test_parent_positive_is_recorded_without_a_negative_control_promise(self):
        source = material()
        step = run_step('recipe_cloning_verification', {
            'recombinant_plasmid_seq_or_file': source, 'insert_start_0based': 300,
            'insert_end_0based': 650, 'background_templates': {'parent': source}},
            sources={'input': source}, step_id='assay')
        self.assertEqual(step.status, 'completed', step.error)
        details = step.result.analysis['details']
        row = details['parental_pcr']['templates'][0]
        self.assertEqual(row['status'], 'PRODUCT_PREDICTED')
        self.assertEqual(row['product_lengths_bp'],
                         [details['junction_pcr_primers']['expected_amplicon_size_bp']])
        self.assertFalse(details['parental_pcr']['all_negative'])
        protocol = ' '.join(p['action'] for p in step.result.analysis['protocol_steps'])
        self.assertNotIn('parental-template negative control', protocol)

    def test_extra_sequencing_oligo_is_checked_and_unmatched_is_failed(self):
        source = material()
        step = run_step('recipe_cloning_verification', {
            'recombinant_plasmid_seq_or_file': source, 'insert_start_0based': 300,
            'insert_end_0based': 650,
            'sequencing_primers': [{'name': 'walk', 'sequence': 'A' * 22}],
            'read_length_bp': 120, 'read_trim_bp': 30},
            sources={'input': source}, step_id='assay')
        self.assertEqual(step.status, 'completed', step.error)
        details = step.result.analysis['details']
        self.assertEqual(details['sequencing_checks'][0]['status'], 'FAILED')
        self.assertIn('NO_UNIQUE_BINDING', details['sequencing_checks'][0]['errors'])
        self.assertEqual(details['sequencing_coverage']['read_length_bp'], 120)
        self.assertFalse(details['sequencing_coverage']['experimental_result'])

    def test_current_report_orders_and_qc_share_a_delivery_and_stale_receipt_fails(self):
        # This valid case is an annotation/file-edit delivery, not a synthesized plasmid.
        source = material('linear')
        sources = {'input': source}
        goal = {'topology': 'linear', 'expected_sequence': str(source.seq)}
        build = run_step('annotate_feature', {'record': '$input', 'name': 'retained',
                    'start': 0, 'end': 30, 'strand': 1}, sources=sources, step_id='built')
        steps = [build]
        for index in (1, 2):
            qc = run_step('recipe_cloning_verification', {
                'recombinant_plasmid_seq_or_file': '$built', 'insert_start_0based': 300 if index == 1 else 600,
                'insert_end_0based': 650 if index == 1 else 850}, sources=sources, previous=steps, step_id=f'assay{index}')
            self.assertEqual(qc.status, 'completed', qc.error)
            steps.append(qc)
        candidate = build.result.only_product()
        with tempfile.TemporaryDirectory(prefix='交付_') as temp:
            result = deliver_result(goal, sources, steps, candidate, temp, output_step='built',
                                    report_notes='Independent reviewed description.', result_kind='component',
                                    required_scopes=['sequence_model', 'file', 'user_goal'])
            directory = Path(result['directory'])
            with (directory / 'oligo_order_table.tsv').open(encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream, delimiter='\t'))
            self.assertEqual(len({p['name'] for p in rows}), len(rows))
            self.assertEqual(len(rows), 6)
            self.assertTrue(all(p['name'].startswith(('assay1_', 'assay2_')) for p in rows))
            self.assertEqual({p['role'] for p in rows}, {'qc'})
            self.assertEqual(result['validation']['verification_quality']['status'], 'PASSED')
            self.assertEqual(result['validation']['verification_quality']['subject_version'], candidate.record_version)
            self.assertIn('Independent reviewed description.', (directory / 'design.md').read_text(encoding='utf-8'))
            from core.runtime_gate import verify_delivery_files
            selected = [str(directory / name) for name in ('construct.gb', 'construct.dna', 'design.md', 'oligo_order_table.tsv')]
            receipt = verify_delivery_files(directory, presented_files=selected,
                              expected_manifest_sha256=result['manifest_sha256'])
            self.assertEqual(receipt['status'], 'verified')
            self.assertEqual(receipt['domain_scope_results'], result['validation']['scope_results'])
            self.assertEqual(receipt['task_completion'], result['task_completion'])
            (directory / 'oligo_order_table.tsv').write_text('unchecked replacement', encoding='utf-8')
            with self.assertRaises(ValidationError):
                verify_delivery_files(directory, presented_files=selected,
                                      expected_manifest_sha256=result['manifest_sha256'])
            with self.assertRaises(GateRejected):
                deliver_result(goal, sources, steps, candidate, Path(temp) / 'changed', output_step='built',
                               validation=result['validation'], primers=result['validation']['primers'],
                               result_kind='component', required_scopes=['sequence_model', 'file', 'user_goal'],
                               report_notes='Changed explanation.')

    def test_failed_supplement_cannot_be_authorized_by_preparation_pass(self):
        source = material('linear')
        sources = {'input': source}
        build = run_step('annotate_feature', {'record': '$input', 'name': 'retained',
                    'start': 0, 'end': 30, 'strand': 1}, sources=sources, step_id='built')
        qc = run_step('recipe_cloning_verification', {'recombinant_plasmid_seq_or_file': '$built',
                'insert_start_0based': 300, 'insert_end_0based': 650,
                'sequencing_primers': [{'name': 'unbound', 'sequence': 'A' * 22}]},
                sources=sources, previous=[build], step_id='assay')
        self.assertEqual(qc.status, 'completed', qc.error)
        primers = [{**p, 'role': 'qc'} for p in qc.result.analysis['primers']]
        result = validate_candidate({'topology': 'linear'}, sources, [build, qc], build.result.only_product(),
                  primers=primers, output_step='built', required_scopes=['sequence_model', 'preparation_model', 'user_goal'])
        self.assertEqual(result['preparation_quality']['status'], 'NOT_APPLICABLE')
        self.assertEqual(result['verification_quality']['status'], 'FAILED')
        self.assertEqual(result['overall'], 'failed')

    def test_relabelling_failed_qc_as_preparation_cannot_bypass_quality(self):
        source = material('linear')
        sources = {'input': source}
        build = run_step('annotate_feature', {'record': '$input', 'name': 'retained',
                    'start': 0, 'end': 30, 'strand': 1}, sources=sources, step_id='built')
        qc = run_step('recipe_cloning_verification', {'recombinant_plasmid_seq_or_file': '$built',
                'insert_start_0based': 300, 'insert_end_0based': 650,
                'sequencing_primers': [{'name': 'unbound', 'sequence': 'A' * 22}]},
                sources=sources, previous=[build], step_id='assay')
        self.assertEqual(qc.status, 'completed', qc.error)
        for wrong_role in ('preparation', 'other'):
            primers = [{**p, 'role': 'qc' if p['name'] != 'unbound' else wrong_role}
                       for p in qc.result.analysis['primers']]
            result = validate_candidate({'topology': 'linear'}, sources, [build, qc], build.result.only_product(),
                       primers=primers, output_step='built', required_scopes=['sequence_model', 'user_goal'])
            self.assertEqual(result['overall'], 'failed', wrong_role)
            self.assertTrue(any(e in result['errors'] for e in ('OLIGO_ROLE_MISMATCH', 'INVALID_OLIGO_ROLE')))

    def test_original_circular_input_without_maintenance_is_still_rejected(self):
        source = material()
        sources = {'input': source}
        step = run_step('annotate_feature', {'record': '$input', 'name': 'retained',
                        'start': 0, 'end': 30, 'strand': 1}, sources=sources, step_id='built')
        result = validate_candidate({'topology': 'circular', 'expected_sequence': str(source.seq)},
                    sources, [step], step.result.only_product(), required_scopes=['sequence_model', 'user_goal'])
        self.assertEqual(result['overall'], 'failed')
        self.assertIn('BIOLOGICAL_CHECK_FAILED: BIO-08-REPLICON_MARKER', result['errors'])

    def test_directional_circular_coverage_follows_3prime_end_and_trim(self):
        from core.recipes.verification import sequencing_coverage
        from core.models.molecule import as_molecule
        source = material()
        primers = [{'role': 'sanger_sequencing', 'sequence': str(source.seq[870:890])},
                   {'role': 'sanger_sequencing', 'sequence': str(source.seq[15:35].reverse_complement())}]
        coverage = sequencing_coverage(as_molecule(source), primers, 50, 10)
        # Forward covers 900..939 modulo 900; reverse covers 4..-35.
        self.assertEqual(coverage['forward_gaps_0based'], [[40, 900]])
        self.assertEqual(coverage['reverse_gaps_0based'], [[5, 865]])
        self.assertEqual(coverage['combined_gaps_0based'], [[40, 865]])

    def test_independent_valid_supplement_keeps_its_actual_binding(self):
        source = material()
        sequence = str(source.seq[720:742])
        step = run_step('recipe_cloning_verification', {'recombinant_plasmid_seq_or_file': source,
                 'insert_start_0based': 300, 'insert_end_0based': 650,
                 'sequencing_primers': [{'name': 'independent_read', 'sequence': sequence}]},
                 sources={'input': source}, step_id='assay')
        self.assertEqual(step.status, 'completed', step.error)
        row = step.result.analysis['details']['sequencing_checks'][0]
        self.assertEqual(row['status'], 'PASSED')
        self.assertEqual(row['binding_interval_0based'], [720, 742])
        self.assertEqual(row['strand'], 1)


if __name__ == '__main__':
    unittest.main()
