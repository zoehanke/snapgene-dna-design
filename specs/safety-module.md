# Safety module: Evidence Trace

Updated: 2026-09-21. This spec owns current Trace behavior and evidence boundaries. [History](../docs/history.md) records why they changed; [development plans](../docs/development-plans/README.md) own phase scope and results; [usage](../references/evidence-trace.md) owns CLI/Schema details; [design.md](../docs/development-plans/design.md) owns reading rules and links the optional framework and visual reference.

## Purpose and present scope

**Evidence Trace 是事实与证据记录系统；Design Decision Trace 是其默认的人类可读组织方式。** Help researchers inspect how users, AI and programs formed a design. Genome Resurrection motivates distinguishing DNA presence, functional restoration and larger consequences; a successful construct alone establishes none of the latter.

Implemented scope: seven entry points plus an explicit local-command file observer, source observations, file handoff checks, authored process/report revisions, applicability comparisons, Change Impact and fixed offline HTML/Markdown. Current scope excludes safety scores, safe/unsafe certification, hidden-thought reconstruction and ecological prediction. Assurance Case, Conclusion Boundary and macro/laboratory framework integration remain later directions, not delivered capabilities.

The [v0.3.2 repair plan](../docs/development-plans/workflow-phase-3-usability-repair-v0.3.2.md) records the implemented v0.3.2 repairs and outstanding host/human evaluation. Real tests exposed file-export faults, large repeated report payloads, incomplete capture and unreadable default details; v0.3.1 engineering success did not establish practical usability.

## Three-layer contract

| Layer | Responsibility |
|---|---|
| Collection | Preserve observable inputs, returns, failures, file versions, supplied user/AI statements and available source material. Unobserved host activity stays outside coverage. |
| Data | AI/researcher organizes goals, stages, steps, branches, reasons and relationships. Code indexes/checks records, references, versions, stated inputs and record disposition; it does not certify scientific meaning. |
| Report | Authored report_plan chooses sourced summaries and grouping within the fixed reading format. Code renders human-readable body and details from saved facts, without a new model call on export or interaction. Raw machine objects belong in a separate technical file. Readable object details are generated deterministically for choices, files, sources and checks. |

The complete machine result includes design_process, its exact report-plan version, source records, typed relationships, coverage and findings. An unassigned record remains accessible; hiding detail in the report never deletes underlying information. Missing/stale organization produces an explicitly limited factual view, not a completed scientific narrative.

Full data retention does not require copying full records into each derived section or embedding the whole machine result in HTML. Reading projections use references and explicit record locations; large-payload changes must preserve evidence, compatibility and offline reading rather than truncate history.

## DNA boundary and collection levels

Observe actual route equivalents of task/plan/execute/validate/finalize at application boundaries. Trace changes no DNA, execution parameters, Core validation or authoritative files. Runtime results alone generate Validation and Artifact facts; preserve failures and original errors. Normal Trace errors continue DNA work with TRACE_INCOMPLETE; explicit strict policy may stop at the boundary without rolling back files. The [Core spec](core-skill.md) owns biological delivery.

| Level | Contract |
|---|---|
| Off | No new trace or organization events; existing records remain readable. |
| Observed | Record available facts and supplied reasons; no extra explanation or organization by default. Explicitly requested later organization remains possible. |
| Full | Brief public rationale during consequential choices, plus explicit host organization at meaningful stage/handoff boundaries. Joint organization/report output still has real token/time cost. |

One global setting applies to subsequent captures; each running capture retains its initial level. Development defaults to Full; release default remains open. File tools require an explicit shared trace directory. No separate model service or conversation/session registry is currently required; these are implementation choices to revisit only for a demonstrated need, not automatic future work.

Prompt boundary: design-time capture stays mostly automatic, with short contemporaneous public notes only at real choices. Full organization and report drafting occur after the relevant design result; detailed schemas are loaded then. Necessary biological checks remain in the main workflow. Compare modes under controlled tasks before changing the default; neither a prompt experiment nor this spec update changes the user's global setting.

## Attribution and evidence

- Record consequential choices, not every parameter or compliance with a user constraint. decision_kind is extensible classification, not a limit on AI design.
- actor is the submitter; decision_actor, decision_source and explanation origin describe the declared chooser/source. Missing authorship stays unknown; a supplied reference is not authentication.
- Preserve user requirements with original/summary form. User change/confirm/reject needs a source and exact affected references. Reuse user reasons as user reasons.
- Original public statements, organized summaries and later interpretations remain distinguishable. Later assistance is appended against an exact old revision; it cannot replace original rationale, fill original-explanation coverage or become Validation.
- Keep Requirement, Source, Statement, Claim, Decision, Validation and Artifact distinct. Source → Statement → Claim → Decision separates reported evidence, contextual inference and choice; a user requirement need not acquire a compulsory paper or Claim.
- Evidence relationships retain support/oppose/constrain/contextualize, aspect, strength, applicability, conditions and limitations. Candidate evidence does not automatically establish preparation-route optimality or performance.
- Source verification records method, scope, verifier, time and locator. It does not establish statement interpretation, applicability or Decision correctness. Text matching establishes occurrence, not authorship.
- Separate declared and computed applicability across organism, strain, host/chassis, construct context, temperature, medium, assay and intended use. direct / partial / extrapolated / unknown are contextual assessments, not proof of transferability.

## Versions, relationships and changes

events.jsonl is the append-only single-writer fact source. Machine export v2 uses local JSON references for repeated audit and run payloads; v1 expansion remains available. Organization and report revisions also append there; graph, manifests and views are rebuildable. Reuse existing task/plan/execution/artifact anchors to bind versions, not to claim intent or tamper-proof authorship.

Explicit context_refs freeze selected records and their dependencies; omitted context retains labeled legacy latest-record selection. Stage references pair real inputs and returns/failures. Same-run associations remain distinct from Claim-specific checks. Append time alone is not occurrence time or causality; missing old anchors are not reconstructed.

New facts make old organization stale; organization/report-only edits do not. Report plans bind an exact process version. Run/file focus preserves the supporting process; historical cutoff excludes later facts. A later-authored organization of old facts remains labeled by its actual recorded author/time.

Change records identify before/after revisions, field, values, time and scope. Automatic comparisons require matching task/Recipe identity; other baselines are explicit. AFFECTED requires explicit dependency, NEEDS REVIEW denotes possible dependency, UNAFFECTED requires complete comparable evidence of irrelevance, UNKNOWN preserves insufficient information. Missing edges are not evidence of no impact.

REASSESS, RECHECK and RERUN request reconsideration, evidence checking and program rerun respectively; STALE marks old context. They are not safety levels and do not modify original conclusions or execute tools. Reviewing an older revision does not clear a newer one.

## Reading and acceptance

- Present task context, real process, files/checks and conditional review. Document/Mind Map/Split share data, selection and expansion. Detailed provenance stays available; internal fields do not dominate the default reading layer.
- Opening a choice, file or source remains a human-reading action: explain its meaning, basis, limits and relationships. Schema, IDs, hashes and raw events are not the default detail content. Unknown types get an honest readable limitation and a separate technical entry, not recursive raw-field rendering.
- Bind evidence to its actual Decision/Claim; contextual references do not inherit another choice's evidence. Keep each relation, conditions and limits together. Omitting a choice from the main narrative must preserve its readable details. Actual changes and review findings remain readable without opening machine JSON; unfamiliar findings remain visible as unclassified records.
- research-report-v1 supplies a consistent format; task content and step count come from records. Do not hard-code example choices, invent user interventions, or create generic review/experiment warnings to fill a template.
- Separate capture faults, missing explanations, unassigned information and actionable scientific review. An unrequested check is not failure; a partial applicability judgment is not automatically a task defect.
- Untraced files remain visible as recording gaps with filename, missing relationship and practical consequence. Do not turn them into scientific todo items or fabricate history to mark them linked. Actually missing files or mismatched checked versions remain delivery issues. Every promised view/download action must have a valid target.
- For major reading-organization changes, use representative static/interactive examples and existing participant feedback to assess understanding early. This is not a blanket preapproval gate for every renderer fix. Proceed within existing authorization, record missing feedback and never claim human acceptance from model self-review or browser tests.
- Engineering evidence must cover actual public entry points, Trace three-level equivalence, normal/strict faults, old/revised records, simple/branched/changed/failed tasks and offline/keyboard/narrow-screen use. Human evidence must establish understanding of purpose, choices, support limits and checks without opening audit data.

## Revisability and remaining limits

Current modules, Schema and phase proposals may be revised within authorized work when evidence justifies the change. Preserve old records and compatibility where needed; update this spec and dependent contracts, and append consequential feedback/reversals to History. Do not make implementation preferences into permanent bans or silently weaken evidence boundaries.

Retain consent, provenance and license rules; avoid unrelated conversations, credentials and raw DNA copies by default. Current limitations include host observation coverage, declared authorship, unavailable/moved source files, exact model-cost measurement and independent human reading evidence. Core annotation/delivery defects remain Core issues rather than Trace failures. Phase numbers alone are not authorization to start later governance work.
