"""Required scoped checks recomputed on the actual candidate through Core."""
import json
from pathlib import Path
from core.tools.grna import check_grna
from core.tools.grna_evaluation import check_grna_vector
from core.tools.result import check_result


def evaluate(*,candidate,sources,requirements,steps,inputs):
    request=json.loads(Path(inputs['request_file']).read_text(encoding='utf-8-sig')) if inputs.get('request_file') else inputs.get('request',{})
    selectors={key:request[key] for key in ('promoter_name','promoter_end_0based','transcription_strand','scaffold_seq') if key in request}
    guide=check_grna(candidate,sources['target'],**selectors).analysis
    vector=check_grna_vector(guide['spacer'],candidate,max_mismatches=request.get('max_mismatches',3)).analysis
    direction=guide['direction_status']=='CORRECT' and guide['orientation_distinguishable'] and guide['valid_target_locus_count']==1
    pam=guide['valid_target_locus_count']==1 and any(hit['pam_valid'] for hit in guide['target_matches'])
    self_ok=vector['self_target_status']=='NO_MATCH_IN_SEARCH_SCOPE'
    return [check_result('mandatory_direction',subject=candidate,status='PASSED' if direction else 'FAILED',scope='direction',details=guide),
            check_result('mandatory_pam',subject=candidate,status='PASSED' if pam else 'FAILED',scope='pam',details=guide),
            check_result('mandatory_vector_self_target',subject=candidate,status='PASSED' if self_ok else 'FAILED',scope='vector_self_target',details=vector)]


def context_for_result(request,result,context,out_dir):
    return result.pop('_kit_gate_context')
