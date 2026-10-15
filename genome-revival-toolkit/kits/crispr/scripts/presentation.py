"""Kit-owned presentation; original evidence/values are preserved."""
from pathlib import Path
from evidence_trace.localization import tr, get_language
from kits.shared.summary import summary as shared_summary

def summary(result,context_snapshot,request,metadata):
    text=lambda value:str(value).replace("<","&lt;").replace(">","&gt;")
    guide = result['grna']
    lines = ['# ' + text(request.get('title', 'CRISPR plasmid preparation')), '', '## Goal', '', text(request['original_request']), '', '## Current outcome', '', text(result['summary']), '', 'Status: ' + result['status'], '', '## What was checked and changed', '', '- Transcribed spacer: `' + guide['spacer'] + '`.', '- Direction: ' + guide['direction_status'] + '; coordinate system: 0-based half-open.', '- Earlier check: ' + result['initial_grna']['direction_status'] + '.', '- Supplied-vector self-target screen: ' + result['self_target']['self_target_status'] + '.', '- Selection compatibility: ' + result['selection']['status'] + '. ' + result['selection']['message']]
    for hit in guide['target_matches']:
        lines.append('- Actual target match: ' + str(hit['protospacer_parts_0based']) + '; identical DNA strand ' + str(hit['strand']) + '; RNA-binding strand ' + str(hit['rna_binding_strand']) + '; PAM ' + hit['pam'] + '; PAM valid: ' + str(hit['pam_valid']) + '.')
    for warning in guide['warnings']:
        lines.append('- Annotation/sequence warning: ' + text(warning['message']))
    if result.get('preparation'):
        data = result['preparation']
        route = data['preparation_route']
        lines.extend(['', '## Planned preparation', '', '- Before: `' + data['replacement']['before'] + '`; after: `' + data['replacement']['after'] + '`.', '- Outside replacement window unchanged: ' + str(data['replacement']['outside_window_unchanged']) + '.', '- Route: ' + route['status'] + '; independent sequence simulation: ' + route['simulation_status'] + '.'])
        lines.extend(('- ' + text(row['action']) for row in data['protocol_steps']))
    lines.extend(['', '## Checks', ''])
    lines.extend(('- ' + row['name'] + ': ' + row['status'] + '.' for row in result['checks']))
    lines.extend(['', '## Files', ''])
    lines.extend(('[' + text(row['purpose']) + '](<' + Path(row['path']).resolve().as_uri() + '>)' for row in result.get('present_files', [])))
    lines.extend(['', '## Limits', '', *('- ' + text(row) for row in metadata['limits']), '- Official GitLab CI has not been executed for the current candidate.', '- Trace records execution and submitted explanations; it does not prove scientific conclusions.', ''])
    return '\n'.join(lines)

def fact_text(record):
    payload=record["payload"];value=payload.get("result",{})
    if isinstance(value,dict):
        analysis=value.get("analysis",{})
        if payload.get('stage') in ('crispr.initial_check', 'crispr.final_check') and isinstance(analysis, dict):
            sites = analysis.get('target_matches', [])
            spacer = analysis.get('spacer')
            spacer_text = str(spacer.get('length')) + ' nt (raw sequence minimized; compare supplied request and final file)' if isinstance(spacer, dict) else str(spacer)
            return 'Transcribed spacer ' + spacer_text + ': ' + str(analysis.get('direction_status')) + '. Target matches/PAMs: ' + '; '.join((str(row['protospacer_parts_0based']) + ', identical strand ' + str(row['strand']) + ', RNA-binding strand ' + str(row['rna_binding_strand']) + ', PAM ' + str(row['pam']) + ', valid=' + str(row['pam_valid']) for row in sites)) + '. Sequence determines direction; annotation warnings remain separate.'
        if payload.get('stage') == 'crispr.replace' and isinstance(value.get('result'), dict):
            data = value['result'].get('analysis', {})
            edit, route = (data.get('replacement', {}), data.get('preparation_route', {}))
            return 'Requested 20 nt spacer replaced; original and current versions are retained' + '; outside window unchanged=' + str(edit.get('outside_window_unchanged')) + '; route=' + str(route.get('status')) + ', independent simulation=' + str(route.get('simulation_status')) + '. Wet experiment NOT_PERFORMED.'
    return None
