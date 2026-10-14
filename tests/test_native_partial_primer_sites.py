"""Native partial matches preserve history without asserting active 3prime binding."""
from repository_paths import SKILL_ROOT
import copy
import json
import random
import tempfile
import unittest
from pathlib import Path
from sgffp import SgffObject, SgffPrimer, SgffBindingSite, SgffWriter
from core.models.molecule import as_molecule
from core.tools import export_snapgene, extract_subsequence
from core.tools.snapgene_io import annotate_record_primers


class NativePartialPrimerSiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        rng = random.Random(775029)
        bases = ''.join(rng.choices('ACGT', k=160))
        self.full = bases[20:70]
        self.prefix = self.full[:20]
        self.sequence = bases[:90] + self.prefix + bases[110:]
        self.path = self.root / 'independent-native.dna'
        sg = SgffObject.new(self.sequence, topology='linear')
        full_site = SgffBindingSite(start=20, end=70, bound_strand='+', annealed_bases=self.full)
        partial_site = SgffBindingSite(start=90, end=110, bound_strand='+', annealed_bases=self.prefix)
        partial_site.extras = {'Component': [{'hybridizedRange': '90-109', 'bases': self.prefix},
                                            {'bases': self.full[20:]}]}
        sg.primers.add(SgffPrimer(name='independent_primer', sequence=self.full,
                                 binding_sites=[full_site, partial_site]))
        SgffWriter.to_file(sg, str(self.path))

    def tearDown(self):
        self.temp.cleanup()

    def partial(self, record):
        return [f for f in record.features if f.qualifiers.get('binding_status') == ['native_partial']]

    def test_native_prefix_match_is_history_and_roundtrips_without_dropping_fields(self):
        source = as_molecule(self.path)
        partial = self.partial(source)
        self.assertTrue(partial)
        for feature in partial:
            self.assertEqual(feature.type, 'primer_bind')
            self.assertEqual(feature.qualifiers['primer_sequence'], [self.full])
            self.assertEqual(str(feature.extract(source.seq)), self.prefix)
            self.assertIn('source_binding', feature.qualifiers)
            self.assertNotIn('binding_core_length', feature.qualifiers)
        files = export_snapgene(source, self.root / 'out').analysis
        for key in ('gb_file', 'dna_file'):
            reread = as_molecule(files[key])
            self.assertEqual(str(reread.seq), self.sequence)
            self.assertEqual(reread.to_dict()['features'], source.to_dict()['features'])

    def test_explicit_active_prefix_binding_is_still_rejected(self):
        source = as_molecule(self.path)
        with self.assertRaisesRegex(Exception, 'end with its binding_sequence'):
            annotate_record_primers(source, [{'name': 'active', 'sequence': self.full,
                    'binding_sequence': self.prefix, 'binding_interval_0based': [90, 110], 'strand': 1}])

    def test_actual_3prime_suffix_stays_active(self):
        source = as_molecule(self.path)
        suffix = self.full[-20:]
        result = annotate_record_primers(source, [{'name': 'valid_suffix', 'sequence': self.full,
                 'binding_sequence': suffix, 'binding_interval_0based': [50, 70], 'strand': 1}])
        feature = next(f for f in result.features if f.qualifiers.get('label') == ['valid_suffix'])
        self.assertEqual(feature.qualifiers['binding_sequence'], [suffix])
        self.assertNotIn('binding_status', feature.qualifiers)

    def test_shifted_partial_site_keeps_current_position_and_original_source_record(self):
        source = as_molecule(self.path)
        partial = self.partial(source)
        self.assertTrue(partial)
        shifted = extract_subsequence(source, 10, 140).only_product()
        current = self.partial(shifted)
        self.assertTrue(current)
        self.assertEqual(int(current[0].location.start), 80)
        self.assertNotIn('binding_core_length', current[0].qualifiers)
        files = export_snapgene(shifted, self.root / 'shifted').analysis
        self.assertEqual(as_molecule(files['dna_file']).to_dict()['features'], shifted.to_dict()['features'])

    def test_contradictory_partial_source_components_do_not_bypass_export(self):
        source = as_molecule(self.path)
        feature = self.partial(source)[0]
        recorded = json.loads(feature.qualifiers['source_binding'][0])
        recorded['native_site']['extras']['Component'][1]['bases'] = 'A' * len(self.full[20:])
        feature.qualifiers['source_binding'] = [json.dumps(recorded)]
        with self.assertRaisesRegex(Exception, 'contradicts'):
            export_snapgene(source, self.root / 'contradictory')


if __name__ == '__main__':
    unittest.main()
