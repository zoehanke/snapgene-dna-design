"""Kit-owned presentation; original evidence/values are preserved."""
from pathlib import Path
from evidence_trace.localization import tr, get_language
from kits.shared.summary import summary as shared_summary

def format_comparison(comparison,text):
    return ('- ' + text(comparison['experiment_group']) + ' / ' + text(comparison['control_group']) + tr('：仅按提交计数计算的菌落产率差 ') + str(comparison['normalised_difference']) + '; ' + text(comparison['scope']))

def summary(result,context_snapshot,request,metadata):
    return shared_summary(result,context_snapshot,request,metadata,format_comparison)

def fact_text(record):
    payload=record["payload"];value=payload.get("result",{})
    if payload.get('stage')=='evidence.compare_expected_results':
        missing=', '.join(value.get('not_tested_assays',[])) or 'none in this supplied comparison'
        return 'Reported bands versus supplied local PCR predictions: '+str(value.get('status'))+'. '+str(value.get('reason'))+' Not tested: '+missing+'. This does not authenticate experiments or prove revival.'
    return None
