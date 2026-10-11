"""Organise known executed workflow facts; supplied scientific reasons stay attributed."""
from __future__ import annotations

from pathlib import Path

from evidence_trace.recorder import Recorder, load_events
from evidence_trace.process import assemble, organize
from evidence_trace.intake import record_handoff
from evidence_trace.render import render
from evidence_trace.models import file_digest
from evidence_trace.runtime import TraceStopped

LABELS = {
    'toolkit.context': '核对项目材料与当前文件版本',
    'toolkit.construct': '完成供体制备与正式验收', 'toolkit.identity': '汇总给定区域的鉴别结果',
    'toolkit.evidence': '整理实验观察与结论范围', 'toolkit.export': '保存本次报告与技术记录',
    'construct.reference': '读取实际目标参考', 'construct.cargo': '读取实际标记模板',
    'construct.donor_template': '核对可用完整PCR模板',
    'construct.model': '核对同源臂、标记片段与目标边界',
    'construct.left_boundary_qc': '检查供体左侧接口',
    'construct.right_boundary_qc': '检查供体右侧接口',
    'construct.delivery': '核查并交付当前供体', 'construct.delivery_receipt': '核对真正交付的文件',
    'construct.outcome': '记录供体构建的实际结果', 'outcome': '记录本次实际结果',
    'identity.compare_regions': '比较两份给定参考区域', 'identity.design_primers': '为选定区间设计检测引物',
    'identity.complete_oligo_quality': '检查完整引物及当前条件', 'identity.simulate_pcr': '在实际参考上模拟PCR',
    'evidence.read_observations': '读取实验记录文件',
}


def _returned_text(record):
    payload = record['payload']
    value = payload.get('result', {})
    if record['event_type'].endswith('_failed'):
        return '本次调用未得到正常返回：' + str(payload.get('error', '未记录原因'))
    if payload.get('stage') == 'construct.model' and isinstance(value, list) and len(value) == 2:
        model = value[1]
        if isinstance(model, dict):
            length = model.get('product', {}).get('expected_length')
            if length is not None:
                return f'按明确的参考位点、左右同源臂和标记边界，核对预期 {length} bp 线性供体。这里只建立序列与注释模型，实际制备在后续步骤执行。'
    if isinstance(value, dict):
        if value.get('summary'):
            return str(value['summary'])
        method = value.get('method')
        returned = value.get('result', {})
        analysis = returned.get('analysis', {}) if isinstance(returned, dict) else {}
        if method and value.get('status') == 'failed':
            error = value.get('error') or {}
            return '本次方法未完成：' + str(error.get('message', '原因见实际返回。'))
        if method in ('prepare_pcr_fragment', 'recipe_gibson_assembly') and value.get('status') == 'completed':
            products = returned.get('products', [])
            sequence = products[0].get('sequence') if len(products) == 1 else None
            length = sequence.get('length') if isinstance(sequence, dict) else len(sequence) if isinstance(sequence, str) else None
            if length is not None:
                route = '由完整模板和本次引物计算得到' if method == 'prepare_pcr_fragment' else '由实际PCR片段计算组装得到'
                return f'{route} {length} bp 供体候选。完整引物、条件及结构质量另行检查；计算产物不等于实际实验成功。'
        if method == 'recipe_cloning_verification' and value.get('status') == 'completed':
            details = analysis.get('details', {})
            length = details.get('junction_pcr_primers', {}).get('expected_amplicon_size_bp')
            if length is not None:
                backgrounds = details.get('parental_pcr', {}).get('templates', [])
                background_text = ('在本次给定背景参考中未预测产物' if backgrounds and all(row.get('status') == 'NO_PRODUCT_PREDICTED' for row in backgrounds)
                                   else '给定背景也有预测产物，需要结合具体长度区分' if any(row.get('status') == 'PRODUCT_PREDICTED' for row in backgrounds)
                                   else '背景鉴别尚未完整核查')
                return f'当前供体的该接口PCR预测为 {length} bp；{background_text}。这是给定序列上的计算方案，不是实测PCR或全基因组特异性结论。'
        if payload.get('stage') == 'construct.delivery' and value.get('status') == 'delivered':
            scopes = value.get('validation', {}).get('scope_results', {})
            if all(scopes.get(name, {}).get('status') == 'PASSED' for name in ('sequence_model', 'preparation_model', 'file', 'user_goal')):
                return '当前正式文件已回读，供体序列、计算制备链、实际文件和已声明目标四项核查通过。该结论不包括实际整合、表达或基因组复活。'
        if payload.get('stage') == 'construct.delivery_receipt' and value.get('status') == 'verified':
            return '真正选择交付的文件与本次受检版本一致。回执核对文件归属及完整性，不重新下生物学结论。'
        if payload.get('stage') in ('construct.reference', 'construct.cargo', 'construct.donor_template'):
            sequence = value.get('sequence')
            if isinstance(sequence, dict) and sequence.get('length') is not None:
                return f'读取本次选定的 {sequence["length"]} bp 序列记录，供后续来源和边界核对。文件存在与版本核对不等于实际菌株身份认证。'
        if value.get('status'):
            return '程序返回状态：' + str(value['status']) + '。含义与实际范围以该次返回为准。'
        analysis = value.get('analysis', {})
        if isinstance(analysis, dict) and analysis.get('amplicon_length'):
            return f"该参考预测扩增产物 {analysis['amplicon_length']} bp；不是实测PCR结果。"
        products = value.get('products', value.get('result', {}).get('products', []))
        if isinstance(products, list) and products:
            lengths = [p.get('sequence', {}).get('length') for p in products if isinstance(p.get('sequence'), dict)]
            if lengths:
                return '程序返回实际分子，长度为 ' + ' / '.join(map(str, lengths)) + ' bp。'
    return '程序完成此步骤；参数、实际返回和对应材料保留在详细记录中。'


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
                'title': '确定本次任务与检查范围' if kind == 'requirement' else node.get('title', node['text']),
                'content': '用户提交了本次任务。完整原文保留在任务与要求及来源记录。' if kind == 'requirement' else node['text'], 'subject_ref': ref,
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
        if stage in {'toolkit.construct', 'toolkit.identity', 'toolkit.evidence', 'construct.outcome'}:
            continue  # Echoed aggregate returns remain in technical data, not duplicated as extra work.
        if stage == 'outcome' and not event['payload'].get('result', {}).get('kit'):
            continue
        title = LABELS.get(stage)
        value = event['payload'].get('result', {})
        if title is None and isinstance(value, dict) and value.get('method'):
            title = {'prepare_pcr_fragment': '从实际模板扩增片段', 'recipe_gibson_assembly': '组装实际PCR片段',
                     'recipe_cloning_verification': '检查当前供体接口'}.get(value['method'])
        if title is None:
            title = '执行 ' + stage.removeprefix('construct.')
        outcomes = [key for key, row in records.items() if row.get('kind') in ('validation', 'artifact') and row.get('result_event_ref') == ref]
        steps['step-' + str(len(steps) + 1)] = {'kind': 'program_result', 'title': title,
            'content': _returned_text(event), 'source_refs': [ref],
            'input_refs': [event['payload']['stage_ref']] if event['payload'].get('stage_ref') else [], 'outcome_refs': outcomes}
    if not steps:
        return None
    order = list(steps)
    refs = list(dict.fromkeys(ref for step in steps.values() for ref in step['source_refs']))
    title = request_title or 'Genome Revival：任务过程与证据'
    return {'schema_version': 'trace-organization-v1', 'id': 'workflow-' + str(graph['snapshot']['through_sequence']),
            'basis': {k: graph['snapshot'][k] for k in ('trace_id', 'through_sequence')},
            'design_process': {'stages': [{'id': 'workflow-stage', 'title': '实际任务过程',
                'purpose': '按记录展示用户要求、已提交的选择和程序执行。顺序不自动证明科学因果。',
                'step_ids': order, 'source_refs': refs}], 'steps': steps, 'relations': [],
                'paths': [{'id': 'recorded-path', 'label': '实际记录顺序', 'step_ids': order, 'source_refs': refs, 'order_kind': 'recorded_order'}],
                'unresolved': [], 'detail_refs': [key for key, row in records.items() if row.get('event_type') != 'node_recorded']},
            'report_plan': {'profile': 'research-report-v1', 'title': title,
                'context': {'text': '本报告记录明确提交的任务、真实材料、程序步骤及检查范围。公开理由只来自已提交说明；未观察的宿主行为不补写成事实。', 'source_refs': refs[:1]},
                'sections': [{'id': 'workflow-section', 'title': '任务怎样形成实际结果？', 'step_refs': order, 'source_refs': refs}],
                'diagram': {'reading_order': order, 'relation_refs': [], 'short_labels': {k: steps[k]['title'] for k in order}},
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
            packet = _workflow_packet(graph)
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
        graph = assemble(recorder.events)
        handoff = graph.get('handoff')
        if handoff:
            previous = handoff['files']
            changed = any(not Path(row['path']).is_file() or file_digest(row['path']) != row.get('sha256') for row in previous)
            if changed:
                record_handoff(recorder, previous, actor='workflow-file-observer', run_id=handoff.get('run_id'))
        graph = recorder.render()
    return {'html': str(Path(directory) / 'index.html'), 'markdown': str(Path(directory) / 'report.md'),
            'integrity': graph['integrity'], 'organization_status': graph['snapshot']['organization_status'],
            'scope': 'Rebuilt from saved events; changed files do not inherit old checks.'}
