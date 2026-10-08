"""One executable goal definition shared by validation and interface discovery."""
from __future__ import annotations
import copy
import jsonschema
from core.errors import ValidationError


_TEXT = {'type': 'string', 'minLength': 1, 'pattern': r'\S'}
_DNA = {'type': 'string', 'minLength': 1, 'pattern': '^[ACGTRYSWKMBDHVNacgtryswkmbdhvn]+$'}
_COMPONENT = {'anyOf': [_TEXT, {
    'type': 'object',
    'properties': {
        'name': _TEXT, 'source_id': _TEXT,
        'expected_sequence': _DNA, 'sequence': _DNA,
        'interval_0based': {'type': 'array', 'minItems': 2, 'maxItems': 2,
                           'items': {'type': 'integer', 'minimum': 0}},
        'strand': {'type': 'integer', 'enum': [1, -1]},
    },
    'anyOf': [{'required': [field]} for field in ('name', 'expected_sequence', 'sequence')],
    'additionalProperties': False,
}]}
_COMPONENT_LIST = {'type': 'array', 'items': _COMPONENT}
_PROPERTIES = {
    'description': {'type': 'string'},
    'original_request': {'type': 'string'},
    'goal_items': {'type': 'array', 'items': {
        'type': 'object', 'required': ['id', 'text'],
        'properties': {'id': _TEXT, 'text': _TEXT, 'source_quote': _TEXT,
                       'constraint_refs': {'type': 'array', 'items': _TEXT, 'uniqueItems': True}},
        'additionalProperties': False}},
    'topology': {'type': 'string', 'enum': ['linear', 'circular']},
    'expected_sequence': _DNA,
    'expected_components': _COMPONENT_LIST,
    'forbidden_components': _COMPONENT_LIST,
    'is_cds': {'type': 'boolean'},
    'required_files': {'type': 'array', 'items': _TEXT, 'uniqueItems': True},
    # Source records may retain Task metadata. Their ids/paths are validated by
    # the common source resolver and cannot replace a different supplied source.
    'sources': {'type': 'array', 'items': {
        'type': 'object', 'properties': {'source_id': _TEXT}, 'required': ['source_id'],
    }},
}
_SCHEMA = {'type': 'object', 'properties': _PROPERTIES, 'additionalProperties': False}


def requirements_definition():
    """Return the same schema consumed by the public validation boundary."""
    return copy.deepcopy(_SCHEMA)


def validate_requirements(requirements):
    """Reject ignored declarations before computation or artifact writing."""
    _validate(_SCHEMA, requirements, 'GOAL_INPUT_INVALID')
    validate_component_declarations(requirements)
    ids=set()
    refs=set(constraint_references(requirements))
    for item in requirements.get('goal_items', []):
        if item['id'] in ids:
            raise ValidationError('GOAL_INPUT_INVALID', 'goal_items ids must be distinct')
        ids.add(item['id'])
        if item.get('source_quote') and item['source_quote'] not in requirements.get('original_request', ''):
            raise ValidationError('GOAL_INPUT_INVALID', 'source_quote must occur in the original request')
        if any(ref not in refs for ref in item.get('constraint_refs', [])):
            raise ValidationError('GOAL_INPUT_INVALID', 'constraint_refs must name declared executable constraints')
    for name in requirements.get('required_files', []):
        from pathlib import PurePosixPath
        path = PurePosixPath(name.replace('\\', '/'))
        if path.is_absolute() or '..' in path.parts or ':' in name:
            raise ValidationError('GOAL_INPUT_INVALID', 'required_files must name relative bundle artifacts')
    return requirements


def _validate(schema, value, code):
    error = next(iter(jsonschema.Draft7Validator(schema).iter_errors(value)), None)
    if error is not None:
        location = '.'.join(map(str, error.absolute_path)) or '<root>'
        if error.validator == 'additionalProperties' and isinstance(error.instance, dict):
            unknown = sorted(set(error.instance) - set(error.schema.get('properties', {})))
            message = f'unsupported fields: {unknown}'
        else:
            message = f'invalid {error.validator} declaration'
        # Validation errors must not dump supplied sequences into ordinary logs.
        raise ValidationError(code, f'{location}: {message}',
                              details={'field': location, 'supported_fields': sorted(_PROPERTIES)})


def validate_component_declarations(request):
    """Check component shape for Workflow, Recipe, Pipeline and legacy Tasks."""
    groups = [(name, request[name]) for name in ('expected_components', 'forbidden_components') if name in request]
    product = request.get('product', {})
    groups.extend(('product.' + name, product[name]) for name in ('required_components', 'forbidden_components')
                  if isinstance(product, dict) and name in product)
    for group, components in groups:
        _validate(_COMPONENT_LIST, components, 'COMPONENT_INPUT_INVALID')
        for component in components:
            if not isinstance(component, dict):
                continue
            first, second = component.get('expected_sequence'), component.get('sequence')
            if first is not None and second is not None and first.upper() != second.upper():
                raise ValidationError('COMPONENT_INPUT_CONFLICT', f'{group}: sequence aliases disagree')
            interval = component.get('interval_0based')
            if interval is not None and interval[0] >= interval[1]:
                raise ValidationError('COMPONENT_INPUT_INVALID', f'{group}: interval must be nonempty and increasing')


def constraint_references(requirements):
    refs=[]
    for name in ('topology','expected_sequence','is_cds'):
        if requirements.get(name): refs.append('/'+name)
    for name in ('expected_components','forbidden_components','required_files'):
        refs.extend('/'+name+'/'+str(i) for i in range(len(requirements.get(name, []))))
    return refs


def goal_coverage(requirements, traces, *, checks=None, subject_version=None):
    """Report declared checks without certifying free-text semantic coverage."""
    checked = [name for name in ('topology', 'expected_sequence', 'expected_components', 'forbidden_components','required_files')
               if requirements.get(name)]
    if requirements.get('is_cds'):
        checked.append('is_cds')
    checks=checks or {}
    results=[{'constraint_ref':ref,'status':checks.get(ref,'UNCHECKED')} for ref in constraint_references(requirements)]
    items=[]
    for item in requirements.get('goal_items', []):
        refs=item.get('constraint_refs', [])
        statuses=[checks.get(ref,'UNCHECKED') for ref in refs]
        status=('MISSED' if not refs else 'FAILED' if 'FAILED' in statuses else
                'UNCHECKED' if any(s!='PASSED' for s in statuses) else 'PASSED')
        items.append({**copy.deepcopy(item),'status':status})
    return {
        'checked_fields': list(dict.fromkeys(r['constraint_ref'].split('/')[1] for r in results if r['status'] in ('PASSED','FAILED'))),
        'declared_fields': checked,
        'check_results': results,
        'goal_items': items,
        'subject_version': subject_version,
        'component_checks': copy.deepcopy(traces),
        'component_semantics': 'declared presence/absence and strand; copy count and order are not implied',
        'unverified_text_fields': [name for name in ('description', 'original_request') if requirements.get(name)],
        'semantic_coverage': 'declared computable constraints only; free-text goals are not automatically verified',
    }


def inherit_requirements(steps=(), requirements=None):
    """Keep earlier goals when a later call omits context; additions remain possible."""
    contexts=[s.get('requirements',{}) if isinstance(s,dict) else getattr(s,'requirements',{}) for s in steps]
    contexts.append({} if requirements is None else requirements)
    merged={}
    for context in contexts:
        _validate(_SCHEMA,context,'GOAL_INPUT_INVALID')
        validate_component_declarations(context)
        for key,value in context.items():
            if key not in merged:
                merged[key]=copy.deepcopy(value)
            elif isinstance(value,list):
                for item in value:
                    prior=next((x for x in merged[key] if key=='goal_items' and x['id']==item['id']),None)
                    if prior is not None:
                        if any(prior.get(k)!=item.get(k) for k in ('text','source_quote')):
                            raise ValidationError('GOAL_CONTEXT_CONFLICT','Earlier goal item changed: '+item['id'])
                        prior['constraint_refs']=list(dict.fromkeys(prior.get('constraint_refs',[])+item.get('constraint_refs',[])))
                    elif item not in merged[key]:merged[key].append(copy.deepcopy(item))
            elif value!=merged[key]:
                raise ValidationError('GOAL_CONTEXT_CONFLICT', 'Earlier requirement changed: '+key)
    validate_requirements(merged)
    return merged


def task_requirements(task):
    """Adapt Task context without treating legacy Handler-specific goals as source features."""
    common={key:task[key] for key in _PROPERTIES if key in task and key!='sources'}
    if task.get('raw_request'):
        common=inherit_requirements(requirements={**common,'original_request':task['raw_request']})
        if task.get('original_request') and task['original_request']!=task['raw_request']:
            raise ValidationError('GOAL_CONTEXT_CONFLICT','raw_request and original_request differ')
    if task.get('product',{}).get('topology'):
        common=inherit_requirements([{'requirements':common}],{'topology':task['product']['topology']})
    return inherit_requirements([{'requirements':common}],task.get('requirements'))


def check_goal_constraints(requirements, material, sources=None):
    """Evaluate current material against declared goals, independently of route choice."""
    from core.runtime_validate import _validate_requested_components
    from core.models.molecule import as_molecule
    material=as_molecule(material)
    checks={}
    errors=[]
    for name,actual in (('topology',material.topology),('expected_sequence',str(material.seq))):
        if requirements.get(name):
            expected=requirements[name].upper() if name=='expected_sequence' else requirements[name]
            checks['/'+name]='PASSED' if expected==actual else 'FAILED'
            if expected!=actual:errors.append('GOAL_'+name.upper()+'_MISMATCH')
    traces,component_errors=_validate_requested_components(requirements,material,source_records=sources)
    errors.extend(component_errors)
    if requirements.get('is_cds'):
        from core.guardrails.checklist import quick_biological_sanity_check
        sanity=quick_biological_sanity_check(material,topology=material.topology,is_cds=True)
        coding=[row['status'] for code,row in sanity['guardrail_status_table'].items() if code.startswith(('BIO-01','BIO-02'))]
        checks['/is_cds']='FAILED' if any(s not in ('PASS','N/A') for s in coding) else 'PASSED' if 'PASS' in coding else 'UNCHECKED'
        if checks['/is_cds']=='FAILED':errors.append('GOAL_CDS_MISMATCH')
    consumed=set()
    for field,kind in (('expected_components','expected_component'),('forbidden_components','forbidden_component')):
        for index,item in enumerate(requirements.get(field, [])):
            name=item if isinstance(item,str) else item.get('name','component')
            source=None if isinstance(item,str) else item.get('source_id')
            matching=next((i for i,t in enumerate(traces) if i not in consumed and
                t.get('check')==kind and t.get('component')==name and t.get('source_id')==source),None)
            if matching is not None:
                consumed.add(matching)
                checks[f'/{field}/{index}']='PASSED' if traces[matching]['passed'] else 'FAILED'
    return traces,errors,checks


def completion_report(coverage, *, local_success, final=True, scope_results=None):
    """A completed operation is not evidence of complete natural-language interpretation."""
    statuses=[r['status'] for r in coverage.get('check_results', [])]+[r['status'] for r in coverage.get('goal_items', [])]
    declared=('FAILED' if 'FAILED' in statuses else 'UNCHECKED' if not statuses or
              any(s!='PASSED' for s in statuses) else 'PASSED')
    original=bool(coverage.get('unverified_text_fields'))
    failed='FAILED' in statuses or any(row.get('status')=='FAILED' for row in (scope_results or {}).values())
    status=('FAILED' if failed and final or not local_success and not final else
            'UNVERIFIED' if not local_success else 'IN_PROGRESS' if not final and statuses else
            'NOT_REQUESTED' if not final and not statuses and not original else
            'UNVERIFIED' if original or declared!='PASSED' else 'DECLARED_GOALS_PASSED')
    return {'status':status,'scope':'declared executable requirements',
            'declared_goals_status':declared,'original_task_verified':False,
            'original_request_status':'UNVERIFIED' if original else 'NOT_PROVIDED',
            'semantic_boundary':'Original-text completeness is not inferred from local checks or host-authored mappings.'}


def validate_validation_options(required_scopes, result_kind):
    allowed = {'sequence_model', 'preparation_model', 'file', 'user_goal'}
    if result_kind not in ('construct', 'component', 'verification', 'primers', 'protocol'):
        raise ValidationError('INVALID_RESULT_ROLE', 'Unknown result_kind')
    if required_scopes is not None and (
            not isinstance(required_scopes, list) or not required_scopes
            or any(not isinstance(scope, str) or scope not in allowed for scope in required_scopes)
            or len(set(required_scopes)) != len(required_scopes)):
        raise ValidationError('INVALID_VALIDATION_SCOPES', 'required_scopes must be a nonempty list of distinct supported scopes')
