"""Source-derived expectations at the public molecular-tool seam."""
from repository_paths import SKILL_ROOT
import copy
import unittest
import tempfile
import json
from pathlib import Path
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord
from core.tools import get_tool
from core.tools.snapgene_io import export_snapgene
from core.io.input_resolution import resolve_sequence_record
from core.handlers.composite_pipeline import run_pipeline_steps
from core.recipes.verification import recipe_cloning_verification
from core.models.molecule import Molecule, as_molecule, derived_molecule
from core.models.assembly_model import FragmentEnd
from Bio.SeqFeature import BeforePosition, AfterPosition
from core import plan,execute,validate
import random


class OriginalTransportFailures(unittest.TestCase):
    def source(self, seq):
        record = SeqRecord(Seq(seq), id='input', annotations={'molecule_type': 'DNA', 'topology': 'linear'})
        record.features = [SeqFeature(FeatureLocation(0, 3), type='misc_feature', qualifiers={'label': ['retained']})]
        return record

    def test_record_digest_uses_actual_bases_and_retains_annotations(self):
        record = self.source('GGGGAATTCTTTTTT')
        before = copy.deepcopy(record)
        result = get_tool('digest_sequence').execute(seq=record, enzyme='EcoRI')
        self.assertEqual([str(p.seq) for p in result.products], ['GGGG', 'AATTCTTTTTT'])
        self.assertEqual(str(result.products[0].features[0].extract(result.products[0].seq)), 'GGG')
        self.assertEqual(str(record.seq), str(before.seq))
        self.assertEqual(record.features, before.features)

    def test_terminal_removal_uses_record_sequence(self):
        record = self.source('ATGGCTTAA')
        result = get_tool('strip_terminal_codons').execute(cds_seq=record, strip_stop=True)
        self.assertEqual(str(result.products[0].seq), 'ATGGCT')
        self.assertEqual(str(record.seq), 'ATGGCTTAA')

    def test_annotation_does_not_mutate_the_original(self):
        record = self.source('ACGTACGT')
        result = get_tool('annotate_feature').execute(record=record, name='new', start=3, end=6)
        self.assertEqual(len(record.features), 1)
        self.assertEqual(len(result.products[0].features), 2)

    def test_feature_identity_is_not_a_short_substring(self):
        record = self.source('ACGT' * 30)
        record.features = [SeqFeature(FeatureLocation(i*20, i*20+12), type='gene', qualifiers={'label': [label]})
                           for i, label in enumerate(['mNeonGreen', 'NeoR/KanR', 'AMPK', 'AmpR'])]
        for query, expected in [('kan', 'NeoR/KanR'), ('neo', 'NeoR/KanR'), ('amp', 'AmpR')]:
            result = get_tool('get_feature').execute(file_path_or_record=record, name_or_type=query)
            self.assertEqual(result.analysis['matches'][0]['name'], expected)

    def test_duplicate_feature_identity_is_explicitly_ambiguous(self):
        record = self.source('ACGT'*20)
        record.features = [SeqFeature(FeatureLocation(i, i+9), type='gene', qualifiers={'label': ['choice']})
                           for i in (3, 21)]
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            get_tool('get_feature').execute(file_path_or_record=record, name_or_type='choice')
        result = get_tool('get_feature').execute(file_path_or_record=record, name_or_type='choice', return_all=True)
        self.assertEqual([str(p.seq) for p in result.products], ['TACGTACGT', 'CGTACGTAC'])

    def test_negative_join_through_terminal_change_fusion_and_readback(self):
        source = self.source('TTAAAACCCGTAGTTTCAT')
        source.features = [SeqFeature(CompoundLocation([FeatureLocation(13,19,strand=-1),
                           FeatureLocation(0,9,strand=-1)], operator='join'), type='CDS', qualifiers={'label':['target']})]
        original = copy.deepcopy(source)
        steps = [
            {'step_id':'selected','tool':'get_feature','params':{'file_path_or_record':'$input','name_or_type':'target'}},
            {'step_id':'trimmed','tool':'strip_terminal_codons','params':{'cds_seq':'$selected','strip_stop':True}},
            {'step_id':'fused','tool':'fuse_in_frame','params':{'partner5_seq':'$trimmed','partner3_seq':'GCT'}},
        ]
        product, _, environment = run_pipeline_steps(steps, {'input':source})
        self.assertEqual(str(environment['selected'].only_product().seq), 'ATGAAAGGGTTTTAA')
        self.assertEqual(str(product.seq), 'ATGAAAGGGTTTGCTTAA')
        self.assertEqual(str(product.features[-1].extract(product.seq)), 'ATGAAAGGGTTTGCTTAA')
        self.assertEqual(str(source.seq), str(original.seq))
        self.assertEqual(source.features, original.features)
        with tempfile.TemporaryDirectory(prefix='分子链 空格-') as tmp:
            files = export_snapgene(product, tmp, topology='linear').analysis
            for kind in ('gb_file', 'dna_file'):
                saved = resolve_sequence_record(Path(files[kind]))
                self.assertEqual(str(saved.seq), 'ATGAAAGGGTTTGCTTAA')
                self.assertEqual(saved.annotations['topology'], 'linear')
                self.assertEqual(saved.source_refs, product.source_refs)


class CandidateSearchFailures(unittest.TestCase):
    def test_original_valid_pair_is_not_lost_after_first_pair_failure(self):
        data = json.loads((SKILL_ROOT.parent/'tests/data/unified-qc-original.json').read_text(encoding='utf-8'))
        source = SeqRecord(Seq(data['sequence']), id='qc-input',
                           annotations={'molecule_type':'DNA', 'topology':'linear'})
        result = recipe_cloning_verification(source, data['insert_start'], data['insert_end'], diagnostic_enzymes=[])
        self.assertTrue(result.quality_checks['complete_oligo_structure_passed'])
        self.assertTrue(result.quality_checks['primer_dimers_safe'])
        self.assertLessEqual(result.quality_checks['colony_pcr_delta_tm'], 3)
        forward, reverse = result.primers[:2]
        top = data['sequence']
        self.assertEqual(top.count(forward['sequence']), 1)
        reverse_site = str(Seq(reverse['sequence']).reverse_complement())
        self.assertEqual(top.count(reverse_site), 1)
        begin, end = top.index(forward['sequence']), top.index(reverse_site) + len(reverse_site)
        self.assertEqual(end-begin, result.details['colony_pcr_primers']['expected_amplicon_size_bp'])
        self.assertEqual(result.quality_checks['pair_search']['status'], 'PASSED')


class IndependentContractBoundaries(unittest.TestCase):
    def material(self,sequence,topology='linear',ends=False):
        return Molecule(SeqRecord(Seq(sequence),id='independent',annotations={'molecule_type':'DNA','topology':topology}),
            strandedness='double',left_end=FragmentEnd('blunt',cut_boundary=0) if ends else None,
            right_end=FragmentEnd('blunt',cut_boundary=len(sequence)) if ends else None)

    def test_three_python_entrypoints_share_seq_and_failure_contract(self):
        from core.tools import translate_dna
        from core.tools.translation import translate_dna as module_call
        from core.errors import ToolExecutionError
        for call in (translate_dna,module_call,get_tool('translate_dna').execute):
            self.assertEqual(call(seq=Seq('ATGGCTTAA')).analysis['translation'],'MA*')
            with self.assertRaises(ToolExecutionError):call(seq='ATG',frame=7)

    def test_known_topology_and_end_geometry_survive_unrelated_edits(self):
        circle=self.material('ACGTTA','circular')
        self.assertEqual(str(get_tool('extract_subsequence').execute(file_path_or_record=circle,start=4,end=2).only_product().seq),'TAAC')
        source=self.material('AACCGGTT',ends=True)
        new=get_tool('mutate_sequence').execute(dna_seq=source,mutations=[{'position_0based':3,'alt_base':'T'}]).only_product()
        self.assertEqual((new.left_end.kind,new.right_end.kind),('blunt','blunt'))
        self.assertEqual(str(get_tool('fill_or_chew_overhang').execute(seq=new).only_product().seq),'AACTGGTT')
        source.dbxrefs=['BioProject:independent']
        rc=get_tool('reverse_complement').execute(seq=source).only_product()
        self.assertEqual(rc.dbxrefs,source.dbxrefs)

    def test_molecular_wire_does_not_mutate_source_and_roundtrips(self):
        source=self.material('acgt',ends=True)
        source.letter_annotations['quality']=[11,12,13,14]
        product=derived_molecule(copy.deepcopy(source),[source],operation='inspection_copy',strandedness='double',mappings=[{'start0':0}])
        wire=product.to_dict()
        self.assertEqual(as_molecule(wire).record_version,product.record_version)
        wire['source_refs'][0]['mapping']['start0']=2
        self.assertEqual(product.source_refs[0]['mapping']['start0'],0)
        with self.assertRaises(ValueError):as_molecule(wire)

    def test_invalid_annotation_boundaries_do_not_modify_input(self):
        source=self.material('ACGTACGT')
        before=source.record_version
        for start,end in ((-1,2),(2,10),(3,3),(5,2)):
            with self.assertRaises(ValueError):get_tool('annotate_feature').execute(record=source,name='site',start=start,end=end)
        self.assertEqual(source.record_version,before)

    def test_fuzzy_annotation_survives_overlap_and_save_read(self):
        first=self.material('GACTAGTCCGATAGCACCGGTTACGAAGTC')
        first.features=[SeqFeature(FeatureLocation(BeforePosition(2),AfterPosition(8),strand=1),type='misc_feature',qualifiers={'label':['fuzzy']})]
        second=self.material(str(first.seq[-15:])+'TACGATCCATGGCATCGGTA')
        product=get_tool('simulate_overlap_assembly').execute(fragments=[first,second],min_overlap=15,circular=False).only_product()
        self.assertEqual(str(product.seq),str(first.seq)+'TACGATCCATGGCATCGGTA')
        self.assertIsInstance(product.features[0].location.start,BeforePosition)
        with tempfile.TemporaryDirectory(prefix='模糊回读 ') as directory:
            files=export_snapgene(product.to_dict(),directory).analysis
            for key in ('gb_file','dna_file'):
                saved=as_molecule(Path(files[key]))
                self.assertIsInstance(saved.features[0].location.start,BeforePosition)
                self.assertIsInstance(saved.features[0].location.end,AfterPosition)

    def test_readback_refuses_hidden_metadata_overwrite_of_actual_file_edit(self):
        source=self.material('ACGTCAGATC')
        source.annotations.update(organism='OriginalTaxon',source='OriginalTaxon')
        source.description='original description'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(export_snapgene(source,directory).analysis['gb_file'])
            original=path.read_text(encoding='utf-8')
            path.write_text(original.replace('OriginalTaxon','RevisedTaxon'),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'information changed'):as_molecule(path)

    def test_digest_products_ligate_without_reintroducing_sites_or_losing_identity(self):
        source=self.material('GGGGAATTCTTTTTT',ends=True)
        cut=get_tool('digest_sequence').execute(seq=source,enzyme='EcoRI')
        product=get_tool('ligate_fragments').execute(fragments=cut.products).only_product()
        self.assertEqual(str(product.seq),'GGGGAATTCTTTTTT')
        self.assertEqual([r['record_version'] for r in product.source_refs],[m.record_version for m in cut.products])
        self.assertEqual(source.left_end.kind,'blunt')
        with self.assertRaises(ValueError):get_tool('ligate_fragments').execute(fragments=[self.material('ACGT'),cut.products[1]])

    def test_saved_first_round_is_actual_second_round_parent(self):
        source=self.material('ACGTACGTACGT',ends=True)
        first=get_tool('mutate_sequence').execute(dna_seq=source,mutations=[{'position_0based':3,'alt_base':'A'}]).only_product()
        with tempfile.TemporaryDirectory(prefix='连续版本 ') as directory:
            saved=as_molecule(Path(export_snapgene(first,directory).analysis['dna_file']))
            second=get_tool('mutate_sequence').execute(dna_seq=saved,mutations=[{'position_0based':7,'alt_base':'C'}]).only_product()
            self.assertEqual(str(second.seq),'ACGAACGCACGT')
            self.assertEqual(second.source_refs[0]['record_version'],saved.record_version)
            self.assertNotEqual(second.source_refs[0]['record_version'],source.record_version)
            self.assertEqual(str(source.seq),'ACGTACGTACGT')

    def test_rotation_preserves_feature_extraction_and_original_record(self):
        source=self.material('ACGTTAGGCA','circular')
        source.features=[SeqFeature(FeatureLocation(6,10,strand=-1),type='misc_feature',qualifiers={'label':['reverse']})]
        before=source.record_version
        product=get_tool('rotate_sequence').execute(dna_seq=source,origin_0based=8).only_product()
        self.assertEqual(str(product.seq),'CAACGTTAGG')
        self.assertEqual(str(product.features[0].extract(product.seq)),'TGCC')
        self.assertEqual(source.record_version,before)
        with self.assertRaises(ValueError):get_tool('rotate_sequence').execute(dna_seq=self.material('ACGT'),origin_0based=1)

    def test_json_translation_is_still_not_dna(self):
        from core.tools.result import to_wire
        protein=get_tool('translate_dna').execute(seq='ATGGCT').analysis['translation']
        restored=json.loads(json.dumps(to_wire(protein)))
        self.assertEqual(restored,{'data_type':'protein_sequence','value':'MA'})
        with self.assertRaises(ValueError):as_molecule(restored)

    def test_feature_selection_retains_partial_coding_boundary(self):
        source=self.material('GCTGCT')
        source.features=[SeqFeature(FeatureLocation(BeforePosition(0),6),type='CDS',qualifiers={'label':['partial']})]
        product=get_tool('get_feature').execute(file_path_or_record=source,name_or_type='partial').only_product()
        from core.tools.sequence_ops import validate_cds_feature
        self.assertIsInstance(product.features[0].location.start,BeforePosition)
        self.assertTrue(validate_cds_feature(product.features[0],product.seq)['valid'])

    def test_ligation_does_not_share_nested_source_annotations(self):
        source=self.material('AACCGG',ends=True)
        source.features=[SeqFeature(FeatureLocation(0,3),type='misc_feature',qualifiers={'label':['input']})]
        other=self.material('TTAGCC',ends=True)
        product=get_tool('ligate_fragments').execute(fragments=[source,other]).only_product()
        product.features[0].qualifiers['label'].append('edited output')
        self.assertEqual(source.features[0].qualifiers['label'],['input'])

    def test_feature_identity_and_visible_comment_survive_file_boundary(self):
        source=self.material('ACGTCAGATC')
        source.annotations['comment']='original visible comment'
        source.features=[SeqFeature(FeatureLocation(1,6),id='feature-identity',type='misc_feature',qualifiers={'label':['region']})]
        with tempfile.TemporaryDirectory() as directory:
            files=export_snapgene(source,directory).analysis
            for kind in ('gb_file','dna_file'):
                self.assertEqual(as_molecule(Path(files[kind])).features[0].id,'feature-identity')
            path=Path(files['gb_file']);text=path.read_text(encoding='utf-8')
            path.write_text(text.replace('original visible comment','changed visible comment'),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'information changed'):as_molecule(path)

    def test_native_annotation_edit_rebinds_real_metadata(self):
        rng=random.Random(91013)
        source=self.material(''.join(rng.choices('ACGT',k=140)),ends=True)
        from scripts.annotate_primers import annotate_primers_dna
        with tempfile.TemporaryDirectory(prefix='原文件引物 ') as directory:
            path=Path(export_snapgene(source,directory,'source').analysis['dna_file'])
            output=Path(directory)/'annotated.dna'
            annotate_primers_dna(path,output,'add',[{'name':'F','sequence':str(source.seq[:22]),
                'binding_sequence':str(source.seq[:22]),'binding_interval_0based':[0,22],'strand':1}])
            actual=as_molecule(output)
            self.assertEqual(str(actual.seq),str(source.seq))
            self.assertEqual(actual.features[-1].qualifiers['primer_sequence'],[str(source.seq[:22])])
            self.assertEqual(actual.operation,'primer_annotation_add')

    def test_real_pcr_digest_ligate_chain_and_annotation_equivalence(self):
        rng=random.Random(91013)
        sequence=''.join(rng.choices('ACGT',k=60))+'GAATTC'+''.join(rng.choices('ACGT',k=74))
        self.assertEqual(sequence.count('GAATTC'),1)
        source=self.material(sequence,ends=True)
        steps=[{'step_id':'pcr','tool':'simulate_pcr','params':{'template':source.to_dict(),
                'f_primer':sequence[:22],'r_primer':str(Seq(sequence[-22:]).reverse_complement())}},
               {'step_id':'digest','tool':'digest_sequence','params':{'seq':'$pcr','enzyme':'EcoRI'}},
               {'step_id':'join','tool':'ligate_fragments','params':{'fragments':['$digest.products.0','$digest.products.1']}},
               {'step_id':'annotation','tool':'annotate_feature','params':{'record':'$join','name':'region','start':40,'end':60}}]
        product,rows,env=run_pipeline_steps(steps,{})
        self.assertEqual(str(product.seq),sequence)
        self.assertEqual(str(env['digest'].products[0].seq)+str(env['digest'].products[1].seq),sequence)
        from core.handlers.composite_pipeline import _preparation_check
        self.assertEqual(_preparation_check(product,rows,{})['status'],'PASSED')
        self.assertEqual(len(source.features),0)

    def test_requirement_for_preparation_is_separate_from_sequence_edit(self):
        source=self.material('ACGTACGTACGT',ends=True)
        with tempfile.TemporaryDirectory(prefix='范围与版本 ') as directory:
            path=Path(export_snapgene(source,directory,'source').analysis['gb_file'])
            task={'task_kind':'composite_pipeline','sources':[{'source_id':'src','path':str(path),'role':'template',
                  'evidence':{'source_evidence_class':'user-provided'}}],
                  'pipeline':{'steps':[{'step_id':'edit','tool':'mutate_sequence','params':{'dna_seq':'$src','mutations':[{'position_0based':3,'alt_base':'A'}]}}]},
                  'product':{'topology':'linear','formats':['gb','fasta','dna']}}
            t,p=plan(task);e=execute(t,p,Path(directory)/'model');report=validate(t,p,e)
            self.assertEqual(report['overall'],'verified',report['errors'])
            self.assertEqual(report['scope_results']['preparation_model']['status'],'INCOMPLETE')
            task['validation_requirements']=['sequence_model','file','user_goal','preparation_model']
            t,p=plan(task);e=execute(t,p,Path(directory)/'preparation');report=validate(t,p,e)
            self.assertEqual(report['overall'],'failed')
            self.assertIn('VALIDATION_SCOPE_UNSATISFIED',report['error_codes'])
            # Tamper a consumed molecular field while leaving old plan hash.
            tampered=copy.deepcopy(p);tampered['product_molecule']['strandedness']='single'
            from core.errors import PlanningError
            with self.assertRaisesRegex(PlanningError,'plan_sha256'):execute(t,tampered,Path(directory)/'tampered')

    def test_legacy_plan_is_rejected_and_material_tampering_is_detected(self):
        source=self.material('ACGTACGTACGT',ends=True)
        with tempfile.TemporaryDirectory() as directory:
            source_path=Path(export_snapgene(source,directory,'source').analysis['gb_file'])
            task={'task_kind':'composite_pipeline','sources':[{'source_id':'src','role':'template','path':str(source_path),
                'evidence':{'source_evidence_class':'user-provided'}}],
                'pipeline':{'steps':[{'step_id':'p','tool':'extract_subsequence','params':{'file_path_or_record':'$src','start':0,'end':12}}]},
                'product':{'topology':'linear','formats':['gb','fasta','dna']}}
            t,p=plan(task)
            from core.runtime_plan import compute_plan_sha256
            old=copy.deepcopy(p);old.pop('product_molecule');old['plan_sha256']=compute_plan_sha256(old)
            from core.errors import PlanningError
            with self.assertRaisesRegex(PlanningError,'Regenerate'):
                execute(t,old,Path(directory)/'old')
            execution=execute(t,p,Path(directory)/'current')
            altered=copy.deepcopy(as_molecule(p['product_molecule']))
            altered.strandedness='single';altered.left_end=altered.right_end=None
            target=Path(execution['product_gb'])
            export_snapgene(altered,target.parent,target.stem,topology='linear')
            report=validate(t,p,execution)
            self.assertFalse(report['artifact_valid'])
            self.assertTrue(any('MOLECULAR_RETENTION_FAILED' in e for e in report['errors']),report['errors'])
            # Same DNA and strand, but fabricated exposed-end evidence must
            # also fail independently of the strandedness case above.
            altered=copy.deepcopy(as_molecule(p['product_molecule']))
            altered.left_end=FragmentEnd('blunt',cut_boundary=0)
            altered.right_end=FragmentEnd('blunt',cut_boundary=len(altered))
            export_snapgene(altered,target.parent,target.stem,topology='linear')
            report=validate(t,p,execution)
            self.assertFalse(report['artifact_valid'])
            self.assertTrue(any('exposed ends differ' in e for e in report['errors']),report['errors'])

    def test_failed_check_cannot_become_successful_selected_product(self):
        from core.handlers.composite_pipeline import CompositePipelineHandler
        source=self.material('ATGTAAGCTTAA')
        task={'pipeline':{'steps':[{'step_id':'product','tool':'extract_subsequence','params':{'file_path_or_record':source.to_dict(),'start':0,'end':12}},
                {'step_id':'frame','tool':'check_reading_frame','params':{'dna_seq':'$product'}}], 'output_step':'product'},'sources':[]}
        handler=CompositePipelineHandler();p=handler.plan(task)
        ok,_,errors=handler.validate_goal(task,p,{},as_molecule(p['product_molecule']),p['product_sequence'])
        self.assertFalse(ok)
        self.assertTrue(any('PROGRAM_CHECK_FAILED' in e for e in errors),errors)

    def test_analysis_and_multi_product_references_are_explicit(self):
        from core.errors import PlanningError
        source=self.material('GGGGAATTCTTTTTT',ends=True)
        steps=[{'step_id':'digest','tool':'digest_sequence','params':{'seq':source.to_dict(),'enzyme':'EcoRI'}}]
        with self.assertRaisesRegex(PlanningError,'explicit product'):run_pipeline_steps(steps,{})
        product,_,_=run_pipeline_steps(steps,{},'digest.products.1')
        self.assertEqual(str(product.seq),'AATTCTTTTTT')
        with self.assertRaises(PlanningError):run_pipeline_steps([{'step_id':'tm','tool':'calc_primer_tm','params':{'primer_seq':'ACGTACGT'}}],{})

    def test_independent_qc_success_exhaustion_and_incomplete_are_distinct(self):
        rng=random.Random(84110)
        sequence=''.join(rng.choices('ACGT',k=900))
        source=self.material(sequence,'circular')
        result=recipe_cloning_verification(source,300,650,diagnostic_enzymes=[])
        self.assertEqual(result.checks[0]['subject_version'],source.record_version)
        with self.assertRaisesRegex(ValueError,'QC_SEARCH_INCOMPLETE'):
            recipe_cloning_verification(source,300,650,diagnostic_enzymes=[],max_pair_checks=1)
        with self.assertRaises(ValueError):recipe_cloning_verification(self.material('A'*900,'circular'),300,650)


if __name__ == '__main__':
    unittest.main()
