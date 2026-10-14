"""Inspect real CLI products of an extracted package, using generated inputs only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import zipfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive',required=True,type=Path)
    parser.add_argument('--work',required=True,type=Path)
    parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args()
    args.work.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(args.archive) as archive:
        archive.extractall(args.work/'installed')
    skill=(args.work/'installed/snapgene-dna-design').resolve()
    sys.path.insert(0,str(skill))
    from Bio.Seq import Seq
    from Bio.SeqRecord import SeqRecord
    from Bio.SeqFeature import FeatureLocation,CompoundLocation,SeqFeature
    from core.models.molecule import as_molecule
    from core.tools import export_snapgene
    rng=random.Random(91013)
    sequence=''.join(rng.choices('ACGT',k=250))+'GAATTC'+''.join(rng.choices('ACGT',k=444))
    assert sequence.count('GAATTC')==1
    source=SeqRecord(Seq(sequence),id='generated',name='generated',
                     annotations={'molecule_type':'DNA','topology':'linear','nested':{'batch':['input']}})
    source.features=[SeqFeature(CompoundLocation([FeatureLocation(90,105,strand=-1),FeatureLocation(45,60,strand=-1)]),
                       type='misc_feature',qualifiers={'label':['negative domain']}),
                     SeqFeature(FeatureLocation(160,190),type='misc_feature',qualifiers={'label':['retained domain']}),
                     SeqFeature(FeatureLocation(35,75),type='rep_origin',qualifiers={'label':['origin']}),
                     SeqFeature(FeatureLocation(100,145),type='misc_feature',qualifiers={'label':['AmpR']})]
    source.letter_annotations['source_position']=list(range(700))
    source.dbxrefs=['DB:generated']
    inputs=args.work/'材料 空格'
    files=export_snapgene(source,inputs).analysis
    steps=[{'step_id':'pcr','tool':'simulate_pcr','params':{'template':'$input','f_primer':sequence[20:44],
             'r_primer':str(Seq(sequence[396:420]).reverse_complement())}},
           {'step_id':'noop','tool':'strip_terminal_codons','params':{'cds_seq':'$pcr'}},
           {'step_id':'digest','tool':'digest_sequence','params':{'seq':'$noop','enzyme':'EcoRI'}}]
    linear=steps+[
        {'step_id':'filled_left','tool':'fill_or_chew_overhang','params':{'seq':'$digest.products.0'}},
        {'step_id':'filled_right','tool':'fill_or_chew_overhang','params':{'seq':'$digest.products.1'}},
        {'step_id':'joined','tool':'ligate_fragments','params':{'fragments':['$filled_left','$filled_right']}}]
    circular=steps+[
        {'step_id':'joined','tool':'ligate_fragments','params':{'fragments':['$digest.products.0','$digest.products.1'],'circular':True}},
        {'step_id':'rotated','tool':'rotate_sequence','params':{'dna_seq':'$joined','origin_0based':37}}]
    rows=[]
    for name,topology,chain,expected,positions in [
        ('fill','linear',linear,sequence[20:251]+'AATT'+sequence[251:420],list(range(20,251))+[None]*4+list(range(251,420))),
        ('rotation','circular',circular,sequence[57:420]+sequence[20:57],list(range(57,420))+list(range(20,57)))]:
        semantic_rows=[]
        case_rows=[]
        pipeline={'task_id':name,'sources':[{'source_id':'input','path':files['gb_file']}],
                  'topology':topology,'validation_requirements':['sequence_model','preparation_model','file','user_goal'],
                  'steps':chain}
        pipeline_path=inputs/(name+'.json')
        pipeline_path.write_text(json.dumps(pipeline),encoding='utf-8')
        for mode in ('off','observed','full'):
            config=args.work/(mode+'.json')
            config.write_text(json.dumps({'trace_level':mode}),encoding='utf-8')
            out=args.work/(name+'-'+mode)
            env={**os.environ,'SNAPGENE_TRACE_CONFIG':str(config),'PYTHONPATH':''}
            start=time.perf_counter()
            run=subprocess.run([sys.executable,'-X','utf8','-B',str(skill/'scripts/run_pipeline.py'),
                '--pipeline',str(pipeline_path),'--out-dir',str(out),'--confirmed','--json'],
                cwd=args.work,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
            seconds=time.perf_counter()-start
            (args.work/(name+'-'+mode+'.stdout')).write_text(run.stdout,encoding='utf-8')
            (args.work/(name+'-'+mode+'.stderr')).write_text(run.stderr,encoding='utf-8')
            assert run.returncode==0,(name,mode,run.stdout[-2000:],run.stderr[-1000:])
            result=json.loads(run.stdout)
            assert result['status']=='delivered'
            for kind in ('gb','dna'):
                product=as_molecule(out/'authoritative'/('construct.'+kind))
                assert str(product.seq)==expected
                assert product.topology==topology
                assert product.letter_annotations['source_position']==positions
                assert product.dbxrefs==['DB:generated']
                assert product.annotations['nested']=={'batch':['input']}
                labels={f.qualifiers['label'][0]:f for f in product.features}
                assert str(labels['negative domain'].extract(product.seq))==(
                    str(Seq(sequence[90:105]).reverse_complement())+str(Seq(sequence[45:60]).reverse_complement()))
            scopes={key:value['status'] for key,value in result['validation_report']['scope_results'].items()}
            assert all(value=='PASSED' for value in scopes.values())
            hashes={kind:hashlib.sha256((out/'authoritative'/('construct.'+kind)).read_bytes()).hexdigest()
                    for kind in ('gb','dna','fasta')}
            semantic={'molecule':product.to_dict(),'primers':(out/'primer_order_table.tsv').read_text(encoding='utf-8'),
                      'scopes':scopes,'artifact_sha256':hashes}
            semantic_rows.append(semantic)
            trace=(out/'evidence-trace/events.jsonl').exists()
            assert trace==(mode!='off')
            case_rows.append({'mode':mode,'seconds':seconds,'length':len(product),
                              'artifact_sha256':hashes,'scopes':scopes,'trace_exists':trace})
        assert semantic_rows[0]==semantic_rows[1]==semantic_rows[2]
        rows.append({'chain':name,'rows':case_rows,'ab_identical':True})
    report={'archive_sha256':hashlib.sha256(args.archive.read_bytes()).hexdigest(),
            'python':sys.executable,'skill_root':str(skill),'rows':rows,
            'scope':'Generated actual public CLI chains and file read-back; no host, desktop or wet-lab claim'}
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    main()
