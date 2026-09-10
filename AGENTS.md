# Repository instructions

## Read before work

- For skill behavior, DNA operations, architecture, CLI, tests or releases, read [specs/core-skill.md](specs/core-skill.md).
- For biosafety, biosecurity, ethics or safety-feature research/development, read [specs/safety-module.md](specs/safety-module.md). Also read the core spec when changing the design workflow or shared code.
- For skill-facing instructions or examples, also read [SKILL.md](SKILL.md) and the relevant signature in [references/recipes.md](references/recipes.md).
- For external sequence services, read [references/privacy-and-consent.md](references/privacy-and-consent.md); for biological recommendations, read [references/source-policy.md](references/source-policy.md).

- Before creating, resuming or closing a development plan, read [docs/development-plans/README.md](docs/development-plans/README.md), the relevant spec and current plan, including the predecessor handoff. Record the disposition of unresolved items; execute only the selected phase.

## Working rules

- Inspect the affected implementation, callers and tests before editing. Treat code and tests as evidence of current behavior, not proof of correctness.
- Follow the user's current task scope. Distinguish confirmed decisions, implementation facts, hypotheses and open questions. Dated audits and proposals are historical context, not an automatic backlog.
- Preserve room for alternative architectures. Prefer the smallest coherent solution to a demonstrated need; justify new abstractions, dependencies or checks by concrete benefit. Update affected callers and tests when changing interfaces.
- Preserve source material and original failure cases. Correct faulty annotations or expectations with an explicit reason; do not change the biological target merely to make checks pass.
- Keep user DNA, restricted fixtures and generated artifacts out of source commits. Check existing worktree changes before editing; preserve unrelated work.
- Use explicit UTF-8 for text I/O and subprocess text streams. Verify relevant Windows/non-ASCII behavior when changing these paths.
- Validate the changed behavior through its actual public entry point and inspect resulting files. Use focused regression tests; for release work, run the applicable suite and integrations described in README. Full suite: `python -X utf8 -B -m unittest discover -s tests`.
- Report performed checks, failures, skips and limits accurately. Documentation-only changes need content/link checks, not a biological regression run. Historical test counts are not current validation.
- After requested development, commit and push validated changes to the user-designated development branch. Check CI for that exact commit; never merge or push to `main` without explicit authorization.
- Update the relevant spec when an accepted product decision changes. Keep these three documents compact; implementation details belong beside code or in existing references.
