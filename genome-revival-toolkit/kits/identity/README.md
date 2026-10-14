# Given-reference Identity Kit

This sub-Skill assesses supplied regions and declared PCR candidates. It retains the existing Identity scientific implementation and shared project context/reporting/receipt boundary. Construct, Evidence and CRISPR are unchanged legacy Kits in this phase.

## Run

The retained interface accepts the same subcommand and flags:

```text
python genome-revival-toolkit/scripts/run_toolkit.py identity --context context.json --request request.json --out-dir output --language en
python genome-revival-toolkit/scripts/run_toolkit.py verify --out-dir output
```

Kit API v1 provides explicit local loading:

```text
python snapgene-dna-design/scripts/run_kit.py describe genome-identity --kit-dir genome-revival-toolkit/kits
python snapgene-dna-design/scripts/run_kit.py run genome-identity --kit-dir genome-revival-toolkit/kits --input inputs.json --out-dir output
python snapgene-dna-design/scripts/describe_tools.py kit.genome-identity.assess --kit-dir genome-revival-toolkit/kits
```

inputs.json has request_file, context_file and optional language/trace_mode. The retained request shape is input_schema.definitions.request in kit.json. Relative input file paths follow the existing caller context; use unambiguous actual paths. Tool kit.genome-identity.assess accepts request/context_uri and returns scoped analysis through ToolResult; it does not create a construct or bypass DNA delivery. context_uri is a local file URI (Path.as_uri), not a DNA filename: the existing step material collector treats ordinary existing file strings as DNA. This adapter preserves the collector/DNA logic rather than silently parsing a context JSON as sequence. Remote URI schemes are rejected.

The manifest lists unconditional result/context/summary/receipt files. identity-primers.tsv is conditional on returned assays; a comparison-only request does not invent an order file. Loading metadata is recorded separately under kit-loading/, while the original business Trace/receipt retain their own boundary.

## Scope and sources

The analytical boundary comes from unchanged scripts/workflow.py, formerly revival/identity.py, and retained independent positive/negative tests. It reuses Core alignment, actual PCR simulation, primer design and full-pair quality. Alignment is not unique placement; prediction is not measured PCR or observed genotype. Whole-genome identity/elimination and donor revival remain unverified.

rules/scope.json records the existing sources. Rule, Pipeline and gate contributions are NOT_IMPLEMENTED; no scientific exemption is introduced. The generic runtime records loading, not code safety or scientific truth. Explicit external directories execute Python with host permissions and emit a notice.

## Generated example and tests

```text
python genome-revival-toolkit/kits/identity/examples/generate_inputs.py --out-dir example-inputs
python snapgene-dna-design/scripts/run_kit.py run genome-identity --kit-dir genome-revival-toolkit/kits --input example-inputs/inputs.json --out-dir example-output
```

Fixed-seed strings and a 23-base deletion define predicted lengths independently. A disrupted exact primer end supplies a no-product control. They are software vectors, not real materials or experiments. Generate outside source. Run Kit tests with unittest discovery in tests/; original repository Identity/public tests remain unchanged.

No single-Kit or frozen release package is issued in phase 1. This Kit relies on shared project-side context/reporting and the same Core/Trace in the complete source/distribution. Official GitLab CI was not executed.
