"""Independent provenance and privacy contracts from the engineering audit."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from evidence_trace.coverage import extract_choices, match_choices
from evidence_trace.intake import record_handoff
from evidence_trace.recorder import Recorder, project
from evidence_trace.runtime import observe, trace_file_call, traced_run

ROOT = Path(__file__).resolve().parents[1]


class EngineeringTraceAuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='trace-audit-中文-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = patch.dict(os.environ, SNAPGENE_TRACE_CONFIG=str(self.root / 'settings.json'))
        env.start()
        self.addCleanup(env.stop)

    def test_source_identity_keeps_version_and_unversioned_scope_distinct(self):
        actual = {'source_path': 'C:/material/source.gb', 'source_sha256': 'b' * 64}
        choices = extract_choices({'template_seq_or_file': actual})
        def match(target):
            return match_choices(choices, [{'key': 'D@1', 'rationale': 'Use recorded material',
                'targets': {'template_seq_or_file': target}}])[0]
        self.assertEqual(match(actual)['target_match'], 'matched')
        changed = match({**actual, 'source_sha256': 'a' * 64})
        self.assertEqual(changed['target_match'], 'unmatched')
        self.assertEqual(changed['source_version_match'], 'different_version')
        old = match(actual['source_path'])
        self.assertEqual(old['target_match'], 'ambiguous')
        self.assertEqual(old['source_version_match'], 'unknown')
        self.assertEqual(old['decision_refs'], ['D@1'])
        # Logical source IDs are not file-version declarations.
        logical = extract_choices({'source_id': 'vector_A'})
        self.assertEqual(match_choices(logical, [{'key': 'D@1', 'targets': {'source_id': 'vector_A'}}])[0]['target_match'], 'matched')

    def test_custom_command_credential_redaction_on_success_and_failure(self):
        marker = 'FAKE-AUDIT-CREDENTIAL-NOT-A-REAL-SECRET'
        sequence = 'ACGTTGCACGTACGATCGTAGCTAGCTA'
        script = self.root / 'command.py'
        script.write_text('import sys\nfrom pathlib import Path\n'
                          'Path(sys.argv[1]).write_text("executed", encoding="utf-8")\n'
                          'sys.exit(7 if "--fail" in sys.argv else 0)\n', encoding='utf-8')
        for fail in (False, True):
            trace = self.root / ('failed' if fail else 'success')
            output = self.root / ('failed.txt' if fail else 'success.txt')
            command = [sys.executable, '-X', 'utf8', str(ROOT / 'scripts/trace_run.py'),
                '--trace-dir', str(trace), '--output-file', str(output), '--',
                sys.executable, str(script), str(output), '--api-key', marker,
                '--token=' + marker, '--temperature', '30', '--sequence=' + sequence,
                '--header', 'Authorization: Bearer ' + marker]
            if fail:
                command.append('--fail')
            result = subprocess.run(command, capture_output=True, encoding='utf-8', errors='replace')
            self.assertEqual(result.returncode, 7 if fail else 0, result.stderr)
            self.assertEqual(output.read_text(encoding='utf-8'), 'executed')
            for name in ('events.jsonl', 'graph.json', 'index.html', 'report.md'):
                content = (trace / name).read_text(encoding='utf-8')
                self.assertNotIn(marker, content, name)
                self.assertNotIn(sequence, content, name)
            events = (trace / 'events.jsonl').read_text(encoding='utf-8')
            self.assertIn('--temperature', events)
            self.assertIn('30', events)

    def test_unobserved_before_state_cannot_assert_creation(self):
        existing = self.root / 'existing.gb'
        existing.write_text('unchanged source material', encoding='utf-8')
        trace = self.root / 'file-trace'
        trace_file_call('return_existing', lambda: str(existing), trace_dir=trace,
                        output_paths=lambda value: [value])
        recorder = Recorder(trace)
        artifacts = [n for n in project(recorder.events)['nodes'] if n['kind'] == 'artifact']
        self.assertEqual(artifacts[0]['generation_observation'], 'presence_only')
        self.assertEqual(record_handoff(recorder, [{'path': str(existing)}])['files'][0]['status'], 'untraced')

    def test_main_route_preserves_prior_artifact_identity_and_new_outputs(self):
        output = self.root / 'build'
        output.mkdir()
        old = output / 'existing.gb'
        old.write_text('source material before run', encoding='utf-8')
        new = output / 'new.gb'
        @traced_run('audit')
        def run(out_dir):
            def operation():
                new.write_text('new simulated output', encoding='utf-8')
                return {'files': [str(old), str(new)]}
            observe('execute', operation)
            return {'status': 'finished'}
        run(output)
        recorder = Recorder(output / 'evidence-trace')
        artifacts = {Path(n['path']).name: n for n in project(recorder.events)['nodes'] if n['kind'] == 'artifact'}
        self.assertEqual(artifacts[old.name]['generation_observation'], 'presence_only')
        self.assertEqual(artifacts[new.name]['generation_observation'], 'created')
        handoff = record_handoff(recorder, [{'path': str(old)}, {'path': str(new)}])
        self.assertEqual([f['status'] for f in handoff['files']], ['untraced', 'linked'])

    def test_known_absent_and_modified_paths_remain_traceable(self):
        file = self.root / 'product.gb'
        trace = self.root / 'write-trace'
        for content, status in [('first', 'created'), ('second', 'modified'), ('second', 'presence_only')]:
            trace_file_call('write', lambda: file.write_text(content, encoding='utf-8'),
                            trace_dir=trace, expected_paths=[file], output_paths=lambda _: [file])
            artifacts = [n for n in project(Recorder(trace).events)['nodes'] if n['kind'] == 'artifact']
            self.assertEqual(artifacts[-1]['generation_observation'], status)

    def test_dynamic_output_directory_records_actual_new_files(self):
        directory = self.root / 'dynamic'
        old = directory / 'old.txt'
        directory.mkdir()
        old.write_text('before', encoding='utf-8')
        new = directory / 'nested' / 'new.txt'
        def create():
            new.parent.mkdir()
            new.write_text('after', encoding='utf-8')
            return [old, new]
        trace = self.root / 'dynamic-trace'
        trace_file_call('dynamic', create, trace_dir=trace, output_directories=[directory],
                        output_paths=lambda files: files)
        artifacts = {Path(n['path']).name: n for n in project(Recorder(trace).events)['nodes'] if n['kind'] == 'artifact'}
        self.assertEqual(artifacts['old.txt']['generation_observation'], 'presence_only')
        self.assertEqual(artifacts['new.txt']['generation_observation'], 'created')

    def test_invalid_evidence_dimension_does_not_poison_log(self):
        recorder = Recorder(self.root / 'safe-log')
        recorder.ingest({'nodes': [
            {'id': 'S', 'kind': 'source', 'source_type': 'user-material', 'title': 'source'},
            {'id': 'E', 'kind': 'statement', 'text': 'observation', 'source_id': 'S'},
            {'id': 'C', 'kind': 'claim', 'text': 'claim'},
            {'id': 'D', 'kind': 'decision', 'text': 'choose', 'claim_ids': ['C']}]})
        before = (recorder.directory / 'events.jsonl').read_bytes()
        with self.assertRaisesRegex(ValueError, 'required_dimensions'):
            recorder.link({'statement_id': 'E', 'claim_id': 'C', 'required_dimensions': ['not-a-dimension']})
        self.assertEqual((recorder.directory / 'events.jsonl').read_bytes(), before)
        recorder.link({'statement_id': 'E', 'claim_id': 'C', 'relation': 'support', 'required_dimensions': ['host']})
        self.assertEqual(recorder.render()['integrity'], 'complete')


if __name__ == '__main__':
    unittest.main()
