"""Append-only Change objects and conservative impact projections; never edits DNA."""
from __future__ import annotations
import copy
import uuid
from evidence_trace.models import now
from evidence_trace.coverage import choices_for_run, match_choices

VERSION = 'change-impact-v0.3.0'
JUDGMENTS = {'AFFECTED', 'NEEDS REVIEW', 'UNAFFECTED', 'UNKNOWN'}
ACTIONS = {'REASSESS', 'RECHECK', 'RERUN', 'STALE', 'NEEDS REVIEW'}
FAMILIES = {'chassis':'host', 'host_or_chassis':'host', 'source_id':'source', 'path':'source',
 'template_seq_or_file':'source', 'template':'source', 'source_sha256':'sequence',
 'start':'boundary', 'end':'boundary', 'start_0based':'boundary', 'end_0based':'boundary',
 'interval_0based':'boundary', 'insert_start':'boundary', 'insert_end':'boundary',
 'strand':'orientation', 'recipe_name':'method', 'tool':'method', 'alt_seq':'mutation',
 'mutations':'mutation', 'tag_name_or_seq':'component', 'temperature':'environment',
 'medium':'environment', 'assay':'environment', 'construct_context':'component',
 'fragment_order':'order', 'step_order':'order'}


def family(field):
    tail = field.rsplit('.', 1)[-1]
    return FAMILIES.get(tail, tail)


def differences(old, new, prefix=''):
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(old.keys() | new.keys()):
            path = f'{prefix}.{key}' if prefix else key
            if key not in old or key not in new:
                yield path, old.get(key), new.get(key), key in old, key in new
            else:
                yield from differences(old[key], new[key], path)
    elif old != new:
        yield prefix, old, new, True, True


def make_change(before, after, field, old, new, *, old_present=True, new_present=True, **origin):
    return {'id':'CH-'+uuid.uuid4().hex[:12], 'from_revision':before, 'to_revision':after,
            'changed_field':field, 'old_value':copy.deepcopy(old), 'new_value':copy.deepcopy(new),
            'old_present':old_present, 'new_present':new_present, 'recorded_at':now(), **origin}


def revision_changes(old, new):
    fields = {'context', 'targets', 'conditions', 'limitations'}
    if new['kind'] in {'requirement', 'decision', 'claim', 'statement'}:
        fields.add('text')
    if new['kind'] == 'source':
        fields.update({'path', 'url', 'doi', 'pmid'})
    a, b = ({k:r[k] for k in fields if k in r} for r in (old, new))
    return [make_change(old['key'], new['key'], f, x, y, old_present=ap, new_present=bp,
                       basis='record_revision', record_key=old['key'])
            for f,x,y,ap,bp in differences(a,b)]


def run_changes(before, after):
    def indexed(run):
        return {(c['subject'], c['input_path']):c for c in choices_for_run(run)}
    a,b = indexed(before),indexed(after)
    changes = []
    for key in sorted(a.keys() | b.keys()):
        old,new = a.get(key),b.get(key)
        if old and new and old['value'] == new['value']:
            continue
        c = new or old
        changes.append(make_change(before['id'], after['id'], c['input_path'],
            old['value'] if old else None, new['value'] if new else None,
            old_present=old is not None, new_present=new is not None,
            basis='observed_run_inputs' if old and new else 'observation_coverage',
            subject=c['subject'], parameter=c['parameter'], choice=old or new))
    old_product, new_product = product_fields(before), product_fields(after)
    for field in sorted(old_product.keys() & new_product.keys()):
        if old_product[field] != new_product[field]:
            changes.append(make_change(before['id'], after['id'], 'product.' + field,
                old_product[field], new_product[field], basis='observed_products', parameter=field))
    return changes


def product_fields(run):
    """Reuse already recorded Core/Recipe anchors; no sequence recalculation."""
    result = {}
    for stage in run.get('stages', []):
        if stage.get('event_type') != 'stage_completed':
            continue
        value = stage.get('result', {})
        if not isinstance(value, dict):
            continue
        if stage.get('stage') == 'execute':
            sequence = value.get('product_sequence_sha256') or value.get('product_sequence')
            topology = value.get('topology')
        elif stage.get('stage') == 'recipe_result':
            sequence = value.get('recipe_result', {}).get('product_sequence')
            topology = value.get('product_topology')
        else:
            continue
        if sequence is not None:
            result['sequence'] = sequence
        if topology is not None:
            result['topology'] = topology
    return result


def comparison_identity(run):
    for stage in run.get('stages', []):
        if stage.get('event_type') == 'stage_completed' and stage.get('stage') == 'task':
            task = stage.get('result', {})
            if task.get('task_id'):
                return ('task', task['task_id'], task.get('task_kind'))
    for choice in choices_for_run(run):
        if choice.get('parameter') == 'recipe_name':
            return ('recipe', choice['value'])
    return None


def assess_impacts(graph):
    nodes = {n['key']:n for n in graph['nodes']}
    runs = {r['id']:r for r in graph['runs']}
    results = []
    ranks = {'UNAFFECTED':-1, 'UNKNOWN':0, 'NEEDS REVIEW':1, 'AFFECTED':2}
    for change in graph.get('changes', []):
        baseline = runs.get(change['from_revision'])
        cutoff = change.get('event_sequence', float('inf'))
        keys = (set(baseline.get('context_refs', [])) | {n['key'] for n in nodes.values() if n.get('run_id') == baseline['id']}) if baseline else {
            n['key'] for n in nodes.values() if n.get('recorded_sequence',0)<cutoff and n['key']!=change['to_revision']}
        keys = sorted(keys)
        edges = [e for e in graph['edges'] if e['from'] in keys and e['to'] in keys and e['relation']!='revised' and e.get('recorded_sequence',0)<cutoff]
        info = {k:{'judgment':'UNKNOWN','reason':'没有足够依赖信息；未找到关系不等于无关','path':[]} for k in keys}
        uncertain_change = change.get('basis') == 'observation_coverage'
        raw_field = change.get('parameter', change['changed_field']).rsplit('.', 1)[-1]
        field = family(raw_field)
        for key in keys:
            if uncertain_change:
                info[key]['reason'] = '前后观察覆盖不全；不能确认实际字段新增、删除或改变'
                continue
            n = nodes[key]
            deps = n.get('depends_on_fields')
            if isinstance(deps,list) and deps:
                if any(d == '*' or d.rsplit('.', 1)[-1] in {raw_field, field} for d in deps):
                    info[key] = {'judgment':'AFFECTED','reason':'显式字段依赖：'+str(deps),'path':[key]}
                elif n.get('dependency_scope_complete') is True:
                    info[key] = {'judgment':'UNAFFECTED','reason':'记录者声明的完整依赖范围无交集；仅限该范围','path':[key]}
            if key==change.get('record_key'):
                info[key] = {'judgment':'AFFECTED','reason':'该记录的明确修订','path':[key]}
        if change.get('choice') and not uncertain_change:
            matched = match_choices([change['choice']], [nodes[k] for k in keys if nodes[k]['kind']=='decision'])[0]
            for key in matched['decision_refs']:
                info[key] = {'judgment':'AFFECTED' if matched['status']=='explained' else 'NEEDS REVIEW',
                    'reason':'旧 targets 与变化输入关联：'+matched['reason'],'path':[key]}
        declared_unrelated = {k for k,v in info.items() if v['judgment']=='UNAFFECTED'}
        pending = True
        while pending:
            pending = False
            for e in edges:
                parent,child = info[e['from']],info[e['to']]
                if parent['judgment'] not in {'AFFECTED','NEEDS REVIEW'}:
                    continue
                verdict = 'AFFECTED' if parent['judgment']=='AFFECTED' and e['relation'] in {'responds_to','claim_ids','source_id'} else 'NEEDS REVIEW'
                if e['to'] in declared_unrelated:
                    verdict = 'NEEDS REVIEW'
                if ranks[verdict]>ranks[child['judgment']]:
                    info[e['to']] = {'judgment':verdict,'reason':'依赖路径 / '+e['relation'],'path':parent['path']+[e['to']]}
                    pending = True
        def add(target,kind,value,**extra):
            verdict = value['judgment']
            actions = []
            if verdict=='AFFECTED':
                action = {'decision':'REASSESS','claim':'REASSESS','requirement':'REASSESS',
                    'statement':'RECHECK','source':'RECHECK','applicability':'RECHECK','validation':'RERUN'}.get(kind)
                actions = ([action] if action else [])+['STALE']
            elif verdict in {'NEEDS REVIEW','UNKNOWN'}:
                actions = ['NEEDS REVIEW']
            results.append({'change_id':change['id'],'target':target,'target_kind':kind,**value,
                'actions':actions,'algorithm_version':VERSION,**extra})
        for key,value in info.items():
            if nodes[key]['kind']!='source' or key==change.get('record_key'):
                add(key,nodes[key]['kind'],value)
        for e in edges:
            if 'statement_id' in e:
                value = max((info[e['from']],info[e['to']]), key=lambda v:ranks[v['judgment']])
                add('applicability:'+e['id'],'applicability',value,statement_ref=e['from'],claim_ref=e['to'],link_id=e['id'])
    return results


def attach_impacts(graph):
    graph['impacts'] = assess_impacts(graph)
    nodes = {n['key']:n for n in graph['nodes']}
    for view in graph['chain_views']:
        for chain in view['chains']:
            related = {chain['decision'],*chain['claims'],*chain['requirements'],*chain['validations'],*chain['artifacts']}
            for b in chain['evidence']:
                related.update([b['statement'],*b['sources']])
            logical = {nodes[k]['id'] for k in related if k in nodes}
            chain['impacts'] = [i for i in graph['impacts'] if nodes.get(i['target'],{}).get('id') in logical or nodes.get(i.get('claim_ref'),{}).get('id') in logical]
    return graph
