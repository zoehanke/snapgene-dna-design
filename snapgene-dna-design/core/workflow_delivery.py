"""Build and check one current delivery bundle, then use the existing atomic gate."""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path
import tempfile
from core.errors import GateRejected
from core.errors import ValidationError
from core.models.molecule import as_molecule
from core.tools.result import to_wire
from core.workflow import _digest
from core.workflow_validation import _step, replay_steps, validate_candidate


def preparation_rows(steps,candidate=None):
    """Owned actual reactions; rich rows and check replays are one preparation."""
    rows=[]
    seen=set()
    for step in steps:
        if step.result.analysis.get('result_kind') in ('verification','primers','protocol'):
            continue  # Diagnostic PCR is an assay, not construct preparation.
        candidates=list(step.result.analysis.get('preparation',[]))
        for operation in step.operations:
            if operation['method']=='simulate_pcr':
                candidates.append({'id':step.step_id,'method':'PCR',
                    'template':operation['params']['template_path_or_seq'],
                    'product':operation['result']['products'][0],
                    'primers':operation['result']['analysis']['primers']})
        ordinal=0
        for item in candidates:
            template=as_molecule(item['template'])
            product=as_molecule(item['product'])
            pair=tuple(p.get('sequence') or p.get('sequence_5to3') or p.get('seq') or p.get('full_sequence')
                       for p in item['primers'])
            key=(step.step_id,template.record_version,product.record_version,pair)
            if key in seen:
                continue
            seen.add(key)
            ordinal+=1
            # Only projection labels change. Keep real molecules/oligos and
            # original labels, and never edit the recorded program response.
            owner=f'{step.step_id}_{ordinal}'
            rows.append({**item,'source_step':step.step_id,'local_id':item.get('id'),
                         'id':owner,'template_version':template.record_version,'product_version':product.record_version,
                         'primers':[{**p,'original_name':p.get('name','primer'),
                                     'name':owner+'_'+p.get('name','primer')} for p in item['primers']]})
    if candidate is not None:
        used = _used_products(steps, candidate)
        rows = [row for row in rows if as_molecule(row['product']).record_version in used]
    return rows


def _used_products(steps,candidate):
    products={candidate.record_version:candidate}
    for step in steps:
        for product in step.result.products:
            products[product.record_version]=product
        for op in step.operations:
            for wire in op['result']['products']:
                product=as_molecule(wire)
                products[product.record_version]=product
    used={}
    def visit(version):
        if version in used or version not in products:return
        material=products[version]
        used[version]=material
        for reference in material.source_refs:visit(reference['record_version'])
    visit(candidate.record_version)
    return used


def file_subjects(steps,candidate):
    """Owned bundle paths follow the shared writer, never arbitrary known DNA."""
    from core.tools.snapgene_io import annotate_record_primers
    subjects={f'construct.{extension}':candidate for extension in ('gb','dna','fasta')}
    for index,(version,product) in enumerate(_used_products(steps,candidate).items()):
        if version==candidate.record_version:continue
        for extension in ('gb','dna'):
            subjects[f'actual_intermediates/intermediate_{index:03d}.{extension}']=product
    for index,row in enumerate(preparation_rows(steps,candidate),1):
        product=as_molecule(row['product'])
        annotated=annotate_record_primers(as_molecule(row['template']),row['primers'])
        for extension in ('gb','dna','fasta'):
            subjects[f'intermediates/preparation_{index:02d}.{extension}']=product
        for extension in ('gb','dna'):
            subjects[f'annotated_sources/preparation_{index:02d}_source.{extension}']=annotated
    return subjects


def order_rows(primers):
    rows=[]
    identifiers={}
    for p in primers:
        row={'name':p.get('name','oligo'),'sequence_5to3':p.get('sequence') or p.get('sequence_5to3') or p.get('seq'),
             'role':p.get('role','preparation')}
        if row['name'] in identifiers and identifiers[row['name']] != row['sequence_5to3']:
            raise ValidationError('ORDER_IDENTIFIER_CONFLICT','Different oligos share order identifier: '+str(row['name']))
        identifiers[row['name']]=row['sequence_5to3']
        if row not in rows:rows.append(row)
    return rows


def synthesis_orders(steps,candidate):
    """Order actual single-strand inputs to consumed Core annealing reactions."""
    used=_used_products(steps,candidate)
    orders=[]
    for step in steps:
        for operation in step.operations:
            if operation['method']!='anneal_oligos' or not any(p['record_version'] in used for p in operation['result']['products']):
                continue
            for side in ('top_oligo','bottom_oligo'):
                material=as_molecule(operation['params'][side])
                orders.append({'name':step.step_id+'_'+side,'sequence':str(material.seq),'role':'synthesis'})
    return order_rows(orders)


def render_design(material,result_kind,steps,orders,requirements=None,quality=None,verification_quality=None,report_notes=None):
    document=['# Current design and preparation',f'Product: {len(material)} bp; topology: {material.topology}; role: {result_kind}.',
              '## Actual steps']
    if report_notes:
        document[0:0]=['# 设计说明',report_notes,
            '以下说明由调用者提交；文件核查确认它与本次交付绑定，科学说明需结合下方实际检查范围复核。']
    document.extend(f'{i+1}. {step.method} ({step.step_id}).' for i,step in enumerate(steps))
    document.append('## Final oligos')
    document.extend(f'{row["name"]}: {row["sequence_5to3"]} ({row["role"]}).' for row in orders)
    if requirements is not None:
        document.append('## Original request and declared constraints')
        for name in ('original_request', 'description', 'topology'):
            if requirements.get(name): document.append(f'{name}: {requirements[name]}')
        for name in ('expected_components', 'forbidden_components'):
            for item in requirements.get(name, []):
                descriptor = item if isinstance(item, str) else item.get('name', 'explicit sequence component')
                source = item.get('source_id') if isinstance(item, dict) else None
                document.append(f'{name}: {descriptor}' + (f' (source: {source})' if source else ''))
        document.append('Checks cover declared computable constraints. Free-text meaning and experimental phenotype are not automatically verified.')
    if quality is not None:
        document.append('## Preparation oligo quality')
        document.append(f'Overall: {quality["status"]}. Reaction replay and oligo quality are separate checks.')
        document.extend(f'{row.get("id")}: {row["status"]} ({row["method"]}).' for row in quality['checks'])
        document.append('Measurements/conditions are in preparation_quality.json; experimental efficiency is not established.')
    if verification_quality is not None:
        document.extend(['## Verification oligo checks',f'Final QC screening: {verification_quality["status"]}.',
                         'Full metrics, actual parent predictions and conditional read coverage: verification_quality.json.'])
        for assay in verification_quality['assays']:
            parental=assay['parental_pcr']
            document.append(f'{assay["step_id"]}: parent background {parental["status"]}.')
            for row in parental.get('templates',[]):
                document.append(f'{row["template"]}: {row["status"]}; predicted lengths {row["product_lengths_bp"]} bp.')
        document.append('A passed oligo screen does not establish observed sequencing or genomic integration. The actual scope and original-request boundary are in validation.json.')
    for step in steps:document.extend(str(p.get('action',p)) for p in step.result.analysis.get('protocol_steps',[]))
    return '\n\n'.join(document)+'\n'


def deliver_result(requirements,sources,steps,candidate,out_dir,*,primers=None,result_kind='construct',
                   required_scopes=None,validation=None,output_step=None,product_index=None,provenance=None,sanity_context=None,report_notes=None):
    """Recheck actual work and publish a coherent bundle; supplied PASS cannot authorize it."""
    from core.preparation import write_preparation_artifacts
    from core.tools import export_snapgene
    from core.runtime_gate import _promote_verified_candidate
    from core.requirements import inherit_requirements, validate_validation_options
    requirements=inherit_requirements(steps,requirements)
    validate_validation_options(required_scopes, result_kind)
    mandatory=['sequence_model','file','user_goal']
    if result_kind=='construct':mandatory.insert(1,'preparation_model')
    # A caller may request extra checks, but cannot subtract the role's checks.
    # Recheck them rather than rejecting an otherwise valid prepared molecule.
    required_scopes=list(dict.fromkeys(mandatory+(required_scopes or [])))
    material=as_molecule(candidate)
    if validation is not None:
        payload={k:v for k,v in validation.items() if k!='validation_sha256'}
        if validation.get('validation_sha256')!=_digest(payload):
            raise GateRejected('GATE_STALE_VALIDATION','Validation content changed')
        if (validation['subject_version']!=material.record_version or validation['requirements']!=requirements
                or validation['steps_sha256']!=_digest([_step(s).to_dict() for s in steps])
                or validation['primers']!=(primers or []) or validation['result_kind']!=result_kind
                or validation.get('report_notes')!=report_notes):
            raise GateRejected('GATE_STALE_VALIDATION','Candidate, parameters, request or final oligos changed')
        for name,path in validation.get('file_paths',{}).items():
            path=Path(path)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=validation['artifact_hashes'].get(name):
                raise GateRejected('GATE_STALE_VALIDATION','Checked file changed: '+name)
    out=Path(out_dir).resolve()
    out.mkdir(parents=True,exist_ok=True)
    bundle=Path(tempfile.mkdtemp(prefix='candidate-',dir=out))
    try:
        replayed=replay_steps(steps,sources)
        rows=preparation_rows(replayed,material)
        preparation=write_preparation_artifacts(rows,bundle)
        files=export_snapgene(material,bundle,filename_base='construct').analysis
        from Bio import SeqIO
        with (bundle/'construct.fasta').open('w',encoding='utf-8') as handle:
            SeqIO.write(material,handle,'fasta')
        files['fasta_file']=str(bundle/'construct.fasta')
        used=_used_products(replayed,material)
        exported=set()
        for index,(version,product) in enumerate(used.items()):
            if version==material.record_version:continue
            export_snapgene(product,bundle/'actual_intermediates',filename_base=f'intermediate_{index:03d}')
            exported.add(version)
        # The same owned rows generate source maps, preparation details and
        # purchase entries. Do not collect their generic analysis aliases again.
        orders=[{**p,'source_step':row['source_step'],'role':'preparation'} for row in rows for p in row['primers']]
        represented={(row['source_step'],p.get('sequence') or p.get('sequence_5to3') or p.get('seq'))
                     for row in rows for p in row['primers']}
        for step in replayed:
            kind=step.result.analysis.get('result_kind')
            if kind != 'verification' and not any(p.record_version in used for p in step.result.products):
                continue
            for p in step.result.analysis.get('primers',[]):
                if isinstance(p,dict) and (kind=='verification' or
                        (step.step_id,p.get('sequence') or p.get('sequence_5to3') or p.get('seq')) not in represented):
                    orders.append({**p,'source_step':step.step_id,'role':'qc' if kind=='verification' else 'preparation'})
        orders.extend(synthesis_orders(replayed,material))
        if primers is not None:
            orders=primers
        else:
            # Separate assays often emit the same generic names. Namespace only conflicts.
            names={}
            for p in orders:names.setdefault(p.get('name','oligo'),set()).add(p.get('sequence') or p.get('sequence_5to3') or p.get('seq'))
            orders=[{**p,'name':str(p['source_step'])+'_'+p.get('name','oligo')}
                    if len(names[p.get('name','oligo')])>1 and p.get('source_step') else p for p in orders]
        # One data object generates both order table and prose, never independent copies.
        ordered=order_rows(orders)
        order_path=bundle/'oligo_order_table.tsv'
        with order_path.open('w',encoding='utf-8',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=['name','sequence_5to3','role'],delimiter='\t')
            writer.writeheader();writer.writerows(ordered)
        from core.preparation import check_verification_quality
        verification_quality=check_verification_quality(ordered,material,replayed)
        (bundle/'verification_quality.json').write_text(json.dumps(verification_quality,ensure_ascii=False,indent=2),encoding='utf-8')
        (bundle/'design.md').write_text(render_design(material,result_kind,replayed,ordered,requirements,preparation['quality'],verification_quality,report_notes),encoding='utf-8')
        (bundle/'execution.json').write_text(json.dumps([s.to_dict() for s in replayed],ensure_ascii=False,indent=2),encoding='utf-8')
        (bundle/'requirements.json').write_text(json.dumps(requirements,ensure_ascii=False,indent=2),encoding='utf-8')
        checked_files={str(path.relative_to(bundle)).replace('\\','/'):str(path)
                       for path in bundle.rglob('*') if path.is_file()}
        report=validate_candidate(requirements,sources,replayed,material,primers=ordered,files=checked_files,
                   required_scopes=required_scopes,result_kind=result_kind,output_step=output_step,product_index=product_index,
                   sanity_context=sanity_context,report_notes=report_notes)
        (bundle/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        if report['overall']!='verified':
            raise GateRejected('GATE_WORKFLOW_INCOMPLETE','Current execution/files failed requested scope checks',
                               details={'candidate_directory':str(bundle),'validation':report})
        # Intermediate files bind their own material, rather than being compared to the final DNA.
        hashes={str(path.relative_to(bundle)).replace('\\','/'):hashlib.sha256(path.read_bytes()).hexdigest()
                for path in bundle.rglob('*') if path.is_file()}
        delivery=_promote_verified_candidate(Path(files['gb_file']),Path(files['fasta_file']),out,
            {'schema_version':'workflow-delivery-v1','artifact_class':'authoritative','result_kind':result_kind,'provenance':provenance or {},
             'requirements':requirements,'scope_results':report['scope_results'],'validation_sha256':report['validation_sha256'],
             'goal_coverage':report['goal_coverage'],'task_completion':report['task_completion'],
             'subject_version':material.record_version,'source_versions':report['source_versions']},
            bundle_dir=bundle,bundle_files=hashes,candidate_dna=Path(files['dna_file']))
        return {**delivery,'validation':report,'goal_coverage':report['goal_coverage'],'task_completion':report['task_completion'],
                'candidate_directory':str(bundle),'preparation_files':preparation}
    except Exception as exc:
        (bundle/'failure.json').write_text(json.dumps({'status':'failed','message':str(exc)},ensure_ascii=False,indent=2),encoding='utf-8')
        raise
