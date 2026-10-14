"""Run one generated correction example through public Core/Toolkit entries.

The planned route is scripted, not an autonomous host evaluation. Construction
data and expected FASTA are independent inputs from generate_evidence_inputs.py.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'snapgene-dna-design'),str(ROOT/'genome-revival-toolkit')]
from Bio import SeqIO
from core.tools.grna import check_grna
from core.workflow import run_step
from core.workflow_delivery import deliver_result
from core.tools.result import to_wire
from evidence_trace.recorder import Recorder, load_events
from evidence_trace.process import assemble, organize
from evidence_trace.runtime import observe, observe_files, traced_run
from evidence_trace.localization import language_scope
from revival.reporting import _workflow_packet


def read_json(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write_json(path,value):Path(path).write_text(json.dumps(to_wire(value),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def check_file_relationships(graph):
    """Independently read bytes; a nonempty fact ID alone is not evidence."""
    def files(value):
        if isinstance(value,dict):
            if isinstance(value.get('path'),str) and isinstance(value.get('sha256'),str):
                yield value['path'],value['sha256'].lower()
            if isinstance(value.get('source_path'),str) and isinstance(value.get('source_sha256'),str):
                yield value['source_path'],value['source_sha256'].lower()
            for child in value.values():yield from files(child)
        elif isinstance(value,list):
            for child in value:yield from files(child)
    records=graph['source_records'];checked=[];supported=set()
    for fact in graph['fact_relations']:
        if (fact.get('kind'),fact.get('origin'),fact.get('scope'),fact.get('verification_method')) != (
                'input_reference','program_derived','same_file_content','sha256_equality'):
            continue
        output=records[fact['from']];consumer=records[fact['to']]
        producer=records[output['result_event_ref']]
        digest=fact['sha256'].lower()
        assert output['sha256'].lower()==digest
        assert producer['sequence']<consumer['sequence']
        assert hashlib.sha256(Path(output['path']).read_bytes()).hexdigest()==digest
        inputs=list(files(consumer['payload']))
        matches=[path for path,value in inputs if value==digest]
        assert matches,'Relationship has no declared input with matching digest'
        assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path in matches)
        supported.add(fact['id']);checked.append({'fact_relation_id':fact['id'],'sha256':digest,
            'output_matches_declared_input':True,'current_file_bytes_match':True})
    links=graph['design_process']['relations']
    program=[link for link in links if link.get('fact_relation_ids') and
        all(key in supported for key in link['fact_relation_ids'])]
    assert all(not link.get('fact_relation_ids') or link in program for link in links)
    return {'program_supported_step_relationships':len(program),
        'declared_step_relationships':len(links)-len(program),
        'declared_fact_relationships':sum(fact.get('origin')=='declared' for fact in graph['fact_relations']),
        'independent_file_hash_checks':checked}


def independent_readback(actual_path,expected_path,receipt_path):
    with Path(actual_path).open(encoding='utf-8') as handle:actual=SeqIO.read(handle,'genbank')
    with Path(expected_path).open(encoding='utf-8') as handle:expected=SeqIO.read(handle,'fasta')
    equal=str(actual.seq)==str(expected.seq)
    result={'sequence_equality':equal,'scope':'Actual exported bases versus independently constructed FASTA; not wet experiments.'}
    write_json(receipt_path,result)
    if not equal:raise RuntimeError('Actual export differs from independent construction')
    return {'paths':[str(receipt_path)],'analysis':result}


@traced_run('core-guide-example')
def core_example(case_dir,out_dir):
    request=read_json(case_dir/'corrected-request.json')
    sources={'vector':str(case_dir/'vector.dna'),'target':str(case_dir/'target.gb')}
    options={'scaffold_seq':request['scaffold_seq']}
    initial=observe('crispr.initial_check',check_grna,sources['vector'],sources['target'],**options)
    step=observe('crispr.replace',run_step,'replace_grna_spacer',
        {'vector_record_or_seq':'$vector','spacer_seq':request['spacer_seq'],**options},
        sources=sources,requirements={'expected_components':[{'sequence':request['spacer_seq']}]})
    if step.status!='completed':raise RuntimeError('Actual Core replacement failed; retain this attempt')
    candidate=step.result.only_product()
    final=observe('crispr.final_check',check_grna,candidate,sources['target'],**options)
    if final.analysis['direction_status']!='CORRECT':raise RuntimeError('Actual final direction/PAM check failed')
    delivery=observe_files('crispr.delivery',deliver_result,
        args=({'expected_components':[{'sequence':request['spacer_seq']}]},sources,[step],candidate,out_dir/'dna'),
        output_paths=lambda value:[row['path'] for row in value.get('present_files',[])],
        output_directories=[out_dir/'dna'],artifact_role='supporting-file')
    actual_path=Path(delivery['directory'])/'construct.gb';expected_path=case_dir/'expected.fasta'
    observe_files('example.independent_readback',independent_readback,
        args=(actual_path,expected_path,out_dir/'independent-readback.json'),
        input_paths=[actual_path,expected_path],output_paths=lambda value:value['paths'],
        output_directories=[out_dir],artifact_role='supporting-file')
    return {'status':'delivered','summary':'Initial '+initial.analysis['direction_status']+
        ' retained; spacer corrected; final '+final.analysis['direction_status']+'. Preparation is simulated, not performed.',
        'initial_grna':initial.analysis,'grna':final.analysis,'preparation':step.result.analysis,
        'delivery':delivery,'report_unverified_scope':['Synthetic locator/ORF function NOT_TESTED.',
        'PCR, DpnI, KLD and transformation PLANNED; wet experiment NOT_PERFORMED.',
        'No genome-wide off-target or knockout-efficiency test. Official GitLab CI not executed.']}


def combine_packets(trace,packets,title):
    recorder=Recorder(trace,mode_at_capture='full');graph=assemble(recorder.events)
    stages=[];steps={};relations=[];paths=[]
    for number,packet in enumerate(packets):
        prefix='attempt-'+str(number+1)+'-';process=packet['design_process']
        mapping={key:prefix+key for key in process['steps']}
        for key,row in process['steps'].items():steps[mapping[key]]=copy.deepcopy(row)
        for stage in process['stages']:
            stage=copy.deepcopy(stage);stage['id']=prefix+stage['id']
            stage['title']='Rejected initial attempt' if number==0 else 'Corrected request and revalidation'
            stage['step_ids']=[mapping[key] for key in stage['step_ids']];stages.append(stage)
        for relation in process['relations']:
            relation=copy.deepcopy(relation);relation['id']=prefix+relation['id']
            relation['from']=mapping[relation['from']];relation['to']=mapping[relation['to']];relations.append(relation)
        for path in process['paths']:
            path=copy.deepcopy(path);path['id']=prefix+path['id'];path['step_ids']=[mapping[key] for key in path['step_ids']];paths.append(path)
    order=list(steps);refs=list(dict.fromkeys(ref for row in steps.values() for ref in row['source_refs']))
    packet={'schema_version':'trace-organization-v1','id':'combined-example',
        'basis':{key:graph['snapshot'][key] for key in ('trace_id','through_sequence')},
        'design_process':{'stages':stages,'steps':steps,'relations':relations,'paths':paths,
            'unresolved':[],'detail_refs':[]},
        'report_plan':{'profile':'research-report-v1','title':title,
            'context':{'text':'Scripted synthetic example: original rejection, explicit correction and actual rechecks. Solid lines prove file-hash equality only. Prior failures remain visible; wet experiments were not performed. Official GitLab CI was not executed.',
                'source_refs':refs[:1]},
            'sections':[],'diagram':{'reading_order':order,'relation_refs':[row['id'] for row in relations],
                'short_labels':{key:row['title'] for key,row in steps.items()}},'detail_refs':[]}}
    organize(recorder,packet,actor='synthetic-example-program')
    with language_scope('en'):return recorder.render()


def run(name,inputs):
    case_dir=inputs/name;trace=case_dir/'trace'
    os.environ['SNAPGENE_TRACE_CONFIG']=str(case_dir/'trace-settings.json')
    if trace.exists():raise FileExistsError('Preserve earlier attempts; use newly generated inputs')
    oracle=read_json(inputs/'construction.json')[name]
    if name in ('kit-identity','kit-evidence'):
        command=name.removeprefix('kit-');output=case_dir/'result'
        process=subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'genome-revival-toolkit/scripts/run_toolkit.py'),
            command,'--context',str(case_dir/'context.json'),'--request',str(case_dir/'request.json'),
            '--out-dir',str(output),'--trace-dir',str(trace),'--language','en'],capture_output=True,encoding='utf-8')
        assert process.returncode==0,process.stderr
        result=read_json(output/'result.json');assert result['status']=='analysed'
        if command=='identity':
            assay=result['assays'][0];assert assay['quality_status']=='PASSED'
            assert {row['reference']:row.get('amplicon_length_bp') for row in assay['predictions']}==oracle['amplicon_lengths']
            assert assay['discrimination']['status']=='PREDICTED_DIFFERENT'
        else:
            assert {row['group']:row['colony_yield_per_reported_cell'] for row in result['groups']}==oracle['colony_yields']
            assert abs(result['comparisons'][0]['normalised_difference']-oracle['normalised_difference'])<1e-12
            assert len(result['findings'])==oracle['expected_contradictions']
            assert all(row['status']=='INSUFFICIENT' for row in result['conclusions'])
        verified=subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'genome-revival-toolkit/scripts/run_toolkit.py'),
            'verify','--out-dir',str(output)],capture_output=True,encoding='utf-8')
        assert verified.returncode==0 and json.loads(verified.stdout)['status']=='verified'
        receipt={'case':name,'independent_construction_checks':'PASSED','file_check':'verified',
            'scope':oracle['scope'],'wet_lab':'NOT_PERFORMED'}
        write_json(case_dir/'example-check.json',receipt);return receipt
    packets=[]
    if name=='core-guide':
        request=read_json(case_dir/'corrected-request.json')
        bundle={'actor':'synthetic-example-author','nodes':[{'kind':'requirement','id':'R-example',
            'text':request['original_request'],'requirement_source':{'reference':'corrected-request.json#/original_request','form':'verbatim'}},
            {'kind':'decision','id':'D-example','text':request['decisions'][0]['text'],
             'rationale':request['decisions'][0]['rationale'],'decision_actor':'ai','explanation_origin':'ai_concurrent',
             'decision_source':{'reference':'corrected-request.json#/decisions/0'},'responds_to':['R-example']}],
            'context_refs':['R-example@1','D-example@1']}
        with language_scope('en'):
            result=core_example(case_dir,case_dir/'result',trace_dir=trace,trace_input=bundle)
        write_json(case_dir/'result/result.json',result)
        graph=assemble(Recorder(trace).events)
        with language_scope('en'):packets.append(_workflow_packet(graph,'Core: one-base spacer correction'))
        # A single packet already retains initial/replacement/final checks.
        recorder=Recorder(trace);organize(recorder,packets[0],actor='synthetic-example-program')
        with language_scope('en'):graph=recorder.render()
    else:
        command='crispr' if name=='kit-guide' else 'construct'
        results=[]
        for label,file in [('initial','request.json'),('corrected','corrected-request.json')]:
            output=case_dir/label
            process=subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'genome-revival-toolkit/scripts/run_toolkit.py'),
                command,'--context',str(case_dir/'context.json'),'--request',str(case_dir/file),
                '--out-dir',str(output),'--trace-dir',str(trace),'--language','en'],capture_output=True,encoding='utf-8')
            result=read_json(output/'result.json');results.append(result)
            assert process.returncode==(2 if label=='initial' else 0),(label,result['status'])
            graph=assemble(Recorder(trace).events)
            with language_scope('en'):packets.append(_workflow_packet(graph,result.get('report_title')))
        result=results[-1]
        graph=combine_packets(trace,packets,'Toolkit: '+('guide correction' if command=='crispr' else 'donor request correction'))
    with Path(result['delivery']['directory'],'construct.gb').open(encoding='utf-8') as handle:
        actual=SeqIO.read(handle,'genbank')
    with (case_dir/'expected.fasta').open(encoding='utf-8') as handle:expected=SeqIO.read(handle,'fasta')
    assert str(actual.seq)==str(expected.seq),'Current files differ from independently constructed expected sequence'
    if name.endswith('guide'):
        assert result['grna']['spacer']==oracle['expected_spacer']
        assert result['grna']['direction_status']=='CORRECT'
    receipt={'case':name,'expected_sequence_source':'Construction slices and expected.fasta, not the DNA implementation',
        'sequence_equality':'PASSED',**check_file_relationships(graph),
        'scope':'Scripted synthetic engineering and report generation; not autonomous agent success or wet experimentation'}
    write_json(case_dir/'example-check.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('core-guide','kit-guide','kit-construct','kit-identity','kit-evidence'),required=True)
    parser.add_argument('--inputs',type=Path,required=True)
    args=parser.parse_args();receipt=run(args.case,args.inputs.resolve())
    print(json.dumps({key:value for key,value in receipt.items() if key!='independent_file_hash_checks'},indent=2))
