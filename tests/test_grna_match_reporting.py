"""Independent physical loci and orientation hypotheses via public entries."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

ROOT = pathlib.Path(__file__).resolve().parents[1] / 'snapgene-dna-design'
sys.path.insert(0, str(ROOT))
from core.tools.registry import TOOL_REGISTRY

Q = 'GACTACATGTCATACGATCA'
RC = 'TGATCGTATGACATGTAGTC'
SCAFFOLD = 'GTTTTAGAGCTAGAAATAGCAAGTTAAAATAAGGC'


def vector(spacer=Q):
    rec = SeqRecord(Seq('A'*28 + spacer + SCAFFOLD + 'C'*60), id='cassette',
                    annotations={'molecule_type': 'DNA', 'topology': 'circular'})
    rec.features = [SeqFeature(FeatureLocation(0,28,strand=1),type='promoter')]
    return rec


def check(target, spacer=Q):
    return TOOL_REGISTRY['check_grna'].execute(vector_record_or_seq=vector(spacer),
                                              target_seq_or_file=target).analysis


class GuideMatchReportTests(unittest.TestCase):
    def test_single_duplex_locus_does_not_report_mirror_as_second_guide_hit(self):
        report = check('A'*8 + Q + 'TGG' + 'T'*8)
        self.assertEqual(report['direction_status'], 'CORRECT')
        self.assertEqual(report['target_locus_count'], 1)
        self.assertEqual(len(report['target_matches']), 1)
        primary = report['target_matches'][0]
        self.assertEqual(primary['protospacer_parts_0based'], [[8,28]])
        self.assertEqual(primary['strand'], 1)
        mirror = report['reverse_insert_hypotheses'][0]
        self.assertEqual(mirror['protospacer_parts_0based'], [[8,28]])
        self.assertEqual(mirror['strand'], -1)
        self.assertTrue(mirror['same_physical_locus_as_transcribed_match'])
        self.assertEqual(primary['locus_id'], mirror['locus_id'])

    def test_invalid_pam_retains_failure_and_reverse_insert_diagnostic(self):
        report = check('A'*8 + Q + 'GCG' + 'T'*8)
        self.assertEqual(report['direction_status'], 'INVALID_PAM')
        self.assertIsNone(report['direction_correct'])
        self.assertEqual(len(report['target_matches']), 1)
        self.assertEqual(report['target_matches'][0]['pam'], 'GCG')
        self.assertFalse(report['target_matches'][0]['pam_valid'])
        self.assertEqual(report['target_locus_count'], 1)
        self.assertEqual(len(report['reverse_insert_hypotheses']), 1)

    def test_two_real_target_loci_keep_both_strands(self):
        # Second guide-identical strand is negative, at a separate locus.
        target = 'A'*8 + Q + 'TGG' + 'T'*12 + 'CCA' + RC + 'A'*8
        report = check(target)
        self.assertEqual(report['target_locus_count'], 2)
        self.assertEqual(len(report['target_matches']), 2)
        self.assertEqual([h['strand'] for h in report['target_matches']], [1,-1])
        self.assertEqual({tuple(h['protospacer_parts_0based'][0]) for h in report['target_matches']},
                         {(8,28),(46,66)})
        self.assertTrue(all(h['pam_valid'] for h in report['target_matches']))
        self.assertIn('MULTIPLE_VALID_TARGETS', [w['code'] for w in report['warnings']])

    def test_reversed_insert_remains_failed_with_alternative_explicit(self):
        report = check('A'*8 + Q + 'TGG' + 'T'*8, RC)
        self.assertEqual(report['direction_status'], 'REVERSED')
        self.assertFalse(report['direction_correct'])
        self.assertFalse(any(h['pam_valid'] for h in report['target_matches']))
        self.assertTrue(any(h['pam_valid'] for h in report['reverse_insert_hypotheses']))

    def test_palindromic_spacer_is_one_locus_with_indistinguishable_orientation(self):
        palindrome = 'ACGATTCGTATACGAATCGT'
        report = check('CCA' + palindrome + 'TGG', palindrome)
        self.assertEqual(report['target_locus_count'], 1)
        self.assertEqual(len(report['target_matches']), 2)
        self.assertTrue(all(h['pam_valid'] for h in report['target_matches']))
        self.assertEqual(report['reverse_insert_hypotheses'], [])
        self.assertFalse(report['orientation_distinguishable'])
        self.assertNotIn('MULTIPLE_VALID_TARGETS', [w['code'] for w in report['warnings']])

    def test_cli_saved_report_separates_actual_and_hypothetical_hits(self):
        with tempfile.TemporaryDirectory(prefix='grna-报告-') as folder:
            folder = pathlib.Path(folder)
            path = folder/'source.gb'
            with path.open('w', encoding='utf-8') as handle:
                SeqIO.write(vector(), handle, 'genbank')
            cfg = folder/'step.json'
            cfg.write_text(json.dumps({'method':'check_grna','params':{
                'vector_record_or_seq':str(path), 'target_seq_or_file':'A'*8 + Q + 'TGG' + 'T'*8}}),encoding='utf-8')
            run = subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'scripts/run_step.py'),
                                  '--input',str(cfg),'--out-dir',str(folder/'out')],
                                  capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            saved = json.loads((folder/'out/steps.json').read_text(encoding='utf-8'))
            report = saved['steps'][0]['result']['analysis']
            self.assertEqual(report['target_locus_count'],1)
            self.assertEqual(len(report['target_matches']),1)
            self.assertEqual(len(report['reverse_insert_hypotheses']),1)


if __name__ == '__main__':
    unittest.main()
