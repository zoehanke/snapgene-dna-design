"""Actual source -> PCR -> digest -> ligation -> shared verified bundle.

Generated inputs are an engineering example, not host benchmarking or wet lab.
CLI step input: {method, params, step_id, sources, history_file?}.
CLI closure input: {record_file, requirements, candidate, primers?, result_kind?,
                   output_step?, product_index?, required_scopes?}.
"""
import argparse
from pathlib import Path
import random
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import FeatureLocation,SeqFeature
from core.workflow import run_step
from core.workflow_delivery import deliver_result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir',required=True)
    args=parser.parse_args()
    rng=random.Random(850134)
    sequence=''.join(rng.choices('ACGT',k=150))+'GAATTC'+''.join(rng.choices('ACGT',k=294))
    assert sequence.count('GAATTC')==1
    source=SeqRecord(Seq(sequence),id='source',annotations={'molecule_type':'DNA','topology':'linear'})
    source.features=[SeqFeature(FeatureLocation(60,80,strand=-1),type='misc_feature',qualifiers={'label':['retained-domain']})]
    source.letter_annotations['source_position']=list(range(450))
    sources={'source':source}
    steps=[]
    for name,method,params in [
        ('pcr','simulate_pcr',{'template':'$source','f_primer':sequence[30:50],
                               'r_primer':str(Seq(sequence[380:400]).reverse_complement())}),
        ('cut','digest_sequence',{'seq':'$pcr','enzyme':'EcoRI'}),
        ('joined','ligate_fragments',{'fragments':['$cut.products.0','$cut.products.1']})]:
        step=run_step(method,params,step_id=name,sources=sources,previous=steps)
        if step.error:raise RuntimeError(step.error)
        steps.append(step)
    candidate=steps[-1].result.only_product()
    assert str(candidate.seq)==sequence[30:400]
    result=deliver_result({'description':'Prepare a fragment from the supplied template',
                          'topology':'linear','expected_sequence':sequence[30:400]},
                         sources,steps,candidate,args.out_dir)
    print(result['directory'])

if __name__=='__main__':main()
