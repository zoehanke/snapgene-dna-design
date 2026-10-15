"""Given-reference discrimination, using Core alignment and exact PCR simulation."""
from __future__ import annotations

from itertools import combinations

from core.tools.comparison import compare_sequences
from core.tools.amplification import simulate_pcr, design_overhang_primers
from core.tools.primer3_backend import check_complete_oligo_pair, Primer3CoreError
from core.tools.result import to_wire
from evidence_trace.runtime import observe, observe_files
from revival import __version__


def _discrimination(predictions, size_resolution_bp):
    states = [row['prediction'] for row in predictions]
    if any(state in ('AMBIGUOUS', 'UNKNOWN') for state in states):
        return {'status': 'UNKNOWN', 'basis': 'Some provided references could not be resolved.'}
    if len(states) < 2:
        return {'status': 'NOT_CHECKED', 'basis': 'Only one reference was provided.'}
    lengths = [row.get('amplicon_length_bp') for row in predictions]
    if len(set(states)) > 1:
        return {'status': 'PREDICTED_DIFFERENT', 'basis': 'Exact binding predicts presence/absence differences in the supplied references.'}
    if len(set(lengths)) == 1:
        return {'status': 'NOT_DISCRIMINATING', 'basis': 'The supplied references have the same predicted band state and length.'}
    differences = [abs(a - b) for a, b in combinations(lengths, 2) if a is not None and b is not None]
    if size_resolution_bp is None:
        return {'status': 'NEEDS_REVIEW', 'basis': 'Product sizes differ; assay size resolution was not specified.',
                'minimum_size_difference_bp': min(differences) if differences else None}
    distinct = len(set(lengths)) == len(lengths) and differences and min(differences) >= size_resolution_bp
    return {'status': 'PREDICTED_DIFFERENT' if distinct else 'NOT_DISCRIMINATING',
            'basis': 'Size comparison under the submitted assay resolution, not observed gel separation.',
            'size_resolution_bp': size_resolution_bp, 'minimum_size_difference_bp': min(differences) if differences else None}


def run_identity(request, context, out_dir):
    ids = request.get('references', list(context.references))
    if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
        raise ValueError('identity.references needs a nonempty list of distinct context reference IDs.')
    materials = context.materials(ids)
    references = [context.reference_info(key) for key in ids]
    imported=None
    if 'construct_handoff_file' in request:
        from pathlib import Path
        from .handoff import read_construct_handoff
        path=Path(context.base_dir)/request['construct_handoff_file']
        imported=observe_files('identity.import_construct_handoff',read_construct_handoff,args=(path,context,ids),
            input_paths=[path,*[context.references[key]['path'] for key in ids]],output_paths=lambda _:())
    if 'export_expectations' in request and type(request['export_expectations']) is not bool:
        raise ValueError('export_expectations must be a boolean.')
    comparisons = []
    if request.get('compare_regions', True):
        for left, right in combinations(ids, 2):
            result = observe('identity.compare_regions', compare_sequences, materials[left], materials[right],
                             mode=request.get('alignment_mode', 'global'))
            comparisons.append({'query': left, 'reference': right, 'analysis': to_wire(result.analysis)})
    assays = request.get('assays', [])
    if not isinstance(assays, list):
        raise ValueError('identity.assays must be a list.')
    assays = list(assays)
    if imported:assays.extend(imported['assays'])
    for design in request.get('design_assays', []):
        if not isinstance(design, dict) or design.get('target_reference') not in materials:
            raise ValueError('design_assays requires a supplied target_reference.')
        interval = design.get('interval', {})
        template = materials[design['target_reference']]
        if not isinstance(interval, dict) or any(type(interval.get(k)) is not int for k in ('start0', 'end0')):
            raise ValueError('Assay interval needs integer start0/end0 on the selected reference.')
        if not 0 <= interval['start0'] < interval['end0'] <= len(template):
            raise ValueError('Assay interval lies outside the selected reference.')
        result = observe('identity.design_primers', design_overhang_primers, template,
                         interval['start0'], interval['end0'], target_tm=design.get('target_tm', 60.0))
        assays.append({'id': design.get('id'),
                       'forward': result.analysis['forward_primer']['full_sequence'],
                       'reverse': result.analysis['reverse_primer']['full_sequence'],
                       'size_resolution_bp': design.get('size_resolution_bp'),
                       'annealing_temperature_C': design.get('annealing_temperature_C'),
                       'expected': design.get('expected', {}),
                       'design': {'target_reference': design['target_reference'], 'interval': interval,
                                  'template_version': template.record_version, 'analysis': to_wire(result.analysis)}})
    assay_ids = set()
    analysed = []
    checks = []
    for assay in assays:
        if not isinstance(assay, dict) or not isinstance(assay.get('id'), str) or not assay['id'].strip():
            raise ValueError('Each assay needs a nonempty id.')
        if assay['id'] in assay_ids:
            raise ValueError('Assay IDs must be unique.')
        assay_ids.add(assay['id'])
        forward, reverse = assay.get('forward'), assay.get('reverse')
        if not all(isinstance(p, str) and len(p.strip()) >= 15 for p in (forward, reverse)):
            raise ValueError(f"Assay {assay['id']}: submit complete forward/reverse oligos of at least 15 bases.")
        forward, reverse = forward.strip().upper(), reverse.strip().upper()
        if set(forward + reverse) - set('ACGT'):
            raise ValueError('This exact-PCR workflow requires concrete A/C/G/T oligos; degenerate binding is not inferred.')
        resolution = assay.get('size_resolution_bp')
        if resolution is not None and (type(resolution) is not int or resolution <= 0):
            raise ValueError('size_resolution_bp must be a positive integer when specified.')
        temperature = assay.get('annealing_temperature_C')
        if temperature is not None and (type(temperature) not in (int, float) or not 0 < temperature < 100):
            raise ValueError('annealing_temperature_C must be finite and between 0 and 100.')
        try:
            quality = observe('identity.complete_oligo_quality', check_complete_oligo_pair,
                              forward, reverse, annealing_temperature=temperature, primer_method='pcr')
            quality_status = 'PASSED' if quality['passed'] else 'FAILED'
        except Primer3CoreError as exc:
            quality, quality_status = {'error': str(exc), 'status': getattr(exc, 'code', 'BACKEND_UNAVAILABLE')}, 'INCOMPLETE'
        predictions = []
        for key, template in materials.items():
            try:
                result = observe('identity.simulate_pcr', simulate_pcr, template, forward, reverse,
                                 forward_binding_core_length=assay.get('forward_binding_core_length', len(forward)),
                                 reverse_binding_core_length=assay.get('reverse_binding_core_length', len(reverse)))
                product = result.only_product()
                prediction = {'reference': key, 'prediction': 'AMPLICON', 'amplicon_length_bp': len(product),
                              'template_version': template.record_version, 'product_version': product.record_version,
                              'analysis': to_wire(result.analysis), 'checks': result.checks}
            except ValueError as exc:
                message = str(exc)
                state = 'NO_EXACT_PRODUCT' if 'has no binding site' in message or 'do not face each other' in message else (
                    'AMBIGUOUS' if 'ambigu' in message.lower() or 'multiple' in message.lower() else 'UNKNOWN')
                prediction = {'reference': key, 'prediction': state, 'template_version': template.record_version,
                              'reason': message}
            predictions.append(prediction)
        expected = assay.get('expected', {})
        if not isinstance(expected, dict) or set(expected) - set(materials) or any(v not in ('AMPLICON', 'NO_EXACT_PRODUCT') for v in expected.values()):
            raise ValueError('assay.expected maps supplied reference IDs to AMPLICON or NO_EXACT_PRODUCT.')
        mismatches = [row['reference'] for row in predictions if row['reference'] in expected and row['prediction'] != expected[row['reference']]]
        discrimination = _discrimination(predictions, resolution)
        status = 'FAILED' if mismatches or quality_status == 'FAILED' else (
            'INCOMPLETE' if quality_status != 'PASSED' or any(row['prediction'] in ('AMBIGUOUS', 'UNKNOWN') for row in predictions) else 'PASSED')
        checks.append({'name': f"Assay {assay['id']}", 'status': status,
                       'tool': 'genome-revival-toolkit', 'tool_version': __version__,
                       'scope': 'Exact PCR and complete-oligo quality on the supplied references and conditions only.',
                       'details': {'expected_mismatches': mismatches, 'quality_status': quality_status}})
        analysed.append({'id': assay['id'], 'forward': forward, 'reverse': reverse, 'quality': quality,
                         'quality_status': quality_status, 'predictions': predictions, 'discrimination': discrimination})
        if assay.get('design'):
            analysed[-1]['design'] = assay['design']
    if not comparisons and not analysed:
        status = 'incomplete'
    else:
        status = 'analysed' if all(row['status'] == 'PASSED' for row in checks) else 'incomplete'
    descriptions = []
    for assay in analysed:
        predicted = ' / '.join(str(row['amplicon_length_bp']) + ' bp' if row.get('amplicon_length_bp') else row['prediction'] for row in assay['predictions'])
        verdict = {'PREDICTED_DIFFERENT': '在所给参考中预测可区分', 'NOT_DISCRIMINATING': '该方案不能区分所给参考',
                   'NEEDS_REVIEW': '分辨率条件待确认', 'UNKNOWN': '存在未解决的扩增预测', 'NOT_CHECKED': '未进行多背景鉴别'}[assay['discrimination']['status']]
        quality = {'PASSED': '完整引物质量通过', 'FAILED': '完整引物质量未通过', 'INCOMPLETE': '完整引物质量未完成'}[assay['quality_status']]
        descriptions.append(f"{assay['id']}：{predicted}，{verdict}，{quality}。")
    summary = f'已比较{len(materials)}份实际参考中的给定区域。' + (' '.join(descriptions) if descriptions else '本次仅有区域比对，未提供或生成检测候选。')
    result = {'kit': 'identity', 'status': status, 'references': references, 'comparisons': comparisons,
            'assays': analysed, 'checks': checks,
            'summary': summary,
            'checked_scope': 'Only selected input records/regions. Alignment is not unique-placement evidence; negative PCR is a prediction under exact binding.',
            'unverified': ['Whole-genome specificity outside the supplied references.', 'Actual PCR performance and genotype observations.',
                           'Whole-host-genome elimination or donor-genome functional revival.']}
    if imported:result['input_files']=[imported['input_file']]
    if request.get('export_expectations'):
        from .handoff import expectation_table
        result['expected_results']=expectation_table(analysed,references)
    return result
