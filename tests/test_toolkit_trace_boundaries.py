import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'snapgene-dna-design'))
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.SeqFeature import SeqFeature, FeatureLocation
from core.models.molecule import as_molecule
from core.workflow import run_step
from core.workflow_delivery import deliver_result
from core.tools.snapgene_io import export_snapgene
from evidence_trace.models import snapshot
from evidence_trace.reader import check_status
from evidence_trace.runtime import TraceRun
from evidence_trace.recorder import load_events, project


class ToolkitTraceBoundaryTests(unittest.TestCase):
    def test_direct_material_snapshot_keeps_version_annotations_and_ends(self):
        source = as_molecule(SeqRecord(Seq('ACGT' * 20), id='annotated',
                             annotations={'topology': 'linear', 'molecule_type': 'DNA'},
                             features=[SeqFeature(FeatureLocation(4, 20, strand=-1), type='misc_feature', qualifiers={'label': ['part']})]))
        data = snapshot(source)
        self.assertEqual(data['record_version'], source.record_version)
        self.assertEqual(data['features'][0]['location']['parts'][0]['strand'], -1)
        self.assertIn('ends', data)
        self.assertEqual(data['sequence']['length'], 80)

    def test_actual_core_status_enums_are_read_without_changing_semantics(self):
        self.assertEqual(check_status('PASSED')[0], 'passed')
        self.assertEqual(check_status('FAILED')[0], 'failed')
        self.assertEqual(check_status('INCOMPLETE')[0], 'unknown')

    def test_nested_actual_delivery_is_formal_and_plain_export_is_not(self):
        source = as_molecule(SeqRecord(Seq('ACGT' * 20), id='s', annotations={'topology': 'linear', 'molecule_type': 'DNA'}))
        requirements = {'expected_components': [{'sequence': 'ACGT' * 12}]}
        with tempfile.TemporaryDirectory() as temp:
            out = pathlib.Path(temp)
            run = TraceRun(out, 'toolkit', level='observed')
            try:
                step = run_step('extract_subsequence', {'file_path_or_record': source, 'start': 0, 'end': 48},
                                step_id='part', sources={'s': source}, requirements=requirements)
                result = deliver_result(requirements, {'s': source}, [step], step.result.only_product(),
                                        out / 'nested' / 'delivery', result_kind='component')
                run.capture('outcome', result)
                exported = export_snapgene(source, out / 'authoritative').analysis
                run.capture('candidate_files', exported)
            finally:
                run.close()
            graph = project(load_events(run.directory)[0])
            files = [n for n in graph['nodes'] if n['kind'] == 'artifact' and n['role'] == 'authoritative']
            self.assertEqual({pathlib.Path(n['path']).suffix for n in files}, {'.gb', '.dna', '.fasta'})
            self.assertTrue(all(n['result_event_ref'] for n in files))
            # Trace records canonical paths; Windows TEMP can use an 8.3 alias.
            plain = [n for n in graph['nodes'] if n['kind'] == 'artifact' and pathlib.Path(n['path']).parent == (out / 'authoritative').resolve()]
            self.assertTrue(plain)
            self.assertTrue(all(n['role'] != 'authoritative' for n in plain))


if __name__ == '__main__':
    unittest.main()
