"""One application boundary for the Kits and the existing Trace sidecar."""
from __future__ import annotations
from evidence_trace.localization import tr, get_language, language_scope

import copy
import csv
import json
from pathlib import Path
import uuid

from revival import __version__
from revival.bootstrap import CORE_VERSION
from revival.context import ProjectContext, read_json
from core.tools.result import to_wire
from core.runtime_gate import verify_delivery_files
from evidence_trace.models import file_digest, now
from evidence_trace.runtime import traced_run, observe, observe_files, observe_value, TraceStopped
from evidence_trace.settings import get_level

COMMON = {'kit', 'title', 'original_request', 'decisions'}
FIELDS = {
    'construct': {'method', 'target_reference', 'cargo_reference', 'target_interval', 'cargo_interval', 'arm_length',
                  'assembly_overlap_bp', 'preparation_method', 'donor_template_reference', 'donor_interval', 'requirements'},
    'identity': {'references', 'compare_regions', 'alignment_mode', 'assays', 'design_assays'},
    'evidence': {'observations', 'observations_file', 'comparisons', 'genotype_results'},
    'crispr': {'vector_reference', 'target_reference', 'operation', 'spacer_seq', 'promoter_name',
               'promoter_end_0based', 'transcription_strand', 'scaffold_seq', 'target_tm',
               'max_mismatches', 'transcription_promoter', 'strain_genotype'},
}
HUMAN_SCOPE = {
    'construct': '程序核对供体序列、真实计算制备、两侧供体鉴别、保存文件及已声明目标。这里没有进行基因组整合实验。',
    'identity': '仅检查提供的参考和选定区域：比对、逐参考PCR预测、完整引物质量及声明的鉴别条件。没有检验区域外特异性或实际PCR表现。',
    'evidence': '整理已提交的观察与对照，检查数值、引用和记录范围。程序没有重新做实验或认证复活机制。',
    'crispr': 'Checks supplied sequence direction/PAM, candidate factors, vector self-targets, separately simulated preparation and declared selection background. Wet experiments NOT_PERFORMED.',
}
HUMAN_LIMITS = {
    'construct': ['实际菌株基因型、实体模板及实验制备效率未由本计算确认。', '供体接口检查不等于已完成基因组整合；整合与复活需要实验。', '给定参考之外的全基因组特异性未覆盖。'],
    'identity': ['预测只适用于本次给定参考与区域，不能直接推广到实验株或完整基因组。', '实验扩增、条带分离及真实基因型尚未由本计算确认。', '所选标记不能单独证明整个宿主基因组消除或供体基因组恢复功能。'],
    'evidence': ['数据是研究者提交的记录，程序未独立认证实验真实性。', '未检测区域、功能依赖和机制证据仍未覆盖。'],
    'crispr': ['Construct preparation is PLANNED; PCR, DpnI, KLD and editing were not performed.',
               'Only supplied target/vector sequences were searched; no genome-wide off-target or editing efficiency claim.',
               'Annotated CDS structure and declared genotype do not establish measured resistance or functional gRNA.'],
}


def selected_references(kit, request, context):
    if kit == 'construct':
        return list(dict.fromkeys(request[k] for k in ('target_reference', 'cargo_reference', 'donor_template_reference') if request.get(k)))
    if kit == 'identity':
        return request.get('references', list(context.references))
    if kit == 'crispr':
        return list(dict.fromkeys(request[k] for k in ('vector_reference', 'target_reference') if request.get(k)))
    return list(dict.fromkeys(row['reference_id'] for row in request.get('genotype_results', []) if row.get('reference_id')))


def make_trace_bundle(request, context, invocation, request_path, reference_ids):
    request_uri = Path(request_path).resolve().as_uri()
    requirement = {'kind': 'requirement', 'id': 'R-' + invocation, 'text': request['original_request'],
                   'requirement_source': {'reference': request_uri + '#/original_request', 'form': 'verbatim'},
                   'request_action': 'request'}
    nodes, sources = [requirement], {}
    for key in reference_ids:
        entry = context.references.get(key)
        if not entry:
            continue
        path = Path(entry['path'])
        source_id = 'S-' + invocation + '-' + str(len(sources) + 1)
        source = {'kind': 'source', 'id': source_id, 'title': key + ' · ' + path.name,
                  'source_type': 'provided-sequence-file', 'path': str(path),
                  'verification_status': 'unverified'}
        if path.is_file():
            source['source_sha256'] = file_digest(path)
            source['verification_status'] = 'verified'
            source['verification'] = {'verifier': 'Toolkit local file observer', 'method': 'SHA-256 of the actual provided file',
                                      'checked_at': now(), 'locator': str(path), 'scope': 'Local file existence/version only; not strain identity or scientific applicability.'}
        nodes.append(source)
        sources[key] = source_id + '@1'
    for number, note in enumerate(request.get('decisions', []), 1):
        if not isinstance(note, dict) or not isinstance(note.get('text'), str):
            raise ValueError('decisions entries need text and an explicit supplied explanation origin.')
        actor = note.get('actor', 'unknown')
        source_refs = [sources[k] for k in note.get('basis_references', []) if k in sources]
        if len(source_refs) != len(note.get('basis_references', [])):
            raise ValueError('Decision basis_references must identify supplied material references.')
        nodes.append({'kind': 'decision', 'id': 'D-' + invocation + '-' + str(number), 'text': note['text'],
                      'decision_kind': note.get('kind', 'other'), 'rationale': note.get('rationale', ''),
                      'decision_actor': actor, 'explanation_origin': note.get('origin', 'unknown'),
                      'decision_source': {'reference': request_uri + '#/decisions/' + str(number - 1)},
                      'responds_to': [requirement['id']], 'basis_refs': source_refs,
                      'limitations': note.get('limitations', [])})
    return {'actor': 'toolkit-submission-observer', 'nodes': nodes,
            'context_refs': [node['id'] + '@1' for node in nodes]}


def human_summary(result, context_snapshot, request):
    text = lambda value: str(value).replace('<', '&lt;').replace('>', '&gt;')
    if result['kit'] == 'crispr':
        guide = result['grna']
        lines = ['# ' + text(request.get('title', 'CRISPR plasmid preparation')), '',
                 '## Goal', '', text(request['original_request']), '',
                 '## Current outcome', '', text(result['summary']), '',
                 'Status: ' + result['status'], '',
                 '## What was checked and changed', '',
                 '- Transcribed spacer: `' + guide['spacer'] + '`.',
                 '- Direction: ' + guide['direction_status'] + '; coordinate system: 0-based half-open.',
                 '- Earlier check: ' + result['initial_grna']['direction_status'] + '.',
                 '- Supplied-vector self-target screen: ' + result['self_target']['self_target_status'] + '.',
                 '- Selection compatibility: ' + result['selection']['status'] + '. ' + result['selection']['message']]
        for hit in guide['target_matches']:
            lines.append('- Actual target match: ' + str(hit['protospacer_parts_0based']) +
                         '; identical DNA strand ' + str(hit['strand']) + '; RNA-binding strand ' +
                         str(hit['rna_binding_strand']) + '; PAM ' + hit['pam'] +
                         '; PAM valid: ' + str(hit['pam_valid']) + '.')
        for warning in guide['warnings']:
            lines.append('- Annotation/sequence warning: ' + text(warning['message']))
        if result.get('preparation'):
            data = result['preparation']
            route = data['preparation_route']
            lines.extend(['', '## Planned preparation', '',
                '- Before: `' + data['replacement']['before'] + '`; after: `' + data['replacement']['after'] + '`.',
                '- Outside replacement window unchanged: ' + str(data['replacement']['outside_window_unchanged']) + '.',
                '- Route: ' + route['status'] + '; independent sequence simulation: ' + route['simulation_status'] + '.'])
            lines.extend('- ' + text(row['action']) for row in data['protocol_steps'])
        lines.extend(['', '## Checks', ''])
        lines.extend('- ' + row['name'] + ': ' + row['status'] + '.' for row in result['checks'])
        lines.extend(['', '## Files', ''])
        lines.extend('[' + text(row['purpose']) + '](<' + Path(row['path']).resolve().as_uri() + '>)'
                     for row in result.get('present_files', []))
        lines.extend(['', '## Limits', '', *('- ' + text(row) for row in HUMAN_LIMITS['crispr']),
                      '- Official GitLab CI has not been executed for the current candidate.',
                      '- Trace records execution and submitted explanations; it does not prove scientific conclusions.', ''])
        return '\n'.join(lines)
    lines = ['# ' + text(request.get('title', tr('Genome Revival Toolkit 结果'))), '',
             tr('## 我们要完成什么？'), '', text(request['original_request']), '',
             tr('## 本次得到了什么？'), '', text(result.get('report_summary', result.get('summary', result.get('error', tr('当前任务未完成。'))))), '',
             tr('状态：') + {'delivered': tr('当前正式文件已核查'), 'analysed': tr('已完成所述范围内的分析'), 'incomplete': tr('尚未完成'), 'failed': tr('本次未完成')}.get(result['status'], text(result['status'])), '', tr('## 使用了哪些实际材料？'), '']
    for reference in context_snapshot.get('references', []):
        lines.append(('- ' + str(text(reference['id'])) + tr('：') + str(reference['length_bp']) + ' bp; ' + str(text(reference['region'] or tr('完整所选记录'))) + str(tr('。声明菌株身份与实际参考文件核对分开。'))))
    lines.extend(['', tr('## 程序确认了什么？'), '', tr(HUMAN_SCOPE[result['kit']]), ''])
    for comparison in result.get('comparisons', []):
        if result['kit'] == 'identity':
            data = comparison['analysis']
            lines.append(('- ' + str(text(comparison['query'])) + ' / ' + str(text(comparison['reference'])) + str(tr('：选定区域长度 ')) + str(data['query_length']) + ' / ' + str(data['reference_length']) + str(tr(' bp；比对身份比例 ')) + str(data['identity_pct']) + str(tr('%。最佳比对不证明唯一定位。'))))
        elif result['kit'] == 'evidence':
            lines.append('- ' + text(comparison['experiment_group']) + ' / ' + text(comparison['control_group']) +
                tr('：仅按提交计数计算的菌落产率差 ') + str(comparison['normalised_difference']) +
                '; ' + text(comparison['scope']))
    for assay in result.get('assays', []):
        quality = {'PASSED': tr('通过'), 'FAILED': tr('未通过'), 'INCOMPLETE': tr('未完成')}[assay['quality_status']]
        discrimination = {'PREDICTED_DIFFERENT': tr('在给定参考中预测可区分'), 'NOT_DISCRIMINATING': tr('不能区分给定参考'), 'NEEDS_REVIEW': tr('鉴别条件待确认'), 'UNKNOWN': tr('结果未确定'), 'NOT_CHECKED': tr('未检查多背景鉴别')}[assay['discrimination']['status']]
        lines.append(('- ' + str(text(assay['id'])) + str(tr('：完整引物质量')) + str(quality) + '；' + str(discrimination) + '。'))
        for row in assay['predictions']:
            prediction = {'AMPLICON': tr('预测有扩增产物'), 'NO_EXACT_PRODUCT': tr('未预测到精确扩增产物'), 'AMBIGUOUS': tr('存在多个可能产物'), 'UNKNOWN': tr('预测未确定')}[row['prediction']]
            lines.append(f"  - {text(row['reference'])}：{prediction}" + (f"，{row['amplicon_length_bp']} bp。" if row.get('amplicon_length_bp') else '。'))
    for group in result.get('groups', []):
        lines.append(('- ' + str(text(group['group'])) + str(tr('：菌落数 ')) + str(group['colonies'] if group['colonies'] is not None else '未提供') + '；' + str(text(group['growth_statement']))))
    for row in result.get('genotype_results', []):
        lines.append(('- ' + str(text(row['sample_id'])) + ' / ' + str(text(row['reference_id'])) + str(tr('：报告结果 ')) + str(text(row['result'])) + str(tr('；本区域判断 ')) + str(row['assessment']) + '。'))
    for check in result.get('checks', []):
        state = {'PASSED': tr('通过'), 'FAILED': tr('未通过'), 'INCOMPLETE': tr('未完成'), 'NOT_APPLICABLE': tr('不适用')}[check['status']]
        lines.append(('- ' + str(text(check['name'])) + '：' + str(state) + str(tr('。具体条件及原返回见技术记录。'))))
    limitations = [tr(value) for value in HUMAN_LIMITS[result['kit']]]
    if limitations or result.get('findings') or result.get('conclusions'):
        lines.extend(['', tr('## 还有哪些范围没有确认？'), ''])
        lines.extend('- ' + text(item) for item in limitations)
        lines.extend('- ' + text(row['text']) for row in result.get('findings', []))
        lines.extend(f"- {text(row['claim'])}：{row['status']}。{text(row['reason'])}" for row in result.get('conclusions', []))
    lines.extend(['', tr('## 文件在哪里？'), ''])
    for item in result.get('present_files', []):
        lines.append('[' + text(item.get('purpose', Path(item['path']).name)) + '](<' + Path(item['path']).resolve().as_uri() + '>)')
    lines.extend(['', tr('完整技术结果见同目录 result.json；实际来源版本见 context-snapshot.json。'),
                  tr('Evidence Trace覆盖本Toolkit公共调用及明确提交的说明，不声称观察到宿主全部行为。'), ''])
    return '\n'.join(lines)


def save_result_files(result, context_snapshot, request, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = [out / 'result.json', out / 'summary.md', out / 'context-snapshot.json']
    writes = []
    for path, text in ((out / 'result.json', json.dumps(to_wire(result), ensure_ascii=False, indent=2)),
                       (out / 'context-snapshot.json', json.dumps(context_snapshot, ensure_ascii=False, indent=2)),
                       (out / 'summary.md', human_summary(result, context_snapshot, request))):
        count = path.write_text(text, encoding='utf-8', errors='replace')
        writes.append({'path': str(path.resolve()), 'sha256': file_digest(path), 'characters_written': count})
    if result.get('assays'):
        path = out / 'identity-primers.tsv'
        with path.open('w', encoding='utf-8', errors='replace', newline='') as handle:
            writer = csv.DictWriter(handle, delimiter='\t', fieldnames=['name', 'sequence_5to3', 'assay', 'quality_status'])
            characters_written = writer.writeheader()
            for assay in result['assays']:
                for side in ('forward', 'reverse'):
                    characters_written += writer.writerow({'name': assay['id'] + '_' + side, 'sequence_5to3': assay[side],
                                                            'assay': assay['id'], 'quality_status': assay['quality_status']})
        files.append(path)
        writes.append({'path': str(path.resolve()), 'sha256': file_digest(path), 'characters_written': characters_written})
    files.extend(Path(item['path']) for item in result.get('auxiliary_files', []))
    return {'paths': [str(path) for path in files], 'write_receipts': writes}


@traced_run('genome-revival-toolkit')
def execute(request, context, out_dir, invocation, request_path):
    kit = request['kit']
    ids = selected_references(kit, request, context)
    context_snapshot = observe('toolkit.context', context.describe, ids)
    params = {k: copy.deepcopy(v) for k, v in request.items() if k not in COMMON}
    params['original_request'] = request['original_request']
    if kit == 'construct':
        from revival.construct import run_construct as function
    elif kit == 'identity':
        from revival.identity import run_identity as function
    elif kit == 'crispr':
        from revival.crispr import run_crispr as function
    else:
        from revival.evidence import run_evidence as function
        params['_request_dir'] = str(Path(request_path).resolve().parent)
    result = observe('toolkit.' + kit, function, params, context, Path(out_dir))
    result.update(toolkit_version=__version__, core_version=CORE_VERSION, invocation=invocation,
                  report_title=request.get('title'),
                  report_scope=tr(HUMAN_SCOPE[kit]), report_unverified_scope=[tr(value) for value in HUMAN_LIMITS[kit]],
                  original_request=request['original_request'], context=context_snapshot,
                  original_task_verified=False,
                  original_task_scope='Explicit supported fields and program checks only; arbitrary natural-language completeness is not certified.')
    if get_language() == 'en':
        result['report_summary'] = 'Toolkit ' + kit + ': ' + result['status'] + '. Read scoped checks and file roles below.'
    if result.get('delivery'):
        observe_value('outcome', result['delivery'])
    items = [dict(row) for row in (result.get('delivery') or {}).get('present_files', [])]
    for item in items:
        item.setdefault('purpose', item.get('label', Path(item['path']).name))
    items.append({'path': str(Path(out_dir).resolve() / 'summary.md'), 'purpose': tr('本次任务与实际结果摘要')})
    if result.get('assays'):
        items.append({'path': str(Path(out_dir).resolve() / 'identity-primers.tsv'), 'purpose': tr('检测候选及完整质量状态；失败候选不可当作已通过订单')})
    items.extend(result.get('auxiliary_files', []))
    result['present_files'] = items
    export = observe_files('toolkit.export', save_result_files,
        args=(result, context_snapshot, request, Path(out_dir)),
        input_paths=[row['path'] for row in (result.get('delivery') or {}).get('present_files',[])]+[row['path'] for row in result.get('auxiliary_files',[])],
        output_paths=lambda value: value['paths'],
        output_directories=[Path(out_dir)], artifact_role='supporting-file')
    result['result_files'] = export['paths']
    return result


def verify_outputs(directory, expected_receipt_sha256=None):
    directory = Path(directory).resolve()
    receipt_path = directory / 'TOOLKIT-RECEIPT.json'
    receipt = read_json(receipt_path)
    errors = []
    if expected_receipt_sha256 and file_digest(receipt_path) != expected_receipt_sha256:
        errors.append('Toolkit receipt changed.')
    for name, sha in receipt['files'].items():
        path = directory / name
        if not path.is_file() or file_digest(path) != sha:
            errors.append('Output changed or missing: ' + name)
    for source in receipt.get('source_files', []):
        path = Path(source['path'])
        if not path.is_file() or file_digest(path) != source['sha256']:
            errors.append('Input version changed or missing: ' + path.name)
    core = receipt.get('core_delivery')
    if core:
        checked = verify_delivery_files(core['directory'], presented_files=core['present_files'], expected_manifest_sha256=core['manifest_sha256'])
        if checked['status'] != 'verified':
            errors.append('Core delivery is not verified.')
    return {'status': 'verified' if not errors else 'incomplete', 'errors': errors,
            'scope': 'Actual Toolkit files/input versions and the original Core delivery receipt; not experimental authentication.',
            'receipt_sha256': file_digest(receipt_path)}


def run(kit, request_path, context_path, out_dir, *, trace_mode='normal', trace_dir=None, language='zh'):
    with language_scope(language):
        return _run(kit, request_path, context_path, out_dir, trace_mode=trace_mode, trace_dir=trace_dir)


def _run(kit, request_path, context_path, out_dir, *, trace_mode='normal', trace_dir=None):
    if kit not in FIELDS:
        raise ValueError('Choose construct, identity, evidence or crispr.')
    request_sha256 = file_digest(request_path)
    request = read_json(request_path)
    if file_digest(request_path) != request_sha256:
        raise ValueError('Request file changed while loading; reload its current content.')
    unknown = set(request) - FIELDS[kit] - COMMON
    if unknown:
        raise ValueError('Unsupported ' + kit + ' fields: ' + ', '.join(sorted(unknown)))
    if request.get('kit', kit) != kit or not isinstance(request.get('original_request'), str) or not request['original_request'].strip():
        raise ValueError('Provide the original_request and a matching Kit.')
    if request.get('title') is not None and (not isinstance(request['title'], str) or not request['title'].strip()):
        raise ValueError('title must be nonempty text when provided.')
    request['kit'] = kit
    context = ProjectContext.load(context_path)
    out = Path(out_dir).resolve()
    invocation = uuid.uuid4().hex
    try:
        level = get_level()
    except (OSError, ValueError):
        level = 'unknown'
    if trace_mode == 'strict' and level == 'off':
        raise TraceStopped('Trace is Off; strict recording cannot be satisfied.')
    bundle = make_trace_bundle(request, context, invocation, request_path, selected_references(kit, request, context)) if level in ('observed', 'full') else None
    result = execute(request, context, out, invocation, str(Path(request_path).resolve()),
                     trace_input=bundle, trace_dir=trace_dir, trace_mode=trace_mode)
    from revival.reporting import finish_trace
    trace = finish_trace(out, Path(trace_dir).resolve() if trace_dir else out / 'evidence-trace', result, level, trace_mode)
    source_files = [{'path': str(Path(request_path).resolve()), 'sha256': request_sha256},
                    {'path': str(Path(context_path).resolve()), 'sha256': context.context_file_sha256}]
    source_files.extend({'path': row['path'], 'sha256': row['file_sha256']} for row in result['context']['references'])
    source_files.extend({'path': row['path'], 'sha256': row['sha256']} for row in result.get('input_files', []))
    receipt = {'schema_version': 'toolkit-files-v1', 'invocation': invocation, 'domain_status': result['status'],
               'files': {Path(p).resolve().relative_to(out).as_posix(): file_digest(p) for p in result['result_files']},
               'source_files': source_files, 'core_delivery': result.get('delivery'), 'trace': trace,
               'scope': 'Supporting report/input versions; Core remains the DNA correctness authority.'}
    receipt_path = out / 'TOOLKIT-RECEIPT.json'
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8', errors='replace')
    checked = verify_outputs(out, file_digest(receipt_path))
    return {'kit': kit, 'status': result['status'], 'summary': result['summary'], 'checked_scope': result['checked_scope'],
            'present_files': result['present_files'], 'technical_record': str(out / 'result.json'),
            'receipt': str(receipt_path), 'receipt_sha256': file_digest(receipt_path), 'file_check': checked,
            'trace': trace, 'toolkit_version': __version__, 'core_version': CORE_VERSION}
