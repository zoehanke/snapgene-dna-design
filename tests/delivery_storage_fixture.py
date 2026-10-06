"""Keep original storage-gate inputs after sanity-only delivery is retired.

These fixtures never had reaction evidence. Assert public rejection first; then
exercise storage, conflicts and desktop checks independently. Actual public
reaction/delivery success is tested in test_execution_closure.
"""
from pathlib import Path
from core.runtime_gate import finalize_candidate_construct, _promote_verified_candidate, GateRejected


def storage_delivery(candidate_gb,candidate_fasta,out_dir,metadata,sanity_check,user_confirmed=False):
    try:
        finalize_candidate_construct(candidate_gb,candidate_fasta,out_dir,metadata,sanity_check,user_confirmed)
    except GateRejected as error:
        if error.error_code!='GATE_EXECUTION_EVIDENCE_REQUIRED':raise
    else:
        raise AssertionError('Sanity-only evidence unexpectedly authorized delivery')
    return _promote_verified_candidate(Path(candidate_gb),Path(candidate_fasta),out_dir,
        {'schema_version':'storage-fixture','scope_note':'Storage check only; not preparation evidence'},
        temp_identifier=str(metadata.get('recipe','fixture')))
