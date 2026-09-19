# 开发计划索引

这里存放新建和当前执行的开发计划。旧审查、历史修复记录保留原位置，不自动成为待办。本索引负责计划导航，不另建任务管理体系。

初次接手或调整长期方向时，先读[项目历史](../history.md)。Spec 管当前契约，History 管形成原因，计划管具体实施与证据；旧计划中的实现建议可在当前授权范围内修订，不作为永久架构限制。

## 当前计划

| 计划 | 模块目标版本 | 文档修订 | 状态 | 前序 |
|---|---|---|---|---|
| [Phase 3 补救：Design Decision Trace 与可读性重构](safety-phase-3-readability-v0.3.1.md) | Evidence Trace v0.3.1 | r13 | 三层接口、正式报告与真实案例工程验收完成；规范修订方式已澄清，独立真人理解及原 Core 注释交付问题保留 | Phase 3 v0.3 |
| [Phase 3：Living Evidence Document & Change Impact](safety-phase-3-change-impact-v0.3.md) | Evidence Trace v0.3 | r2 | 工程完成；阅读问题转入补救计划 | Phase 2 |
| [Phase 2：Evidence Applicability & Trace Usability](safety-phase-2-applicability-v0.2.md) | Evidence Trace v0.2 | r3 | 工程实现及本阶段验收完成 | Phase 1 |
| [Phase 1：Evidence Trace](safety-phase-1-trace-v0.1.md) | v0.1 | r3 | 工程验收完成，试用反馈已转化为 Phase 2 UI/Capture 改进 | 无已执行阶段 |

当前阅读/UI 规则：[design.md](design.md)；Phase 2 历史参考：[evidence-trace-phase2-reference.svg](evidence-trace-phase2-reference.svg)。

当前视觉参考：[报告视觉设计 r1](evidence-trace-report-visual-design-v0.3.1.md)，含用户参考图。正式 renderer 已采用相应框架并由真实记录驱动；原型示例不作为真实事实，也不代替独立真人页面验收。

[Reader Demo 通用空白框架](evidence-trace-reader-template.md)：实现前必读的阅读结构契约，汇总可选步骤与附录；按实际任务取用，不要求全部出现。

采集、来源、组织与报告规则已同步 spec/design.md；正式 HTML 已替换 v0.3 的单 Decision 组织。GFP +3 bp 继续作工程回归，静态 [Reader Demo](safety-phase-3-reading-draft.md) 原接受记录保留，用户未提交修改未动。真实 GFP 对照/A206K 已完成新接口验收；独立真人试读未执行。Phase 4 继续暂停。

相关 spec：[主 skill](../../specs/core-skill.md)、[安全模块](../../specs/safety-module.md)。Phase 4 至 Phase 6 尚未创建执行计划，完整路线图留在安全 spec。

## 三层重构设计与机器结果

2026-09-20，目标为 Evidence Trace v0.3.1，文档 r4。在 AI／人语义组织、完整机器过程和独立 report_plan 基础上，细化 research-report-v1 默认报告格式；顶层结构由程序固定，AI 在其中填写有来源的内容。两版逐章对应，代码已实现；旧版本保留在 Git，实际证据记录在当前计划，不重写历史结果。

- [开发设计](safety-phase-3-three-layer-design-v0.3.1.md)：采集入口、数据契约、关系处理、报告接口、文件改动、兼容及验收。
- [人工理解与审查](safety-phase-3-three-layer-review-v0.3.1.md)：面向不熟悉编程的负责人，解释各层原理、信息来源和需要确认的选择。
- [完整机器结果示例](safety-phase-3-process-example-v0.3.1.json)：可解析、引用完整的模拟 JSON，区分原始记录、过程及报告编排，不是实际运行证据。

依据：[可信度研究](../EVIDENCE-TRACE-TRUST-ARCHITECTURE-20260914.md)、[真实使用审查](../EVIDENCE-TRACE-REAL-USE-AUDIT-20260915.md)、[Archify 对照](../ARCHIFY-REFERENCE-REVIEW-20260919.md)。已确认职责同步两份 spec、design.md 和 Phase 3.1；接口细节仍可审查调整，不能把“结构核对通过”写成科学意义已证明。

## 文件职责与版本

- **Spec**：目标、已确认决定、约束、开放问题和跨阶段路线图。不因换计划重置。
- **History**：方向、关键取舍及重要反馈的形成原因。追加被推翻决定的后续解释，不复制代码变更和日常测试记录；长期契约改变时同时改 Spec。
- **阶段计划**：一次只执行一个阶段，写具体改动、验收、完成证据和交接项。阶段内可以分多个实现步骤。
- **Design**：唯一 reader guideline，保存主链/旁支、条件性栏目、语言、交互与少量正反例；不另建重复指南，也不作为宿主运行时页面生成提示词。
- **索引**：标明当前计划、前序、状态与文档修订。历史计划保留并标记完成或被替代，避免多个“当前版本”。
- 文件名采用 `<module>-phase-<n>-<name>-v<目标版本>.md`。目标模块版本与主 skill 版本、文档修订号分开；文档改动不会升级软件。
- 同一计划修订原文件、递增 r1/r2，并简记改动。新阶段或实质替代计划另建文件，双向链接前后计划；旧文件不覆盖。Git 保存文件内历史。

## 防止换计划丢上下文

1. 开始或恢复：读相关 spec、本索引、当前计划及前序计划的完成/交接记录；核对实际代码和证据，不能仅凭“完成”标签。
2. 创建计划：注明编号、目标版本、文档修订、状态、关联 spec、前序与本次范围。逐项处理前序未完成项/限制及相关 spec 开放问题，标明承接、延期或取消及理由。
3. 阶段结束：在原计划记录实际实现、验收证据、遗留项、限制和下一阶段注意事项；未验收项不能标完成。长期决定同步 spec，状态同步索引。
4. 下一阶段：依据交接和当前任务确定范围，不因阶段完成自动扩张工作。旧方案需要改变时，说明证据、影响与被替代决定，同步 Spec/计划；重大转向与参与者反馈追加到 History。已有明确授权不重复询问。

这些指引使上下文有固定读取路径，不保证模型不会遗漏。交接条目的明确去向和实际验收证据是复核依据。
