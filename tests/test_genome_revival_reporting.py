"""Human summaries reflect actual returns, not exemplar lengths or blanket success."""
from repository_paths import PROJECT_ROOT
import sys
import unittest
sys.path.insert(0, str(PROJECT_ROOT / 'genome-revival-toolkit'))
from revival.reporting import _returned_text, LABELS


def event(stage, result):
    return {'event_type': 'stage_completed', 'payload': {'stage': stage, 'result': result}}


class GenomeRevivalReportingTests(unittest.TestCase):
    def test_junction_lengths_and_backgrounds_come_from_current_actual_return(self):
        for length, side in ((827, 'left'), (315, 'right')):
            value = {'method': 'recipe_cloning_verification', 'status': 'completed',
                     'result': {'analysis': {'details': {'junction_pcr_primers': {'expected_amplicon_size_bp': length},
                         'parental_pcr': {'templates': [{'status': 'PRODUCT_PREDICTED', 'product_lengths_bp': [length]}]}}}}}
            text = _returned_text(event('construct.' + side + '_boundary_qc', value))
            self.assertIn(str(length), text)
            self.assertIn('背景也有预测产物', text)
            self.assertIn('不是实测PCR', text)
        self.assertNotEqual(LABELS['construct.left_boundary_qc'], LABELS['construct.right_boundary_qc'])

    def test_unknown_background_is_not_called_negative(self):
        value = {'method': 'recipe_cloning_verification', 'status': 'completed',
                 'result': {'analysis': {'details': {'junction_pcr_primers': {'expected_amplicon_size_bp': 450},
                              'parental_pcr': {'templates': [{'status': 'UNKNOWN'}]}}}}}
        text = _returned_text(event('construct.left_boundary_qc', value))
        self.assertIn('尚未完整核查', text)
        self.assertNotIn('未预测产物', text)

    def test_expected_model_is_not_presented_as_actual_preparation(self):
        text = _returned_text(event('construct.model', [{}, {'product': {'expected_length': 998}}]))
        self.assertIn('998', text)
        self.assertIn('这里只建立序列与注释模型', text)

    def test_actual_pcr_candidate_length_is_not_experimental_success(self):
        value = {'method': 'prepare_pcr_fragment', 'status': 'completed',
                 'result': {'products': [{'sequence': {'omitted': 'sequence', 'length': 643}}], 'analysis': {}}}
        text = _returned_text(event('construct.donor_preparation', value))
        self.assertIn('643', text)
        self.assertIn('候选', text)
        self.assertIn('不等于实际实验成功', text)


if __name__ == '__main__':
    unittest.main()
