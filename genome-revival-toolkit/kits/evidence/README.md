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
