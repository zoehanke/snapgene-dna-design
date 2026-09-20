"""Regression for inherited primers after real PCR extraction and export."""
import tempfile
import unittest
from pathlib import Path

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from core.tools.amplification import simulate_pcr
from core.tools.sequence_ops import slice_record_interval
from core.tools.snapgene_io import annotate_record_primers, export_plasmid, read_native_dna_record
from scripts.run_recipe import write_preparation_artifacts


class PreparationPrimerLocations(unittest.TestCase):
    def test_pcr_keeps_shifted_primers_and_clipped_annotation(self):
        import random
        rng = random.Random(317)
        seq = ''.join(rng.choice('ACGT') for _ in range(600))
        rec = SeqRecord(Seq(seq), id='source', annotations={'molecule_type': 'DNA', 'topology': 'linear'})
        definitions = []
        for name, start, end, strand in [('inside', 240, 263, '-'), ('clipped', 390, 420, '+')]:
            core = seq[start:end] if strand == '+' else str(Seq(seq[start:end]).reverse_complement())
            definitions.append(dict(name=name, sequence='AACCGG'+core, binding_sequence=core,
                                    binding_interval_0based=[start, end], strand=strand))
        rec = annotate_record_primers(rec, definitions)
        pcr = simulate_pcr(rec, 'TTAGGA'+seq[100:122], str(Seq(seq[378:400]).reverse_complement()),
                           forward_binding_core_length=22, reverse_binding_core_length=22)
        row = dict(id='pcr', template=pcr['template'], primers=pcr['primers'],
                   product=dict(sequence=pcr['amplicon'], features=pcr['features'], topology='linear'))
        with tempfile.TemporaryDirectory() as temp:
            result = write_preparation_artifacts([row], temp)
            files = result['steps'][0]['product']
            for record in [SeqIO.read(files['gb_file'], 'genbank'), read_native_dna_record(files['dna_file'])]:
                inside = next(f for f in record.features if f.qualifiers.get('label') == ['inside'])
                self.assertEqual((int(inside.location.start), int(inside.location.end)), (146, 169))
                self.assertEqual(str(inside.extract(record.seq)), definitions[0]['binding_sequence'])
                self.assertEqual(inside.qualifiers['binding_interval'], ['[146,169]'])
                clipped = next(f for f in record.features if f.qualifiers.get('label') == ['clipped'])
                self.assertEqual(clipped.type, 'misc_feature')
                self.assertEqual(clipped.qualifiers['partial'], ['true'])
            self.assertEqual(rec.features[0].qualifiers['binding_interval'], ['[240,263]'])

    def test_shifted_location_does_not_hide_wrong_core(self):
        rec = SeqRecord(Seq('A'*100), id='bad', annotations={'molecule_type': 'DNA'})
        rec = annotate_record_primers(rec, [dict(name='p', sequence='A'*20,
              binding_sequence='A'*20, binding_interval_0based=[20,40], strand='+')])
        rec.seq = Seq('C'*100)
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(ValueError, 'does not match'):
            export_plasmid(rec, temp)

    def test_circular_origin_and_reverse_complement(self):
        rec = SeqRecord(Seq('ACGTACGTTAGC' * 10), id='circle',
                        annotations={'molecule_type': 'DNA', 'topology': 'circular'})
        core = str(rec.seq[110:] + rec.seq[:10])
        rec = annotate_record_primers(rec, [dict(name='crossing', sequence='GG'+core,
              binding_sequence=core, binding_interval_0based=[110,10], strand='+')])
        fragment = slice_record_interval(rec, 100, 40, circular=True).reverse_complement()
        fragment.annotations.update(molecule_type='DNA', topology='linear')
        with tempfile.TemporaryDirectory() as temp:
            files = export_plasmid(fragment, temp)
            restored = read_native_dna_record(files['dna_file'])
            primer = next(f for f in restored.features if f.type == 'primer_bind')
            self.assertEqual(primer.location.strand, -1)
            self.assertEqual(str(primer.extract(restored.seq)), core)


if __name__ == '__main__':
    unittest.main()
