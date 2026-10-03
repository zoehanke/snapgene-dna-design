#!/usr/bin/env python3
"""Summarize examiner evidence, not the executing model's self-reported success."""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

FIELDS = ('goal','preparation','files','verification','conclusion')
STATUSES = {'PASS','FAIL','UNREVIEWED','NOT_APPLICABLE'}


def summarize(rows: list[dict], applicability: dict[str,list[str]]) -> dict:
    results=[]
    seen=set()
    for row in rows:
        task=row['task_id']
        if task not in applicability:
            raise ValueError(f'Unknown or unissued task: {task}')
        key=(row['model'],row['skill_version'],task,row['run_id'])
        if key in seen:
            raise ValueError(f'Duplicate run: {key}')
        seen.add(key)
        required=applicability[task]
        if not required or not set(required).issubset(FIELDS):
            raise ValueError(f'Invalid required criteria for {task}')
        for field in FIELDS:
            status=row.get(field) or 'UNREVIEWED'
            if status not in STATUSES:
                raise ValueError(f'Unknown status for {task}/{field}: {status}')
            if field in required and status=='NOT_APPLICABLE':
                raise ValueError(f'Required criterion cannot be omitted: {task}/{field}')
            if status in {'PASS','FAIL'} and not row.get('evidence'):
                raise ValueError(f'Missing examiner evidence for {task}')
        values=[row.get(f) or 'UNREVIEWED' for f in required]
        intervention=row.get('human_interventions')
        if intervention not in (None,''):
            try:
                intervention=int(intervention)
            except (ValueError,TypeError):
                raise ValueError(f'Invalid human intervention count for {task}')
            if intervention<0:
                raise ValueError(f'Invalid human intervention count for {task}')
        verdict=('FAILED' if 'FAIL' in values else 'UNREVIEWED'
                 if 'UNREVIEWED' in values or intervention in (None,'') else
                 'ASSISTED' if intervention>0 else 'PASSED')
        results.append({**row,'verdict':verdict})
    groups=[]
    for model,version in sorted({(r['model'],r['skill_version']) for r in results}):
        subset=[r for r in results if (r['model'],r['skill_version'])==(model,version)]
        missing=sorted(set(applicability)-{r['task_id'] for r in subset})
        passed=sum(r['verdict']=='PASSED' for r in subset)
        unreviewed=sum(r['verdict']=='UNREVIEWED' or any((r.get(f) or 'UNREVIEWED')=='UNREVIEWED' for f in applicability[r['task_id']])
                       or r.get('human_interventions') in (None,'') for r in subset)
        counts={task:sum(r['task_id']==task for r in subset) for task in applicability}
        balanced=len(set(counts.values()))==1 and not missing
        metadata_complete=bool(model and version and model!='TO_RECORD' and version!='TO_RECORD')
        finished=bool(subset and balanced and not unreviewed and metadata_complete)
        groups.append({'model':model,'skill_version':version,'runs':len(subset),'passed':passed,
                       'failed':sum(r['verdict']=='FAILED' for r in subset),'unfinished_reviews':unreviewed,
                       'assisted':sum(r['verdict']=='ASSISTED' for r in subset),
                       'missing_tasks':missing,'run_counts':counts,'metadata_complete':metadata_complete,
                       'success_rate':passed/len(subset) if finished else None,
                       'all_repeats_success_task_fraction':
                           sum(all(r['verdict']=='PASSED' for r in subset if r['task_id']==t) for t in applicability)/len(applicability)
                           if finished and min(counts.values())>=2 else None})
    return {'source':'examiner-entered evidence; not an automatic DNA verifier','groups':groups,'runs':results}


def main():
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scores',required=True,type=pathlib.Path)
    parser.add_argument('--applicability',type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parents[1]/'benchmarks/host-readiness-v0.1/applicability.json')
    parser.add_argument('--out',type=pathlib.Path)
    args=parser.parse_args()
    with args.scores.open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream))
    rules=json.loads(args.applicability.read_text(encoding='utf-8'))
    try:
        result=summarize(rows,rules)
    except (ValueError,KeyError) as error:
        parser.error(str(error))
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.out:
        args.out.write_text(text+'\n',encoding='utf-8',errors='replace')
    print(text)


if __name__=='__main__':
    main()
