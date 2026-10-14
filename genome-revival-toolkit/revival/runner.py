"""One application boundary for the Kits and the existing Trace sidecar."""
from __future__ import annotations
from evidence_trace.localization import tr, get_language
from revival.localization import language_scope

import copy
import json
from pathlib import Path
import uuid

from revival import __version__
from kits.catalog import application, applications, application_function, request_fields
from revival.bootstrap import CORE_VERSION
from revival.context import ProjectContext, read_json
from core.tools.result import to_wire
from core.runtime_gate import verify_delivery_files
from evidence_trace.models import file_digest, now
from evidence_trace.runtime import traced_run, observe, observe_files, observe_value, TraceStopped
from evidence_trace.settings import get_level

COMMON = {'kit', 'title', 'original_request', 'decisions'}





def selected_references(kit,request,context):
    return application_function(kit,'references_entry')(request,context)


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


def human_summary(result,context_snapshot,request):
    app=application(result['kit'])
    return application_function(result['kit'],'summary_entry')(result,context_snapshot,request,app['manifest']['metadata'])


def additional_outputs(result,out_dir,write=False):
    if not application(result['kit'])['manifest']['metadata'].get('output_entry'):
        return {'paths':[],'write_receipts':[],'present_files':[]}
    return application_function(result['kit'],'output_entry')(result,out_dir,write=write)


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
    extra=additional_outputs(result,out,write=True)
    files.extend(Path(path) for path in extra['paths']);writes.extend(extra['write_receipts'])
    files.extend(Path(item['path']) for item in result.get('auxiliary_files', []))
    return {'paths': [str(path) for path in files], 'write_receipts': writes}


@traced_run('genome-revival-toolkit')
def execute(request, context, out_dir, invocation, request_path):
    kit = request['kit']
    ids = selected_references(kit, request, context)
    context_snapshot = observe('toolkit.context', context.describe, ids)
    params = {k: copy.deepcopy(v) for k, v in request.items() if k not in COMMON}
    params['original_request'] = request['original_request']
    function=application_function(kit,'workflow_entry')
    directory_parameter=application(kit)['manifest']['metadata'].get('request_directory_parameter')
    if directory_parameter:params[directory_parameter]=str(Path(request_path).resolve().parent)
    result = observe('toolkit.' + kit, function, params, context, Path(out_dir))
    metadata=application(kit)['manifest']['metadata']
    if metadata.get('gate_context_entry'):
        from core.kit_contributions import evaluate_active_gates
        from core.kits import KitCatalog
        gate_context=application_function(kit,'gate_context_entry')(request,result,context,Path(out_dir))
        results=evaluate_active_gates(**gate_context)
        result['kit_gate_results']=results
        if any(not row['passed'] for row in results) and result['status'] not in ('failed','incomplete'):
            result['status']='failed'
    result.update(toolkit_version=__version__, core_version=CORE_VERSION, invocation=invocation,
                  report_title=request.get('title'),
                  report_scope=tr(application(kit)['manifest']['metadata']['scope']), report_unverified_scope=[tr(value) for value in application(kit)['manifest']['metadata']['limits']],
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
    items.extend(additional_outputs(result,Path(out_dir))['present_files'])
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
    from core.kits import KitCatalog
    from core.kit_contributions import active_validation
    app=application(kit)
    active=active_validation()
    if active and active['kit']['name']==app['manifest']['name']:
        with language_scope(language):
            return _run(kit,request_path,context_path,out_dir,trace_mode=trace_mode,trace_dir=trace_dir)
    catalog=KitCatalog(bundled_directory=app['directory'].parent)
    try:
        with catalog.execution_scope(app['manifest']['name'],{'request_file':str(request_path),'context_file':str(context_path)}):
            with language_scope(language):
                result=_run(kit,request_path,context_path,out_dir,trace_mode=trace_mode,trace_dir=trace_dir)
                active_validation()['terminal_status']=result['status']
                return result
    finally:catalog.unload(app['manifest']['name'])


def _run(kit, request_path, context_path, out_dir, *, trace_mode='normal', trace_dir=None):
    if kit not in applications():
        raise ValueError('Choose '+', '.join(list(applications())[:-1])+' or '+list(applications())[-1]+'.')
    request_sha256 = file_digest(request_path)
    request = read_json(request_path)
    if file_digest(request_path) != request_sha256:
        raise ValueError('Request file changed while loading; reload its current content.')
    unknown = set(request) - request_fields(kit) - COMMON
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
