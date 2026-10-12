"""Independent sequence oracles; public registry/CLI, no private user DNA."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

ROOT = pathlib.Path(__file__).resolve().parents[1] / 'snapgene-dna-design'
sys.path.insert(0, str(ROOT))
from core.tools.registry import TOOL_REGISTRY

Q = 'GACTACATGTCATACGATCA'
RC = 'TGATCGTATGACATGTAGTC'


def invoke(name, **kwargs):
    return TOOL_REGISTRY[name].execute(**kwargs).analysis


class GuideEvaluationTests(unittest.TestCase):
    def test_supplied_vector_exact_near_invalid_pam_and_outside_bound(self):
        # One deliberately placed physical site, independent expected bases.
        for protospacer, pam, expected in (
            (Q, 'TGG', 'EXACT_MATCH'),
            ('AACTACATGTCATACGATCA', 'TGG', 'NEAR_MATCH_RISK'),
            (Q, 'TGC', 'NO_MATCH_IN_SEARCH_SCOPE'),
            ('TTAAACATGTCATACGATCA', 'TGG', 'NO_MATCH_IN_SEARCH_SCOPE'),
        ):
            with self.subTest(protospacer=protospacer, pam=pam):
                report = invoke('check_grna_vector', spacer_seq=Q,
                                vector_seq_or_file='A'*8 + protospacer + pam + 'T'*8)
                self.assertEqual(report['self_target_status'], expected)
                if expected != 'NO_MATCH_IN_SEARCH_SCOPE':
                    hit = report['matches'][0]
                    self.assertEqual(hit['protospacer_parts_0based'], [[8, 28]])
                    self.assertEqual(hit['pam'], 'TGG')
                    self.assertEqual(hit['strand'], 1)
                if expected == 'EXACT_MATCH':
                    self.assertIn('会切到质粒自身', ' '.join(report['warnings']))
                if expected == 'NEAR_MATCH_RISK':
                    self.assertEqual(report['matches'][0]['mismatch_positions_1based'], [1])

    def test_second_input_reverse_and_circular_site_coordinates(self):
        # Independent reverse site: CCA + literal reverse-complement, at 7.
        vector = 'A'*7 + 'CCA' + RC + 'T'*9
        report = invoke('check_grna_vector', spacer_seq=Q, vector_seq_or_file=vector)
        hit = report['matches'][0]
        self.assertEqual((hit['strand'], hit['pam']), (-1, 'TGG'))
        self.assertEqual(hit['protospacer_parts_0based'], [[10, 30]])
        self.assertEqual(hit['pam_parts_0based'], [[7, 10]])
        # Circular origin lies ten bases into the protospacer.
        wrapped = Q[10:] + 'AGG' + 'A'*19 + Q[:10]
        rec = SeqRecord(Seq(wrapped), id='circle', annotations={'topology': 'circular'})
        report = invoke('check_grna_vector', spacer_seq=Q, vector_seq_or_file=rec)
        hit = next(h for h in report['matches'] if h['mismatches'] == 0)
        self.assertEqual(hit['protospacer_parts_0based'], [[32, 42], [0, 10]])
        self.assertEqual(hit['pam_parts_0based'], [[10, 13]])
        linear = invoke('check_grna_vector', spacer_seq=Q, vector_seq_or_file=wrapped)
        self.assertEqual(linear['self_target_status'], 'NO_MATCH_IN_SEARCH_SCOPE')

    def test_profiles_uniqueness_secondary_sites_and_coordinate_contract(self):
        target = 'A'*5 + Q + 'TGG' + 'A'*25 + Q + 'TGC' + 'A'*25
        report = invoke('design_crispr_grna', target_seq_or_file=target,
                        vector_seq_or_file='A'*8 + Q + 'TGG' + 'T'*8)
        candidate = next(c for c in report['candidates'] if c['spacer'] == Q)
        self.assertEqual(candidate['target_interval_0based'], [5, 28])
        self.assertEqual(candidate['cut_position_0based'], 22)
        self.assertEqual(candidate['strand'], 1)
        self.assertEqual(candidate['gc_percent'], 40.0)
        self.assertIsNone(candidate['quality_score'])
        self.assertEqual(candidate['evaluation']['target_uniqueness']['exact_locus_count'], 2)
        self.assertFalse(candidate['evaluation']['target_uniqueness']['unique'])
        self.assertEqual(candidate['evaluation']['target_secondary_sites']['matches'], [])
        self.assertEqual(candidate['evaluation']['vector_self_target']['self_target_status'], 'EXACT_MATCH')
        near = 'AACTACATGTCATACGATCA'
        report = invoke('design_crispr_grna', target_seq_or_file='A'*5 + Q + 'TGG' + 'A'*25 + near + 'AGG',
                        vector_seq_or_file=None)
        candidate = next(c for c in report['candidates'] if c['spacer'] == Q)
        self.assertEqual(candidate['evaluation']['target_secondary_sites']['matches'][0]['mismatches'], 1)
        self.assertEqual(candidate['evaluation']['vector_self_target']['self_target_status'], 'NOT_SUPPLIED')
        reverse = invoke('design_crispr_grna', target_seq_or_file='A'*7 + 'CCA' + RC + 'T'*9)
        candidate = next(c for c in reverse['candidates'] if c['spacer'] == Q)
        self.assertEqual(candidate['target_interval_0based'], [7, 30])
        self.assertEqual(candidate['cut_position_0based'], 13)
        self.assertEqual(candidate['strand'], -1)

    def test_expression_factors_are_contextual_and_ranking_preserves_ties(self):
        poly = 'ACTTTTACATGTCATACGAT'
        target = 'A'*25 + poly + 'TGG' + 'A'*25 + Q + 'TGG' + 'A'*25
        report = invoke('design_crispr_grna', target_seq_or_file=target, transcription_promoter='human_U6')
        by_spacer = {c['spacer']: c for c in report['candidates']}
        self.assertTrue(by_spacer[poly]['has_poly_t'])
        self.assertEqual(by_spacer[poly]['evaluation']['five_prime_base']['base'], 'A')
        self.assertTrue(by_spacer[poly]['evaluation']['five_prime_base']['preference_applied'])
        self.assertLess(by_spacer[Q]['screening_rank'], by_spacer[poly]['screening_rank'])
        report = invoke('design_crispr_grna', target_seq_or_file='A'*25 + Q + 'TGG' + 'A'*25 + Q + 'TGG')
        repeated = [c for c in report['candidates'] if c['spacer'] == Q]
        self.assertEqual(len(repeated), 2)
        self.assertEqual(repeated[0]['screening_rank'], repeated[1]['screening_rank'])
        self.assertFalse(repeated[0]['evaluation']['five_prime_base']['preference_applied'])
        self.assertEqual(report['ranking_policy']['kind'], 'lexicographic_screening_not_activity_prediction')

    def test_unknown_bases_invalid_inputs_and_cas12_boundary(self):
        report = invoke('check_grna_vector', spacer_seq=Q, vector_seq_or_file='A'*25 + 'N' + 'T'*25)
        self.assertEqual(report['self_target_status'], 'INCOMPLETE')
        self.assertFalse(report['search_complete'])
        for mismatch_limit in (-1, 4):
            with self.subTest(mismatch_limit=mismatch_limit), self.assertRaises(Exception):
                invoke('check_grna_vector', spacer_seq=Q, vector_seq_or_file=Q, max_mismatches=mismatch_limit)
        with self.assertRaises(Exception):
            invoke('check_grna_vector', spacer_seq=Q[:19], vector_seq_or_file=Q)
        guide = Q + 'ACA'
        report = invoke('design_crispr_grna', target_seq_or_file='A'*8 + 'TTTA' + guide + 'C'*20, nuclease='AsCas12a')
        candidate = next(c for c in report['candidates'] if c['spacer'] == guide)
        self.assertEqual(candidate['target_interval_0based'], [8, 35])
        self.assertEqual(candidate['cut_position_0based'], 30)
        with self.assertRaisesRegex(Exception, 'SpCas9'):
            invoke('design_crispr_grna', target_seq_or_file='TTTA' + guide, nuclease='AsCas12a', vector_seq_or_file=Q)

    def test_public_cli_reads_native_vector_and_saves_inspectable_report(self):
        # Independent binary SnapGene packets, not the tested runtime writer.
        import struct
        def packet(kind, payload):
            return struct.pack('>BI', kind, len(payload)) + payload
        with tempfile.TemporaryDirectory(prefix='grna-载体-') as folder:
            folder = pathlib.Path(folder)
            native = folder / 'vector.dna'
            native.write_bytes(packet(9, b'SnapGene' + struct.pack('>HHH', 1, 1, 1)) +
                               packet(0, b'\x01' + ('A'*8 + Q + 'TGG' + 'T'*8).encode('ascii')))
            config = folder / 'step.json'
            config.write_text(json.dumps({'method': 'design_crispr_grna', 'params': {
                'target_seq_or_file': 'A'*5 + Q + 'TGG' + 'T'*15,
                'vector_seq_or_file': str(native)}}, ensure_ascii=False), encoding='utf-8')
            run = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(ROOT/'scripts/run_step.py'),
                                  '--input', str(config), '--out-dir', str(folder/'out')],
                                 capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            saved = json.loads((folder/'out/steps.json').read_text(encoding='utf-8'))
            report = saved['steps'][0]['result']['analysis']
            candidate = next(c for c in report['candidates'] if c['spacer'] == Q)
            self.assertEqual(candidate['evaluation']['vector_self_target']['matches'][0]['protospacer_parts_0based'], [[8, 28]])
            self.assertTrue(report['sources'])


if __name__ == '__main__':
    unittest.main()
