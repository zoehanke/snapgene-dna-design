"""Independent string/size oracles. Imports no Core, Toolkit or PCR implementation."""
import argparse
import json
from pathlib import Path
from Bio import SeqIO


def read(path,format='genbank'):
    with Path(path).open('rb' if format=='snapgene' else 'r',**({} if format=='snapgene' else {'encoding':'utf-8'})) as handle:
        return str(SeqIO.read(handle,format).seq)


def rc(sequence):return sequence.translate(str.maketrans('ACGT','TGCA'))[::-1]


def positions(text,query):return [i for i in range(len(text)-len(query)+1) if text[i:i+len(query)]==query]


def pcr_length(sequence,forward,reverse):
    f=positions(sequence,forward);r=positions(sequence,rc(reverse))
    if not f or not r:return None
    if len(f)!=1 or len(r)!=1:raise AssertionError('Oracle input has ambiguous complete-primer binding')
    return r[0]+len(reverse)-f[0] if f[0]+len(forward)<=r[0] else None


def expected_bands(inputs,handoff):
    inputs=Path(inputs);packet=json.loads(Path(handoff).read_text(encoding='utf-8'))
    return {assay['id']:{ref:pcr_length(read(inputs/(ref+'.gb')),assay['forward'],assay['reverse'])
            for ref in ('edited_model','wild_type')} for assay in packet['assays']}


def prepare_observations(inputs,handoff,expected_file,out):
    """Generate simulated observations from constructed DNA, not Identity answers."""
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    bands=expected_bands(inputs,handoff)
    assert len(bands)==2 and all(row['edited_model'] is not None and row['wild_type'] is None for row in bands.values())
    counts=out/'synthetic-counts.csv'
    counts.write_text('id,group,colonies\nfusion-simulation,fusion,12\ncontrol-simulation,control,40\n',encoding='utf-8')
    base={'original_request':'Compare explicitly synthetic reported bands with the local PCR model; not an experiment or revival claim.',
          'expected_results_file':str(Path(expected_file).resolve()),'observations_file':str(counts.resolve())}
    good=[{'sample_id':'synthetic-sample','reference_id':'edited_model','assay_id':assay,'result':'positive',
           'control_status':'passed','observed_band_bp':values['edited_model']} for assay,values in bands.items()]
    bad=json.loads(json.dumps(good));bad[0]['observed_band_bp']+=17
    requests={}
    for name,rows in (('matching',good),('contradicted',bad),('counts-only',[])):
        value=dict(base,genotype_results=rows,title='Synthetic local evidence: '+name)
        path=out/(name+'.json');path.write_text(json.dumps(value,indent=2),encoding='utf-8');requests[name]=path
    (out/'independent-band-expectations.json').write_text(json.dumps({'bands':bands,'method':'Independent full-string primer search on construction-defined linear references; no Kit import.'},indent=2),encoding='utf-8')
    return requests


def check(root):
    root=Path(root);inputs=root/'inputs'; errors=[]
    construction=json.loads((inputs/'CONSTRUCTION.json').read_text(encoding='utf-8'))
    wild=read(inputs/'wild_type.gb');cargo=read(inputs/'cargo.gb')
    donor=wild[600:800]+cargo[200:440]+wild[810:1010]
    assert len(donor)==construction['donor_bp']==640
    assert read(inputs/'edited_model.gb')==wild[:800]+cargo[200:440]+wild[810:]
    result=json.loads((root/'construct/result.json').read_text(encoding='utf-8'))
    assert read(Path(result['delivery']['directory'])/'construct.gb')==donor
    bands=expected_bands(inputs,root/'construct/identity-handoff.json')
    table=json.loads((root/'identity/identity-expected-results.json').read_text(encoding='utf-8'))
    for row in table['rows']:
        size=bands[row['assay_id']][row['reference_id']]
        assert row['size_bp']==size
        assert row['expected']==('AMPLICON' if size is not None else 'NO_EXACT_PRODUCT')
    recalculated={}
    for case in ('matching','contradicted','counts-only'):
        observations=json.loads((root/'observations'/(case+'.json')).read_text(encoding='utf-8'))['genotype_results']
        if not observations:status='INSUFFICIENT'
        else:
            # These construction-defined examples declare passing controls and
            # zero tolerance; determine consistency from the independent bands.
            assert all(row['control_status']=='passed' for row in observations)
            agrees=[]
            for row in observations:
                expected_size=bands[row['assay_id']][row['reference_id']]
                agrees.append(row['result']==('negative' if expected_size is None else 'positive') and
                              row.get('observed_band_bp')==expected_size)
            status='SUPPORTED' if all(agrees) else 'CONTRADICTED'
        recalculated[case]=status
        value=json.loads((root/('evidence-'+case)/'result.json').read_text(encoding='utf-8'))
        assert value['expected_result_comparison']['status']==status
        assert all(row['status']!='SUPPORTED' for row in value['conclusions'])
    original=read(inputs/'crispr/vector.dna','snapgene')
    guide=json.loads((inputs/'crispr/CONSTRUCTION.json').read_text(encoding='utf-8'))
    target=read(inputs/'crispr/target.gb'); start=guide['target_start0']
    assert target[start:start+20]==guide['correct_spacer'] and target[start+20:start+23]=='CGG'
    assert original[60:80]==target[start-1:start+19]
    assert target[start+19:start+22]==guide['invalid_pam'] and guide['invalid_pam'][-2:]!='GG'
    before=json.loads((root/'crispr-before/result.json').read_text(encoding='utf-8'))
    after=json.loads((root/'crispr-after/result.json').read_text(encoding='utf-8'))
    assert before['grna']['direction_status']=='INVALID_PAM'
    assert after['grna']['direction_status']=='CORRECT' and after['selection']['status']=='UNKNOWN'
    assert after['laboratory_status']=='PLANNED' and after['wet_lab']=='NOT_PERFORMED'
    candidate=next(Path(row['path']) for row in after['auxiliary_files'] if row['path'].endswith('.gb'))
    sequence=read(candidate)
    assert sequence==original[:60]+guide['correct_spacer']+original[80:]
    primers=after['preparation']['primers']
    forward=next(row for row in primers if row['strand']==1)
    reverse=next(row for row in primers if row['strand']==-1)
    for primer in (forward,reverse):assert primer['sequence']==primer['five_prime_tail']+primer['binding_sequence']
    extended_template=original+original[:max(len(forward['binding_sequence']),len(reverse['binding_sequence']))-1]
    f=[pos for pos in positions(extended_template,forward['binding_sequence']) if pos<len(original)]
    r=[pos for pos in positions(extended_template,rc(reverse['binding_sequence'])) if pos<len(original)]
    assert len(f)==len(r)==1
    end=(r[0]+len(reverse['binding_sequence']))%len(original)
    body=original[f[0]:end] if end>=f[0] else original[f[0]:]+original[:end]
    amplicon=forward['five_prime_tail']+body+rc(reverse['five_prime_tail'])
    assert len(amplicon)==len(sequence) and sequence in amplicon+amplicon
    # Independent circular, both-strand NGG scan with the same stated mismatch limit.
    hits=[]; extended=sequence+sequence[:22]
    for index in range(len(sequence)):
        region=extended[index:index+23]
        for strand,oriented in ((1,region),(-1,rc(region))):
            if oriented[-2:]=='GG' and sum(a!=b for a,b in zip(guide['correct_spacer'],oriented[:20]))<=3:
                hits.append((index,strand))
    assert hits==[],hits
    assert after['self_target']['self_target_status']=='NO_MATCH_IN_SEARCH_SCOPE'
    report={'status':'PASSED','donor_bp':len(donor),'edited_reference_bp':len(read(inputs/'edited_model.gb')),
            'bands':bands,'evidence':recalculated,
            'crispr':'INVALID_PAM -> CORRECT; no <=3-mismatch NGG vector site; selection UNKNOWN',
            'independent_inverse_pcr_circle_matches':True,
            'laboratory_status':'PLANNED','wet_lab':'NOT_PERFORMED','official_ci':'官方 GitLab CI 未执行'}
    (root/'INDEPENDENT-CHECK.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,required=True)
    print(json.dumps(check(parser.parse_args().directory),ensure_ascii=False,indent=2))
