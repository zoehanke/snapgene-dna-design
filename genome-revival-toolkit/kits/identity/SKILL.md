---
name: genome-identity
description: Assess whether supplied reference regions and PCR assays distinguish the declared backgrounds, including ambiguous binding, unresolved band resolution and unsupported genome-wide conclusions.
---

# Given-reference identity assessment

Use this Kit to compare supplied DNA regions or check/design bounded PCR assay candidates. It does not establish whole-genome identity, host-genome elimination, donor revival or measured PCR performance.

1. Inspect the actual reference files/record selections in the project context. Keep missing or ambiguous selections unresolved.
2. Read kit.json for the wrapper inputs. Preserve the user's original_request and explicit reference/assay fields in the request file. The [README](README.md) gives the retained CLI and generic Kit entry.
3. Execute the existing identity workflow. Compare every supplied background's exact-binding prediction, full oligo quality and stated band-resolution condition. A negative prediction is not an observed negative gel.
4. Inspect result.json, identity-primers.tsv, summary.md, TOOLKIT-RECEIPT.json and the actual Trace files. Run the retained verify command on the output directory. Report failed/incomplete checks and their scope.

[Sourced scope rules](rules/scope.json) describe the existing boundaries; they do not add a new gate or scientific exemption. The scientific implementation is unchanged. Host routing, wet experiments and genome-wide specificity need separate evidence.
