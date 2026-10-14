"""Common project result layout; Kit owns scope and comparison semantics."""
from pathlib import Path
from evidence_trace.localization import tr

def summary(result, context_snapshot, request, metadata, format_comparison=None):
    text = lambda value: str(value).replace('<', '&lt;').replace('>', '&gt;')

    lines = ['# ' + text(request.get('title', tr('Genome Revival Toolkit 结果'))), '',
             tr('## 我们要完成什么？'), '', text(request['original_request']), '',
             tr('## 本次得到了什么？'), '', text(result.get('report_summary', result.get('summary', result.get('error', tr('当前任务未完成。'))))), '',
             tr('状态：') + {'delivered': tr('当前正式文件已核查'), 'analysed': tr('已完成所述范围内的分析'), 'incomplete': tr('尚未完成'), 'failed': tr('本次未完成')}.get(result['status'], text(result['status'])), '', tr('## 使用了哪些实际材料？'), '']
    for reference in context_snapshot.get('references', []):
        lines.append(('- ' + str(text(reference['id'])) + tr('：') + str(reference['length_bp']) + ' bp; ' + str(text(reference['region'] or tr('完整所选记录'))) + str(tr('。声明菌株身份与实际参考文件核对分开。'))))
    lines.extend(['', tr('## 程序确认了什么？'), '', tr(metadata['scope']), ''])
    for comparison in result.get('comparisons', []):
        lines.append(format_comparison(comparison,text))
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
    limitations = [tr(value) for value in metadata['limits']]
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
