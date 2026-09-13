# 开发计划索引

这里存放新建和当前执行的开发计划。旧审查、历史修复记录保留原位置，不自动成为待办。只维护本索引、相关 spec 和阶段计划，不另建任务管理体系。

## 当前计划

| 计划 | 模块目标版本 | 文档修订 | 状态 | 前序 |
|---|---|---|---|---|
| [Phase 3 补救：Design Decision Trace 与可读性重构](safety-phase-3-readability-v0.3.1.md) | Evidence Trace v0.3.1 | r9 | 第四步投影与映射通过相关回归，下一项第五步；renderer 未重构 | Phase 3 v0.3 |
| [Phase 3：Living Evidence Document & Change Impact](safety-phase-3-change-impact-v0.3.md) | Evidence Trace v0.3 | r2 | 工程完成；阅读问题转入补救计划 | Phase 2 |
| [Phase 2：Evidence Applicability & Trace Usability](safety-phase-2-applicability-v0.2.md) | Evidence Trace v0.2 | r3 | 工程实现及本阶段验收完成 | Phase 1 |
| [Phase 1：Evidence Trace](safety-phase-1-trace-v0.1.md) | v0.1 | r3 | 工程验收完成，试用反馈已转化为 Phase 2 UI/Capture 改进 | 无已执行阶段 |

当前阅读/UI 规则：[design.md](design.md)；Phase 2 历史参考：[evidence-trace-phase2-reference.svg](evidence-trace-phase2-reference.svg)。

[Reader Demo 通用空白框架](evidence-trace-reader-template.md)：实现前必读的阅读结构契约，汇总可选步骤与附录；按实际任务取用，不要求全部出现。

补救的采集规则和阅读目标已同步 spec/design.md；当前 HTML 仍是 v0.3。GFP +3 bp 只作工程回归，[Reader Demo](safety-phase-3-reading-draft.md) 的第二步已获负责人审阅通过；双人计时未执行，最终页面仍待独立验收。第四步统一阅读投影已实现；[数据映射](../../references/evidence-trace-reader-mapping.md) 已整理，下一项第五步切换 HTML。Phase 4 暂停。

相关 spec：[主 skill](../../specs/core-skill.md)、[安全模块](../../specs/safety-module.md)。Phase 4 至 Phase 6 尚未创建执行计划，完整路线图留在安全 spec。

## 文件职责与版本

- **Spec**：目标、已确认决定、约束、开放问题和跨阶段路线图。不因换计划重置。
- **阶段计划**：一次只执行一个阶段，写具体改动、验收、完成证据和交接项。阶段内可以分多个实现步骤。
- **Design**：唯一 reader guideline，保存主链/旁支、条件性栏目、语言、交互与少量正反例；不另建重复指南，也不作为宿主运行时页面生成提示词。
- **索引**：标明当前计划、前序、状态与文档修订。历史计划保留并标记完成或被替代，避免多个“当前版本”。
- 文件名采用 `<module>-phase-<n>-<name>-v<目标版本>.md`。目标模块版本与主 skill 版本、文档修订号分开；文档改动不会升级软件。
- 同一计划修订原文件、递增 r1/r2，并简记改动。新阶段或实质替代计划另建文件，双向链接前后计划；旧文件不覆盖。Git 保存文件内历史。

## 防止换计划丢上下文

1. 开始或恢复：读相关 spec、本索引、当前计划及前序计划的完成/交接记录；核对实际代码和证据，不能仅凭“完成”标签。
2. 创建计划：注明编号、目标版本、文档修订、状态、关联 spec、前序与本次范围。逐项处理前序未完成项/限制及相关 spec 开放问题，标明承接、延期或取消及理由。
3. 阶段结束：在原计划记录实际实现、验收证据、遗留项、限制和下一阶段注意事项；未验收项不能标完成。长期决定同步 spec，状态同步索引。
4. 下一阶段：依据上述交接生成新计划；保留未到阶段的路线图，不重复抄入执行范围。当前阶段完成后，不自动启动后续阶段。

这些指引使上下文有固定读取路径，不保证模型不会遗漏。交接条目的明确去向和实际验收证据是复核依据。
