"""Regression for inherited primers after real PCR extraction and export."""

from core.models.construct_model import feature_to_dict
from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import tempfile
import unittest
from pathlib import Path

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

from core.tools.amplification import simulate_pcr
from core.models.construct_model import ConstructModel
from core.tools.sequence_ops import slice_record_interval
from core.tools.snapgene_io import annotate_record_primers, export_plasmid, read_native_dna_record
from scripts.run_recipe import write_preparation_artifacts


class PreparationPrimerLocations(unittest.TestCase):
    def test_rotated_circular_primer_keeps_all_parts_in_biological_order(self):
        import random
        rng = random.Random(717)
        seq = ''.join(rng.choice('ACGT') for _ in range(200))
        with tempfile.TemporaryDirectory() as temp:
            for strand in (1, -1):
                core = seq[190:]+seq[:14]
                if strand == -1:
                    core = str(Seq(core).reverse_complement())
                source = SeqRecord(Seq(seq), id='circle', annotations={
                    'molecule_type': 'DNA', 'topology': 'circular'})
                source = annotate_record_primers(source, [dict(name='p', sequence='GGAA'+core,
                    binding_sequence=core, binding_interval_0based=[190, 14], strand=strand)])
                for cut in (0, 30, 195):
                    for reverse in (False, True):
                        with self.subTest(strand=strand, cut=cut, reverse=reverse):
                            record = ConstructModel(source).rotate(cut).to_record()
                            expected = seq[cut:]+seq[:cut]
                            if reverse:
                                record = record.reverse_complement()
                                record.annotations.update(molecule_type='DNA', topology='circular')
                                expected = str(Seq(expected).reverse_complement())
                            files = export_plasmid(record, temp)
                            for out in (SeqIO.read(files.analysis['gb_file'], 'genbank'), read_native_dna_record(files.analysis['dna_file'])):
                                self.assertEqual(str(out.seq), expected)
                                self.assertEqual(out.annotations['topology'], 'circular')
                                self.assertEqual(str(out.features[0].extract(out.seq)), core)
                                self.assertEqual(out.features[0].qualifiers['primer_sequence'], ['GGAA'+core])

    def test_compound_primer_order_is_not_rewritten_to_fit_qualifiers(self):
        seq = Seq('T'*10+'A'*10+'C'*10+'G'*10)
        with tempfile.TemporaryDirectory() as temp:
            for strand in (1, -1):
                core = str(seq[10:30] if strand == 1 else seq[10:30].reverse_complement())
                correct_order = [(10, 20), (20, 30)] if strand == 1 else [(20, 30), (10, 20)]
                for valid in (True, False):
                    with self.subTest(strand=strand, valid_order=valid):
                        parts = correct_order if valid else correct_order[::-1]
                        record = SeqRecord(seq, id='compound', annotations={
                            'molecule_type': 'DNA', 'topology': 'linear'})
                        record.features = [SeqFeature(CompoundLocation([
                            FeatureLocation(start, end, strand=strand) for start, end in parts]),
                            type='primer_bind', qualifiers={'label': ['p'],
                                'primer_sequence': [core], 'binding_sequence': [core]})]
                        if not valid:
                            with self.assertRaisesRegex(ValueError, 'compound location'):
                                export_plasmid(record, temp)
                            continue
                        files = export_plasmid(record, temp)
                        for out in (SeqIO.read(files.analysis['gb_file'], 'genbank'), read_native_dna_record(files.analysis['dna_file'])):
                            self.assertEqual(str(out.features[0].extract(out.seq)), core)

    def test_linear_extraction_preserves_sites_only_when_physically_contiguous(self):
        """Oracle uses source base identities, not the coordinate/export helpers."""
        import random
        rng = random.Random(90317)
        seq = ''.join(rng.choice('ACGT') for _ in range(200))
        with tempfile.TemporaryDirectory() as temp:
            for strand in (1, -1):
                for site_start in (5, 80, 175, 190):
                    source_positions = [(site_start + i) % len(seq) for i in range(24)]
                    oriented_positions = source_positions if strand == 1 else source_positions[::-1]
                    core = ''.join(seq[p] for p in source_positions)
                    if strand == -1:
                        core = str(Seq(core).reverse_complement())
                    source = SeqRecord(Seq(seq), id='circular-source', annotations={
                        'molecule_type': 'DNA', 'topology': 'circular'})
                    source = annotate_record_primers(source, [dict(
                        name='retained-site', sequence='GGAA'+core, binding_sequence=core,
                        binding_interval_0based=[site_start, (site_start+24) % len(seq)],
                        strand=strand)])
                    for cut, length in ((0, 200), (30, 200), (185, 200), (180, 60), (170, 30), (0, 80)):
                        for reverse in (False, True):
                            with self.subTest(strand=strand, site=site_start, cut=cut,
                                              length=length, reverse=reverse):
                                bases = [(cut+i) % len(seq) for i in range(length)]
                                expected_seq = ''.join(seq[p] for p in bases)
                                if reverse:
                                    bases.reverse()
                                    expected_seq = str(Seq(expected_seq).reverse_complement())
                                expected_positions = [bases.index(p) for p in oriented_positions if p in bases]
                                output_strand = -strand if reverse else strand
                                contiguous = (len(expected_positions) == 24 and all(
                                    b-a == output_strand for a, b in zip(expected_positions, expected_positions[1:])))
                                product = slice_record_interval(source, cut, length, circular=True)
                                if reverse:
                                    product = product.reverse_complement()
                                    product.annotations.update(molecule_type='DNA', topology='linear')
                                files = export_plasmid(product, temp)
                                for out in (SeqIO.read(files.analysis['gb_file'], 'genbank'), read_native_dna_record(files.analysis['dna_file'])):
                                    self.assertEqual(str(out.seq), expected_seq)
                                    features = [f for f in out.features if f.qualifiers.get('label') == ['retained-site']]
                                    self.assertEqual(len(features), bool(expected_positions))
                                    if not features:
                                        continue
                                    feature = features[0]
                                    self.assertEqual(set(feature.location), set(expected_positions))
                                    self.assertEqual(feature.location.strand, output_strand)
                                    self.assertEqual(feature.qualifiers['primer_sequence'], ['GGAA'+core])
                                    if contiguous:
                                        self.assertEqual(feature.type, 'primer_bind')
                                        self.assertEqual(str(feature.extract(out.seq)), core)
                                    else:
                                        self.assertEqual(feature.type, 'misc_feature')
                                        self.assertEqual(feature.qualifiers['partial'], ['true'])
                                        self.assertEqual(feature.qualifiers['source_feature_type'], ['primer_bind'])
                    self.assertEqual(source.features[0].type, 'primer_bind')
                    self.assertNotIn('partial', source.features[0].qualifiers)

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
        row = dict(id='pcr', template=pcr.analysis['template'], primers=pcr.analysis['primers'],
                   product=dict(sequence=str(pcr.only_product().seq), features=[feature_to_dict(f, len(pcr.only_product())) for f in pcr.only_product().features], topology='linear'))
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
            export_plasmid(rec, temp,topology='linear')

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
            restored = read_native_dna_record(files.analysis['dna_file'])
            primer = next(f for f in restored.features if f.type == 'primer_bind')
            self.assertEqual(primer.location.strand, -1)
            self.assertEqual(str(primer.extract(restored.seq)), core)


if __name__ == '__main__':
    unittest.main()
