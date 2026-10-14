# Construct Kit

Use this Kit for an explicitly bounded linear integration donor. Scientific calculation is unchanged scripts/workflow.py, with same-version Core preparation, interface QC and delivery. Identity compares supplied references/assays; Evidence evaluates submitted records; CRISPR prepares guide plasmids.

## Inputs and run

kit.json owns the wrapper inputs and request shape. Its example is illustrative, not a project answer. All intervals are 0-based half-open on selected records; arm length must be explicit. PCR requires the actual complete donor template. Gibson uses actual source fragments and complete primers. Conditions and unavailable solutions remain explicit.

```text
python kits/construct/examples/generate_inputs.py --out-dir example-inputs
python scripts/run_toolkit.py construct --context example-inputs/context.json --request example-inputs/request.json --out-dir example-output --language en
python scripts/run_toolkit.py verify --out-dir example-output
```

The synthetic expectation is 200 bp left arm + 240 bp cargo + 200 bp right arm, constructed before any Core call. Inputs are software vectors, not laboratory stocks or project facts. Generate outside source.

## Checks and outputs

Inspect preparation, complete oligos, both donor interfaces, sequence/annotations, declared goals and actual exported file versions. A successful request returns the Core-owned DNA bundle and Toolkit result.json, context-snapshot.json, summary.md and TOOLKIT-RECEIPT.json. Failure may leave supporting records without formal DNA delivery; use actual returned paths.

rules/scope.json carries the sources of existing boundaries; guidance is not an exemption. Actual strain genotype, whole-genome specificity, physical preparation and genomic integration remain unverified. Official GitLab CI was not executed.
