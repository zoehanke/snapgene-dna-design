"""Readable object details. Raw records remain in the machine result, never drawers."""
from evidence_trace.localization import tr, display
from pathlib import Path

ROLES = {'authoritative': '正式产物', 'intermediate-or-candidate': '中间或候选产物',
         'derived': '衍生文件', 'document': '说明文档', 'qc': '验证设计', 'preview': '预览文件',
         'supporting-file': '配套记录文件'}
CHECKS = {'artifact_valid': '文件可读取且符合文件契约', 'computation_valid': '计算过程一致性',
          'biological_sanity': '序列与注释检查', 'requested_components': '请求的元件检查', 'goal_valid': '用户目标检查',
          'goal_satisfied': '用户目标检查', 'goal_check': '用户目标检查', 'sanity': '序列与注释检查',
          'sequence_model': '产物序列与实际输入一致', 'preparation_model': '实际计算制备链检查',
          'file': '当前交付文件回读检查', 'user_goal': '已声明目标核对',
          'primer_amplification': '完整引物PCR计算检查', 'junction_pcr_design': '构建接口PCR方案检查',
          'verification_design': '给定模板的验证方案检查'}
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
        return tr('通过本项程序检查')
    if value is False or value in ('FAIL', 'FAILED', 'failed'):
        return tr('本项程序检查未通过')
    if value in ('not_requested', 'N/A', 'not_applicable'):
        return tr('本项未请求或不适用，未作通过判断')
    return str(value) if isinstance(value, (str, int, float)) else tr('结果需查看技术记录')


def handoff_text(item):
    return {'linked': tr('已关联生成记录'), 'untraced': tr('交付时文件存在，但未采集生成过程；这项观察不判断文件是否符合设计要求'),
            'missing': tr('交付时未找到文件'), 'changed': tr('文件与已记录版本不同，需要重新核对'),
            'ambiguous': tr('存在多个匹配生成记录，尚未确定本次交付对应哪一次')}[item['status']]


def readable_details(records):
    result = {}
    for ref, raw in records.items():
        record = raw.get('payload', {}) if raw.get('event_type') == 'node_recorded' else raw
        kind = record.get('kind', 'event')
        title = record.get('title') or record.get('text') or display(CHECKS, record.get('check'), record.get('check'))
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
            field(tr('要求'), record.get('text'))
            form = record.get('requirement_source', {}).get('form')
            field(tr('记录方式'), tr('用户原话') if form == 'verbatim' else tr('提交的要求摘要，原话身份未核实'))
            refs(tr('原始请求'), record.get('observed_quote_ref'))
        elif kind == 'decision':
            field(tr('作出的选择'), record.get('text'))
            who = record.get('decision_actor')
            field(tr('选择者'), 'AI' if who in {'ai', 'assistant', 'host-assistant', 'model'} else
                  tr('用户') if who in {'user', 'human', 'researcher'} else tr('未记录'))
            field(display(ORIGINS, record.get('explanation_origin'), tr('已提交的公开说明，发生时间未核实')), record.get('rationale'))
            refs(tr('依据'), record.get('basis_refs'))
        elif kind in {'source', 'statement', 'claim'}:
            field({'source': tr('来源'), 'statement': tr('来源报告的内容'), 'claim': tr('当前任务中的判断')}[kind], title)
            field(tr('相关片段'), record.get('excerpt'))
            locator = record.get('locator') or record.get('verification', {}).get('locator')
            if isinstance(locator, str) and not locator.lower().startswith(('sha256', 'sha-256')):
                field(tr('定位'), locator)
            if kind == 'source':
                field(tr('来源核对'), tr('已核对来源；不代表其适用于当前设计') if record.get('verification_status') == 'verified'
                      else tr('来源核对尚无已验证记录'))
            for label, key in [(tr('适用条件'), 'conditions'), (tr('适用边界'), 'limitations')]:
                values = record.get(key, [])
                for value in values if isinstance(values, list) else [values]:
                    field(label, value)
        elif kind == 'validation':
            title = display(CHECKS, record.get('check'), record.get('check', tr('程序检查')))
            field(tr('结果'), result_text(record.get('result')))
            scope = record.get('scope')
            field(tr('范围'), display(CHECKS, scope, scope) or tr('仅对应原程序本项检查；同次运行不等于逐项验证每个设计选择'))
            details = record.get('details', {})
            if isinstance(details, dict):
                table = details.get('guardrail_status_table', {})
                for row in table.values() if isinstance(table, dict) else table:
                    field(row.get('title', tr('检查项')), result_text(row.get('status')) + '；' + str(row.get('details', '')))
                for key, label in [('message', tr('检查说明')), ('scope', tr('检查范围')), ('path', tr('检查对象'))]:
                    value = details.get(key)
                    field(label, display(CHECKS, value, value) if key == 'scope' and isinstance(value, str) else value)
                for key in ('errors', 'warnings'):
                    values = details.get(key, [])
                    for value in values if isinstance(values, list) else [values]:
                        field(tr('检查发现'), value if isinstance(value, str) else value.get('message') if isinstance(value, dict) else None)
            refs(tr('实际程序返回'), record.get('result_event_ref'))
        elif kind == 'artifact':
            title = filename(record.get('path'))
            if record.get('role'):
                field(tr('文件身份'), display(ROLES, record['role'], record['role']))
            field(tr('用途'), record.get('purpose'))
            field(tr('生成记录'), {'created': tr('调用期间新建'), 'modified': tr('调用期间修改'),
                             'rewritten_same_content': tr('本次受观察的写入已返回，文件内容同原版本；不是新DNA序列'),
                             'presence_only': tr('只观察到文件存在，没有证明生成过程')}.get(record.get('generation_observation')))
            for item in record.get('input_files', []):
                field(tr('输入材料'), filename(item.get('path')))
            refs(tr('生成动作'), record.get('result_event_ref'))
            refs(tr('来源材料'), record.get('input_artifact_refs'))
            refs(tr('同次运行的检查（范围分别查看）'), record.get('validated_by'))
            path = Path(record.get('path', ''))
            if path.is_file():
                links.append({'label': tr('打开文件'), 'href': path.resolve().as_uri()})
            else:
                field(tr('文件位置'), tr('当前无法在原位置打开；请核对是否移动或未随报告提供'))
        else:
            payload = record.get('payload', {})
            event = record.get('event_type', '')
            title = display(STAGES, payload.get('stage'), payload.get('stage')) or tr('采集记录')
            if event == 'material_observed':
                title = filename(payload.get('path')) or tr('提交的原文材料')
                field(tr('已采集内容'), payload.get('text'))
                field(tr('材料来源'), tr('从本地文件读取') if payload.get('kind') == 'local_text' else tr('宿主主动提交'))
            elif event.endswith('_failed'):
                field(tr('执行失败'), payload.get('error'))
            elif event in {'stage_completed', 'file_operation_completed'}:
                field(tr('发生了什么'), tr('程序调用已返回。调用成功本身不代表生物学验证通过。'))
                for item in payload.get('before', []):
                    field(tr('输入或原文件'), filename(item.get('path')))
                for item in payload.get('after', []):
                    field(tr('返回后的文件'), filename(item.get('path')))
                value = payload.get('result', {})
                if isinstance(value, dict):
                    for key, label in [('message', tr('返回说明')), ('sequence_length', tr('序列长度（bp）')),
                                       ('file_name', tr('检查文件')), ('topology', tr('拓扑'))]:
                        field(label, value.get(key))
            else:
                field(tr('记录内容'), tr('此记录属于技术过程；完整输入、返回和历史保留在技术文件中'))
            refs(tr('对应调用'), payload.get('stage_ref'))
        for label, values in record.get('references', {}).items():
            refs({'source_id': tr('原始来源'), 'claim_ids': tr('相关判断'), 'responds_to': tr('对应用户要求')}.get(label, tr('关联记录')), values)
        uri = record.get('url') or record.get('source_uri') or record.get('locator') or record.get('verification', {}).get('locator')
        if isinstance(uri, str) and uri.startswith(('https://', 'http://')):
            links.append({'label': tr('打开原始来源'), 'href': uri})
        label = {'requirement': tr('用户要求'), 'decision': tr('设计选择'), 'validation': tr('程序检查'),
                 'artifact': tr('文件'), 'source': tr('来源'), 'statement': tr('证据内容'), 'claim': tr('任务判断')}.get(kind, tr('程序记录'))
        result[ref] = {'title': title or label, 'label': (title or label), 'kind': kind,
                       'type_label': label, 'fields': fields, 'related': related, 'links': links, 'evidence': []}
    return result


def applicability_text(assessment):
    labels = {'organism': tr('物种'), 'strain': tr('菌株'), 'host': tr('宿主'), 'construct_context': tr('构建背景'),
              'temperature': tr('温度'), 'medium': tr('培养基'), 'assay': tr('检测方法'), 'intended_use': tr('用途')}
    reason = assessment.get('reason', '')
    for key, label in labels.items():
        reason = reason.replace(key, label)
    return reason
