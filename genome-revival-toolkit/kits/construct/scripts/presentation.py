"""Kit-owned presentation; original evidence/values are preserved."""
from pathlib import Path
from evidence_trace.localization import tr, get_language
from kits.shared.summary import summary as shared_summary

def summary(result,context_snapshot,request,metadata):
    return shared_summary(result,context_snapshot,request,metadata)

def fact_text(record):
    payload=record["payload"];value=payload.get("result",{})
    if payload.get('stage')=='construct.identity_handoff':
        return 'Exported actual completed donor-QC primer candidates and a version-bound Identity request. The supplied references are models, not observed genotypes.'
    if payload.get('stage') == 'construct.model' and isinstance(value, list) and (len(value) == 2):
        model = value[1]
        if isinstance(model, dict):
            length = model.get('product', {}).get('expected_length')
            if length is not None:
                return str(tr('按明确的参考位点、左右同源臂和标记边界，核对预期 ')) + str(length) + str(tr(' bp 线性供体。这里只建立序列与注释模型，实际制备在后续步骤执行。'))
    if isinstance(value,dict):
        if value.get("summary"):return None
        method=value.get("method");returned=value.get("result",{})
        analysis=returned.get("analysis",{}) if isinstance(returned,dict) else {}
        if method in ('prepare_pcr_fragment', 'recipe_gibson_assembly') and value.get('status') == 'completed':
            products = returned.get('products', [])
            sequence = products[0].get('sequence') if len(products) == 1 else None
            length = sequence.get('length') if isinstance(sequence, dict) else len(sequence) if isinstance(sequence, str) else None
            if length is not None:
                route = tr('由完整模板和本次引物计算得到') if method == 'prepare_pcr_fragment' else tr('由实际PCR片段计算组装得到')
                return str(route) + ' ' + str(length) + str(tr(' bp 供体候选。完整引物、条件及结构质量另行检查；计算产物不等于实际实验成功。'))
        if method == 'recipe_cloning_verification' and value.get('status') == 'completed':
            details = analysis.get('details', {})
            length = details.get('junction_pcr_primers', {}).get('expected_amplicon_size_bp')
            if length is not None:
                backgrounds = details.get('parental_pcr', {}).get('templates', [])
                background_text = tr('在本次给定背景参考中未预测产物') if backgrounds and all((row.get('status') == 'NO_PRODUCT_PREDICTED' for row in backgrounds)) else tr('给定背景也有预测产物，需要结合具体长度区分') if any((row.get('status') == 'PRODUCT_PREDICTED' for row in backgrounds)) else tr('背景鉴别尚未完整核查')
                return str(tr('当前供体的该接口PCR预测为 ')) + str(length) + ' bp；' + str(background_text) + str(tr('。这是给定序列上的计算方案，不是实测PCR或全基因组特异性结论。'))
        if payload.get('stage') == 'construct.delivery' and value.get('status') == 'delivered':
            scopes = value.get('validation', {}).get('scope_results', {})
            if all((scopes.get(name, {}).get('status') == 'PASSED' for name in ('sequence_model', 'preparation_model', 'file', 'user_goal'))):
                return tr('当前正式文件已回读，供体序列、计算制备链、实际文件和已声明目标四项核查通过。该结论不包括实际整合、表达或基因组复活。')
        if payload.get('stage') == 'construct.delivery_receipt' and value.get('status') == 'verified':
            return tr('真正选择交付的文件与本次受检版本一致。回执核对文件归属及完整性，不重新下生物学结论。')
        if payload.get('stage') in ('construct.reference', 'construct.cargo', 'construct.donor_template'):
            sequence = value.get('sequence')
            if isinstance(sequence, dict) and sequence.get('length') is not None:
                return str(tr('读取本次选定的 ')) + str(sequence['length']) + str(tr(' bp 序列记录，供后续来源和边界核对。文件存在与版本核对不等于实际菌株身份认证。'))
    return None
