---
name: genome-revival-toolkit
description: Prepare and verify yeast marker donors for Genome Revival, compare supplied genetic reference regions and PCR discrimination, and organise reported revival experiments with their evidence limits. Use for project Construct, Genome Identity or Revival Evidence tasks involving supplied materials, including SY14 and XT2 references.
---

# Genome Revival Toolkit

Toolkit 0.1.1 uses Core 2.2.4 and Evidence Trace 0.3.4. Use the three Kits through `scripts/run_toolkit.py`. The package includes the same DNA Design Core used by these workflows. Scientific choices remain yours; use program results for sequence, preparation, quality and file facts.

Read `INSTALL-SOURCE.json` in this Skill root when present and use its verified interpreter. Otherwise install the listed dependencies and use the interpreter that passes the local checks. Do not search unrelated parent/test folders for installation records.

1. Inspect actual materials with `python -X utf8 -B scripts/run_toolkit.py inspect --context project-context.json`. Context holds reference paths, explicit record/region selection, declared strains and source-labelled project facts. Relative material paths resolve from the context file. A reference filename does not establish an experimental strain or locus.
2. Choose the Kit and read its input shape with `... run_toolkit.py describe construct`, `describe identity` or `describe evidence`. Write the original request and only the supported parameters. See [workflow inputs](references/workflows.md) for conditional fields. Context and requests are ordinary task inputs, not examiner material.
3. Execute `python -X utf8 -B scripts/run_toolkit.py <kit> --context project-context.json --request request.json --out-dir results`. Inspect returned status, current checks, failures and usable files before claiming completion. Keep failed attempts; change actual parameters or the route without weakening the original goal.
4. Present returned file paths and run `... run_toolkit.py verify --out-dir results --receipt-sha256 <returned value>`. DNA files remain governed by the Core receipt. Edited files, inputs or annotations need a fresh run/check; a previous PASS does not authorise a new version.

**Construct:** explicit target/cargo bounds and positive arm length. Existing valid donor material may need only PCR preparation; separate real sources may use Gibson. Do not invent SY14 URA3 coordinates, silently use an entire plasmid as cargo, or turn a sequence model into a physical preparation claim.

**Identity:** analyse the provided records/regions and candidate assays. `design_assays` uses the existing primer designer; a failed candidate may need different valid positions. Compare every requested reference. Ambiguous PCR, unresolved size separation and unavailable quality stay explicit. A local alignment is not unique placement, and selected negative markers do not establish whole-genome elimination.

**Evidence:** organise submitted observations and controls. Missing counts are not zero. Reported colony growth, local PCR or fluorescence alone does not prove donor-genome functional revival. Distinguish supplied experimental observations from computational predictions and record authentication.

Evidence Trace collects these public calls. Global Off/Observed/Full is set by `... run_toolkit.py trace-level <level>`; use isolated settings only for explicit testing. Observed needs no extra AI explanation. In Full, submit short `decisions` alongside actual consequential choices, with actor, rationale, origin and material basis where available. Preserve user reasons. Omit a rationale when none was supplied; later explanation must not masquerade as the original reason. Exported reports do not call another model or reconstruct hidden thought.

Toolkit-defined workflow structure may be projected from actual program records. Add scientific relationships only with explicit sources. Custom host scripts, browsing or presentation outside observed entries remain outside collection. A complete Trace means complete records within that scope, not correct DNA or successful experiments.

Program-verified file links mean an observed output SHA-256 equals a step's declared input SHA-256. Solid lines require the referenced computed file fact; a declared or structural fact ID still gets a dashed line. Read their `fact_relation_ids` and the scoped report summary separately from declared scientific relationships. Matching bytes do not prove physical use, source identity or causality. Missing or mismatched hashes produce no automatic link; no missing relationship is filled from step order.
