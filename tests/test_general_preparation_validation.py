"""Preparation invariants derived from new synthetic inputs and ordered oligos."""
import copy
import pathlib
import random
import tempfile
import unittest

from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from scripts.run_recipe import write_preparation_artifacts


class GeneralPreparationValidationTests(unittest.TestCase):
    @staticmethod
    def pcr_row():
        sequence=''.join(random.Random(191784).choices('ACGT',k=450))
        source=SeqRecord(Seq(sequence),id='independent_source',
                         annotations={'molecule_type':'DNA','topology':'linear'})
        forward=sequence[80:104]
        reverse=str(Seq(sequence[316:340]).reverse_complement())
        return {'id':'independent_preparation','method':'PCR','template':source,
                'product':{'sequence':sequence[80:340],'topology':'linear'},
                'primers':[
                    {'name':'F','sequence':forward,'binding_sequence':forward,
                     'binding_interval_0based':[80,104],'strand':1},
                    {'name':'R','sequence':reverse,'binding_sequence':reverse,
                     'binding_interval_0based':[316,340],'strand':-1}]}

    def test_actual_oligos_produce_the_declared_fragment(self):
        row=self.pcr_row()
        with tempfile.TemporaryDirectory() as temp:
            result=write_preparation_artifacts([row],temp)
            self.assertEqual(len(result['steps']),1)

    def test_unknown_method_cannot_bypass_pcr_product_checks(self):
        row=self.pcr_row()
        row['method']='custom_pcr'
        product=row['product']['sequence']
        row['product']['sequence']=product[:-1]+('A' if product[-1]!='A' else 'C')
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                write_preparation_artifacts([row],temp)
            self.assertEqual(list(pathlib.Path(temp).iterdir()),[])

    @staticmethod
    def quikchange_row():
        sequence=''.join(random.Random(981407).choices('ACGT',k=480))
        original=sequence[150:153]
        changed='CCC' if original!='CCC' else 'AAA'
        reference=sequence[130:173]
        forward=sequence[130:150]+changed+sequence[153:173]
        reverse=str(Seq(forward).reverse_complement())
        return {'id':'independent_mutation','method':'quikchange',
                'template':{'sequence':sequence,'topology':'circular'},
                'product':{'sequence':sequence[:150]+changed+sequence[153:],
                           'topology':'circular','evidence':{
                               'reference_segment':reference,
                               'mutant_segment_from_primers':forward}},
                'primers':[
                    {'name':'F','sequence':forward,'binding_sequence':sequence[153:173],
                     'binding_interval_0based':[153,173],'strand':1,
                     'left_flank':sequence[130:150],'right_flank':sequence[153:173]},
                    {'name':'R','sequence':reverse,'binding_sequence':str(Seq(sequence[130:150]).reverse_complement()),
                     'binding_interval_0based':[130,150],'strand':-1}]}

    def test_quikchange_product_must_come_from_the_actual_mutagenic_oligos(self):
        row=self.quikchange_row()
        row['product']['sequence']=str(row['template']['sequence'])
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'PREPARATION_PRODUCT_MISMATCH'):
                write_preparation_artifacts([row],temp)
            self.assertEqual(list(pathlib.Path(temp).iterdir()),[])

    def test_quikchange_valid_input_indel_and_circular_origin_are_preserved(self):
        row=self.quikchange_row()
        for variant in ('original','indel','rotated'):
            current=copy.deepcopy(row)
            if variant=='indel':
                source=current['template']['sequence']
                forward=source[130:150]+'AAAAAAA'+source[153:173]
                current['primers'][0]['sequence']=forward
                current['primers'][1]['sequence']=str(Seq(forward).reverse_complement())
                current['product']['sequence']=source[:150]+'AAAAAAA'+source[153:]
            elif variant=='rotated':
                origin=141
                for field in ('template','product'):
                    sequence=current[field]['sequence']
                    current[field]['sequence']=sequence[origin:]+sequence[:origin]
                for primer in current['primers']:
                    primer['binding_interval_0based']=[(i-origin)%480 for i in primer['binding_interval_0based']]
                    primer['position_0based']={'start_0based':9,'end_0based':12}
            with self.subTest(variant=variant),tempfile.TemporaryDirectory() as temp:
                result=write_preparation_artifacts([current],temp)
                self.assertEqual(len(result['steps']),1)

    def test_material_names_do_not_select_a_preparation_answer(self):
        from Bio import SeqIO
        for name in ('source_01','pYTK096','previous-answer','arbitrary_sample'):
            row=self.pcr_row()
            row['template'].id=name
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                source=pathlib.Path(temp)/(name+'.gb')
                with source.open('w',encoding='utf-8') as handle:
                    SeqIO.write(row['template'],handle,'genbank')
                row['template']=source
                result=write_preparation_artifacts([row],pathlib.Path(temp)/'delivery')
                with pathlib.Path(result['steps'][0]['product']['gb_file']).open(encoding='utf-8') as handle:
                    self.assertEqual(str(SeqIO.read(handle,'genbank').seq),row['product']['sequence'])

    def test_invalid_goal_schema_does_not_leave_a_predecessor_receipt(self):
        from scripts.run_recipe import run_recipe_cli
        params={'target_cds_seq_or_file':'ATGAAACCCGGGTTTTAA','tag_name_or_seq':'6xHis'}
        with tempfile.TemporaryDirectory() as temp:
            run_recipe_cli('protein_tagging',params,temp)
            receipt=pathlib.Path(temp)/'candidate/recipe_protein_tagging_result.json'
            self.assertTrue(receipt.exists())
            with self.assertRaises(ValueError):
                run_recipe_cli('protein_tagging',{**params,'expected_components':'invalid-list'},temp)
            self.assertFalse(receipt.exists())

    def test_primer_report_uses_recorded_method_tm_and_does_not_invent_zero(self):
        from core.recipes.contract import RecipeResult
        from scripts.run_recipe import format_markdown_summary
        primer={'name':'independent_oligo','sequence':'ACGTACGTACGTACGTAC','qc_tm':79.4}
        recipe=RecipeResult(recipe_name='report_fixture',result_kind='component',
                            completeness='component_only',primers=[primer])
        data={'recipe_result':recipe,'sanity_check':{},'recipe':'report_fixture',
              'result_kind':'component','completeness':'component_only',
              'product_length':0,'candidate_directory':'fixture',
              'goal_check':{'status':'not_requested'}}
        self.assertIn('| 79.4 |',format_markdown_summary(data))
        del primer['qc_tm']
        self.assertIn('| not provided |',format_markdown_summary(data))

    def test_public_quikchange_runner_exports_actual_mutagenic_primers_on_source(self):
        from Bio import SeqIO
        from scripts.run_recipe import run_recipe_cli
        row=self.quikchange_row()
        with tempfile.TemporaryDirectory() as temp:
            result=run_recipe_cli('site_directed_mutagenesis',{
                'template_seq_or_file':row['template'],'start_0based':150,'end_0based':153,
                'alt_seq':row['product']['sequence'][150:153],
                'target_flank_bp':20,'method':'quikchange'},temp)
            candidate=pathlib.Path(result['candidate_directory'])/'recipe_site_directed_mutagenesis.gb'
            with candidate.open(encoding='utf-8') as handle:
                self.assertEqual(str(SeqIO.read(handle,'genbank').seq),row['product']['sequence'])
            source_path=pathlib.Path(result['preparation_files']['steps'][0]['annotated_source']['gb_file'])
            with source_path.open(encoding='utf-8') as handle:
                source=SeqIO.read(handle,'genbank')
            self.assertEqual(str(source.seq),row['template']['sequence'])
            annotations=[f for f in source.features if f.type=='primer_bind']
            self.assertEqual(len(annotations),2)
            expected={row['template']['sequence'][153:173],str(Seq(row['template']['sequence'][130:150]).reverse_complement())}
            self.assertEqual({str(f.extract(source.seq)) for f in annotations},expected)
