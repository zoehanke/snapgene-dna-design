"""Owned conditional assay/order projection; no candidate quality is changed."""
import csv
from pathlib import Path
from evidence_trace.localization import tr
from evidence_trace.models import file_digest


def outputs(result,out_dir,write=False):
    if not result.get('assays'):return {'paths':[],'write_receipts':[],'present_files':[]}
    path=Path(out_dir)/'identity-primers.tsv'
    receipts=[]
    if write:
        with path.open('w',encoding='utf-8',errors='replace',newline='') as handle:
            writer=csv.DictWriter(handle,delimiter='\t',fieldnames=['name','sequence_5to3','assay','quality_status'])
            characters=writer.writeheader()
            for assay in result['assays']:
                for side in ('forward','reverse'):
                    characters+=writer.writerow({'name':assay['id']+'_'+side,'sequence_5to3':assay[side],
                        'assay':assay['id'],'quality_status':assay['quality_status']})
        receipts.append({'path':str(path.resolve()),'sha256':file_digest(path),'characters_written':characters})
    return {'paths':[str(path)],'write_receipts':receipts,
      'present_files':[{'path':str(path.resolve()),'purpose':tr('检测候选及完整质量状态；失败候选不可当作已通过订单')}]}
