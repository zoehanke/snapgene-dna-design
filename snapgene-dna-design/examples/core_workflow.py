"""Executable Core API walkthrough using the public synthetic fixture.

This is a sequence-file edit, not a PCR/preparation protocol. For actual
preparation use scripts/demo_engineering_cycle.py or a supported Recipe.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from Bio import SeqIO
from core import plan,execute,validate,finalize


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir',required=True,type=Path)
    args=parser.parse_args()
    out=args.out_dir.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error('Use a new or empty output directory')
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'fixtures/synthetic/pSynthetic-GFP.gb'
    original=SeqIO.read(source,'genbank')
    position=100  # Explicit 1-based coordinate for the mutation interface.
    reference=str(original.seq[position-1])
    alternate='C' if reference!='C' else 'A'
    task={
        'task_id':'api-walkthrough','mode':'formal','task_kind':'point_mutation',
        'sources':[{'source_id':'template','role':'template','path':str(source),
                    'evidence':{'source_evidence_class':'user-provided'}}],
        'target':{'source_id':'template'},
        'operation':{'mutations':[{'position_1based':position,'ref':reference,'alt':alternate}]},
        'product':{'topology':'circular','formats':['gb','fasta','dna']},
        'approvals':{'user_confirmed_task':{'value':True}},
    }
    task,planned=plan(task)
    execution=execute(task,planned,out/'work')
    validation=validate(task,planned,execution)
    for name,data in (('task',task),('plan',planned),('execution',execution),('validation',validation)):
        (out/f'{name}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    delivery=finalize(task,planned,execution,validation,out/'delivery')
    product=SeqIO.read(Path(delivery['directory'])/'construct.gb','genbank')
    expected=str(original.seq[:position-1])+alternate+str(original.seq[position:])
    def annotation_identity(record):
        return sorted((f.type,str(f.location),tuple(f.qualifiers.get('label',[])),
                       tuple(f.qualifiers.get('gene',[]))) for f in record.features)
    if str(product.seq)!=expected or annotation_identity(product)!=annotation_identity(original):
        raise RuntimeError('Independent source/product check failed')
    (out/'delivery.json').write_text(json.dumps(delivery,indent=2),encoding='utf-8')
    print(json.dumps({'status':delivery['status'],'directory':delivery['directory'],
                      'source_length':len(original),'product_length':len(product),
                      'source_features':len(original.features),'product_features':len(product.features),
                      'exact_requested_edit':True,'scope':planned['scope_note']},ensure_ascii=False))
    return 0


if __name__=='__main__':sys.exit(main())
