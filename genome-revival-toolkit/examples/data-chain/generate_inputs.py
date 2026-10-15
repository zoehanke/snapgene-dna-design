"""Construct fixed synthetic references before any Kit is called."""
import argparse
import importlib.util
import json
from pathlib import Path
import random
import sys
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord


def save(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def generate(root):
    root=Path(root); root.mkdir(parents=True,exist_ok=False)
    rng=random.Random(681120)
    wild=''.join(rng.choices('ACGT',k=2000));cargo=''.join(rng.choices('ACGT',k=900))
    insert=cargo[200:440]
    donor=wild[600:800]+insert+wild[810:1010]
    edited=wild[:800]+insert+wild[810:]
    references={}
    for name,sequence in (('wild_type',wild),('cargo',cargo),('donor_template',donor),('edited_model',edited)):
        path=root/(name+'.gb')
        record=SeqRecord(Seq(sequence),id=name,annotations={'molecule_type':'DNA','topology':'linear','date':'01-JAN-2000'})
        with path.open('w',encoding='utf-8') as handle:SeqIO.write(record,handle,'genbank')
        references[name]={'path':str(path.resolve()),'source':'Fixed-seed prospective software model; not a measured strain or functional material.'}
    save(root/'context.json',{'references':references})
    save(root/'construct-request.json',{'original_request':'Prepare the specified synthetic donor from its supplied complete template, check both donor boundaries and hand off those actual QC candidates for local-reference comparison.',
        'title':'Synthetic donor to regional PCR to reported observations',
        'method':'integration_donor','target_reference':'wild_type','cargo_reference':'cargo',
        'target_interval':{'start0':800,'end0':810},'cargo_interval':{'start0':200,'end0':440},'arm_length':200,
        'preparation_method':'pcr','donor_template_reference':'donor_template','donor_interval':{'start0':0,'end0':640},
        'identity_handoff':{'references':['edited_model','wild_type'],'size_resolution_bp':20}})
    save(root/'CONSTRUCTION.json',{'seed':681120,'wild_type_bp':2000,'donor_bp':640,'edited_model_bp':2230,
        'replacement_interval':[800,810],'insert_bp':240,'model_status':'PROSPECTIVE_SYNTHETIC_REFERENCE',
        'laboratory_status':'PLANNED','wet_lab':'NOT_PERFORMED'})
    # Reuse an independent input constructor, never a Core/Kit computation.
    toolkit=Path(__file__).resolve().parents[2]
    path=toolkit/'kits/crispr/examples/generate_inputs.py'
    spec=importlib.util.spec_from_file_location('synthetic_crispr_input_constructor',path)
    module=importlib.util.module_from_spec(spec)
    sys.path.insert(0,str(path.parent))
    try:spec.loader.exec_module(module)
    finally:sys.path.remove(str(path.parent))
    crispr=root/'crispr';crispr.mkdir()
    request,_=module.fixture(crispr,17011,replace=True,genotype=False)
    case=module.build_cases(17011)['control']
    with (crispr/'target.gb').open(encoding='utf-8') as handle:target=SeqIO.read(handle,'genbank')
    with (crispr/'vector.dna').open('rb') as handle:vector=SeqIO.read(handle,'snapgene')
    correct=case.new_spacer
    shifted=str(target.seq[case.target_start-1:case.target_start+19])
    vector.seq=Seq(str(vector.seq[:60])+shifted+str(vector.seq[80:]))
    module.write_native(vector,crispr/'vector.dna',double_stranded=True)
    check={key:value for key,value in request.items() if key!='spacer_seq'};check['operation']='check'
    check['title']='Synthetic one-base guide correction; selection remains unknown'
    save(crispr/'check-request.json',check)
    request['title']=check['title'];save(crispr/'replace-request.json',request)
    save(crispr/'CONSTRUCTION.json',{'seed':17011,'spacer_interval':[60,80],'target_start0':case.target_start,
        'correct_spacer':correct,'shifted_spacer':shifted,'invalid_pam':str(target.seq[case.target_start+19:case.target_start+22]),
        'expected_direction_before':'INVALID_PAM','expected_direction_after':'CORRECT','expected_selection':'UNKNOWN',
        'laboratory_status':'PLANNED','wet_lab':'NOT_PERFORMED'})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out-dir',type=Path,required=True)
    generate(parser.parse_args().out_dir)
