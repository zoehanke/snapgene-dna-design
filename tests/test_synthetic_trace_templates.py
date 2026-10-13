"""Independent construction oracles and real public PCR boundary checks."""
import contextlib
import io
import importlib.util
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

from Bio import SeqIO
from Bio.Seq import Seq
from repository_paths import SKILL_ROOT
from scripts.run_recipe import run_recipe_cli
from scripts.synthetic_trace_template import CASES, EDIT_STARTS, build_template, write_template


class SyntheticFullTemplateTests(unittest.TestCase):
    def test_seed_and_feature_geometry_are_independently_constructed(self):
        sequences = []
        for seed, length in CASES:
            original = build_template(seed, length)
            self.assertEqual(str(original.seq), str(build_template(seed, length).seq))
            self.assertEqual(len(original), length)
            self.assertEqual(original.annotations['topology'], 'circular')
            for start in EDIT_STARTS:
                self.assertEqual(str(original.seq[start:start + 3]), 'TAT')
            self.assertEqual(str(original.features[1].extract(original.seq))[:3], 'ATG')
            self.assertEqual(str(original.features[1].extract(original.seq))[-3:], 'TAA')
            self.assertNotIn('*', str(original.features[1].extract(original.seq).translate())[:-1])
            self.assertEqual(original.features[2].location.strand, -1)
            self.assertEqual([(int(p.start), int(p.end)) for p in original.features[3].location.parts],
                             [(length - 80, length), (0, 80)])
            sequences.append(str(original.seq))
        self.assertNotEqual(sequences[0], sequences[1])

    def _public_pcr(self, root, template, seed):
        # The primers and answer come directly from fixed input coordinates.
        # Duplicate the entire region, not a binding length chosen by the tool.
        start, end, core_length = 103, 827, 35
        sequence = str(template.seq)
        forward = sequence[start:start + core_length]
        reverse = str(Seq(sequence[end - core_length:end]).reverse_complement())
        for repeated in (False, True):
            record = template[:]
            record.annotations = dict(template.annotations)
            if repeated:
                record.seq = Seq(sequence[:1900] + sequence[start:end] + sequence[1900 + end - start:])
            name = f'{seed}-' + ('duplicate' if repeated else 'control')
            source = root / (name + '.gb')
            with source.open('w', encoding='utf-8') as handle:
                SeqIO.write(record, handle, 'genbank')
            config = {'method': 'simulate_pcr', 'params': {
                'template_path_or_seq': str(source), 'f_primer': forward, 'r_primer': reverse,
                'forward_binding_core_length': core_length, 'reverse_binding_core_length': core_length}}
            cfg = root / (name + '.json')
            cfg.write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
            out = root / name
            done = subprocess.run([sys.executable, '-X', 'utf8', '-B',
                str(SKILL_ROOT / 'scripts/run_step.py'), '--input', str(cfg), '--out-dir', str(out)],
                capture_output=True, text=True, encoding='utf-8')
            if repeated:
                self.assertNotEqual(done.returncode, 0)
                self.assertIn('primer-binding ambiguity', done.stdout + done.stderr)
                self.assertFalse(list(out.rglob('*.gb')), 'Rejected ambiguous PCR must not export a product')
            else:
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                result = json.loads((out / 'steps.json').read_text(encoding='utf-8'))['steps'][0]['result']
                self.assertEqual(result['products'][0]['sequence'], sequence[start:end])
                # Inspect the actual GenBank product written by the public CLI.
                files = list(out.rglob('*.gb'))
                self.assertTrue(files, 'Public PCR output has no GenBank product')
                with files[0].open(encoding='utf-8') as handle:
                    self.assertEqual(str(SeqIO.read(handle, 'genbank').seq), sequence[start:end])

    def test_public_pcr_full_templates_and_duplicate_binding_failure(self):
        for seed, length in CASES:
            with self.subTest(seed=seed), tempfile.TemporaryDirectory(prefix='synthetic-public-pcr-') as folder:
                self._public_pcr(Path(folder), build_template(seed, length), seed)

    def test_unconstrained_window_preserves_real_primer_structure_rejection(self):
        rng = random.Random(75)
        sequence = ''.join(rng.choices('ACGT', k=3100))
        # This preserves the first, unconstrained synthetic authoring failure.
        # Independently encode official Primer3 Boulder-IO without using Core
        # adapters/design answers. Explicit salt conditions match documented
        # defaults. Python native bindings are not invoked in the test process.
        executable = os.environ.get('PRIMER3_CORE') or shutil.which('primer3_core') or shutil.which('primer3_core.exe')
        if not executable:
            spec = importlib.util.find_spec('primer3')
            self.assertIsNotNone(spec, 'Required real Primer3 dependency is missing')
            candidates = [p for p in Path(spec.origin).parent.rglob('primer3_core*')
                          if p.is_file() and p.name in ('primer3_core', 'primer3_core.exe')]
            self.assertTrue(candidates, 'Required real Primer3 binary is missing')
            executable = str(candidates[0])
        metrics = []
        for length in range(25, 36):
            primer = 'CAT' + sequence[232:232 + length]
            # Primer3 limits annealing-field size to 36 nt. Its official
            # overhang field retains any remaining complete-oligo bases.
            parameters = {'SEQUENCE_PRIMER': primer[-36:], 'SEQUENCE_OVERHANG_LEFT': primer[:-36],
                'PRIMER_TASK': 'check_primers',
                'PRIMER_PICK_RIGHT_PRIMER': 0, 'PRIMER_PICK_ANYWAY': 1,
                'PRIMER_MIN_SIZE': 18, 'PRIMER_OPT_SIZE': 25, 'PRIMER_MAX_SIZE': min(36, len(primer)),
                'PRIMER_SECONDARY_STRUCTURE_ALIGNMENT': 1, 'PRIMER_SALT_MONOVALENT': 50,
                'PRIMER_SALT_DIVALENT': 1.5, 'PRIMER_DNTP_CONC': 0.6, 'PRIMER_DNA_CONC': 50}
            boulder = ''.join(f'{key}={value}\n' for key, value in parameters.items()) + '=\n'
            done = subprocess.run([executable, '--strict_tags'], input=boulder,
                capture_output=True, text=True, encoding='utf-8', errors='replace')
            self.assertEqual(done.returncode, 0, 'Independent Primer3 call failed')
            parsed = dict(line.split('=', 1) for line in done.stdout.splitlines() if '=' in line)
            self.assertNotIn('PRIMER_ERROR', parsed)
            metrics.append(float(parsed['PRIMER_LEFT_0_HAIRPIN_TH']))
        self.assertGreater(min(metrics), 60)
        with tempfile.TemporaryDirectory(prefix='synthetic-rejected-edit-') as folder:
            source = Path(folder) / 'input.gb'
            record = build_template(75, 3100)
            # Reconstruct the original unfiltered input including its valid
            # ORF, so malformed annotations cannot explain this rejection.
            bases = list(sequence)
            for start in EDIT_STARTS:
                bases[start:start + 3] = 'TAT'
            codons = [a + b + c for a in 'ACGT' for b in 'ACGT' for c in 'ACGT'
                      if a + b + c not in ('TAA', 'TAG', 'TGA')]
            bases[1080:1386] = 'ATG' + ''.join(rng.choices(codons, k=100)) + 'TAA'
            record.seq = Seq(''.join(bases))
            self.assertNotIn('*', str(record.features[1].extract(record.seq).translate())[:-1])
            with source.open('w', encoding='utf-8') as handle:
                SeqIO.write(record, handle, 'genbank')
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(Exception, 'NO_VALID_PRIMER_PAIR'):
                run_recipe_cli('site_directed_mutagenesis', {'template_seq_or_file': str(source),
                    'start_0based': 229, 'end_0based': 232, 'alt_seq': 'CAT', 'method': 'inverse_pcr',
                    'target_flank_bp': 25}, Path(folder) / 'rejected', True, True)


if __name__ == '__main__':
    unittest.main()
