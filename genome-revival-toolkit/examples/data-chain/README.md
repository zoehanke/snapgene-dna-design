# Synthetic data chain

This example uses fixed software inputs, prospective reference models and simulated reported observations. It demonstrates file handoff and bounded prediction comparison. All laboratory actions are **PLANNED / NOT_PERFORMED**. No user material, measured strain, actual knockout or wet experiment is represented. Official GitLab CI was not executed.

From the repository root, with the same configured Python/Primer3 used for the Toolkit:

```powershell
python -X utf8 -B genome-revival-toolkit/examples/data-chain/run_story.py --out-dir output/data-chain
python -X utf8 -B genome-revival-toolkit/examples/data-chain/independent_check.py --directory output/data-chain
```

Use a fresh output directory for every run. The complete installable Skill has the same `examples/data-chain/` directory; run those scripts from its own root without the repository prefix. No development helper is imported by the scripts or runtime.

The first script runs actual public Toolkit commands and `verify`, retains every command/stdout/stderr and output file, and then runs the independent checker. An expected nonzero exit from the CRISPR case is retained: selection genotype was not supplied. The oracle imports no Core/Kit calculation. It uses independently constructed reference slicing and full-primer string search, then recomputes observed-versus-predicted consistency. Simulated band records are generated from that independent search, never copied from Identity's answer table.

## What to inspect

| Stage | Constructed expectation / file |
|---|---|
| Construct | 200 + 240 + 200 = 640 bp donor from its actual complete template; both donor-QC pairs. `construct/identity-handoff.json` and `identity-request.json` are actual output files. |
| Given references | 2000 bp original and 2230 bp prospective edited model, supplied before any Kit call. Neither is an experimentally established genotype. |
| Identity | Rechecks actual donor-QC pairs on both models; exports `identity/identity-expected-results.json`. Independent exact-string calculation finds 256/286 bp on the edited model and no exact product on the original. |
| Evidence | `evidence-matching`, `evidence-contradicted`, `evidence-counts-only` compare synthetic reported records: SUPPORTED, CONTRADICTED, INSUFFICIENT. Revival and whole-genome elimination remain unsupported. |
| CRISPR | `crispr-before`: a guide starts one base early, so its adjacent PAM ends CG and fails. `crispr-after`: replace with the specified correct guide, recheck direction/PAM and vector sites, retain a simulated inverse-PCR/DpnI/KLD plan and complete primers in result.json. Selection is UNKNOWN; candidate files remain candidates. |

`COMMANDS.json` contains actual reproducible public argument lists. `INDEPENDENT-CHECK.json` records the recomputed sizes/bands/conclusions. `chain-trace` reuses one append-only Trace across the three Kits and observation counterexamples; `crispr-trace` retains the failed check and correction. A shared log preserves all runs; its old full view may focus on the latest invocation. File-content facts do not establish causal scientific support.

The video runbook and reader questions accompany the private Wiki material. Readers receive only the rendered card, never manager answers. Developers do not execute that reading/routing evaluation.
