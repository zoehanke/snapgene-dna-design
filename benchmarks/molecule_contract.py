"""Comparable public-operation measurements, independent of the tool result layout."""
import argparse
import copy
import json
import random
import statistics
import sys
import time
import tracemalloc
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skill-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.skill_root.resolve()))
    from Bio.Seq import Seq
    from Bio.SeqFeature import FeatureLocation, SeqFeature
    from Bio.SeqRecord import SeqRecord
    from core.tools import get_tool

    rows = []
    for length in (5000, 50000):
        rng = random.Random(10429 + length)
        seq = ''.join(rng.choices('ACGT', k=length))
        record = SeqRecord(Seq(seq), id='generated', annotations={'molecule_type': 'DNA', 'topology': 'linear'})
        record.features = [SeqFeature(FeatureLocation(i, i + 12), type='misc_feature',
                           qualifiers={'label': [f'interval-{i}']}) for i in range(0, length - 12, 100)]
        for operation, params, expected in (
            ('extract_subsequence', {'file_path_or_record': record, 'start': 100, 'end': length - 100}, seq[100:length - 100]),
            ('mutate_sequence', {'dna_seq': record, 'mutations': [{'position_0based': 50, 'alt_base': 'N'}]}, seq[:50] + 'N' + seq[51:]),
        ):
            samples = []
            tool = get_tool(operation)
            tool.execute(**params)  # same warm-up on both trees
            for _ in range(3):
                copies = [0]
                original_copy = copy.deepcopy
                def observed_copy(value, *a, **kw):
                    copies[0] += 1
                    return original_copy(value, *a, **kw)
                tracemalloc.start()
                start = time.perf_counter()
                copy.deepcopy = observed_copy
                try:
                    result = tool.execute(**params)
                finally:
                    copy.deepcopy = original_copy
                elapsed = time.perf_counter() - start
                _, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                products = getattr(result, 'products', None)
                actual = str(products[0].seq) if products is not None else result['sequence']
                assert actual == expected
                assert str(record.seq) == seq
                samples.append({'seconds': elapsed, 'python_peak_bytes': peak,
                                'deepcopy_calls': copies[0], 'file_conversions': 0})
            rows.append({'operation': operation, 'length': length, 'samples': samples,
                         'median_seconds': statistics.median(x['seconds'] for x in samples),
                         'max_python_peak_bytes': max(x['python_peak_bytes'] for x in samples)})
    report = {'python': sys.executable, 'skill_root': str(args.skill_root.resolve()),
              'scope': 'CPU public tool calls; generated input; not whole-process RSS or biological effectiveness',
              'rows': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
