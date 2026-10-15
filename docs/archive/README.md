# 历史档案

这里保存旧计划、审查、研究和合并前指南，不是当前规范或自动待办。文件内“当前基线”“必须先做”“禁止push”等措辞属于当时范围，不覆盖现行spec及本次授权。

默认从[开发入口](../README.md)及[当前交接](../development-plans/README.md)开始。只有追查特定决定、失败或历史实证时才打开对应原件。归档不表示未关闭事项已解决，未决项集中在交接页。

| 分类 | 保存内容与用途 |
| [块S数据链](plans/data-chain-s-2026-10-15.md) | 2026-10-15来源/可选Kit文件闭环/运行卡片实施与本地/独立包证据；精确CI尾项由仓库外交付索引承接，不代表K验收、冻结或真人理解 |
|---|---|
| `plans/` | 已结束Phase 1至3.1、v0.3.2及v1.0.2至1.0.4计划、设计草案/审查版、案例和视觉原件 |
| `reviews/` | 早期工程审查、修复及发布周期结果，旧试题草案 |
| `research/` | AI与生物安全、可信度及Archify调研，包含尚未采纳的路线 |
| `guides/` | 合并前架构/数据流/接口/扩展/测试/复现指南，保留旧证据和示例 |
| `development/`、`architecture/` | v0.9.0/v0.9.1旧手册、基线和重构要求，不能当作现行开发入口 |

常用追溯：[v1.0.4通用审查](plans/general-capability-audit-v1.0.4.md)、[v1.0.3宿主交接](plans/workflow-host-readiness-v1.0.3.md)、[v0.3.2实用性修复](plans/workflow-phase-3-usability-repair-v0.3.2.md)、[2026-09-22最终报告](reviews/final-remediation-report.md)、[三层设计](plans/safety-phase-3-three-layer-design-v0.3.1.md)、[人工解释](plans/safety-phase-3-three-layer-review-v0.3.1.md)。

早期原件：[重构清单](RECONSTRUCTION-CHECKLIST-20260903.md)、[开发manifest](DEVELOPMENT-MANIFEST-v0.9.1-dev2.json)、[旧升级记录](upgrade-log.md)。历史叙述不为当前方案重写，移动时只修正引用；具体修改历史仍由Git保留。

2026-10-05：[统一分子契约v2.0.0实施验收](plans/unified-molecule-contract-v2.0.0.md)，包含T01至T09、旧预期调整理由、性能、包验证和六环境代码CI；未关闭外部验证由当前交接继续管理。

2026-10-05：[分子契约v2.0.1残留修复](plans/molecule-contract-v2.0.1.md)，固定F01至F08，包含原反例、独立边界、覆盖、冻结性能、三档独立包及六环境实施CI；保留前序未验证范围。

2026-10-06：[架构调研与现存结构审查](reviews/architecture-research-2026-10-06.md)，保存一手来源、63e97a0仓库外快照、16方面审查与公开入口/真实Primer3证据；优化方向由现行架构管理，运行改造尚未执行。

2026-10-11：[实际执行闭环2.2.1收尾](plans/actual-execution-closure-v2.2.1.md)，保存r1至r6、原失败、真实宿主与开发者辅助结果、包/CI及性能。r6实施和验收结束，复杂突变自主性、融合边界、阶段QC与后续验证由当前交接承接。

2026-10-11：Genome Revival Toolkit 0.1.0（原稿曾公开，现已移出当前树并完整私有备份；历史仍可见），本轮三个Kit、Context、Trace整合、冻结包、正常宿主核心与本地软件/Wiki准备已核。受检主方案与错误补充文稿分开；正式提交、未知项目数据及外部验证由当前交接承接。
