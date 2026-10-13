"""User-request continuity, using source-derived expectations and public entries."""
from repository_paths import SKILL_ROOT
import random
import tempfile
import unittest
import json
import os
import subprocess
import sys
from pathlib import Path
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation
from core.workflow import run_step
from core.workflow_validation import validate_candidate


class GoalContinuityTests(unittest.TestCase):
    def setUp(self):
        self.sequence=''.join(random.Random(93612).choices('ACGT',k=240))
        self.source=SeqRecord(Seq(self.sequence),id='original',annotations={'molecule_type':'DNA','topology':'linear'})
        self.source.features=[SeqFeature(FeatureLocation(160,180,strand=1),type='misc_feature',qualifiers={'label':['retained_module']})]
        self.sources={'original':self.source}

    def test_local_pass_does_not_certify_unmapped_original_request(self):
        step=run_step('extract_subsequence',{'source':'$original','start':0,'end':100},sources=self.sources)
        report=validate_candidate({'topology':'linear','original_request':'Keep the retained module from the supplied original material.'},
            self.sources,[step],step.result.only_product(),required_scopes=['sequence_model','user_goal'],result_kind='component')
        self.assertEqual(report['scope_results']['user_goal']['status'],'PASSED')
        self.assertEqual(report.get('task_completion',{}).get('status'),'UNVERIFIED')
        self.assertFalse(report['task_completion']['original_task_verified'])

    def test_step_context_is_inherited_and_cannot_be_silently_replaced(self):
        requirements={'original_request':'Keep retained_module.','topology':'linear',
            'expected_components':[{'name':'retained_module','source_id':'original'}]}
        first=run_step('extract_subsequence',{'source':'$original','start':0,'end':210},step_id='first',
                       sources=self.sources,requirements=requirements)
        self.assertIsNone(first.error)
        second=run_step('extract_subsequence',{'source':'$first','start':0,'end':100},step_id='second',
                        sources=self.sources,previous=[first])
        self.assertEqual(second.to_dict()['requirements'],requirements)
        report=validate_candidate({'topology':'linear'},self.sources,[first,second],second.result.only_product(),
            required_scopes=['sequence_model','user_goal'],result_kind='component')
        self.assertEqual(report['scope_results']['user_goal']['status'],'FAILED')
        self.assertIn('REQUIRED_COMPONENT_MISSING',str(report['errors']))

    def test_recipe_accepts_request_context_without_treating_it_as_method_argument(self):
        from scripts.run_recipe import run_recipe_cli
        with tempfile.TemporaryDirectory() as directory:
            result=run_recipe_cli('protein_tagging',{'target_cds_seq_or_file':'ATGGCTTAA','tag_name_or_seq':'6xHis',
                'original_request':'Add an N-terminal histidine tag.'},directory)
            self.assertEqual(result['requirements']['original_request'],'Add an N-terminal histidine tag.')
            self.assertEqual(result['task_completion']['status'],'UNVERIFIED')

    def test_declared_goal_items_distinguish_pass_fail_missed_and_unchecked(self):
        from core.requirements import goal_coverage
        request={'topology':'linear','expected_components':[{'name':'retained_module','source_id':'original'}],
            'goal_items':[{'id':'shape','text':'Linear material','constraint_refs':['/topology']},
                          {'id':'module','text':'Keep the source module','constraint_refs':['/expected_components/0']},
                          {'id':'unmapped','text':'Additional requirement not converted to a check'}]}
        before=goal_coverage(request,[])
        self.assertEqual(before['checked_fields'],[])
        self.assertEqual([i['status'] for i in before['goal_items']],['UNCHECKED','UNCHECKED','MISSED'])
        step=run_step('extract_subsequence',{'source':'$original','start':0,'end':100},sources=self.sources,requirements=request)
        self.assertEqual([i['status'] for i in step.goal_coverage['goal_items']],['PASSED','FAILED','MISSED'])
        self.assertEqual(step.status,'completed')
        self.assertEqual(step.task_completion['status'],'IN_PROGRESS')

    def test_two_valid_routes_and_changed_intermediate_keep_same_goal(self):
        request={'topology':'linear','expected_components':[{'name':'retained_module','source_id':'original'}],
            'goal_items':[{'id':'keep','text':'Keep the supplied module','constraint_refs':['/expected_components/0']}]}
        for end in (200,220):
            first=run_step('extract_subsequence',{'source':'$original','start':0,'end':end},step_id='first',sources=self.sources,requirements=request)
            second=run_step('extract_subsequence',{'source':'$first','start':10,'end':190},step_id='second',sources=self.sources,previous=[first])
            self.assertEqual(str(second.result.only_product().seq),self.sequence[10:190])
            report=validate_candidate({},self.sources,[first,second],second.result.only_product(),
                required_scopes=['sequence_model','user_goal'],result_kind='component')
            self.assertEqual(report['overall'],'verified',report['errors'])
            self.assertEqual(report['goal_coverage']['goal_items'][0]['status'],'PASSED')
            self.assertEqual(report['goal_coverage']['subject_version'],second.result.only_product().record_version)
            self.assertEqual(report['task_completion']['status'],'DECLARED_GOALS_PASSED')

    def test_goal_cannot_disappear_or_change_during_resume(self):
        request={'topology':'linear','original_request':'Retain the original source module.'}
        first=run_step('extract_subsequence',{'source':'$original','start':0,'end':220},step_id='first',sources=self.sources,requirements=request)
        changed=run_step('extract_subsequence',{'source':'$first','start':0,'end':100},step_id='second',sources=self.sources,
                         previous=[first],requirements={'original_request':'Remove the source module.'})
        self.assertEqual(changed.error['error_code'],'GOAL_CONTEXT_CONFLICT')
        from core.errors import ValidationError
        with self.assertRaises(ValidationError) as conflict:
            validate_candidate({'original_request':'Original text','goal_items':[{'id':'x','text':'Keep it','source_quote':'invented quote'}]},
                self.sources,[first],first.result.only_product())
        self.assertEqual(conflict.exception.error_code,'GOAL_CONTEXT_CONFLICT')
        with self.assertRaisesRegex(ValidationError,'source_quote'):
            validate_candidate({'original_request':request['original_request'],'goal_items':[{'id':'x','text':'Keep it','source_quote':'invented quote'}]},
                self.sources,[first],first.result.only_product())

    def test_analysis_without_full_goal_is_still_usable(self):
        result=run_step('calc_primer_tm',{'primer_seq':'ACGTTGCAACCGTTAAGCGT'})
        self.assertEqual(result.status,'completed')
        self.assertEqual(result.result.products,[])
        self.assertEqual(result.task_completion['status'],'NOT_REQUESTED')

    def test_malformed_empty_context_is_not_silently_accepted(self):
        from core.requirements import inherit_requirements
        from core.errors import ValidationError
        for value in ([],False,'',0):
            with self.subTest(value=value),self.assertRaises(ValidationError):
                inherit_requirements(requirements=value)

    def test_missing_check_remains_unverified_instead_of_becoming_a_failed_fact(self):
        from core.requirements import completion_report,goal_coverage
        coverage=goal_coverage({'goal_items':[{'id':'future','text':'Future use must work'}]},[])
        self.assertEqual(coverage['goal_items'][0]['status'],'MISSED')
        result=completion_report(coverage,local_success=False,scope_results={'user_goal':{'status':'INCOMPLETE'}})
        self.assertEqual(result['status'],'UNVERIFIED')

    def test_new_goal_items_can_be_bound_later_without_rewriting_original(self):
        original={'original_request':'Keep retained_module.','goal_items':[{'id':'keep','text':'Keep retained_module.',
                   'source_quote':'Keep retained_module.'}]}
        first=run_step('extract_subsequence',{'source':'$original','start':0,'end':220},step_id='first',sources=self.sources,requirements=original)
        bound={'expected_components':[{'name':'retained_module','source_id':'original'}],
               'goal_items':[{'id':'keep','text':'Keep retained_module.','source_quote':'Keep retained_module.',
                              'constraint_refs':['/expected_components/0']}]}
        second=run_step('extract_subsequence',{'source':'$first','start':0,'end':200},step_id='second',sources=self.sources,previous=[first],requirements=bound)
        self.assertIsNone(second.error)
        self.assertEqual(second.goal_coverage['goal_items'][0]['status'],'PASSED')
        self.assertEqual(first.goal_coverage['goal_items'][0]['status'],'MISSED')

    def test_changed_candidate_annotations_and_saved_files_do_not_reuse_old_acceptance(self):
        import copy
        from core.tools import export_snapgene
        from core.workflow_delivery import deliver_result
        from core.errors import GateRejected
        request={'topology':'linear','expected_components':[{'name':'retained_module','source_id':'original'}]}
        step=run_step('extract_subsequence',{'source':'$original','start':0,'end':210},sources=self.sources,requirements=request)
        candidate=step.result.only_product()
        changed=copy.deepcopy(candidate)
        changed.features[0].qualifiers['label']=['different_annotation']
        report=validate_candidate({},self.sources,[step],changed,result_kind='component',required_scopes=['sequence_model','user_goal'])
        self.assertEqual(report['scope_results']['sequence_model']['status'],'FAILED')
        with tempfile.TemporaryDirectory() as directory:
            files=export_snapgene(candidate,Path(directory)/'checked').analysis
            report=validate_candidate({},self.sources,[step],candidate,result_kind='component',
                files={'construct.gb':files['gb_file']})
            self.assertEqual(report['overall'],'verified',report['errors'])
            Path(files['gb_file']).write_text('modified after acceptance',encoding='utf-8')
            with self.assertRaisesRegex(GateRejected,'Checked file changed'):
                deliver_result({},self.sources,[step],candidate,Path(directory)/'delivery',result_kind='component',validation=report)

    def test_real_clis_inherit_goals_and_separate_delivery_from_original_task(self):
        from core.tools import export_snapgene
        sequence='ACGTTGCAACCGTTAAGCGT'
        source=SeqRecord(Seq(sequence),id='original',annotations={'molecule_type':'DNA','topology':'linear'})
        original='保留给定来源序列，交付线性 DNA。'
        request={'original_request':original,'topology':'linear','expected_sequence':sequence,
                 'goal_items':[{'id':'retain','text':'保留给定来源序列','source_quote':'保留给定来源序列',
                                'constraint_refs':['/expected_sequence']}]}
        with tempfile.TemporaryDirectory(prefix='目标 连续性 ') as directory:
            base=Path(directory)
            config=base/'trace.json';config.write_text('{"trace_level":"off"}',encoding='utf-8')
            env={**os.environ,'SNAPGENE_TRACE_CONFIG':str(config),'PYTHONPATH':''}
            source_path=export_snapgene(source,base/'inputs').analysis['gb_file']
            def invoke(script,name,data,flags):
                inp=base/(name+'.json');inp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
                run=subprocess.run([sys.executable,'-X','utf8','-B',str(SKILL_ROOT/'scripts'/script),*flags(str(inp)),
                                    '--out-dir',str(base/name)],cwd=base,env=env,capture_output=True,text=True,
                                    encoding='utf-8',errors='replace',timeout=120)
                self.assertEqual(run.returncode,0,run.stdout[-1500:]+run.stderr[-500:])
                return json.loads(run.stdout)
            first=invoke('run_step.py','first',{'step_id':'duplex','method':'anneal_oligos',
                'params':{'top_oligo':sequence,'bottom_oligo':str(Seq(sequence).reverse_complement())},
                'sources':{'original':source_path},'requirements':request},lambda p:['--input',p])
            second=invoke('run_step.py','second',{'step_id':'copy','method':'strip_terminal_codons',
                'params':{'cds_seq':'$duplex'},'history_file':first['record_file']},lambda p:['--input',p])
            history=json.loads(Path(second['record_file']).read_text(encoding='utf-8'))
            candidate=history['steps'][-1]['result']['products'][0]
            result=invoke('finalize_workflow.py','final',{'record_file':second['record_file'],'candidate':candidate},
                          lambda p:['--input',p,'--deliver','--confirmed'])
            self.assertEqual(result['status'],'delivered')
            self.assertEqual(result['task_completion']['status'],'UNVERIFIED')
            self.assertFalse(result['task_completion']['original_task_verified'])
            self.assertEqual(result['task_completion']['declared_goals_status'],'PASSED')
            actual=json.loads((Path(result['directory'])/'requirements.json').read_text(encoding='utf-8'))
            self.assertEqual(actual,request)
            pipeline={'task_id':'continuity','topology':'linear','original_request':original,'requirements':request,
                'sources':[{'source_id':'original','path':source_path}],
                'steps':[{'step_id':'duplex','tool':'anneal_oligos','params':{'top_oligo':sequence,'bottom_oligo':str(Seq(sequence).reverse_complement())}}]}
            result=invoke('run_pipeline.py','pipeline',pipeline,lambda p:['--pipeline',p,'--confirmed','--json'])
            self.assertEqual(result['status'],'delivered')
            self.assertEqual(result['task_completion']['status'],'UNVERIFIED')
            task=json.loads((base/'pipeline/task.json').read_text(encoding='utf-8'))
            # Existing TaskSession needs an explicit host; this fixture prepares DNA in vitro.
            task['host']='in-vitro DNA preparation'
            result=invoke('run_construction_task.py','task',task,lambda p:['--task',p,'--json'])
            self.assertEqual(result['status'],'delivered')
            self.assertEqual(result['task_completion']['status'],'UNVERIFIED')
            self.assertEqual(result['goal_coverage']['subject_version'],result['validation']['scope_results']['user_goal']['subject_version'])
            self.assertEqual(result['delivery']['task_completion']['status'],'UNVERIFIED')


if __name__=='__main__':unittest.main()
