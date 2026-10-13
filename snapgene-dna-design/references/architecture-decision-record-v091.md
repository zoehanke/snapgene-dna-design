# 架构决策记录 ADR-001：v0.9.1 架构恢复

- 状态：已采用（强制执行）
- 日期：2026-08-28
- 基线：v0.9.0 只读（不覆盖正式包、报告与错误证据）
- 开发目录：`<workspace>`
- 版本：`0.9.1-dev1`

## 背景

v0.9.0 真实构建审查发现：自然语言关键词解析器丢失 LLM 已理解的语义；`_intent_for_plan` 以文件顺序和全长区间补默认值；点突变缺省为 `100:A`；通用规划器把替换/扩增任务压成“骨架+片段”；验证层只检查文件自洽；多脚本可绕过验证写正式 `.gb/.dna`。结论：v0.9.0 是“DNA 工具箱 + 薄弱 Agent 壳”，中央生物学设计契约缺失。

## 决策

1. **ConstructionTask v1 成为唯一执行契约**（schema：`schemas/construction-task-v1.json`）。DesignSpec 仅保留会话/版本职责。
2. **LLM 生成 ConstructionTask，程序只做确定性校验与执行**。程序不猜 source role、interval、mutation、task kind。
3. **严格路由器**：`task_kind` 必须来自 `core/registry.py`；未迁移 kind 返回 `TASK_KIND_NOT_IMPLEMENTED`，不退回通用组装器。
4. **专用 planner**：首批迁移 `component_amplification`、`plasmid_replace`、`plasmid_insert`、`point_mutation`。
5. **三层验证**：`verified = artifact-valid AND computation-valid AND goal-valid`；experimental 方法最多 `experimental-preview`。
6. **唯一 authoritative gate**：`core.finalize()` 是唯一正式产物出口；其他路径只能 `intermediate/`、`preview/`、`experimental-preview/`。
7. **证据印章**：`source_evidence_class`（user-provided/public-record/internal-fixture/synthetic-fixture/heuristic）与 `method_maturity`（validated/experimental）独立记录并传播；产物证据等级不高于最弱关键来源。
8. **旧路径弃用**：`run_design_agent.py --mode formal` 返回 `LEGACY_AGENT_FORMAL_DEPRECATED`；旧 exploration 路径保留为预览级兼容层。
9. **危险默认值移除**：`100:A` 已删除（`MUTATION_SPEC_REQUIRED`）；组件全长选择被拒绝（`WHOLE_TEMPLATE_SELECTED_FOR_COMPONENT`）；replace 缺 interval 被拒绝（`REPLACE_INTERVAL_REQUIRED`）。
10. **历史事故负例回归**：S01/S05/S06/S08 固化在 `tests/test_historical_accidents_v091.py` 与 `tests/test_architecture_recovery.py`。

## 迁移状态

| task_kind | 状态 |
|---|---|
| component_amplification | 已迁移（负链、跨原点、近全长防护） |
| plasmid_replace | 已迁移 |
| plasmid_insert | 已迁移 |
| point_mutation | 已迁移（旋转无关目标检查） |
| overlap_assembly | 已迁移（显式 interval + strand） |
| protein_fusion | 已迁移（读框/翻译/stop 策略强制校验） |
| integration_donor | 已迁移（臂与座位匹配、供体污染检查） |
| gateway_recombination | 已迁移（复用严格 att 对算法，BP/LR） |
| restriction_ligation | 已迁移（experimental；单酶复用共享末端模型，双酶确定性黏端模型） |
| hierarchical_assembly | 已迁移（逐级独立组装与验证） |
| crispr_editing | 已迁移（experimental；registry 扫描 + HDR 供体模型，脱靶未评估即未评估） |

`TASK_KIND_NOT_IMPLEMENTED` 不再对任何注册 kind 返回；未注册 kind 返回 `TASK_KIND_NOT_REGISTERED`，无通用兜底。

## 已知剩余工作（v0.9.1 后续切片）

- 旧 exploration Agent 的 `_file_role_candidates` 名称启发式与 `_intent_for_plan` 全长 fallback 在兼容层中标注 deprecated，随各 kind 迁移后删除。
- `experimental` 方法的 preview 出口与报告 verdict 词汇统一。
- 审计评分 N/A 维度和固定 verdict 实施到报告工具。
