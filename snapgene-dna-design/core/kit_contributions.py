"""Kit adapters into existing Pipeline, validation and experience-rule seams."""
from contextlib import contextmanager
from contextvars import ContextVar
import copy

from core.errors import GateRejected, ValidationError

_ACTIVE = ContextVar('active_kit_validation',default=None)


def pipeline_callable(content,scope_factory=None):
    """A normal ToolSpec callable delegates to the existing linear executor."""
    def execute_pipeline(inputs: dict):
        from jsonschema import Draft7Validator
        from core.handlers.composite_pipeline import run_pipeline_steps
        from core.tools.result import ToolResult
        from core.tools.registry import _schema_value
        Draft7Validator(content['inputs_schema']).validate(_schema_value(inputs))
        from contextlib import nullcontext
        with scope_factory(inputs) if scope_factory else nullcontext():
            product,rows,environment=run_pipeline_steps(copy.deepcopy(content['steps']),inputs,
                output_step=content.get('output_step'))
            gates=evaluate_active_gates(candidate=product,sources=inputs)
            require_gate_results(gates)
        selected=content.get('output_step') or content['steps'][-1]['step_id']
        selected_result=environment.get(selected.lstrip('$').split('.')[0])
        return ToolResult(products=[product],analysis={'pipeline_steps':rows,'kit_gate_results':gates},
                          checks=selected_result.checks if selected_result else [])
    return execute_pipeline


@contextmanager
def validation_scope(receipt,inputs,gates):
    context={'kit':receipt,'inputs':copy.deepcopy(inputs),'gates':gates,'evaluated':set(),'results':{}}
    token=_ACTIVE.set(context)
    try:yield context
    finally:_ACTIVE.reset(token)


def active_validation():
    return _ACTIVE.get()


def evaluate_gate(gate,*,candidate,sources,requirements=None,steps=(),inputs=None):
    """Actual callable checks bind the current candidate; declarations are not passes."""
    from core.models.molecule import as_molecule
    from core.tools.result import to_wire
    from evidence_trace.runtime import observe_value
    material=as_molecule(candidate)
    rows=gate['callable'](candidate=material,sources=sources,requirements=requirements or {},
                         steps=list(steps),inputs=inputs or {})
    if not isinstance(rows,list):raise ValidationError('KIT_GATE_RESULT_INVALID','Gate must return scoped check rows.')
    definitions={row['scope']:row for row in gate['content']['required_scopes']}
    acceptances={row['scope']:row for row in gate['content'].get('acceptances',[])}
    seen=set();checks=[];errors=[]
    for check in rows:
        if not isinstance(check,dict) or check.get('scope') not in definitions or check['scope'] in seen:
            raise ValidationError('KIT_GATE_RESULT_INVALID','Gate returned an unknown or repeated scope.')
        if check.get('subject_version')!=material.record_version or check.get('status') not in ('PASSED','FAILED','INCOMPLETE','NOT_APPLICABLE'):
            raise ValidationError('KIT_GATE_RESULT_INVALID','Gate check lacks its actual subject/status binding.')
        scope=check['scope'];seen.add(scope);definition=definitions[scope]
        row={**to_wire(check),'gate':gate['name'],'source':gate['source'],
             'error_code':definition['error_code'],'message':definition['message']}
        accepted=acceptances.get(scope)
        if check['status']=='FAILED' and accepted and check.get('details',{}).get('inherited_from_source'):
            source_id=check['details']['inherited_from_source']
            original=as_molecule(sources[source_id]) if source_id in sources else None
            if original is not None and check['details'].get('input_version')==original.record_version:
                row.update(accepted_by_kit_rule=True,effective_status='ACCEPTED_BY_KIT_RULE',
                    acceptance_notice='按 Kit 规则豁免',acceptance_source=accepted['source'],acceptance_reason=accepted['reason'])
        if check['status']!='PASSED' and not row.get('accepted_by_kit_rule'):
            errors.append({'error_code':definition['error_code'],'message':definition['message'],'scope':scope})
        checks.append(row)
    for scope,definition in definitions.items():
        if scope not in seen:errors.append({'error_code':definition['error_code'],'message':definition['message'],'scope':scope,'status':'NOT_CHECKED'})
    result={'gate':gate['name'],'passed':not errors,'checks':checks,'errors':errors,
            'acceptance_scope':'Explicit Kit-owned checks only; original statuses and Core base validation remain unchanged.'}
    observe_value('kit.gate',result)
    active=_ACTIVE.get()
    if active is not None:
        active['evaluated'].add(gate['name']);active['results'][gate['name']]=copy.deepcopy(result)
    return result


def evaluate_active_gates(*,candidate,sources,requirements=None,steps=()):
    active=_ACTIVE.get()
    if not active:return []
    return [evaluate_gate(gate,candidate=candidate,sources=sources,requirements=requirements,
                          steps=steps,inputs=active['inputs']) for gate in active['gates']]


def apply_validation_gates(validation,*,candidate,sources,requirements,steps):
    context=_ACTIVE.get()
    if not context or not context['gates']:return validation
    results=[evaluate_gate(gate,candidate=candidate,sources=sources,requirements=requirements,
                          steps=steps,inputs=context['inputs']) for gate in context['gates']]
    validation['kit_gate_results']=results
    validation['kit']=context['kit']
    for result in results:
        validation['errors'].extend(row['error_code']+': '+row['message'] for row in result['errors'])
    if validation['errors']:validation['overall']='failed'
    return validation


def require_gate_results(results):
    results=list(results)
    failures=[row for result in results for row in result['errors']]
    if failures:
        first=failures[0]
        raise GateRejected(first['error_code'],first['message'],details={'gate_results':results})


def rule_rows(path,fields):
    """Validate the existing rule grammar with explicitly declared extra fields."""
    import json
    from rules.experience import validate_rule, field_scope
    try:data=json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,UnicodeError,ValueError) as error:
        raise ValidationError('KIT_RULE_INVALID','Rule file is not readable UTF-8 JSON.',details={'reason':type(error).__name__}) from error
    if not isinstance(data,dict) or not isinstance(data.get('rules'),list):
        raise ValidationError('KIT_RULE_INVALID','Rule file needs an existing rules list.')
    ids=set()
    with field_scope(fields):
        for row in data['rules']:
            source=row.get('source') if isinstance(row,dict) else None
            nonblank=lambda value:isinstance(value,str) and bool(value.strip())
            if not isinstance(source,dict) or not nonblank(source.get('type')) or not (nonblank(source.get('description')) or nonblank(source.get('url'))):
                raise ValidationError('KIT_RULE_SOURCE_MISSING','Every Kit rule requires an explicit source.')
            try:errors=validate_rule(row,persistent=False)
            except (TypeError,ValueError,AttributeError) as error:
                raise ValidationError('KIT_RULE_INVALID','Rule field shape is invalid.',details={'reason':type(error).__name__}) from error
            if errors:raise ValidationError('KIT_RULE_INVALID','; '.join(errors))
            if row['id'] in ids:raise ValidationError('KIT_RULE_CONFLICT','Rule identifiers must be unique.')
            ids.add(row['id'])
    return copy.deepcopy(data['rules'])


def evaluate_rule_rows(rows,fields,trigger,context,project_id):
    from rules.experience import evaluate_rules,field_scope
    from evidence_trace.runtime import observe_value
    with field_scope(fields):result=evaluate_rules(rows,trigger,context,project_id=project_id)
    observe_value('kit.rules',result)
    return result
