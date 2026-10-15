"""Independent material-boundary regressions, not answer-derived construction routes.

The prior end helper accepted both label equality and actual extension
complementarity. These tests keep both inputs but declare their meanings.
"""
from repository_paths import PROJECT_ROOT, SKILL_ROOT
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord
from core.models.molecule import Molecule, as_molecule
from core.tools.restriction import check_overhang_compatibility
from core.tools.snapgene_io import export_snapgene, write_native_dna
from core.workflow import run_step
from core.workflow_validation import replay_steps


class MaterialContinuityBoundaries(unittest.TestCase):
    @staticmethod
    def source():
        rng = random.Random(531103)
        record = SeqRecord(Seq(''.join(rng.choice('ACGT') for _ in range(1200))),
                           id='independent', name='independent', description='Independent source',
                           annotations={'molecule_type': 'DNA', 'topology': 'circular', 'comment': 'Original provenance'})
        record.features = [SeqFeature(CompoundLocation([
            FeatureLocation(3, 18, strand=-1), FeatureLocation(70, 85, strand=-1)], operator='join'),
            type='misc_feature', id='feature_identity', qualifiers={'label': ['joined marker']})]
        return Molecule(record, strandedness='double')

    def test_end_representation_does_not_confuse_actual_extension_with_label(self):
        self.assertFalse(check_overhang_compatibility('AAGC', 'AAGC').analysis['compatible'])
        self.assertTrue(check_overhang_compatibility('AAGC', 'GCTT').analysis['compatible'])
        label = check_overhang_compatibility('AAGC', 'AAGC', representation='junction_label').analysis
        self.assertTrue(label['compatible'])
        self.assertFalse(check_overhang_compatibility('AAGC', 'GCTT', representation='junction_label').analysis['compatible'])
        self.assertEqual(label['representation'], 'junction_label')
        self.assertEqual(label['scope'], 'junction_label_equality')

    def test_unknown_topology_is_reported_before_qc_design(self):
        source = self.source()
        source.annotations['topology'] = None
        record = run_step('recipe_cloning_verification', {
            'recombinant_plasmid_seq_or_file': '$source', 'insert_start_0based': 300, 'insert_end_0based': 700},
            step_id='qc', sources={'source': source})
        self.assertIsNotNone(record.error)
        self.assertEqual(record.error['error_code'], 'MOLECULE_TOPOLOGY_REQUIRED')
        self.assertIn('recombinant_plasmid_seq_or_file.topology', record.error['missing_fields'])
        self.assertNotIn("'none'", record.error['message'])
        self.assertIsNone(source.topology)
        self.assertEqual(record.operations, [])

    def test_export_retains_original_material_version_and_rejects_file_edits(self):
        original = self.source()
        version = original.record_version
        with tempfile.TemporaryDirectory() as temp:
            files = export_snapgene(original, temp).analysis
            for key in ('gb_file', 'dna_file'):
                with self.subTest(format=key):
                    loaded = as_molecule(files[key])
                    self.assertEqual(loaded.record_version, version)
                    self.assertEqual(str(loaded.features[0].extract(loaded.seq)),
                                     str(original.features[0].extract(original.seq)))
            gb = Path(files['gb_file'])
            edited = SeqIO.read(gb, 'genbank')
            edited.features[0].qualifiers['label'] = ['changed annotation']
            with gb.open('w', encoding='utf-8') as handle:
                SeqIO.write(edited, handle, 'genbank')
            with self.assertRaisesRegex(ValueError, 'File-visible material information changed'):
                as_molecule(gb)
            native = Path(files['dna_file'])
            # Edit the actual native feature packet, not a reader's cached XML.
            raw = native.read_bytes()
            self.assertIn(b'joined marker', raw)
            native.write_bytes(raw.replace(b'joined marker', b'edited marker'))
            with self.assertRaisesRegex(ValueError, 'File-visible material information changed'):
                as_molecule(native)
        self.assertEqual(original.record_version, version)

    def test_native_format_normalization_does_not_redefine_molecule(self):
        from Bio.SeqFeature import BeforePosition
        rec = SeqRecord(Seq('GCTGCTTAA'), id='fuzzy', name='fuzzy',
                        annotations={'molecule_type': 'DNA', 'topology': 'linear'})
        rec.features = [SeqFeature(FeatureLocation(BeforePosition(0), 9, strand=1), type='CDS',
                                   qualifiers={'label': ['partial domain']})]
        source = Molecule(rec, strandedness='double')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'fuzzy.dna'
            write_native_dna(source, path)
            self.assertEqual(as_molecule(path).record_version, source.record_version)
        self.assertNotIn('partial', source.features[0].qualifiers)

    def test_format_aliases_and_comment_whitespace_do_not_change_identity(self):
        source = self.source()
        source.annotations['molecule_type'] = 'ds-DNA'
        source.annotations['comment'] = '  Original provenance \nAdditional context  '
        source.features.append(SeqFeature(FeatureLocation(100, 120, strand=1), type='primer_bind',
                                          qualifiers={'label': ['actual source primer']}))
        version = source.record_version
        with tempfile.TemporaryDirectory() as temp:
            files = export_snapgene(source, temp).analysis
            for key in ('gb_file', 'dna_file'):
                with self.subTest(format=key):
                    self.assertEqual(as_molecule(files[key]).record_version, version)
        self.assertEqual(source.record_version, version)

    def test_sequence_edits_do_not_inherit_file_metadata(self):
        source = self.source()
        with tempfile.TemporaryDirectory() as temp:
            files = export_snapgene(source, temp).analysis
            gb = Path(files['gb_file'])
            edited = SeqIO.read(gb, 'genbank')
            replacement = 'A' if str(edited.seq)[0] != 'A' else 'C'
            edited.seq = Seq(replacement + str(edited.seq)[1:])
            with gb.open('w', encoding='utf-8') as handle:
                SeqIO.write(edited, handle, 'genbank')
            with self.assertRaisesRegex(ValueError, 'File-visible material information changed'):
                as_molecule(gb)
            native = Path(files['dna_file'])
            raw = native.read_bytes()
            original_dna = str(source.seq).encode('ascii')
            self.assertIn(original_dna, raw)
            native.write_bytes(raw.replace(original_dna, (replacement + str(source.seq)[1:]).encode('ascii')))
            with self.assertRaisesRegex(ValueError, 'File-visible material information changed'):
                as_molecule(native)

    def test_pcr_product_coordinates_are_current_before_export(self):
        from core.tools.amplification import simulate_pcr
        from core.tools.snapgene_io import annotate_record_primers
        rng = random.Random(890117)
        sequence = ''.join(rng.choice('ACGT') for _ in range(500))
        source = SeqRecord(Seq(sequence), id='primer_source', annotations={'molecule_type':'DNA', 'topology':'linear'})
        core = str(Seq(sequence[214:235]).reverse_complement())
        source = annotate_record_primers(source, [
            {'name':'inside', 'sequence':'AACCGG'+core, 'binding_sequence':core,
             'binding_interval_0based':[214,235], 'strand':'-'},
            {'name':'clipped', 'sequence':'GGTT'+sequence[338:368], 'binding_sequence':sequence[338:368],
             'binding_interval_0based':[338,368], 'strand':'+'}])
        original_version = source.record_version
        product = simulate_pcr(source, 'GGCT'+sequence[80:102], str(Seq(sequence[318:340]).reverse_complement()),
            forward_binding_core_length=22, reverse_binding_core_length=22).only_product()
        self.assertEqual(str(product.seq), 'GGCT'+sequence[80:340])
        inside = next(f for f in product.features if f.qualifiers.get('label') == ['inside'])
        self.assertEqual(inside.qualifiers['binding_interval'], ['[138,159]'])
        self.assertEqual(inside.qualifiers['binding_strand'], ['-'])
        self.assertEqual(str(inside.extract(product.seq)), core)
        clipped = next(f for f in product.features if f.qualifiers.get('label') == ['clipped'])
        self.assertEqual(clipped.type, 'misc_feature')
        self.assertEqual(clipped.qualifiers['partial'], ['true'])
        self.assertNotIn('binding_interval', clipped.qualifiers)
        self.assertEqual(json.loads(clipped.qualifiers['source_binding'][-1])['binding_interval'], ['[338,368]'])
        self.assertEqual(json.loads(clipped.qualifiers['binding_retained'][0]),
                         [{'start0':262, 'end0':264, 'strand':1}])
        with tempfile.TemporaryDirectory() as temp:
            files = export_snapgene(product, temp).analysis
            for key in ('gb_file','dna_file'):
                self.assertEqual(as_molecule(files[key]).record_version, product.record_version)
        self.assertEqual(source.record_version, original_version)

    def test_origin_crossing_reverse_extraction_updates_binding_fields(self):
        from core.tools.sequence_ops import extract_subsequence
        from core.tools.snapgene_io import annotate_record_primers
        rng = random.Random(891071)
        sequence = ''.join(rng.choice('ACGT') for _ in range(400))
        for strand in (1,-1):
            with self.subTest(strand=strand):
                core = sequence[380:]+sequence[:7]
                if strand == -1:
                    core = str(Seq(core).reverse_complement())
                source = SeqRecord(Seq(sequence), id='wrap', annotations={'molecule_type':'DNA','topology':'circular'})
                source = annotate_record_primers(source, [{'name':'wrapped', 'sequence':'GGCC'+core,
                    'binding_sequence':core, 'binding_interval_0based':[380,7], 'strand':strand}])
                version = source.record_version
                product = extract_subsequence(source,370,40,strand=-1).only_product()
                self.assertEqual(str(product.seq), str(Seq(sequence[370:]+sequence[:40]).reverse_complement()))
                feature = product.features[0]
                self.assertEqual(feature.qualifiers['binding_interval'], ['[33,60]'])
                self.assertEqual(feature.qualifiers['binding_strand'], ['-' if strand==1 else '+'])
                self.assertEqual(str(feature.extract(product.seq)), core)
                self.assertEqual(source.record_version, version)

    def test_coordinate_refresh_does_not_repair_an_incorrect_binding_core(self):
        from core.tools.sequence_ops import extract_subsequence
        from core.tools.snapgene_io import annotate_record_primers
        source = SeqRecord(Seq('A'*100), id='bad_core', annotations={'molecule_type':'DNA','topology':'linear'})
        source = annotate_record_primers(source, [{'name':'bad', 'sequence':'GG'+'A'*20,
             'binding_sequence':'A'*20, 'binding_interval_0based':[20,40], 'strand':1}])
        source.seq = Seq('C'*100)
        product = extract_subsequence(source,10,60).only_product()
        self.assertEqual(product.features[0].qualifiers['binding_interval'], ['[10,30]'])
        self.assertEqual(product.features[0].qualifiers['binding_sequence'], ['A'*20])
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(ValueError, 'does not match'):
            export_snapgene(product, temp)

    def test_implicit_binding_core_is_observed_without_inventing_full_oligo(self):
        from core.tools.sequence_ops import extract_subsequence
        rng = random.Random(449311)
        sequence = ''.join(rng.choice('ACGT') for _ in range(150))
        record = SeqRecord(Seq(sequence), id='implicit', annotations={'molecule_type':'DNA','topology':'linear'})
        record.features = [SeqFeature(FeatureLocation(29,44,strand=1), type='primer_bind', qualifiers={'label':['source site']})]
        source = Molecule(record, strandedness='double')
        version = source.record_version
        product = extract_subsequence(source,20,60).only_product()
        feature = product.features[0]
        self.assertEqual(feature.qualifiers['binding_sequence'], [sequence[29:44]])
        self.assertEqual(feature.qualifiers['binding_interval'], ['[9,24]'])
        self.assertNotIn('primer_sequence', feature.qualifiers)
        self.assertNotIn('full_sequence', feature.qualifiers)
        self.assertEqual(source.record_version, version)
        with tempfile.TemporaryDirectory() as temp:
            files = export_snapgene(product, temp).analysis
            for key in ('gb_file', 'dna_file'):
                self.assertEqual(as_molecule(files[key]).record_version, product.record_version)

    def test_actual_run_step_files_continue_and_finalize(self):
        # Independently known synthesis duplex, self-ligation and full annotated file.
        # No sample-specific DNA, target coordinates or expected outputs in production.
        top = 'AGGTCACGTGACCTAGTCGATTCAGGCTACGTCAGC'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trace_config = root / 'trace.json'
            trace_config.write_text('{"trace_level":"off"}', encoding='utf-8')
            env = {**os.environ, 'SNAPGENE_TRACE_CONFIG': str(trace_config)}

            def invoke(script, config, directory, flags=(), expected_exit=0):
                input_path = root / (directory + '.input.json')
                input_path.write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
                process = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(SKILL_ROOT / 'scripts' / script),
                    '--input', str(input_path), '--out-dir', str(root / directory), *flags],
                    cwd=PROJECT_ROOT, env=env, encoding='utf-8', errors='replace', capture_output=True)
                result = json.loads(process.stdout)
                self.assertEqual(process.returncode, expected_exit, result)
                return result

            prepared = invoke('run_step.py', {'step_id': 'duplex', 'method': 'anneal_oligos',
                'params': {'top_oligo': top, 'bottom_oligo': str(Seq(top).reverse_complement())},
                'requirements': {'topology': 'circular', 'expected_sequence': top}}, 'prepare')
            history = json.loads(Path(prepared['record_file']).read_text(encoding='utf-8'))
            product_version = history['steps'][0]['result']['products'][0]['record_version']
            for fmt in ('gb_file', 'dna_file'):
                with self.subTest(format=fmt):
                    file_path = prepared['material_files'][product_version][fmt]
                    circularized = invoke('run_step.py', {'step_id': 'circular', 'method': 'ligate_fragments',
                        'history_file': prepared['record_file'], 'params': {'fragments': [file_path], 'circular': True}}, fmt)
                    current = json.loads(Path(circularized['record_file']).read_text(encoding='utf-8'))
                    replayed = replay_steps(current['steps'], current['sources'])
                    self.assertEqual(str(replayed[-1].result.only_product().seq), top)
                    current_file = next(iter(circularized['material_files'].values()))['gb_file']
                    # The original circular fixture is retained as a negative:
                    # 36 bp has neither an origin nor a selectable marker.
                    rejected = invoke('finalize_workflow.py', {'record_file': circularized['record_file'],
                        'candidate': current_file}, fmt + '_circle_rejected', flags=('--deliver', '--confirmed'), expected_exit=1)
                    report = rejected['error']['details']['validation']
                    self.assertEqual(report['scope_results']['sequence_model']['status'], 'PASSED')
                    self.assertEqual(report['scope_results']['preparation_model']['status'], 'PASSED')
                    self.assertTrue(any('BIO-08-REPLICON_MARKER' in e for e in report['errors']))

            linear = invoke('run_step.py', {'step_id': 'duplex', 'method': 'anneal_oligos',
                'params': {'top_oligo': top, 'bottom_oligo': str(Seq(top).reverse_complement())},
                'requirements': {'topology': 'linear', 'expected_sequence': top + top}}, 'linear_prepare')
            linear_history = json.loads(Path(linear['record_file']).read_text(encoding='utf-8'))
            linear_version = linear_history['steps'][0]['result']['products'][0]['record_version']
            for fmt in ('gb_file', 'dna_file'):
                with self.subTest(linear_format=fmt):
                    file_path = linear['material_files'][linear_version][fmt]
                    joined = invoke('run_step.py', {'step_id': 'joined', 'method': 'ligate_fragments',
                        'history_file': linear['record_file'], 'params': {'fragments': [file_path, file_path], 'circular': False}}, 'linear_' + fmt)
                    current_file = next(iter(joined['material_files'].values()))['gb_file']
                    delivered = invoke('finalize_workflow.py', {'record_file': joined['record_file'],
                        'candidate': current_file}, 'linear_' + fmt + '_delivery', flags=('--deliver', '--confirmed'))
                    self.assertEqual(delivered['status'], 'delivered')
                    self.assertEqual(str(as_molecule(Path(delivered['directory']) / 'construct.gb').seq), top + top)
                    self.assertEqual(str(as_molecule(Path(delivered['directory']) / 'construct.dna').seq), top + top)
                    self.assertFalse(delivered['task_completion']['original_task_verified'])


if __name__ == '__main__':
    unittest.main()
