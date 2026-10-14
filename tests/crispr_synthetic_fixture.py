"""Fixed-seed synthetic inputs/oracles. No Core imports or private materials.

The random anchor is a sequence locator, not a functional sgRNA scaffold.
An AmpR label on a 20 nt CDS deliberately tests annotation interpretation;
it is not a claim that synthetic DNA confers resistance.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import random
import struct
import xml.etree.ElementTree as ET

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqFeature import FeatureLocation, SeqFeature
from Bio.SeqRecord import SeqRecord

SEEDS = (17011, 42043)


def reverse_complement(sequence):
    return sequence.translate(str.maketrans('ACGT', 'TGCA'))[::-1]


def occurrences(sequence, query):
    return [i for i in range(len(sequence)-len(query)+1) if sequence[i:i+len(query)] == query]


@dataclass
class SyntheticCase:
    name: str
    seed: int
    vector: SeqRecord
    target: SeqRecord
    scaffold: str
    intended_spacer: str
    expressed_spacer: str
    new_spacer: str
    spacer_start: int
    target_start: int
    expected_direction: str
    expected_pam: str
    construction: str


def build_cases(seed):
    rng = random.Random(seed)
    draw = lambda length: ''.join(rng.choice('ACGT') for _ in range(length))
    promoter, guide, anchor, backbone, new_guide = draw(60), draw(20), draw(60), draw(800), draw(20)
    left, right = draw(95)+'ATATAA', 'T'+draw(100)
    # An upstream CCN would accidentally permit the opposite guide orientation.
    # Fixed six-base context excludes it for original and one-base shifted sites.
    target = left + guide + 'CGG' + right
    assert occurrences(target, guide) == [len(left)]
    assert occurrences(target, reverse_complement(guide)) == []
    shifted = left[-1] + guide[:19]
    assert occurrences(target, shifted) == [len(left)-1]
    assert occurrences(target, reverse_complement(shifted)) == []
    source_sequence = promoter + guide + anchor + backbone
    # Independent string checks establish the intended binding-site counts.
    f_core, r_core = anchor[:40], reverse_complement(promoter[-40:])
    assert occurrences(source_sequence, f_core) == [80]
    assert occurrences(source_sequence, reverse_complement(r_core)) == [20]

    def record(spacer=guide, annotation_strand=1, annotation_type='misc_RNA', duplicate_cores=False):
        sequence = promoter + spacer + anchor + backbone
        if duplicate_cores:
            # Both outward-PCR cores are copied, including every possible
            # shorter 3-prime core, but no promoter annotation is duplicated.
            sequence += promoter[-40:] + guide + anchor[:40]
        rec = SeqRecord(Seq(sequence), id='synthetic_cassette', name='synthetic_cassette',
                        annotations={'molecule_type':'DNA','topology':'circular'})
        rec.features = [SeqFeature(FeatureLocation(0,60,strand=1), type='promoter',
                                   qualifiers={'label':['synthetic promoter locator']}),
                        SeqFeature(FeatureLocation(60,80,strand=annotation_strand),type=annotation_type,
                                   qualifiers={'label':['AmpR' if annotation_type=='CDS' else 'synthetic guide']})]
        return rec

    def case(name, expressed=guide, direction='CORRECT', pam='CGG', target_sequence=target,
             construction='', **kwargs):
        return SyntheticCase(name, seed, record(expressed,**kwargs),
            SeqRecord(Seq(target_sequence),id='synthetic_target',annotations={'molecule_type':'DNA','topology':'linear'}),
            anchor, guide, expressed, new_guide, 60, len(left), direction, pam, construction)

    repeated_target = target + draw(87) + guide + 'CGG' + draw(90)
    assert len(occurrences(repeated_target, guide)) == 2
    return {
        'control': case('control', construction='Forward guide, explicit CGG PAM, one target and one pair of binding cores.'),
        'reversed': case('reversed', reverse_complement(guide), 'REVERSED',
                         construction='Reverse complement of intended guide inserted after forward promoter.'),
        'shifted': case('shifted', shifted, 'INVALID_PAM', guide[-1]+'CG',
                        construction='Guide copied from one base before intended target; its adjacent PAM ends CG, not GG.'),
        'annotation_conflict': case('annotation_conflict',annotation_strand=-1,
                        construction='DNA unchanged; only guide annotation strand changed to minus.'),
        'spacer_cds': case('spacer_cds',annotation_type='CDS',
                        construction='DNA unchanged; 20 nt spacer labelled AmpR CDS; 20 modulo 3 is nonzero.'),
        'repeated_target': case('repeated_target',target_sequence=repeated_target,
                        construction='A second full guide+CGG site appended at a separately known position.'),
        'repeated_binding': case('repeated_binding',duplicate_cores=True,
                        construction='Both 40 nt outward-PCR binding cores duplicated elsewhere in template.'),
    }


def write_native(record, path, *, double_stranded=False):
    """Independent SnapGene packet construction, no runtime native writer."""
    packet = lambda kind,payload: struct.pack('>BI',kind,len(payload))+payload
    features = ET.Element('Features')
    for feature in record.features:
        node = ET.SubElement(features,'Feature',{'type':feature.type,
            'name':feature.qualifiers['label'][0],'directionality':'1' if feature.location.strand==1 else '2'})
        ET.SubElement(node,'Segment',{'range':f'{int(feature.location.start)+1}-{int(feature.location.end)}','type':'standard'})
    # SnapGeneReader's independent format implementation: bit 0x01 circular,
    # bit 0x02 double-stranded. Preserve original circular-single test packets
    # by default; physical preparation inputs must explicitly request duplex.
    # https://github.com/Edinburgh-Genome-Foundry/SnapGeneReader/blob/master/snapgene_reader/snapgene_reader.py
    flags = 0x01 | (0x02 if double_stranded else 0)
    Path(path).write_bytes(packet(9,b'SnapGene'+struct.pack('>HHH',1,1,1))+
        packet(0,bytes([flags])+str(record.seq).encode('ascii'))+packet(10,ET.tostring(features,encoding='utf-8')))


def materialize(directory, seed):
    """Files and construction metadata only; expected values never call Core."""
    root = Path(directory)
    root.mkdir(parents=True,exist_ok=True)
    result = {}
    for name, case in build_cases(seed).items():
        vector, target = root/(name+'.dna'), root/(name+'-target.gb')
        write_native(case.vector, vector)
        with target.open('w',encoding='utf-8') as handle:
            SeqIO.write(case.target,handle,'genbank')
        result[name] = {'vector':str(vector), 'target':str(target), 'case':case}
    (root/'construction.json').write_text(json.dumps({name:{'seed':seed,
        'construction':row['case'].construction,'expected_direction':row['case'].expected_direction,
        'expected_pam':row['case'].expected_pam,'spacer_start_0based':60,
        'target_start_0based':row['case'].target_start} for name,row in result.items()},indent=2),encoding='utf-8')
    return result
