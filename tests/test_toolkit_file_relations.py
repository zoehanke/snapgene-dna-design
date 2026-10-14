"""Real file operations and Toolkit CLI; hashes/sequence expectations independent."""
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from repository_paths import PROJECT_ROOT
sys.path.insert(0,str(PROJECT_ROOT/'genome-revival-toolkit'))
from evidence_trace.runtime import traced_run, observe_files
from evidence_trace.recorder import Recorder, load_events
from evidence_trace.process import assemble
from revival.reporting import _workflow_packet
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ToolkitFileRelationTests(unittest.TestCase):
    def test_real_file_equality_renamed_input_and_changed_input_counterexample(self):
        for changed in (False,True):
            with self.subTest(changed=changed),tempfile.TemporaryDirectory(prefix='关系-') as temp:
                root=Path(temp); config=root/'settings.json'
                config.write_text('{"trace_level":"full"}',encoding='utf-8')
                def writer(path,content):
                    count=path.write_text(content,encoding='utf-8')
                    return {'paths':[str(path)],'write_receipts':[{'path':str(path),'sha256':sha(path),'characters_written':count}]}
                @traced_run('genome-revival-toolkit')
                def flow(out_dir):
                    original=out_dir/'first.tsv'; incoming=out_dir/'renamed.tsv'
                    observe_files('source.export',writer,args=(original,'independent exact bytes'),
                        output_paths=lambda r:r['paths'],output_directories=[out_dir])
                    shutil.copyfile(original,incoming)
                    if changed:
                        incoming.write_text('different bytes',encoding='utf-8')
                    observe_files('toolkit.export',writer,args=(out_dir/'second.tsv',incoming.read_text(encoding='utf-8')+' result'),
                        input_paths=[incoming],output_paths=lambda r:r['paths'],output_directories=[out_dir])
                with patch.dict(os.environ,{'SNAPGENE_TRACE_CONFIG':str(config)}):
                    flow(root,trace_dir=root/'trace')
                graph=assemble(load_events(root/'trace')[0])
                packet=_workflow_packet(graph)
                links=packet['design_process']['relations']
                self.assertEqual(len(links),0 if changed else 1)
                if links:
                    self.assertEqual(links[0]['kind'],'grouped_with')
                    self.assertTrue(links[0]['fact_relation_ids'])
                    self.assertIn('程序验证',links[0]['meaning'])
                    facts={f['id']:f for f in graph['fact_relations']}
                    self.assertTrue(all(facts[i]['kind']=='input_reference' for i in links[0]['fact_relation_ids']))

    def test_late_artifact_record_uses_observed_producer_event_not_journal_order(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); file=root/'result.tsv'; file.write_text('actual bytes',encoding='utf-8')
            rec=Recorder(root/'trace'); rec.run_id='one-run'
            rec.append('run_started',{'route':'toolkit','context_refs':[],'decision_refs':[],'event_count_at_start':0})
            produced=rec.append('stage_completed',{'stage':'export.first','result':{}})
            incoming=rec.append('stage_started',{'stage':'toolkit.export','input_files':[{'path':str(file),'sha256':sha(file)}]})
            rec.append('file_operation_completed',{'stage':'toolkit.export','stage_ref':incoming['event_id'],'result':{}})
            rec.record({'id':'late-file','kind':'artifact','path':str(file),'sha256':sha(file),'role':'supporting-file',
                'generation_observation':'created','result_event_ref':produced['event_id']},runtime=True)
            rec.append('run_finished',{'status':'finished'})
            graph=assemble(rec.events); packet=_workflow_packet(graph)
            self.assertEqual(len(packet['design_process']['relations']),1)
            self.assertTrue(packet['design_process']['relations'][0]['fact_relation_ids'])

    def test_real_multistep_construct_cli_has_supported_relations_and_exact_donor(self):
        with tempfile.TemporaryDirectory(prefix='kit-实际-') as temp:
            root=Path(temp); rng=random.Random(681120)
            target=''.join(rng.choices('ACGT',k=2000)); cargo=''.join(rng.choices('ACGT',k=900))
            expected=target[600:800]+cargo[200:440]+target[810:1010]
            refs={}
            for name,sequence in (('target',target),('cargo',cargo),('donor',expected)):
                path=root/(name+'.gb')
                with path.open('w',encoding='utf-8') as handle:
                    SeqIO.write(SeqRecord(Seq(sequence),id=name,annotations={'molecule_type':'DNA','topology':'linear'}),handle,'genbank')
                refs[name]={'path':str(path),'source':'independently constructed synthetic template'}
            context=root/'context.json'; context.write_text(json.dumps({'references':refs}),encoding='utf-8')
            request=root/'request.json'; request.write_text(json.dumps({'original_request':'Prepare this explicit donor and verify both boundaries.',
                'method':'integration_donor','target_reference':'target','cargo_reference':'cargo',
                'target_interval':{'start0':800,'end0':810},'cargo_interval':{'start0':200,'end0':440},'arm_length':200,
                'preparation_method':'pcr','donor_template_reference':'donor','donor_interval':{'start0':0,'end0':640}}),encoding='utf-8')
            config=root/'settings.json'; config.write_text('{"trace_level":"full"}',encoding='utf-8')
            out=root/'output'; trace=root/'trace'
            run=subprocess.run([sys.executable,'-X','utf8','-B',str(PROJECT_ROOT/'genome-revival-toolkit/scripts/run_toolkit.py'),
                'construct','--context',str(context),'--request',str(request),'--out-dir',str(out),'--trace-dir',str(trace)],
                env={**os.environ,'SNAPGENE_TRACE_CONFIG':str(config)},capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            result=json.loads((out/'result.json').read_text(encoding='utf-8'))
            self.assertEqual(result['status'],'delivered')
            with (Path(result['delivery']['directory'])/'construct.gb').open(encoding='utf-8') as handle:
                self.assertEqual(str(SeqIO.read(handle,'genbank').seq),expected)
            graph=json.loads((trace/'graph.json').read_text(encoding='utf-8'))
            links=graph['design_process']['relations']
            self.assertGreater(len(links),0)
            self.assertTrue(all(link['fact_relation_ids'] for link in links))
            self.assertIn('程序验证',(trace/'report.md').read_text(encoding='utf-8'))


if __name__=='__main__':
    unittest.main()
