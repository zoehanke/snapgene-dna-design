"""Full-template edits and Trace A/B using independently constructed synthetic DNA."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.synthetic_trace_template import EDIT_STARTS, PCR_INTERVAL, write_template


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', help='Optional legally supplied complete circular GenBank; default is synthetic')
    parser.add_argument('--first-edit-start', type=int, default=EDIT_STARTS[0])
    parser.add_argument('--second-edit-start', type=int, default=EDIT_STARTS[1])
    parser.add_argument('--pcr-start', type=int, default=PCR_INTERVAL[0])
    parser.add_argument('--pcr-end', type=int, default=PCR_INTERVAL[1])
    parser.add_argument('--out-dir', required=True)
    args = parser.parse_args()
    out = Path(args.out_dir).resolve()
    if out.exists():
        raise ValueError('Use a new output directory to preserve previous evidence')
    out.mkdir(parents=True)
    template = Path(args.template).resolve() if args.template else out / 'synthetic-input.gb'
    if not args.template:
        write_template(template)
    from Bio import SeqIO
    with template.open(encoding='utf-8') as handle:
        original = SeqIO.read(handle, 'genbank')
    first, second = args.first_edit_start, args.second_edit_start
    if original.annotations.get('topology') != 'circular' or not 0 <= first < first + 3 <= second < second + 3 <= len(original):
        raise ValueError('Require circular topology and ordered, nonoverlapping 3 nt intervals')
    if not 0 <= args.pcr_start < args.pcr_end <= len(original):
        raise ValueError('PCR interval lies outside the template')
    trace, commands = out / 'evidence-trace', []

    def write(name, value):
        path = out / name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        return str(path)

    def run(script, *parts):
        command = [sys.executable, '-X', 'utf8', '-B', str(ROOT / 'scripts' / script), *map(str, parts)]
        target = str(parts[parts.index('--out-dir') + 1]) if '--out-dir' in parts else ''
        config = write('demo-trace-settings.json', {'trace_level': 'off' if target.endswith('-off') else 'full'})
        done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace',
                              env={**os.environ, 'SNAPGENE_TRACE_CONFIG': config})
        commands.append({'script': script, 'exit_code': done.returncode})
        write('commands.json', commands)
        if done.returncode:
            raise RuntimeError(f'{script} failed with exit code {done.returncode}; retain original outputs')
        return json.loads(done.stdout)

    context = {'actor': 'synthetic-demo-author', 'nodes': [
        {'id': 'R-edit', 'kind': 'requirement', 'text': '保留完整环形模板，连续执行两次指定替换，交付实际产物。'},
        {'id': 'S-template', 'kind': 'source', 'title': '完整工程演示输入',
         'source_type': 'user-material' if args.template else 'synthetic-construction', 'path': str(template)},
        {'id': 'E-template', 'kind': 'statement', 'source_id': 'S-template', 'text': '完整输入提供序列及注释；不证明生物功能。'},
        {'id': 'C-edit', 'kind': 'claim', 'text': '以完整模板和第一轮实际产物连续改造。', 'limitations': ['仅序列模拟，没有湿实验或表型验证']},
        {'id': 'D-edit', 'kind': 'decision', 'text': '第一轮指定替换', 'rationale': '区间由演示构造或调用者给定，扩增由实际工具计算。',
         'responds_to': ['R-edit'], 'claim_ids': ['C-edit'], 'decision_kind': 'method_selection',
         'targets': {'start_0based': first, 'end_0based': first + 3, 'alt_seq': 'CAT'}}],
        'links': [{'statement_id': 'E-template', 'claim_id': 'C-edit', 'relation': 'contextualize',
                   'applicability': 'direct', 'strength': 'source location only', 'limitations': ['不是实验验证或科学因果证明']}]}
    run('trace_design.py', 'record', '--trace-dir', trace, '--input', write('decisions-v1.json', context))
    params = {'template_seq_or_file': str(template), 'start_0based': first, 'end_0based': first + 3,
              'alt_seq': 'CAT', 'target_flank_bp': 25, 'method': 'inverse_pcr'}
    for mode in ('off', 'on'):
        run('run_recipe.py', '--recipe', 'site_directed_mutagenesis', '--params-json', write('params-edit1.json', params),
            '--out-dir', out / ('edit1-' + mode), '--finalize', '--confirmed', '--json',
            *(['--trace-dir', trace] if mode == 'on' else []))
    revision = {'actor': 'synthetic-demo-author', 'nodes': [
        {'id': 'C-edit', 'kind': 'claim', 'text': '保留第一轮实际产物，再加入第二次指定替换。', 'limitations': ['没有湿实验或表型验证']},
        {'id': 'D-edit', 'kind': 'decision', 'text': '修订：以第一轮真实产物作为模板', 'rationale': '使用已生成完整文件，不将理想序列冒充中间体。',
         'responds_to': ['R-edit'], 'claim_ids': ['C-edit'], 'decision_kind': 'mutation_selection',
         'targets': {'start_0based': second, 'end_0based': second + 3, 'alt_seq': 'TTT'}}]}
    run('trace_design.py', 'record', '--trace-dir', trace, '--input', write('decisions-v2.json', revision))
    revised = {**params, 'template_seq_or_file': str(out / 'edit1-on/authoritative/construct.gb'),
               'start_0based': second, 'end_0based': second + 3, 'alt_seq': 'TTT'}
    run('run_recipe.py', '--recipe', 'site_directed_mutagenesis', '--params-json', write('params-edit2.json', revised),
        '--out-dir', out / 'edit2', '--finalize', '--confirmed', '--json', '--trace-dir', trace)
    pipeline = {'task_id': 'synthetic-fragment', 'topology': 'linear', 'output_step': 'pcr',
        'sources': [{'source_id': 'source', 'path': str(template)}], 'steps': [
            {'step_id': 'pcr', 'tool': 'prepare_pcr_fragment', 'params': {'template': '$source',
                'start': args.pcr_start, 'end': args.pcr_end, 'name': 'synthetic-fragment'}}]}
    for mode in ('off', 'on'):
        run('run_pipeline.py', '--pipeline', write('pipeline.json', pipeline), '--out-dir', out / ('pipeline-' + mode),
            '--confirmed', '--json', *(['--trace', '--trace-input', write('pipeline-context.json', context)] if mode == 'on' else []))
    checks = {}
    for route in ('edit1', 'pipeline'):
        for ext in ('gb', 'dna', 'fasta'):
            checks[route + '.' + ext] = (out / (route + '-off') / 'authoritative' / ('construct.' + ext)).read_bytes() == (out / (route + '-on') / 'authoritative' / ('construct.' + ext)).read_bytes()
    with (out / 'edit2/authoritative/construct.gb').open(encoding='utf-8') as handle:
        final = SeqIO.read(handle, 'genbank')
    expected = str(original.seq[:first]) + 'CAT' + str(original.seq[first + 3:second]) + 'TTT' + str(original.seq[second + 3:])
    checks['two_edit_sequence'] = str(final.seq) == expected
    with (out / 'pipeline-on/authoritative/construct.gb').open(encoding='utf-8') as handle:
        checks['pcr_sequence'] = str(SeqIO.read(handle, 'genbank').seq) == str(original.seq[args.pcr_start:args.pcr_end])
    if not all(checks.values()):
        raise AssertionError(checks)
    summary = {'checks': checks, 'view': str(trace / 'index.html'),
               'final_construct': str(out / 'edit2/authoritative/construct.dna'),
               'scope': 'Developer synthetic engineering regression; sequence simulation only; no wet-lab or heldout success claim.'}
    write('demo-summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
