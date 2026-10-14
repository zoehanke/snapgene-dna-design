---
name: genome-crispr
description: Check an existing guide plasmid or replace its explicit 20 nt spacer when actual vector/target sequences and cassette selectors are supplied. Use Construct for integration donors, Identity for regional PCR discrimination, and Evidence for submitted observations. This Kit does not infer genotype, certify knockout activity or waive inherited template errors.
---

# Check or prepare a guide plasmid

Read kit.json for wrapper/request fields. Inspect actual Context references and promoter-to-scaffold direction. Check mode reuses existing DNA; replace mode requires an explicit new spacer. Resolve ambiguous cassettes with selectors.

Run the declared entry or retained `run_toolkit.py crispr --context context.json --request request.json --out-dir output`. Mandatory checks cover sequence-derived direction, valid PAM, target uniqueness/orientation distinguishability, supplied-vector self-targets and declared selection background. Unknown genotype or an annotation-only resistance claim does not establish compatibility.

Replacement must preserve outside bases, retain annotation disposition, calculate primer Tm/quality and independently simulate the original-template PCR and circularisation. PCR, DpnI and KLD remain planned laboratory actions. Inspect actual checks and file roles; failed or unresolved checks retain candidates instead of formal delivery.

Present source-labelled selection.tsv and actual returned DNA/primer/report files. Verify TOOLKIT-RECEIPT.json and the Core delivery receipt. See README.md and rules/scope.json for boundaries and software examples. No wet experiment, whole-genome off-target, editing efficiency or scaffold-function claim follows from this run.
