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


def goal_coverage(requirements, traces):
    """Report declared checks without certifying free-text semantic coverage."""
    checked = [name for name in ('topology', 'expected_sequence', 'expected_components', 'forbidden_components')
               if requirements.get(name)]
    if requirements.get('is_cds'):
        checked.append('is_cds')
    return {
        'checked_fields': checked,
        'component_checks': copy.deepcopy(traces),
        'component_semantics': 'declared presence/absence and strand; copy count and order are not implied',
        'unverified_text_fields': [name for name in ('description', 'original_request') if requirements.get(name)],
        'semantic_coverage': 'declared computable constraints only; free-text goals are not automatically verified',
    }


def validate_validation_options(required_scopes, result_kind):
    allowed = {'sequence_model', 'preparation_model', 'file', 'user_goal'}
    if result_kind not in ('construct', 'component', 'verification', 'primers', 'protocol'):
        raise ValidationError('INVALID_RESULT_ROLE', 'Unknown result_kind')
    if required_scopes is not None and (
            not isinstance(required_scopes, list) or not required_scopes
            or any(not isinstance(scope, str) or scope not in allowed for scope in required_scopes)
            or len(set(required_scopes)) != len(required_scopes)):
        raise ValidationError('INVALID_VALIDATION_SCOPES', 'required_scopes must be a nonempty list of distinct supported scopes')
