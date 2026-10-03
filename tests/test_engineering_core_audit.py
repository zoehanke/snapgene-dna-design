"""Independent source/target regressions for the 2026-09 engineering audit."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import copy
import tempfile
import unittest
from pathlib import Path

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core import plan, execute, validate, finalize
from core.errors import GateRejected
from core.runtime_plan import compute_plan_sha256
from core.runtime_validate import compute_validation_sha256
from core.tools.snapgene_io import export_plasmid, read_native_dna_record


class EngineeringCoreAudit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def source(self, name, sequence, features=(), topology='linear', role='template', fmt='gb'):
        record = SeqRecord(Seq(sequence), id=name, annotations={'molecule_type':'DNA', 'topology':topology})
        record.features = list(features)
        path = self.root / (name+'.'+fmt)
        if fmt == 'dna':
            path = Path(export_plasmid(record,self.root,name)['dna_file'])
        else:
            with path.open('w',encoding='utf-8') as handle:
                SeqIO.write(record,handle,'fasta' if fmt=='fasta' else 'genbank')
        return {'source_id':name, 'path':str(path), 'role':role, 'topology':topology,
                'evidence':{'source_evidence_class':'user-provided'}}

    def feature(self, name, start, end, strand=1, cds=False):
        return SeqFeature(FeatureLocation(start,end,strand=strand), type='CDS' if cds else 'misc_feature',
                          qualifiers={'label':[name]})

    def task(self, kind, sources, operation, **extra):
        task = {'schema_version':'construction-task-v1','task_id':'audit-'+kind,'revision':1,
                'mode':'formal','task_kind':kind,'sources':sources,'operation':operation,
                'target':{'source_id':sources[0]['source_id']},'product':{'topology':'linear'},
                'method_constraints':{},'approvals':{'user_confirmed_task':{'value':True}},
                'assumptions':[],'provenance':[]}
        task.update(extra)
        task["product"].setdefault("formats", ["gb", "fasta", "dna"])
        return task

    def run_task(self, task):
        task, planned = plan(task)
        execution = execute(task,planned,self.root/task['task_id'])
        validation = validate(task,planned,execution)
        record = SeqIO.read(execution['product_gb'],'genbank')
        return task, planned, execution, validation, record

    def test_goal_exception_and_nested_requirements_cannot_be_delivered(self):
        source = self.source('template','ATGAAACCCTAA'+'ACGT'*20,[self.feature('coding',0,12,cds=True)])
        for extra in ({'expected_components':[{'name':'outside','source_id':'template','interval_0based':[0,999]}]},
                      {'product':{'topology':'linear','required_components':['absent']}},
                      {'product':{'topology':'linear','forbidden_components':['coding']}}):
            with self.subTest(extra=extra):
                task = self.task('point_mutation',[source],{'mutations':[{'position_1based':20,'ref':'T','alt':'A'}]},**extra)
                t,p,e,v,_=self.run_task(task)
                self.assertTrue(v['artifact_valid'],v['errors'])
                self.assertFalse(v['goal_valid'])
                self.assertEqual(v['overall'],'failed')
                with self.assertRaises(GateRejected):finalize(t,p,e,v,self.root/'rejected')

    def test_mutation_keeps_annotations_and_detects_internal_stop(self):
        source = self.source('template','ATGAAACCCTAA'+'ACGT'*20,[self.feature('coding',0,12,cds=True),self.feature('reverse',20,32,-1)])
        t,p,e,v,record=self.run_task(self.task('point_mutation',[source],{'mutations':[{'position_1based':4,'ref':'A','alt':'T'}]}))
        self.assertEqual(str(record.seq[:12]),'ATGTAACCCTAA')
        self.assertEqual([(f.type,int(f.location.start),int(f.location.end),f.location.strand) for f in record.features],
                         [('CDS',0,12,1),('misc_feature',20,32,-1)])
        self.assertFalse(v['artifact_valid'])
        self.assertIn('CDS_PREMATURE_STOP',v['error_codes'])

    def test_plan_feature_removal_cannot_launder_annotation_loss(self):
        source = self.source('template','ATGAAACCCTAA'+'ACGT'*20,[self.feature('coding',0,12,cds=True)])
        t,p=plan(self.task('point_mutation',[source],{'mutations':[{'position_1based':20,'ref':'T','alt':'A'}]}))
        p['product_features']=[]
        p['plan_sha256']=compute_plan_sha256(p)
        e=execute(t,p,self.root/'tampered')
        v=validate(t,p,e)
        self.assertFalse(v['artifact_valid'])
        self.assertIn('ANNOTATION_RETENTION_FAILED',v['error_codes'])

    def test_input_formats_and_legitimate_final_delivery(self):
        for fmt in ('gb','dna','fasta'):
            with self.subTest(fmt=fmt):
                source=self.source('template-'+fmt,'ATGAAACCCTAA'+'ACGT'*20,[self.feature('coding',0,12,cds=True)],fmt=fmt)
                task=self.task('point_mutation',[source],{'mutations':[{'position_1based':20,'ref':'T','alt':'A'}]})
                t,p,e,v,record=self.run_task(task)
                self.assertEqual(v['overall'],'verified',v['errors'])
                result=finalize(t,p,e,v,self.root/('delivery-'+fmt))
                actual=read_native_dna_record(Path(result['directory'])/'construct.dna')
                self.assertEqual(str(actual.seq),str(record.seq))
                self.assertEqual(len(actual.features),0 if fmt=='fasta' else 1)

    def test_slice_donor_insert_and_replace_coordinate_oracles(self):
        source=self.source('piece','ACGT'*20,[self.feature('part',12,21,-1)])
        selection={'kind':'interval','interval_0based':[10,30],'strand':-1,'resolution_status':'resolved'}
        component=self.task('component_amplification',[source],{},target={'source_id':'piece','selection':selection})
        t,p,e,v,record=self.run_task(component)
        self.assertEqual(v['overall'],'verified',v['errors'])
        self.assertEqual(str(record.seq),str(Seq(('ACGT'*20)[10:30]).reverse_complement()))
        self.assertEqual((int(record.features[0].location.start),int(record.features[0].location.end),record.features[0].location.strand),(9,18,1))
        donor=self.task('integration_donor',[source],{'homology_arms':{'left_arm':'AAA','right_arm':'CCC'}},
            target={'source_id':'piece','selection':{'kind':'interval','interval_0based':[10,30],'strand':1,'resolution_status':'resolved'}})
        _,_,_,v,record=self.run_task(donor)
        self.assertEqual(v['overall'],'verified',v['errors'])
        self.assertEqual((int(record.features[0].location.start),int(record.features[0].location.end)),(5,14))
        backbone=self.source('backbone','T'*60,[self.feature('backbone-mark',40,50)],topology='circular',role='backbone')
        insert=copy.deepcopy(source);insert['role']='insert'
        for kind,operation,expected_start in (
            ('plasmid_insert',{'insert':{'boundary_0based':20,'insert_source_id':'piece','interval_0based':[10,30]}},22),
            ('plasmid_replace',{'replace':{'interval_0based':[10,20],'replacement_source_id':'piece','replacement_interval_0based':[10,30]}},12)):
            with self.subTest(kind=kind):
                task=self.task(kind,[backbone,insert],operation,product={'topology':'circular'},
                    target={'source_id':'backbone','selection':{'kind':'interval','interval_0based':[10,20],'resolution_status':'resolved'}})
                _,_,_,v,record=self.run_task(task)
                self.assertEqual(v['overall'],'verified',v['errors'])
                marker=next(f for f in record.features if f.qualifiers.get('label')==['part'])
                self.assertEqual((int(marker.location.start),int(marker.location.end)),(expected_start,expected_start+9))
                self.assertTrue(any(f.qualifiers.get('label')==['backbone-mark'] for f in record.features))

    def test_overlap_and_hierarchy_preserve_reverse_fragment_once(self):
        one=self.source('one','AAAACCCCGGGG',[self.feature('one-mark',4,8)],role='insert')
        two=self.source('two','AAAACCCC',[self.feature('two-mark',0,4)],role='insert')
        fragments=[{'source_id':'one','interval_0based':[0,12],'order':0},
                   {'source_id':'two','interval_0based':[0,8],'strand':-1,'order':1}]
        for kind,operation in (
            ('overlap_assembly',{'fragments':fragments,'overlap_length':4}),
            ('hierarchical_assembly',{'stages':[{'stage_id':'s','fragments':fragments,'overlap_length':4,'product_topology':'linear'}]})):
            with self.subTest(kind=kind):
                _,_,_,v,record=self.run_task(self.task(kind,[one,two],operation))
                self.assertEqual(v['overall'],'verified',v['errors'])
                self.assertEqual(str(record.seq),'AAAACCCCGGGGTTTT')
                marker=next(f for f in record.features if f.qualifiers.get('label')==['two-mark'])
                self.assertEqual((int(marker.location.start),int(marker.location.end),marker.location.strand),(12,16,-1))

    def test_fusion_preserves_partner_annotations_and_explicit_stop_removal(self):
        left=self.source('left','ATGAAACCCTAA',[self.feature('left-cds',0,12,cds=True)],role='insert')
        right=self.source('right','ATGGGGTAA',[self.feature('right-cds',0,9,cds=True)],role='insert')
        task=self.task('protein_fusion',[left,right],{'partner5':{'source_id':'left','interval_0based':[0,12]},
            'partner3':{'source_id':'right','interval_0based':[0,9]},'linker':{'dna':'GGT'},'stop_policy':'stop'})
        _,_,_,v,record=self.run_task(task)
        self.assertEqual(v['overall'],'verified',v['errors'])
        self.assertEqual(str(record.seq),'ATGAAACCCGGTATGGGGTAA')
        self.assertEqual([(int(f.location.start),int(f.location.end)) for f in record.features],[(0,9),(12,21)])
        self.assertEqual(record.features[0].qualifiers['partial'],['true'])

    def test_restriction_preserves_retained_backbone_and_insert(self):
        vector=self.source('vector','GGGGAATTCAAAAAGCTTCCC',[self.feature('vector-mark',0,3)],topology='circular',role='backbone')
        insert=self.source('insert','AAGAATTCTTTTTTAAGCTTGG',[self.feature('insert-mark',9,12)],role='insert')
        task=self.task('restriction_ligation',[vector,insert],{'vector_source_id':'vector','insert_source_id':'insert',
            'vector_enzymes':['EcoRI','HindIII'],'orientation':'forward'},product={'topology':'circular'})
        _,_,_,v,record=self.run_task(task)
        self.assertEqual(v['overall'],'experimental-preview',v['errors'])
        features={f.qualifiers['label'][0]:f for f in record.features}
        self.assertEqual(str(features['vector-mark'].extract(record.seq)),'GGG')
        self.assertEqual(str(features['insert-mark'].extract(record.seq)),'TTT')

    def test_gateway_preserves_actual_recombined_sources(self):
        from core.tools.recombination import ATTL1, ATTL2, ATTR1, ATTR2
        body='AAAACCCTTTTAA'
        entryseq=ATTL1+body+str(Seq(ATTL2).reverse_complement())+'G'*40
        destseq=ATTR1+'TTTTCCCC'+str(Seq(ATTR2).reverse_complement())+'C'*40
        entry=self.source('entry',entryseq,[self.feature('body',len(ATTL1),len(ATTL1)+len(body))],topology='circular',role='entry')
        dest=self.source('dest',destseq,[self.feature('kept',len(destseq)-30,len(destseq)-20)],topology='circular',role='destination')
        task=self.task('gateway_recombination',[entry,dest],{'reaction':'lr','entry_source_id':'entry',
            'destination_source_id':'dest','stop_policy':'stop'},product={'topology':'circular'})
        _,_,_,v,record=self.run_task(task)
        self.assertEqual(v['overall'],'verified',v['errors'])
        features={f.qualifiers['label'][0]:f for f in record.features}
        self.assertEqual(str(features['body'].extract(record.seq)),body)
        self.assertEqual(str(features['kept'].extract(record.seq)),'C'*10)

    def test_crispr_preview_keeps_reference_and_donor_features(self):
        refseq='AAAA'+'TACGTACGTACGTACGTACGTGG'+'A'*28
        ref=self.source('reference',refseq,[self.feature('retained',34,38)],role='reference')
        donor=self.source('donor','G'*10,[self.feature('donor-mark',2,8)],role='donor_component')
        task=self.task('crispr_editing',[ref,donor],{'nuclease':'spcas9-wt','target_interval_0based':[4,28],
            'guide_strategy':{'pam':'NGG'},'donor_strategy':{'donor_source_id':'donor','replacement_interval_0based':[0,10],
                'homology_arms':{'left_arm':refseq[:4],'right_arm':refseq[28:32]}}})
        _,_,_,v,record=self.run_task(task)
        self.assertEqual(v['overall'],'experimental-preview',v['errors'])
        features={f.qualifiers['label'][0]:f for f in record.features}
        self.assertEqual((int(features['retained'].location.start),int(features['retained'].location.end)),(20,24))
        self.assertEqual((int(features['donor-mark'].location.start),int(features['donor-mark'].location.end)),(6,12))

    def test_negative_locus_donor_uses_unequal_arms_on_correct_flanks(self):
        reference_seq='ACGT'*20
        reference=self.source('locus',reference_seq,[self.feature('left-genomic',5,10)],role='reference')
        piece=self.source('piece','GGGAAACCC',[self.feature('payload',0,9)],role='template')
        left=str(Seq(reference_seq[20:23]).reverse_complement())
        right=str(Seq(reference_seq[5:10]).reverse_complement())
        task=self.task('integration_donor',[piece,reference],{
            'homology_arms':{'left_arm':left,'right_arm':right},
            'locus':{'source_id':'locus','interval_0based':[10,20],'strand':-1}},
            target={'source_id':'piece','selection':{'kind':'interval','interval_0based':[0,9],'resolution_status':'resolved'}})
        _,_,_,v,record=self.run_task(task)
        self.assertEqual(v['overall'],'verified',v['errors'])
        self.assertEqual(str(record.seq),left+'GGGAAACCC'+right)
        feature=next(f for f in record.features if f.qualifiers.get('label')==['left-genomic'])
        self.assertEqual((int(feature.location.start),int(feature.location.end),feature.location.strand),(12,17,-1))

    def test_fabricated_plan_component_cannot_satisfy_unknown_requirement(self):
        source=self.source('template','ATGAAACCCTAA'+'ACGT'*20)
        task=self.task('point_mutation',[source],{'mutations':[{'position_1based':20,'ref':'T','alt':'A'}]},
            product={'topology':'linear','required_components':['invented-component']})
        t,p=plan(task)
        p['expected_components']=[{'name':'invented-component','expected_sequence':p['product_sequence']}]
        p['plan_sha256']=compute_plan_sha256(p)
        e=execute(t,p,self.root/'invented')
        v=validate(t,p,e)
        self.assertFalse(v['goal_valid'])
        self.assertEqual(v['overall'],'failed')

    def test_gate_rejects_contradictory_or_nonboolean_validation(self):
        source=self.source('template','ATGAAACCCTAA'+'ACGT'*20)
        t,p,e,v,_=self.run_task(self.task('point_mutation',[source],{'mutations':[{'position_1based':20,'ref':'T','alt':'A'}]}))
        self.assertEqual(v['overall'],'verified')
        for mutation in ({'errors':['a recorded check failed']},{'artifact_valid':'false'}):
            with self.subTest(mutation=mutation):
                forged=copy.deepcopy(v);forged.update(mutation)
                forged['validation_sha256']=compute_validation_sha256(forged)
                with self.assertRaises(GateRejected):finalize(t,p,e,forged,self.root/'invalid-evidence')

    def test_deriving_missing_translation_does_not_repair_wrong_source_translation(self):
        cds=self.feature('coding',0,12,cds=True)
        cds.qualifiers['translation']=['WRONG']
        source=self.source('template','ATGAAACCCTAA'+'ACGT'*20,[cds])
        _,_,_,v,record=self.run_task(self.task('point_mutation',[source],{'mutations':[{'position_1based':20,'ref':'T','alt':'A'}]}))
        self.assertFalse(v['artifact_valid'])
        self.assertEqual(record.features[0].qualifiers['translation'],['WRONG'])
        self.assertIn('CDS_TRANSLATION_MISMATCH',v['error_codes'])


if __name__ == '__main__':
    unittest.main()
