---
name: genome-identity
description: Compare supplied reference regions and PCR candidates when the user needs bounded genetic discrimination. Use Construct for donor preparation, Evidence for submitted observations, and CRISPR for guide plasmids. This Kit does not infer whole-genome identity or functional revival.
---

# Given-reference identity assessment

Use this Kit to compare supplied DNA regions or check/design bounded PCR assay candidates. It does not establish whole-genome identity, host-genome elimination, donor revival or measured PCR performance.

1. Inspect the actual reference files/record selections in the project context. Keep missing or ambiguous selections unresolved.
2. Read kit.json for the wrapper inputs. Preserve the user's original_request and explicit reference/assay fields in the request file. The [README](README.md) gives the retained CLI and generic Kit entry.
3. Execute the existing identity workflow. Compare every supplied background's exact-binding prediction, full oligo quality and stated band-resolution condition. A negative prediction is not an observed negative gel.
4. Inspect result.json, identity-primers.tsv, summary.md, TOOLKIT-RECEIPT.json and the actual Trace files. Run the retained verify command on the output directory. Report failed/incomplete checks and their scope.

[Sourced scope rules](rules/scope.json) describe the existing boundaries; they do not add a new gate or scientific exemption. The scientific implementation is unchanged. Host routing, wet experiments and genome-wide specificity need separate evidence.

Example: generate software inputs with `examples/generate_inputs.py --out-dir example-inputs`, then run the declared entry using example-inputs/inputs.json. Constructed PCR lengths are local sequence predictions, not observed bands.
