"""Whole native restriction sources must use both declared enzymes."""
import tempfile
import unittest
from pathlib import Path

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import SeqFeature, FeatureLocation
from Bio.SeqRecord import SeqRecord

from planning.planner import plan_assembly
from scripts.operation_consent import ConsentBroker
from planning.executor import execute_assembly, ExecutionError
from planning.planner import _anchored_primer_fallback, PlannerError


class PlanningRestrictionAudit(unittest.TestCase):
    def test_anchored_fallback_keeps_specificity_and_explicit_backend_constraints(self):
        template=SeqRecord(Seq('A'*200),id='nonunique',annotations={'molecule_type':'DNA','topology':'linear'})
        fragment={'name':'nonunique','_source_record':template,'source_interval':[0,200],'sequence':str(template.seq)}
        with self.assertRaises(ValueError):
            _anchored_primer_fallback(fragment,'','',None)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(PlannerError,'ANCHORED_BACKEND_UNAVAILABLE'):
                _anchored_primer_fallback(fragment,'','',str(Path(temp)/'missing-primer3-core'))

    def test_missing_terminal_site_and_reversed_enzyme_order_are_rejected(self):
        vector='CCCCCGAATTCACATGGATCC'+'T'*25
        insert='GAATTCGTCAGTCAGGATCC'
        records=[SeqRecord(Seq(vector),id='v',annotations={'molecule_type':'DNA','topology':'circular'}),
                 SeqRecord(Seq(insert),id='i',annotations={'molecule_type':'DNA','topology':'linear'})]
        def fragments(end):
            return [{'name':r.id,'role':'backbone' if i==0 else 'insert','source_path':r.id+'.gb',
                'sequence':str(r.seq[:len(r) if i==0 else end]),'source_interval':[0,len(r) if i==0 else end],
                '_source_record':r,'_extraction_strand':1} for i,r in enumerate(records)]
        # Preserve the original scenario error: end excludes two bases of BamHI.
        with self.assertRaisesRegex(ExecutionError,'BamHI.*found 0'):
            execute_assembly(fragments(len(insert)-2),'digest-ligate','circular',['EcoRI','BamHI'])
        with self.assertRaisesRegex(ExecutionError,'ordered'):
            execute_assembly(fragments(len(insert)),'digest-ligate','circular',['BamHI','EcoRI'])

    def test_single_enzyme_requires_two_insert_sites_without_forcing_pcr(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);paths=[]
            vector='CCCCCGAATTC'+'T'*25
            insert='AAAGAATTCGTCAGTCAGAATTCCCC'
            for name,seq,topology in [('vector',vector,'circular'),('insert',insert,'linear')]:
                record=SeqRecord(Seq(seq),id=name,annotations={'molecule_type':'DNA','topology':topology})
                path=root/(name+'.gb')
                with path.open('w',encoding='utf-8') as f:SeqIO.write(record,f,'genbank')
                paths.append(str(path))
            result=plan_assembly(paths,{'method':'digest-ligate','enzymes':['EcoRI'],
                'backbone':{'source':0},'fragments':[{'source':1}]},consent_broker=ConsentBroker(policy='auto'))
            self.assertEqual(result['status'],'complete',result['execution'])
            self.assertFalse(any(p.get('pcr_required') for p in result['primers']))
            v=vector.index('GAATTC')+1
            i1=insert.index('GAATTC')+1;i2=insert.index('GAATTC',i1)+1
            self.assertEqual(result['final_construct']['sequence'],vector[:v]+insert[i1:i2]+vector[v:])

    def test_two_enzymes_native_inputs_and_cut_based_product(self):
        for enzymes,sites in ((['EcoRI','BamHI'],['GAATTC','GGATCC']),
                              (['HindIII','XbaI'],['AAGCTT','TCTAGA']),
                              (['BamHI','XhoI'],['GGATCC','CTCGAG'])):
            with self.subTest(enzymes=enzymes), tempfile.TemporaryDirectory() as temp:
                root=Path(temp)
                vector='CCCCC'+sites[0]+'ACAT'+sites[1]+'T'*25
                insert='AAA'+sites[0]+'GTCAGTCA'+sites[1]+'CCC'
                paths=[]
                for name,seq,topology,start,end in [('vector',vector,'circular',0,4),('insert',insert,'linear',10,14)]:
                    record=SeqRecord(Seq(seq),id=name,annotations={'molecule_type':'DNA','topology':topology})
                    record.features=[SeqFeature(FeatureLocation(start,end,strand=1),type='misc_feature',qualifiers={'label':[name+'-mark']})]
                    path=root/(name+'.gb')
                    with path.open('w',encoding='utf-8') as f:SeqIO.write(record,f,'genbank')
                    paths.append(str(path))
                result=plan_assembly(paths,{'method':'digest-ligate','enzymes':enzymes,
                    'backbone':{'source':0},'fragments':[{'source':1}]},consent_broker=ConsentBroker(policy='auto'))
                self.assertEqual(result['status'],'complete',result['execution'])
                self.assertEqual(result['assembly_strategy']['method'],'digest-ligate')
                self.assertFalse(any(p.get('pcr_required') for p in result['primers']))
                # These four enzymes cut the top strand after recognition base 1.
                v1,v2=(vector.index(site)+1 for site in sites)
                i1,i2=(insert.index(site)+1 for site in sites)
                self.assertEqual(result['final_construct']['sequence'],vector[:v1]+insert[i1:i2]+vector[v2:])
                labels=[f.get('label') or f.get('qualifiers',{}).get('label') for f in result['execution']['feature_specs']]
                self.assertIn('vector-mark',labels)
                self.assertIn('insert-mark',labels)


if __name__=='__main__':unittest.main()
