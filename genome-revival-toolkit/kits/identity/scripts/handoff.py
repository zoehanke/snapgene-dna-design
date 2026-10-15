"""Optional version-bound donor-QC input and explicit PCR expectation export."""
import json
from pathlib import Path
from evidence_trace.models import file_digest


def read_construct_handoff(path, context, ids):
    path=Path(path); before=file_digest(path)
    value=json.loads(path.read_text(encoding='utf-8'))
    if value.get('schema_version')!='construct-identity-handoff-v1' or not isinstance(value.get('assays'),list):
        raise ValueError('Unsupported Construct handoff format; no assay format was guessed.')
    bindings=value.get('references')
    if not isinstance(bindings,dict) or set(bindings)-set(ids):
        raise ValueError('Construct handoff references must be explicitly selected in Identity.')
    for key,binding in bindings.items():
        if not isinstance(binding,dict):raise ValueError('Construct handoff reference binding must be an object.')
        actual=context.reference_info(key)
        if any(binding.get(field)!=actual[field] for field in ('file_sha256','record_id','region','topology')) or ('record_version' in binding and binding['record_version']!=actual['record_version']):
            raise ValueError('Construct handoff reference version changed: '+key)
    if file_digest(path)!=before:raise ValueError('Construct handoff changed while reading.')
    return {'assays':value['assays'],'input_file':{'path':str(path.resolve()),'sha256':before}}


def expectation_table(assays, references):
    rows=[]
    for assay in assays:
        for prediction in assay['predictions']:
            state=prediction['prediction']
            expected=state if state in ('AMPLICON','NO_EXACT_PRODUCT') else 'NOT_COVERED'
            rows.append({'assay_id':assay['id'],'reference_id':prediction['reference'],'expected':expected,
                         'size_bp':prediction.get('amplicon_length_bp') if expected=='AMPLICON' else None,
                         'primer_quality_status':assay['quality_status'],
                         'discrimination_status':assay['discrimination']['status'],
                         'interpretation_if_observed':'Consistent local bands can support this supplied-reference comparison only under the stated assay/control conditions; no whole-genome or experimental identity is proved.'})
    return {'schema_version':'identity-expected-results-v1',
            'scope':'Exact PCR predictions on supplied reference models, not measured bands or experimental genotypes.',
            'references':{row['id']:{key:row[key] for key in ('file_sha256','record_id','region','topology','record_version')} for row in references},
            'rows':rows,'laboratory_status':'PLANNED','wet_lab':'NOT_PERFORMED'}
