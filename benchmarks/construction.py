"""Time actual public task seams, reporting independent annotation correctness."""
import argparse
import json
from pathlib import Path
import random
import statistics
import sys
import tempfile
import time

p=argparse.ArgumentParser()
p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]/'snapgene-dna-design')
p.add_argument('--output',required=True,type=Path)
a=p.parse_args()
sys.path.insert(0,str(a.root.resolve()))
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature,SimpleLocation
from Bio import SeqIO
from core import plan,execute,validate,finalize
from core.tools.snapgene_io import read_native_dna_record
samples=[];checks=[]
with tempfile.TemporaryDirectory(prefix='task-benchmark-') as tmp:
 tmp=Path(tmp);rng=random.Random(221)
 rec=SeqRecord(Seq('ATGGCTAAATAA'+''.join(rng.choices('ACGT',k=2988))),id='synthetic',annotations={'molecule_type':'DNA','topology':'linear'})
 rec.features=[SeqFeature(SimpleLocation(0,12,strand=1),type='CDS',qualifiers={'label':['test CDS'],'translation':['MAK']})]
 source=tmp/'source.gb'
 with source.open('w',encoding='utf-8') as h:SeqIO.write(rec,h,'genbank')
 task={'schema_version':'construction-task-v1','task_id':'benchmark','revision':1,'mode':'formal','task_kind':'point_mutation','sources':[{'source_id':'source','path':str(source),'role':'template','annotation_status':'reviewed','evidence':{'source_evidence_class':'synthetic-fixture'}}], 'operation':{'mutations':[{'position_1based':6,'ref':'T','alt':'C'}]},'target':{'source_id':'source'},'product':{'topology':'linear','formats':['gb','fasta','dna']},'method_constraints':{},'approvals':{'user_confirmed_task':{'value':True}},'assumptions':[],'provenance':[]}
 for i in range(3):
  t=time.perf_counter();validated,p=plan(task);e=execute(validated,p,tmp/str(i));v=validate(validated,p,e);d=finalize(validated,p,e,v,tmp/str(i));samples.append(time.perf_counter()-t)
  actual=read_native_dna_record(Path(d['directory'])/'construct.dna')
  checks.append({'goal_verified':v['overall']=='verified','sequence_correct':str(actual.seq)==str(rec.seq[:5])+'C'+str(rec.seq[6:]),'annotated_cds_preserved':any(f.type=='CDS' and int(f.location.start)==0 and int(f.location.end)==12 for f in actual.features)})
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps({'case':'public-construction-task','bases':3000,'seed':221,'repeats':3,'seconds':samples,'median_seconds':statistics.median(samples),'independent_checks':checks,'scope':'Computational annotated-file editing, not PCR or wet-lab validation.'},indent=2),encoding='utf-8')
print(a.output)
