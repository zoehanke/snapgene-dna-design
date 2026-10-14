"""Construction-defined source records; no Core or Toolkit calculation imports."""
import argparse
import json
from pathlib import Path
import random
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord


def generate(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    rng=random.Random(681120)
    target=''.join(rng.choices('ACGT',k=2000));cargo=''.join(rng.choices('ACGT',k=900))
    expected=target[600:800]+cargo[200:440]+target[810:1010]
    references={}
    for name,sequence in [('target',target),('cargo',cargo),('donor',expected)]:
        features=[] if name=='target' else [SeqFeature(FeatureLocation(200,440,strand=1),type='misc_feature',qualifiers={'label':['independent_cargo']})]
        record=SeqRecord(Seq(sequence),id=name,features=features,annotations={'molecule_type':'DNA','topology':'linear','date':'01-JAN-2000'})
        with (out/(name+'.gb')).open('w',encoding='utf-8') as handle:SeqIO.write(record,handle,'genbank')
        references[name]={'path':name+'.gb','source':'Fixed-seed software vector; no experimental claim.'}
    request={'original_request':'Prepare the explicit 200+240+200 bp donor from the actual supplied complete donor template.',
      'method':'integration_donor','target_reference':'target','cargo_reference':'cargo','target_interval':{'start0':800,'end0':810},
      'cargo_interval':{'start0':200,'end0':440},'arm_length':200,'preparation_method':'pcr',
      'donor_template_reference':'donor','donor_interval':{'start0':0,'end0':640}}
    values={'context.json':{'references':references},'request.json':request,
      'inputs.json':{'request_file':str((out/'request.json').resolve()),'context_file':str((out/'context.json').resolve()),'language':'en'},
      'EXPECTED.json':{'sequence':expected,'length':640,'source':'Independent input slicing before any runtime call.'}}
    for name,value in values.items():(out/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    return expected


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out-dir',required=True);generate(parser.parse_args().out_dir)
