# Changelog

## 1.0.2 · 2026-09-30 delivery repair

- Restriction and Type IIS annotations use the shared slicing contract: clipped CDS features retain partial status and correct phase, and do not assert their source's complete translation. Cut primers remain partial annotations.
- Explicit peptide-tag and protease-cleavage products are distinguished from complete proteins while retaining translation, codon-table and internal-stop validation.
- Competing delivery attempts explicitly reject an existing delivery and preserve the winner instead of surfacing a Windows permission error.
- Installations bind a verified package to its source commit and local Python executable; prior installs are preserved in a backup. Host usability testing remains separate from regression checks.

## 2026-09-22/23 engineering audit, incorporated into 1.0.2

Historical local remediation on the development branch; VERSION was 1.0.1 during that cycle. Its evidence and limits remain in the [final engineering report](docs/final-remediation-report.md). The current delivery repair packages those changes with the fixes above.

- Preserve annotated records across task handlers, recompute constraints from actual sources, and reject incomplete or contradictory delivery receipts.
- Correct double-digest execution, primer search boundaries, MSA/Sanger results, rejected state updates and file-conversion failures.
- Bind Trace choices to file versions, distinguish observed presence from generation, and minimize captured credentials without changing DNA execution.
- Package reviewed sources only; keep mandatory regressions independent of nonredistributable material. Test extracted packages separately.
- Add reproducible benchmarks, current user/developer documentation and source-backed iGEM 2026 preparation materials. External user, scientific and submission evidence remains separate.
- Complete legacy-preview acceptance: immutable snapshots, no stale artifact handoff, explicit source/state failures and real CLI coverage. Restore all scenarios under instrumentation and enable required Primer3 checks in CI.

## 1.0.0 · 可用大版本

First usable major release, promoting the verified 0.9.4 runtime without changing its reaction algorithms. Includes the accumulated real-workflow repairs, complete-oligo primer design, actual consecutive PCR preparation, per-junction Gibson homology placement, source annotation preservation, strict CDS checks and current-invocation delivery state.

Validation: 727 tests passed, 7 optional integrations skipped; 41 focused checks passed after the final fixes. Five source-complete paper-based tasks and ten official SnapGene Native save/readback checks passed. Q4 remains untested because its original donor material is unavailable. These results establish the tested software workflows, not wet-lab success rates.

Release scope and evidence: `docs/RELEASE-v1.0.0.md`. Git tag: `v1.0.0`.

## 0.9.4

- Preserve complete source records through Pipeline tools. Reject path text as DNA, protein results as DNA outputs, and requested topology that conflicts with the actual reaction. Failed invocations replace the current result while retaining historical artifacts.
- Correct circular restriction backbone selection, origin-crossing deletions, clipped compound features and stale CDS translations. Share strict CDS validation between runtime checks and the standalone validator, respecting explicit genetic codes and partial feature evidence.
- Evaluate complete oligos, including homology and tag tails. Select feasible binding temperatures within the existing bounds, report actual annealing estimates, and retain Primer3 structural checks for extended cores selected with Biopython nearest-neighbor calculations.
- Add the public `prepare_pcr_fragment` tool. Long additions use consecutive actual PCR products with complete primer orders, source annotations and intermediate files. Gibson chooses homology placement per junction to find feasible reactions without changing target DNA.
- Correct public tool parameter aliases, bare-list Pipeline input and continuous primer complementarity reporting. Restore complete source features without retaining redundant machine-clipped copies.
- Replace synthetic benchmark release claims with workflow smoke results. Invalid repetitive fixtures remain unchanged and are tested as refusals; successful design evidence comes from the real paper workflows.

Current acceptance and development evidence: `docs/FINAL-RELEASE-AUDIT-20260907.md` and `docs/FINAL-RELEASE-DEVELOPMENT-20260907.md` in the source checkout.

## 0.9.3

- Require complete CDS stop codons independently of the observed result; share explicit partial-feature evidence with the standalone validator.
- Bind candidate promotion to the checked sequence and repeat the original biological context on the saved record.
- Derive verification PCR, primer regions, Sanger distance and diagnostic digests from actual template reactions and topology. Export source annotations and verification primers in Native files.
- Restore the original test templates. The original high-GC GOI now works by moving homology to reverse primers, retaining full-oligo structural checks and unchanged target DNA. Internal annealing may restore source boundaries through actual 5′ primer extensions; actual PCR still supplies assembly input.
- Keep legacy point-edit annotations in GenBank. Refuse unsupported biological edits in the old keyword preview route instead of labeling concatenation as those edits. Propagate rejection status and actual diagnostics.

Acceptance and corrected historical evidence: `docs/INTEGRITY-AUDIT-AND-REPAIR-20260907.md`. Previous test counts include invalid positive expectations and cannot establish biological usability. Five paper tasks passed public-CLI replay and independent reaction/artifact checks. Official Native save preserved all 21 features and 3 full verification primers. Final suite: 688 passed, 7 optional tests skipped (695 total), with actual Primer3 enabled.

## 0.9.2

- Compute PCR from complete templates and actual oligos, reject competing complete binding cores, and preserve circular boundaries and source features.
- Add multi-template Gibson preparation, inverse-PCR mutation preparation, compatible vector/insert restriction enzymes, actual duplex-cut projection and native expression-start checks.
- Prepare complete pML104 guide cassettes and explicit HDR replacement donors with actual oligos, edited genomic records and preserved partial CDS meaning.
- Check Recipe required/forbidden DNA components on saved candidates through the existing goal validator.
- Export full primers separately from binding intervals, retain original source topology, normalize the origin endpoint, and check Native files using official Native-to-Native saves.
- Include runtime schemas in install packages and report non-biological qualifier normalization separately from lost biological information.

Validation: a full 688-test run with the real Primer3 backend passed; the final Native compatibility changes passed 29 focused tests. Five composite research tasks were checked against actual template/oligo reactions and external sequence references. Optional Cas-OFFinder, prediction-model and live-NCBI integrations were not part of this acceptance. Laboratory efficiency and whole-genome specificity are not established by these checks.

## 0.9.1-dev1

Imported development baseline from the local architecture-recovery worktree.
This version is not release-ready. See
`docs/development/BASELINE-STATUS.md` for the independent review status.
