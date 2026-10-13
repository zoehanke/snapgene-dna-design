"""Reference-based machine export; expand for legacy in-process consumers."""
import copy
import json


def _reference_view(graph):
    """Read-only serialization view; copy only containers where references are replaced."""
    result = dict(graph)
    result['schema_version'] = 'design-process-v2'
    records = result['source_records'] = dict(graph['source_records'])
    def pointer(key, *parts):
        return {'$ref': '#/source_records/' + '/'.join(str(p).replace('~', '~0').replace('/', '~1') for p in (key, *parts))}
    for event in result['audit_events']:
        # Authored revision events need not be present in the factual projection.
        records.setdefault(event['event_id'], event)
    result['audit_events'] = [pointer(e['event_id']) for e in result['audit_events']]
    result['runs'] = [dict(run, stages=[dict(stage) for stage in run['stages']]) for run in graph['runs']]
    for run in result['runs']:
        for stage in run['stages']:
            record = records.get(stage.get('event_id'))
            if not record:
                continue
            for field in ('input', 'result', 'before', 'after', 'choice'):
                if field in stage and stage[field] == record['payload'].get(field):
                    stage[field] = pointer(stage['event_id'], 'payload', field)
    return result


def machine_export(graph):
    """Return an independent machine object; callers cannot edit the source through it."""
    return copy.deepcopy(_reference_view(graph))


def machine_json(graph):
    """Serialize the same lossless view without cloning payloads that will only be read."""
    return json.dumps(_reference_view(graph), ensure_ascii=False, separators=(',', ':'))


def expand_machine(graph):
    """Accept v1 or dereference the documented v2 fields without touching user data."""
    if graph.get('schema_version') != 'design-process-v2':
        return graph
    result = copy.deepcopy(graph)
    def resolve(value):
        if not isinstance(value, dict) or set(value) != {'$ref'}:
            return value
        ref = value['$ref']
        if not isinstance(ref, str) or not ref.startswith('#/source_records/'):
            raise ValueError('Invalid machine-record reference')
        item = graph
        for part in ref[2:].split('/'):
            item = item[part.replace('~1', '/').replace('~0', '~')]
        return copy.deepcopy(item)
    result['audit_events'] = [resolve(e) for e in result['audit_events']]
    for run in result['runs']:
        for stage in run['stages']:
            for field in ('input', 'result', 'before', 'after', 'choice'):
                if field in stage:
                    stage[field] = resolve(stage[field])
    result['schema_version'] = 'design-process-v1'
    return result
