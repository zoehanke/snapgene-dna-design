"""Generate source-only synthetic correction examples, never user DNA.

Construction determines expected bases, positions and rejected boundaries.
Run outputs and reader questions are generated outside the repository.
"""
import argparse
import json
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from crispr_synthetic_fixture import build_cases, write_native
from test_crispr_kit import fixture
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord


def write_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def generate(directory):
    out=Path(directory).resolve()
    if out.exists():raise FileExistsError('Preserve previous examples; choose a new directory')
    out.mkdir(parents=True)
    manifest={}
    for name,seed in (('core-guide',17011),('kit-guide',42043)):
        case_dir=out/name;case_dir.mkdir()
        request,original=fixture(case_dir,seed,'shifted')
        case=build_cases(seed)['shifted']
        intended=case.intended_spacer
        if name=='kit-guide':
            # Retain the original GC-rich guide as a rejected prior example.
            # This constructor uses its independent alternate guide to make a
            # different one-base-displacement input, not to relax primer QC.
            intended=case.new_spacer
            with (case_dir/'target.gb').open(encoding='utf-8') as handle:target=SeqIO.read(handle,'genbank')
            raw=str(target.seq);target.seq=Seq(raw[:case.target_start]+intended+raw[case.target_start+20:])
            with (case_dir/'vector.dna').open('rb') as handle:vector=SeqIO.read(handle,'snapgene')
            displaced=str(target.seq[case.target_start-1])+intended[:19]
            original=original[:60]+displaced+original[80:];vector.seq=Seq(original)
            write_native(vector,case_dir/'vector.dna',double_stranded=True)
            with (case_dir/'target.gb').open('w',encoding='utf-8') as handle:SeqIO.write(target,handle,'genbank')
        request['original_request']='Inspect the displaced guide; intended replacement spacer is '+intended+'. Preserve outside DNA and check the supplied target only.'
        write_json(case_dir/'request.json',request)
        request.update(title='Correct a one-base spacer displacement',
            operation='replace',spacer_seq=intended)
        request['decisions']=[{'text':'Use the specified spacer and the Core inverse-PCR route',
            'rationale':'Scripted example choice: the constructed target has an explicit CGG PAM. Direction, full-primer quality and simulation must still pass; this rationale does not prove them.',
            'actor':'ai','origin':'ai_concurrent','kind':'other','basis_references':['vector','target']}]
        write_json(case_dir/'corrected-request.json',request)
        write_json(case_dir/'trace-settings.json',{'trace_level':'full'})
        expected=original[:60]+intended+original[80:]
        with (case_dir/'expected.fasta').open('w',encoding='utf-8') as handle:
            SeqIO.write(SeqRecord(Seq(expected),id='constructed_expected'),handle,'fasta')
        manifest[name]={'seed':seed,'expected_spacer':intended,
            'vector_interval_0based':[60,80],'expected_target_interval_0based':[case.target_start,case.target_start+20],
            'original_pam':intended[-1]+'CG','corrected_pam':'CGG','identical_target_strand':1,'rna_binding_strand':-1,
            'construction':'One-base-upstream target sequence inserted after forward promoter; intended guide restores its explicit CGG PAM.',
            'scope':'Synthetic random locators and ORFs; scaffold, marker function and replication NOT_TESTED.'}
    case_dir=out/'kit-construct';case_dir.mkdir()
    rng=random.Random(681120)
    target=''.join(rng.choices('ACGT',k=2000));cargo=''.join(rng.choices('ACGT',k=900))
    expected=target[600:800]+cargo[200:440]+target[810:1010]
    references={}
    for name,sequence in (('target',target),('cargo',cargo),('donor',expected)):
        with (case_dir/(name+'.gb')).open('w',encoding='utf-8') as handle:
            SeqIO.write(SeqRecord(Seq(sequence),id=name,
                annotations={'molecule_type':'DNA','topology':'linear'}),handle,'genbank')
        references[name]={'path':name+'.gb','source':'Independently constructed synthetic input; physical stock NOT_VERIFIED'}
    write_json(case_dir/'context.json',{'references':references})
    request={'title':'Recover a truncated donor preparation request',
        'original_request':'Prepare the explicit donor from the supplied full template and verify both junctions; preserve the rejected attempt.',
        'method':'integration_donor','target_reference':'target','cargo_reference':'cargo',
        'target_interval':{'start0':800,'end0':810},'cargo_interval':{'start0':200,'end0':440},'arm_length':200,
        'preparation_method':'pcr','donor_template_reference':'donor','donor_interval':{'start0':0,'end0':637}}
    write_json(case_dir/'request.json',request)
    request['donor_interval']['end0']=640
    request['original_request']+=' Correction: donor_interval changes from [0,637) to [0,640); the expected donor remains 640 bp.'
    request['decisions']=[{'text':'Use the supplied complete donor as PCR template',
        'rationale':'Scripted choice: the complete 640 bp template is supplied. The requested interval must cover it; PCR and both junction designs need actual checks.',
        'actor':'ai','origin':'ai_concurrent','kind':'other','basis_references':['donor','target','cargo']}]
    write_json(case_dir/'corrected-request.json',request)
    write_json(case_dir/'trace-settings.json',{'trace_level':'full'})
    with (case_dir/'expected.fasta').open('w',encoding='utf-8') as handle:
        SeqIO.write(SeqRecord(Seq(expected),id='constructed_expected'),handle,'fasta')
    manifest['kit-construct']={'seed':681120,'expected_length_bp':640,
        'left_arm_0based':[600,800],'cargo_0based':[200,440],'right_arm_0based':[810,1010],
        'original_donor_interval_0based':[0,637],'corrected_donor_interval_0based':[0,640],
        'construction':'Expected donor is explicit target slice + cargo slice + target slice; original request omits final three bases.',
        'scope':'Synthetic sequence/PCR/assembly engineering, not a measured integration experiment.'}
    write_json(out/'construction.json',manifest)
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir',required=True)
    args=parser.parse_args()
    print(json.dumps(generate(args.out_dir),ensure_ascii=False,indent=2))
