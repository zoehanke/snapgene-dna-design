"""Independent supplied predictions/observations through the real Evidence CLI."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from repository_paths import PROJECT_ROOT


class KitDataChainTests(unittest.TestCase):
    def test_complete_public_story_is_independently_checked_and_stays_offline(self):
        from test_kit_network_defaults import LAUNCHER
        examples=PROJECT_ROOT/'genome-revival-toolkit/examples/data-chain'
        spec=importlib.util.spec_from_file_location('data_chain_story_under_test',examples/'run_story.py')
        module=importlib.util.module_from_spec(spec)
        sys.path.insert(0,str(examples))
        try:spec.loader.exec_module(module)
        finally:sys.path.remove(str(examples))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);launcher=root/'blocked.py';launcher.write_text(LAUNCHER,encoding='utf-8')
            report=module.run(root/'story',launcher=launcher)
            self.assertEqual(report['status'],'PASSED')
            self.assertEqual(report['donor_bp'],640)
            self.assertEqual(report['edited_reference_bp'],2230)
            self.assertEqual(report['evidence'],{'matching':'SUPPORTED','contradicted':'CONTRADICTED','counts-only':'INSUFFICIENT'})
            counters=[json.loads(path.read_text(encoding='utf-8')) for path in (root/'story').glob('*-network.json')]
            self.assertEqual(len(counters),14)
            self.assertEqual(sum(row['connection_attempts'] for row in counters),0)
            from evidence_trace.recorder import load_events
            from evidence_trace.process import assemble
            graph=assemble(load_events(root/'story/chain-trace')[0])
            records=graph['source_records']; links=set()
            for fact in graph['fact_relations']:
                if fact.get('kind')!='input_reference' or fact.get('verification_method')!='sha256_equality':continue
                artifact=records[fact['from']]; consumer=records[fact['to']]
                producer=records.get(artifact.get('result_event_ref'),{})
                pair=(producer.get('payload',{}).get('stage'),consumer.get('payload',{}).get('stage'))
                if pair[1] not in ('identity.import_construct_handoff','evidence.read_expected_results'):continue
                actual_hash=hashlib.sha256(Path(artifact['path']).read_bytes()).hexdigest()
                self.assertEqual(actual_hash,artifact['sha256'])
                self.assertTrue(any(row['sha256']==actual_hash for row in consumer['payload']['input_files']))
                links.add(pair)
            self.assertIn(('construct.identity_handoff','identity.import_construct_handoff'),links)
            self.assertIn(('toolkit.export','evidence.read_expected_results'),links)

    def test_no_product_prediction_uses_reported_controls_and_quality(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);reference=root/'reference.gb'
            with reference.open('w',encoding='utf-8') as handle:
                SeqIO.write(SeqRecord(Seq('ACGT'*40),id='reference',annotations={'molecule_type':'DNA','topology':'linear'}),handle,'genbank')
            (root/'context.json').write_text(json.dumps({'references':{'local':{'path':str(reference)}}}),encoding='utf-8')
            base={'schema_version':'identity-expected-results-v1','references':{'local':{'file_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),
                'record_id':'reference','region':None,'topology':'linear'}},'rows':[{'assay_id':'a','reference_id':'local',
                'expected':'NO_EXACT_PRODUCT','size_bp':None,'primer_quality_status':'PASSED'}]}
            table=root/'no-product.json';table.write_text(json.dumps(base),encoding='utf-8')
            for label,result,size,wanted in [('absent','negative',None,'SUPPORTED'),('unexpected','positive',137,'CONTRADICTED')]:
                value=self.execute(root,label,{'original_request':'Compare a synthetic no-product model.',
                    'expected_results_file':str(table),'genotype_results':[{'sample_id':'s','reference_id':'local',
                        'assay_id':'a','result':result,'control_status':'passed','observed_band_bp':size}]})
                self.assertEqual(value['expected_result_comparison']['status'],wanted)
            base['rows'][0]['primer_quality_status']='FAILED'
            unavailable=root/'failed-quality.json';unavailable.write_text(json.dumps(base),encoding='utf-8')
            value=self.execute(root,'quality',{'original_request':'Do not support an unusable synthetic prediction.',
                'expected_results_file':str(unavailable),'genotype_results':[{'sample_id':'s','reference_id':'local',
                    'assay_id':'a','result':'negative','control_status':'passed'}]})
            self.assertEqual(value['expected_result_comparison']['status'],'INSUFFICIENT')

    def test_wrong_table_format_or_reference_version_is_explicitly_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);record=root/'reference.gb'
            with record.open('w',encoding='utf-8') as handle:
                SeqIO.write(SeqRecord(Seq('ACGT'*40),id='reference',annotations={'molecule_type':'DNA'}),handle,'genbank')
            (root/'context.json').write_text(json.dumps({'references':{'local':{'path':str(record)}}}),encoding='utf-8')
            for name,table,message in [('format',{'schema_version':'unsupported','rows':[],'references':{}},'Unsupported Identity'),
                ('version',{'schema_version':'identity-expected-results-v1','rows':[],
                    'references':{'local':{'file_sha256':'0'*64,'record_id':'reference','region':None}}},'reference version changed')]:
                path=root/(name+'-table.json');path.write_text(json.dumps(table),encoding='utf-8')
                response=self.execute(root,name,{'original_request':'Reject a deliberately invalid synthetic prediction.',
                    'expected_results_file':str(path)},expected_exit=2)
                self.assertIn(message,response['error'])

    def test_prediction_table_is_compared_with_reported_bands_and_missing_tests(self):
        with tempfile.TemporaryDirectory(prefix='预测-') as temp:
            root=Path(temp); reference=root/'reference.gb'
            record=SeqRecord(Seq('ACGT'*80),id='synthetic-reference',annotations={'molecule_type':'DNA','topology':'linear'})
            with reference.open('w',encoding='utf-8') as handle:SeqIO.write(record,handle,'genbank')
            (root/'context.json').write_text(json.dumps({'references':{'local':{'path':str(reference)}}}),encoding='utf-8')
            table={'schema_version':'identity-expected-results-v1',
                   'scope':'Synthetic declared prediction, not a measured experiment.',
                   'references':{'local':{'file_sha256':hashlib.sha256(reference.read_bytes()).hexdigest(),
                                        'record_id':'synthetic-reference','region':None,'topology':'linear'}},
                   'rows':[{'assay_id':'junction','reference_id':'local','expected':'AMPLICON',
                            'size_bp':137,'primer_quality_status':'PASSED'}]}
            table_path=root/'expected.json';table_path.write_text(json.dumps(table),encoding='utf-8')
            cases=[('matching',137,'positive','passed','SUPPORTED'),
                   ('wrong-size',154,'positive','passed','CONTRADICTED'),
                   ('missing-band',None,'negative','passed','CONTRADICTED'),
                   ('unknown-control',137,'positive','unknown','INSUFFICIENT'),
                   ('not-tested',None,'not_tested','unknown','NOT_TESTED')]
            for name,size,result,control,expected in cases:
                with self.subTest(name=name):
                    request={'original_request':'Compare synthetic supplied predictions and reported band records.',
                             'expected_results_file':str(table_path),
                             'genotype_results':[{'sample_id':'sample','reference_id':'local','assay_id':'junction',
                                'result':result,'control_status':control,'observed_band_bp':size}]}
                    detail=self.execute(root,name,request)
                    self.assertEqual(detail['expected_result_comparison']['status'],expected)
                    self.assertEqual(detail['genotype_results'][0]['assessment'],expected)
                    self.assertTrue(detail['expected_result_comparison']['rows'][0]['reason'])
            counts={'original_request':'Only synthetic colony counts, no genotype evidence.',
                    'expected_results_file':str(table_path),
                    'observations':[{'id':'c','group':'experiment','colonies':12}]}
            detail=self.execute(root,'counts-only',counts)
            self.assertEqual(detail['expected_result_comparison']['status'],'INSUFFICIENT')
            self.assertIn('junction',detail['expected_result_comparison']['not_tested_assays'])

    def execute(self,root,label,request,expected_exit=0):
        path=root/(label+'.json');path.write_text(json.dumps(request),encoding='utf-8')
        config=root/'trace.json';config.write_text('{"trace_level":"observed"}',encoding='utf-8')
        out=root/label
        process=subprocess.run([sys.executable,'-X','utf8','-B',str(PROJECT_ROOT/'genome-revival-toolkit/scripts/run_toolkit.py'),
             'evidence','--context',str(root/'context.json'),'--request',str(path),'--out-dir',str(out),'--language','en'],
             capture_output=True,encoding='utf-8',env=dict(os.environ,SNAPGENE_TRACE_CONFIG=str(config)))
        self.assertEqual(process.returncode,expected_exit,process.stdout+process.stderr)
        if expected_exit:return json.loads(process.stdout)
        return json.loads((out/'result.json').read_text(encoding='utf-8'))


if __name__=='__main__':unittest.main()
