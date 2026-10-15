"""Export actual donor-QC pairs for a separately supplied reference comparison."""
import json
from pathlib import Path
from evidence_trace.models import file_digest


def validate_options(options, context):
    if not isinstance(options,dict) or set(options)-{'references','size_resolution_bp'}:
        raise ValueError('identity_handoff needs references and optional size_resolution_bp.')
    ids=options.get('references')
    if not isinstance(ids,list) or not ids or any(not isinstance(key,str) or key not in context.references for key in ids) or len(set(ids))!=len(ids):
        raise ValueError('identity_handoff.references must identify distinct supplied Context references.')
    resolution=options.get('size_resolution_bp')
    if resolution is not None and (type(resolution) is not int or resolution<=0):
        raise ValueError('identity_handoff.size_resolution_bp must be a positive integer.')
    return ids


def write_handoff(options, context, steps_file, out_dir, original_request):
    ids=validate_options(options,context)
    steps=json.loads(Path(steps_file).read_text(encoding='utf-8'))['steps']
    assays=[]
    for step in steps:
        if step.get('error') or step.get('method')!='recipe_cloning_verification':continue
        rows=[row for row in step['result']['analysis'].get('primers',[]) if row.get('role')=='colony_pcr_screening']
        forward=[row for row in rows if row.get('strand')==1]
        reverse=[row for row in rows if row.get('strand')==-1]
        if len(forward)!=1 or len(reverse)!=1:
            raise ValueError('Construct QC has no single unambiguous screening pair; handoff was not guessed.')
        assay={'id':step['step_id'],'forward':forward[0]['sequence'],'reverse':reverse[0]['sequence']}
        if options.get('size_resolution_bp') is not None:assay['size_resolution_bp']=options['size_resolution_bp']
        assays.append(assay)
    if not assays:raise ValueError('No actual completed donor-QC pairs are available for Identity.')
    out_dir=Path(out_dir); handoff=out_dir/'identity-handoff.json'; request=out_dir/'identity-request.json'
    bindings={key:context.reference_info(key) for key in ids}
    payload={'schema_version':'construct-identity-handoff-v1','references':bindings,'assays':assays,
             'scope':'Actual donor-QC candidates; Identity must recheck these against the explicitly supplied reference models. No experimental genotype is established.',
             'laboratory_status':'PLANNED','wet_lab':'NOT_PERFORMED'}
    next_request={'original_request':original_request,
                  'references':ids,'compare_regions':False,'construct_handoff_file':str(handoff.resolve()),'export_expectations':True}
    receipts=[]
    for path,value in ((handoff,payload),(request,next_request)):
        count=path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        receipts.append({'path':str(path.resolve()),'sha256':file_digest(path),'characters_written':count})
    return {'paths':[str(handoff.resolve()),str(request.resolve())],'write_receipts':receipts,
            'file':str(handoff.resolve()),'request_file':str(request.resolve()),'scope':payload['scope']}
