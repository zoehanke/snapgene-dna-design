import datetime
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'snapgene-dna-design'))
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from core.models.molecule import as_molecule
from core.tools.snapgene_io import export_snapgene


class MolecularDateTests(unittest.TestCase):
    def material(self):
        record = SeqRecord(Seq('ACGT' * 25), id='dated_source', name='dated_source',
                           annotations={'molecule_type': 'DNA', 'topology': 'linear',
                                        'received': datetime.date(2024, 6, 8),
                                        'created': datetime.datetime(2024, 6, 9, 15, 12, 7, tzinfo=datetime.timezone.utc),
                                        'date': '08-JUN-2024'})
        return as_molecule(record)

    def test_date_metadata_survives_wire_without_changing_sequence_or_type(self):
        material = self.material()
        version = material.record_version
        restored = as_molecule(json.loads(json.dumps(material.to_dict())))
        self.assertEqual(str(restored.seq), 'ACGT' * 25)
        self.assertEqual(restored.annotations['received'], datetime.date(2024, 6, 8))
        self.assertIs(type(restored.annotations['received']), datetime.date)
        self.assertEqual(restored.annotations['created'].isoformat(), '2024-06-09T15:12:07+00:00')
        self.assertIs(type(restored.annotations['created']), datetime.datetime)
        self.assertEqual(restored.annotations['date'], '08-JUN-2024')
        self.assertEqual(restored.record_version, version)

    def test_genbank_and_native_preserve_actual_dates_and_original_source(self):
        material = self.material()
        before = dict(material.annotations)
        with tempfile.TemporaryDirectory(prefix='日期-') as folder:
            files = export_snapgene(material, folder).analysis
            for field in ('gb_file', 'dna_file'):
                loaded = as_molecule(files[field])
                self.assertEqual(loaded.record_version, material.record_version)
                self.assertEqual(loaded.annotations['created'], before['created'])
                self.assertEqual(loaded.annotations['received'], before['received'])
        self.assertEqual(material.annotations, before)

    def test_changed_timestamp_is_a_changed_material_version(self):
        material = self.material()
        before = material.record_version
        material.annotations['received'] = datetime.date(2024, 6, 10)
        self.assertNotEqual(material.record_version, before)


if __name__ == '__main__':
    unittest.main()
