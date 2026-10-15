"""Literal existing evidence boundaries; no experiment or implementation-derived oracle."""
from repository_paths import PROJECT_ROOT
import json
import sys
import unittest

sys.path.insert(0,str(PROJECT_ROOT/'genome-revival-toolkit'))
from revival.evidence import conclusion_rows


class EvidenceConclusionDataTests(unittest.TestCase):
    def test_all_existing_observation_states_keep_their_bounded_statuses(self):
        cases=[
            (False,False,['NOT_TESTED','NOT_TESTED']),
            (True,False,['INSUFFICIENT','NOT_TESTED']),
            (False,True,['INSUFFICIENT','INSUFFICIENT']),
            (True,True,['INSUFFICIENT','INSUFFICIENT'])]
        for counts,genetics,expected in cases:
            with self.subTest(counts=counts,genetics=genetics):
                self.assertEqual([row['status'] for row in conclusion_rows(counts,genetics)],expected)

    def test_each_loaded_conclusion_row_has_a_declared_contract_source(self):
        path=PROJECT_ROOT/'genome-revival-toolkit/kits/evidence/rules/conclusions.json'
        table=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(len(table['rules']),2)
        for row in table['rules']:
            self.assertEqual(row['source']['type'],'project_contract')
            self.assertTrue(row['source']['reference'].strip())
            self.assertTrue(row['source']['description'].strip())
        self.assertNotIn('SUPPORTED',[status for row in table['rules'] for status in row['status_by_state']])
