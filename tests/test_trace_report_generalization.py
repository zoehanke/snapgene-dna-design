"""Independent report contracts, including contradictions absent from the demo."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from evidence_trace.recorder import Recorder
from evidence_trace.process import organize
from evidence_trace.projection import build_facts
from evidence_trace.report import markdown

ROOT = SKILL_ROOT


class ReportGeneralizationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env = patch.dict(os.environ, SNAPGENE_TRACE_CONFIG=str(self.root/'config.json'))
        env.start()
        self.addCleanup(env.stop)
        self.r = Recorder(self.root/'trace')
        self.r.ingest({'nodes': [
            {'id':'R', 'kind':'requirement', 'text':'比较两种设计的依据'},
            {'id':'S', 'kind':'source', 'title':'同一个来源', 'source_type':'paper'},
            {'id':'E1', 'kind':'statement', 'text':'观察甲', 'source_id':'S'},
            {'id':'E2', 'kind':'statement', 'text':'观察乙', 'source_id':'S'},
            {'id':'C1', 'kind':'claim', 'text':'判断甲', 'context':{'host':'host-A'}},
            {'id':'C2', 'kind':'claim', 'text':'判断乙'},
            {'id':'D1', 'kind':'decision', 'text':'选择甲', 'claim_ids':['C1'], 'responds_to':['R'], 'decision_actor':'ai', 'decision_source':{'reference':'assistant-message'}},
            {'id':'D2', 'kind':'decision', 'text':'选择乙', 'claim_ids':['C2'], 'responds_to':['R'], 'decision_actor':'user', 'decision_source':{'reference':'user-message'}}]})
        self.r.link({'statement_id':'E1', 'claim_id':'C1', 'relation':'support'})
        self.r.link({'statement_id':'E2', 'claim_id':'C2', 'relation':'oppose'})

    def test_failed_check_and_opposing_evidence_reach_the_actual_report(self):
        self.r.run_id = 'test-run'
        self.r.append('run_started', {'route':'test','context_refs':self.r.select_context(),
                                      'decision_refs':['D1@1','D2@1'], 'event_count_at_start':len(self.r.events)})
        event = self.r.append('stage_completed', {'stage':'validate', 'result':{'goal_valid':False}})
        self.r.record({'id':'V', 'kind':'validation', 'check':'goal_valid', 'result':False,
                       'result_event_ref':event['event_id']},runtime=True)
        self.r.append('run_finished', {'status':'failed'})
        g = self.r.render()
        self.assertTrue(any(f['category']=='program_check' for f in g['findings']))
        self.assertTrue(any(x['category']=='program_check' for x in g['report']['review']))
        self.assertTrue(any(x['category']=='evidence_conflict' for x in g['report']['review']))
        self.assertIn('反对', markdown(g['report']).split('## 需要处理')[1])

    def test_background_choice_does_not_donate_its_evidence_to_subject(self):
        facts = build_facts(self.r.events)
        packet = {'schema_version':'trace-organization-v1', 'id':'ORG',
                  'basis':{k:facts['snapshot'][k] for k in ('trace_id','through_sequence')},
                  'design_process':{'stages':[{'id':'compare','title':'比较','purpose':'比较依据',
                       'step_ids':['one','two'],'source_refs':['R@1']}],
                       'steps':{'one':{'kind':'choice','content':'选择甲','subject_ref':'D1@1','source_refs':['D1@1','D2@1']},
                                'two':{'kind':'choice','content':'选择乙','subject_ref':'D2@1','source_refs':['D2@1']}},
                       'relations':[],'paths':[],'unresolved':[],'detail_refs':[]}}
        organize(self.r, packet)
        report = self.r.render()['report']
        one,two = report['steps']
        self.assertEqual([e['statement'] for e in one['evidence']], ['观察甲'])
        self.assertEqual([e['statement'] for e in two['evidence']], ['观察乙'])
        self.assertEqual([e['relation'] for e in report['sources']['D1@1']['evidence']], ['support'])
        self.assertEqual([e['relation'] for e in report['sources']['D2@1']['evidence']], ['oppose'])
        shared = report['sources']['S@1']['evidence']
        self.assertEqual({(e['decision_ref'],e['relation'],e['claim']) for e in shared},
                         {('D1@1','support','判断甲'),('D2@1','oppose','判断乙')})
        # Excluding a background choice from the body must not erase its details.
        packet['basis'] = {k:build_facts(self.r.events)['snapshot'][k] for k in ('trace_id','through_sequence')}
        del packet['design_process']['steps']['two']
        packet['design_process']['stages'][0]['step_ids'] = ['one']
        packet['design_process']['detail_refs'] = ['D2@1','C2@1','E2@1']
        organize(self.r, packet)
        report = self.r.render()['report']
        self.assertEqual(len(report['steps']), 1)
        self.assertEqual([e['relation'] for e in report['sources']['D2@1']['evidence']], ['oppose'])
        self.assertEqual(len(report['sources']['S@1']['evidence']), 2)

    def test_change_values_and_actions_remain_readable_without_json(self):
        self.r.record({'id':'C1','kind':'claim','text':'判断甲','context':{'host':'host-B'}})
        report = self.r.render()['report']
        self.assertTrue(report['change_details'])
        body = markdown(report)
        self.assertIn('host-A',body)
        self.assertIn('host-B',body)
        self.assertIn('重新判断',body)
        self.r.record({'id':'C1','kind':'claim','text':'判断甲','context':{'host':'host-B','temperature':None}})
        self.r.record({'id':'C1','kind':'claim','text':'判断甲','context':{'host':'host-B','temperature':{'value':30,'unit':'C'}}})
        report = self.r.render()['report']
        changes = report['change_details']
        self.assertTrue(any(c['before']=='未提供此条件' and c['after']=='明确留空' for c in changes))
        self.assertTrue(any(c['before']=='明确留空' and c['after']=='30 C' for c in changes))

    def test_verified_locator_survives_and_render_is_stable_across_processes(self):
        self.r.record({'id':'verified', 'kind':'source', 'title':'独立核实来源', 'source_type':'paper',
                       'verification_status':'verified', 'verification':{
                           'method':'manual','scope':'identity','verifier':'researcher',
                           'checked_at':'2026-09-20','locator':'https://example.org/verified'}})
        report = self.r.render()['report']
        self.assertEqual(report['sources']['verified@1']['links'][0]['href'], 'https://example.org/verified')
        self.assertIn('https://example.org/verified', markdown(report))
        outputs=[]
        for seed in ('1','42'):
            p=subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'scripts/trace_design.py'),
                              'render','--trace-dir',str(self.r.directory)],
                             env=dict(os.environ,PYTHONHASHSEED=seed),capture_output=True,
                             encoding='utf-8',errors='replace')
            self.assertEqual(p.returncode,0,p.stderr)
            outputs.append((self.r.directory/'index.html').read_bytes())
        self.assertEqual(*outputs)


if __name__=='__main__': unittest.main()
