# Core skill

Updated: 2026-09-20. This spec defines the current DNA product contract. [History](../docs/history.md) explains its evolution; [development plans](../docs/development-plans/README.md) own implementation scope, validation and handoff. [Safety spec](safety-module.md) owns Evidence Trace; [SKILL.md](../SKILL.md) and [Recipe reference](../references/recipes.md) own usage and signatures.

## Goal and current functionality

Help molecular and synthetic biology researchers turn real materials and a design request into correct, inspectable DNA constructs and usable preparation instructions. Serve general research and laboratory R&D; iGEM and safety work extend that practical purpose.

| Surface | Current responsibility |
|---|---|
| Host AI and Skill guidance | Understand intent, clarify biological ambiguity, choose a route and explain consequential choices. |
| Recipes | Gibson, restriction cloning, Golden Gate, mutagenesis, tagging, HDR donors and cloning verification. |
| Pipeline and atomic tools | Compose actual feature, sequence, PCR, digestion, assembly and inspection operations. |
| ConstructionTask runtime | Structured task, plan, execution, validation and authoritative delivery. |
| File tools | Annotated GenBank/native SnapGene/FASTA, intermediates, complete primers, source annotations and preparation tables. |

Inputs include full sequence records/files and raw DNA. Routes differ in supported operations and maturity; the current task registry marks restriction_ligation and crispr_editing experimental, not every similarly named Recipe. The deprecated keyword route must not pretend to implement complex edits. Optional backends retain their documented availability and licensing limits.

## User workflow

1. Inspect complete sources, topology, relevant features and available physical materials; resolve ambiguity that changes the result.
2. Express required/forbidden components and other constraints, then choose a supported Recipe or compose a Pipeline/structured task.
3. Compute preparation and reactions from actual inputs; feed each real intermediate into its next step.
4. Check saved files against the request and reaction chain: sequence, junctions, topology, features and complete primers.
5. Deliver files and preparation/verification information, distinguishing candidates, components, QC designs and final constructs. Existing authorization persists; a confirmation interface is not grounds to ask again unnecessarily.

## Product contracts

- Practical task completion and correct artifacts take priority over tool counts, test counts or review frameworks.
- Host AI handles intent and strategy; executable tools compute sequences and reactions. A desired sequence is not proof of PCR amplification from the supplied template and delivered primers.
- Assembly inputs must be supplied prepared material or products of an explicit preparation step; include real backbone preparation where required.
- Preserve source, backbone, inserted-feature and primer annotations through transformations and export. Explain source annotation corrections separately from DNA changes.
- Keep actual coordinate, strand, compound-location and circular-origin conventions consistent across each interface; no implicit biological defaults without evidence and applicability.
- Missing checks, failed runs, components and historical successes must not be presented as newly verified complete constructs. Do not change the biological target or relax validation merely to obtain a pass.
- Sequence/file checks establish their stated computational scope, not wet-lab performance, whole-genome specificity or safety. File hashes bind versions, not biological correctness.
- Preserve external-service consent, provenance and distribution/license requirements. Local tools do not imply that the host never transmits data.

## Evidence Trace integration

Trace observes each route's actual inputs, returns and files. It does not change DNA, parameters, planners, Handlers, Core validation or authoritative artifacts; a Recipe run need not invent a ConstructionTask history. Missing/stale organization is a report condition, not a reason to modify the design.

The host or researcher explicitly organizes captured records and may author a report plan in the same response; code checks references/versions and renders the saved result. This is real AI work. Normal capture failures preserve DNA execution; explicit strict policy can stop at an execution boundary without rewriting completed files. Mode, attribution and report contracts are maintained in the [safety spec](safety-module.md).

## Architecture and rule changes

Current modules and orchestration are implementation choices, not permanent restrictions. Within the authorized task, revise a stale spec/plan when observed behavior or user feedback warrants it; explain the tradeoff, update affected callers/tests and record major reversals in History. Preserve the product contracts above. A historical phase boundary neither authorizes unrelated work nor blocks a necessary, authorized correction.

## Acceptance and open issues

- Run representative tasks through public entry points and inspect resulting files against independent source/target evidence; rejecting an invalid task is not successful design completion.
- Verify relevant sequence, topology, feature coordinates/strands and complete primers through export/read-back. Claim desktop SnapGene compatibility only with actual desktop evidence.
- Keep mandatory regressions reproducible with tracked/generated inputs; explicitly invoked private integrations and skipped backends are separate evidence. For release work, verify a package outside the checkout.
- For Trace changes, compare Off/Observed/Full DNA, annotations, primers, preparation, validation semantics and authoritative artifacts; injected normal-mode Trace failure must preserve otherwise successful DNA work.
- Inherited pET annotation conflicts still block formal delivery in the recorded GFP/A206K case. Resolve that source/annotation and validation interaction separately; Trace success does not close it.
- Remaining product questions: underserved real workflows, duplicated orchestration worth consolidating, host clarification reliability, measurable user effort saved and reproducible optional-backend claims.

The [current plan](../docs/development-plans/safety-phase-3-readability-v0.3.1.md) records implementation evidence and outstanding human reading validation. Historical releases/audits are indexed through History and do not certify current universal correctness.
