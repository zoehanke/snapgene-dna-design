"""Render the audit's measured samples, not a performance or biology claim."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[1]/'results/engineering-audit-20260922'
a=json.loads((root/'baseline-benchmarks.json').read_text(encoding='utf-8'))
b=json.loads((root/'final-benchmarks.json').read_text(encoding='utf-8'))
fig,axes=plt.subplots(1,3,figsize=(12,3.6),layout='constrained')
for ax,case,title in zip(axes,['extract-export-readback','inspect-cli-including-startup','trace-rebuild'],['Extract, export and read back','Inspection including startup','Trace rebuild (requirement nodes)']):
 for label,data,color in [('Baseline',a,'#64748b'),('Repaired',b,'#176b63')]:
  rows=[r for r in data['rows'] if r['case']==case]
  xs=[r.get('bases',r.get('events')) for r in rows];ys=[r['median_seconds'] for r in rows]
  ax.plot(xs,ys,'o-',label=label,color=color,linewidth=1.5)
  ax.vlines(xs,[min(r['seconds']) for r in rows],[max(r['seconds']) for r in rows],color=color,linewidth=1)
 ax.set(xscale='log',yscale='log',title=title,xlabel='Events' if case=='trace-rebuild' else 'Input bases',ylabel='Seconds (median and range)')
 ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.15)
axes[0].legend(frameon=False)
fig.suptitle('Observed local runtime, 3 repetitions; not a speedup or biological-validation claim',fontsize=11)
fig.savefig(root/'runtime-comparison.svg');fig.savefig(root/'runtime-comparison.png',dpi=160)
svg=root/'runtime-comparison.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
