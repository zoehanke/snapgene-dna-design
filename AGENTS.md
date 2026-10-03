# Repository instructions

## Read before work

- For skill behavior, DNA operations, architecture, CLI, tests or releases, read [specs/core-skill.md](specs/core-skill.md).
- For biosafety, biosecurity, ethics or safety-feature research/development, read [specs/safety-module.md](specs/safety-module.md). Also read the core spec when changing the design workflow or shared code.
- For skill-facing instructions or examples, also read [SKILL.md](SKILL.md) and the relevant signature in [references/recipes.md](references/recipes.md).
- For external sequence services, read [references/privacy-and-consent.md](references/privacy-and-consent.md); for biological recommendations, read [references/source-policy.md](references/source-policy.md).

- Before creating, resuming or closing a development plan, read [docs/development-plans/README.md](docs/development-plans/README.md), the relevant spec and current plan, including the predecessor handoff. Record unresolved-item dispositions and follow the current authorized scope; a roadmap does not itself authorize later phases.
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
- Validate the changed behavior through its actual public entry point and inspect resulting files. Use focused regression tests; for release work, run the applicable suite and integrations described in README. Full suite: `python -X utf8 -B -m unittest discover -s tests`.
- Report simplification must preserve findings, evidence ownership and usable detail access.
- A new chat/shared work directory is not isolation. Freeze code/package/rubric before formal evaluation, retain contaminated and repeated runs, and report unverified items explicitly; no heldout evidence means no claim of general success-rate improvement.
- Report performed checks, failures, skips and limits accurately. Documentation-only changes need content/link checks, not a biological regression run. Historical test counts are not current validation.
- After requested development, commit and push validated changes to the user-designated development branch. Check CI for that exact commit; never merge or push to `main` without explicit authorization.
- Update the relevant spec when a product boundary or development rule changes; append consequential decisions and participant feedback to `docs/history.md`. Keep specs current and compact, history explanatory, and implementation/test details in code, references or phase plans. Superseded decisions remain in history.

## 开发与修复原则

- 目标是提高程序对真实任务的通用能力。测试通过是证据，不是目的。
- 从失败中提炼通用问题。禁止按题号、样例身份或参考答案加入特判、预设结果或检查豁免。
- 修复须保留原失败案例，并用独立输入验证成功与失败边界。不得用待测实现生成自己的验收答案。
- 禁止为通过测试删要求、改目标或放宽检查。旧测试确有错误时，须提供独立依据并记录修改原因。
- 已知题回归、陌生题评测、人工辅助结果分别报告。不得将样例通过宣称为普遍可靠，或将人工修正计为独立成功。

样例身份包括测试路径、文件名、材料身份及参考哈希；正常领域常量须说明来源与用途。每项修复先说明原行为、违反的事实或要求及泛化依据。
