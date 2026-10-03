
from repository_paths import PROJECT_ROOT, SKILL_ROOT, TOOLS_ROOT, RUNTIME_SCRIPTS
import unittest
from tools.summarize_host_scores import summarize, FIELDS


class HostScoreSummaryTests(unittest.TestCase):
    @staticmethod
    def row():
        return dict(task_id='case',run_id='1',model='test_model',skill_version='test_version',
                    human_interventions='0',
                    evaluation_kind='heldout',input_condition='original',
                    isolation_status='verified',freeze_record='synthetic-examiner-freeze.json',
                    evidence='independent-check.json',**{f:'PASS' for f in FIELDS})

    def test_correct_dna_does_not_compensate_for_failed_preparation(self):
        row=self.row()
        row['preparation']='FAIL'
        result=summarize([row],{'case':list(FIELDS)})
        self.assertEqual(result['groups'][0]['success_rate'],0)
        self.assertEqual(result['runs'][0]['verdict'],'FAILED')

    def test_unreviewed_item_has_no_final_success_rate(self):
        row=self.row()
        row['verification']='UNREVIEWED'
        self.assertIsNone(summarize([row],{'case':list(FIELDS)})['groups'][0]['success_rate'])

    def test_required_check_cannot_be_declared_not_applicable(self):
        row=self.row()
        row['preparation']='NOT_APPLICABLE'
        with self.assertRaisesRegex(ValueError,'cannot be omitted'):
            summarize([row],{'case':list(FIELDS)})

    def test_missing_task_and_uneven_repeats_are_not_a_complete_benchmark(self):
        row=self.row()
        self.assertIsNone(summarize([row],{'case':list(FIELDS),'other':list(FIELDS)})['groups'][0]['success_rate'])
        extra={**row,'run_id':'2'}
        other={**row,'task_id':'other'}
        self.assertIsNone(summarize([row,extra,other],{'case':list(FIELDS),'other':list(FIELDS)})['groups'][0]['success_rate'])

    def test_stability_is_reported_only_after_independent_repeats(self):
        row=self.row()
        rule={'case':list(FIELDS)}
        self.assertIsNone(summarize([row],rule)['groups'][0]['all_repeats_success_task_fraction'])
        second={**row,'run_id':'2','goal':'FAIL'}
        group=summarize([row,second],rule)['groups'][0]
        self.assertEqual(group['success_rate'],0.5)
        self.assertEqual(group['all_repeats_success_task_fraction'],0)

    def test_empty_rubric_and_missing_evidence_cannot_pass(self):
        row=self.row()
        with self.assertRaisesRegex(ValueError,'Invalid required'):
            summarize([row],{'case':[]})
        row['evidence']=''
        with self.assertRaisesRegex(ValueError,'Missing examiner evidence'):
            summarize([row],{'case':list(FIELDS)})

    def test_assistance_is_not_independent_success_and_unknown_is_not_zero(self):
        row={**self.row(),'human_interventions':'1'}
        result=summarize([row],{'case':list(FIELDS)})
        self.assertEqual(result['runs'][0]['verdict'],'ASSISTED')
        self.assertEqual(result['groups'][0]['success_rate'],0)
        row['human_interventions']=''
        result=summarize([row],{'case':list(FIELDS)})
        self.assertEqual(result['runs'][0]['verdict'],'UNREVIEWED')
        self.assertIsNone(result['groups'][0]['success_rate'])
