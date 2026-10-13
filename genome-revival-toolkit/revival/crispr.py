"""A thin application workflow over the existing Core gRNA operations."""
import csv
from pathlib import Path

from core.tools.crispr import design_crispr_grna
from core.tools.grna import check_grna
from core.tools.grna_evaluation import check_grna_vector
from core.tools.snapgene_io import export_snapgene
from core.tools.result import to_wire
from core.workflow import run_step
from core.workflow_delivery import deliver_result
from core.errors import GateRejected
from evidence_trace.runtime import observe, observe_files
from revival.selection import selection_report


def write_selection(report, path):
    with Path(path).open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, delimiter='\t', fieldnames=
            ['marker', 'host', 'plate', 'compatibility', 'functional_status', 'source_url'])
        writer.writeheader()
        for marker in report['markers']:
            for option in marker['plate_options']:
                writer.writerow({'marker': marker['name'], 'host': option['host'], 'plate': option['plate'],
                    'compatibility': option['compatibility'], 'functional_status': marker['functional_status'],
                    'source_url': option['source']['url']})
    return {'paths': [str(path)]}


def run_crispr(request, context, out_dir):
    vector_id, target_id = request.get('vector_reference'), request.get('target_reference')
    if not isinstance(vector_id, str) or not isinstance(target_id, str):
        raise ValueError('Provide vector_reference and target_reference from the actual Context')
    vector = observe('crispr.vector', context.material, vector_id)
    target = observe('crispr.target', context.material, target_id)
    operation = request.get('operation', 'replace' if 'spacer_seq' in request else 'check')
    if operation not in ('check', 'replace'):
        raise ValueError('operation must be check or replace')
    if operation == 'check' and 'spacer_seq' in request:
        raise ValueError('spacer_seq is a replacement input; do not silently ignore it in check mode')
    if operation == 'replace' and not isinstance(request.get('spacer_seq'), str):
        raise ValueError('replace requires an explicit new 20 nt spacer_seq')
    selectors = {key: request[key] for key in ('promoter_name', 'promoter_end_0based',
                 'transcription_strand', 'scaffold_seq') if key in request}
    limits = request.get('max_mismatches', 3)
    evaluation = observe('crispr.candidates', design_crispr_grna, target,
        vector_seq_or_file=vector, max_mismatches=limits,
        transcription_promoter=request.get('transcription_promoter', 'other_pol_III')).analysis
    initial = observe('crispr.initial_check', check_grna, vector, target, **selectors)
    candidate, preparation, steps, delivery = vector, None, [], None
    requirements = {'expected_components': [{'sequence': request['spacer_seq']}]} if operation == 'replace' else {}
    sources = {'vector': vector, 'target': target}
    if operation == 'replace':
        step = observe('crispr.replace', run_step, 'replace_grna_spacer',
            {'vector_record_or_seq': '$vector', 'spacer_seq': request['spacer_seq'],
             'target_tm': request.get('target_tm', 60.0), **selectors},
            step_id='replace', sources=sources, requirements=requirements)
        if step.status != 'completed' or len(step.result.products) != 1:
            raise ValueError('Core replacement failed; retained step records contain the reason')
        steps.append(step)
        candidate = step.result.products[0]
        preparation = step.result.analysis
    checked = observe('crispr.final_check', check_grna, candidate, target, **selectors)
    self_target = observe('crispr.self_target', check_grna_vector, checked.analysis['spacer'],
                          candidate, max_mismatches=limits).analysis
    selection = observe('crispr.selection', selection_report, candidate, request.get('strain_genotype'))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    table = out / 'selection.tsv'
    observe_files('crispr.selection_table', write_selection, args=(selection, table),
                  output_paths=lambda value:value['paths'], output_directories=[out], artifact_role='supporting-file')
    checks = [*checked.checks,
        {'name': 'provided_vector_self_target', 'status': 'PASSED' if self_target['self_target_status'] == 'NO_MATCH_IN_SEARCH_SCOPE' else 'INCOMPLETE' if self_target['self_target_status'] == 'INCOMPLETE' else 'FAILED',
         'scope': 'provided_vector', 'details': self_target},
        {'name': 'declared_selection_compatibility', 'status': 'PASSED' if selection['status'] == 'DECLARED_COMPATIBLE' else 'FAILED' if selection['status'] == 'CONFLICT' else 'INCOMPLETE',
         'scope': 'declared_background', 'details': selection}]
    if checked.analysis['valid_target_locus_count'] != 1:
        checks.append({'name': 'unique_provided_target', 'status': 'INCOMPLETE', 'scope': 'provided_target'})
    if not checked.analysis['orientation_distinguishable']:
        checks.append({'name': 'distinguishable_orientation', 'status': 'INCOMPLETE', 'scope': 'provided_target'})
    if preparation:
        checks.extend(steps[0].result.checks)
    ready = all(check['status'] in ('PASSED', 'NOT_APPLICABLE') for check in checks)
    if ready and operation == 'replace':
        try:
            delivery = observe_files('crispr.delivery', deliver_result,
                args=(requirements, sources, steps, candidate, out / 'dna'), kwargs={'result_kind':'construct'},
                output_paths=lambda value:[row['path'] for row in value.get('present_files',[])],
                output_directories=[out/'dna'], artifact_role='supporting-file')
        except GateRejected as exc:
            checks.append({'name': 'core_delivery', 'status': 'FAILED', 'scope': 'delivery', 'details': exc.to_dict()})
            ready = False
    auxiliary = [{'path': str(table), 'purpose': 'Annotated markers, conditional plates and literature sources'}]
    if operation == 'replace' and delivery is None:
        exported = observe_files('crispr.candidate_export', export_snapgene,
            args=(candidate, out / 'candidate'), kwargs={'filename_base': 'grna-candidate'},
            output_paths=lambda value: [value.analysis[key] for key in ('gb_file', 'dna_file') if value.analysis.get(key)],
            artifact_role='candidate-file')
        auxiliary.extend({'path': exported.analysis[key], 'purpose': 'Candidate DNA; not formally delivered'}
                         for key in ('gb_file', 'dna_file') if exported.analysis.get(key))
    failed = any(row['status'] == 'FAILED' for row in checks)
    status = 'delivered' if delivery else 'analysed' if ready else 'failed' if failed else 'incomplete'
    return {'kit': 'crispr', 'status': status,
        'summary': ('Current sequence and conditional selection checks completed.' if ready else
                    'Candidate retained; failed or unresolved checks prevent a complete handoff.'),
        'checked_scope': 'Given target/vector, sequence direction and PAM, simulated preparation and user-declared selection background.',
        'candidates': evaluation, 'initial_grna': initial.analysis, 'grna': checked.analysis,
        'self_target': self_target, 'selection': selection, 'preparation': preparation,
        'laboratory_status': preparation['preparation_route']['status'] if preparation else 'NOT_REQUESTED',
        'wet_lab': 'NOT_PERFORMED', 'checks': checks, 'delivery': delivery,
        'selection_table': str(table), 'auxiliary_files': auxiliary,
        'scope_note': 'No genome-wide off-target or efficiency prediction. CDS labels and user genotype do not establish measured resistance.'}
