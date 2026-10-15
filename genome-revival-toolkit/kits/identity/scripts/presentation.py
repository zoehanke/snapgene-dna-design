"""Kit-owned presentation; original evidence/values are preserved."""
from pathlib import Path
from evidence_trace.localization import tr, get_language
from kits.shared.summary import summary as shared_summary

def format_comparison(comparison,text):
    data = comparison['analysis']
    return ('- ' + str(text(comparison['query'])) + ' / ' + str(text(comparison['reference'])) + str(tr('：选定区域长度 ')) + str(data['query_length']) + ' / ' + str(data['reference_length']) + str(tr(' bp；比对身份比例 ')) + str(data['identity_pct']) + str(tr('%。最佳比对不证明唯一定位。')))

def summary(result,context_snapshot,request,metadata):
    return shared_summary(result,context_snapshot,request,metadata,format_comparison)

def fact_text(record):
    payload=record["payload"];value=payload.get("result",{})
    if payload.get('stage')=='identity.import_construct_handoff':
        return 'Imported '+str(len(value.get('assays',[])))+' actual donor-QC candidate pairs after checking supplied reference versions; exact PCR and full-pair quality are checked again.'
    return None
