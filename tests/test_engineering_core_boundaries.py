"""Public source, input and delivery boundaries; no external desktop dependency."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import copy
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core import execute, finalize, plan, validate, validate_construction_task
from core.errors import GateRejected, PlanningError, TaskValidationError
from core.guardrails.checklist import quick_biological_sanity_check
from core.io.input_resolution import resolve_sequence_input, resolve_sequence_string
from core.runtime_gate import finalize_candidate_construct
from core.runtime_plan import compute_plan_sha256


class CoreBoundaryContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / '原始模板.gb'
        self.record = SeqRecord(Seq('ATGAAACCCTAA' + 'ACGT'*20), id='source',
                               annotations={'molecule_type':'DNA', 'topology':'linear'})
        self.record.features = [SeqFeature(FeatureLocation(0,12,strand=1),type='CDS',
                                          qualifiers={'label':['coding']})]
        with self.source.open('w',encoding='utf-8') as handle:
            SeqIO.write(self.record,handle,'genbank')

    def task(self, name='boundary'):
        return {'task_id':name,'mode':'formal','task_kind':'point_mutation',
                'sources':[{'source_id':'template','path':str(self.source),'role':'template',
                            'evidence':{'source_evidence_class':'user-provided'}}],
                'operation':{'mutations':[{'position_1based':20,'ref':'T','alt':'A'}]},
                'target':{'source_id':'template'},
                'product':{'topology':'linear','formats':[]},
                'approvals':{'user_confirmed_task':{'value':True}}}

    def prepared(self, name):
        task, planned = plan(self.task(name))
        execution = execute(task,planned,self.root/name)
        validation = validate(task,planned,execution)
        self.assertEqual(validation['overall'],'verified',validation['errors'])
        return task, planned, execution, validation

    def test_relative_sources_and_computable_defaults(self):
        original = self.task()
        original['sources'][0]['path'] = self.source.name
        result = validate_construction_task(original, base_dir=self.root)
        self.assertEqual(Path(result['sources'][0]['_resolved_path']),self.source)
        self.assertEqual(result['sources'][0]['topology'],'linear')
        self.assertEqual(len(result['sources'][0]['sha256']),64)
        self.assertEqual(result['product']['formats'],['gb','fasta','dna'])
        self.assertEqual(result['revision'],1)
        self.assertEqual(result['assumptions'],[])

    def test_ambiguous_or_contradictory_sources_are_rejected(self):
        cases=[]
        duplicate=self.task();duplicate['sources'].append(copy.deepcopy(duplicate['sources'][0]))
        cases.append((duplicate,'DUPLICATE_SOURCE_ID'))
        duplicate_role=self.task();other=copy.deepcopy(duplicate_role['sources'][0]);other['source_id']='another'
        duplicate_role['sources'].append(other);cases.append((duplicate_role,'DUPLICATE_SOURCE_ROLE'))
        missing=self.task();missing['sources'][0]['path']=str(self.root/'missing.gb')
        cases.append((missing,'SOURCE_FILE_MISSING'))
        bad_hash=self.task();bad_hash['sources'][0]['sha256']='0'*64
        cases.append((bad_hash,'SOURCE_HASH_MISMATCH'))
        bad_topology=self.task();bad_topology['sources'][0]['topology']='circular'
        cases.append((bad_topology,'SOURCE_TOPOLOGY_MISMATCH'))
        unresolved=self.task();unresolved.update(task_kind='component_amplification',operation={},
            target={'source_id':'template','selection':{'kind':'interval','interval_0based':[0,12],
                                                       'resolution_status':'unresolved'}})
        cases.append((unresolved,'COMPONENT_BOUNDARY_REQUIRED'))
        for task,code in cases:
            with self.subTest(code=code), self.assertRaises(TaskValidationError) as caught:
                validate_construction_task(task)
            self.assertEqual(caught.exception.error_code,code)
        with self.assertRaises(TaskValidationError) as caught:
            validate_construction_task([])
        self.assertEqual(caught.exception.error_code,'TASK_MUST_BE_OBJECT')

    def test_execution_requires_the_same_task_and_frozen_plan(self):
        task, planned=plan(self.task())
        changed_task=copy.deepcopy(task);changed_task['operation']['mutations'][0]['alt']='G'
        changed_plan=copy.deepcopy(planned);changed_plan['product_topology']='circular'
        for t,p,code in ((changed_task,planned,'PLAN_TASK_HASH_MISMATCH'),
                         (task,changed_plan,'PLAN_HASH_MISMATCH')):
            with self.subTest(code=code), self.assertRaises(PlanningError) as caught:
                execute(t,p,self.root/'must-not-execute')
            self.assertEqual(caught.exception.error_code,code)
        self.assertFalse((self.root/'must-not-execute').exists())

    def test_foreign_or_edited_receipts_cannot_be_promoted(self):
        task,planned,execution,validation=self.prepared('first')
        _,_,other_execution,other_validation=self.prepared('other')
        altered_plan=copy.deepcopy(planned);altered_plan['task_revision']+=1
        altered_execution=copy.deepcopy(execution);altered_execution['execution_sha256']='F'*64
        altered_validation=copy.deepcopy(validation);altered_validation['validation_sha256']='F'*64
        for label,p,e,v in (
            ('revision',altered_plan,execution,validation),
            ('foreign-execution',planned,other_execution,validation),
            ('foreign-validation',planned,execution,other_validation),
            ('changed-execution',planned,altered_execution,validation),
            ('changed-validation',planned,execution,altered_validation)):
            with self.subTest(label=label), self.assertRaises(GateRejected) as caught:
                finalize(task,p,e,v,self.root/label)
            self.assertEqual(caught.exception.error_code,'GATE_HASH_CHAIN_BROKEN')
            self.assertFalse((self.root/label/'authoritative').exists())

    def test_source_and_product_presence_are_rechecked_at_delivery(self):
        original=self.source.read_bytes()
        for name,code in (('source-missing','GATE_SOURCE_MISSING'),
                          ('source-changed','GATE_SOURCE_TAMPERED'),
                          ('product-missing','GATE_ARTIFACT_MISSING'),
                          ('product-changed','GATE_ARTIFACT_TAMPERED')):
            with self.subTest(name=name):
                self.source.write_bytes(original)
                t,p,e,v=self.prepared(name)
                if name=='source-missing':self.source.unlink()
                elif name=='source-changed':self.source.write_bytes(original+b'\n')
                elif name=='product-missing':Path(e['product_fasta']).unlink()
                else:Path(e['product_fasta']).write_text('>wrong\nAAAA\n',encoding='utf-8')
                with self.assertRaises(GateRejected) as caught:
                    finalize(t,p,e,v,self.root/(name+'-delivery'))
                self.assertEqual(caught.exception.error_code,code)
                self.assertFalse((self.root/(name+'-delivery')/'authoritative').exists())

    def test_inline_and_file_inputs_preserve_sequence_or_fail_clearly(self):
        record,sequence=resolve_sequence_input('>user sequence\nacgtNN\n',default_topology='circular')
        self.assertEqual(sequence,'ACGTNN')
        self.assertEqual(record.annotations['topology'],'circular')
        self.assertEqual(resolve_sequence_string(' acgt\nry '),'ACGTRY')
        genbank_as_text=self.root/'材料.txt';genbank_as_text.write_bytes(self.source.read_bytes())
        self.assertEqual(resolve_sequence_string(genbank_as_text),str(self.record.seq))
        with self.assertRaises(FileNotFoundError):resolve_sequence_input(self.root/'absent.dna')
        with self.assertRaises(TypeError):resolve_sequence_input(123)
        with self.assertRaises(ValueError):resolve_sequence_input({'sequence':None})
        for suffix in ('.gb','.dna','.seq'):
            path=self.root/('损坏'+suffix);path.write_bytes(b'not a sequence format\x00\xff')
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):resolve_sequence_input(path)
        for text in ('not a DNA record', 'not-dna-'*10000, '>one\nACGT\n>two\nACGT'):
            with self.subTest(text_length=len(text)), self.assertRaises(ValueError) as caught:
                resolve_sequence_input(text)
            self.assertLess(len(str(caught.exception)),220)

    def test_mismatched_candidate_formats_leave_no_authoritative_output(self):
        fasta=self.root/'mismatched.fa';fasta.write_text('>different\nACGT\n',encoding='utf-8')
        original=self.source.read_bytes()
        sanity=quick_biological_sanity_check(self.record,topology='linear',is_cds=False)
        destination=self.root/'candidate-delivery'
        with self.assertRaises(GateRejected) as caught:
            finalize_candidate_construct(self.source,fasta,destination,
                {'recipe':'source-inspection'},sanity,user_confirmed=True)
        self.assertEqual(caught.exception.error_code,'GATE_THREE_FORMAT_SEQUENCE_MISMATCH')
        self.assertFalse((destination/'authoritative').exists())
        self.assertFalse(list(destination.glob('.authoritative-*.tmp')))
        self.assertEqual(self.source.read_bytes(),original)

    def test_missing_receipt_hashes_cannot_authorize_delivery(self):
        t,p,e,v=self.prepared('missing-receipts')
        for receipt,key in ((e,'execution_sha256'),(v,'validation_sha256')):
            with self.subTest(key=key):
                original=receipt.pop(key)
                with self.assertRaises(GateRejected):
                    finalize(t,p,e,v,self.root/key)
                self.assertFalse((self.root/key/'authoritative').exists())
                receipt[key]=original

    def test_legacy_plan_requires_regeneration_before_execution(self):
        t,p=plan(self.task())
        p.pop('product_features')
        p['plan_sha256']=compute_plan_sha256(p)
        with self.assertRaises(PlanningError) as caught:
            execute(t,p,self.root/'legacy')
        self.assertEqual(caught.exception.error_code,'PLAN_REGENERATION_REQUIRED')

    def candidate(self):
        fasta=self.root/'candidate.fa'
        with fasta.open('w',encoding='utf-8') as stream:
            SeqIO.write(self.record,stream,'fasta')
        sanity=quick_biological_sanity_check(self.record,topology='linear',is_cds=False)
        return fasta,sanity

    def test_requested_desktop_check_requires_executable_and_actual_boolean_receipt(self):
        fasta,sanity=self.candidate()
        run=subprocess.run
        variants=[('missing',None,None),('process-error',1,''),('invalid-json',0,'not JSON'),
                  ('array',0,'[]'),('truthy-string',0,'{"ok":"true"}'),
                  ('rejected',0,'{"core_passed":false}'),('verified',0,'{"core_passed":true}')]
        for name,code,body in variants:
            destination=self.root/name
            def external(args,**kwargs):
                if any(str(a).endswith('validate_roundtrip.py') for a in args):
                    return subprocess.CompletedProcess(args,code,body,'desktop diagnostic')
                return run(args,**kwargs)
            with self.subTest(name=name), mock.patch.dict(os.environ,{'SNAPGENE_VERIFY_OFFICIAL':'1'}), \
                 mock.patch('core.tools.snapgene_io.find_snapgene_executable',return_value=None if code is None else Path(sys.executable)), \
                 mock.patch('core.runtime_gate.subprocess.run',side_effect=external):
                if name=='verified':
                    result=finalize_candidate_construct(self.source,fasta,destination,{'recipe':'test'},sanity,True)
                    self.assertEqual(result['status'],'delivered')
                else:
                    with self.assertRaises(GateRejected) as caught:
                        finalize_candidate_construct(self.source,fasta,destination,{'recipe':'test'},sanity,True)
                    self.assertEqual(caught.exception.error_code,'GATE_OFFICIAL_ROUNDTRIP_FAILED')
                    self.assertFalse((destination/'authoritative').exists())
                self.assertFalse(list(destination.glob('.authoritative-*.tmp')))

    def test_delivery_collision_does_not_remove_another_attempts_files(self):
        fasta,sanity=self.candidate()
        destination=self.root/'collision'
        real_replace=Path.replace
        def race(path,target):
            if path.name.startswith('.authoritative-'):
                Path(target).mkdir()
                (Path(target)/'other-result.txt').write_text('keep',encoding='utf-8')
                raise FileExistsError('competing writer completed')
            return real_replace(path,target)
        with mock.patch.object(Path,'replace',race), self.assertRaises(GateRejected) as rejected:
            finalize_candidate_construct(self.source,fasta,destination,{'recipe':'../../not-a-path'},sanity,True)
        self.assertEqual(rejected.exception.error_code,'GATE_AUTHORITATIVE_ALREADY_EXISTS')
        self.assertEqual((destination/'authoritative/other-result.txt').read_text(encoding='utf-8'),'keep')
        self.assertFalse(list(destination.glob('.authoritative-*.tmp')))

    def test_native_write_and_read_failures_preserve_candidate(self):
        fasta,sanity=self.candidate()
        original=self.source.read_bytes()
        for name in ('write','read'):
            destination=self.root/name
            patch=(mock.patch('core.runtime_gate.subprocess.run',return_value=subprocess.CompletedProcess([],1,'','write failed'))
                   if name=='write' else mock.patch('core.tools.snapgene_io.read_native_dna_record',side_effect=ValueError('corrupt native result')))
            with self.subTest(name=name), patch, self.assertRaises(GateRejected):
                finalize_candidate_construct(self.source,fasta,destination,{'recipe':'test'},sanity,True)
            self.assertFalse((destination/'authoritative').exists())
            self.assertFalse(list(destination.glob('.authoritative-*.tmp')))
            self.assertEqual(self.source.read_bytes(),original)


if __name__=='__main__':unittest.main()
