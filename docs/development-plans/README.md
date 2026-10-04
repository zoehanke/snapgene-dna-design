# 当前状态与开发交接

2026-10-04更新。这里管理当前任务和未关闭事项，不把所有历史阶段列作“当前计划”。开发入口见[docs](../README.md)，契约见两个spec，改变原因见[history](../history.md)。

## 当前授权与已结束工作

当前授权是编写[统一分子契约与连续工作流改造计划](unified-molecule-contract.md)，范围为7项契约/工程改造和2项算法修复的开发方案。目标架构已记录，T01至T09实现未开始，目标发布版本待定。本次文档授权不自动启动运行代码改造。

此前开发文档收敛、布局迁移和v1.0.4通用修复已结束，原证据和未关闭事项保留。

| 记录 | 当前分类 |
|---|---|
| [统一分子契约](unified-molecule-contract.md) | 当前开发方案；仅文档已形成，实施与性能验收待执行 |
| [目录迁移](../archive/plans/workspace-layout-v1.0.4.md) | 已结束；`d5cfa09`独立包及六环境CI通过 |
| [通用能力审查](../archive/plans/general-capability-audit-v1.0.4.md) | 已结束的修复/回归；未完成原九题独立验收，不是保留评测 |
| [原宿主修复](../archive/plans/workflow-host-readiness-v1.0.3.md) | 已结束的实现；下面承接未验收项 |

## 未关闭事项

| 事项 | 当前事实与处理边界 | 原记录 |
|---|---|---|
| 原九题完整复核及同宿主重测 | 已知开发题；换路、校订和污染分别统计，不算陌生题；未完成独立整体验收 | [v1.0.3交接](../archive/plans/workflow-host-readiness-v1.0.3.md)、[v1.0.4分类](../archive/plans/general-capability-audit-v1.0.4.md) |
| 宿主提示干扰、成本及实际用户价值 | 未做受控无Skill/旧版/新版或模式对照；代码三档一致性不能代替 | [v0.3.2交接](../archive/plans/workflow-phase-3-usability-repair-v0.3.2.md) |
| 新版报告的独立真人理解 | 浏览器工程证据已有，陌生读者回答尚未验证；未提交Reader Demo保留原文件，其三条旧产物链接已不可达，待稿件接续时核对 | [阅读规则](../trace-report/design.md)、[Demo](safety-phase-3-reading-draft.md) |
| 复杂源注释及制备/QC限制 | pET/Chr1完整表达边界仍需逐件检查；不自动校订源文件、不豁免失败；候选搜索失败如实报告 | [v0.3.2](../archive/plans/workflow-phase-3-usability-repair-v0.3.2.md)、[v1.0.3](../archive/plans/workflow-host-readiness-v1.0.3.md) |
| 外部试用、专家/实验与真实后端泛化 | 负责人确认外部试用及湿实验未安排；公开合成/本机证据不能补成实验或全基因组保证 | [团队任务](../igem/best-software-task-table.md)、[外部证据](../igem/external-evidence-needed.md) |
| 正式iGEM提交与完整教学交接 | 权属、账号发布和提交回执仍需团队；原14节教学未整体完成，文档存在不等于讲解完成 | [iGEM](../igem/README.md)、[工程交接](../archive/reviews/final-remediation-report.md) |

独立保留评测由独立评测者管理；开发者只接错误类别/汇总。Phase 4至Phase 6仍未授权执行，后续方向留在安全spec。未关闭事项不自动构成当前开发范围。

## 计划维护

有新开发授权时才建立或恢复相应阶段计划，标明范围、目标版本、修订、相关spec和承接项。只查本任务相关前序证据，不要求通读全部前序计划。

结束后在原计划记录实际实现、检查、失败/跳过、限制及每项去向；状态和未关闭项更新此页，已结束计划进入[历史档案](../archive/README.md)。新计划不能清空旧缺口；延期或取消须写理由。重要产品边界变更同步spec和history。

报告开发通常先读[design](../trace-report/design.md)，需要写静态稿时再查[可选框架](../trace-report/reader-template.md)。三层JSON示例和旧Phase稿在档案，仅用于有针对性的追溯。

## 本次文档整理验收

合并前指南/旧手册、阶段计划和审查原件均有档案去向；六类未关闭事项仍保留，验收阈值和真人要求不变。121份Markdown、500条本地链接已核对，无新增断链；49份历史Markdown叙述保留，399份Skill/测试/工具及实证文件字节未变；docs根目录Markdown由31份收敛为9份；本次没有运行生物学回归或声称新增实验验证，精确提交CI另行核对。Reader Demo三条旧产物链接是保留稿的既存缺口，不算本次新增断链。
