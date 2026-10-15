"""View-only run cards over actual observed files, including a changed-input control."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from repository_paths import SKILL_ROOT
from evidence_trace.runtime import traced_run, observe_files
from evidence_trace.recorder import load_events
from evidence_trace.process import assemble
from evidence_trace.render import render


def observed_files(root,changed=False):
    config=root/'settings.json';config.write_text('{"trace_level":"observed"}',encoding='utf-8')
    def write(path,text):
        count=path.write_text(text,encoding='utf-8')
        return {'paths':[str(path)],'write_receipts':[{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'characters_written':count}]}
    @traced_run('synthetic-file-steps')
    def flow(out_dir):
        first=out_dir/'first.txt';incoming=out_dir/'incoming.txt'
        observe_files('first.export',write,args=(first,'construction-defined bytes'),output_paths=lambda value:value['paths'],output_directories=[out_dir])
        incoming.write_bytes(first.read_bytes()+(b' changed' if changed else b''))
        observe_files('next.read_export',write,args=(out_dir/'last.txt',incoming.read_text(encoding='utf-8')),
            input_paths=[incoming],output_paths=lambda value:value['paths'],output_directories=[out_dir])
    with patch.dict(os.environ,{'SNAPGENE_TRACE_CONFIG':str(config)}):flow(root,trace_dir=root/'trace')
    return assemble(load_events(root/'trace')[0])


class RunCardTests(unittest.TestCase):
    def test_author_note_stays_in_view_and_candidate_role_is_not_demoted(self):
        from evidence_trace.run_card import project_card
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);graph=observed_files(root)
            render(root/'trace',graph,language='en',notes=['Official GitLab CI was not executed.'])
            self.assertIn('Official GitLab CI was not executed.',(root/'trace/index.html').read_text(encoding='utf-8'))
            self.assertNotIn('Official GitLab CI was not executed.',(root/'trace/graph.json').read_text(encoding='utf-8'))
        graph={'nodes':[{'key':'candidate@1','kind':'artifact','path':'candidate.gb','sha256':'a'*64,'role':'candidate-file'},
                        {'key':'support@1','kind':'artifact','path':'candidate.gb','sha256':'a'*64,'role':'supporting-file'}]}
        self.assertEqual(project_card(graph)['outputs'][0]['role'],'candidate-file')

    def test_public_renderer_defaults_to_english_card_and_keeps_full_view(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);graph=observed_files(root)
            events=(root/'trace/events.jsonl').read_bytes()
            render(root/'trace',graph,language='en')
            html=(root/'trace/index.html').read_text(encoding='utf-8')
            self.assertTrue('id="run-card"' in html,'Default run-card view is missing')
            self.assertIn('id="full-view"',html)
            for label in ('Data chain','Program-verified checks','Declared statements','Not checked or not performed','Technical details','Full view'):
                self.assertIn(label,html)
            self.assertIn('id="report"',html)
            self.assertIn('id="trace-data"',html)
            self.assertNotRegex(html,r'<(?:script|link)[^>]+(?:src|href)=["\']https?://')
            self.assertEqual((root/'trace/events.jsonl').read_bytes(),events)
            self.assertIn('Run card',(root/'trace/report.md').read_text(encoding='utf-8'))

    def test_solid_links_require_actual_equal_file_hashes(self):
        from evidence_trace.run_card import project_card
        for changed in (False,True):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory() as temp:
                graph=observed_files(Path(temp),changed);before=copy.deepcopy(graph)
                card=project_card(graph)
                verified=[row for row in card['relations'] if row['verified']]
                self.assertEqual(bool(verified),not changed)
                self.assertTrue(all(row['fact_relation_ids'] for row in verified))
                self.assertEqual(graph,before)

    def test_valid_looking_digest_alone_cannot_create_a_solid_link(self):
        from evidence_trace.run_card import project_card
        with tempfile.TemporaryDirectory() as temp:
            graph=observed_files(Path(temp))
            fact=next(row for row in graph['fact_relations'] if row.get('verification_method')=='sha256_equality')
            graph['source_records'][fact['from']]['sha256']='0'*64
            self.assertFalse(any(row['verified'] for row in project_card(graph)['relations']))


if __name__=='__main__':unittest.main()
