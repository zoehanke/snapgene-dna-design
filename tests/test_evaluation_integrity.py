"""Independent examiner metadata cases, not simulated biological successes."""

from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import unittest

from tools.summarize_host_scores import FIELDS, aggregate_feedback, summarize


class EvaluationIntegrityTests(unittest.TestCase):
    @staticmethod
    def row():
        return dict(task_id='independent_case', run_id='1', model='declared_model',
                    skill_version='declared_version', human_interventions='0',
                    evidence='examiner-record.json', **{field:'PASS' for field in FIELDS})

    def test_complete_checks_without_evaluation_provenance_are_not_a_formal_rate(self):
        result=summarize([self.row()], {'independent_case':list(FIELDS)})
        self.assertIsNone(result['groups'][0]['success_rate'])

    def test_shared_directory_pilot_is_not_isolated_heldout_evaluation(self):
        row={**self.row(),'evaluation_kind':'host_pilot','input_condition':'original',
             'isolation_status':'unverified','freeze_record':''}
        result=summarize([row], {'independent_case':list(FIELDS)})
        self.assertIsNone(result['groups'][0]['success_rate'])

    def test_a_contaminated_run_cannot_count_as_heldout_success(self):
        row={**self.row(),'evaluation_kind':'heldout','input_condition':'original',
             'isolation_status':'contaminated','freeze_record':'freeze-record.json'}
        result=summarize([row], {'independent_case':list(FIELDS)})
        self.assertIsNone(result['groups'][0]['success_rate'])

    def test_declared_heldout_success_requires_original_inputs_and_a_freeze(self):
        row={**self.row(),'evaluation_kind':'heldout','input_condition':'original',
             'isolation_status':'verified','freeze_record':'synthetic-freeze.json'}
        self.assertEqual(summarize([row],{'independent_case':list(FIELDS)})['groups'][0]['success_rate'],1)
        for change in ({'input_condition':'corrected'},{'freeze_record':''},{'isolation_status':'unverified'}):
            result=summarize([{**row,**change}],{'independent_case':list(FIELDS)})
            self.assertIsNone(result['groups'][0]['success_rate'])

    def test_regression_and_heldout_runs_do_not_mix(self):
        row={**self.row(),'evaluation_kind':'heldout','input_condition':'original',
             'isolation_status':'verified','freeze_record':'synthetic-freeze.json'}
        regression={**row,'evaluation_kind':'development_regression','run_id':'2'}
        result=summarize([row,regression],{'independent_case':list(FIELDS)})
        self.assertEqual(len(result['groups']),2)
        by_kind={g['evaluation_kind']:g for g in result['groups']}
        self.assertIsNone(by_kind['development_regression']['success_rate'])
        self.assertEqual(by_kind['heldout']['runs'],1)

    def test_contaminated_run_is_retained_and_reported_outside_the_denominator(self):
        row={**self.row(),'evaluation_kind':'heldout','input_condition':'original',
             'isolation_status':'verified','freeze_record':'synthetic-freeze.json'}
        contaminated={**row,'run_id':'2','isolation_status':'contaminated','goal':'FAIL'}
        result=summarize([row,contaminated],{'independent_case':list(FIELDS)})
        self.assertEqual(len(result['runs']),2)
        self.assertEqual(result['groups'][0]['recorded_runs'],2)
        self.assertEqual(result['groups'][0]['contaminated'],1)
        self.assertEqual(result['groups'][0]['runs'],1)
        self.assertEqual(result['groups'][0]['success_rate'],1)

    def test_unreviewed_required_item_is_still_not_success(self):
        row={**self.row(),'evaluation_kind':'heldout','input_condition':'original',
             'isolation_status':'verified','freeze_record':'synthetic-freeze.json','files':'UNREVIEWED'}
        self.assertIsNone(summarize([row],{'independent_case':list(FIELDS)})['groups'][0]['success_rate'])

    def test_developer_feedback_omits_task_identity_and_answer_paths(self):
        import json
        row={**self.row(),'task_id':'private_case_identity','goal':'FAIL',
             'evaluation_kind':'heldout','input_condition':'original','isolation_status':'verified',
             'freeze_record':'private_freeze_location','evidence':'private_answer_location'}
        result=aggregate_feedback(summarize([row],{'private_case_identity':list(FIELDS)}))
        rendered=json.dumps(result)
        for private in ('private_case_identity','private_freeze_location','private_answer_location'):
            self.assertNotIn(private,rendered)
        self.assertEqual(result['groups'][0]['failure_categories']['goal'],1)
