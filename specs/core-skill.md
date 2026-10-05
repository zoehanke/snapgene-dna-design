# Core skill

Updated: 2026-10-06. This spec defines the current DNA product contract. Developer documents have a [single router](../docs/README.md); closed plans are historical references, while unresolved handoffs stay in the plan index. [History](../docs/history.md) explains its evolution; [development plans](../docs/development-plans/README.md) own implementation scope, validation and handoff. [Safety spec](safety-module.md) owns Evidence Trace; [SKILL.md](../snapgene-dna-design/SKILL.md) and [Recipe reference](../snapgene-dna-design/references/recipes.md) own usage and signatures.

## Goal and current functionality

Workspace layout: project/Git root owns AGENTS, specs, developer docs/tests/tools and the project navigation README. `snapgene-dna-design/` is the standalone Skill root with its own user README, SKILL.md, runtime code and references. Its packaged README is the same usage document maintained in source. Runtime code must not depend on the outer development tree; packages contain only the tracked Skill subtree and permitted materials, not developer records or grader tools. The migration changes paths and packaging, not DNA semantics.

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
- Shared Primer3 subprocess integration belongs in Core tools; CLI compatibility imports do not own calculation logic. QC primer selection measures actual oligo structures as well as binding/Tm. It checks the recombinant template, while parental discrimination remains a separate control.
- Inverse-PCR mutagenesis uses that shared design search and actual complete oligos, not fixed-length flanks assumed to work. No solution retains the original edit requirement and permits another supported route. Export/import canonicalizes source primer binding metadata before retention comparison without dropping source features. A guide-preparation operation carries its actual PCR and circularization evidence.
- Keep the original must-haves before route selection; revise an unsuitable route instead of dropping a requirement. Recipe goals may reference named original source features. The exact PCR CLI uses the shared Core model, including 5-prime tails, and reports missing/ambiguous binding as failure. Declared preparation products are replayed against actual templates and oligos before export; tables name their template coordinate reference. A final file edited after that check needs renewed validation.
- Assembly inputs must be supplied prepared material or products of an explicit preparation step; include real backbone preparation where required.
- Preserve source, backbone, inserted-feature and primer annotations through transformations and export. Feature locations govern transformed primer coordinates; verify binding cores at those locations. A clipped primer site remains an explicitly partial annotation, not a complete binding site. Explain source annotation corrections separately from DNA changes.
- Keep actual coordinate, strand, compound-location and circular-origin conventions consistent across each interface; no implicit biological defaults without evidence and applicability.
- Preserve compound locations in biological order. Reject contradictory primer annotations instead of reordering them to obtain an export. A binding site split across the ends of a linear product is not an intact site, even if all its bases remain annotated.
- Missing checks, failed runs, components and historical successes must not be presented as newly verified complete constructs. Do not change the biological target or relax validation merely to obtain a pass.
- Bind checks to their actual object and scope: donor structure, exported file, integrated-locus model and cell phenotype are different conclusions. Investigate inherited annotation failures against source and product; neither blanket rejection nor unsupported exemption is acceptable.
- Sequence/file checks establish their stated computational scope, not wet-lab performance, whole-genome specificity or safety. File hashes bind versions, not biological correctness.
- Preserve external-service consent, provenance and distribution/license requirements. Local tools do not imply that the host never transmits data.

## Workflow freedom and reuse

Confirmed direction, 2026-10-06; orchestration changes remain unimplemented. [Architecture](../docs/architecture.md#流程复用与结构收敛方向) owns the findings and proposed interfaces; [handoff](../docs/development-plans/README.md) owns execution scope.

- A workflow can be composed by the host, reused from built-in methods, or adapted from a user-supplied workflow. Its origin does not require a separate execution, validation or delivery architecture.
- Task expresses the user's goal, materials and constraints; Pipeline expresses this run's steps; Recipe packages reusable method knowledge and algorithms. These are distinct responsibilities, not three mandatory parallel routes. Their current names and classes are implementation choices.
- The host can reuse a whole method, combine it with atomic operations, or execute a step and revise the remaining route from observed results. Required scientific parameters remain explicit; a fixed task classification or fully populated upfront form must not substitute for this reasoning.
- Reuse preserves mature candidate search, conditional preparation, method-specific checks and actual intermediates. It does not require flattening every Recipe into a static step list. A reused workflow is recomputed for its actual materials and conditions, not treated as a previous successful product.
- Shared orchestration preserves full molecules, explicit product selection, result roles, check subjects/scopes and source-derived validation. Efficiency changes reduce redundant computation and default host payloads while keeping required checks and inspectable full results.

## Unified molecule and result contract

The [implementation plan](../docs/development-plans/unified-molecule-contract.md) owns T01 through T09 evidence and final acceptance. v2 replaces public atomic-tool strings/dictionaries with `ToolResult(products, analysis, checks)`. DNA products use `Molecule`, a SeqRecord subclass with FragmentEnd, explicit topology/strandedness, native features, input-version references and JSON wire conversion. Analysis is never automatically selected as DNA. Multiple products require explicit selection. Public transforms preserve original input and nested metadata. Host route selection remains free.

A schema-valid object is not a correct molecular transformation. Verify consecutive real records and saved-file read-back, with measured runtime/copy cost. [Architecture](../docs/architecture.md#统一分子契约目标架构) owns exact data and boundary semantics. File supplements preserve otherwise unsupported attributes and bind actual file-visible content; they cannot overwrite edited file facts or substitute for native-reader compatibility. FASTA preserves sequence only. Record versions identify model states, not authenticated physical samples.

Validation records separate `sequence_model`, `preparation_model`, `file`, and `user_goal`, with actual subject/version and conditions. ConstructionTask and Pipeline accept `validation_requirements`; defaults require sequence/file/user-goal checks. Requiring preparation blocks a sequence-edit-only result. A checked reaction chain is computational evidence, not proof of physical stock or wet-lab success. Pure annotation changes and circular origin rotation can retain preparation evidence through verified physical-material equivalence, never by copying a previous PASS to a new object. Rotation requires the actual parent version and a matching coordinate map; sequence or physical-state changes do not inherit this evidence. Trace remains optional and cannot supply missing biological validation.

Legal DNA representations share one input interpretation, including primer analyses. No-op transforms preserve physical state and independent mutable data. Compound extraction judges each original feature once; rotations retain original fuzzy outside boundaries while newly split boundaries are exact. Ligation maps per-base data to the retained bases, with unknown values where source data is absent. Shared record annotations may be retained only when present and equal across all inputs; differing or missing fields are disclosed with input-version references in `analysis.annotation_conflicts`, not silently attributed to the complete product.

Exact feature identity, controlled domain aliases and explicit ambiguity replace short-substring/first-match selection. QC searches candidate pairs within unchanged windows and thresholds; no solution, incomplete search and unavailable/failed backends are distinct. Actual package, full regression, performance and CI acceptance remain recorded in the plan until completed; no heldout success-rate claim follows from this migration.

## Evidence Trace integration

Trace observes each route's actual inputs, returns and files. It does not change DNA, parameters, planners, Handlers, Core validation or authoritative artifacts; a Recipe run need not invent a ConstructionTask history. Missing/stale organization is a report condition, not a reason to modify the design.

The host or researcher explicitly organizes captured records and may author a report plan in the same response; code checks references/versions and renders the saved result. This is real AI work. Normal capture failures preserve DNA execution; explicit strict policy can stop at an execution boundary without rewriting completed files. Mode, attribution and report contracts are maintained in the [safety spec](safety-module.md).

Keep design-time guidance focused on the task, necessary correctness checks and minimal capture; load full Trace organization/report instructions after the relevant design conclusion is available. Trace metadata gaps must not become biological gates. Prompt interference is a hypothesis to test under controlled conditions, not an established property of a model.

## Architecture and rule changes

Current modules and orchestration are implementation choices, not permanent restrictions. Within the authorized task, revise a stale spec/plan when observed behavior or user feedback warrants it; explain the tradeoff, update affected callers/tests and record major reversals in History. Preserve the product contracts above. A historical phase boundary neither authorizes unrelated work nor blocks a necessary, authorized correction.

## Acceptance and open issues

Evaluation integrity: runtime must not return reference answers or waive checks based on benchmark/sample identity. Fixed domain components and protocol constants require stated purpose/provenance; their presence alone is not evidence of cheating. Prove defects and check independent positive/negative inputs before changing code. Preserve failed inputs and document corrected test expectations; never weaken biological requirements or thresholds to manufacture success.

Development regression and independently managed heldout evaluation are separate. Developers must not inspect heldout inputs, answers, products or case-level feedback. Formal evaluation freezes code, package, rubric and conditions; actual tool/filesystem/history/network access must be checked. Shared-directory or new-chat trials are not isolation. Retain contaminated runs outside the heldout denominator and every repeated attempt. Record developer/human intervention and input correction; corrected-material results cannot count as original-input independent success. Scoring metadata records examiner declarations, not programmatically proven isolation. Without qualifying heldout evidence, report regression fixes only, with no claim of improved general task-success rate.

- Run representative tasks through public entry points and inspect resulting files against independent source/target evidence; rejecting an invalid task is not successful design completion.
- Replaying a reported success/failure is necessary regression evidence, not proof of general readiness. Check independent inputs and both valid and invalid boundaries of the changed contract; retain unmet acceptance items.
- Verify relevant sequence, topology, feature coordinates/strands and complete primers through export/read-back. Claim desktop SnapGene compatibility only with actual desktop evidence.
- Keep mandatory regressions reproducible with redistributable or generated inputs; external-material integrations and skipped backends are separate evidence. For release work, verify a package outside the checkout, including mandatory Trace A/B checks, rather than relying on fixtures excluded from that package.
- For Trace changes, compare Off/Observed/Full DNA, annotations, primers, preparation, validation semantics and authoritative artifacts; injected normal-mode Trace failure must preserve otherwise successful DNA work.
- Preserve the original pET/Chr1 failures. Reaction clipping must use the shared partial-feature and CDS-phase contract; explicit peptide-tag/cleavage-site products are not complete proteins. Wrong translations, unknown bases and incompatible declared codon tables still fail. Evidence-backed source annotation corrections use a documented copy, never automatic mutation of the input or a validation exemption.
- Remaining product questions: underserved real workflows, duplicated orchestration worth consolidating, host clarification reliability, measurable user effort saved and reproducible optional-backend claims.

The [preceding usability repair](../docs/archive/plans/workflow-phase-3-usability-repair-v0.3.2.md) covers task priority, prompt isolation, primer export and scoped validation as well as Trace usability. Primer extraction/export and staged guidance are implemented; host behavior improvement still needs controlled evidence; the [predecessor](../docs/archive/plans/safety-phase-3-readability-v0.3.1.md) preserves earlier engineering evidence. Historical releases/audits do not certify current universal correctness.


## Delivery and compatibility contracts

Current methods and evidence boundaries are maintained in [testing](../docs/testing.md), and unfinished work in the [handoff](../docs/development-plans/README.md). The archived engineering cycle records dated evidence, not a current startup gate or permanent publication restriction.

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

An attempt that loses atomic promotion to an existing delivery reports the same explicit collision rejection as an already-existing destination. Reproduced Windows transient rename denial may retry the same verified staging directory for a bounded interval; persistent/other filesystem failures remain errors, and copying is not an atomic-promotion substitute. Installed-package evidence binds the actual source commit and file manifest, plus a checked local Python executable when supplied; source-tree tests do not validate a different installation.

Release packaging uses reviewed tracked paths, or an explicit source list outside Git. Exclude untracked local inputs and known restricted/external fixtures from the redistributable variant. A file's presence in Git is not proof of redistribution rights. Validate the extracted package separately from the checkout.

Keep historical coverage results scoped to their measured commit and environment; newer repairs do not inherit them. Record fresh checks only when actually run.

Legacy-preview handoff now uses an immutable snapshot in preview/delivery, separate from preview working files. Preview working files and delivery snapshots are separate; snapshots include actual omission reasons, stay consistent with their hashes and cannot absorb stale outputs. Missing/unreadable sources and unverified state block preview handoff. Its deprecated formal route stays blocked. Coverage instrumentation must not change which regression scenarios execute.
