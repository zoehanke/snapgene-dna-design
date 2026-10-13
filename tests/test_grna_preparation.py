"""Independent template construction, physical-route simulations and delivery."""
import copy
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'snapgene-dna-design'))
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import SeqFeature, FeatureLocation
from Bio.SeqRecord import SeqRecord
from Bio.SeqUtils import MeltingTemp as mt
from core.tools import replace_grna_spacer, simulate_pcr, ligate_fragments, rotate_sequence
from core.models.molecule import as_molecule
from core.workflow import run_step
from core.workflow_validation import validate_candidate

ROOT = Path(__file__).resolve().parents[1] / 'snapgene-dna-design'
OLD = 'ACGATCTGCAATGTCAGCTA'
SCAFFOLD = 'GTTTTAGAGCTAGAAATAGCAAGTTAAAATAAGGC'


def published_nn_reference(sequence):
    """Independent arithmetic from published Allawi/SantaLucia NN parameters.

    Source: https://biopython.org/docs/1.88/api/Bio.SeqUtils.MeltingTemp.html
    DNA_NN3 scientific constants, SantaLucia saltcorr=5, von Ahsen Mg/dNTP
    equivalence. This calls neither Core Tm nor Biopython's Tm implementation.
    """
    constants = {'AA':(-7.9,-22.2),'TT':(-7.9,-22.2),'AT':(-7.2,-20.4),'TA':(-7.2,-21.3),
        'CA':(-8.5,-22.7),'TG':(-8.5,-22.7),'GT':(-8.4,-22.4),'AC':(-8.4,-22.4),
        'CT':(-7.8,-21.0),'AG':(-7.8,-21.0),'GA':(-8.2,-22.2),'TC':(-8.2,-22.2),
        'CG':(-10.6,-27.2),'GC':(-9.8,-24.4),'GG':(-8.0,-19.9),'CC':(-8.0,-19.9)}
    enthalpy, entropy = 0.0, 0.0
    for base in (sequence[0],sequence[-1]):
        h,s=(2.3,4.1) if base in 'AT' else (0.1,-2.8)
        enthalpy+=h;entropy+=s
    for index in range(len(sequence)-1):
        h,s=constants[sequence[index:index+2]];enthalpy+=h;entropy+=s
    sodium_equivalent=(50+120*math.sqrt(1.5-0.6))/1000
    entropy+=0.368*(len(sequence)-1)*math.log(sodium_equivalent)
    return 1000*enthalpy/(entropy+1.987*math.log(50e-9/4))-273.15


def template(seed=17123, start=230, n=850):
    rng = random.Random(seed)
    text = ''.join(rng.choice('ACGT') for _ in range(n))
    # Known marker is a complete toy ORF; no functional resistance claim.
    text = text[:600] + 'ATG' + 'GCT'*40 + 'TAA' + text[726:]
    text = text[:start] + OLD + SCAFFOLD + text[start+55:]
    rec = SeqRecord(Seq(text), id='independent_vector', name='independent_vector',
                    annotations={'molecule_type':'DNA','topology':'circular'})
    rec.features = [SeqFeature(FeatureLocation(start-80,start,strand=1),type='promoter'),
        SeqFeature(FeatureLocation(0,60,strand=1),type='rep_origin',qualifiers={'label':['ori']}),
        SeqFeature(FeatureLocation(600,726,strand=1),type='CDS',qualifiers={'label':['AmpR']})]
    return rec


class GuidePreparationTests(unittest.TestCase):
    def test_route_is_planned_but_independently_simulated_and_replayable(self):
        for seed, spacer in ((17123,'GATACCTCGTACGATCGTCA'),(9937,'CGTACTAGCGACTATGACCG')):
            with self.subTest(seed=seed):
                rec=template(seed)
                expected=str(rec.seq[:230])+spacer+str(rec.seq[250:])
                result=replace_grna_spacer(rec,spacer)
                route=result.analysis['preparation_route']
                self.assertEqual(route['status'],'PLANNED')
                self.assertEqual(route['simulation_status'],'PASSED')
                self.assertEqual(route['wet_lab'],'NOT_PERFORMED')
                self.assertEqual(str(result.only_product().seq),expected)
                row=result.analysis['preparation'][0]
                f,r=row['primers']
                # Exactly one 5-prime payload; either placement satisfies the task.
                self.assertEqual(bool(f['five_prime_tail'])+bool(r['five_prime_tail']),1)
                self.assertEqual(f['five_prime_tail'] or str(Seq(r['five_prime_tail']).reverse_complement()),spacer)
                for primer in (f,r):
                    self.assertEqual(primer['sequence'],primer['five_prime_tail']+primer['binding_sequence'])
                for primer in (f,r):
                    # Independent documented public calculator, not Core Tm output.
                    reference=mt.Tm_NN(primer['binding_sequence'],nn_table=mt.DNA_NN3,
                        Na=50,Mg=1.5,dNTPs=0.6,dnac1=25,dnac2=25,saltcorr=5)
                    independent=published_nn_reference(primer['binding_sequence'])
                    self.assertAlmostEqual(independent,reference,places=6)
                    self.assertAlmostEqual(primer['binding_core_tm'],reference,delta=0.6)
                    self.assertGreaterEqual(primer['binding_core_tm'],52.0)
                    self.assertLessEqual(primer['binding_core_tm'],72.0)
                    self.assertIn('purification',primer)
                pcr=simulate_pcr(rec,f['sequence'],r['sequence'],topology='circular',
                    forward_binding_core_length=len(f['binding_sequence']),reverse_binding_core_length=len(r['binding_sequence']))
                circ=ligate_fragments([pcr.only_product()],circular=True)
                restored=rotate_sequence(circ.only_product(),(len(rec)-250+len(f['five_prime_tail']))%len(rec)).only_product()
                self.assertEqual(str(restored.seq),expected)
                self.assertEqual(str(as_molecule(row['product']).seq),str(pcr.only_product().seq))
                self.assertTrue(any(c['scope']=='preparation_model' and c['status']=='PASSED' for c in result.checks))

    def test_minus_and_origin_crossing_use_original_reference(self):
        spacer='CGTACTAGCGACTATGACCG'
        rec=template(9937)
        minus=rec.reverse_complement(id='reverse',name='reverse',annotations=True)
        result=replace_grna_spacer(minus,spacer)
        expected=str(minus.seq[:600])+str(Seq(spacer).reverse_complement())+str(minus.seq[620:])
        self.assertEqual(str(result.only_product().seq),expected)
        # Independently change display origin inside old spacer, not Core rotation.
        rec=template();n=len(rec)
        wrapped=SeqRecord(Seq(str(rec.seq[240:])+str(rec.seq[:240])),id='wrapped',
            annotations={'molecule_type':'DNA','topology':'circular'})
        wrapped.features=[SeqFeature(FeatureLocation(n-90,n-10,strand=1),type='promoter')]
        result=replace_grna_spacer(wrapped,spacer)
        expected=spacer[10:]+str(wrapped.seq[10:n-10])+spacer[:10]
        self.assertEqual(str(result.only_product().seq),expected)
        self.assertEqual(result.analysis['preparation_route']['simulation_status'],'PASSED')
        self.assertTrue(any(w['code']=='GRNA_ORIGIN_CROSSING' for w in result.analysis['warnings']))

    def test_repeated_spacer_warns_but_repeated_binding_cores_block_route(self):
        spacer='GATACCTCGTACGATCGTCA'
        rec=template();text=str(rec.seq);rec.seq=Seq(text[:400]+spacer+text[420:])
        result=replace_grna_spacer(rec,spacer)
        self.assertTrue(any(w['code']=='GRNA_SPACER_REPEATED_IN_TEMPLATE' for w in result.analysis['warnings']))
        self.assertEqual(result.analysis['preparation_route']['simulation_status'],'PASSED')
        rec=template();text=str(rec.seq)
        # Entire admissible scaffold-side core repeated elsewhere.
        rec.seq=Seq(text[:400]+text[250:290]+text[440:])
        result=replace_grna_spacer(rec,spacer)
        self.assertEqual(result.analysis['preparation_route']['status'],'UNAVAILABLE')
        self.assertEqual(result.analysis.get('preparation',[]),[])
        self.assertFalse(any(c['scope']=='preparation_model' and c['status']=='PASSED' for c in result.checks))

    def test_poly_t_is_not_silently_changed_and_high_gc_can_fail(self):
        spacer='GATTTTTCGTACGATCGTCA'
        result=replace_grna_spacer(template(),spacer)
        self.assertEqual(str(result.only_product().seq[230:250]),spacer)
        self.assertTrue(any(w['code']=='GRNA_POL_III_POLY_T' for w in result.analysis['warnings']))
        rec=template();text=str(rec.seq);rec.seq=Seq(text[:180]+'G'*50+text[230:])
        result=replace_grna_spacer(rec,'GATACCTCGTACGATCGTCA')
        self.assertEqual(result.analysis['preparation_route']['status'],'UNAVAILABLE')
        self.assertIn('reason',result.analysis['preparation_route'])

    def test_sequence_only_opt_out_cannot_claim_preparation(self):
        result=replace_grna_spacer(template(),'GATACCTCGTACGATCGTCA',preparation_mode='sequence_only')
        self.assertEqual(result.analysis['preparation_route']['status'],'NOT_REQUESTED')
        self.assertFalse(any(c['scope']=='preparation_model' and c['status']=='PASSED' for c in result.checks))

    def test_public_step_trace_and_final_delivery_keep_scopes_and_primer_files(self):
        rec=template();spacer='GATACCTCGTACGATCGTCA'
        with tempfile.TemporaryDirectory(prefix='构建路线-') as temp:
            out=Path(temp);source=out/'模板.gb'
            with source.open('w',encoding='utf-8') as h:SeqIO.write(rec,h,'genbank')
            cfg=out/'step.json';cfg.write_text(json.dumps({'method':'replace_grna_spacer',
                'sources':{'v':str(source)},'params':{'vector_record_or_seq':'$v','spacer_seq':spacer},
                'requirements':{'expected_components':[{'sequence':spacer}]}},ensure_ascii=False),encoding='utf-8')
            env={**os.environ,'SNAPGENE_TRACE_CONFIG':str(out/'trace-settings.json')}
            (out/'trace-settings.json').write_text('{"trace_level":"full"}',encoding='utf-8')
            run=subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'scripts/run_step.py'),'--input',str(cfg),
                '--workspace',str(out/'work')],capture_output=True,text=True,encoding='utf-8',env=env)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            data=json.loads((out/'work/steps.json').read_text(encoding='utf-8'))
            operations=data['steps'][0]['operations']
            self.assertTrue(any(o['method']=='simulate_pcr' for o in operations))
            self.assertTrue(any(o['method']=='ligate_fragments' for o in operations))
            events=(out/'work/steps/001/evidence-trace/events.jsonl').read_text(encoding='utf-8')
            self.assertIn('PLANNED',events);self.assertIn('NOT_PERFORMED',events)
            run=subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'scripts/finalize_workflow.py'),
                '--workspace',str(out/'work'),'--candidate-ref','$step_001.products.0','--result-kind','construct',
                '--deliver','--confirmed','--out-dir',str(out/'final')],capture_output=True,text=True,encoding='utf-8',env=env)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            info=json.loads(run.stdout);self.assertEqual(info['status'],'delivered')
            final=Path(info['directory'])
            table=(final/'primer_order_table.tsv').read_text(encoding='utf-8')
            self.assertIn('tm_C',table);self.assertIn('binding_sequence_5to3',table)
            design=(final/'design.md').read_text(encoding='utf-8')
            self.assertIn('PLANNED',design);self.assertIn('DpnI',design);self.assertIn('KLD',design)
            with (final/'construct.gb').open(encoding='utf-8') as h:actual=SeqIO.read(h,'genbank')
            self.assertEqual(str(actual.seq),str(rec.seq[:230])+spacer+str(rec.seq[250:]))


if __name__=='__main__':unittest.main()
