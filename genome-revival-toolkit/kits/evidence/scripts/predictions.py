"""Compare supplied local PCR models with reported observations, never experiments."""
import json
import hashlib
from pathlib import Path
from evidence_trace.models import file_digest, now
from evidence_trace.runtime import observe_source


def read_expected_results(path, context):
    path=Path(path); before=file_digest(path)
    value=json.loads(path.read_text(encoding='utf-8'))
    if value.get('schema_version')!='identity-expected-results-v1' or not isinstance(value.get('rows'),list) or not isinstance(value.get('references'),dict):
        raise ValueError('Unsupported Identity expected-results format; no prediction format was guessed.')
    for key,binding in value['references'].items():
        if not isinstance(binding,dict):raise ValueError('Expected-results reference binding must be an object.')
        actual=context.reference_info(key)
        if any(binding.get(field)!=actual[field] for field in ('file_sha256','record_id','region','topology')) or ('record_version' in binding and binding['record_version']!=actual['record_version']):
            raise ValueError('Expected-results reference version changed: '+key)
    seen=set()
    for row in value['rows']:
        if not isinstance(row,dict):raise ValueError('Expected-results row must be an object.')
        key=(row.get('assay_id'),row.get('reference_id'))
        if not all(isinstance(k,str) and k for k in key) or key in seen or key[1] not in value['references']:
            raise ValueError('Expected-results rows need unique assay/reference IDs with supplied bindings.')
        seen.add(key)
        if row.get('expected') not in ('AMPLICON','NO_EXACT_PRODUCT','NOT_COVERED') or row.get('primer_quality_status') not in ('PASSED','FAILED','INCOMPLETE'):
            raise ValueError('Expected-results row has an unsupported prediction or quality state.')
        size=row.get('size_bp')
        if (row['expected']=='AMPLICON' and (type(size) is not int or size<=0)) or (row['expected']!='AMPLICON' and size is not None):
            raise ValueError('Expected-results band size contradicts its stated prediction.')
    if file_digest(path)!=before:raise ValueError('Expected-results file changed while reading.')
    observe_source({'kind':'source','id':'S-predictions-'+before[:20],'title':'Supplied PCR prediction table',
        'source_type':'provided-prediction-table','path':str(path.resolve()),'source_sha256':before,'verification_status':'verified',
        'verification':{'verifier':'Evidence local file observer','method':'SHA-256 and supplied reference-file binding',
            'checked_at':now(),'locator':str(path.resolve()),'scope':'File bytes/reference selection only; neither experimental observations nor scientific correctness are authenticated.'}})
    return {'table':value,'input_file':{'path':str(path.resolve()),'sha256':before}}


def read_bound_observations(path, reader):
    before=file_digest(path); result=reader(path)
    if result['sha256']!=before or file_digest(path)!=before:
        raise ValueError('Reported observation file changed while reading.')
    observe_source({'kind':'source','id':'S-observations-'+before[:20],'title':'Researcher-reported observation file',
        'source_type':'researcher-reported-observations','path':str(Path(path).resolve()),'source_sha256':before,
        'verification_status':'unverified','scope':'File bytes are recorded. Counts, measurements and control statements are submitted records, not authenticated experiments.'})
    return result


def observe_reported_bands(rows):
    if not rows:return
    identity=hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()
    observe_source({'kind':'source','id':'S-reported-bands-'+identity[:20],'title':'Researcher-reported inline band/control declarations',
        'source_type':'researcher-reported-observations','verification_status':'unverified','record_count':len(rows),
        'scope':'Inline submitted declarations; no file hash or independent measurement authentication.'})


def _assessment(model, observation):
    if observation is None or observation['result']=='not_tested':return 'NOT_TESTED','No band observation was supplied for this assay.'
    if model is None or model['expected']=='NOT_COVERED':return 'INSUFFICIENT','This assay/reference is not covered by an exact prediction.'
    if model['primer_quality_status']!='PASSED':return 'INSUFFICIENT','The prediction does not have passing complete-primer quality.'
    if observation.get('control_status')!='passed':return 'INSUFFICIENT','Passing assay controls were not reported; absence/presence is not interpretable here.'
    if observation['result']=='indeterminate':return 'INSUFFICIENT','The reported band observation is indeterminate.'
    if observation['result']=='negative':
        if observation.get('observed_band_bp') is not None:raise ValueError('A negative band observation cannot also state a band size.')
        return ('SUPPORTED','Reported absence agrees with the supplied exact-PCR prediction under reported controls.') if model['expected']=='NO_EXACT_PRODUCT' else ('CONTRADICTED','A predicted band was reported absent under reported passing controls.')
    size=observation.get('observed_band_bp'); tolerance=observation.get('band_tolerance_bp',0)
    if size is None:return 'INSUFFICIENT','A positive band was reported without its size.'
    if type(size) is not int or size<=0 or type(tolerance) is not int or tolerance<0:
        raise ValueError('observed_band_bp must be a positive integer; band_tolerance_bp a nonnegative integer.')
    if model['expected']=='NO_EXACT_PRODUCT':return 'CONTRADICTED','A band was reported where the supplied model predicts no exact product.'
    if abs(size-model['size_bp'])<=tolerance:return 'SUPPORTED','Reported band size agrees with the supplied local prediction and explicit size tolerance.'
    return 'CONTRADICTED','Reported band size differs from the supplied local prediction beyond the explicit size tolerance.'


def compare_expected(table, genotypes, observed_counts):
    expected={(row['assay_id'],row['reference_id']):row for row in table['rows']}
    rows=[]; observed=set()
    for row in genotypes:
        key=(row.get('assay_id'),row['reference_id'])
        status,reason=_assessment(expected.get(key),row)
        rows.append({'sample_id':row['sample_id'],'assay_id':key[0],'reference_id':key[1],
                     'status':status,'reason':reason,'observed_band_bp':row.get('observed_band_bp'),
                     'expected_size_bp':expected.get(key,{}).get('size_bp')})
        row['reported_record_assessment']=row['assessment'];row['assessment']=status
        row['prediction_comparison']=rows[-1]
        observed.add((row['sample_id'],key[0],key[1]))
    for sample,reference in {(row['sample_id'],row['reference_id']) for row in genotypes}:
        for (assay,ref),model in expected.items():
            if ref==reference and (sample,assay,ref) not in observed:
                rows.append({'sample_id':sample,'assay_id':assay,'reference_id':ref,'status':'NOT_TESTED',
                             'reason':'No observation was supplied for this predicted assay.'})
    if not genotypes:
        rows=[{'sample_id':None,'assay_id':assay,'reference_id':ref,'status':'NOT_TESTED',
               'reason':'No genotype band observation was supplied.'} for assay,ref in expected]
    states=[row['status'] for row in rows]
    status=('CONTRADICTED' if 'CONTRADICTED' in states else
            'INSUFFICIENT' if 'INSUFFICIENT' in states or ('SUPPORTED' in states and 'NOT_TESTED' in states) else
            'SUPPORTED' if states and all(state=='SUPPORTED' for state in states) else
            'INSUFFICIENT' if observed_counts and not genotypes else 'NOT_TESTED')
    return {'status':status,'rows':rows,
            'not_tested_assays':sorted({row['assay_id'] for row in rows if row['status']=='NOT_TESTED' and row['assay_id']}),
            'reason':'Colony counts alone do not test the predicted PCR assays.' if observed_counts and not genotypes else
                     'Comparison of supplied local predictions with researcher-reported bands/controls only.',
            'scope':'Consistency under declared model/assay conditions; not authenticated experiments, whole-genome identity, revival or elimination.'}
