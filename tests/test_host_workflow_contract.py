"""Public workflow failures exposed by real host tasks, using independent DNA."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import copy
import json
import pathlib
import random
import subprocess
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

ROOT = SKILL_ROOT


class HostWorkflowContractTests(unittest.TestCase):
    def test_recipe_cli_explains_failed_cds_and_preserves_candidate(self):
        record = SeqIO.read(ROOT / 'fixtures/synthetic/pSynthetic-GFP.gb', 'genbank')
        sequence = str(record.seq)
        record.seq = Seq(sequence[:1000] + 'AAAGCTTAA' + sequence[1009:])
        record.features.append(SeqFeature(FeatureLocation(1000, 1009, strand=1),
            type='CDS', qualifiers={'label': ['错误编码区']}))
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            source = base / '原始材料.gb'
            SeqIO.write(record, source, 'genbank')
            original = source.read_bytes()
            params = base / 'params.json'
            alt = 'C' if sequence[1300] != 'C' else 'G'
            params.write_text(json.dumps({'template_seq_or_file': str(source),
                'start_0based': 1300, 'end_0based': 1301, 'alt_seq': alt,
                'method': 'quikchange'}), encoding='utf-8')
            output = base / '结果'
            run = subprocess.run([sys.executable, '-X', 'utf8', '-B',
                str(ROOT / 'scripts/run_recipe.py'), '--recipe', 'recipe_site_directed_mutagenesis',
                '--params-json', str(params), '--out-dir', str(output),
                '--finalize', '--confirmed', '--json'], capture_output=True, encoding='utf-8')
            self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
            result = json.loads(run.stdout)
            self.assertEqual(result['status'], 'failed')
            self.assertIsNone(result['authoritative_delivery'])
            error = result['error']
            self.assertEqual(error['error_code'], 'GATE_GUARDRAILS_FAILED')
            failure = next(f for f in error['details']['cds_failures'] if f['name'] == '错误编码区')
            self.assertEqual(failure['interval_0based'], [1000, 1009])
            self.assertIn('CDS_START_CODON_INVALID', [i['code'] for i in failure['validation_errors']])
            self.assertIn('错误编码区', run.stderr)
            receipt = pathlib.Path(error['details']['result_json'])
            self.assertTrue(receipt.is_file())
            self.assertFalse(json.loads(receipt.read_text(encoding='utf-8'))['sanity_check']['all_applicable_pass'])
            self.assertTrue((output / 'candidate/recipe_site_directed_mutagenesis.gb').is_file())
            self.assertFalse((output / 'authoritative').exists())
            self.assertEqual(source.read_bytes(), original)

    def test_recipe_cli_parameter_failures_are_json(self):
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            malformed = base / '错误参数.json'
            malformed.write_text('{', encoding='utf-8')
            for path in [malformed, base / 'missing.json']:
                with self.subTest(path=path):
                    run = subprocess.run([sys.executable, '-X', 'utf8', '-B',
                        str(ROOT / 'scripts/run_recipe.py'), '--recipe', 'protein_tagging',
                        '--params-json', str(path), '--out-dir', str(base / '结果'), '--json'],
                        capture_output=True, encoding='utf-8')
                    self.assertNotEqual(run.returncode, 0)
                    result = json.loads(run.stdout)
                    self.assertEqual(result['status'], 'failed')
                    self.assertFalse(result['error']['write_authoritative_artifact'])
                    self.assertIsNone(result['authoritative_delivery'])

    def test_pipeline_exports_actual_consumed_digest_products(self):
        from core.models.molecule import as_molecule
        from core.models.assembly_model import FragmentEnd
        from agent.pipeline_agent import execute_agent_pipeline
        record = self.source()
        sequence = str(record.seq).replace('GAATTC', 'GACTTC')
        sequence = sequence[:90] + 'GAATTC' + sequence[96:]
        record.seq = Seq(sequence)
        material = as_molecule(record)
        material.strandedness = 'double'
        material.left_end = FragmentEnd('blunt', '', cut_boundary=0)
        material.right_end = FragmentEnd('blunt', '', cut_boundary=len(material))
        steps = [
            {'step_id': 'actual_pcr', 'tool': 'simulate_pcr', 'params': {
                'template': material.to_dict(), 'f_primer': sequence[:22],
                'r_primer': str(Seq(sequence[-22:]).reverse_complement())}},
            {'step_id': 'actual_digest', 'tool': 'digest_sequence', 'params': {'seq': '$actual_pcr', 'enzyme': 'EcoRI'}},
            {'step_id': 'actual_join', 'tool': 'ligate_fragments', 'params': {
                'fragments': ['$actual_digest.products.0', '$actual_digest.products.1']}},
        ]
        with tempfile.TemporaryDirectory(prefix='实际步骤 ') as temp:
            from core.tools.snapgene_io import export_snapgene
            source_file = export_snapgene(material, temp, 'source').analysis['gb_file']
            steps[0]['params']['template'] = '$original'
            result = execute_agent_pipeline('consumed_products', steps,
                [{'source_id': 'original', 'path': source_file}],
                product_topology='linear', out_dir=temp, user_confirmed=True,
                expected_components=[{'name': 'original material', 'sequence': sequence}],
                validation_requirements=['sequence_model', 'preparation_model', 'file', 'user_goal'])
            self.assertEqual(result['validation_report']['overall'], 'verified', result['validation_report']['errors'])
            products = result['preparation_files']['step_products']
            digest_products = [p for p in products if p['step_id'] == 'actual_digest']
            self.assertEqual([p['product_index'] for p in digest_products], [0, 1])
            expected = [sequence[:91], sequence[91:]]
            for saved, bases in zip(digest_products, expected):
                for kind in ('gb_file', 'dna_file'):
                    actual = as_molecule(pathlib.Path(saved[kind]))
                    self.assertEqual(str(actual.seq), bases)
                    self.assertEqual(actual.topology, 'linear')
            self.assertFalse(any(p['step_id'] == 'actual_join' for p in products))

    def test_inverse_pcr_selects_complete_checked_primers(self):
        from core.recipes.mutagenesis import recipe_site_directed_mutagenesis
        rng = random.Random(73022)
        sequence = ''.join(rng.choices('ACGT', k=480))
        source = SeqRecord(Seq(sequence), id='independent_circular_template',
            annotations={'molecule_type': 'DNA', 'topology': 'circular'})
        alternative = 'C' if sequence[200] != 'C' else 'A'
        result = recipe_site_directed_mutagenesis(source, 200, 201, alternative, method='inverse_pcr')
        self.assertEqual(str(result.product_record.seq), sequence[:200] + alternative + sequence[201:])
        self.assertEqual(str(source.seq), sequence)
        design = result.details['reaction_evidence']['primer_design']
        for key in ('forward_primer', 'reverse_primer'):
            self.assertTrue(design[key]['unique_binding'])
            self.assertTrue(52 <= design[key]['binding_core_tm'] <= 72)
            self.assertLessEqual(design[key]['full_length'], 60)
        self.assertLessEqual(design['binding_core_delta_tm'], 3)
        self.assertTrue(design['primer3_metrics']['selected_pair_quality']['complete_oligo_structure']['passed'])
        with self.assertRaisesRegex(ValueError, 'unique|NO_VALID_PRIMER_PAIR'):
            recipe_site_directed_mutagenesis(SeqRecord(Seq('A' * 480),
                annotations={'molecule_type': 'DNA', 'topology': 'circular'}),
                200, 201, 'C', method='inverse_pcr')

    def test_guide_pipeline_retains_implicit_primers_and_actual_preparation(self):
        from agent.pipeline_agent import execute_agent_pipeline
        from core.io.input_resolution import resolve_sequence_record
        scaffold = 'GTTTTAGAGCTAGAAATAGCAAGTTAAAATAAGGCTAGTCCGTTATCAACTTGAAAAAGTGGCACCGAGTCGGTGGTGC'
        reverse_site = str(Seq('GATCATTTATCTTTCACTGC').reverse_complement())
        backbone = SeqIO.read(ROOT / 'fixtures/synthetic/pSynthetic-GFP.gb', 'genbank')
        middle = str(backbone.seq)
        oriented = scaffold + 'TTTTTT' + middle + reverse_site + 'TCACCATGAACT'
        scaffold_length = len(scaffold) + 6
        oriented_record = SeqRecord(Seq(oriented), id='guide_template',
            annotations={'molecule_type': 'DNA', 'topology': 'circular'})
        oriented_record.features = [feature._shift(scaffold_length) for feature in backbone.features]
        oriented_record.features.append(SeqFeature(FeatureLocation(scaffold_length+1000, scaffold_length+1017, strand=1),
            type='primer_bind', qualifiers={'label': ['existing source primer']}))
        source = oriented_record.reverse_complement(id=True, name=True, annotations=True)
        spacer = 'ATCGTCAGTTGACCGATAGC'
        expected = scaffold + 'TTTTTT' + middle + reverse_site + spacer
        with tempfile.TemporaryDirectory(prefix='完整制备与原引物 ') as temp:
            source_path = pathlib.Path(temp) / 'source.gb'
            SeqIO.write(source, source_path, 'genbank')
            original = source_path.read_bytes()
            result = execute_agent_pipeline('guide_preparation', [
                {'step_id': 'actual_guide', 'tool': 'prepare_pml104_guide', 'params': {
                    'vector_record_or_seq': '$original', 'spacer_seq': spacer}}],
                [{'source_id': 'original', 'path': str(source_path)}], product_topology='circular',
                out_dir=temp, user_confirmed=True,
                expected_components=[{'name': 'actual guide construct', 'sequence': expected}],
                validation_requirements=['sequence_model', 'preparation_model', 'file', 'user_goal'])
            self.assertEqual(result['validation_report']['overall'], 'verified', result['validation_report']['errors'])
            product = resolve_sequence_record(pathlib.Path(temp) / 'authoritative/construct.gb')
            self.assertEqual(str(product.seq), expected)
            primer = next(f for f in product.features if f.qualifiers.get('label') == ['existing source primer'])
            self.assertEqual(primer.qualifiers['binding_sequence'], [str(primer.extract(product.seq))])
            self.assertEqual(source_path.read_bytes(), original)

    def test_inverse_pcr_insertion_at_origin_and_internal_boundary(self):
        from core.recipes.mutagenesis import recipe_site_directed_mutagenesis
        sequence = ''.join(random.Random(73022).choices('ACGT', k=480))
        for position in (0, 200):
            source = SeqRecord(Seq(sequence), id='insertion_template',
                annotations={'molecule_type': 'DNA', 'topology': 'circular'})
            with self.subTest(position=position):
                result = recipe_site_directed_mutagenesis(source, position, position, 'GCTGCT', method='inverse_pcr')
                self.assertEqual(str(result.product_record.seq), sequence[:position]+'GCTGCT'+sequence[position:])
                self.assertEqual(str(source.seq), sequence)

    @staticmethod
    def source():
        rng = random.Random(73021)
        return SeqRecord(Seq(''.join(rng.choices('ACGT', k=240))), id='actual_source',
                         annotations={'molecule_type': 'DNA', 'topology': 'linear'})

    def test_public_pcr_accepts_ordered_oligos_with_5prime_tails(self):
        record = self.source()
        fwd = 'GAGACCCG' + str(record.seq[30:54])
        rev = 'ACTGGTAC' + str(record.seq[166:190].reverse_complement())
        expected = 'GAGACCCG' + str(record.seq[30:190]) + str(Seq('ACTGGTAC').reverse_complement())
        with tempfile.TemporaryDirectory() as temp:
            source = pathlib.Path(temp) / '中文源.gb'
            output = pathlib.Path(temp) / '扩增片段.gb'
            record.features = [SeqFeature(FeatureLocation(80,100), type='misc_feature',
                                          qualifiers={'label':['retained_part']})]
            SeqIO.write(record, source, 'genbank')
            run = subprocess.run([sys.executable, '-X', 'utf8', '-B',
                                  str(ROOT / 'scripts/simulate_pcr.py'), str(source),
                                  '--fwd', fwd, '--rev', rev, '--json', '--out', str(output)],
                                 capture_output=True, text=True, encoding='utf-8', errors='replace')
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)['data']['amplicon'], expected)
            saved = SeqIO.read(output, 'genbank')
            self.assertEqual(str(saved.seq),expected)
            feature = next(f for f in saved.features if f.qualifiers.get('label')==['retained_part'])
            self.assertEqual(str(feature.extract(saved.seq)),str(record.seq[80:100]))

    def test_public_pcr_no_binding_is_failure_without_an_output(self):
        record = self.source()
        with tempfile.TemporaryDirectory() as temp:
            source = pathlib.Path(temp)/'source.gb'
            output = pathlib.Path(temp)/'failed.gb'
            SeqIO.write(record,source,'genbank')
            run = subprocess.run([sys.executable,'-X','utf8',str(ROOT/'scripts/simulate_pcr.py'),
                                  str(source),'--fwd','A'*24,'--rev','C'*24,'--out',str(output),'--json'],
                                 capture_output=True,text=True,encoding='utf-8',errors='replace')
            self.assertNotEqual(run.returncode,0)
            self.assertFalse(json.loads(run.stdout)['ok'])
            self.assertFalse(output.exists())

    def test_marker_inspection_keeps_reporter_identity(self):
        from core.tools.inspection import summarize_backbone
        from scripts.inspect_plasmid import inspect_single_file
        record = self.source()
        labels = ['mNeonGreen', 'AMPK', 'catalase', 'NeoR/KanR', 'hphNT1']
        record.features = [SeqFeature(FeatureLocation(i*30, i*30+24), type='CDS',
                                      qualifiers={'label': [name]}) for i,name in enumerate(labels)]
        with tempfile.TemporaryDirectory() as temp:
            source = pathlib.Path(temp) / 'source.gb'
            SeqIO.write(record, source, 'genbank')
            for result in (summarize_backbone(source).analysis, inspect_single_file(source)):
                names = {item['name'] for item in result['selection_markers']}
                self.assertEqual(names, {'NeoR/KanR', 'hphNT1'})

    def test_export_rejects_product_not_generated_by_actual_primers(self):
        from scripts.run_recipe import write_preparation_artifacts
        record = self.source()
        fwd, rev = str(record.seq[30:54]), str(record.seq[166:190].reverse_complement())
        row = {'id': 'PCR', 'method': 'PCR', 'template': record,
               'product': {'sequence': str(record.seq[30:191]), 'topology': 'linear'},
               'primers': [dict(name='F',sequence=fwd,binding_sequence=fwd,
                                binding_interval_0based=[30,54],strand=1),
                           dict(name='R',sequence=rev,binding_sequence=rev,
                                binding_interval_0based=[166,190],strand=-1)]}
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'PREPARATION_PRODUCT_MISMATCH'):
                write_preparation_artifacts([row], temp)
            self.assertEqual(list(pathlib.Path(temp).iterdir()), [])

    def test_recipe_goals_resolve_original_source_feature_without_copying_dna(self):
        from scripts.run_recipe import run_recipe_cli
        record = SeqRecord(Seq('ATGAAACCCGGGTTTTAA'), id='source',
                           annotations={'molecule_type':'DNA','topology':'linear'})
        record.features = [SeqFeature(FeatureLocation(0,9),type='misc_feature',
                                      qualifiers={'label':['required_part']})]
        with tempfile.TemporaryDirectory() as temp:
            source = pathlib.Path(temp) / '原始源.gb'
            SeqIO.write(record, source, 'genbank')
            params = dict(target_cds_seq_or_file=str(source), tag_name_or_seq='6xHis',
                          sources=[{'source_id':'original','path':str(source)}],
                          expected_components=[{'name':'required_part','source_id':'original'}])
            result = run_recipe_cli('protein_tagging',params,pathlib.Path(temp)/'result')
            self.assertEqual(result['goal_check']['status'],'passed')

    def test_tool_catalog_reports_real_aliases_and_output_field(self):
        from scripts.describe_tools import describe
        info=describe('simulate_pcr')
        self.assertEqual(info['parameter_aliases']['template'],'template_path_or_seq')
        self.assertEqual(info['result']['products'],'Molecule[]')
        self.assertIn('f_primer',info['parameters']['required'])
        self.assertIn('fragments',describe('recipe_gibson_assembly')['signature'])

    def test_failed_recipe_retry_does_not_leave_a_previous_success_receipt(self):
        from scripts.run_recipe import run_recipe_cli
        with tempfile.TemporaryDirectory() as temp:
            params=dict(target_cds_seq_or_file='ATGAAACCCGGGTTTTAA',tag_name_or_seq='6xHis')
            run_recipe_cli('protein_tagging',params,temp)
            receipt=pathlib.Path(temp)/'candidate/recipe_protein_tagging_result.json'
            self.assertTrue(receipt.exists())
            params['target_cds_seq_or_file']='not_a_sequence_or_file'
            with self.assertRaises(Exception):
                run_recipe_cli('protein_tagging',params,temp)
            self.assertFalse(receipt.exists(),'A failed new attempt must not appear to have its predecessor receipt')

    def test_required_pam_change_is_not_replaced_by_a_warning(self):
        from core.tools.crispr import design_hdr_donor
        prefix='ATGGCT'*4
        record=SeqRecord(Seq(prefix+'TGG'+'GCTGAG'*8+'TAA'),
                         annotations={'molecule_type':'DNA','topology':'linear'})
        record.features=[SeqFeature(FeatureLocation(0,len(record),strand=1),type='CDS')]
        # TGG is the only Trp codon: altering its GG cannot be synonymous.
        with self.assertRaisesRegex(ValueError,'PAM_DISRUPTION_REQUIRED'):
            design_hdr_donor(record,21,'GTT',grna_seq=prefix[4:24],
                             edit_start_0based=9,edit_end_0based=12,
                             require_pam_disruption=True)
        # An Arg AGG PAM can change synonymously; only A4V remains in protein.
        record.seq=Seq(prefix+'AGG'+'GCTGAG'*8+'TAA')
        result=design_hdr_donor(record,21,'GTT',grna_seq=prefix[4:24],
                                edit_start_0based=9,edit_end_0based=12,
                                require_pam_disruption=True)
        self.assertTrue(result.analysis['pam_silenced_in_donor'])
        before=str(record.seq.translate())
        after=str(Seq(result.analysis['edited_target_sequence']).translate())
        self.assertEqual([(i+1,a,b) for i,(a,b) in enumerate(zip(before,after)) if a!=b],[(4,'A','V')])

    def test_verification_search_rejects_a_strong_hairpin_candidate(self):
        from core.recipes.verification import _optimize_verification_primer
        from scripts.primer3_core_backend import discover_primer3_core, run_boulder
        core = discover_primer3_core()
        if not core:
            self.skipTest('Real Primer3 executable is unavailable')
        sequence = ''.join(random.Random(1).choices('ACGT', k=700))
        primer = _optimize_verification_primer(sequence, 200)
        self.assertIsNotNone(primer)
        # Independent real engine measurement, not a copy of the ranking score.
        measured = run_boulder(core, {
            'PRIMER_TASK':'check_primers', 'PRIMER_PICK_ANYWAY':1,
            'SEQUENCE_PRIMER':primer['sequence'], 'PRIMER_PICK_RIGHT_PRIMER':0,
            'PRIMER_MIN_SIZE':18, 'PRIMER_OPT_SIZE':20, 'PRIMER_MAX_SIZE':30,
            'PRIMER_SECONDARY_STRUCTURE_ALIGNMENT':1,
        })
        for metric in ('_HAIRPIN_TH', '_SELF_ANY_TH', '_SELF_END_TH'):
            self.assertLess(float(measured['PRIMER_LEFT_0'+metric]), 47)


if __name__ == '__main__':
    unittest.main()
