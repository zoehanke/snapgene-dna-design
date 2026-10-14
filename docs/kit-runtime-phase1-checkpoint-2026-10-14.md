# Block K phase 1 checkpoint: 2026-10-14

This source checkpoint starts from `e7b1f1629e9677ff04d9428c3fb7c2fa459cf375` on `codex/kit-runtime-phase1-20261014`. It covers only the local runtime/tool adapter and Identity pilot. Main, the official repository and frozen candidates are untouched. The final CI outcome is attached to the exact pushed head in [draft PR 5 checks](https://github.com/zoehanke/snapgene-dna-design/pull/5/checks); creating the PR does not authorize merging it.

## Checkpoint matrix

| Verified | Simulation only | Not performed | Uncertain |
|---|---|---|---|
| Inventory of real Core seams and actual revival reuse; no project registration in Core/Trace. | No scientific claim follows from an interface inventory. | Pipeline, gate, rule, Handler, Recipe and schema contribution adapters. | Compatibility with arbitrary third-party Python. |
| Manifest validation, metadata-only describe, external-code notice, three distinct bad-Kit errors and neighbor isolation. | Test-only arithmetic Kit uses literal 7→14, 9→18 and 13→26 expectations. | Remote discovery, sandboxing or persistent trust storage. | Arbitrary import effects cannot be undone by removing registry entries. |
| Real public describe/run_step/Kit entry calls; category refusal prevents the marker function; reload records one operation per call. | Generated toy inputs are engineering regressions. | Host routing and independent heldout-agent evaluation. | Host selection quality. |
| Identity scientific file unchanged; 75 legacy files compared: 69 byte-identical and 6 equivalent JSON key ordering only. | Synthetic PCR predictions are 164 bp, 141 bp and no exact product, from independently constructed strings. | Wet-lab PCR, genotype observations and whole-genome validation. | Actual assay performance outside supplied references. |
| Sixteen new focused cases pass: twelve runtime and four pilot cases. Final complete local suite: 1311 run, 1287 passed, 24 skipped, zero failure/error; actual Primer3 gate enforced. Baseline: 1295 run, 1271 passed, 24 skipped. | Comparisons control UUID/time for reproducibility; this artificial metadata is not experimental evidence. | At source freeze, exact-head GitHub CI is still pending; use its final checks for CI acceptance. Skips are not passes. | Optional external resources are not validated when unavailable or excluded. |

**Official GitLab CI was not executed. 官方GitLab CI未执行。**

## Contracts and pilot choice

The [inventory](kit-extension-inventory.md) records which seam exists and which adapter is missing. The executable manifest shape is [kit-v1.json](../snapgene-dna-design/schemas/kit-v1.json); the English [contract and shortest addition steps](../snapgene-dna-design/references/kit-contract.md) own field definitions and the SKILL.md trigger template.

Required fields are schema_version, name, version, core_version (inclusive minimum/exclusive maximum), input_schema, input_example, entrypoint, outputs and contributions. Each contribution declares target, local name, content, source and description. Only tools are implemented; their content declares callable, category and parameters. No new execution/category contract replaces ToolSpec/run_step.

Identity is the P0 pilot because supplied-region/PCR assessment already has independent positive/negative and public tests, with less preparation/delivery/selection coupling than Construct or CRISPR. Its [sub-Skill](../genome-revival-toolkit/kits/identity/SKILL.md) has manifest, scripts, sourced guidance rules, generated examples, tests and English README. The remaining three scientific modules and legacy tests retain their expectations. Shared project context/reporting remain on the project side; standalone single-Kit packaging is not claimed.

## Reproducible evidence

Keep raw evidence outside Git. The retained evidence root contains:

| Relative evidence file | Scope |
|---|---|
| baseline-suite.json | Original complete baseline, separate passes/skips. |
| compatibility-02/before/CAPTURE.json | Frozen old public output capture and independent expectations. |
| compatibility-02/after-05-comparison.json | Post-commit per-file old/new SHA-256, byte/structural verdict, with no ignored fields; earlier attempts remain. |
| compatibility-02/CONDITIONS.json | Cases, literal product-length construction and controlled metadata. |
| toy-and-pilot-final.stderr.txt | Sixteen focused test outcomes through actual entrypoints/files. |
| final-full-suite-01/complete-suite.json | Final complete suite, eight existing disjoint test-ID shards; no repeated matrix accumulation. |
| review-spec/summary.json and review-spec/attempt-02/ | Preserved loader failures and independent fix probes. |

Use `tools/compare_kit_compatibility.py --baseline <old-checkout> --current <new-checkout> --out-dir <outside-Git>` to reproduce captures. Baseline capture uses `--capture-baseline`; subsequent attempts get distinct `--attempt` names. Compare the same six inputs/modes, all four describe responses, legacy help, actual receipts and English/Chinese Trace files. Only repository code-source location and JSON object key ordering are normalized; biological values, errors, checks, scopes and report text remain exact.

Known baseline regressions, independent constructed inputs and developer-assisted invocation are separate evidence. These are scripted engineering checks, not a general success-rate improvement. Original failed attempts remain: the initially discriminating “unresolved” fixture, missing English titles, Windows nested Trace recorder failure and non-DNA context interpreted as a DNA file. They were not overwritten by later passes.

The final local suite's 24 skips comprise 14 unavailable academic fixtures, four optional model/dependency cases, three unconfigured Cas-OFFinder/OpenCL integrations, two explicit private-material integrations and one opt-in live-network integration. Their individual test IDs/reasons remain in complete-suite.json. No skipped case is counted as passed; no optional resource or user DNA is fetched to change this number.

## Review dispositions

Standards axis found one adapter defect: existing assay checks were left inside analysis. The tool now forwards those same checks to ToolResult.checks; an independently constructed contradictory expectation remains FAILED. The scientific file is unchanged.

Spec axis found three loader defects: repeated registration wrappers duplicated operation records; a disappearing manifest blocked a valid neighbor; non-JSON values escaped the JSON result declaration. Restoring only owned module bindings, structured loading errors and finite JSON validation close them. Original probes and corrected public calls are retained. No scientific gate was weakened.

The original package test counted every SKILL.md basename as another installable root. The explicit sub-Skill requirement makes that assertion obsolete. It now requires one top-level entry and manifest-backed nested kits; payload hashes, private-material exclusion, vendor ownership and public standalone package execution remain checked. The original assertion counterexample remains outside Git.

## Next phase recommendations

Migrate the remaining three Kits only under a new scope, retaining equivalent receipts/files. Adapt Pipeline, gate and rules into their existing seams without another executor or gate exemption. Then test host routing, installation/removal and packaging of complete/individual distributions. Update owning specs and English instructions with actual support boundaries. Do not add these to a frozen candidate before separate validation and authorization.
