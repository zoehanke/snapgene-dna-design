---
name: revival-evidence
description: Compare submitted colony counts, controls and genetic-test records when the user needs their consistency and conclusion limits. Use Identity to design or simulate regional assays, Construct for donor preparation, and CRISPR for guide plasmids. This Kit does not authenticate experiments or prove revival.
---

# Evaluate submitted observations

Read kit.json for wrapper/request fields. Preserve record source, missing denominators, control status and unmeasured regions. Empty data and missing counts are not zero.

Run the declared entry with request_file/context_file, or the retained `run_toolkit.py evidence --request request.json --context context.json --out-dir output`. CSV input is UTF-8 and resolves relative to the request file. Genetic records must reference explicit supplied Context entries.

Inspect structure/count/reference checks, contradictions and each conclusion's coverage. The existing finite conclusion table and per-rule scope-contract sources are in rules/conclusions.json; it is loaded by the workflow. Growth or local PCR alone does not establish donor-genome function or complete host-genome elimination. Sources are submitted observations, not newly performed or authenticated experiments.

For observation-versus-prediction comparison, set optional `expected_results_file` to Identity's exported table. Each genotype record identifies `assay_id`, `reference_id`, reported `result`/`control_status`, and positive `observed_band_bp`; optional `band_tolerance_bp` is explicit and defaults to exact size equality. Inspect `expected_result_comparison`, reasons and `not_tested_assays`. SUPPORTED concerns local consistency under reported controls only. Counts alone remain INSUFFICIENT. Missing/changed prediction files or reference bindings fail explicitly; no format or genotype is guessed.

Present result.json, context-snapshot.json, summary.md, TOOLKIT-RECEIPT.json and available Trace. Verify actual files with `run_toolkit.py verify`. See README.md for a synthetic example and rules/scope.json for sourced boundaries.
