"""Public organization contracts for branched, revised and adversarial submissions."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evidence_trace.intake import observe_material
from evidence_trace.process import assemble, organize, save_report_plan
from evidence_trace.projection import build_facts
from evidence_trace.recorder import Recorder
from evidence_trace.runtime import trace_file_call


class ProcessBoundaryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='trace-process-boundary-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = patch.dict(os.environ, SNAPGENE_TRACE_CONFIG=str(self.root / 'config.json'))
        env.start()
        self.addCleanup(env.stop)
        self.trace = self.root / 'trace'
        self.r = Recorder(self.trace)
        self.r.record({'id': 'R', 'kind': 'requirement', 'text': 'Keep both comparison branches'})
        self.reason = 'Use the supplied material.\nRetain the alternative for comparison.'
        self.quote = observe_material(self.r, {'kind': 'submitted_text', 'text': self.reason})
        self.r.record({'id': 'D', 'kind': 'decision', 'text': 'Use the supplied material',
            'rationale': self.reason, 'decision_actor': 'ai', 'explanation_origin': 'ai_concurrent',
            'decision_source': {'reference': 'public-response'}, 'responds_to': ['R']})
        output = self.root / 'observation.txt'
        trace_file_call('save_observation', lambda: output.write_text('actual file', encoding='utf-8'),
            trace_dir=self.trace, expected_paths=[output], output_paths=lambda _: [output], artifact_role='document')
        self.r = Recorder(self.trace)
        facts = build_facts(self.r.events)
        self.result_ref = next(e['event_id'] for e in self.r.events if e['event_type'] == 'file_operation_completed')
        self.artifact_ref = next(k for k, v in facts['source_records'].items() if v.get('kind') == 'artifact')
        self.packet = {'schema_version': 'trace-organization-v1', 'id': 'process',
            'basis': {k: facts['snapshot'][k] for k in ('trace_id', 'through_sequence')},
            'design_process': {
                'stages': [{'id': 'comparison', 'title': 'Compare materials', 'purpose': 'Preserve the requested alternative',
                    'step_ids': ['request', 'choice', 'operation', 'file'], 'source_refs': ['R@1'],
                    'branches': [{'id': 'retained', 'label': 'Retained comparison', 'step_ids': ['choice'], 'source_refs': ['D@1']}]}],
                'steps': {
                    'request': {'kind': 'requirement', 'content': 'Keep both comparison branches', 'source_refs': ['R@1']},
                    'choice': {'kind': 'choice', 'title': 'Material selection', 'content': 'Use the supplied material',
                        'subject_ref': 'D@1', 'source_refs': ['D@1'],
                        'reason': {'text': self.reason, 'origin': 'original_statement', 'source_refs': [self.quote]},
                        'limitations': [{'text': 'File observations do not establish expression.', 'source_refs': ['D@1']}]},
                    'operation': {'kind': 'program_result', 'content': 'Save the actual observation',
                        'source_refs': [self.result_ref], 'outcome_refs': [self.artifact_ref]},
                    'file': {'kind': 'artifact', 'content': 'Observation document', 'source_refs': [self.artifact_ref]}},
                'relations': [{'id': 'request-choice', 'from': 'request', 'to': 'choice',
                    'kind': 'responds_to', 'meaning': 'Selection responds to the comparison requirement',
                    'source_refs': ['R@1', 'D@1']}],
                'paths': [{'id': 'path', 'label': 'Recorded sequence', 'order_kind': 'recorded_order',
                    'step_ids': ['request', 'choice', 'operation', 'file'], 'source_refs': ['R@1', 'D@1']}],
                'unresolved': [{'id': 'question', 'text': 'The observation is not an expression assay.',
                    'source_refs': ['D@1'], 'step_refs': ['choice']}], 'detail_refs': [self.quote]},
            'report_plan': {'profile': 'research-report-v1', 'title': 'Independent comparison record',
                'context': {'text': 'Compare supplied materials using the recorded requirement.', 'source_refs': ['R@1']},
                'sections': [{'id': 'section', 'title': 'How the comparison was formed',
                    'step_refs': ['request', 'choice', 'operation', 'file'], 'source_refs': ['R@1', 'D@1'],
                    'summary': 'Keep selection and program observation distinct.', 'unresolved_refs': ['question']}],
                'diagram': {'reading_order': ['request', 'choice', 'operation', 'file'],
                    'relation_refs': ['request-choice'], 'short_labels': {'choice': 'Material selection'}},
                'default_expanded_refs': ['choice'], 'detail_refs': [self.quote]}}

    def assert_rejected_without_append(self, packet):
        before = (self.trace / 'events.jsonl').read_bytes()
        with self.assertRaises(ValueError):
            organize(self.r, packet)
        self.assertEqual((self.trace / 'events.jsonl').read_bytes(), before)

    def test_branched_process_preserves_human_context_without_promoting_observation(self):
        source_events = copy.deepcopy(self.r.events)
        key = organize(self.r, self.packet)
        graph = self.r.render()
        self.assertEqual(key, 'process@1')
        self.assertEqual(graph['snapshot']['organization_status'], 'current')
        self.assertEqual(graph['design_process'], self.packet['design_process'])
        self.assertEqual(graph['report']['sections'][0]['title'], 'How the comparison was formed')
        self.assertEqual(graph['report']['steps'][1]['reason']['origin'], 'original_statement')
        self.assertTrue(any('not an expression assay' in item['text'] for item in graph['report']['review']))
        self.assertFalse(graph['report']['checks'])
        self.assertEqual(self.r.events[:len(source_events)], source_events)

    def test_host_relations_cannot_impersonate_program_provenance(self):
        for change in ({'kind': 'produced_by'}, {'to': 'unrecorded-step'},
                       {'fact_relation_ids': ['fabricated-runtime-edge']}):
            with self.subTest(change=change):
                packet = copy.deepcopy(self.packet)
                packet['design_process']['relations'][0].update(change)
                self.assert_rejected_without_append(packet)

    def test_logical_reordering_is_allowed_but_cannot_be_called_recorded_order(self):
        packet = copy.deepcopy(self.packet)
        packet['design_process']['paths'][0]['step_ids'].reverse()
        self.assert_rejected_without_append(packet)
        packet['design_process']['paths'][0]['order_kind'] = 'logical_process'
        organize(self.r, packet)
        self.assertEqual(self.r.render()['design_process']['paths'][0]['step_ids'][0], 'file')

    def test_later_explanation_cannot_be_laundered_as_an_original_quote(self):
        packet = copy.deepcopy(self.packet)
        reason = packet['design_process']['steps']['choice']['reason']
        reason['text'] = 'Later interpretation of the comparison.'
        self.assert_rejected_without_append(packet)
        reason['origin'] = 'later_interpretation'
        organize(self.r, packet)
        graph = self.r.render()
        self.assertEqual(graph['source_records']['D@1']['rationale'], self.reason)
        self.assertEqual(graph['report']['steps'][1]['reason']['origin'], 'later_interpretation')
        self.assertEqual(graph['report']['steps'][1]['reason']['text'], reason['text'])

    def test_public_quote_allows_line_endings_but_not_truncated_claims(self):
        packet = copy.deepcopy(self.packet)
        packet['design_process']['steps']['choice']['reason']['text'] = self.reason.splitlines()[0]
        self.assert_rejected_without_append(packet)
        packet['design_process']['steps']['choice']['reason']['text'] = self.reason.replace('\n', '\r\n')
        organize(self.r, packet)
        self.assertEqual(self.r.render()['design_process']['steps']['choice']['reason']['origin'], 'original_statement')

    def test_subject_and_branch_must_belong_to_their_actual_scope(self):
        changes = [lambda p: p['steps']['operation'].update(subject_ref='D@1', source_refs=['D@1', self.result_ref]),
                   lambda p: p['steps']['choice'].update(subject_ref='R@1'),
                   lambda p: p['stages'][0]['branches'][0].update(step_ids=['unrecorded-step']),
                   lambda p: p['stages'][0]['branches'][0].update(id='choice')]
        for change in changes:
            with self.subTest(change=changes.index(change)):
                packet = copy.deepcopy(self.packet)
                change(packet['design_process'])
                self.assert_rejected_without_append(packet)

    def test_report_revision_cannot_import_future_facts_or_alias_a_step(self):
        key = organize(self.r, self.packet)
        self.r.record({'id': 'Later', 'kind': 'requirement', 'text': 'New unrelated requirement'})
        before = (self.trace / 'events.jsonl').read_bytes()
        for change in ({'source_refs': ['Later@1']}, {'id': 'choice'}):
            plan = copy.deepcopy(self.packet['report_plan'])
            plan['sections'][0].update(change)
            with self.assertRaises(ValueError):
                save_report_plan(self.r, key, plan)
            self.assertEqual((self.trace / 'events.jsonl').read_bytes(), before)
        with self.assertRaisesRegex(ValueError, 'Unknown exact process_ref'):
            save_report_plan(self.r, 'process@missing', self.packet['report_plan'])

    def test_exact_process_version_is_selectable_and_missing_version_is_rejected(self):
        first = organize(self.r, self.packet)
        second_packet = copy.deepcopy(self.packet)
        second_packet['design_process']['steps']['choice']['title'] = 'Revised reading title'
        second = organize(self.r, second_packet)
        self.assertEqual(assemble(self.r.events)['snapshot']['organization_ref'], second)
        self.assertEqual(assemble(self.r.events, process_ref=first)['design_process']['steps']['choice']['title'], 'Material selection')
        with self.assertRaisesRegex(ValueError, 'Unknown process_ref'):
            assemble(self.r.events, process_ref='process@999')


if __name__ == '__main__':
    unittest.main()
