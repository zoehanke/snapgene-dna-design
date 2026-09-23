# Core skill

Updated: 2026-09-23. This spec defines the current DNA product contract. [History](../docs/history.md) explains its evolution; [development plans](../docs/development-plans/README.md) own implementation scope, validation and handoff. [Safety spec](safety-module.md) owns Evidence Trace; [SKILL.md](../SKILL.md) and [Recipe reference](../references/recipes.md) own usage and signatures.

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

1. Inspect supplied sources and the user's stated context. First determine whether the material can be reused, needs physical preparation, or requires a new design; an already suitable donor need not be redesigned. Do not invent a conflicting recipient background. Clarify missing information when it changes the necessary decision or action.
2. Express required/forbidden components and other constraints. Choose a supported Recipe or Pipeline/structured task only for work still needed; verification-only requests need not become construction workflows.
3. Compute preparation and reactions from actual inputs; feed each real intermediate into its next step.
4. Check saved files against the request and reaction chain: sequence, junctions, topology, features and complete primers.
5. Deliver files and preparation/verification information, distinguishing candidates, components, QC designs and final constructs. Existing authorization persists; a confirmation interface is not grounds to ask again unnecessarily.

Lead the answer with the material conclusion, whether new design is needed and the shortest next action. Place consequential conditions at the step they affect; do not bury an established result under generic cautions. Include existing main artifacts, explanatory material and generated Trace links in the first handoff. Supplied design files are not physical DNA, but this distinction is not grounds to invent an unnecessary design step.

## Product contracts

- Practical task completion and correct artifacts take priority over tool counts, test counts or review frameworks.
- Host AI handles intent and strategy; executable tools compute sequences and reactions. A desired sequence is not proof of PCR amplification from the supplied template and delivered primers.
- Assembly inputs must be supplied prepared material or products of an explicit preparation step; include real backbone preparation where required.
- Preserve source, backbone, inserted-feature and primer annotations through transformations and export. Feature locations govern transformed primer coordinates; verify binding cores at those locations. A clipped primer site remains an explicitly partial annotation, not a complete binding site. Explain source annotation corrections separately from DNA changes.
- Keep actual coordinate, strand, compound-location and circular-origin conventions consistent across each interface; no implicit biological defaults without evidence and applicability.
- Preserve compound locations in biological order. Reject contradictory primer annotations instead of reordering them to obtain an export. A binding site split across the ends of a linear product is not an intact site, even if all its bases remain annotated.
- Missing checks, failed runs, components and historical successes must not be presented as newly verified complete constructs. Do not change the biological target or relax validation merely to obtain a pass.
- Bind checks to their actual object and scope: donor structure, exported file, integrated-locus model and cell phenotype are different conclusions. Investigate inherited annotation failures against source and product; neither blanket rejection nor unsupported exemption is acceptable.
- Sequence/file checks establish their stated computational scope, not wet-lab performance, whole-genome specificity or safety. File hashes bind versions, not biological correctness.
- Preserve external-service consent, provenance and distribution/license requirements. Local tools do not imply that the host never transmits data.

## Evidence Trace integration

Trace observes each route's actual inputs, returns and files. It does not change DNA, parameters, planners, Handlers, Core validation or authoritative artifacts; a Recipe run need not invent a ConstructionTask history. Missing/stale organization is a report condition, not a reason to modify the design.

The host or researcher explicitly organizes captured records and may author a report plan in the same response; code checks references/versions and renders the saved result. This is real AI work. Normal capture failures preserve DNA execution; explicit strict policy can stop at an execution boundary without rewriting completed files. Mode, attribution and report contracts are maintained in the [safety spec](safety-module.md).

Keep design-time guidance focused on the task, necessary correctness checks and minimal capture; load full Trace organization/report instructions after the relevant design conclusion is available. Trace metadata gaps must not become biological gates. Prompt interference is a hypothesis to test under controlled conditions, not an established property of a model.

## Architecture and rule changes

Current modules and orchestration are implementation choices, not permanent restrictions. Within the authorized task, revise a stale spec/plan when observed behavior or user feedback warrants it; explain the tradeoff, update affected callers/tests and record major reversals in History. Preserve the product contracts above. A historical phase boundary neither authorizes unrelated work nor blocks a necessary, authorized correction.

## Acceptance and open issues

- Run representative tasks through public entry points and inspect resulting files against independent source/target evidence; rejecting an invalid task is not successful design completion.
- Replaying a reported success/failure is necessary regression evidence, not proof of general readiness. Check independent inputs and both valid and invalid boundaries of the changed contract; retain unmet acceptance items.
- Verify relevant sequence, topology, feature coordinates/strands and complete primers through export/read-back. Claim desktop SnapGene compatibility only with actual desktop evidence.
- Keep mandatory regressions reproducible with redistributable or generated inputs; external-material integrations and skipped backends are separate evidence. For release work, verify a package outside the checkout, including mandatory Trace A/B checks, rather than relying on fixtures excluded from that package.
- For Trace changes, compare Off/Observed/Full DNA, annotations, primers, preparation, validation semantics and authoritative artifacts; injected normal-mode Trace failure must preserve otherwise successful DNA work.
- Inherited pET annotation conflicts still block formal delivery in the recorded GFP/A206K case. Resolve that source/annotation and validation interaction separately; Trace success does not close it.
- Remaining product questions: underserved real workflows, duplicated orchestration worth consolidating, host clarification reliability, measurable user effort saved and reproducible optional-backend claims.

The [preceding usability repair](../docs/development-plans/workflow-phase-3-usability-repair-v0.3.2.md) covers task priority, prompt isolation, primer export and scoped validation as well as Trace usability. Primer extraction/export and staged guidance are implemented; host behavior improvement still needs controlled evidence; the [predecessor](../docs/development-plans/safety-phase-3-readability-v0.3.1.md) preserves earlier engineering evidence. Historical releases/audits do not certify current universal correctness.


## 2026-09-22 verified scope

The [engineering cycle](../docs/remediation-plan.md) supersedes the earlier phase as current work. [Final evidence](../docs/final-remediation-report.md) records failures and limits as well as passes. No remote push or public submission is authorized in this cycle.

| Status | Scope |
|---|---|
| IMPLEMENTED | Shared source parsing and annotated Handler execution; task/source-derived component checks; failed or contradictory validation cannot authorize delivery. |
| VALIDATED | Independent positive/negative public-entry tests for sequence, source version, compound/negative features, task/plan/receipt tampering and file read-back. Existing regression, actual PCR demo, Primer3, local model and Cas-OFFinder synthetic-reference tests have separate recorded results. This is bounded software evidence. |
| EXPERIMENTAL | Legacy intent planning, sequence-only reaction approximations, predictive guide scores and scientific generalization beyond tested inputs. |
| PLANNED | Further real-user/host comparisons, independently curated problematic source annotations and representative wet-lab validation; no automatic authorization for new modules. |
| OUT OF SCOPE | Inferring experimental success, certifying biological safety or ecological effects from sequence/file checks. |

Non-Composite ConstructionTask handlers model declared sequence/annotation changes. Their plan and delivery `scope_note` must state that physical preparation is not established; use an actual Recipe/Pipeline for preparation claims. New plans bind `product_features` and scope to the plan hash. Regenerate old plans missing the annotation contract; do not reuse old receipts as current evidence.

Derive translation only from a valid complete CDS with no supplied translation. Do not overwrite conflicting source translations or demote invalid CDS annotations to make validation pass. Recompute expected components and feature transformations from the original task/source, not mutable plan declarations.

Execution and validation receipts require their version hashes. An explicitly requested desktop verification must fail when its executable or valid boolean result is missing. Each delivery attempt owns a fresh in-directory staging folder; failure cleanup must preserve another attempt's files and must not derive filesystem paths from task/recipe labels.

Release packaging uses reviewed tracked paths, or an explicit source list outside Git. Exclude untracked local inputs and known restricted/external fixtures from the redistributable variant. A file's presence in Git is not proof of redistribution rights. Validate the extracted package separately from the checkout.

The reopened local acceptance now passes all 54 coverage targets at the existing thresholds, including legacy preview. Keep its scope distinct from external user effectiveness, wet-lab outcomes, other-platform CI and authorized publication.

Legacy-preview handoff now uses an immutable snapshot in preview/delivery, separate from preview working files. Preview working files and delivery snapshots are separate; snapshots include actual omission reasons, stay consistent with their hashes and cannot absorb stale outputs. Missing/unreadable sources and unverified state block preview handoff. Its deprecated formal route stays blocked. Coverage instrumentation must not change which regression scenarios execute.
