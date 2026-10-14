"""Literal arithmetic vectors, not experiment observations or runtime answers."""
import argparse
import json
from pathlib import Path


def generate(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    request={'original_request':'Compare these synthetic software count vectors and keep experimental authenticity unverified.',
      'observations':[{'id':'e1','group':'experiment','colonies':30,'plated_cells':50},
                      {'id':'c1','group':'control','colonies':5,'plated_cells':50}],
      'comparisons':[{'experiment_group':'experiment','control_group':'control'}]}
    values={'context.json':{'references':{}},'request.json':request,
      'inputs.json':{'request_file':str((out/'request.json').resolve()),'context_file':str((out/'context.json').resolve()),'language':'en'},
      'EXPECTED.json':{'normalised_difference':0.5,'source':'Literal 30/50 minus 5/50, before any runtime call.'}}
    for name,value in values.items():(out/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out-dir',required=True);generate(parser.parse_args().out_dir)
