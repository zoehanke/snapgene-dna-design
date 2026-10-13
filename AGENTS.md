# Repository instructions

## Workspace layout

Project/Git root contains development instructions, specs, docs, tests, benchmarks and tools. `snapgene-dna-design/` is the Skill root. Its README and SKILL.md are runtime/user entry points. Preserve standalone Skill operation; runtime modules must not import project development helpers. Build packages from the Skill root, excluding development data.

`genome-revival-toolkit/` is the project-specific Skill. It consumes the same DNA Core source; independent packages bundle the selected runtime version rather than maintaining a second implementation.

## Read before work

Use [docs/README.md](docs/README.md) as the developer document router. Read only the branch relevant to the current task; completed plans and old manuals under `docs/archive/` are historical evidence, not startup prerequisites or current instructions.

- For skill behavior, DNA operations, architecture, CLI, tests or releases, read [specs/core-skill.md](specs/core-skill.md).
- For Genome Revival Kit workflows, Project Context or Toolkit packaging, also read [specs/genome-revival-toolkit.md](specs/genome-revival-toolkit.md).
- For biosafety, biosecurity, ethics or safety-feature research/development, read [specs/safety-module.md](specs/safety-module.md). Also read the core spec when changing the design workflow or shared code.
- For skill-facing instructions or examples, also read [SKILL.md](snapgene-dna-design/SKILL.md) and the relevant signature in [references/recipes.md](snapgene-dna-design/references/recipes.md).
- For external sequence services, read [references/privacy-and-consent.md](snapgene-dna-design/references/privacy-and-consent.md); for biological recommendations, read [references/source-policy.md](snapgene-dna-design/references/source-policy.md).

- Before creating, resuming or closing a plan, read [current handoff](docs/development-plans/README.md), the relevant spec and active plan if one exists. The handoff carries unresolved items from closed plans; inspect only the predecessor evidence needed for this task. Record dispositions. A roadmap does not authorize later phases.
- For module/data/API questions read [architecture](docs/architecture.md); for setup/debugging read [developer guide](docs/developer-guide.md); for tests, reproducibility or packaging read [testing](docs/testing.md). Report UI work also reads [reader design](docs/trace-report/design.md); the blank template is optional authoring reference.
- For onboarding or changes to product direction, architecture or long-term rules, read [docs/history.md](docs/history.md). It explains decisions; it does not override current specs or expand the task.
- For benchmarks or task-success claims, read [docs/question-bank/scoring-v0.1.md](docs/question-bank/scoring-v0.1.md). Developers may inspect regression cases; never inspect independently managed heldout materials, answers, products or case-level feedback.

## Working rules

- Inspect the affected implementation, callers and tests before editing. Treat code and tests as evidence of current behavior, not proof of correctness.
- Follow the user's current task scope. Distinguish confirmed decisions, implementation facts, hypotheses and open questions. Dated audits and proposals are historical context, not an automatic backlog.
- Preserve room for alternative architectures. Prefer the smallest coherent solution to a demonstrated need; justify new abstractions, dependencies or checks by concrete benefit. Update affected callers and tests when changing interfaces.
- Treat implementation proposals and old phase gates as revisable. Within the user's authorized task, resolve stale rules using current requirements and evidence, and update affected specs/plans with the reason. Do not request permission again for already authorized work or weaken correctness to bypass a failure.
- Preserve original source material; explain annotation corrections separately from DNA changes.
- Keep user DNA, restricted fixtures and generated artifacts out of source commits. Check existing worktree changes before editing; preserve unrelated work.
- Use explicit UTF-8 for text I/O and subprocess text streams. Verify relevant Windows/non-ASCII behavior when changing these paths.
- Validate the changed behavior through its actual public entry point and inspect resulting files. Use focused regression tests; for release work, run the applicable suite and integrations described in README. From project root: `python -X utf8 -B tools/run_test_suite.py` or `python -X utf8 -B -m unittest discover -s tests`.
- Report simplification must preserve findings, evidence ownership and usable detail access.
- A new chat/shared work directory is not isolation. Freeze code/package/rubric before formal evaluation, retain contaminated and repeated runs, and report unverified items explicitly; no heldout evidence means no claim of general success-rate improvement.
- Report performed checks, failures, skips and limits accurately. Documentation-only changes need content/link checks, not a biological regression run. Historical test counts are not current validation.
- After requested development, commit and push validated changes to the user-designated development branch. Check CI for that exact commit; never merge or push to `main` without explicit authorization.
- Keep one owner per topic: specs for product contracts, architecture for modules/data/interfaces, developer guide for operations, testing for verification methods, plan index for active scope/unresolved handoffs, history for reasons. Update that owner rather than creating another latest guide. Archive completed plans; preserve their evidence and unfinished-item disposition. Contract/rule changes update the relevant spec; consequential decisions and feedback append to history.

## 开发与修复原则

- 目标是提高程序对真实任务的通用能力。测试通过是证据，不是目的。
- 从失败中提炼通用问题。禁止按题号、样例身份或参考答案加入特判、预设结果或检查豁免。
- 修复须保留原失败案例，并用独立输入验证成功与失败边界。不得用待测实现生成自己的验收答案。
- 禁止为通过测试删要求、改目标或放宽检查。旧测试确有错误时，须提供独立依据并记录修改原因。
- 已知题回归、陌生题评测、人工辅助结果分别报告。不得将样例通过宣称为普遍可靠，或将人工修正计为独立成功。

样例身份包括测试路径、文件名、材料身份及参考哈希；正常领域常量须说明来源与用途。每项修复先说明原行为、违反的事实或要求及泛化依据。
