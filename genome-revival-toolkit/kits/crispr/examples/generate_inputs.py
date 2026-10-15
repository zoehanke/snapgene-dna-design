"""Independent fixed-seed synthetic input construction, not a runtime oracle."""
import argparse
import json
from pathlib import Path
import random
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from synthetic_fixture import build_cases, write_native


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


def generate(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    request,expected=fixture(out,17011,replace=True)
    (out/'inputs.json').write_text(json.dumps({'request_file':str((out/'request.json').resolve()),'context_file':str((out/'context.json').resolve()),'language':'en'}),encoding='utf-8')
    (out/'EXPECTED.json').write_text(json.dumps({'sequence':expected,'length':len(expected),'source':'Constructed replacement at input positions 60:80 before any Core calculation.'}),encoding='utf-8')
    return expected

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out-dir',required=True);generate(parser.parse_args().out_dir)
