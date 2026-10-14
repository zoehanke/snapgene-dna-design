"""Compare submitted observations without certifying a revival mechanism."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from evidence_trace.models import file_digest
from evidence_trace.runtime import observe
from revival import __version__

CONCLUSION_RULES = json.loads((Path(__file__).resolve().parents[1]/'rules/conclusions.json').read_text(encoding='utf-8'))['rules']


def conclusion_rows(observed_counts, tested_genotypes):
    # A finite truth table for the two existing observation flags, not a DSL.
    state = int(bool(observed_counts)) + 2 * int(bool(tested_genotypes))
    return [{'claim': rule['claim'], 'status': rule['status_by_state'][state], 'reason': rule['reason']}
            for rule in CONCLUSION_RULES]


def read_observations(path):
    path = Path(path)
    with path.open(encoding='utf-8-sig', errors='replace', newline='') as handle:
        rows = list(csv.DictReader(handle))
    if rows and not {'id', 'group', 'colonies'}.issubset(rows[0]):
        raise ValueError('Observation CSV needs id, group, colonies; plated_cells and role are optional.')
    return {'rows': rows, 'path': str(path.resolve()), 'sha256': file_digest(path)}


def _count(value, field):
    if value is None or value == '':
        return None
    if type(value) is bool:
        raise ValueError(field + ' must be a nonnegative integer, not a boolean.')
    try:
        number = float(value)
        valid = number.is_integer() and number >= 0
    except (ValueError, TypeError, OverflowError):
        valid = False
    if not valid:
        raise ValueError(field + ' must be a nonnegative integer or omitted.')
    return int(number)


def run_evidence(request, context, out_dir):
    observations = request.get('observations', [])
    if not isinstance(observations, list):
        raise ValueError('observations must be a list.')
    observations = list(observations)
    inputs = []
    if request.get('observations_file'):
        path = Path(request.get('_request_dir', context.base_dir)) / request['observations_file']
        loaded = observe('evidence.read_observations', read_observations, path)
        observations.extend(loaded['rows'])
        inputs.append({k: loaded[k] for k in ('path', 'sha256')})
    groups = defaultdict(list)
    sample_ids = set()
    findings = []
    for row in observations:
        if not isinstance(row, dict) or not all(isinstance(row.get(k), str) and row[k].strip() for k in ('id', 'group')):
            raise ValueError('Each observation needs nonempty id and group.')
        if row['id'] in sample_ids:
            raise ValueError('Observation IDs must be unique; keep repeat observations as separate IDs.')
        sample_ids.add(row['id'])
        current = dict(row, colonies=_count(row.get('colonies'), 'colonies'),
                       plated_cells=_count(row.get('plated_cells'), 'plated_cells'))
        current['observation_origin'] = 'Submitted experimental record; not independently measured by this program.'
        groups[current['group']].append(current)
        if current.get('role') == 'inactivated_donor_control' and current['colonies'] is not None and current['colonies'] > 0:
            findings.append({'status': 'CONTRADICTED', 'sample_id': current['id'],
                             'text': 'The reported inactivated-donor control produced colonies. Complete absence of outgrowth is not supported under these recorded conditions.'})
    group_rows = []
    by_group = {}
    for name, rows in groups.items():
        counts_known = all(row['colonies'] is not None for row in rows)
        plated_known = all(row['plated_cells'] is not None for row in rows)
        colonies = sum(row['colonies'] for row in rows) if counts_known else None
        plated = sum(row['plated_cells'] for row in rows) if plated_known else None
        result = {'group': name, 'sample_ids': [row['id'] for row in rows], 'records': rows,
                  'colonies': colonies, 'plated_cells': plated,
                  'colony_yield_per_reported_cell': colonies / plated if counts_known and plated and plated_known else None,
                  'growth_assessment': 'NOT_TESTED' if colonies is None else ('SUPPORTED' if colonies > 0 else 'NOT_DETECTED'),
                  'growth_statement': 'Growth was reported.' if colonies and colonies > 0 else (
                      'No colonies were reported in the submitted observations; this is not proof that every cell was dead.' if colonies == 0 else 'Colony counts were not supplied.')}
        group_rows.append(result)
        by_group[name] = result
    comparisons = []
    for comparison in request.get('comparisons', []):
        if not isinstance(comparison, dict) or comparison.get('experiment_group') not in by_group or comparison.get('control_group') not in by_group:
            raise ValueError('Each comparison needs existing experiment_group and control_group.')
        experiment, control = (by_group[comparison[k]] for k in ('experiment_group', 'control_group'))
        erate, crate = experiment['colony_yield_per_reported_cell'], control['colony_yield_per_reported_cell']
        comparisons.append({'experiment_group': experiment['group'], 'control_group': control['group'],
                            'experiment_colonies': experiment['colonies'], 'control_colonies': control['colonies'],
                            'normalised_difference': erate - crate if erate is not None and crate is not None else None,
                            'scope': 'Reported colony counts/yields only. A difference does not establish genetic origin or functional revival.'})
    genotypes = []
    outcomes = defaultdict(set)
    for row in request.get('genotype_results', []):
        if not isinstance(row, dict) or not isinstance(row.get('sample_id'), str) or not row['sample_id'].strip():
            raise ValueError('Each genotype result needs sample_id.')
        if row.get('reference_id') not in context.references:
            raise ValueError('Genotype result reference_id must identify a supplied reference or selected region.')
        if row.get('result') not in ('positive', 'negative', 'indeterminate', 'not_tested'):
            raise ValueError('Genotype result must be positive, negative, indeterminate or not_tested.')
        control = row.get('control_status', 'unknown')
        if control not in ('passed', 'failed', 'unknown'):
            raise ValueError('control_status is the reported passed/failed/unknown assay-control state.')
        result = row['result']
        status = 'NOT_TESTED' if result == 'not_tested' else ('SUPPORTED' if result in ('positive', 'negative') and control == 'passed' else 'INSUFFICIENT')
        item = {**row, 'control_status': control, 'assessment': status,
                'reference': context.reference_info(row['reference_id']),
                'scope': 'Reported result at the selected reference/region only; control state is also supplied, not independently certified.'}
        genotypes.append(item)
        if control == 'passed' and result in ('positive', 'negative'):
            outcomes[(row['sample_id'], row['reference_id'])].add(result)
    for (sample_id, reference_id), results in outcomes.items():
        if len(results) > 1:
            findings.append({'status': 'CONTRADICTED', 'sample_id': sample_id, 'reference_id': reference_id,
                             'text': 'Positive and negative results were submitted for the same sample/reference. A single consistent genotype conclusion is not supported.'})
    reported = bool(observations or genotypes)
    observed_counts = any(row['colonies'] is not None for rows in groups.values() for row in rows)
    tested_genotypes = any(row['result'] != 'not_tested' for row in genotypes)
    summary = (f'整理了{len(observations)}条菌落观察和{len(genotypes)}条已报告遗传检测；'
               f'保留{len(findings)}项对照或一致性问题。局部观察尚不能证明基因组复活或完整消除。') if reported else '没有提供可计算的实验观察或遗传检测结果。本次只能记录缺口，未作复活或全基因组消除判断。'
    return {'kit': 'evidence', 'status': 'analysed' if reported else 'incomplete',
            'summary': summary,
            'groups': group_rows, 'comparisons': comparisons, 'genotype_results': genotypes, 'findings': findings,
            'input_files': inputs,
            'checks': [{'name': 'Submitted record structure and explicit references', 'status': 'PASSED' if reported else 'INCOMPLETE',
                        'tool': 'genome-revival-toolkit', 'tool_version': __version__,
                        'scope': 'Local parsing, nonnegative integer counts and reference correspondence; no experimental authentication.'}],
            'conclusions': conclusion_rows(observed_counts,tested_genotypes),
            'checked_scope': 'Consistency and scope of supplied experimental records, not a new experiment.',
            'unverified': ['Experimental record authenticity.', 'Unmeasured genomic regions and functional dependencies.']}
