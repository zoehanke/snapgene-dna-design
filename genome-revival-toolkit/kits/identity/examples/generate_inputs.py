"""Generate nonfunctional software vectors; expected PCR lengths are literal construction."""
import argparse
import json
from pathlib import Path
import random
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord


def generate(out):
    out.mkdir(parents=True,exist_ok=False)
    forward='AGAGGAGAAAGAGGGAAGAGGA';reverse='AAGGAAGAGAGGAGAGGAGAAG'
    rng=random.Random(87569);middle=''.join(rng.choices('ACGT',k=120))
    first='TCGTACCGTATCGACTACGT'+forward+middle+str(Seq(reverse).reverse_complement())+'GCATCGTAGCATACGTCGAT'
    second=first[:20+len(forward)+45]+first[20+len(forward)+68:]
    negative=first[:20+len(forward)-1]+'C'+first[20+len(forward):]
    refs={}
    for name,sequence in {'a':first,'b':second,'negative':negative}.items():
        path=out/(name+'.gb')
        record=SeqRecord(Seq(sequence),id=name,annotations={'molecule_type':'DNA','topology':'linear'})
        with path.open('w',encoding='utf-8') as handle:SeqIO.write(record,handle,'genbank')
        refs[name]={'path':str(path.resolve()),'source':'Fixed-seed generated software test vector, not functional laboratory material.'}
    request={'original_request':'Assess the supplied regions and full PCR primers without whole-genome claims.',
             'references':list(refs),'compare_regions':False,
             'assays':[{'id':'regional_pair','forward':forward,'reverse':reverse,'size_resolution_bp':20}]}
    values={'context.json':{'references':refs},'request.json':request,
            'inputs.json':{'request_file':str((out/'request.json').resolve()),'context_file':str((out/'context.json').resolve()),'language':'en'},
            'construction-expected.json':{'a':len(forward)+120+len(reverse),'b':len(forward)+97+len(reverse),'negative':None}}
    for name,value in values.items():(out/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out-dir',type=Path,required=True)
    generate(parser.parse_args().out_dir)
