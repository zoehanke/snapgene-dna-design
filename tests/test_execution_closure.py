"""Independent public-entry regressions for actual execution and delivery."""
from repository_paths import SKILL_ROOT
import copy
import json
import random
import tempfile
import unittest
from pathlib import Path
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation, CompoundLocation
from core.tools import simulate_overlap_assembly


class LongOverlapTests(unittest.TestCase):
    def test_uncapped_overlap_from_independent_fragment_relationship(self):
        for length in (40,60,61,80,150,2000):
            rng=random.Random(911+length)
            overlap=''.join(rng.choices('ACGT',k=length))
            first=SeqRecord(Seq('AAAA'+overlap),annotations={'molecule_type':'DNA','topology':'linear'})
            second=SeqRecord(Seq(overlap+'CCCC'),annotations={'molecule_type':'DNA','topology':'linear'})
            second.features=[SeqFeature(CompoundLocation([FeatureLocation(length,length+2,strand=-1),
                FeatureLocation(length+2,length+4,strand=-1)]),type='misc_feature',qualifiers={'label':['retained']})]
            with self.subTest(length=length):
                result=simulate_overlap_assembly([first,second],min_overlap=length,circular=False)
                self.assertEqual(str(result.only_product().seq),'AAAA'+overlap+'CCCC')
                self.assertEqual(result.analysis['junctions'][0]['overlap_length'],length)
                self.assertEqual(str(result.only_product().features[0].extract(result.only_product().seq)),'GGGG')
                self.assertEqual(str(first.seq),'AAAA'+overlap)

    def test_no_match_and_full_consumption_are_not_preparation(self):
        for fragments in (['AAAACCCC','GGGGTTTT'],['AAAACCCC','CCCC'],['ACGT'*30,'ACGT'*30]):
            with self.subTest(fragments=fragments),self.assertRaises(ValueError):
                simulate_overlap_assembly(fragments,min_overlap=4,circular=False)


class MixedStepsTests(unittest.TestCase):
    def test_material_alias_does_not_replace_ordinary_names(self):
        from core.workflow import run_step
        source=SeqRecord(Seq('ATGGCTTAA'),annotations={'molecule_type':'DNA','topology':'linear'})
        sources={'domain':source}
        step=run_step('annotate_feature',{'record':'domain','name':'domain','feature_type':'misc_feature',
                       'start':0,'end':9,'strand':1},sources=sources)
        self.assertEqual(step.status,'completed',step.error)
        self.assertEqual(step.result.only_product().features[-1].qualifiers['label'],['domain'])

    def test_atomic_recipe_and_analysis_keep_actual_material_and_metadata(self):
        from core.workflow import run_step
        source=SeqRecord(Seq('ATGGCTTAA'),id='coding',annotations={'molecule_type':'DNA','topology':'linear'})
        first=run_step('extract_subsequence',{'source':'$input','start':0,'end':9},step_id='selected',sources={'input':source})
        self.assertEqual(first.status,'completed',first.error)
        recipe=run_step('recipe_protein_tagging',{'target_cds_seq_or_file':'$selected','tag_name_or_seq':'6xHis'},
                        step_id='tagged',sources={'input':source},previous=[first])
        self.assertEqual(recipe.status,'completed',recipe.error)
        self.assertEqual(recipe.result.analysis['result_kind'],'component')
        self.assertTrue(recipe.result.analysis['citations'])
        self.assertTrue(recipe.operations)
        analysis=run_step('calc_primer_tm',{'primer_seq':'AACCGGAACCGG'},step_id='temperature',sources={'input':source},previous=[first,recipe])
        self.assertEqual(analysis.result.products,[])
        fail=run_step('extract_subsequence',{'source':'$not-recorded','start':0,'end':3},sources={'input':source},previous=[first,recipe])
        self.assertEqual(fail.status,'failed')
        self.assertEqual(fail.error['error_code'],'UNRESOLVED_STEP_REFERENCE')
        self.assertEqual(str(first.result.only_product().seq),'ATGGCTTAA')

    def test_recipe_is_composable_in_existing_pipeline(self):
        from core.handlers.composite_pipeline import run_pipeline_steps
        source=SeqRecord(Seq('ATGGCTTAA'),id='coding',annotations={'molecule_type':'DNA','topology':'linear'})
        product,rows,env=run_pipeline_steps([
            {'step_id':'tagged','tool':'recipe_protein_tagging','params':{'target_cds_seq_or_file':'$input','tag_name_or_seq':'6xHis'}},
            {'step_id':'result','tool':'strip_terminal_codons','params':{'cds_seq':'$tagged'}}],{'input':source})
        self.assertTrue(str(product.seq).startswith('ATGGCT'))
        self.assertEqual(len(rows),2)
        self.assertEqual(env['tagged'].analysis['completeness'],'component_only')


class CandidateChecksTests(unittest.TestCase):
    def test_actual_annealing_orders_preserve_synthesis_role_and_missing_reagent_fails(self):
        from core.workflow import run_step
        from core.workflow_delivery import deliver_result
        from core.workflow_validation import validate_candidate
        top='ACGTTGCAACCGTTAAGCGT'
        bottom=str(Seq(top).reverse_complement())
        step=run_step('anneal_oligos',{'top_oligo':top,'bottom_oligo':bottom},step_id='duplex',sources={})
        self.assertEqual(step.status,'completed',step.error)
        candidate=step.result.only_product()
        requirement={'topology':'linear','expected_sequence':top}
        rejected=validate_candidate(requirement,{},[step],candidate,primers=[],required_scopes=['sequence_model','preparation_model','user_goal'])
        self.assertIn('MISSING_FINAL_SYNTHESIS_OLIGO',rejected['errors'])
        with tempfile.TemporaryDirectory() as temp:
            result=deliver_result(requirement,{},[step],candidate,temp)
            import csv
            with (Path(result['directory'])/'oligo_order_table.tsv').open(encoding='utf-8') as stream:
                orders=list(csv.DictReader(stream,delimiter='\t'))
            self.assertEqual({p['sequence_5to3'] for p in orders},{top,bottom})
            self.assertEqual({p['role'] for p in orders},{'synthesis'})

    def test_trace_direct_workflow_return_records_real_scopes_and_final_files(self):
        from evidence_trace.runtime import traced_run
        from unittest.mock import patch
        from core.workflow import run_step
        from core.workflow_delivery import deliver_result
        import json
        seq='ATGCGATTGCGCATGCCGTA'
        step=run_step('anneal_oligos',{'top_oligo':seq,'bottom_oligo':str(Seq(seq).reverse_complement())},sources={})
        @traced_run('workflow')
        def execute(out_dir):
            return deliver_result({'topology':'linear'}, {},[step],step.result.only_product(),out_dir)
        with tempfile.TemporaryDirectory() as temp,patch('evidence_trace.runtime.get_level',return_value='observed'):
            execute(temp)
            events=[json.loads(line) for line in (Path(temp)/'evidence-trace/events.jsonl').read_text(encoding='utf-8').splitlines()]
            nodes=[e['payload'] for e in events if e.get('event_type')=='node_recorded']
            self.assertEqual(len([n for n in nodes if n['kind']=='artifact' and n.get('role')=='authoritative']),3)
            self.assertEqual(len([n for n in nodes if n['kind']=='validation']),4)
            self.assertTrue(all(n['result']=='passed' for n in nodes if n['kind']=='validation'))

    def test_history_wrong_source_unbound_fragments_and_lost_letters_are_rejected(self):
        from core.workflow import run_step
        from core.workflow_validation import validate_candidate
        seq=''.join(random.Random(979716).choices('ACGT',k=280))
        source=SeqRecord(Seq(seq),id='original',annotations={'molecule_type':'DNA','topology':'linear'})
        source.letter_annotations['quality']=[32]*280
        sources={'source':source}
        pcr=run_step('simulate_pcr',{'template':'$source','f_primer':seq[20:40],
            'r_primer':str(Seq(seq[240:260]).reverse_complement())},step_id='pcr',sources=sources)
        changed=copy.deepcopy(source);changed.letter_annotations['quality']=[9]*280
        resumed=run_step('strip_terminal_codons',{'cds_seq':'$pcr'},step_id='next',sources={'source':changed},previous=[pcr])
        self.assertEqual(resumed.status,'failed')
        lost=copy.deepcopy(pcr.result.only_product());lost.letter_annotations.clear()
        required=['sequence_model','preparation_model','user_goal']
        report=validate_candidate({'topology':'linear'},sources,[pcr],lost,required_scopes=required)
        self.assertEqual(report['overall'],'failed')
        unbound=run_step('simulate_overlap_assembly',{'fragments':['AAAACCCC','CCCCGGGG'],'min_overlap':4,'circular':False},
                        step_id='unbound',sources=sources)
        report=validate_candidate({'topology':'linear'},sources,[unbound],unbound.result.only_product(),required_scopes=required)
        self.assertEqual(report['overall'],'failed')
        wrong_roles=[{**p,'role':'qc'} for p in pcr.result.analysis['primers']]
        report=validate_candidate({'topology':'linear'},sources,[pcr],pcr.result.only_product(),primers=wrong_roles,required_scopes=required)
        self.assertEqual(report['scope_results']['preparation_model']['status'],'FAILED')

    def test_declared_intermediate_orders_records_and_extensions_are_bound(self):
        from core.workflow import run_step
        from core.workflow_validation import validate_candidate
        from core.tools import export_snapgene
        seq=''.join(random.Random(345673).choices('ACGT',k=280))
        source=SeqRecord(Seq(seq),id='original',annotations={'molecule_type':'DNA','topology':'linear'})
        sources={'source':source}
        pcr=run_step('simulate_pcr',{'template':'$source','f_primer':seq[20:40],
            'r_primer':str(Seq(seq[240:260]).reverse_complement())},step_id='pcr',sources=sources)
        primers=[{**p,'role':'preparation'} for p in pcr.result.analysis['primers']]
        with tempfile.TemporaryDirectory() as temp:
            template_files=export_snapgene(source,Path(temp)/'template').analysis
            cases=[('intermediates/preparation_01.gb',Path(template_files['gb_file']),None),
                   ('construct.gb',Path(temp)/'not-DNA.txt','not DNA'),
                   ('execution.json',Path(temp)/'execution.json','[]'),
                   ('requirements.json',Path(temp)/'requirements.json','{"expected_sequence":"AAA"}'),
                   ('oligo_order_table.tsv',Path(temp)/'order.tsv','name\tsequence_5to3\trole\nwrong\tAAAA\tpreparation\n'),
                   ('design.md',Path(temp)/'design.md','old unrelated design'),
                   ('validation.json',Path(temp)/'validation.json','{"overall":"verified"}')]
            for name,path,text in cases:
                if text is not None:path.write_text(text,encoding='utf-8')
                report=validate_candidate({'topology':'linear'},sources,[pcr],pcr.result.only_product(),
                     primers=primers,files={name:str(path)})
                self.assertEqual(report['scope_results']['file']['status'],'FAILED',name)

    def test_long_qualifier_roundtrip_restores_only_authenticated_content(self):
        from core.tools import export_snapgene
        from core.models.molecule import as_molecule
        source=SeqRecord(Seq('ATGGCTTAA'),id='source',annotations={'molecule_type':'DNA','topology':'linear'})
        label='long_oligo_name_'+'continuity'*14
        source.features=[SeqFeature(FeatureLocation(0,9,strand=1),type='misc_feature',qualifiers={'label':[label]})]
        with tempfile.TemporaryDirectory() as temp:
            files=export_snapgene(source,temp).analysis
            saved=as_molecule(files['gb_file'])
            self.assertEqual(saved.features[0].qualifiers['label'],[label])
            path=Path(files['gb_file'])
            original=path.read_text(encoding='utf-8')
            path.write_text(original.replace('/label="long_oligo_name_','/label="changed_oligo_name_',1),encoding='utf-8')
            with self.assertRaisesRegex(Exception,'changed|metadata'):
                as_molecule(path)

    def test_unstranded_genbank_normalization_is_not_reported_lossless(self):
        from core.workflow import run_step
        from core.workflow_validation import validate_candidate
        from core.tools import export_snapgene
        source=SeqRecord(Seq('ATGGCTTAA'),annotations={'molecule_type':'DNA','topology':'linear'})
        # Preserve the initially encountered legal but unrepresentable None strand case.
        source.features=[SeqFeature(FeatureLocation(0,9),type='misc_feature',qualifiers={'label':['unstranded']})]
        sources={'source':source}
        step=run_step('strip_terminal_codons',{'cds_seq':'$source'},step_id='copy',sources=sources)
        with tempfile.TemporaryDirectory() as temp:
            files=export_snapgene(step.result.only_product(),temp).analysis
            report=validate_candidate({'topology':'linear'},sources,[step],step.result.only_product(),
                                      files={'gb_file':files['gb_file']},required_scopes=['sequence_model','file','user_goal'])
            self.assertEqual(report['scope_results']['file']['status'],'FAILED')

    def test_actual_chain_wrong_product_and_fake_checks(self):
        from core.workflow import run_step
        from core.workflow_validation import validate_candidate
        sequence=''.join(random.Random(875123).choices('ACGT',k=240))
        source=SeqRecord(Seq(sequence),id='template',annotations={'molecule_type':'DNA','topology':'linear'})
        sources={'input':source}
        pcr=run_step('simulate_pcr',{'template':'$input','f_primer':sequence[20:40],
                     'r_primer':str(Seq(sequence[200:220]).reverse_complement())},step_id='amplified',sources=sources)
        self.assertEqual(pcr.status,'completed',pcr.error)
        selected=pcr.result.only_product()
        required=['sequence_model','preparation_model','user_goal']
        report=validate_candidate({'topology':'linear'},sources,[pcr],selected,required_scopes=required)
        # Preserve the original input. Frozen 2.1.0 Primer3 independently
        # measures its forward hairpin at 51.27 C, above the unchanged 47 C
        # default; reaction identity is valid but full preparation is not.
        self.assertEqual(report['scope_results']['sequence_model']['status'],'PASSED')
        self.assertEqual(report['scope_results']['preparation_model']['status'],'FAILED')
        self.assertIn('OLIGO_QUALITY_FAILED', str(report['errors']))
        wrong=copy.deepcopy(selected)
        wrong.seq=Seq(str(wrong.seq)[:-1]+('A' if str(wrong.seq)[-1]!='A' else 'C'))
        report=validate_candidate({'topology':'linear'},sources,[pcr],wrong,required_scopes=required)
        self.assertEqual(report['scope_results']['sequence_model']['status'],'FAILED')

        fake=pcr.to_dict()
        fake['result']['checks'][0]['status']='FAILED'
        report=validate_candidate({'topology':'linear'},sources,[fake],selected,required_scopes=required)
        self.assertEqual(report['scope_results']['sequence_model']['status'],'FAILED')
        altered=copy.deepcopy(source)
        altered.features=[SeqFeature(FeatureLocation(0,10),type='misc_feature',qualifiers={'label':['changed-source']})]
        report=validate_candidate({'topology':'linear'},{'input':altered},[pcr],selected,required_scopes=required)
        self.assertEqual(report['scope_results']['sequence_model']['status'],'FAILED')

    def test_delivery_replays_and_keeps_one_current_bundle(self):
        from core.workflow import run_step
        from core.workflow_delivery import deliver_result
        from core.workflow_validation import validate_candidate
        from core.models.molecule import as_molecule
        from core.tools import export_snapgene
        seq=''.join(random.Random(88119).choices('ACGT',k=300))
        source=SeqRecord(Seq(seq),id='template',annotations={'molecule_type':'DNA','topology':'linear'})
        source.features=[SeqFeature(FeatureLocation(40,55,strand=1),type='misc_feature',qualifiers={'label':['source-domain']})]
        sources={'source':source}
        pcr=run_step('simulate_pcr',{'template':'$source','f_primer':seq[20:40],
            'r_primer':str(Seq(seq[260:280]).reverse_complement())},step_id='pcr',sources=sources)
        self.assertEqual(pcr.status,'completed',pcr.error)
        product=pcr.result.only_product()
        with tempfile.TemporaryDirectory(prefix='闭环 空格') as temp:
            files=export_snapgene(product,Path(temp)/'checked').analysis
            checked=validate_candidate({'topology':'linear'},sources,[pcr],product,
                     files={k:v for k,v in files.items() if k in ('gb_file','dna_file','fasta_file')})
            self.assertEqual(checked['overall'],'verified',checked['errors'])
            try:
                delivery=deliver_result({'topology':'linear'},sources,[pcr],product,Path(temp)/'delivery',validation=checked)
            except Exception as exc:
                self.fail(str(getattr(exc,'details',{}).get('validation',{}).get('errors',exc)))
            actual=Path(delivery['directory'])
            self.assertEqual(str(as_molecule(actual/'construct.gb').seq),seq[20:280])
            self.assertTrue((actual/'oligo_order_table.tsv').is_file())
            self.assertTrue((actual/'design.md').is_file())
            self.assertTrue(list((actual/'annotated_sources').glob('*.gb')))
            with (actual/'oligo_order_table.tsv').open(encoding='utf-8') as handle:
                import csv
                orders=list(csv.DictReader(handle,delimiter='\t'))
            document=(actual/'design.md').read_text(encoding='utf-8')
            self.assertTrue(all(row['sequence_5to3'] in document for row in orders))
            import hashlib
            self.assertEqual(hashlib.sha256((actual/'construct.dna').read_bytes()).hexdigest(),
                             delivery['validation']['artifact_hashes']['construct.dna'])
            Path(files['gb_file']).write_text('modified',encoding='utf-8')
            with self.assertRaisesRegex(Exception,'Checked file changed'):
                deliver_result({'topology':'linear'},sources,[pcr],product,Path(temp)/'stale',validation=checked)
