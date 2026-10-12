"""Independent cassette inputs and public-entry regressions, not heldout tasks."""
import copy
import json
import os
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'snapgene-dna-design'))
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord
from core.models.molecule import as_molecule, feature_data
from core.tools import export_snapgene, get_feature
from core.tools.inspection import summarize_backbone
from core.tools.registry import TOOL_REGISTRY

ROOT = pathlib.Path(__file__).resolve().parents[1] / 'snapgene-dna-design'
# Published SpCas9 scaffold prefix, also used by the existing pML104 method.
SCAFFOLD = 'GTTTTAGAGCTAGAAATAGCAAGTTAAAATAAGGC'
OLD = 'ACGATCTGCAATGTCAGCTA'
NEW = 'GATACCTCGTACGATCGTCA'


def cassette():
    # All expected coordinates/products come from this independent construction.
    promoter = 'ACGTCGA' * 4
    gene = 'ATG' + 'GCT' * 40 + 'TAA'
    seq = promoter + OLD + SCAFFOLD + 'TTTTTT' + gene
    rec = SeqRecord(Seq(seq), id='unrelated_vector', name='unrelated_vector',
                    annotations={'molecule_type': 'DNA', 'topology': 'circular'})
    rec.features = [
        SeqFeature(FeatureLocation(0, 28, strand=1), type='promoter', qualifiers={'label': ['Pol III promoter']}),
        SeqFeature(FeatureLocation(28, 48, strand=-1), type='misc_feature', qualifiers={'label': ['old gRNA']}),
        SeqFeature(FeatureLocation(28, 48, strand=1), type='CDS', qualifiers={'label': ['hphNT1']}),
        SeqFeature(FeatureLocation(20, 55, strand=1), type='primer_bind', qualifiers={'label': ['old primer']}),
        SeqFeature(FeatureLocation(48, 83, strand=1), type='misc_RNA', qualifiers={'label': ['scaffold']}),
        SeqFeature(FeatureLocation(89, len(seq), strand=1), type='CDS', qualifiers={'label': ['AmpR']}),
        SeqFeature(FeatureLocation(0, len(seq)), type='source', qualifiers={'note': ['whole source']}),
        SeqFeature(FeatureLocation(28, 48), type='source', qualifiers={'note': ['old local source']}),
    ]
    rec.letter_annotations['quality'] = list(range(len(seq)))
    return rec


def invoke(name, **kwargs):
    # These original v2.2.3 tests own sequence/annotation behavior; physical
    # preparation defaults are tested independently in test_grna_preparation.
    if name == 'replace_grna_spacer':
        kwargs.setdefault('preparation_mode','sequence_only')
    if name not in TOOL_REGISTRY:
        raise AssertionError('Missing public tool: ' + name)
    return TOOL_REGISTRY[name].execute(**kwargs)


class GuideCassetteTests(unittest.TestCase):
    def test_same_length_swap_preserves_backbone_and_records_annotation_dispositions(self):
        source = cassette()
        original = as_molecule(source).to_dict()
        result = invoke('replace_grna_spacer', vector_record_or_seq=source, spacer_seq=NEW)
        product = result.only_product()
        self.assertEqual(str(product.seq), str(source.seq[:28]) + NEW + str(source.seq[48:]))
        self.assertEqual(as_molecule(source).to_dict(), original)
        self.assertEqual(product.topology, 'circular')
        self.assertEqual(result.analysis['replacement']['before'], OLD)
        self.assertEqual(result.analysis['replacement']['after'], NEW)
        kept = [feature_data(f) for f in source.features if f.qualifiers.get('label') == ['AmpR']]
        self.assertEqual([feature_data(f) for f in product.features if f.qualifiers.get('label') == ['AmpR']], kept)
        removed = [row['feature']['name'] for row in result.analysis['annotation_changes']]
        self.assertIn('old gRNA', removed)
        self.assertIn('hphNT1', removed)
        self.assertIn('old primer', removed)
        self.assertEqual(product.letter_annotations['quality'][:28], list(range(28)))
        self.assertEqual(product.letter_annotations['quality'][28:48], [None] * 20)
        self.assertEqual(product.letter_annotations['quality'][48:], list(range(48, len(source))))
        self.assertTrue(any(f.type == 'source' and len(f) == len(source) for f in product.features))
        guide = next(f for f in product.features if f.qualifiers.get('label') == ['gRNA spacer'])
        self.assertEqual(str(guide.extract(product.seq)), NEW)

    def test_reverse_transcribed_cassette_uses_actual_sequence(self):
        source = cassette().reverse_complement(id='other', name='other', annotations=True)
        result = invoke('replace_grna_spacer', vector_record_or_seq=source, spacer_seq=NEW)
        n = len(source)
        expected = str(source.seq[:n-48]) + str(Seq(NEW).reverse_complement()) + str(source.seq[n-28:])
        self.assertEqual(str(result.only_product().seq), expected)
        target = 'AACCTT' + NEW + 'AGG' + 'TAATAC'
        audit = invoke('check_grna', vector_record_or_seq=result.only_product(), target_seq_or_file=target).analysis
        self.assertEqual(audit['transcription_strand'], -1)
        self.assertEqual(audit['spacer'], NEW)
        self.assertEqual(audit['direction_status'], 'CORRECT')

    def test_origin_crossing_spacer_preserves_reference_origin(self):
        # Cut origin ten bases into the spacer, independently of rotation tools.
        rec = cassette()
        seq = str(rec.seq[38:]) + str(rec.seq[:38])
        n = len(seq)
        rec = SeqRecord(Seq(seq), id='wrapped', annotations={'molecule_type': 'DNA', 'topology': 'circular'})
        rec.features = [SeqFeature(FeatureLocation(n-38, n-10, strand=1), type='promoter')]
        result = invoke('replace_grna_spacer', vector_record_or_seq=rec, spacer_seq=NEW)
        self.assertEqual(str(result.only_product().seq), NEW[10:] + seq[10:n-10] + NEW[:10])
        guide = result.only_product().features[-1]
        self.assertEqual(str(guide.extract(result.only_product().seq)), NEW)
        self.assertEqual(len(guide.location.parts), 2)

    def test_invalid_spacer_and_non_20nt_gap_are_rejected(self):
        for spacer in ('A'*19, 'A'*21, 'A'*19+'N'):
            with self.subTest(spacer=spacer), self.assertRaises(Exception):
                invoke('replace_grna_spacer', vector_record_or_seq=cassette(), spacer_seq=spacer)
        rec = cassette()
        rec.features[0].location = FeatureLocation(0, 27, strand=1)
        with self.assertRaisesRegex(Exception, 'cassette|20 nt'):
            invoke('replace_grna_spacer', vector_record_or_seq=rec, spacer_seq=NEW)

    def test_multiple_cassettes_require_selector(self):
        rec = cassette()
        seq = str(rec.seq) * 2
        multi = SeqRecord(Seq(seq), id='multi', annotations=copy.deepcopy(rec.annotations))
        multi.features = [copy.deepcopy(rec.features[0]),
            SeqFeature(FeatureLocation(len(rec), len(rec)+28, strand=1), type='promoter', qualifiers={'label': ['second promoter']})]
        with self.assertRaisesRegex(Exception, 'ambiguous'):
            invoke('replace_grna_spacer', vector_record_or_seq=multi, spacer_seq=NEW)
        result = invoke('replace_grna_spacer', vector_record_or_seq=multi, spacer_seq=NEW, promoter_name='second promoter')
        self.assertEqual(str(result.only_product().seq), str(rec.seq) + str(rec.seq[:28]) + NEW + str(rec.seq[48:]))

    def test_explicit_boundary_and_variant_scaffold(self):
        rec = cassette()
        rec.features = []
        rec.seq = Seq(str(rec.seq).replace(SCAFFOLD, 'CGACTGACCTGTAGTCAGTCAGTTACGATCGATCG'))
        result = invoke('replace_grna_spacer', vector_record_or_seq=rec, spacer_seq=NEW,
            promoter_end_0based=28, transcription_strand=1, scaffold_seq='CGACTGACCTGTAGTCAGTCAGTTACGATCGATCG')
        self.assertEqual(str(result.only_product().seq[28:48]), NEW)
        with self.assertRaises(Exception):
            invoke('replace_grna_spacer', vector_record_or_seq=rec, spacer_seq=NEW, promoter_end_0based=28)

    def test_plus_match_and_annotation_conflict_do_not_imply_reversed_insert(self):
        target = 'AACCTT' + OLD + 'TGG' + 'TAATAC'
        result = invoke('check_grna', vector_record_or_seq=cassette(), target_seq_or_file=target)
        audit = result.analysis
        self.assertEqual(audit['direction_status'], 'CORRECT')
        self.assertIs(audit['direction_correct'], True)
        hit = next(h for h in audit['target_matches'] if h['pam_valid'])
        self.assertEqual(hit['strand'], 1)
        self.assertEqual(hit['protospacer_parts_0based'], [[6, 26]])
        self.assertEqual(hit['pam'], 'TGG')
        self.assertTrue(any(w['code'] == 'GRNA_ANNOTATION_STRAND_CONFLICT' for w in audit['warnings']))
        self.assertEqual(result.checks[0]['status'], 'PASSED')

    def test_minus_match_is_reported_in_reference_coordinates(self):
        target = str(Seq('AACCTT' + OLD + 'CGG' + 'TAATAC').reverse_complement())
        audit = invoke('check_grna', vector_record_or_seq=cassette(), target_seq_or_file=target).analysis
        hit = next(h for h in audit['target_matches'] if h['pam_valid'])
        self.assertEqual(hit['strand'], -1)
        self.assertEqual(hit['rna_binding_strand'], 1)
        self.assertEqual(hit['protospacer_parts_0based'], [[9, 29]])
        self.assertEqual(hit['pam_parts_0based'], [[6, 9]])
        self.assertEqual(hit['pam'], 'CGG')
        self.assertEqual(audit['direction_status'], 'CORRECT')

    def test_reversed_insert_is_distinct_from_invalid_or_missing_pam(self):
        target = 'AACCTT' + str(Seq(OLD).reverse_complement()) + 'CGG' + 'TAATAC'
        audit = invoke('check_grna', vector_record_or_seq=cassette(), target_seq_or_file=target).analysis
        self.assertEqual(audit['direction_status'], 'REVERSED')
        self.assertIs(audit['direction_correct'], False)
        # An exact match alone must not count as a valid guide.
        for target in ('AACCTT' + OLD + 'ATC', 'AACCTT' + OLD):
            audit = invoke('check_grna', vector_record_or_seq=cassette(), target_seq_or_file=target).analysis
            self.assertEqual(audit['direction_status'], 'INVALID_PAM')
            self.assertTrue(all(not h['pam_valid'] for h in audit['target_matches']))
        audit = invoke('check_grna', vector_record_or_seq=cassette(), target_seq_or_file='A'*70).analysis
        self.assertEqual(audit['direction_status'], 'NO_TARGET_MATCH')
        self.assertIsNone(audit['direction_correct'])

    def test_multiple_valid_loci_are_retained(self):
        target = OLD + 'AGG' + 'TTAAA' + OLD + 'TGG'
        audit = invoke('check_grna', vector_record_or_seq=cassette(), target_seq_or_file=target).analysis
        self.assertEqual(len([h for h in audit['target_matches'] if h['query_role']=='transcribed_spacer' and h['pam_valid']]), 2)
        self.assertTrue(any(w['code']=='MULTIPLE_VALID_TARGETS' for w in audit['warnings']))

    def test_short_misannotated_cds_is_not_a_selection_marker(self):
        audit = summarize_backbone(cassette()).analysis
        self.assertEqual([m['name'] for m in audit['selection_markers']], ['AmpR'])
        self.assertTrue(any(w['code']=='SELECTION_MARKER_ANNOTATION_CONFLICT' for w in audit['warnings']))

    def test_real_run_step_and_utf8_export_readback(self):
        with tempfile.TemporaryDirectory(prefix='gRNA-中文-') as folder:
            folder = pathlib.Path(folder)
            rec = cassette()
            rec.features[0].qualifiers['label'] = ['中文启动子']
            # Independent writer supplies input. Do not make expected DNA through Core.
            source = folder / '中文模板.gb'
            with source.open('w', encoding='utf-8') as handle:
                SeqIO.write(rec, handle, 'genbank')
            config = {'method':'replace_grna_spacer', 'params':{'vector_record_or_seq':str(source), 'spacer_seq':NEW, 'preparation_mode':'sequence_only'}}
            cfg = folder / 'step.json'
            cfg.write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
            run = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/run_step.py'), '--input', str(cfg),
                '--out-dir', str(folder/'work')], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            expected = str(rec.seq[:28]) + NEW + str(rec.seq[48:])
            files = json.loads(run.stdout)['material_files']
            info = next(iter(files.values()))
            for key in ('gb_file', 'dna_file'):
                product = as_molecule(info[key])
                self.assertEqual(str(product.seq), expected)
                self.assertTrue(any(f.qualifiers.get('label') == ['中文启动子'] for f in product.features))
            text = pathlib.Path(info['gb_file']).read_bytes().decode('utf-8')
            self.assertIn('中文启动子', text)
            command = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/inspect_plasmid.py'), info['gb_file'], '--json'],
                capture_output=True, text=True, encoding='utf-8',
                env={**os.environ, 'PYTHONUTF8': '0', 'PYTHONIOENCODING': 'cp936'})
            self.assertEqual(command.returncode, 0, command.stderr)
            inspected = json.loads(command.stdout)
            self.assertEqual([m['name'] for m in inspected['selection_markers']], ['AmpR'])


class NativeDateEntryTests(unittest.TestCase):
    def test_independent_native_packets_with_date_through_public_entries(self):
        # SnapGene packet format, independent of the Skill's native writer.
        def packet(kind, payload):
            return struct.pack('>BI', kind, len(payload)) + payload
        data = packet(9, b'SnapGene' + struct.pack('>HHH', 1, 1, 1))
        data += packet(0, b'\x01' + ('ACGT'*25).encode('ascii'))
        data += packet(6, b'<Notes><LastModified>2024.06.08</LastModified></Notes>')
        data += packet(10, b'<Features><Feature type="misc_feature" name="anchor" directionality="1"><Segment range="1-20" type="standard"/></Feature></Features>')
        with tempfile.TemporaryDirectory(prefix='native-日期-') as folder:
            folder = pathlib.Path(folder)
            source = folder/'independent.dna'
            source.write_bytes(data)
            molecule = as_molecule(source)
            self.assertEqual(str(molecule.seq), 'ACGT'*25)
            self.assertEqual(molecule.annotations['date'].isoformat(), '2024-06-08T00:00:00')
            self.assertEqual(str(get_feature(source, 'anchor').only_product().seq), 'ACGT'*5)
            cfg = folder/'step.json'
            cfg.write_text(json.dumps({'method':'get_feature','params':{'file_path_or_record':str(source), 'name_or_type':'anchor'}}), encoding='utf-8')
            run = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/run_step.py'), '--input', str(cfg), '--out-dir', str(folder/'out')],
                capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            saved = json.loads((folder/'out/steps.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['steps'][0]['result']['products'][0]['sequence'], 'ACGT'*5)


class TemplateQCOriginTests(unittest.TestCase):
    def test_public_qc_distinguishes_unchanged_template_error_and_new_error(self):
        bad = 'ATG' + 'GCT'*12 + 'TGA' + 'GCT'*8 + 'TAA'
        good = 'ATG' + 'GCT'*20 + 'TAA'
        source = SeqRecord(Seq(bad + good), id='baseline', annotations={'molecule_type':'DNA', 'topology':'circular'})
        source.features = [
            SeqFeature(FeatureLocation(0,len(bad),strand=1), type='CDS', qualifiers={'label':['same label']}),
            SeqFeature(FeatureLocation(len(bad),len(source),strand=1), type='CDS', qualifiers={'label':['same label']})]
        # Native and text files can differ only in DNA display case.
        source.seq = source.seq.lower()
        # Move both annotations; introduce a stop only in the second CDS.
        seq = 'C'*12 + bad + good[:15] + 'TGA' + good[18:]
        product = SeqRecord(Seq(seq), id='edited', annotations=copy.deepcopy(source.annotations))
        product.features = [SeqFeature(FeatureLocation(12,len(bad)+12,strand=1), type='CDS', qualifiers={'label':['same label']}),
            SeqFeature(FeatureLocation(len(bad)+12,len(product),strand=1), type='CDS', qualifiers={'label':['same label']})]
        with tempfile.TemporaryDirectory(prefix='qc-来源-') as folder:
            folder = pathlib.Path(folder)
            for rec, name in ((source,'template.gb'),(product,'product.gb')):
                with (folder/name).open('w',encoding='utf-8') as handle:
                    SeqIO.write(rec,handle,'genbank')
            command = subprocess.run([sys.executable,'-B',str(ROOT/'scripts/validate_construct.py'),str(folder/'product.gb'),
                '--template',str(folder/'template.gb'),'--json'],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(command.returncode,1,command.stdout+command.stderr)
            payload=json.loads(command.stdout)
            report=payload.get('data',payload)
            issues=[c for c in report['checks'] if c['status']=='error']
            self.assertEqual([c['origin'] for c in issues],['INHERITED_FROM_TEMPLATE','INTRODUCED_OR_CHANGED'])
            self.assertEqual(report['summary']['inherited_errors'],1)
            self.assertEqual(report['summary']['introduced_or_changed_errors'],1)
            self.assertFalse(report['summary']['pass'])
            self.assertFalse(payload['ok'])

    def test_without_template_qc_does_not_invent_error_origin(self):
        rec=cassette()
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'input.gb'
            with path.open('w',encoding='utf-8') as handle:
                SeqIO.write(rec,handle,'genbank')
            run=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/validate_construct.py'),str(path),'--json'],
                capture_output=True,text=True,encoding='utf-8')
            report=json.loads(run.stdout)
            report=report.get('data',report)
            self.assertTrue(all(c.get('origin')=='UNDETERMINED' for c in report['checks'] if c['status']=='error'))


if __name__ == '__main__':
    unittest.main()
