"""Focused tests of domain constants versus sample-identity exemptions."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import random
import unittest
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import FeatureLocation, SeqFeature


class DomainConstantsIntegrityTests(unittest.TestCase):
    def test_published_guide_cassette_route_uses_actual_template_and_rejects_wrong_dna(self):
        from core.tools.crispr import prepare_pml104_guide
        scaffold='GTTTTAGAGCTAGAAATAGCAAGTTAAAATAAGGCTAGTCCGTTATCAACTTGAAAAAGTGGCACCGAGTCGGTGGTGC'
        reverse_core='GATCATTTATCTTTCACTGC'
        reverse_site=str(Seq(reverse_core).reverse_complement())
        spacer='ATCGTCAGTTGACCGATAGC'
        for length in (503,701):
            middle=''.join(random.Random(length).choices('ACGT',k=length))
            oriented=scaffold+'TTTTTT'+middle+reverse_site+'TCACCATGAACT'
            record=SeqRecord(Seq(oriented).reverse_complement(),id='unrelated_material',
                             annotations={'molecule_type':'DNA','topology':'circular'})
            # Expected sequence is directly derived from input and ordered spacer.
            expected=scaffold+'TTTTTT'+middle+reverse_site+spacer
            with self.subTest(length=length):
                result=prepare_pml104_guide(record,spacer)
                self.assertEqual(str(result.only_product().seq),expected)
                record.id='pML104'
                self.assertEqual(str(prepare_pml104_guide(record,spacer).only_product().seq),expected)
                wrong=oriented[:45]+('A' if oriented[45]!='A' else 'C')+oriented[46:]
                record.seq=Seq(wrong).reverse_complement()
                with self.assertRaises(ValueError):
                    prepare_pml104_guide(record,spacer)

    def test_reporter_names_do_not_waive_complete_cds_checks(self):
        from core.tools.sequence_ops import validate_cds_feature
        record=SeqRecord(Seq('ATG'+'GCT'*30),annotations={'molecule_type':'DNA'})
        for name in ('mCherry2','sfGFP','eGFP','arbitrary_gene'):
            feature=SeqFeature(FeatureLocation(0,len(record),strand=1),type='CDS',qualifiers={'label':[name]})
            with self.subTest(name=name):
                audit=validate_cds_feature(feature,record.seq)
                self.assertFalse(audit['partial'])
                self.assertFalse(audit['terminal_stop'])
