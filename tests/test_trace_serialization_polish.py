"""Independent storage expectations and public report rebuild error preservation."""
import copy
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

from repository_paths import PROJECT_ROOT
sys.path.insert(0, str(PROJECT_ROOT / 'genome-revival-toolkit'))
from evidence_trace.storage import expand_machine, machine_export, machine_json
from evidence_trace.recorder import Recorder
from revival.reporting import rebuild


class TraceSerializationPolishTests(unittest.TestCase):
    def test_public_title_is_used_and_invalid_title_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory(prefix='标题公共入口-') as temporary:
            root=Path(temporary)
            context=root/'context.json';context.write_text('{"references":{}}',encoding='utf-8')
            config=root/'settings.json';config.write_text('{"trace_level":"full"}',encoding='utf-8')
            title='独立材料核对 & <原始标题>'
            request=root/'request.json'
            request.write_text(json.dumps({'title':title,'original_request':'没有原始实验观察，只保留缺口。','observations':[]},ensure_ascii=False),encoding='utf-8')
            env=dict(os.environ,SNAPGENE_TRACE_CONFIG=str(config),PYTHONIOENCODING='utf-8')
            entry=PROJECT_ROOT/'genome-revival-toolkit/scripts/run_toolkit.py'
            command=[sys.executable,'-X','utf8','-B',str(entry),'evidence','--context',str(context),'--request',str(request),'--out-dir',str(root/'out')]
            result=subprocess.run(command,env=env,capture_output=True,encoding='utf-8',errors='replace')
            self.assertEqual(result.returncode,2)  # Missing science is still incomplete.
            self.assertEqual(json.loads(result.stdout)['status'],'incomplete')
            graph=json.loads((root/'out/evidence-trace/graph.json').read_text(encoding='utf-8'))
            self.assertEqual(graph['report']['title'],title)
            html=(root/'out/evidence-trace/index.html').read_text(encoding='utf-8')
            self.assertNotIn('<原始标题>',html)
            request.write_text(json.dumps({'title':{'not':'text'},'original_request':'核对缺口。'}),encoding='utf-8')
            invalid=subprocess.run(command[:-1]+[str(root/'invalid')],env=env,capture_output=True,encoding='utf-8',errors='replace')
            self.assertEqual(invalid.returncode,2)
            self.assertIn('title must be nonempty text',invalid.stdout)

    def test_reference_export_matches_independent_contract_and_does_not_borrow_mutable_data(self):
        event = {'event_id':'event/a~1','payload':{'input':{'rows':[{'value':17}, {'value':0}]},'result':{'exact':False}}}
        authored = {'event_id':'organization','payload':{'text':'后来整理'}}
        graph = {'schema_version':'design-process-v1','source_records':{event['event_id']:event},
                 'audit_events':[event, authored], 'runs':[{'id':'run','stages':[
                    {'event_id':event['event_id'],'input':copy.deepcopy(event['payload']['input']),
                     'result':{'exact':True}, 'before':{'retained':'different value'}}]}]}
        before = copy.deepcopy(graph)
        expected = copy.deepcopy(graph)
        expected['schema_version'] = 'design-process-v2'
        expected['source_records']['organization'] = authored
        expected['audit_events'] = [{'$ref':'#/source_records/event~1a~01'}, {'$ref':'#/source_records/organization'}]
        expected['runs'][0]['stages'][0]['input'] = {'$ref':'#/source_records/event~1a~01/payload/input'}
        self.assertEqual(json.loads(machine_json(graph)),expected)
        self.assertEqual(machine_export(graph),expected)
        self.assertEqual(graph,before)
        exported = machine_export(graph)
        exported['source_records'][event['event_id']]['payload']['input']['rows'][0]['value'] = 999
        exported['runs'][0]['stages'][0]['result']['exact'] = False
        self.assertEqual(graph,before)
        # The authored event is intentionally added to source_records for dereferencing.
        restored = expand_machine(machine_export(graph))
        self.assertEqual(restored['runs'],before['runs'])
        self.assertEqual(restored['audit_events'],before['audit_events'])

    def test_rebuild_keeps_failed_capture_and_all_original_journal_bytes(self):
        with tempfile.TemporaryDirectory(prefix='报告重建-') as temporary:
            root = Path(temporary)
            recorder = Recorder(root)
            recorder.record({'id':'request','kind':'requirement','text':'核对给定材料'})
            recorder.append('trace_error',{'message':'原调用没有完整返回'})
            original = (root/'events.jsonl').read_bytes()
            result = rebuild(root)
            self.assertNotEqual(result['integrity'],'complete')
            self.assertEqual((root/'events.jsonl').read_bytes(),original)
            graph = json.loads((root/'graph.json').read_text(encoding='utf-8'))
            self.assertTrue(any('原调用没有完整返回' in item for item in graph['issues']))
            self.assertIn('原调用没有完整返回',(root/'index.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
