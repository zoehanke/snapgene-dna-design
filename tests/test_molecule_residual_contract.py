"""Source-derived regressions for the v2 residual public-contract defects."""
from repository_paths import SKILL_ROOT
import copy
import json
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation, CompoundLocation, BeforePosition, AfterPosition, ExactPosition
from core.models.molecule import Molecule, as_molecule
from core.models.assembly_model import FragmentEnd
from core.tools import (calc_primer_tm, check_primer_dimers, fill_or_chew_overhang,
                        ligate_fragments, get_feature, get_tool, strip_terminal_codons,
                        rotate_sequence, export_snapgene, extract_subsequence)


def duplex(sequence, topology='linear'):
    record = SeqRecord(Seq(sequence), id='source', name='source', dbxrefs=['DB:1'],
                       annotations={'molecule_type':'DNA', 'topology':topology,
                                    'nested':{'values':['original']}})
    record.features = [SeqFeature(FeatureLocation(0,3), type='misc_feature',
                                 qualifiers={'label':['tag'], 'nested':['original']})]
    record.letter_annotations['position'] = list(range(len(record)))
    return Molecule(record, strandedness='double',
                    left_end=FragmentEnd('blunt',cut_boundary=0) if topology=='linear' else None,
                    right_end=FragmentEnd('blunt',cut_boundary=len(record)) if topology=='linear' else None)


class ResidualInputAndOwnership(unittest.TestCase):
    def test_primer_input_representations_and_independent_risks(self):
        # Complementary 20 nt oligos versus poly-A pairs have independently known 20/0 matches.
        for first,second,match in [('AAAACCCCGGGGTTTTACGT','ACGTAAAACCCCGGGGTTTT',20),('AAAAAAAAAAAA','AAAAAAAAAAAA',0)]:
            with tempfile.TemporaryDirectory(prefix='引物 空格') as temp:
                paths=[]
                for i,seq in enumerate((first,second)):
                    path=Path(temp)/f'{i}.gb'
                    with path.open('w',encoding='utf-8') as handle:
                        SeqIO.write(duplex(seq),handle,'genbank')
                    paths.append(path)
                values=[(first,second),(duplex(first),duplex(second)),
                        (duplex(first).to_dict(),duplex(second).to_dict()),tuple(paths)]
                for a,b in values:
                    for function in (check_primer_dimers,get_tool('check_primer_dimers').execute):
                        result=function(primer1=a,primer2=b).analysis
                        self.assertEqual(result['primer1_length'],len(first))
                        self.assertEqual(result['max_continuous_complementarity'],match)
                        self.assertEqual(result['high_dimer_risk'],bool(match))
                    for function in (calc_primer_tm,get_tool('calc_primer_tm').execute):
                        self.assertEqual(function(primer_seq=a).analysis,calc_primer_tm(first).analysis)
        for bad in ({'sequence':'EFIL'}, {'sequence':'ACGT','coordinate_system':'1-based'}, {'wrong':'ACGT'}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                check_primer_dimers(bad)

    def test_end_repair_owns_metadata_and_new_positions_are_unknown(self):
        for extension in ('','AG'):
            source=duplex('AACCGG')
            if extension:
                source.right_end=FragmentEnd("5'-overhang",extension,cut_boundary=6)
            version=source.record_version
            product=fill_or_chew_overhang(source).only_product()
            self.assertEqual(str(product.seq),'AACCGG'+('CT' if extension else ''))
            self.assertEqual(product.letter_annotations['position'],list(range(6))+([None,None] if extension else []))
            self.assertEqual(product.dbxrefs,['DB:1'])
            product.annotations['nested']['values'].append('changed')
            product.features[0].qualifiers['nested'].append('changed')
            product.left_end.cut_boundary=1
            self.assertEqual(source.record_version,version)
            self.assertEqual(product.source_refs[0]['record_version'],version)
        with self.assertRaises(ValueError):
            fill_or_chew_overhang(duplex('AACCGG','circular'))

    def test_ligation_maps_letters_and_discloses_record_conflicts(self):
        a,b=duplex('ACGTTGCAAGTC'),duplex('TTGACCAA')
        b.annotations['nested']={'values':['other']}
        b.dbxrefs=['DB:2']
        b.letter_annotations.clear()
        b.letter_annotations['quality']=[31]*8
        versions=[a.record_version,b.record_version]
        result=ligate_fragments([a,b])
        product=result.only_product()
        self.assertEqual(str(product.seq),'ACGTTGCAAGTCTTGACCAA')
        self.assertEqual(product.letter_annotations['position'],list(range(12))+[None]*8)
        self.assertEqual(product.letter_annotations['quality'],[None]*12+[31]*8)
        self.assertEqual(product.dbxrefs,['DB:1','DB:2'])
        self.assertNotIn('nested',product.annotations)
        self.assertIn('nested',result.analysis['annotation_conflicts'])
        self.assertEqual([ref['record_version'] for ref in product.source_refs],versions)
        product.features[0].qualifiers['nested'].append('changed')
        self.assertEqual([a.record_version,b.record_version],versions)
        product2=ligate_fragments([a,a]).only_product()
        self.assertEqual(product2.letter_annotations['position'],list(range(12))*2)
        product2.annotations['nested']['values'].append('changed')
        self.assertEqual(a.record_version,versions[0])


class ResidualLocationsAndState(unittest.TestCase):
    def test_repeated_extracted_intervals_cannot_hide_missing_feature_bases(self):
        source=duplex('ATGCCCTAA')
        source.features=[SeqFeature(CompoundLocation([FeatureLocation(0,3),FeatureLocation(0,3),FeatureLocation(3,6)]),
                                    type='misc_feature',qualifiers={'label':['selected']}),
                         SeqFeature(FeatureLocation(0,9),type='misc_feature',qualifiers={'label':['nested']})]
        product=get_feature(source,'selected').only_product()
        nested=[f for f in product.features if f.qualifiers['label']==['nested']][0]
        self.assertEqual(str(product.seq),'ATGATGCCC')
        self.assertEqual(nested.qualifiers.get('partial'),['true'])

    def test_compound_clipping_retains_cds_phase_and_removes_whole_translation(self):
        source=duplex('AAATGCCCTAA')
        source.features=[SeqFeature(CompoundLocation([FeatureLocation(4,7),FeatureLocation(8,11)]),
                                    type='misc_feature',qualifiers={'label':['selection']}),
                         SeqFeature(FeatureLocation(2,11),type='CDS',qualifiers={
                             'label':['coding'], 'codon_start':['1'], 'translation':['MP']})]
        product=get_feature(source,'selection').only_product()
        coding=[f for f in product.features if f.type=='CDS'][0]
        self.assertEqual(str(product.seq),'GCCTAA')
        self.assertEqual(coding.qualifiers['partial'],['true'])
        self.assertEqual(coding.qualifiers['codon_start'],['2'])
        self.assertNotIn('translation',coding.qualifiers)

    def test_compound_nested_features_are_rebuilt_once(self):
        for strand in (1,-1):
            record=duplex('ATGCCCTAA')
            parts=[FeatureLocation(0,3,strand=strand),FeatureLocation(6,9,strand=strand)]
            if strand==-1: parts.reverse()
            location=CompoundLocation(parts)
            record.features=[SeqFeature(location,type='misc_feature',qualifiers={'label':['selected']}),
                             SeqFeature(copy.deepcopy(location),type='misc_feature',qualifiers={'label':['nested']}),
                             SeqFeature(FeatureLocation(1,8,strand=strand),type='misc_feature',qualifiers={'label':['clipped']})]
            product=get_feature(record,'selected').only_product()
            nested=[f for f in product.features if f.qualifiers['label']==['nested']]
            self.assertEqual(len(nested),1)
            self.assertNotIn('partial',nested[0].qualifiers)
            self.assertEqual(str(nested[0].extract(product.seq)), 'ATGTAA' if strand==1 else 'TTACAT')
            clipped=[f for f in product.features if f.qualifiers['label']==['clipped']]
            self.assertEqual(len(clipped),1)
            self.assertEqual(clipped[0].qualifiers['partial'],['true'])

    def test_noop_codon_strip_preserves_physical_state(self):
        for topology in ('linear','circular'):
            for sequence,flags in [('ATGCCCTAA',{}),('ACGCCCAAC',{'strip_start':True,'strip_stop':True})]:
                source=duplex(sequence,topology)
                version=source.record_version
                product=strip_terminal_codons(source,**flags).only_product()
                self.assertEqual(product.topology,topology)
                self.assertEqual(product.left_end.to_dict() if product.left_end else None,
                                 source.left_end.to_dict() if source.left_end else None)
                self.assertEqual(product.right_end.to_dict() if product.right_end else None,
                                 source.right_end.to_dict() if source.right_end else None)
                product.annotations['nested']['values'].append('changed')
                self.assertEqual(source.record_version,version)
                if topology=='linear':
                    self.assertEqual(str(ligate_fragments([product,source]).only_product().seq),sequence*2)
        source=duplex('ATGCCCTAA','circular')
        product=strip_terminal_codons(source,strip_start=True,strip_stop=True).only_product()
        self.assertEqual(str(product.seq),'CCC')
        self.assertEqual(product.topology,'linear')
        self.assertIsNone(product.left_end)
        self.assertEqual(product.letter_annotations['position'],[3,4,5])

    def test_rotation_preserves_only_original_fuzzy_boundaries_and_readback(self):
        for strand in (1,-1):
            source=duplex('AAGCTTACGCGA','circular')
            source.features=[SeqFeature(FeatureLocation(BeforePosition(2),AfterPosition(10),strand=strand),
                                       type='misc_feature',qualifiers={'label':['uncertain']})]
            version=source.record_version
            for origin in (0,5):
                product=rotate_sequence(source,origin).only_product()
                loc=product.features[0].location
                if origin:
                    parts=list(loc.parts)
                    if strand==-1: parts.reverse()
                    self.assertIsInstance(parts[0].start,BeforePosition)
                    self.assertIsInstance(parts[0].end,ExactPosition)
                    self.assertIsInstance(parts[1].start,ExactPosition)
                    self.assertIsInstance(parts[1].end,AfterPosition)
                else:
                    self.assertIsInstance(loc.start,BeforePosition)
                    self.assertIsInstance(loc.end,AfterPosition)
                self.assertEqual(str(product.features[0].extract(product.seq)), 'GCTTACGC' if strand==1 else 'GCGTAAGC')
                with tempfile.TemporaryDirectory() as temp:
                    files=export_snapgene(product,temp).analysis
                    for key in ('gb_file','dna_file'):
                        saved=as_molecule(Path(files[key]))
                        self.assertEqual(saved.features[0].location,loc)
                self.assertEqual(source.record_version,version)
            cropped=extract_subsequence(source,4,8).only_product()
            self.assertIsInstance(cropped.features[0].location.start,ExactPosition)
            self.assertIsInstance(cropped.features[0].location.end,ExactPosition)


class ResidualPublicPipeline(unittest.TestCase):
    def test_prepared_circle_rotation_and_actual_edit_scopes(self):
        from agent.pipeline_agent import execute_agent_pipeline
        sequence=''.join(random.Random(51897).choices('ACGT',k=240))
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'template.gb'
            template=duplex(sequence,'circular')
            template.features=[SeqFeature(FeatureLocation(30,50),type='rep_origin',qualifiers={'label':['ori']}),
                               SeqFeature(FeatureLocation(70,100),type='misc_feature',qualifiers={'label':['AmpR']})]
            with source.open('w',encoding='utf-8') as handle:
                SeqIO.write(template,handle,'genbank')
            config=Path(temp)/'off.json'
            config.write_text('{"trace_level":"off"}',encoding='utf-8')
            steps=[{'step_id':'pcr','tool':'simulate_pcr','params':{'template_path_or_seq':'$src_1',
                    'f_primer':sequence[:20],'r_primer':str(Seq(sequence[-20:]).reverse_complement())}},
                   {'step_id':'circle','tool':'ligate_fragments','params':{'fragments':['$pcr'],'circular':True}}]
            for suffix,extra,expected in [('base',[],sequence),('zero',[{'step_id':'rotated','tool':'rotate_sequence',
                  'params':{'dna_seq':'$circle','origin_0based':0}}],sequence),('shift',[{'step_id':'rotated','tool':'rotate_sequence',
                  'params':{'dna_seq':'$circle','origin_0based':37}}],sequence[37:]+sequence[:37])]:
                with self.subTest(suffix=suffix),patch.dict(os.environ,{'SNAPGENE_TRACE_CONFIG':str(config)}):
                    result=execute_agent_pipeline(suffix,steps+extra,[source],out_dir=Path(temp)/suffix,
                          product_topology='circular',user_confirmed=True,
                          validation_requirements=['sequence_model','preparation_model','file','user_goal'])
                    self.assertEqual(result['status'],'delivered',result['validation_report']['errors'])
                    product=as_molecule(Path(result['authoritative_dir'])/'construct.gb')
                    self.assertEqual(str(product.seq),expected)
                    plan=json.loads(Path(result['plan_file']).read_text(encoding='utf-8'))
                    checked=result['validation_report']['scope_results']['preparation_model']
                    self.assertEqual(checked['subject_version'],product.record_version)
            # A real edit is sequence-model evidence only, not a prepared reaction.
            mutation=[{'step_id':'edited','tool':'mutate_sequence','params':{'dna_seq':'$circle',
                      'mutations':[{'position_0based':11,'alt_base':'A' if sequence[11]!='A' else 'C'}]}}]
            with patch.dict(os.environ,{'SNAPGENE_TRACE_CONFIG':str(config)}):
                result=execute_agent_pipeline('edit',steps+mutation,[source],out_dir=Path(temp)/'edit',
                     product_topology='circular',user_confirmed=True,
                     validation_requirements=['sequence_model','preparation_model','file','user_goal'])
                self.assertIsNone(result['delivery'])
            plan=json.loads((Path(temp)/'edit/plan.json').read_text(encoding='utf-8'))
            self.assertEqual(plan['preparation_check']['status'],'INCOMPLETE')
            # A saved input with an absent reaction parent cannot inherit preparation.
            supplied=duplex(sequence,'circular')
            supplied.source_refs=({'record_version':'absent-parent','mapping':{'origin_0based':37,'length':240}},)
            steps_missing=[{'step_id':'rotated','tool':'rotate_sequence',
                            'params':{'dna_seq':supplied.to_dict(),'origin_0based':17}}]
            with patch.dict(os.environ,{'SNAPGENE_TRACE_CONFIG':str(config)}):
                result=execute_agent_pipeline('missing-parent',steps_missing,[source],out_dir=Path(temp)/'missing',
                     product_topology='circular',user_confirmed=True,
                     validation_requirements=['sequence_model','preparation_model','file','user_goal'])
            plan=json.loads(Path(result['plan_file']).read_text(encoding='utf-8'))
            self.assertEqual(plan['preparation_check']['status'],'INCOMPLETE')
            self.assertIsNone(result['delivery'])

    def test_cli_open_status_is_structured_without_mocking_construction(self):
        import contextlib
        import io
        from scripts.run_pipeline import main
        with tempfile.TemporaryDirectory() as temp:
            pipeline=Path(temp)/'pipeline.json'
            source=Path(temp)/'source.gb'
            with source.open('w',encoding='utf-8') as handle:
                SeqIO.write(duplex('ACGTACGTTGCA'),handle,'genbank')
            pipeline.write_text(json.dumps({'task_id':'public-status','topology':'linear',
                'sources':[str(source)],
                'steps':[{'step_id':'selected','tool':'extract_subsequence','params':{
                    'file_path_or_record':'$src_1','start':0,'end':8}}]}),encoding='utf-8')
            argv=['run_pipeline.py','--pipeline',str(pipeline),'--out-dir',str(Path(temp)/'out'),
                  '--confirmed','--open-snapgene','--json']
            output=io.StringIO()
            with patch('sys.argv',argv),patch('core.tools.snapgene_io.find_snapgene_executable',return_value=None),contextlib.redirect_stdout(output):
                code=main()
            result=json.loads(output.getvalue())
            self.assertEqual(code,0,result)
            self.assertIsInstance(result['snapgene_status'],dict)
            self.assertEqual(result['snapgene_status']['status'],'UNAVAILABLE')
            self.assertFalse(result['snapgene_status']['success'])
            self.assertEqual(str(as_molecule(Path(result['authoritative_dir'])/'construct.gb').seq),'ACGTACGT')
