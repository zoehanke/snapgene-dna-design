
from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from evidence_trace.recorder import Recorder, load_events
from evidence_trace.intake import record_handoff
from evidence_trace.storage import machine_export, expand_machine
from evidence_trace.process import organize
from evidence_trace.details import readable_details
from test_evidence_trace_process import packet

ROOT = SKILL_ROOT


class UsabilityTests(unittest.TestCase):
    def test_actual_guardrail_table_is_readable_without_expanding_raw_result(self):
        details = readable_details({'V@1': {'kind': 'validation', 'check': 'biological_sanity',
            'result': False, 'details': {'guardrail_status_table': {
                'BIO-01-FRAME': {'title':'Reading frame', 'status':'FAIL', 'details':'premature stop'},
                'BIO-03-ENZYME': {'title':'Restriction sites', 'status':'N/A', 'details':'not requested'}}}}})
        fields = details['V@1']['fields']
        self.assertTrue(any('premature stop' in f['text'] for f in fields))
        self.assertFalse(any('source_refs' == f['label'] for f in fields))

    def test_readable_file_gap_and_lossless_compact_export(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SNAPGENE_TRACE_CONFIG': tmp+'/config.json'}):
            root = Path(tmp)
            r = Recorder(root/'trace')
            r.record({'id':'R', 'kind':'requirement', 'text':'核对现有供体'})
            r.run_id = 'run'
            r.append('run_started', {'route':'custom'})
            # Large structured input, not DNA. Exact payload must survive storage.
            original = {'rows':[{'description':'record '*100, 'value':i} for i in range(800)]}
            event = r.append('stage_started', {'stage':'inspect', 'input':original})
            r.append('stage_completed', {'stage':'inspect', 'stage_ref':event['event_id'], 'result':{'message':'实际检查完成'}})
            r.append('run_finished', {'status':'finished'})
            file = root/'已存在.txt'; file.write_text('actual', encoding='utf-8')
            record_handoff(r, [{'path':str(file), 'purpose':'用户原有材料'}])
            g = r.render(); report = g['report']
            self.assertEqual(report['artifacts'][0]['name'], file.name)
            self.assertEqual(len(report['recording_gaps']), 1)
            self.assertFalse(report['review'])
            detail = report['sources'][report['artifacts'][0]['ref']]
            self.assertTrue(detail['links'])
            self.assertTrue(any(f['text']=='用户原有材料' for f in detail['fields']))
            self.assertNotIn('data', detail)
            exported = machine_export(g)
            restored = expand_machine(exported)
            self.assertEqual(restored, g)
            self.assertEqual(restored['source_records'][event['event_id']]['payload']['input'], original)
            html = (root/'trace/index.html').read_text(encoding='utf-8')
            embedded = html.split('<script id="trace-data" type="application/json">')[1].split('</script>')[0]
            self.assertEqual(set(json.loads(embedded)), {'report'})
            self.assertNotIn('"rows":', embedded)
            self.assertLess(len(html), len(json.dumps(original)))

    def test_explicit_subject_cannot_borrow_unrelated_record_type(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'SNAPGENE_TRACE_CONFIG': tmp+'/config.json'}):
            r=Recorder(Path(tmp)/'trace')
            r.record({'id':'R','kind':'requirement','text':'核对材料'})
            r.record({'id':'S','kind':'source','title':'原材料','source_type':'user-material'})
            p=packet(r)
            p['design_process']['steps']['requirement'].update(source_refs=['R@1','S@1'], subject_ref='S@1')
            with self.assertRaisesRegex(ValueError, 'Requirement step'):
                organize(r,p)

    def test_custom_command_modes_failure_and_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            script=root/'生成.py'
            script.write_text("from pathlib import Path\nimport sys\np=Path(sys.argv[1]);p.write_text('真实结果',encoding='utf-8')\nif len(sys.argv)>2: raise RuntimeError('expected failure')\n",encoding='utf-8')
            env=dict(os.environ, SNAPGENE_TRACE_CONFIG=str(root/'config.json'))
            for mode in ('off','observed','full'):
                (root/'config.json').write_text(json.dumps({'trace_level':mode}),encoding='utf-8')
                out=root/(mode+'.txt');trace=root/mode
                cmd=[sys.executable,'-X','utf8','-B',str(ROOT/'scripts/trace_run.py'), '--trace-dir',str(trace),
                     '--input-file',str(script),'--output-file',str(out),'--role','document','--',sys.executable,str(script),str(out)]
                run=subprocess.run(cmd,env=env,capture_output=True,encoding='utf-8',errors='replace')
                self.assertEqual(run.returncode,0,run.stderr)
                self.assertEqual(out.read_text(encoding='utf-8'),'真实结果')
                if mode=='off': self.assertFalse(trace.exists());continue
                r=Recorder(trace)
                self.assertEqual(record_handoff(r,[{'path':str(out)}])['files'][0]['status'],'linked')
                self.assertFalse([e for e in r.events if e['event_type']=='node_recorded' and e['payload']['kind']=='validation'])
                run=subprocess.run(cmd+['fail'],env=env,capture_output=True,encoding='utf-8',errors='replace')
                self.assertNotEqual(run.returncode,0)
                events,_=load_events(trace)
                self.assertTrue(any(e['event_type']=='file_operation_failed' for e in events))


if __name__=='__main__': unittest.main()
