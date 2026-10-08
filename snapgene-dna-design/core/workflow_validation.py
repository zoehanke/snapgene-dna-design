"""Replay declared work against original materials; compare actual candidates and files."""
from __future__ import annotations
import copy
import inspect
from pathlib import Path
from core.errors import ValidationError
from core.models.molecule import as_molecule
from core.tools.result import ToolResult, check_result, to_wire
from core.workflow import StepExecution, run_step, runtime_conditions, _materials, _digest


def _core_method(method,folder):
    from core.workflow import get_method
    spec=get_method(method)
    filename=inspect.getsourcefile(inspect.unwrap(spec._function)) if spec is not None else None
    return bool(filename and Path(filename).resolve().is_relative_to(Path(__file__).resolve().parent/folder))


def _material_inputs(value):
    """Check source objects/file/wire inputs, not literal edit/spacer strings."""
    from Bio.SeqRecord import SeqRecord
    if isinstance(value,SeqRecord) or isinstance(value,dict) and 'sequence' in value:
        return [as_molecule(value)]
    if isinstance(value,dict):return [m for v in value.values() for m in _material_inputs(v)]
    if isinstance(value,(list,tuple)):return [m for v in value for m in _material_inputs(v)]
    if isinstance(value,(str,Path)):
        try:
            if len(str(value))<1024 and Path(value).is_file():return [as_molecule(value)]
        except OSError:pass
    return []


def _step(value):
    if isinstance(value,StepExecution):return value
    result=value.get('result')
    if result is not None:
        result=ToolResult([as_molecule(p) for p in result['products']],result['analysis'],result['checks'])
    return StepExecution(value['step_id'],value['method'],value['params'],result,value.get('error'),
                         value.get('input_versions',[]),value.get('source_versions',{}),value.get('conditions',{}),value.get('operations',[]),
                         value.get('requirements',{}),value.get('goal_coverage',{}))


def replay_steps(steps,sources):
    """Ignore imported PASS/operation claims; recompute each recorded public call."""
    source_versions={key:as_molecule(value,default_topology='linear').record_version for key,value in sources.items()}
    conditions=runtime_conditions()
    replayed=[]
    available=set(source_versions.values())
    for value in steps:
        previous=_step(value)
        if previous.error:
            continue  # Retained failed attempts supply no selectable material or checks.
        if previous.source_versions != source_versions:
            raise ValidationError('SOURCE_VERSION_CHANGED',f'Original sources differ at {previous.step_id}')
        if previous.conditions != conditions:
            raise ValidationError('EXECUTION_CONDITIONS_CHANGED',f'Implementation/backend conditions differ at {previous.step_id}')
        actual=run_step(previous.method,previous.params,step_id=previous.step_id,sources=sources,previous=replayed,
                        requirements=previous.requirements,_history_checked=True)
        if actual.error:
            raise ValidationError('REPLAY_FAILED',f'{previous.step_id}: {actual.error["message"]}',details={'error':actual.error})
        if actual.result.products:
            for name,value in actual.params.items():
                if 'primer' in name or 'oligo' in name:
                    continue  # Explicit synthesis/primer parameters are reaction inputs, not templates.
                if any(m.record_version not in available for m in _material_inputs(value)):
                    raise ValidationError('UNDECLARED_INPUT_MATERIAL',f'{previous.step_id}: material is not an original source or completed product')
        if actual.input_versions != previous.input_versions or _digest(actual.result)!=_digest(previous.result):
            raise ValidationError('EXECUTION_RESULT_CHANGED',f'Recorded parameters/material/result differ at {previous.step_id}')
        if _digest(actual.operations)!=_digest(previous.operations):
            raise ValidationError('REACTION_RECORD_CHANGED',f'Internal reaction facts differ at {previous.step_id}')
        if actual.requirements!=previous.requirements:
            raise ValidationError('GOAL_CONTEXT_CHANGED',f'Goal context differs at {previous.step_id}')
        replayed.append(actual)
        available.update(p.record_version for p in actual.result.products)
        available.update(p['record_version'] for op in actual.operations for p in op['result']['products'])
    return replayed


def _match(expected,actual):
    from core.runtime_validate import compare_retained_annotations
    errors=[]
    if str(expected.seq)!=str(actual.seq):errors.append('CANDIDATE_SEQUENCE_MISMATCH')
    if expected.topology!=actual.topology:errors.append('CANDIDATE_TOPOLOGY_MISMATCH')
    errors.extend(compare_retained_annotations(expected,actual))
    return errors


def validate_candidate(requirements,sources,steps,candidate,*,primers=None,files=None,
                       required_scopes=None,result_kind='construct',output_step=None,product_index=None,sanity_context=None):
    """Check computable requirements and actual chain without inventing a Task/route."""
    from core.runtime_validate import _validate_requested_components
    from core.tools.sequence_ops import validate_cds_feature
    from core.handlers.composite_pipeline import _preparation_check
    from core.requirements import (inherit_requirements, validate_validation_options, goal_coverage,
                                   check_goal_constraints, completion_report)
    requirements=inherit_requirements(steps,requirements)
    validate_validation_options(required_scopes, result_kind)
    material=as_molecule(candidate)
    errors=[]
    scopes={scope:check_result(scope,subject=material,status='INCOMPLETE',scope=scope)
            for scope in ('sequence_model','preparation_model','file','user_goal')}
    replayed=[]
    expected=None
    try:
        if steps and _step(steps[-1]).error and output_step is None:
            raise ValidationError('LAST_STEP_FAILED','Select a completed output explicitly after a failure')
        replayed=replay_steps(steps,sources)
        if not replayed:raise ValidationError('NO_REPLAY_EVIDENCE','No actual completed public steps supplied')
        chosen=next((s for s in replayed if s.step_id==output_step),None) if output_step else replayed[-1]
        if chosen is None:raise ValidationError('UNKNOWN_OUTPUT_STEP','Output step is absent')
        if chosen.result.analysis.get('result_kind') in ('verification','primers','protocol') and result_kind=='construct':
            raise ValidationError('RESULT_ROLE_MISMATCH','QC/oligo/protocol results are not new constructs')
        if result_kind=='verification' and chosen.result.analysis.get('subject') is not None:
            expected=as_molecule(chosen.result.analysis['subject'])
        elif product_index is None:
            expected=chosen.result.only_product()
        else:
            if type(product_index) is not int or not 0<=product_index<len(chosen.result.products):
                raise ValidationError('INVALID_PRODUCT_SELECTION','Choose a valid zero-based product index')
            expected=chosen.result.products[product_index]
        mismatches=_match(expected,material)
        for feature in material.features:
            if feature.type=='CDS':
                mismatches.extend(item['code'] for item in validate_cds_feature(feature,material.seq)['errors'])
        errors.extend(mismatches)
        known_method=_core_method(chosen.method,'tools') or _core_method(chosen.method,'recipes')
        known_material=any(not _match(as_molecule(p),expected) for op in chosen.operations
                          if _core_method(op['method'],'tools') for p in op['result']['products'])
        scopes['sequence_model']=check_result('actual_step_replay',subject=material,
                 status='FAILED' if mismatches else ('PASSED' if known_method or known_material else 'INCOMPLETE'),
                 scope='sequence_model',details={'errors':mismatches,'replay_consistency':'PASSED',
                                                'scope_note':('Actual source-bound Core transformation replay' if known_method or known_material else
                                                              'Custom algorithm replay alone is not independent transformation validation')})
        rows=[]
        for step in replayed:
            # Only newly executed program results establish checks. Supplied rows do not.
            for operation in step.operations:
                result=operation['result']
                if result['products'] and _core_method(operation['method'],'tools'):
                    rows.append({'details':result})
            if _core_method(step.method,'recipes') and step.result.analysis.get('preparation'):
                from core.preparation import check_preparation
                preparations=step.result.analysis['preparation']
                check_preparation(preparations)
                for preparation in preparations:
                    product=as_molecule(preparation['product'])
                    checks=[check_result('complete_oligo_replay',subject=product,status='PASSED',scope='preparation_model',
                        conditions={'method':preparation.get('method','PCR')},details={'wet_lab':'NOT_CHECKED'})]
                    rows.append({'details':ToolResult([product],checks=checks).to_dict()})
            if _core_method(step.method,'recipes'):
                # Known Recipe annotations can follow their checked physical parent,
                # but the Recipe's own asserted checks do not establish preparation.
                rows.append({'details':ToolResult(step.result.products).to_dict()})
        preparation=_preparation_check(expected,rows,sources) if result_kind!='verification' else {'status':'NOT_APPLICABLE','details':{'reason':'QC subject is not a newly prepared construct'}}
        scopes['preparation_model']=check_result('actual_reaction_chain',subject=material,
            status=preparation['status'] if not mismatches else 'FAILED',scope='preparation_model',details=preparation['details'])
    except Exception as exc:
        if steps:errors.append(str(exc))
        scopes['sequence_model']=check_result('actual_step_replay',subject=material,status='INCOMPLETE' if not steps else 'FAILED',
               scope='sequence_model',details={'error':exc.to_dict() if isinstance(exc,ValidationError) else str(exc)})

    from core.workflow_delivery import _used_products, preparation_rows
    from core.preparation import check_preparation_quality
    used_versions = _used_products(replayed, expected if expected is not None else material)
    quality_rows = preparation_rows(replayed,expected if expected is not None else material)
    quality = check_preparation_quality(quality_rows)
    scopes['preparation_model']['details']['oligo_quality'] = quality
    if quality['status'] in ('FAILED', 'INCOMPLETE'):
        scopes['preparation_model']['status'] = quality['status']
        errors.append('OLIGO_QUALITY_' + quality['status'] + ': complete preparation oligo quality was not established')
    actual_primers=[p for row in replayed for p in row.result.analysis.get('primers',[])]
    for row in replayed:
        for op in row.operations:
            analysis=op['result']['analysis']
            actual_primers.extend(p for p in analysis.get('primers',[]) if isinstance(p,dict))
            actual_primers.extend(analysis[key] for key in ('forward_primer','reverse_primer') if isinstance(analysis.get(key),dict))
    if primers is not None:
        from core.workflow_delivery import _used_products, preparation_rows, synthesis_orders
        used=_used_products(replayed,expected or material)
        needed=[]
        for row in preparation_rows(replayed,expected if expected is not None else material):
            if as_molecule(row['product']).record_version in used:
                needed.extend(p.get('sequence') or p.get('seq') for p in row['primers'])
        supplied={p.get('sequence') or p.get('sequence_5to3') or p.get('seq') for p in primers if p.get('role','preparation')=='preparation'}
        if any(sequence not in supplied for sequence in needed):
            errors.append('MISSING_FINAL_PREPARATION_OLIGO')
            scopes['preparation_model']['status']='FAILED'
        synthesis=synthesis_orders(replayed,expected or material)
        synthesis_supplied={p.get('sequence') or p.get('sequence_5to3') or p.get('seq') for p in primers if p.get('role')=='synthesis'}
        if any(p['sequence_5to3'] not in synthesis_supplied for p in synthesis):
            errors.append('MISSING_FINAL_SYNTHESIS_OLIGO')
            scopes['preparation_model']['status']='FAILED'
        # Every delivered oligo has explicit usage; QC is separate from preparation.
        for p in primers:
            sequence=p.get('sequence') or p.get('sequence_5to3')
            role=p.get('role','preparation')
            if role=='synthesis':
                if sequence not in {q['sequence_5to3'] for q in synthesis}:
                    errors.append('FINAL_OLIGO_NOT_IN_ACTUAL_REACTION')
                    scopes['preparation_model']['status']='FAILED'
                continue
            allowed=[q for row in replayed if (row.result.analysis.get('result_kind')=='verification')==(role=='qc')
                     for q in row.result.analysis.get('primers',[]) if isinstance(q,dict)]
            if role=='qc' and not any(sequence==(q.get('sequence') or q.get('seq')) for q in allowed):
                errors.append('OLIGO_ROLE_MISMATCH')
                scopes['preparation_model']['status']='FAILED'
            if not any(sequence==(q.get('sequence') or q.get('sequence_5to3') or q.get('seq')) for q in actual_primers):
                errors.append('FINAL_OLIGO_NOT_IN_ACTUAL_REACTION')
                scopes['preparation_model']['status']='FAILED'
    goal_errors=[]
    from core.guardrails.checklist import quick_biological_sanity_check
    context={**(sanity_context or {}),'topology':material.topology}
    if 'is_cds' in requirements and 'is_cds' in context and context['is_cds'] != requirements['is_cds']:
        raise ValidationError('GOAL_CONTEXT_CONFLICT', 'is_cds disagrees between the goal and validation conditions')
    context.setdefault('is_cds',bool(requirements.get('is_cds',False)))
    sanity=quick_biological_sanity_check(material,**context)
    if sanity.get('all_applicable_pass') is not True:
        goal_errors.extend('BIOLOGICAL_CHECK_FAILED: '+str(code) for code in sanity.get('blocking_codes',[]))
    traces,component_errors,goal_checks=check_goal_constraints(requirements,material,{k:as_molecule(v) for k,v in sources.items()})
    goal_errors.extend(component_errors)
    coverage=goal_coverage(requirements,traces,checks=goal_checks,subject_version=material.record_version)
    structured=bool(coverage['declared_fields'])
    unmapped=any(item['status'] in ('MISSED','UNCHECKED') for item in coverage['goal_items'])
    errors.extend(goal_errors)
    scopes['user_goal']=check_result('computable_user_requirements',subject=material,
        status=('FAILED' if goal_errors else 'INCOMPLETE' if unmapped else 'PASSED') if structured else 'INCOMPLETE',scope='user_goal',
        details={'checks':traces,'errors':goal_errors,'coverage':coverage,
                 'semantic_coverage':'declared computable requirements only'})
    hashes={}
    file_errors=[]
    verified_files=set()
    if files:
        import hashlib
        from Bio import SeqIO
        from core.workflow_delivery import file_subjects,order_rows,render_design
        subjects=file_subjects(replayed,material)
        for name,path in files.items():
            before_errors=len(file_errors)
            path=Path(path)
            if not path.is_file():file_errors.append('MISSING_FILE: '+name);continue
            hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
            declared_suffix=Path(name).suffix.lower()
            if declared_suffix in ('.gb','.gbk','.dna','.fa','.fasta') and path.suffix.lower()!=declared_suffix:
                file_errors.append('FILE_FORMAT_MISMATCH: '+name)
                continue
            expected_file=subjects.get(name,material if '/' not in name else None)
            if path.suffix.lower() in ('.gb','.gbk','.dna'):
                saved=as_molecule(path)
                if expected_file is None or _match(expected_file,saved):
                    file_errors.append('FILE_MATERIAL_MISMATCH: '+name)
                    if expected_file is not None:file_errors.extend(_match(expected_file,saved))
            elif path.suffix.lower() in ('.fa','.fasta'):
                with path.open(encoding='utf-8') as handle:record=SeqIO.read(handle,'fasta')
                if expected_file is None or str(record.seq).upper()!=str(expected_file.seq):file_errors.append('FILE_SEQUENCE_MISMATCH')
            elif name=='oligo_order_table.tsv':
                import csv
                with path.open(encoding='utf-8') as handle:record=list(csv.DictReader(handle,delimiter='\t'))
                if primers is None or record!=order_rows(primers):file_errors.append('ORDER_TABLE_MISMATCH')
            elif name=='design.md':
                if primers is None or path.read_text(encoding='utf-8')!=render_design(material,result_kind,replayed,order_rows(primers),requirements,quality):
                    file_errors.append('EXPLANATION_NOT_CURRENT')
            elif name=='execution.json':
                import json
                if _digest(json.loads(path.read_text(encoding='utf-8')))!=_digest([s.to_dict() for s in replayed]):
                    file_errors.append('EXECUTION_RECORD_MISMATCH')
            elif name=='requirements.json':
                import json
                if json.loads(path.read_text(encoding='utf-8'))!=requirements:file_errors.append('REQUIREMENTS_RECORD_MISMATCH')
            elif name=='preparation_quality.json':
                import json
                if json.loads(path.read_text(encoding='utf-8')) != quality:
                    file_errors.append('PREPARATION_QUALITY_RECORD_MISMATCH')
            elif name=='primer_order_table.tsv':
                import csv
                from core.workflow_delivery import preparation_rows
                needed=[(p.get('name','primer'),p.get('sequence') or p.get('seq')) for row in preparation_rows(replayed,material) for p in row['primers']]
                with path.open(encoding='utf-8') as handle:orders=list(csv.DictReader(handle,delimiter='\t'))
                if [(p.get('name'),p.get('sequence_5to3')) for p in orders]!=needed:file_errors.append('PREPARATION_ORDER_TABLE_MISMATCH')
            else:
                file_errors.append('FILE_CONTENT_UNVERIFIED: '+name)
            if len(file_errors)==before_errors:verified_files.add(name)
        for name in requirements.get('required_files',[]):
            if name not in files:file_errors.append('MISSING_REQUIRED_FILE: '+name)
        for index,name in enumerate(requirements.get('required_files',[])):
            goal_checks[f'/required_files/{index}']='PASSED' if name in verified_files else 'FAILED'
        scopes['file']=check_result('saved_file_readback',subject=material,status='FAILED' if file_errors else 'PASSED',scope='file',details={'errors':file_errors})
        errors.extend(file_errors)
    coverage=goal_coverage(requirements,traces,checks=goal_checks,subject_version=material.record_version)
    if structured and not goal_errors:
        goal_statuses=[item['status'] for item in coverage['goal_items']+coverage['check_results']]
        scopes['user_goal']['status']='FAILED' if 'FAILED' in goal_statuses else 'INCOMPLETE' if any(s!='PASSED' for s in goal_statuses) else 'PASSED'
    scopes['user_goal']['details']['coverage']=coverage
    required=required_scopes or (['sequence_model','preparation_model','file','user_goal'] if result_kind=='construct' else ['sequence_model','file','user_goal'])
    errors.extend('VALIDATION_SCOPE_UNSATISFIED: '+scope for scope in required if scopes[scope]['status']!='PASSED')
    coverage=goal_coverage(requirements,traces,checks=goal_checks,subject_version=material.record_version)
    result={'overall':'verified' if not errors else 'failed','scope_results':scopes,'errors':errors,
            'goal_coverage':coverage, 'task_completion':completion_report(coverage,local_success=not errors,scope_results=scopes),
            'preparation_quality': quality,
            'subject_version':material.record_version,'source_versions':{k:as_molecule(v,default_topology='linear').record_version for k,v in sources.items()},
            'requirements':requirements,'conditions':runtime_conditions(),'primers':primers or [],'sanity_context':context,'sanity_check':sanity,
            'steps_sha256':_digest([_step(s).to_dict() for s in steps]),'artifact_hashes':hashes,'file_paths':{k:str(v) for k,v in (files or {}).items()},
            'required_scopes':required,'result_kind':result_kind,'output_step':output_step,'product_index':product_index}
    result['validation_sha256']=_digest(result)
    return result
