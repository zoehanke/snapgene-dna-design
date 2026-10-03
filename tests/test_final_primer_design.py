
from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import random
import unittest
from pathlib import Path
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.tools.amplification import design_overhang_primers


class FinalPrimerDesignTests(unittest.TestCase):
    def test_sequence_analyses_use_record_bases_not_record_repr(self):
        from core.tools.amplification import calc_primer_tm, check_primer_dimers
        from core.tools.sequence_ops import check_reading_frame
        seq = 'ATGCGTACGTAGCTAGCTAGC'
        record = SeqRecord(Seq(seq), id='source')
        self.assertEqual(calc_primer_tm(record), calc_primer_tm(seq))
        self.assertEqual(check_primer_dimers(record, record), check_primer_dimers(seq, seq))
        self.assertTrue(check_reading_frame(SeqRecord(Seq('ATGGCTTAA')))['valid'])
        with self.assertRaises(ValueError):
            calc_primer_tm('ATGNNNTAA')

    def test_long_tail_is_prepared_by_real_successive_pcr(self):
        rng = random.Random(75)
        original = SeqRecord(Seq(''.join(rng.choices('ACGT', k=900))),
                             id='synthetic-long-tail',
                             annotations={'molecule_type': 'DNA', 'topology': 'circular'})
        self._assert_successive_pcr(original)

    @unittest.skipUnless((Path(__file__).parent/'data/pBP-eGFP.gb').is_file(),
                         'external pBP regression material is not in the redistributable package')
    def test_long_tail_original_external_material(self):
        source = Path(__file__).parent/'data/pBP-eGFP.gb'
        with source.open(encoding='utf-8') as handle:
            original = SeqIO.read(handle, 'genbank')
        self._assert_successive_pcr(original)

    def _assert_successive_pcr(self, original):
        from core.tools.amplification import prepare_pcr_fragment
        left = 'CATGTCATGA'+'TG'+'CAT'*5+'CAC'+'GAAAACCTGTATTTTCAGGGC'
        right = 'CCGCTCGAG'
        result = prepare_pcr_fragment(original, 3, 720, left, right)
        self.assertEqual(len(result['preparation']), 2)
        known_template = str(original.seq)
        for step in result['preparation']:
            self.assertEqual(step['template']['sequence'], known_template)
            f, r = step['primers']
            fc, rc = f['binding_sequence'], str(Seq(r['binding_sequence']).reverse_complement())
            search = known_template*2 if step['template']['topology']=='circular' else known_template
            f_hits = [i for i in range(len(known_template)) if search[i:i+len(fc)]==fc]
            r_hits = [i for i in range(len(known_template)) if search[i:i+len(rc)]==rc]
            self.assertEqual(len(f_hits),1)
            self.assertEqual(len(r_hits),1)
            predicted = f['sequence'][:-len(fc)] + search[f_hits[0]:r_hits[0]+len(rc)] + str(Seq(r['sequence'][:-len(rc)]).reverse_complement())
            self.assertEqual(step['product']['sequence'], predicted)
            known_template = predicted
            self.assertTrue(all(len(p['sequence'])<=60 for p in (f,r)))
            qc = step['primer_design']['primer3_metrics']['selected_pair_quality']['complete_oligo_structure']
            self.assertTrue(qc['passed'])
            self.assertTrue(all(v < qc['annealing_temperature_C']-5 for metrics in qc['metrics'].values() for v in metrics.values()))
        expected = left + str(original.seq[3:720]) + str(Seq(right).reverse_complement())
        self.assertEqual(result['pcr']['amplicon'],expected)

    def test_same_template_without_the_bad_tail_has_a_valid_complete_pair(self):
        from core.tools import get_tool
        rng = random.Random(75)
        sequence = ''.join(rng.choices('ACGT', k=900))
        result = get_tool('design_overhang_primers').execute(
            template_record_or_seq=sequence, start=100, end=700,
            circular=False, topology='linear')
        self.assertTrue(result['primer3_metrics']['selected_pair_quality']['acceptable'])
        self.assertTrue(result['primer3_metrics']['selected_pair_quality']['complete_oligo_structure']['passed'])

    def test_binding_only_retry_does_not_certify_strong_full_primer_hairpin(self):
        rng = random.Random(75)
        sequence = ''.join(rng.choices('ACGT', k=900))
        with self.assertRaisesRegex(ValueError, 'complete|structure|primer pair'):
            design_overhang_primers(sequence, 100, 700,
                fwd_5prime_overhang='GCGCGCGCAAAAGCGCGCGC')

    def test_topology_alias_is_not_python_string_truthiness(self):
        with self.assertRaisesRegex(ValueError, 'conflict|disagree'):
            design_overhang_primers('ACGT'*60, 200, 50,
                                   circular=True, topology='linear')

    def test_internal_complementarity_keeps_run_before_later_mismatch(self):
        from core.tools.amplification import check_primer_dimers

        result = check_primer_dimers("GAGCAACAGAAA", "TGCGGTGTTGCT")

        self.assertEqual(result["max_continuous_complementarity"], 7)
        self.assertTrue(any("Internal complementarity (7 bp)" in warning
                            for warning in result["warnings"]))


if __name__ == '__main__':
    unittest.main()
