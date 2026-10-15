"""Bounded donor preparation and donor QC using the shared DNA Core."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile

from revival.bootstrap import CORE_VERSION
from revival.context import ProjectContext
from core import plan
from core.runtime_gate import verify_delivery_files
from core.tools import export_snapgene
from core.tools.result import to_wire
from core.workflow import run_step
from core.workflow_delivery import deliver_result
from evidence_trace.runtime import observe, observe_value, observe_files, TraceStopped


def _interval(value, length, name, *, allow_empty=False):
    if not isinstance(value, dict) or any(type(value.get(key)) is not int for key in ('start0', 'end0')):
        raise ValueError(f'{name}: provide integer start0/end0, 0-based half-open on the selected record.')
    start, end = value['start0'], value['end0']
    if not 0 <= start <= end <= length or (start == end and not allow_empty):
        raise ValueError(f'{name}: outside the selected record or empty.')
    return start, end


def _save(path, value):
    path.write_text(json.dumps(to_wire(value), ensure_ascii=False, indent=2), encoding='utf-8', errors='replace')


def run_construct(request: dict, context: ProjectContext, out_dir: Path) -> dict:
    """Prepare a linear donor from explicit reference/cargo bounds; never infer a strain locus."""
    allowed = {'method', 'original_request', 'target_reference', 'cargo_reference', 'target_interval',
               'cargo_interval', 'arm_length', 'assembly_overlap_bp', 'preparation_method',
               'donor_template_reference', 'donor_interval', 'requirements', 'identity_handoff'}
    if not isinstance(request, dict):
        raise ValueError('Construct request must be an object.')
    unknown = set(request) - allowed
    if unknown:
        raise ValueError('Unsupported Construct fields: ' + ', '.join(sorted(unknown)))
    if 'identity_handoff' in request:
        from .handoff import validate_options
        validate_options(request['identity_handoff'],context)
    for field in ('original_request', 'target_reference', 'cargo_reference'):
        if not isinstance(request.get(field), str) or not request[field].strip():
            raise ValueError(f'{field}: provide the original request or actual reference ID.')
    if request.get('method') != 'integration_donor':
        raise ValueError('Construct v0.1 supports method integration_donor.')
    length = request.get('arm_length')
    if type(length) is not int or length <= 0:
        raise ValueError('arm_length: provide a positive integer; no default locus or arm length is assumed.')
    preparation = request.get('preparation_method', 'gibson')
    if preparation not in ('gibson', 'pcr'):
        raise ValueError('preparation_method must be gibson or pcr; failure never changes the requested method.')
    if preparation == 'pcr' and 'assembly_overlap_bp' in request:
        raise ValueError('assembly_overlap_bp applies to Gibson, not PCR preparation.')
    overlap = request.get('assembly_overlap_bp', 22)
    if type(overlap) is not int or not 15 <= overlap <= 35:
        raise ValueError('assembly_overlap_bp must be 15 to 35 bp, the existing Recipe supported range.')
    target_id, cargo_id = request['target_reference'], request['cargo_reference']
    if target_id == cargo_id:
        raise ValueError('Use distinct reference IDs for genomic target and cargo template, with explicit selected records.')
    reference = observe('construct.reference', context.material, target_id)
    cargo = observe('construct.cargo', context.material, cargo_id)
    if reference.topology != 'linear':
        raise ValueError('Construct v0.1 requires an explicitly linear selected genomic reference.')
    start, end = _interval(request.get('target_interval'), len(reference), 'target_interval', allow_empty=True)
    cargo_start, cargo_end = _interval(request.get('cargo_interval'), len(cargo), 'cargo_interval')
    if start < length or end + length > len(reference):
        raise ValueError('Insufficient supplied reference sequence for both declared homology arms.')
    sources = {target_id: reference, cargo_id: cargo}
    if preparation == 'pcr':
        donor_id = request.get('donor_template_reference')
        if not isinstance(donor_id, str) or not donor_id.strip():
            raise ValueError('PCR preparation requires the actual complete donor_template_reference.')
        donor = observe('construct.donor_template', context.material, donor_id)
        donor_start, donor_end = _interval(request.get('donor_interval'), len(donor), 'donor_interval')
        sources[donor_id] = donor
    elif 'donor_template_reference' in request or 'donor_interval' in request:
        raise ValueError('Donor-template PCR fields require preparation_method pcr; they cannot be silently ignored.')
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix='construct-', dir=out_dir))
    snapshots = run_dir / 'model_inputs'
    snapshots.mkdir()
    model_paths = {}
    for name, material, reference_id in (('target', reference, target_id), ('cargo', cargo, cargo_id)):
        entry = context.references[reference_id]
        # A file already representing the selected record needs no re-export.
        # In particular, unrelated legacy annotations elsewhere in a genomic
        # reference do not require native-file generation merely to read a locus.
        if entry.get('region') is None and not entry.get('record_id'):
            model_paths[name] = entry['path']
        else:
            saved = observe('construct.model_input', export_snapgene, material, snapshots, filename_base=name)
            model_paths[name] = saved.analysis['gb_file']
    model_task = {
        'schema_version': 'construction-task-v1', 'task_id': 'integration-donor-model', 'revision': 1,
        'mode': 'exploration', 'task_kind': 'integration_donor', 'raw_request': request['original_request'],
        'sources': [
            {'source_id': cargo_id, 'path': model_paths['cargo'], 'role': 'template',
             'topology': cargo.topology,
             'evidence': {'source_evidence_class': 'user-provided'}, 'annotation_status': 'unreviewed'},
            {'source_id': target_id, 'path': model_paths['target'], 'role': 'reference',
             'topology': reference.topology,
             'evidence': {'source_evidence_class': 'user-provided'}, 'annotation_status': 'unreviewed'}],
        'target': {'source_id': cargo_id, 'selection': {'kind': 'interval',
            'interval_0based': [cargo_start, cargo_end], 'resolution_status': 'resolved',
            'resolution_evidence': [{'kind': 'user-interval'}]}},
        'operation': {'locus': {'source_id': target_id, 'interval_0based': [start, end], 'strand': 1},
                      'homology_arms': {'arm_length': length}},
        'product': {'topology': 'linear', 'formats': ['gb', 'dna', 'fasta']}}
    model_task, model = observe('construct.model', plan, model_task)
    _save(run_dir / 'model_task.json', model_task)
    _save(run_dir / 'model_plan.json', model)
    requirements = copy.deepcopy(request.get('requirements', {}))
    if not isinstance(requirements, dict):
        raise ValueError('requirements must be an object.')
    if requirements.get('original_request', request['original_request']) != request['original_request']:
        raise ValueError('requirements.original_request conflicts with the submitted original request.')
    requirements.setdefault('original_request', request['original_request'])
    requirements.setdefault('topology', 'linear')
    requirements.setdefault('expected_sequence', model['product_sequence'])
    existing = requirements.get('expected_components', [])
    if not isinstance(existing, list):
        raise ValueError('requirements.expected_components must be an array.')
    requirements['expected_components'] = existing + [
        {'name': 'left_homology_arm', 'source_id': target_id, 'interval_0based': [start-length, start]},
        {'name': 'cargo', 'source_id': cargo_id, 'interval_0based': [cargo_start, cargo_end]},
        {'name': 'right_homology_arm', 'source_id': target_id, 'interval_0based': [end, end+length]}]
    requirements.setdefault('required_files', ['construct.gb', 'construct.dna', 'oligo_order_table.tsv', 'design.md'])
    steps = []
    observations = []

    def call(step_id, method, params):
        step = observe('construct.' + step_id, run_step, method, params, sources=sources,
                       step_id=step_id, requirements=requirements)
        steps.append(step)
        _save(run_dir / 'steps.json', {'sources': sources, 'requirements': requirements,
                                      'steps': [row.to_dict() for row in steps]})
        observations.append({'step': step_id, 'method': method, 'status': step.status,
                             'error': step.error, 'record_file': str(run_dir / 'steps.json')})
        return step

    def failure(step, reason=None):
        result = {'status': 'failed', 'kit': 'construct', 'method': 'integration_donor',
                  'core_version': CORE_VERSION, 'error': step.error or {'message': reason},
                  'summary': '当前候选未通过完整制备或验证，未生成正式交付。原目标和失败记录保留。',
                  'observations': observations, 'execution_record': str(run_dir / 'steps.json'),
                  'delivery': None, 'write_authoritative_artifact': False,
                  'scope': 'Explicit selected reference/cargo only; no strain or wet-lab certification.'}
        observe_value('construct.outcome', result)
        return result

    if preparation == 'pcr':
        build = call('donor_preparation', 'prepare_pcr_fragment',
                     {'template': sources[donor_id], 'start': donor_start, 'end': donor_end, 'name': 'donor'})
    else:
        build = call('donor_preparation', 'recipe_gibson_assembly',
                     {'fragments': [
                         {'id': 'left_arm', 'template': reference, 'start': start-length, 'end': start},
                         {'id': 'cargo', 'template': cargo, 'start': cargo_start, 'end': cargo_end},
                         {'id': 'right_arm', 'template': reference, 'start': end, 'end': end+length}],
                      'circular_product': False, 'overlap_length': overlap})
    if build.status != 'completed':
        return failure(build)
    candidate = build.result.only_product()
    if str(candidate.seq) != model['product_sequence']:
        return failure(build, 'Actual prepared product differs from the source-bound donor model; reselect the actual template interval.')
    for name, begin, finish in (('left_boundary_qc', length, length+cargo_end-cargo_start),
                                ('right_boundary_qc', length+cargo_end-cargo_start, len(candidate))):
        qc = call(name, 'recipe_cloning_verification',
                  {'recombinant_plasmid_seq_or_file': candidate, 'insert_start_0based': begin,
                   'insert_end_0based': finish, 'background_templates': {'unedited_reference': reference},
                   'read_length_bp': 800, 'read_trim_bp': 30})
        if qc.status != 'completed':
            return failure(qc)
    provenance = [context.reference_info(key) for key in sources]
    notes = ('根据用户明确的参考、替换/插入边界、cargo边界和同源臂长度制备线性供体。'
             '实际产物来自完整模板PCR' + ('。' if preparation == 'pcr' else '及现有Gibson组装。') +
             '核查的是供体结构、完整引物、当前文件及已声明目标。'
             '两组接口PCR针对当前供体，原参考背景按实际序列预测；这些不是基因组整合结果。'
             '测序覆盖采用800 bp读长、前段裁去30 bp的计算假设，不是实测。'
             '本流程仅针对所提供的选定参考，不证明全基因组唯一性、实际菌株基因型或复活成功；未自动指定SY14的URA3插入位点。')
    try:
        delivery = observe_files('construct.delivery', deliver_result,
            args=(requirements,sources,steps,candidate,run_dir/'delivery'),
            kwargs={'output_step':'donor_preparation','result_kind':'construct','report_notes':notes,
                    'provenance':{'kit':'construct','references':provenance}},
            output_paths=lambda value:[str(Path(value['directory'])/name) for name in
                ('construct.gb','construct.dna','construct.fasta')],
            output_directories=[run_dir/'delivery'],artifact_role='authoritative')
        receipt = observe_files('construct.delivery_receipt', verify_delivery_files,
            args=(delivery['directory'],),
            kwargs={'presented_files':delivery['present_files'],'expected_manifest_sha256':delivery['manifest_sha256']},
            input_paths=[row['path'] for row in delivery['present_files']],output_paths=lambda _: ())
    except TraceStopped:
        raise
    except Exception as exc:
        result = failure(build, str(exc))
        result['error'] = exc.to_dict() if hasattr(exc, 'to_dict') else {'message': str(exc)}
        return result
    result = {'status': 'delivered', 'kit': 'construct', 'method': 'integration_donor', 'core_version': CORE_VERSION,
              'summary': f'得到{len(candidate)} bp线性供体，按实际模板{preparation}制备，并完成两侧供体接口检查及正式文件回读。',
              'observations': observations, 'references': provenance, 'delivery': delivery,
              'delivery_receipt': receipt, 'execution_record': str(run_dir / 'steps.json'),
              'model_record': str(run_dir / 'model_plan.json'), 'write_authoritative_artifact': True,
              'checked_scope': 'Donor sequence, actual computational preparation, donor QC, saved files and declared goals.',
              'not_checked': ['Actual genomic integration or revival', 'Whole-genome specificity', 'Physical stock and experimental efficiency'],
              'coordinate_system': '0-based-half-open on context.material selected records'}
    if 'identity_handoff' in request:
        from .handoff import write_handoff
        ids=request['identity_handoff']['references']
        handoff=observe_files('construct.identity_handoff',write_handoff,
            args=(request['identity_handoff'],context,run_dir/'steps.json',out_dir,request['original_request']),
            input_paths=[run_dir/'steps.json',*[context.references[key]['path'] for key in ids]],
            output_paths=lambda value:value['paths'],output_directories=[out_dir],artifact_role='supporting-file')
        result['identity_handoff']=handoff
        result['auxiliary_files']=[{'path':path,'purpose':'Identity handoff: actual donor-QC candidates and explicit supplied references.'} for path in handoff['paths']]
    observe_value('construct.outcome', result)
    return result
