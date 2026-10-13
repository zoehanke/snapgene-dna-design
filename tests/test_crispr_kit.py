"""Public CLI tests; expected DNA/directions follow independently constructed inputs."""
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature

from crispr_synthetic_fixture import build_cases, write_native

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'genome-revival-toolkit/scripts/run_toolkit.py'


def fixture(directory, seed, kind='control', replace=False, genotype=True, self_site=False, bad_pam=False, origin=True):
    case = build_cases(seed)[kind]
    vector = case.vector
    rng = random.Random(seed + 551)
    codons = [a+b+c for a in 'ACGT' for b in 'ACGT' for c in 'ACGT' if a+b+c not in ('TAA','TAG','TGA')]
    # A complete synthetic ORF is an annotation classifier input, not functional URA3.
    orf = 'ATG' + ''.join(rng.choice(codons) for _ in range(98)) + 'TAA'
    bases = str(vector.seq)
    vector.seq = Seq(bases[:200] + orf + bases[500:])
    vector.features.append(SeqFeature(FeatureLocation(200,500,strand=1),type='CDS',
        qualifiers={'label':['URA3'], 'note':['Synthetic ORF; marker function NOT_TESTED']}))
    if origin:
        vector.features.append(SeqFeature(FeatureLocation(600,700,strand=1),type='rep_origin',
            qualifiers={'label':['synthetic origin locator'], 'note':['Annotation-only synthetic input; replication NOT_TESTED']}))
    if self_site:
        vector.seq += Seq(case.intended_spacer + 'CGG')
    target = case.target
    spacer = case.new_spacer if replace else case.intended_spacer
    if replace:
        raw = str(target.seq)
        target.seq = Seq(raw[:case.target_start] + spacer + raw[case.target_start+20:])
    if bad_pam:
        raw = str(target.seq)
        target.seq = Seq(raw[:case.target_start+20] + 'CAA' + raw[case.target_start+23:])
    write_native(vector, directory/'vector.dna', double_stranded=True)
    with (directory/'target.gb').open('w',encoding='utf-8') as handle:
        SeqIO.write(target,handle,'genbank')
    context = {'references':{'vector':{'path':'vector.dna'},'target':{'path':'target.gb'}}}
    request = {'original_request':'Check my synthetic guide and conditional selection; prepare a replacement only when explicitly requested.',
        'operation':'replace' if replace else 'check', 'vector_reference':'vector', 'target_reference':'target',
        'scaffold_seq':case.scaffold}
    if replace:
        request['spacer_seq'] = spacer
    if genotype:
        request['strain_genotype'] = {'description':'Explicit synthetic test background',
            'organism':'S. cerevisiae','existing_markers':[],'auxotrophies':['ura3']}
    for name, data in [('context.json',context),('request.json',request)]:
        (directory/name).write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    (directory/'trace-settings.json').write_text('{"trace_level":"observed"}',encoding='utf-8')
    expected = str(vector.seq[:60]) + spacer + str(vector.seq[80:]) if replace else str(vector.seq)
    return request, expected


def execute(directory):
    env = {**os.environ,'SNAPGENE_TRACE_CONFIG':str(directory/'trace-settings.json')}
    process = subprocess.run([sys.executable,'-X','utf8','-B',str(CLI),'crispr',
        '--context',str(directory/'context.json'),'--request',str(directory/'request.json'),
        '--out-dir',str(directory/'result')],capture_output=True,text=True,encoding='utf-8',env=env)
    detail = directory/'result/result.json'
    return process, json.loads(detail.read_text(encoding='utf-8')) if detail.is_file() else None


def append_marker(directory, label):
    # Independently literal complete ORF: annotation-only, no phenotype claimed.
    with (directory/'vector.dna').open('rb') as handle:
        vector = SeqIO.read(handle, 'snapgene')
    start = len(vector.seq)
    vector.seq += Seq('ATG' + 'GCT'*98 + 'TAA')
    vector.features.append(SeqFeature(FeatureLocation(start, start+300, strand=1), type='CDS',
        qualifiers={'label':[label], 'note':['Synthetic ORF; function NOT_TESTED']}))
    write_native(vector, directory/'vector.dna', double_stranded=True)


class CrisprKitTests(unittest.TestCase):
    def test_truncated_target_has_no_pam(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root,42043)
            with (root/'target.gb').open(encoding='utf-8') as handle:
                target=SeqIO.read(handle,'genbank')
            target.seq=target.seq[:build_cases(42043)['control'].target_start+20]
            target.features=[]
            with (root/'target.gb').open('w',encoding='utf-8') as handle:
                SeqIO.write(target,handle,'genbank')
            process,result=execute(root)
            self.assertEqual(process.returncode,2,process.stdout+process.stderr)
            self.assertEqual(result['grna']['direction_status'],'INVALID_PAM')

    def test_shuttle_marker_is_scoped_to_declared_recipient(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root,17011);append_marker(root,'AmpR')
            process,result=execute(root)
            self.assertEqual(process.returncode,0,process.stdout+process.stderr)
            self.assertEqual(result['selection']['status'],'DECLARED_COMPATIBLE')
            marker=next(row for row in result['selection']['markers'] if row['marker_id']=='amp')
            self.assertEqual(marker['compatibility'],'NOT_APPLICABLE')
            self.assertEqual(marker['plate_options'][0]['compatibility'],'UNKNOWN')
            self.assertIn('LB + ampicillin',(root/'result/selection.tsv').read_text(encoding='utf-8'))

    def test_generic_aph_and_tetr_do_not_establish_resistance(self):
        for label in ('APH(6)-Id','tetR'):
            with self.subTest(label=label),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);request,_=fixture(root,42043);append_marker(root,label)
                request['strain_genotype']={'organism':'E. coli','existing_markers':[]}
                (root/'request.json').write_text(json.dumps(request),encoding='utf-8')
                process,result=execute(root)
                self.assertEqual(process.returncode,2,process.stdout+process.stderr)
                self.assertEqual(result['selection']['status'],'UNKNOWN')
                self.assertIn(label,[row['name'] for row in result['selection']['unmapped_markers']])
                self.assertFalse(any(row['marker_id'] in ('kan','tet') for row in result['selection']['markers']))

    def test_documented_natmx_and_unmapped_cassette_are_not_omitted(self):
        for label, expected in [('NatMX','DECLARED_COMPATIBLE'),('patMX','UNKNOWN')]:
            with self.subTest(label=label),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);fixture(root,17011);append_marker(root,label)
                process,result=execute(root)
                self.assertEqual(result['selection']['status'],expected)
                if label=='NatMX':
                    self.assertEqual(process.returncode,0,process.stdout+process.stderr)
                    marker=next(row for row in result['selection']['markers'] if row['marker_id']=='nat')
                    self.assertIn('Nourseothricin',marker['plate_options'][0]['plate'])
                    self.assertEqual(marker['plate_options'][0]['source']['source_type'],'peer_reviewed_paper')
                else:
                    self.assertEqual(process.returncode,2,process.stdout+process.stderr)
                    self.assertIn(label,[row['name'] for row in result['selection']['unmapped_markers']])

    def test_original_unannotated_maintenance_template_still_fails_core_delivery(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root,17011,replace=True,origin=False)
            process,result=execute(root)
            self.assertEqual(process.returncode,2,process.stdout+process.stderr)
            self.assertEqual(result['status'],'failed')
            failure=next(row for row in result['checks'] if row['name']=='core_delivery')
            self.assertTrue(any('BIO-08-REPLICON_MARKER' in error
                                for error in failure['details']['details']['validation']['errors']))

    def test_original_single_strand_packet_cannot_claim_inverse_pcr(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root,17011,replace=True)
            path=root/'vector.dna';raw=bytearray(path.read_bytes())
            # 19-byte header followed by DNA packet's 5-byte TLV header.
            raw[24]=0x01
            path.write_bytes(raw)
            process,result=execute(root)
            self.assertEqual(process.returncode,2,process.stdout+process.stderr)
            self.assertEqual(result['status'],'incomplete')
            self.assertEqual(result['preparation']['preparation_route']['status'],'UNAVAILABLE')
            self.assertIn('duplex',result['preparation']['preparation_route']['reason'])

    def test_two_native_templates_complete_planned_replacement_and_exact_files(self):
        for seed in (17011,42043):
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as temp:
                root=Path(temp); _,expected=fixture(root,seed,replace=True)
                process,result=execute(root)
                self.assertEqual(process.returncode,0,process.stdout+process.stderr)
                self.assertEqual(result['status'],'delivered')
                self.assertEqual(result['grna']['direction_status'],'CORRECT')
                self.assertEqual(result['laboratory_status'],'PLANNED')
                self.assertEqual(result['wet_lab'],'NOT_PERFORMED')
                self.assertEqual(result['preparation']['preparation_route']['simulation_status'],'PASSED')
                delivery=Path(result['delivery']['directory'])
                with (delivery/'construct.gb').open(encoding='utf-8') as handle:
                    actual=SeqIO.read(handle,'genbank')
                self.assertEqual(str(actual.seq),expected)
                self.assertTrue((delivery/'primer_order_table.tsv').is_file())
                verified=subprocess.run([sys.executable,'-X','utf8','-B',str(CLI),'verify','--out-dir',str(root/'result')],
                    capture_output=True,text=True,encoding='utf-8')
                self.assertEqual(json.loads(verified.stdout)['status'],'verified',verified.stdout)

    def test_reversed_shifted_missing_pam_and_self_target_are_not_successes(self):
        for kind,pam,self_site,expected in [('reversed',False,False,'REVERSED'),
                                          ('shifted',False,False,'INVALID_PAM'),
                                          ('control',True,False,'INVALID_PAM'),
                                          ('control',False,True,'CORRECT')]:
            with self.subTest(case=(kind,pam,self_site)),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);fixture(root,17011,kind,bad_pam=pam,self_site=self_site)
                process,result=execute(root)
                self.assertEqual(process.returncode,2,process.stdout+process.stderr)
                self.assertEqual(result['grna']['direction_status'],expected)
                if self_site:self.assertEqual(result['self_target']['self_target_status'],'EXACT_MATCH')

    def test_annotation_direction_is_warning_not_bad_dna(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root,42043,'annotation_conflict')
            process,result=execute(root)
            self.assertEqual(process.returncode,0,process.stdout+process.stderr)
            self.assertEqual(result['grna']['direction_status'],'CORRECT')
            self.assertTrue(result['grna']['warnings'])

    def test_false_cds_and_existing_marker_conflict_do_not_infer_safe_plate(self):
        for kind in ('spacer_cds','control'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);request,_=fixture(root,17011,kind)
                if kind=='control':
                    request['strain_genotype']['existing_markers']=['URA3']
                    (root/'request.json').write_text(json.dumps(request),encoding='utf-8')
                process,result=execute(root)
                self.assertEqual(process.returncode,2,process.stdout+process.stderr)
                self.assertEqual(result['selection']['status'],'CONFLICT')
                self.assertFalse(any(row['marker_id']=='amp' for row in result['selection']['markers']))

    def test_missing_genotype_stays_unknown_and_selection_file_is_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root,42043,genotype=False)
            process,result=execute(root)
            self.assertEqual(process.returncode,2,process.stdout+process.stderr)
            self.assertEqual(result['status'],'incomplete')
            self.assertEqual(result['selection']['status'],'UNKNOWN')
            self.assertIn('未提供基因型，无法判断兼容性',result['selection']['message'])
            table=root/'result/selection.tsv';table.write_text('changed',encoding='utf-8')
            checked=subprocess.run([sys.executable,'-X','utf8','-B',str(CLI),'verify','--out-dir',str(root/'result')],
                capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(json.loads(checked.stdout)['status'],'incomplete')


if __name__=='__main__':unittest.main()
