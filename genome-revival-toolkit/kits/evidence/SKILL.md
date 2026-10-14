---
name: revival-evidence
description: Compare submitted colony counts, controls and genetic-test records when the user needs their consistency and conclusion limits. Use Identity to design or simulate regional assays, Construct for donor preparation, and CRISPR for guide plasmids. This Kit does not authenticate experiments or prove revival.
---

# Evaluate submitted observations

Read kit.json for wrapper/request fields. Preserve record source, missing denominators, control status and unmeasured regions. Empty data and missing counts are not zero.

Run the declared entry with request_file/context_file, or the retained `run_toolkit.py evidence --request request.json --context context.json --out-dir output`. CSV input is UTF-8 and resolves relative to the request file. Genetic records must reference explicit supplied Context entries.

Inspect structure/count/reference checks, contradictions and each conclusion's coverage. Growth or local PCR alone does not establish donor-genome function or complete host-genome elimination. Sources are submitted observations, not newly performed or authenticated experiments.

Present result.json, context-snapshot.json, summary.md, TOOLKIT-RECEIPT.json and available Trace. Verify actual files with `run_toolkit.py verify`. See README.md for a synthetic example and rules/scope.json for sourced boundaries.
