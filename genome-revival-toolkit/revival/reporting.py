"""Organise known executed workflow facts; supplied scientific reasons stay attributed."""
from __future__ import annotations
from evidence_trace.localization import tr, display, get_language

from pathlib import Path
from types import MappingProxyType
from kits.catalog import stage_application, application_function, trace_labels, trace_skip, strip_trace_prefix

from evidence_trace.recorder import Recorder, load_events
from evidence_trace.process import assemble, organize
from evidence_trace.intake import record_handoff
from evidence_trace.render import render
from evidence_trace.models import file_digest
from evidence_trace.runtime import TraceStopped

# Legacy readers retain a read-only view; declarations are owned by manifests.
LABELS = MappingProxyType(trace_labels())




def _returned_text(record):
    payload = record['payload']
    value = payload.get('result', {})
    if record['event_type'].endswith('_failed'):
        return tr('本次调用未得到正常返回：') + str(payload.get('error', tr('未记录原因')))

    app=stage_application(payload.get('stage',''))
    if app:
        custom=application_function(app['manifest']['metadata']['command'],'fact_entry')(record)
        if custom is not None:return custom
    if isinstance(value, dict):
        if get_language() == 'en' and value.get('kit'):
            return value.get('report_summary') or ('Toolkit ' + value['kit'] + ': ' + str(value.get('status')) + '. See scoped checks and files.')
        analysis = value.get('analysis', {})


        if value.get('summary'):
            return str(value['summary'])
        method = value.get('method')
        returned = value.get('result', {})
        analysis = returned.get('analysis', {}) if isinstance(returned, dict) else {}
        if method and value.get('status') == 'failed':
            error = value.get('error') or {}
            return tr('本次方法未完成：') + str(error.get('message', tr('原因见实际返回。')))





        if value.get('status'):
            return tr('程序返回状态：') + str(value['status']) + tr('。含义与实际范围以该次返回为准。')
        analysis = value.get('analysis', {})
        if isinstance(analysis, dict) and analysis.get('amplicon_length'):
            return (str(tr('该参考预测扩增产物 ')) + str(analysis['amplicon_length']) + str(tr(' bp；不是实测PCR结果。')))
        products = value.get('products', value.get('result', {}).get('products', []))
        if isinstance(products, list) and products:
            lengths = [p.get('sequence', {}).get('length') for p in products if isinstance(p.get('sequence'), dict)]
            if lengths:
                return tr('程序返回实际分子，长度为 ') + ' / '.join(map(str, lengths)) + ' bp。'
    return tr('程序完成此步骤；参数、实际返回和对应材料保留在详细记录中。')


def _workflow_packet(graph, request_title=None):
    records = graph['source_records']
    run = graph['runs'][-1] if graph['runs'] else None
    run_id = run['id'] if run else None
    contexts = set(run.get('context_refs', [])) if run else set()
    steps = {}
    for ref in sorted(contexts, key=lambda r: records.get(r, {}).get('recorded_sequence', 0)):
        node = records.get(ref, {})
        kind = node.get('kind')
        if kind not in ('requirement', 'decision'):
            continue
        key = 'step-' + str(len(steps) + 1)
        step = {'kind': 'requirement' if kind == 'requirement' else 'choice',
                'title': tr('确定本次任务与检查范围') if kind == 'requirement' else node.get('title', node['text']),
                'content': tr('用户提交了本次任务。完整原文保留在任务与要求及来源记录。') if kind == 'requirement' else node['text'], 'subject_ref': ref,
                'source_refs': [ref], 'input_refs': [], 'outcome_refs': []}
        if kind == 'decision' and node.get('rationale'):
            step['reason'] = {'text': node['rationale'], 'source_refs': [ref],
                              'origin': 'original_statement' if node.get('explanation_origin') in ('ai_concurrent', 'user_statement') else 'unknown'}
        steps[key] = step
    events = sorted((r for r in records.values() if r.get('run_id') == run_id and r.get('event_type') in
                     {'stage_completed', 'stage_failed', 'file_operation_completed', 'file_operation_failed'}), key=lambda e: e['sequence'])
    for event in events:
        ref = event['event_id']
        stage = event['payload'].get('stage', '')
        if stage in trace_skip():
            continue  # Echoed aggregate returns remain in technical data, not duplicated as extra work.
        if stage == 'outcome' and not event['payload'].get('result', {}).get('kit'):
            continue
        title = display(trace_labels(), stage)
        value = event['payload'].get('result', {})
        if title is None and isinstance(value, dict) and value.get('method'):
            title = {'prepare_pcr_fragment': tr('从实际模板扩增片段'), 'recipe_gibson_assembly': tr('组装实际PCR片段'),
                     'recipe_cloning_verification': tr('检查当前供体接口')}.get(value['method'])
        if title is None:
            title = tr('执行 ') + strip_trace_prefix(stage)
        outcomes = [key for key, row in records.items() if row.get('kind') in ('validation', 'artifact') and row.get('result_event_ref') == ref]
        steps['step-' + str(len(steps) + 1)] = {'kind': 'program_result', 'title': title,
            'content': _returned_text(event), 'source_refs': [ref],
            'input_refs': [event['payload']['stage_ref']] if event['payload'].get('stage_ref') else [], 'outcome_refs': outcomes}
    if not steps:
        return None
    owners={ref:key for key,step in steps.items() for ref in [*step['source_refs'],*step['input_refs'],*step['outcome_refs']]}
    matched={}
    for fact in graph['fact_relations']:
        if fact.get('kind')!='input_reference' or fact.get('verification_method')!='sha256_equality':
            continue
        artifact=records.get(fact['from'],{})
        producer=owners.get(artifact.get('result_event_ref')); consumer=owners.get(fact['to'])
        if not producer or not consumer or producer==consumer:
            continue
        link=matched.setdefault((producer,consumer),{'id':'file-match-'+str(len(matched)+1),
            'from':producer,'to':consumer,'kind':'grouped_with',
            'meaning':tr('程序验证的关系：输出文件与声明输入文件的SHA-256相等。仅文件内容关联，不推断科学支持、物理使用或因果。'),
            'source_refs':[],'fact_relation_ids':[]})
        link['fact_relation_ids'].append(fact['id'])
        link['source_refs']=list(dict.fromkeys([*link['source_refs'],*fact['source_refs']]))
    relations=list(matched.values())
    order = list(steps)
    refs = list(dict.fromkeys(ref for step in steps.values() for ref in step['source_refs']))
    title = request_title or tr('Genome Revival：任务过程与证据')
    return {'schema_version': 'trace-organization-v1', 'id': 'workflow-' + str(graph['snapshot']['through_sequence']),
            'basis': {k: graph['snapshot'][k] for k in ('trace_id', 'through_sequence')},
            'design_process': {'stages': [{'id': 'workflow-stage', 'title': tr('实际任务过程'),
                'purpose': tr('按记录展示用户要求、已提交的选择和程序执行。顺序不自动证明科学因果。'),
                'step_ids': order, 'source_refs': refs}], 'steps': steps, 'relations': relations,
                'paths': [{'id': 'recorded-path', 'label': tr('实际记录顺序'), 'step_ids': order, 'source_refs': refs, 'order_kind': 'recorded_order'}],
                'unresolved': [], 'detail_refs': [key for key, row in records.items() if row.get('event_type') != 'node_recorded']},
            'report_plan': {'profile': 'research-report-v1', 'title': title,
                'context': {'text': (str(tr('程序验证的文件关系')) + str(len(relations)) + str(tr('条；本次自动组织的声明关系0条。其他声明关系只有提交记录，不能借此认证科学含义。本报告记录明确提交的任务、真实材料、程序步骤及检查范围。公开理由只来自已提交说明；未观察的宿主行为不补写成事实。'))), 'source_refs': refs[:1]},
                'sections': [{'id': 'workflow-section', 'title': tr('任务怎样形成实际结果？'), 'step_refs': order, 'source_refs': refs}],
                'diagram': {'reading_order': order, 'relation_refs': [link['id'] for link in relations], 'short_labels': {k: steps[k]['title'] for k in order}},
                'default_expanded_refs': [], 'detail_refs': []}}


def finish_trace(out_dir, directory, result, level, policy='normal'):
    if level == 'off':
        return {'status': 'off', 'scope': 'No new Evidence Trace was collected.'}
    try:
        recorder = Recorder(directory, mode_at_capture=level if level in ('observed', 'full') else 'observed')
        with recorder.writing():
            graph = assemble(recorder.events)
            if not graph['runs']:
                raise ValueError('No completed Toolkit run was captured.')
            latest_run_id = graph['runs'][-1]['id']
            if not any(event.get('run_id') == latest_run_id and event.get('event_type') == 'stage_completed'
                       and event.get('payload', {}).get('stage') == 'outcome'
                       and event['payload'].get('result', {}).get('invocation') == result['invocation']
                       for event in recorder.events):
                raise ValueError('The current invocation has no captured outcome; previous runs cannot provide its evidence.')
            paths = [item for item in result.get('present_files', []) if Path(item['path']).is_file()]
            if paths:
                record_handoff(recorder, paths, actor='workflow-program', run_id=graph['runs'][-1]['id'])
            graph = assemble(recorder.events)
            packet = _workflow_packet(graph, request_title=result.get('report_title'))
            if packet:
                organize(recorder, packet, actor='workflow-program')
            graph = recorder.render()
        status = 'complete' if graph['integrity'] == 'complete' else 'TRACE_INCOMPLETE'
        if policy == 'strict' and status != 'complete':
            raise ValueError('Required Toolkit recording has capture gaps.')
        return {'status': status, 'html': str(Path(directory) / 'index.html'), 'markdown': str(Path(directory) / 'report.md'),
                'technical_record': str(Path(directory) / 'graph.json'),
                'scope': 'Toolkit calls, their actual results/files and supplied notes only. Record completeness is not DNA correctness or experimental proof.'}
    except Exception as exc:
        if policy == 'strict':
            raise TraceStopped('Trace report incomplete; completed DNA files remain unchanged: ' + str(exc)) from exc
        return {'status': 'TRACE_INCOMPLETE', 'error': str(exc), 'scope': 'DNA/domain result retained; records or views are incomplete.'}


def rebuild(directory):
    recorder = Recorder(directory, mode_at_capture='observed')
    with recorder.writing():
        events, errors = load_events(directory)
        graph = assemble(events, errors)
        handoff = graph.get('handoff')
        if handoff:
            previous = handoff['files']
            changed = any(not Path(row['path']).is_file() or file_digest(row['path']) != row.get('sha256') for row in previous)
            if changed:
                record_handoff(recorder, previous, actor='workflow-file-observer', run_id=handoff.get('run_id'))
                events, errors = load_events(directory)
                graph = assemble(events, errors)
        # Reuse the checked snapshot without another molecular-payload projection.
        graph = render(directory, graph)
    return {'html': str(Path(directory) / 'index.html'), 'markdown': str(Path(directory) / 'report.md'),
            'integrity': graph['integrity'], 'organization_status': graph['snapshot']['organization_status'],
            'scope': 'Rebuilt from saved events; changed files do not inherit old checks.'}
