"""Structured primer history must survive the actual GB qualifier, not a COMMENT repair."""
from repository_paths import SKILL_ROOT
import base64
import copy
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
import warnings
from pathlib import Path

from Bio import SeqIO, BiopythonParserWarning
from sgffp import SgffObject, SgffPrimer, SgffBindingSite, SgffWriter, SgffReader
from core.models.molecule import as_molecule
from core.tools import export_snapgene


class GenBankPrimerHistoryEncodingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='引物历史-')
        self.root = Path(self.temp.name)
        bases = ''.join(random.Random(775029).choices('ACGT', k=160))
        self.full = bases[20:70]
        self.prefix = self.full[:20]
        self.sequence = bases[:90] + self.prefix + bases[110:]
        self.source = self.root / 'source.dna'
        sg = SgffObject.new(self.sequence, topology='linear')
        partial = SgffBindingSite(start=90, end=110, bound_strand='+', annealed_bases=self.prefix)
        partial.extras = {'Component': [{'hybridizedRange': '90-109', 'bases': self.prefix},
                                       {'bases': self.full[20:]}]}
        sg.primers.add(SgffPrimer(name='independent_primer', sequence=self.full,
                                 binding_sites=[partial]))
        SgffWriter.to_file(sg, str(self.source))
        # Expected history comes directly from the independently parsed source,
        # not from Core's qualifier or the implementation under test.
        actual_site = next(iter(SgffReader.from_file(str(self.source)).primers)).binding_sites[0]
        self.expected = {'primer_sequence': self.full, 'binding_sequence': self.prefix,
                         'native_site': {'start': 90, 'end': 110, 'bound_strand': '+',
                                         'annealed_bases': self.prefix,
                                         'melting_temperature': actual_site.melting_temperature,
                                         'simplified': actual_site.simplified,
                                         'extras': copy.deepcopy(actual_site.extras)}}

    def tearDown(self):
        self.temp.cleanup()

    def raw(self, path):
        with Path(path).open(encoding='utf-8') as handle:
            return SeqIO.read(handle, 'genbank')

    def raw_history(self, feature):
        # External reader needs only the physical qualifier and its declared
        # encoding. It never sees MOLECULE-CONTRACT metadata or a Core decoder.
        text = feature.qualifiers['source_binding'][0]
        wire = ''.join(text.split())
        if wire.startswith('base64-json-v1:'):
            text = base64.b64decode(wire.split(':', 1)[1], validate=True).decode('utf-8')
        return json.loads(text)

    def test_raw_genbank_history_is_independently_lossless_without_comment(self):
        material = as_molecule(self.source)
        before = material.to_dict()
        files = export_snapgene(material, self.root / 'out').analysis
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always', BiopythonParserWarning)
            physical = self.raw(files['gb_file'])
        feature = next(f for f in physical.features if f.qualifiers.get('binding_status') == ['native_partial'])
        self.assertEqual(self.raw_history(feature), self.expected)
        self.assertFalse([w for w in caught if issubclass(w.category, BiopythonParserWarning)])
        self.assertEqual(str(physical.seq), self.sequence)
        self.assertEqual(feature.type, 'primer_bind')
        self.assertEqual((int(feature.location.start), int(feature.location.end)), (90, 110))
        self.assertEqual(''.join(feature.qualifiers['primer_sequence'][0].split()), self.full)
        physical.annotations.pop('comment', None)
        detached = self.root / 'physical-only.gb'
        with detached.open('w', encoding='utf-8') as handle:
            SeqIO.write(physical, handle, 'genbank')
        reread = as_molecule(detached)
        restored = next(f for f in reread.features if f.qualifiers.get('binding_status') == ['native_partial'])
        self.assertEqual(json.loads(restored.qualifiers['source_binding'][0]), self.expected)
        native = export_snapgene(reread, self.root / 'physical-reexport').analysis['dna_file']
        actual_primer = next(iter(SgffReader.from_file(native).primers))
        self.assertEqual(actual_primer.sequence, self.full)
        self.assertEqual(actual_primer.binding_sites[0].extras, self.expected['native_site']['extras'])
        self.assertEqual(material.to_dict(), before)

    def test_wrapping_preserves_spaces_quotes_unicode_and_multiple_history_entries(self):
        material = as_molecule(self.source)
        feature = next(f for f in material.features if f.qualifiers.get('binding_status') == ['native_partial'])
        extra = {'binding_interval': ['[90,110]'],
                 'note': '保留 有意义的 空格和 "原始说明" ' * 13,
                 'nested': {'a key with spaces': 'a value with spaces'}}
        feature.qualifiers['source_binding'].append(json.dumps(extra, ensure_ascii=False, separators=(',', ':')))
        before = copy.deepcopy(feature.qualifiers['source_binding'])
        files = export_snapgene(material, self.root / 'multi').analysis
        physical = self.raw(files['gb_file'])
        observed = next(f for f in physical.features if f.qualifiers.get('binding_status') == ['native_partial'])
        decoded = []
        for text in observed.qualifiers['source_binding']:
            wire = ''.join(text.split())
            self.assertTrue(wire.startswith('base64-json-v1:'))
            decoded.append(base64.b64decode(wire.split(':', 1)[1], validate=True).decode('utf-8'))
        self.assertEqual(decoded, before)
        self.assertEqual(as_molecule(files['gb_file']).to_dict()['features'], material.to_dict()['features'])

    def test_encoded_history_rejects_invalid_base64_json_and_unknown_version(self):
        for invalid in ('base64-json-v1:!!!!',
                        'base64-json-v1:' + base64.b64encode(b'not JSON').decode('ascii'),
                        'base64-json-v2:e30='):
            with self.subTest(invalid=invalid):
                material = as_molecule(self.source)
                feature = next(f for f in material.features if f.qualifiers.get('binding_status') == ['native_partial'])
                feature.qualifiers['source_binding'] = [invalid]
                path = self.root / 'invalid.gb'
                with path.open('w', encoding='utf-8') as handle:
                    SeqIO.write(material, handle, 'genbank')
                with self.assertRaisesRegex(ValueError, 'source_binding'):
                    as_molecule(path)

    def test_legacy_plain_history_remains_readable(self):
        material = as_molecule(self.source)
        feature = next(f for f in material.features if f.qualifiers.get('binding_status') == ['native_partial'])
        old = {'binding_interval': ['[90,110]']}
        feature.qualifiers['source_binding'] = [json.dumps(old, separators=(',', ':'))]
        path = self.root / 'legacy.gb'
        with path.open('w', encoding='utf-8') as handle:
            SeqIO.write(material, handle, 'genbank')
        loaded = as_molecule(path)
        actual = next(f for f in loaded.features if f.qualifiers.get('binding_status') == ['native_partial'])
        self.assertEqual(json.loads(actual.qualifiers['source_binding'][0]), old)

    def test_changed_physical_history_cannot_be_repaired_by_old_comment(self):
        material = as_molecule(self.source)
        files = export_snapgene(material, self.root / 'tamper').analysis
        physical = self.raw(files['gb_file'])
        feature = next(f for f in physical.features if f.qualifiers.get('binding_status') == ['native_partial'])
        changed = copy.deepcopy(self.expected)
        changed['native_site']['simplified'] = not changed['native_site']['simplified']
        feature.qualifiers['source_binding'] = ['base64-json-v1:' + base64.b64encode(
            json.dumps(changed, separators=(',', ':')).encode('utf-8')).decode('ascii')]
        path = self.root / 'stale-comment.gb'
        with path.open('w', encoding='utf-8') as handle:
            SeqIO.write(physical, handle, 'genbank')
        with self.assertRaisesRegex(ValueError, 'File-visible material information changed'):
            as_molecule(path)

    def convert(self, source, destination):
        config = self.root / 'trace-off.json'
        config.write_text(json.dumps({'trace_level': 'off'}), encoding='utf-8')
        environment = dict(os.environ, SNAPGENE_TRACE_CONFIG=str(config))
        return subprocess.run([sys.executable, '-X', 'utf8', '-B',
                               str(SKILL_ROOT / 'scripts/convert.py'), str(source),
                               '--out', str(destination), '--format', 'snapgene', '--json'],
                              cwd=self.root, env=environment, capture_output=True,
                              encoding='utf-8', errors='replace', timeout=60)

    def test_actual_convert_cli_authenticates_before_normalizing_wrapped_oligos(self):
        material = as_molecule(self.source)
        files = export_snapgene(material, self.root / 'cli-input').analysis
        before = Path(files['gb_file']).read_bytes()
        destination = self.root / 'converted.dna'
        process = self.convert(files['gb_file'], destination)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        native = SgffReader.from_file(str(destination))
        primer = next(iter(native.primers))
        self.assertEqual(str(native.sequence.data.value), self.sequence)
        self.assertEqual(primer.sequence, self.full)
        self.assertEqual(primer.binding_sites[0].extras, self.expected['native_site']['extras'])
        self.assertEqual(Path(files['gb_file']).read_bytes(), before)

    def test_actual_convert_cli_still_rejects_tampered_physical_history(self):
        files = export_snapgene(as_molecule(self.source), self.root / 'cli-tamper').analysis
        physical = self.raw(files['gb_file'])
        feature = next(f for f in physical.features if f.qualifiers.get('binding_status') == ['native_partial'])
        feature.qualifiers['source_binding'] = ['base64-json-v1:' + base64.b64encode(b'{"edited":true}').decode('ascii')]
        path = self.root / 'changed-history.gb'
        with path.open('w', encoding='utf-8') as handle:
            SeqIO.write(physical, handle, 'genbank')
        destination = self.root / 'must-not-exist.dna'
        process = self.convert(path, destination)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn('File-visible material information changed', process.stdout + process.stderr)
        self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
