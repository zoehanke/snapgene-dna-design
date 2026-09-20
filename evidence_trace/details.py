"""Readable object details. Raw records remain in the machine result, never drawers."""
from pathlib import Path

ROLES = {'authoritative': '正式产物', 'intermediate-or-candidate': '中间或候选产物',
         'derived': '衍生文件', 'document': '说明文档', 'qc': '验证设计', 'preview': '预览文件'}
CHECKS = {'artifact_valid': '文件可读取且符合文件契约', 'computation_valid': '计算过程一致性',
          'biological_sanity': '序列与注释检查', 'requested_components': '请求的元件检查', 'goal_valid': '用户目标检查',
          'goal_satisfied': '用户目标检查', 'goal_check': '用户目标检查', 'sanity': '序列与注释检查'}
STAGES = {'inspect': '检查材料', 'recipe_execute': '执行构建方案', 'preparation': '导出制备材料与引物',
          'annotate_primers': '标注引物', 'convert': '转换格式', 'finalize': '正式交付',
          'execute': '执行设计', 'validate': '检查设计', 'plan': '生成执行方案',
          'sanity': '检查序列与注释', 'goal_check': '核对用户目标'}
ORIGINS = {'ai_concurrent': 'AI 同期公开说明（提交者声明）', 'user_provided': '用户说明',
           'user_statement': '用户说明',
           'post_hoc': '事后补充', 'retrospective': '事后补充',
           'original_statement': '原始公开说明', 'organized_summary': '根据记录整理',
           'later_interpretation': '后来补充解释'}


def filename(value):
    return str(value or '').replace('\\', '/').rsplit('/', 1)[-1]


def result_text(value):
    if value is True or value in ('PASS', 'PASSED', 'passed'):
        return '通过本项程序检查'
    if value is False or value in ('FAIL', 'FAILED', 'failed'):
        return '本项程序检查未通过'
    if value in ('not_requested', 'N/A', 'not_applicable'):
        return '本项未请求或不适用，未作通过判断'
    return str(value) if isinstance(value, (str, int, float)) else '结果需查看技术记录'


def handoff_text(item):
    return {'linked': '已关联生成记录', 'untraced': '文件存在，但未采集生成过程；可使用文件，无法回溯其生成步骤',
            'missing': '交付时未找到文件', 'changed': '文件与已记录版本不同，需要重新核对',
            'ambiguous': '存在多个匹配生成记录，尚未确定本次交付对应哪一次'}[item['status']]


def readable_details(records):
    result = {}
    for ref, raw in records.items():
        record = raw.get('payload', {}) if raw.get('event_type') == 'node_recorded' else raw
        kind = record.get('kind', 'event')
        title = record.get('title') or record.get('text') or CHECKS.get(record.get('check'), record.get('check'))
        fields, related = [], []
        def field(label, value):
            if isinstance(value, (str, int, float)) and not isinstance(value, bool) and str(value).strip():
                fields.append({'label': label, 'text': str(value)})
        def refs(label, values):
            if isinstance(values, str):
                values = [values]
            for value in values or []:
                if value in records and value != ref:
                    related.append({'label': label, 'ref': value})
        links = []
        if kind == 'requirement':
            field('要求', record.get('text'))
            form = record.get('requirement_source', {}).get('form')
            field('记录方式', '用户原话' if form == 'verbatim' else '提交的要求摘要，原话身份未核实')
            refs('原始请求', record.get('observed_quote_ref'))
        elif kind == 'decision':
            field('作出的选择', record.get('text'))
            who = record.get('decision_actor')
            field('选择者', 'AI' if who in {'ai', 'assistant', 'host-assistant', 'model'} else
                  '用户' if who in {'user', 'human', 'researcher'} else '未记录')
            field(ORIGINS.get(record.get('explanation_origin'), '已提交的公开说明，发生时间未核实'), record.get('rationale'))
            refs('依据', record.get('basis_refs'))
        elif kind in {'source', 'statement', 'claim'}:
            field({'source': '来源', 'statement': '来源报告的内容', 'claim': '当前任务中的判断'}[kind], title)
            field('相关片段', record.get('excerpt'))
            locator = record.get('locator')
            if isinstance(locator, str) and not locator.lower().startswith(('sha256', 'sha-256')):
                field('定位', locator)
            if kind == 'source':
                field('来源核对', '已核对来源；不代表其适用于当前设计' if record.get('verification_status') == 'verified'
                      else '来源核对尚无已验证记录')
            for label, key in [('适用条件', 'conditions'), ('适用边界', 'limitations')]:
                values = record.get(key, [])
                for value in values if isinstance(values, list) else [values]:
                    field(label, value)
        elif kind == 'validation':
            title = CHECKS.get(record.get('check'), record.get('check', '程序检查'))
            field('结果', result_text(record.get('result')))
            field('范围', record.get('scope') or '仅对应原程序本项检查；同次运行不等于逐项验证每个设计选择')
            details = record.get('details', {})
            if isinstance(details, dict):
                table = details.get('guardrail_status_table', {})
                for row in table.values() if isinstance(table, dict) else table:
                    field(row.get('title', '检查项'), result_text(row.get('status')) + '；' + str(row.get('details', '')))
                for key, label in [('message', '检查说明'), ('scope', '检查范围'), ('path', '检查对象')]:
                    field(label, details.get(key))
                for key in ('errors', 'warnings'):
                    values = details.get(key, [])
                    for value in values if isinstance(values, list) else [values]:
                        field('检查发现', value if isinstance(value, str) else value.get('message') if isinstance(value, dict) else None)
            refs('实际程序返回', record.get('result_event_ref'))
        elif kind == 'artifact':
            title = filename(record.get('path'))
            if record.get('role'):
                field('文件身份', ROLES.get(record['role'], record['role']))
            field('用途', record.get('purpose'))
            field('生成记录', {'created': '调用期间新建', 'modified': '调用期间修改',
                             'presence_only': '只观察到文件存在，没有证明生成过程'}.get(record.get('generation_observation')))
            for item in record.get('input_files', []):
                field('输入材料', filename(item.get('path')))
            refs('生成动作', record.get('result_event_ref'))
            refs('来源材料', record.get('input_artifact_refs'))
            refs('同次运行的检查（范围分别查看）', record.get('validated_by'))
            path = Path(record.get('path', ''))
            if path.is_file():
                links.append({'label': '打开文件', 'href': path.resolve().as_uri()})
            else:
                field('文件位置', '当前无法在原位置打开；请核对是否移动或未随报告提供')
        else:
            payload = record.get('payload', {})
            event = record.get('event_type', '')
            title = STAGES.get(payload.get('stage'), payload.get('stage')) or '采集记录'
            if event == 'material_observed':
                title = filename(payload.get('path')) or '提交的原文材料'
                field('已采集内容', payload.get('text'))
                field('材料来源', '从本地文件读取' if payload.get('kind') == 'local_text' else '宿主主动提交')
            elif event.endswith('_failed'):
                field('执行失败', payload.get('error'))
            elif event in {'stage_completed', 'file_operation_completed'}:
                field('发生了什么', '程序调用已返回。调用成功本身不代表生物学验证通过。')
                for item in payload.get('before', []):
                    field('输入或原文件', filename(item.get('path')))
                for item in payload.get('after', []):
                    field('返回后的文件', filename(item.get('path')))
                value = payload.get('result', {})
                if isinstance(value, dict):
                    for key, label in [('message', '返回说明'), ('sequence_length', '序列长度（bp）'),
                                       ('file_name', '检查文件'), ('topology', '拓扑')]:
                        field(label, value.get(key))
            else:
                field('记录内容', '此记录属于技术过程；完整输入、返回和历史保留在技术文件中')
            refs('对应调用', payload.get('stage_ref'))
        for label, values in record.get('references', {}).items():
            refs({'source_id': '原始来源', 'claim_ids': '相关判断', 'responds_to': '对应用户要求'}.get(label, '关联记录'), values)
        uri = record.get('url') or record.get('source_uri') or record.get('locator')
        if isinstance(uri, str) and uri.startswith(('https://', 'http://')):
            links.append({'label': '打开原始来源', 'href': uri})
        label = {'requirement': '用户要求', 'decision': '设计选择', 'validation': '程序检查',
                 'artifact': '文件', 'source': '来源', 'statement': '证据内容', 'claim': '任务判断'}.get(kind, '程序记录')
        result[ref] = {'title': title or label, 'label': (title or label), 'kind': kind,
                       'type_label': label, 'fields': fields, 'related': related, 'links': links}
    return result


def applicability_text(assessment):
    labels = {'organism': '物种', 'strain': '菌株', 'host': '宿主', 'construct_context': '构建背景',
              'temperature': '温度', 'medium': '培养基', 'assay': '检测方法', 'intended_use': '用途'}
    reason = assessment.get('reason', '')
    for key, label in labels.items():
        reason = reason.replace(key, label)
    return reason
