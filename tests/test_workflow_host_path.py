"""Independent public workflow regressions: facts, references and finish semantics."""
from repository_paths import SKILL_ROOT
import csv
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation
from core.errors import CoreError
from core.workflow import run_step
from core.workflow_validation import validate_candidate
from core.workflow_delivery import deliver_result


def source(seed=423):
    rng=random.Random(seed)
    record=SeqRecord(Seq(''.join(rng.choices('ACGT',k=360))),id='original',
                      annotations={'molecule_type':'DNA','topology':'linear'})
    record.features=[SeqFeature(FeatureLocation(70,95,strand=-1),type='misc_feature',qualifiers={'label':['kept']})]
    return record


class HostWorkflowTests(unittest.TestCase):
    def test_original_source_extension_and_changes_are_distinct(self):
        original=source(); sources={'original':original}
        first=run_step('extract_subsequence',{'source':'$original','start':0,'end':240},step_id='fragment',sources=sources)
        extended={**sources,'new_material':source(997)}
        second=run_step('extract_subsequence',{'source':'$fragment','start':0,'end':200},step_id='trimmed',sources=extended,previous=[first])
        self.assertEqual(second.status,'completed',second.error)
        self.assertEqual(str(second.result.only_product().seq),str(original.seq[:200]))
        changed=source(998)
        failure=run_step('extract_subsequence',{'source':'$fragment','start':0,'end':200},step_id='bad',sources={'original':changed},previous=[first])
        self.assertEqual(failure.error['error_code'],'SOURCE_VERSION_CHANGED')

    def test_new_source_cannot_shadow_an_actual_step_product(self):
        original=source();sources={'original':original}
        first=run_step('extract_subsequence',{'source':'$original','start':0,'end':240},step_id='fragment',sources=sources)
        second=run_step('extract_subsequence',{'source':'$fragment','start':0,'end':50},step_id='next',
                     sources={**sources,'fragment':source(1332)},previous=[first])
        self.assertEqual(second.status,'failed')
        self.assertEqual(second.error['error_code'],'INVALID_SOURCE_ID')

    def test_public_python_continuation_accepts_actual_pipeline_execution_dicts(self):
        original=source();sources={'original':original}
        first=run_step('extract_subsequence',{'source':'$original','start':0,'end':240},step_id='fragment',sources=sources)
        second=run_step('extract_subsequence',{'source':'$fragment','start':10,'end':60},step_id='next',
                        sources=sources,previous=[first.to_dict()])
        self.assertEqual(second.status,'completed',second.error)
        self.assertEqual(str(second.result.only_product().seq),str(original.seq[10:60]))

    def test_deleted_scope_cannot_authorize_a_new_construct(self):
        original=source(); sources={'input':original}
        base='A' if str(original.seq)[100]!='A' else 'C'
        edited=run_step('mutate_sequence',{'dna_seq':'$input','mutations':[{'position_0based':100,'alt_base':base}]},step_id='edited',sources=sources)
        self.assertEqual(edited.status,'completed',edited.error)
        expected=str(original.seq[:100])+base+str(original.seq[101:])
        goal={'topology':'linear','expected_sequence':expected}
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(CoreError):
                deliver_result(goal,sources,[edited],edited.result.only_product(),temp,
                    required_scopes=['sequence_model','file','user_goal'])
            # A disclosed sequence-design component remains legitimate.
            result=deliver_result(goal,sources,[edited],edited.result.only_product(),Path(temp)/'sequence_design',
                    result_kind='component',required_scopes=['sequence_model','file','user_goal'])
            self.assertEqual(result['status'],'delivered')
            self.assertEqual(result['validation']['scope_results']['preparation_model']['status'],'INCOMPLETE')

    def test_relabelling_an_edit_as_verification_is_rejected(self):
        original=source(); sources={'input':original}
        edited=run_step('mutate_sequence',{'dna_seq':'$input','mutations':[{'position_0based':100,'alt_base':'T'}]},step_id='edited',sources=sources)
        result=validate_candidate({'topology':'linear'},sources,[edited],edited.result.only_product(),
                 result_kind='verification',required_scopes=['sequence_model','user_goal'])
        self.assertEqual(result['overall'],'failed')
        self.assertIn('RESULT_ROLE_MISMATCH',str(result['errors']))

    def test_delivery_adds_missing_required_checks_to_a_valid_reaction(self):
        original=source(1258); sequence=str(original.seq); sources={'input':original}
        step=run_step('anneal_oligos',{'top_oligo':sequence,'bottom_oligo':str(Seq(sequence).reverse_complement())},
                      step_id='prepared',sources=sources)
        self.assertEqual(step.status,'completed',step.error)
        with tempfile.TemporaryDirectory() as temp:
            result=deliver_result({'topology':'linear','expected_sequence':sequence},sources,[step],
                   step.result.only_product(),temp,required_scopes=['sequence_model','file','user_goal'])
            self.assertEqual(result['status'],'delivered')
            self.assertEqual(result['validation']['scope_results']['preparation_model']['status'],'PASSED')
            self.assertIn('preparation_model',result['validation']['required_scopes'])

    def test_pipeline_sequence_design_is_disclosed_and_cannot_certify_preparation(self):
        from agent.pipeline_agent import execute_agent_pipeline
        original=source(3210)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            from core.tools.snapgene_io import export_snapgene
            path=export_snapgene(original,root/'source').analysis['gb_file']
            steps=[{'step_id':'part','tool':'extract_subsequence','params':{'source':'$input','start':10,'end':240}}]
            scoped=execute_agent_pipeline('scoped',steps,[{'source_id':'input','path':path}],
                       product_topology='linear',out_dir=root/'component',user_confirmed=True)
            self.assertEqual(scoped['status'],'delivered')
            self.assertEqual(scoped['result_kind'],'component')
            self.assertEqual(scoped['delivery']['validation']['scope_results']['preparation_model']['status'],'INCOMPLETE')
            prepared=execute_agent_pipeline('full',steps,[{'source_id':'input','path':path}],
                       product_topology='linear',out_dir=root/'construct',user_confirmed=True,
                       result_kind='construct',validation_requirements=['sequence_model','file','user_goal'])
            self.assertEqual(prepared['status'],'failed')
            self.assertIsNone(prepared['delivery'])
            self.assertEqual(prepared['validation_report']['scope_results']['preparation_model']['status'],'INCOMPLETE')

    def test_failed_ids_are_not_silently_reused(self):
        original=source(); sources={'input':original}
        first=run_step('extract_subsequence',{'source':'$input','start':10,'end':80},step_id='part',sources=sources)
        failed=run_step('extract_subsequence',{'source':'$absent','start':0,'end':20},step_id='attempt',sources=sources,previous=[first])
        repeat=run_step('calc_primer_tm',{'primer_seq':'ACGTACGTCGATCGTACGTA'},step_id='attempt',sources=sources,previous=[first,failed])
        self.assertEqual(repeat.status,'failed')
        self.assertEqual(repeat.error['error_code'],'INVALID_STEP_ID')

    def test_invalid_arguments_return_actual_signature_without_full_schema(self):
        record=run_step('extract_subsequence',{'source':source(),'start':'not a coordinate','end':200})
        self.assertEqual(record.error['error_code'],'TOOL_ARGUMENT_INVALID')
        self.assertEqual(record.error['details']['parameter_path'],['start'])
        self.assertIn('end',record.error['details']['required_parameters'])
        self.assertIn('describe_tools.py',record.error['details']['recovery'])
        self.assertNotIn('Failed validating',record.error['message'])

    def invoke(self,script,arguments,cwd):
        proc=subprocess.run([sys.executable,'-X','utf8','-B',str(SKILL_ROOT/'scripts'/script),*map(str,arguments)],
                cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
        return proc,json.loads(proc.stdout)

    def test_default_analysis_output_contains_actual_result(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);config=root/'step.json'
            config.write_text(json.dumps({'method':'calc_primer_tm','step_id':'temperature',
                'params':{'primer_seq':'ACGTACGTCGATCGTACGTA'}}),encoding='utf-8')
            proc,result=self.invoke('run_step.py',['--input',config,'--out-dir',root/'out'],root)
            self.assertEqual(proc.returncode,0,proc.stderr)
            from Bio.SeqUtils.MeltingTemp import Tm_NN
            expected=round(Tm_NN('ACGTACGTCGATCGTACGTA',Na=50,Mg=0,dNTPs=0,dnac1=100,dnac2=100),1)
            self.assertEqual(result['analysis']['tm'],expected)

    def test_workspace_continuation_supplies_references_and_current_state(self):
        with tempfile.TemporaryDirectory(prefix='连续工作流 ') as temp:
            root=Path(temp);first=root/'first.json';second=root/'second.json'
            original=source(); from core.tools.result import to_wire
            first.write_text(json.dumps({'method':'extract_subsequence','step_id':'fragment',
                'sources':{'original':to_wire(original)},'params':{'source':'$original','start':0,'end':240},
                'requirements':{'topology':'linear'}},ensure_ascii=False),encoding='utf-8')
            proc,created=self.invoke('run_step.py',['--input',first,'--workspace',root/'work'],root)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertEqual(created['products'][0]['product_ref'],'$fragment.products.0')
            second.write_text(json.dumps({'method':'extract_subsequence','step_id':'shorter',
                'params':{'source':created['products'][0]['product_ref'],'start':0,'end':200}}),encoding='utf-8')
            proc,continued=self.invoke('run_step.py',['--input',second,'--workspace',root/'work'],root)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertEqual(continued['completed_prefix'],['fragment','shorter'])
            self.assertEqual(continued['products'][0]['length'],200)
            proc,status=self.invoke('run_step.py',['--workspace',root/'work','--status'],root)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertEqual(status['selected_product_ref'],'$shorter.products.0')

    def test_wrong_record_type_has_a_specific_recovery_instruction(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);record=root/'plan.json';config=root/'close.json'
            record.write_text(json.dumps({'sources':[{'id':'x'}],'steps':[{'tool':'rotate_sequence'}]}),encoding='utf-8')
            config.write_text(json.dumps({'record_file':str(record),'candidate':'ACGT'}),encoding='utf-8')
            proc,result=self.invoke('finalize_workflow.py',['--input',config,'--out-dir',root/'out'],root)
            self.assertNotEqual(proc.returncode,0)
            self.assertEqual(result['error']['error_code'],'WORKFLOW_RECORD_INVALID')
            self.assertIn('steps.json',result['error']['message'])
            self.assertNotIn('object has no attribute',result['error']['message'])

    def test_invalid_parameter_shape_keeps_workspace_recoverable(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            from core.tools.result import to_wire
            configs=[{'method':'extract_subsequence','step_id':'fragment','sources':{'original':to_wire(source())},
                      'params':{'source':'$original','start':0,'end':240}},
                     {'method':'extract_subsequence','step_id':'bad_shape','params':[]},
                     {'method':'extract_subsequence','step_id':'recovered','params':{'source':'$fragment','start':0,'end':200}}]
            outputs=[]
            for index,config in enumerate(configs):
                path=root/f'{index}.json';path.write_text(json.dumps(config),encoding='utf-8')
                outputs.append(self.invoke('run_step.py',['--input',path,'--workspace',root/'work'],root))
            self.assertEqual(outputs[0][0].returncode,0)
            self.assertNotEqual(outputs[1][0].returncode,0)
            self.assertEqual(outputs[2][0].returncode,0,outputs[2][1])
            history=json.loads((root/'work/steps.json').read_text(encoding='utf-8'))
            self.assertEqual([row['step_id'] for row in history['steps']],['fragment','bad_shape','recovered'])
            self.assertEqual(history['steps'][1]['params'],[])
            self.assertEqual(history['steps'][1]['error']['error_code'],'TOOL_ARGUMENT_INVALID')


if __name__=='__main__': unittest.main()
