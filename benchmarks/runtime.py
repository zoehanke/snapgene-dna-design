"""Reproducible synthetic file/Trace timings; not biological validation."""
import sys,time,json,platform,statistics,tracemalloc,tempfile,random,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'snapgene-dna-design';sys.path.insert(0,str(ROOT))
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature,SimpleLocation
from Bio import SeqIO
from core.tools.sequence_ops import slice_record_interval
from core.tools.snapgene_io import export_plasmid,read_native_dna_record
from evidence_trace.recorder import Recorder
from evidence_trace.process import assemble
from evidence_trace.render import render
from importlib.metadata import version

def measure(fn,repeats=3):
 samples=[];peaks=[]
 for _ in range(repeats):
  tracemalloc.start();t=time.perf_counter();fn();samples.append(time.perf_counter()-t);peaks.append(tracemalloc.get_traced_memory()[1]);tracemalloc.stop()
 return {'seconds':samples,'median_seconds':statistics.median(samples),'max_python_allocated_bytes':max(peaks),'repeats':repeats}

def run(out):
 rows=[]
 with tempfile.TemporaryDirectory(prefix='dna-benchmark-') as tmp:
  tmp=Path(tmp);os.environ['SNAPGENE_TRACE_CONFIG']=str(tmp/'config.json');(tmp/'config.json').write_text('{"trace_level":"off"}',encoding='utf-8')
  for n in (5000,50000,500000):
   rng=random.Random(810+n);seq=''.join(rng.choices('ACGT',k=n))
   rec=SeqRecord(Seq(seq),id='synthetic',annotations={'molecule_type':'DNA','topology':'circular'})
   rec.features=[SeqFeature(SimpleLocation(i,i+30,strand=1),type='misc_feature',qualifiers={'label':[f'region-{i}']}) for i in range(100,n-30,1000)]
   source=tmp/f'synthetic-{n}.gb'
   with source.open('w',encoding='utf-8') as h:SeqIO.write(rec,h,'genbank')
   def transform():
    fragment=slice_record_interval(rec,n-200,n//2,circular=True)
    paths=export_plasmid(fragment,tmp/'export',f'fragment-{n}',topology='linear')
    actual=read_native_dna_record(paths['dna_file']);assert str(actual.seq)==seq[-200:]+seq[:n//2-200]
   rows.append({'case':'extract-export-readback','bases':n,'features':len(rec.features),**measure(transform)})
   def inspect_cli():
    p=subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'scripts/inspect_plasmid.py'),str(source),'--json'],capture_output=True,encoding='utf-8',errors='replace',cwd=ROOT)
    assert p.returncode==0,p.stderr
   rows.append({'case':'inspect-cli-including-startup','bases':n,'features':len(rec.features),**measure(inspect_cli)})
  (tmp/'config.json').write_text('{"trace_level":"observed"}',encoding='utf-8')
  for count in (100,1000):
   r=Recorder(tmp/f'trace-{count}')
   with r.writing():
    for i in range(count):r.record({'id':f'R{i}','kind':'requirement','text':f'Independent recorded requirement {i}'})
   def build():render(r.directory,assemble(r.events))
   rows.append({'case':'trace-rebuild','events':len(r.events),**measure(build), 'html_bytes':(r.directory/'index.html').stat().st_size})
 data={'python':sys.version,'platform':platform.platform(),'processor':platform.processor(),'cpu_count':os.cpu_count(),'versions':{p:version(p) for p in ('biopython','sgffp','jsonschema','primer3-py')},'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,encoding='utf-8').strip(),'working_tree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,encoding='utf-8').strip()),'memory_scope':'tracemalloc in this Python process; excludes child-process/native allocations','rows':rows}
 Path(out).parent.mkdir(parents=True,exist_ok=True);Path(out).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8');print(out)
if __name__=='__main__':run(sys.argv[1])
