"""Public report exports retain original statements, facts and JS escaping."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from repository_paths import SKILL_ROOT
from evidence_trace.recorder import Recorder
from evidence_trace.process import organize, assemble


class ReportLocalizationTests(unittest.TestCase):
    def test_public_english_export_preserves_sources_and_default_language(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); trace=root/'trace'
            config=root/'settings.json';config.write_text('{"trace_level":"observed"}',encoding='utf-8')
            recorder=Recorder(trace)
            original='用户要求：程序结果不等于实验成功。'
            recorder.record({'id':'R','kind':'requirement','text':original})
            recorder.record({'id':'D','kind':'decision','text':'Keep the original input',
                'rationale':original,'decision_actor':'ai','explanation_origin':'ai_concurrent',
                'decision_source':{'reference':'synthetic-input.json#/choice'}})
            facts=assemble(recorder.events)
            organize(recorder,{'schema_version':'trace-organization-v1','id':'language-case',
                'basis':{k:facts['snapshot'][k] for k in ('trace_id','through_sequence')},
                'design_process':{'stages':[{'id':'preservation','title':'Keep source and provenance',
                    'purpose':'Compare display languages without changing original records',
                    'step_ids':['goal','choice'],'source_refs':['R@1','D@1']}],'steps':{
                    'goal':{'kind':'requirement','content':'Preserve original input','source_refs':['R@1']},
                    'choice':{'kind':'choice','content':'Keep original input','subject_ref':'D@1','source_refs':['D@1']}},
                    'relations':[],'paths':[],'unresolved':[],'detail_refs':[]},
                'report_plan':{'profile':'research-report-v1','title':'Source-preserving language export','sections':[],
                    'diagram':{'reading_order':['goal','choice'],'relation_refs':[],'short_labels':{}}}})
            before=(trace/'events.jsonl').read_bytes()
            env={**os.environ,'SNAPGENE_TRACE_CONFIG':str(config)}
            def export(language):
                result=subprocess.run([sys.executable,'-X','utf8','-B',str(SKILL_ROOT/'scripts/trace_design.py'),
                    'render','--trace-dir',str(trace),'--language',language],env=env,capture_output=True,encoding='utf-8')
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertEqual((trace/'events.jsonl').read_bytes(),before)
                return json.loads((trace/'graph.json').read_text(encoding='utf-8'))['report']
            english=export('en')
            self.assertEqual(english['language'],'en')
            self.assertEqual([step['label'] for step in english['steps']],['User requirement','AI choice'])
            self.assertEqual(english['requirements'][0]['text'],original)
            self.assertIn(original,(trace/'details.md').read_text(encoding='utf-8'))
            self.assertIn('## Detailed records',(trace/'report.md').read_text(encoding='utf-8'))
            self.assertIn('Solid: program-verified file SHA-256 equality',(trace/'report.md').read_text(encoding='utf-8'))
            self.assertIn('Dashed: declared/structural relationship',(trace/'report.md').read_text(encoding='utf-8'))
            self.assertIn('lang="en"',(trace/'index.html').read_text(encoding='utf-8'))
            chinese=export('zh')
            self.assertEqual([step['label'] for step in chinese['steps']],['用户要求','AI 选择'])
            self.assertEqual(chinese['requirements'][0]['text'],original)
            self.assertIn('虚线：声明或结构性关系，程序未验证其含义',(trace/'report.md').read_text(encoding='utf-8'))

    def test_reader_literal_translation_keeps_html_escaping(self):
        node=shutil.which('node')
        if node is None:self.skipTest('Node.js required to execute shipped reader JavaScript')
        # Execute the actual reader initializer, not a reimplementation of h/T.
        code="""const fs=require('fs'),vm=require('vm');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const source=fs.readFileSync(process.argv[1],'utf8').split('const stepById')[0];
const document={getElementById:()=>({textContent:JSON.stringify({report:{language:'en',
ui_text:{'程序记录':'Program record'},sources:{},steps:[],default_expanded_refs:[]}})})};
const functions=vm.runInNewContext(source+'\\n({h,T})',{document});
console.log(JSON.stringify({escaped:functions.h(input.text),label:functions.T(input.label)}));"""
        result=subprocess.run([node,'-e',code,str(SKILL_ROOT/'evidence_trace/view.js')],
            input=json.dumps({'text':'&<"\'>','label':'程序记录'},ensure_ascii=False),
            capture_output=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(data['escaped'],'&amp;&lt;&quot;&#39;&gt;')
        self.assertEqual(data['label'],'Program record')


if __name__=='__main__':unittest.main()
