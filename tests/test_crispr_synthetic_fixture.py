"""Permanent paired regressions through actual native input and saved CLI files."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from Bio import SeqIO
from repository_paths import SKILL_ROOT
from crispr_synthetic_fixture import SEEDS, build_cases, materialize, reverse_complement
from core.tools.registry import TOOL_REGISTRY


class SyntheticCrisprRegressionTests(unittest.TestCase):
    def test_seed_reproducibility_and_independent_construction(self):
        for seed in SEEDS:
            a,b = build_cases(seed),build_cases(seed)
            self.assertEqual(str(a['control'].vector.seq),str(b['control'].vector.seq))
            self.assertEqual(a['reversed'].expressed_spacer,reverse_complement(a['control'].intended_spacer))
            self.assertEqual(a['shifted'].expressed_spacer,str(a['control'].target.seq[a['control'].target_start-1:a['control'].target_start+19]))
        self.assertNotEqual(build_cases(SEEDS[0])['control'].intended_spacer,build_cases(SEEDS[1])['control'].intended_spacer)

    def test_all_five_failure_types_and_controls_through_public_native_cli(self):
        for seed in SEEDS:
            with self.subTest(seed=seed), tempfile.TemporaryDirectory(prefix='synthetic-回归-') as folder:
                root = Path(folder)
                rows = materialize(root/'inputs',seed)
                saved={}
                # Each variant is paired with independently constructed control.
                for name,row in rows.items():
                    case=row['case']
                    config={'method':'check_grna','params':{'vector_record_or_seq':row['vector'],
                        'target_seq_or_file':row['target'],'scaffold_seq':case.scaffold}}
                    cfg=root/(name+'.json')
                    cfg.write_text(json.dumps(config,ensure_ascii=False),encoding='utf-8')
                    run=subprocess.run([sys.executable,'-X','utf8','-B',str(SKILL_ROOT/'scripts/run_step.py'),
                        '--input',str(cfg),'--out-dir',str(root/name)],capture_output=True,text=True,encoding='utf-8')
                    self.assertEqual(run.returncode,0,run.stdout+run.stderr)
                    result=json.loads((root/name/'steps.json').read_text(encoding='utf-8'))['steps'][0]['result']
                    report=result['analysis']; saved[name]=report
                    self.assertEqual(report['spacer'],case.expressed_spacer)
                    self.assertEqual(report['direction_status'],case.expected_direction)
                    if name=='shifted':
                        self.assertEqual(report['target_matches'][0]['pam'],case.expected_pam)
                        self.assertEqual(report['target_matches'][0]['protospacer_parts_0based'],[[case.target_start-1,case.target_start+19]])
                    if name in ('shifted','reversed'):
                        self.assertEqual(result['checks'][0]['status'],'FAILED')
                    else:
                        self.assertEqual(result['checks'][0]['status'],'PASSED')
                    with Path(row['target']).open(encoding='utf-8') as handle:
                        self.assertEqual(str(SeqIO.read(handle,'genbank').seq),str(case.target.seq))
                self.assertEqual(saved['control']['target_locus_count'],1)
                self.assertFalse(saved['control']['warnings'])
                self.assertIn('GRNA_ANNOTATION_STRAND_CONFLICT',[w['code'] for w in saved['annotation_conflict']['warnings']])
                self.assertEqual(saved['annotation_conflict']['direction_status'],'CORRECT')
                self.assertEqual(saved['repeated_target']['target_locus_count'],2)
                self.assertIn('MULTIPLE_VALID_TARGETS',[w['code'] for w in saved['repeated_target']['warnings']])
                for name in ('control','spacer_cds'):
                    inspected=TOOL_REGISTRY['summarize_backbone'].execute(file_path_or_record=rows[name]['vector']).analysis
                    self.assertEqual(inspected['selection_markers'],[])
                    warnings=inspected['warnings']
                    self.assertEqual(bool(warnings),name=='spacer_cds')

    def test_repeated_pcr_binding_rejects_while_control_sequence_is_exact(self):
        for seed in SEEDS:
            cases=build_cases(seed); control=cases['control']; repeated=cases['repeated_binding']
            sequence=str(control.vector.seq)
            forward=control.new_spacer+control.scaffold[:40]
            reverse=reverse_complement(sequence[20:60])
            params={'f_primer':forward,'r_primer':reverse,'forward_binding_core_length':40,'reverse_binding_core_length':40}
            product=TOOL_REGISTRY['simulate_pcr'].execute(template_path_or_seq=control.vector,**params).only_product()
            self.assertEqual(str(product.seq),control.new_spacer+sequence[80:]+sequence[:60])
            with self.assertRaisesRegex(Exception,'primer-binding ambiguity'):
                TOOL_REGISTRY['simulate_pcr'].execute(template_path_or_seq=repeated.vector,**params)


if __name__=='__main__':
    unittest.main()
