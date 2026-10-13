"""Real Toolkit CLI tests with independent inputs and isolated Trace settings.

The PCR expectations are arithmetic on supplied strings, not Kit-generated
answers. Fault launchers alter only the temporary Trace log after the real CLI
has completed domain work; they never replace DNA computation or validation.
"""
from repository_paths import PROJECT_ROOT
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord


TOOLKIT = PROJECT_ROOT / 'genome-revival-toolkit'
ENTRY = TOOLKIT / 'scripts' / 'run_toolkit.py'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class GenomeRevivalPublicTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='revival-cli-', suffix='-中文材料')
        self.root = Path(self.temp.name)
        self.config = self.root / 'trace-settings.json'
        self.config.write_text('{"trace_level":"full"}', encoding='utf-8')
        self.env = dict(os.environ, SNAPGENE_TRACE_CONFIG=str(self.config),
                        PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
        self.calls = 0

    def tearDown(self):
        self.temp.cleanup()

    def write_json(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        return path

    def write_record(self, name, sequence, features=()):
        path = self.root / (name + '.gb')
        record = SeqRecord(Seq(sequence), id=name,
                           annotations={'molecule_type': 'DNA', 'topology': 'linear'},
                           features=list(features))
        with path.open('w', encoding='utf-8') as handle:
            SeqIO.write(record, handle, 'genbank')
        return path

    def identity_inputs(self):
        # A/G-only complete oligos cannot form Watson-Crick self/pair duplexes.
        # The 23-base deletion and the disrupted 3prime match are input facts.
        forward = 'AGAGGAGAAAGAGGGAAGAGGA'
        reverse = 'AAGGAAGAGAGGAGAGGAGAAG'
        rng = random.Random(271104)
        insert = ''.join(rng.choices('ACGT', k=120))
        prefix, suffix = 'TCGTACCGTATCGACTACGT', 'GCATCGTAGCATACGTCGAT'
        a = prefix + forward + insert + str(Seq(reverse).reverse_complement()) + suffix
        b = prefix + forward + insert[:45] + insert[68:] + str(Seq(reverse).reverse_complement()) + suffix
        negative = a[:len(prefix) + len(forward) - 1] + 'C' + a[len(prefix) + len(forward):]
        raw = {'a': a, 'b': b, 'negative': negative}
        refs = {key: {'path': str(self.write_record(key, value)),
                      'source': 'independent synthetic CLI input'} for key, value in raw.items()}
        context = self.write_json('identity-context.json', {'references': refs})
        request = {'original_request': '比较这些给定区域，用提供的完整引物预测PCR并检查质量。不要扩大为全基因组判断。',
                   'references': list(raw), 'compare_regions': True,
                   'assays': [{'id': 'regional_pair', 'forward': forward, 'reverse': reverse,
                               'size_resolution_bp': 20}],
                   'decisions': [{'text': '用户选择用提供的引物比较给定区域。', 'actor': 'user',
                                  'origin': 'user_statement', 'rationale': '两份参考覆盖同一局部检测范围。',
                                  'basis_references': ['a', 'b'],
                                  'limitations': ['局部检测不能证明完整基因组身份。']}]}
        return context, request, raw, forward, reverse

    def construct_inputs(self):
        # Source-bound independent expectation: 200-base arm + 240-base cargo
        # + 200-base arm. Existing donor is a supplied real PCR template.
        rng = random.Random(681120)
        target = ''.join(rng.choices('ACGT', k=2000))
        cargo = ''.join(rng.choices('ACGT', k=900))
        expected = target[600:800] + cargo[200:440] + target[810:1010]
        refs = {}
        for key, value, feature in (
                ('target', target, []),
                ('cargo', cargo, [SeqFeature(FeatureLocation(200, 440, strand=1), type='misc_feature',
                                            qualifiers={'label': ['independent_cargo']})]),
                ('donor', expected, [SeqFeature(FeatureLocation(200, 440, strand=1), type='misc_feature',
                                               qualifiers={'label': ['independent_cargo']})])):
            refs[key] = {'path': str(self.write_record(key, value, feature)),
                         'source': 'independent synthetic supplied template'}
        context = self.write_json('construct-context.json', {'references': refs})
        request = {'original_request': '按给定边界从现有供体模板制备线性供体，保留注释，并检查两侧接口及完整订单。',
                   'method': 'integration_donor', 'target_reference': 'target', 'cargo_reference': 'cargo',
                   'target_interval': {'start0': 800, 'end0': 810},
                   'cargo_interval': {'start0': 200, 'end0': 440}, 'arm_length': 200,
                   'preparation_method': 'pcr', 'donor_template_reference': 'donor',
                   'donor_interval': {'start0': 0, 'end0': 640}}
        return context, request, expected

    def cli(self, arguments, *, expected_code=0, lost_trace=False):
        entry = ENTRY
        if lost_trace:
            # Run the unchanged public parser/runner and actual DNA algorithms.
            # Simulate loss of the temporary log only after execute() returned.
            entry = self.root / 'lost-trace-launcher.py'
            entry.write_text(
                'import pathlib, runpy, sys\n'
                'sys.path.insert(0, ' + repr(str(TOOLKIT)) + ')\n'
                'import revival.bootstrap\n'
                'import revival.reporting as reporting\n'
                'original = reporting.finish_trace\n'
                'def missing_log(out, directory, result, level, policy="normal"):\n'
                '    if not (pathlib.Path(out) / "result.json").is_file():\n'
                '        raise AssertionError("Fault must happen after actual domain files exist")\n'
                '    (pathlib.Path(directory) / "events.jsonl").unlink()\n'
                '    return original(out, directory, result, level, policy)\n'
                'reporting.finish_trace = missing_log\n'
                'sys.argv[0] = ' + repr(str(ENTRY)) + '\n'
                'runpy.run_path(' + repr(str(ENTRY)) + ', run_name="__main__")\n',
                encoding='utf-8')
        process = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(entry), *map(str, arguments)],
                                 cwd=str(PROJECT_ROOT), env=self.env, text=True,
                                 encoding='utf-8', errors='replace', capture_output=True, timeout=240)
        self.assertEqual(process.returncode, expected_code,
                         process.stdout + '\nSTDERR:\n' + process.stderr)
        try:
            result = json.loads(process.stdout)
        except ValueError as exc:
            self.fail('Public CLI did not return usable JSON: ' + process.stdout + '\n' + str(exc))
        return result

    def run_kit(self, kit, context, request, *, level='full', policy='normal', expected_code=0,
                trace_dir=None, lost_trace=False, out=None):
        self.calls += 1
        self.config.write_text(json.dumps({'trace_level': level}), encoding='utf-8')
        out = out or self.root / ('result-' + str(self.calls))
        request_path = self.write_json('request-' + str(self.calls) + '.json', request)
        arguments = [kit, '--context', context, '--request', request_path, '--out-dir', out,
                     '--trace-mode', policy]
        if trace_dir is not None:
            arguments.extend(['--trace-dir', trace_dir])
        result = self.cli(arguments, expected_code=expected_code, lost_trace=lost_trace)
        return result, Path(out)

    def technical(self, public):
        return json.loads(Path(public['technical_record']).read_text(encoding='utf-8'))

    def graph(self, public):
        return json.loads(Path(public['trace']['technical_record']).read_text(encoding='utf-8'))

    def assert_actual_donor(self, result, expected):
        domain = self.technical(result)
        self.assertEqual(domain['status'], 'delivered')
        self.assertFalse(domain['original_task_verified'])
        delivery = domain['delivery']
        directory = Path(delivery['directory'])
        with (directory / 'construct.gb').open(encoding='utf-8') as handle:
            actual = SeqIO.read(handle, 'genbank')
        self.assertEqual(str(actual.seq), expected)
        self.assertEqual(actual.annotations['topology'], 'linear')
        with (directory / 'construct.dna').open('rb') as handle:
            native = SeqIO.read(handle, 'snapgene')
        self.assertEqual(str(native.seq), expected)
        self.assertEqual(native.annotations['topology'], 'linear')
        cargo = [feature for feature in actual.features
                 if feature.qualifiers.get('label') == ['independent_cargo']]
        self.assertEqual(len(cargo), 1)
        self.assertEqual((int(cargo[0].location.start), int(cargo[0].location.end), cargo[0].location.strand),
                         (200, 440, 1))
        scopes = delivery['validation']['scope_results']
        self.assertEqual({key: scopes[key]['status'] for key in
                          ('sequence_model', 'preparation_model', 'file', 'user_goal')},
                         {key: 'PASSED' for key in ('sequence_model', 'preparation_model', 'file', 'user_goal')})
        self.assertEqual(domain['delivery_receipt']['status'], 'verified')
        self.assertEqual(result['file_check']['status'], 'verified')
        self.assertIn('Whole-genome', ' '.join(domain['not_checked']))
        with (directory / 'oligo_order_table.tsv').open(encoding='utf-8', newline='') as handle:
            orders = list(csv.DictReader(handle, delimiter='\t'))
        self.assertTrue(orders)
        return domain, directory, orders

    def test_actual_identity_and_original_user_reason_are_traceable(self):
        context, request, raw, forward, reverse = self.identity_inputs()
        public, _ = self.run_kit('identity', context, request)
        domain = self.technical(public)
        assay = domain['assays'][0]
        self.assertEqual(public['status'], 'analysed')
        self.assertEqual(assay['quality_status'], 'PASSED', assay['quality'])
        predictions = {row['reference']: row for row in assay['predictions']}
        self.assertEqual(predictions['a']['amplicon_length_bp'], len(forward) + 120 + len(reverse))
        self.assertEqual(predictions['b']['amplicon_length_bp'], len(forward) + 97 + len(reverse))
        self.assertEqual(predictions['negative']['prediction'], 'NO_EXACT_PRODUCT')
        self.assertEqual(predictions['a']['amplicon_length_bp'] - predictions['b']['amplicon_length_bp'], 23)
        self.assertEqual(assay['discrimination']['status'], 'PREDICTED_DIFFERENT')
        self.assertFalse(domain['original_task_verified'])
        self.assertEqual(public['trace']['status'], 'complete')
        graph = self.graph(public)
        self.assertEqual(graph['integrity'], 'complete')
        nodes = list(graph['source_records'].values())
        requirements = [row for row in nodes if row.get('kind') == 'requirement']
        self.assertEqual([row['text'] for row in requirements], [request['original_request']])
        decisions = [row for row in nodes if row.get('kind') == 'decision']
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]['rationale'], request['decisions'][0]['rationale'])
        self.assertEqual(decisions[0]['decision_actor'], 'user')
        self.assertEqual(decisions[0]['explanation_origin'], 'user_statement')
        validations = [row for row in nodes if row.get('kind') == 'validation']
        self.assertTrue(any(row.get('result_event_ref') for row in validations))
        self.assertTrue(all(row['status'] == 'linked' for row in graph['handoff']['files']))
        events = [row for row in nodes if row.get('event_type') == 'stage_completed']
        pcr = [row['payload']['result'] for row in events
               if row['payload'].get('stage') == 'identity.simulate_pcr']
        self.assertEqual(sorted(row['analysis']['amplicon_length'] for row in pcr), [141, 164])
        order = next(Path(row['path']) for row in public['present_files'] if Path(row['path']).suffix == '.tsv')
        with order.open(encoding='utf-8', newline='') as handle:
            rows = list(csv.DictReader(handle, delimiter='\t'))
        self.assertEqual([row['sequence_5to3'] for row in rows], [forward, reverse])
        self.assertTrue(all(row['quality_status'] == 'PASSED' for row in rows))

    def test_failed_expectation_is_not_upgraded_by_complete_trace_or_file_receipt(self):
        context, request, _, _, _ = self.identity_inputs()
        request['assays'][0]['expected'] = {'negative': 'AMPLICON'}
        public, _ = self.run_kit('identity', context, request, expected_code=2)
        domain = self.technical(public)
        self.assertEqual(public['status'], 'incomplete')
        self.assertEqual(domain['checks'][0]['status'], 'FAILED')
        self.assertEqual(domain['checks'][0]['details']['expected_mismatches'], ['negative'])
        self.assertEqual(public['trace']['status'], 'complete')
        self.assertEqual(public['file_check']['status'], 'verified')
        validations = [row for row in self.graph(public)['source_records'].values()
                       if row.get('kind') == 'validation']
        self.assertTrue(any(row.get('result') == 'FAILED' for row in validations), validations)
        self.assertFalse(domain['original_task_verified'])

    def test_missing_evidence_returns_unmeasured_not_a_fake_zero_or_pass(self):
        context = self.write_json('empty-context.json', {'references': {}})
        request = {'original_request': '当前没有菌落计数和遗传检测原始数据，请指出可证明的范围和缺口。',
                   'observations': [], 'comparisons': [], 'genotype_results': []}
        public, _ = self.run_kit('evidence', context, request, expected_code=2)
        domain = self.technical(public)
        self.assertEqual(domain['status'], 'incomplete')
        self.assertEqual(domain['groups'], [])
        self.assertEqual(domain['checks'][0]['status'], 'INCOMPLETE')
        self.assertTrue(all(row['status'] == 'NOT_TESTED' for row in domain['conclusions']))
        self.assertEqual(public['trace']['status'], 'complete')
        self.assertEqual(public['file_check']['status'], 'verified')
        self.assertFalse(domain['original_task_verified'])

    def test_construct_off_observed_full_keep_actual_dna_order_quality_and_scopes(self):
        context, request, expected = self.construct_inputs()
        before = {entry['path']: digest(entry['path'])
                  for entry in json.loads(context.read_text(encoding='utf-8'))['references'].values()}
        fingerprints = []
        for level in ('off', 'observed', 'full'):
            with self.subTest(level=level):
                public, out = self.run_kit('construct', context, request, level=level)
                domain, directory, _ = self.assert_actual_donor(public, expected)
                fingerprints.append({
                    'files': {name: digest(directory / name) for name in
                              ('construct.gb', 'construct.dna', 'construct.fasta', 'oligo_order_table.tsv')},
                    'preparation_quality': domain['delivery']['validation']['preparation_quality'],
                    'verification_quality': domain['delivery']['validation']['verification_quality'],
                    'scopes': domain['delivery']['validation']['scope_results']})
                if level == 'off':
                    self.assertEqual(public['trace']['status'], 'off')
                    self.assertFalse((out / 'evidence-trace' / 'events.jsonl').exists())
                else:
                    self.assertEqual(public['trace']['status'], 'complete')
                    graph = self.graph(public)
                    artifacts = [row for row in graph['source_records'].values()
                                 if row.get('kind') == 'artifact' and row.get('role') == 'authoritative']
                    self.assertEqual({Path(row['path']).suffix for row in artifacts}, {'.gb', '.dna', '.fasta'})
                    self.assertTrue(all(row.get('result_event_ref') for row in artifacts))
                    self.assertTrue(all(row['status'] == 'linked' for row in graph['handoff']['files']))
        self.assertEqual(fingerprints[0], fingerprints[1])
        self.assertEqual(fingerprints[0], fingerprints[2])
        self.assertEqual(before, {path: digest(path) for path in before})

    def test_rebuild_views_uses_same_records_and_original_explanation(self):
        context, request, _, _, _ = self.identity_inputs()
        public, out = self.run_kit('identity', context, request)
        trace = out / 'evidence-trace'
        events_before = (trace / 'events.jsonl').read_bytes()
        original = self.graph(public)
        original_md = (trace / 'report.md').read_text(encoding='utf-8')
        for name in ('index.html', 'report.md', 'graph.json'):
            (trace / name).unlink()
        rebuilt = self.cli(['rebuild-report', '--trace-dir', trace])
        self.assertEqual(rebuilt['integrity'], 'complete')
        self.assertEqual((trace / 'events.jsonl').read_bytes(), events_before)
        self.assertEqual((trace / 'report.md').read_text(encoding='utf-8'), original_md)
        graph = json.loads((trace / 'graph.json').read_text(encoding='utf-8'))
        self.assertEqual(graph['source_records'], original['source_records'])
        self.assertEqual(graph['handoff'], original['handoff'])
        self.assertIn(request['decisions'][0]['rationale'], (trace / 'index.html').read_text(encoding='utf-8'))

    def test_changed_output_source_context_request_and_receipt_reject_old_receipt(self):
        context, request, _, _, _ = self.identity_inputs()
        public, out = self.run_kit('identity', context, request)
        receipt = json.loads(Path(public['receipt']).read_text(encoding='utf-8'))
        source = Path(json.loads(context.read_text(encoding='utf-8'))['references']['a']['path'])
        inputs = {Path(row['path']).name: Path(row['path']) for row in receipt['source_files']}
        request_path = next(path for name, path in inputs.items() if name.startswith('request-'))
        for path, message in ((out / 'summary.md', 'Output changed'),
                              (out / 'identity-primers.tsv', 'Output changed'),
                              (source, 'Input version changed'), (context, 'Input version changed'),
                              (request_path, 'Input version changed'),
                              (Path(public['receipt']), 'Toolkit receipt changed')):
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(original + b'\n')
                try:
                    checked = self.cli(['verify', '--out-dir', out, '--receipt-sha256', public['receipt_sha256']], expected_code=2)
                    self.assertEqual(checked['status'], 'incomplete')
                    self.assertTrue(any(message in error for error in checked['errors']), checked)
                finally:
                    path.write_bytes(original)
        valid = self.cli(['verify', '--out-dir', out, '--receipt-sha256', public['receipt_sha256']])
        self.assertEqual(valid['status'], 'verified')

    def test_changed_formal_dna_cannot_inherit_toolkit_or_core_receipt(self):
        context, request, expected = self.construct_inputs()
        public, out = self.run_kit('construct', context, request, level='off')
        _, directory, _ = self.assert_actual_donor(public, expected)
        for name in ('construct.gb', 'construct.dna'):
            with self.subTest(name=name):
                path = directory / name
                raw = path.read_bytes()
                if name.endswith('.gb'):
                    self.assertIn(b'independent_cargo', raw)
                    changed = raw.replace(b'independent_cargo', b'changed_annotation')
                else:
                    changed = raw + b'outside-modification'
                path.write_bytes(changed)
                try:
                    checked = self.cli(['verify', '--out-dir', out, '--receipt-sha256', public['receipt_sha256']], expected_code=2)
                    self.assertEqual(checked['status'], 'failed')
                    self.assertEqual(checked['exception'], 'ValidationError')
                    self.assertEqual(checked['error'], 'Delivered files are missing or changed')
                finally:
                    path.write_bytes(raw)

    def test_rebuild_changed_presented_file_keeps_old_validation_unapplied(self):
        context, request, _, _, _ = self.identity_inputs()
        public, out = self.run_kit('identity', context, request)
        trace = out / 'evidence-trace'
        before = self.graph(public)
        (out / 'identity-primers.tsv').write_text('name\tsequence_5to3\nchanged\tACGT\n', encoding='utf-8')
        rebuilt = self.cli(['rebuild-report', '--trace-dir', trace])
        after = json.loads((trace / 'graph.json').read_text(encoding='utf-8'))
        handoff = next(row for row in after['handoff']['files'] if Path(row['path']).suffix == '.tsv')
        self.assertEqual(handoff['status'], 'changed')
        self.assertEqual(handoff['artifact_refs'], [])
        self.assertEqual(after['handoff']['run_id'], before['handoff']['run_id'])
        self.assertEqual(before['snapshot']['organization_status'], 'current')
        self.assertEqual(rebuilt['organization_status'], 'stale')
        old_validations = {ref: row for ref, row in before['source_records'].items() if row.get('kind') == 'validation'}
        self.assertEqual({ref: after['source_records'][ref] for ref in old_validations}, old_validations)
        checked = self.cli(['verify', '--out-dir', out, '--receipt-sha256', public['receipt_sha256']], expected_code=2)
        self.assertEqual(checked['status'], 'incomplete')

    def test_normal_trace_startup_fault_preserves_domain_and_checked_files(self):
        context, request, _, forward, reverse = self.identity_inputs()
        blocked = self.root / 'trace-is-a-file'
        blocked.write_text('intentional temporary recorder failure', encoding='utf-8')
        public, _ = self.run_kit('identity', context, request, trace_dir=blocked)
        self.assertEqual(public['status'], 'analysed')
        self.assertEqual(public['trace']['status'], 'TRACE_INCOMPLETE')
        domain = self.technical(public)
        self.assertEqual((domain['assays'][0]['forward'], domain['assays'][0]['reverse']), (forward, reverse))
        self.assertEqual(domain['checks'][0]['status'], 'PASSED')
        self.assertEqual(public['file_check']['status'], 'verified')

    def test_bad_settings_new_call_cannot_borrow_an_old_trace_run(self):
        context, request, _, _, _ = self.identity_inputs()
        first, out = self.run_kit('identity', context, request)
        old_graph = self.graph(first)
        self.config.write_text('{"trace_level":"invalid-value"}', encoding='utf-8')
        # Same actual paths, but a new public invocation. Runtime deliberately
        # permits domain work in normal mode; no old run can prove new capture.
        public = self.cli(['identity', '--context', context,
                           '--request', self.root / 'request-1.json', '--out-dir', out])
        self.assertEqual(public['status'], 'analysed')
        self.assertEqual(public['trace']['status'], 'TRACE_INCOMPLETE')
        self.assertEqual(public['file_check']['status'], 'verified')
        domain = self.technical(public)
        self.assertEqual(domain['assays'][0]['quality_status'], 'PASSED')
        current = json.loads((out / 'evidence-trace' / 'graph.json').read_text(encoding='utf-8'))
        self.assertTrue(all(ref in current['source_records'] for ref in old_graph['source_records']))

    def test_normal_lost_trace_after_construct_keeps_actual_dna_and_failure_visible(self):
        context, request, expected = self.construct_inputs()
        public, _ = self.run_kit('construct', context, request, lost_trace=True)
        self.assert_actual_donor(public, expected)
        self.assertEqual(public['trace']['status'], 'TRACE_INCOMPLETE')
        self.assertIn('No completed Toolkit run', public['trace']['error'])

    def test_strict_lost_trace_stops_without_deleting_completed_dna(self):
        context, request, expected = self.construct_inputs()
        public, out = self.run_kit('construct', context, request, policy='strict', lost_trace=True, expected_code=2)
        self.assertEqual(public['status'], 'failed')
        self.assertEqual(public['exception'], 'TraceStopped')
        self.assertIn('completed DNA files remain unchanged', public['error'])
        self.assertIn('No completed Toolkit run', public['error'])
        domain = json.loads((out / 'result.json').read_text(encoding='utf-8'))
        self.assertEqual(domain['status'], 'delivered')
        directory = Path(domain['delivery']['directory'])
        with (directory / 'construct.gb').open(encoding='utf-8') as handle:
            self.assertEqual(str(SeqIO.read(handle, 'genbank').seq), expected)
        self.assertTrue((directory / 'construct.dna').is_file())
        self.assertEqual(domain['delivery_receipt']['status'], 'verified')
        self.assertFalse((out / 'TOOLKIT-RECEIPT.json').exists())

    def test_strict_off_rejects_before_execution_and_preserves_existing_files(self):
        context, request, _, _, _ = self.identity_inputs()
        out = self.root / 'strict-off'
        out.mkdir()
        previous = out / 'previous-result.dna'
        previous.write_bytes(b'previous checked files remain the caller responsibility')
        before = previous.read_bytes()
        public, _ = self.run_kit('identity', context, request, level='off', policy='strict', expected_code=2, out=out)
        self.assertEqual(public['exception'], 'TraceStopped')
        self.assertIn('Trace is Off', public['error'])
        self.assertEqual(previous.read_bytes(), before)
        self.assertFalse((out / 'result.json').exists())

    def test_same_path_same_bytes_two_actual_runs_use_the_selected_handoff_run(self):
        context, request, _, _, _ = self.identity_inputs()
        out = self.root / 'same-output'
        first, _ = self.run_kit('identity', context, request, out=out)
        first_graph = self.graph(first)
        first_tsv = (out / 'identity-primers.tsv').read_bytes()
        second, _ = self.run_kit('identity', context, request, out=out)
        second_graph = self.graph(second)
        self.assertEqual((out / 'identity-primers.tsv').read_bytes(), first_tsv)
        self.assertEqual(second['trace']['status'], 'complete')
        self.assertEqual(len(second_graph['runs']), 2)
        self.assertNotEqual(first_graph['handoff']['run_id'], second_graph['handoff']['run_id'])
        self.assertEqual(second_graph['handoff']['run_id'], second_graph['runs'][-1]['id'])
        self.assertTrue(all(row['status'] == 'linked' for row in second_graph['handoff']['files']))
        for row in second_graph['handoff']['files']:
            self.assertTrue(row['artifact_refs'])
            self.assertTrue(all(second_graph['source_records'][ref]['run_id'] == second_graph['handoff']['run_id']
                                for ref in row['artifact_refs']))


if __name__ == '__main__':
    unittest.main()
