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
            for result in (summarize_backbone(source), inspect_single_file(source)):
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
        self.assertEqual(info['sequence_output_key'],'amplicon')
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
        self.assertTrue(result['pam_silenced_in_donor'])
        before=str(record.seq.translate())
        after=str(Seq(result['edited_target_sequence']).translate())
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
