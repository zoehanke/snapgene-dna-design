"""Independent comparison expectations; no case identities or genomic answers."""
from repository_paths import SKILL_ROOT
import unittest
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import FeatureLocation, SeqFeature
from core.tools import get_tool


class SequenceComparisonTests(unittest.TestCase):
    def compare(self, query, reference, **options):
        method = get_tool('compare_sequences')
        self.assertIsNotNone(method, 'No public evidence path for sequence/coding comparisons')
        return method.execute(query=query, reference=reference, **options)

    def test_short_query_inside_long_reference_has_local_coverage(self):
        query = 'AACCGTATGCTAGTCA'
        result = self.compare(query, 'TTTTTTTT' + query + 'GGGGGGGG')
        self.assertEqual(result.products, [])
        self.assertEqual(result.analysis['query_coverage_pct'], 100.0)
        self.assertEqual(result.analysis['identity_pct'], 100.0)
        self.assertEqual(result.analysis['reference_interval_0based'], [8, 24])

    def test_synonymous_and_nonsynonymous_are_translated_not_guessed(self):
        reference = 'ATGGCTGAATAA'
        query = 'ATGGCCGACTAA'
        result = self.compare(query, reference, coding=True, mode='global')
        coding = result.analysis['coding_comparison']
        self.assertFalse(coding['protein_identical'])
        self.assertEqual([item['synonymous'] for item in coding['changed_codons']], [True, False])
        self.assertEqual(coding['phenotype'], 'NOT_CHECKED')

    def test_feature_boundaries_and_negative_strand_are_respected(self):
        coding = 'ATGGCTGAATAA'
        source = SeqRecord(Seq('CCC' + str(Seq(coding).reverse_complement()) + 'GGG'),
                           annotations={'molecule_type': 'DNA', 'topology': 'linear'})
        source.features = [SeqFeature(FeatureLocation(3, 15, strand=-1), type='CDS',
                                       qualifiers={'label': ['actual_gene']})]
        result = self.compare(source, coding, query_feature='actual_gene', coding=True)
        self.assertTrue(result.analysis['coding_comparison']['protein_identical'])
        self.assertEqual(result.analysis['query_region']['source_parts'], [[3, 15, -1]])

    def test_limits_and_invalid_cds_are_explicit_failures(self):
        with self.assertRaisesRegex(Exception, 'limit|cells'):
            self.compare('ACGT' * 10, 'ACGT' * 10, max_alignment_cells=5)
        with self.assertRaisesRegex(Exception, 'CDS|coding'):
            self.compare('ATGGCT', 'ATGGCT', coding=True)

    def test_reverse_orientation_and_feature_ambiguity_are_explicit(self):
        query = 'AACCGTATGCTAGTCA'
        reference = 'GGGG' + str(Seq(query).reverse_complement()) + 'AAAA'
        result = self.compare(query, reference)
        self.assertEqual(result.analysis['query_orientation'], -1)
        self.assertEqual(result.analysis['query_interval_0based'], [0, len(query)])
        self.assertEqual(result.analysis['query_coverage_pct'], 100.0)
        source = SeqRecord(Seq('ATGGCTTAAATGGCTTAA'), annotations={'molecule_type': 'DNA'})
        source.features = [SeqFeature(FeatureLocation(0, 9, strand=1), type='CDS'),
                           SeqFeature(FeatureLocation(9, 18, strand=1), type='CDS')]
        with self.assertRaisesRegex(Exception, 'ambiguous'):
            self.compare(source, 'ATGGCTTAA', coding=True)


if __name__ == '__main__':
    unittest.main()
