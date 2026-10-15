# Revival Evidence Kit

Use this Kit for submitted counts, controls and selected-region genotype records. scripts/workflow.py performs parsing and bounded comparisons; rules/conclusions.json owns the existing conclusion truth table, claim text, reasons and per-rule scope-contract sources. Identity handles sequence/PCR candidates, Construct prepares donors and CRISPR checks/prepares guide vectors.

## Inputs and run

kit.json owns wrapper inputs, the request shape and illustrative example. Observation IDs are unique; counts are nonnegative integers or missing. Denominators remain explicit. CSV paths resolve from the request file; genetic records refer to actual Context references and submitted control states.

```text
python kits/evidence/examples/generate_inputs.py --out-dir example-inputs
python scripts/run_toolkit.py evidence --request example-inputs/request.json --context example-inputs/context.json --out-dir example-output --language en
python scripts/run_toolkit.py verify --out-dir example-output
```

Generated records are software test vectors. Arithmetic expectation is 30/50 minus 5/50 = 0.5; deleting one denominator makes that difference unknown. They are not experiment records.

## Checks, outputs and boundaries

Inspect input structure, references, duplicates, controls, contradictions and explicit conclusion scopes. Results include result.json, context-snapshot.json, summary.md, TOOLKIT-RECEIPT.json and Trace when enabled. Keep original failure messages and missing values.

rules/scope.json is guidance; rules/conclusions.json is loaded for the four existing count-present/genotype-tested states. Its sources are explicit project contracts, not empirical validation. It distinguishes NOT_TESTED from INSUFFICIENT and does not define sufficient proof of revival or genome elimination. No rule language or exemption is added. Submitted observations are not authenticated by the software. Colony growth, fluorescence or local genetic results do not prove causal revival or complete genome elimination. Official GitLab CI was not executed.

## Optional observation-versus-prediction file

Set `expected_results_file` to the actual Identity `identity-expected-results-v1` JSON. Its supplied reference file/record/region/topology bindings must match the Context; changed or malformed tables reject explicitly. This local file is hashed, recorded as a source and consumed by the existing file-observation boundary. CSV observations retain their reported origin; inline band/control statements have no invented file hash.

Each genotype record may identify `assay_id`, a reference ID, reported result/control state and `observed_band_bp`. Report positive sizes as integers; a negative observation has no band size. `band_tolerance_bp` is an explicit nonnegative integer, default zero. Passing reported controls and a quality-supported local prediction are prerequisites for a consistency result. Unknown controls/quality/uncovered predictions are INSUFFICIENT; missing assays are NOT_TESTED; disagreements are CONTRADICTED. Counts alone are INSUFFICIENT and enumerate missing assays.

With a table, per-record `assessment` describes prediction consistency and `reported_record_assessment` retains the original record-only assessment. `expected_result_comparison` adds reasons, scope and missing assays. High-level revival/elimination conclusions retain their original limits. No-table outputs remain unchanged. The [synthetic chain](../../examples/data-chain/README.md) demonstrates matching, contradictory and counts-only records without experiments.
