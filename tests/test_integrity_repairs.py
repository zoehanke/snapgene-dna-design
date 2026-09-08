import random
import unittest
import tempfile
from pathlib import Path
from Bio import SeqIO

from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.guardrails.checklist import quick_biological_sanity_check
from core.recipes.verification import recipe_cloning_verification


class IntegrityRepairTests(unittest.TestCase):
    def test_verification_distance_sequence_and_native_source_annotations(self):
        from scripts.run_recipe import run_recipe_cli
        rng = random.Random(924)
        seq = ''.join(rng.choices('ACGT', k=1800))
        record = SeqRecord(Seq(seq), id='source', annotations={'molecule_type': 'DNA', 'topology': 'circular'})
        record.features = [SeqFeature(FeatureLocation(1100,1500,strand=-1), type='misc_feature', qualifiers={'label':['source feature']})]
        with tempfile.TemporaryDirectory() as tmp:
            result = run_recipe_cli('cloning_verification', {'recombinant_plasmid_seq_or_file':record,
                'insert_start_0based':350, 'insert_end_0based':900}, tmp)
            details = result['recipe_result'].details
            sanger = details['sanger_sequencing_primer']
            self.assertEqual(sanger['distance_upstream_of_junction_bp'], 350-sanger['interval_0based'][1])
            self.assertTrue(50 <= sanger['distance_upstream_of_junction_bp'] <= 100)
            pcr = details['colony_pcr_simulation']
            start,end = pcr['template_interval_0based']
            self.assertEqual(pcr['amplicon'], seq[start:end])
            native = Path(tmp)/'candidate/recipe_cloning_verification.dna'
            with native.open('rb') as handle:
                reread = SeqIO.read(handle,'snapgene')
            self.assertEqual(str(reread.seq),seq)
            self.assertEqual(reread.annotations['topology'],'circular')
            self.assertEqual(len([f for f in reread.features if f.type=='primer_bind']),3)
            self.assertTrue(any('source feature' in f.qualifiers.get('label',[]) for f in reread.features))

    def test_circular_digest_includes_site_across_origin(self):
        rng=random.Random(983)
        seq='AATTC'+''.join(rng.choices('ACGT',k=600))+'GAATTC'+''.join(rng.choices('ACGT',k=600))+'G'
        record=SeqRecord(Seq(seq),annotations={'topology':'circular'})
        result=recipe_cloning_verification(record,300,800,['EcoRI'])
        digest=result.details['diagnostic_restriction_digests'][0]
        from Bio.Restriction import EcoRI
        cuts=sorted(p-1 for p in EcoRI.search(record.seq,linear=False))
        self.assertIn(0,cuts)
        self.assertEqual(digest['cut_count'],len(cuts))
        self.assertEqual(sorted(digest['predicted_band_sizes_bp']),sorted((b-a)%len(seq) for a,b in zip(cuts,cuts[1:]+cuts[:1])))

    def test_candidate_cannot_borrow_same_length_report(self):
        from core.runtime_gate import finalize_candidate_construct, GateRejected
        good = quick_biological_sanity_check('ATGGCTTAA', is_cds=True)
        changed = SeqRecord(Seq('ATGGCCCTA'), id='changed', annotations={'molecule_type': 'DNA', 'topology': 'linear'})
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for ext, fmt in [('gb', 'genbank'), ('fasta', 'fasta')]:
                with (folder / ('candidate.' + ext)).open('w', encoding='utf-8') as handle:
                    SeqIO.write(changed, handle, fmt)
            with self.assertRaises(GateRejected):
                finalize_candidate_construct(folder/'candidate.gb', folder/'candidate.fasta', folder/'out', {}, good, True)

    def test_unmarked_circular_cds_without_stop_is_rejected(self):
        record = SeqRecord(Seq('ATG' + 'GCT' * 30 + 'ACGT' * 75),
                           annotations={'molecule_type': 'DNA', 'topology': 'circular'})
        record.features = [
            SeqFeature(FeatureLocation(0, 93, strand=1), type='CDS', qualifiers={'label': ['AmpR']}),
            SeqFeature(FeatureLocation(100, 250, strand=1), type='rep_origin', qualifiers={'label': ['ori']}),
        ]
        report = quick_biological_sanity_check(record, is_cds=False)
        self.assertEqual(report['guardrail_status_table']['BIO-02-STOP']['status'], 'FAIL')
        self.assertFalse(report['all_applicable_pass'])

    def test_repeated_verification_core_cannot_claim_one_pcr_product(self):
        rng = random.Random(704)
        repeated = ''.join(rng.choices('ACGT', k=700))
        unique = ''.join(rng.choices('ACGT', k=500))
        record = SeqRecord(Seq(repeated + repeated + unique), annotations={'topology': 'circular'})
        with self.assertRaisesRegex(ValueError, 'unique|ambigu'):
            recipe_cloning_verification(record, 350, 600)

    def test_linear_verification_digest_keeps_terminal_fragments(self):
        rng = random.Random(94)
        parts = [''.join(rng.choices('ACGT', k=n)) for n in (300, 250, 300)]
        record = SeqRecord(Seq('GAATTC'.join(parts)), annotations={'topology': 'linear'})
        result = recipe_cloning_verification(record, 200, 600, ['EcoRI'])
        digest = result.details['diagnostic_restriction_digests'][0]
        self.assertEqual(sorted(digest['predicted_band_sizes_bp']), [256, 301, 305])


if __name__ == '__main__':
    unittest.main()
