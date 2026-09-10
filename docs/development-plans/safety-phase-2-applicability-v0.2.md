# Phase 2：Evidence Applicability & Trace Usability

- 计划编号：`safety-phase-2-applicability`
- 模块目标版本：`Evidence Trace v0.2`
- 文档修订：`r1`，2026-09-10
- 状态：**计划完成，尚未开发**
- 前序：[Phase 1 Evidence Trace v0.1](safety-phase-1-trace-v0.1.md)（工程验收完成）
- 关联 spec：[safety-module.md](../../specs/safety-module.md)、[core-skill.md](../../specs/core-skill.md)
- UI 规范：[design.md](design.md)

## 1. 本阶段目标

Phase 1 已能记录 `Source → Evidence Statement → Claim → Decision`、真实 Validation、Artifact 与修订历史，并证明 Trace 开关不改变正式 DNA 文件。本阶段解决 3 个实际问题：

1. **Chain UX**：当前信息完整但不够像“证据链”，关系过多时难读。
2. **Decision Capture Coverage**：减少对宿主 LLM 主动上报 Decision 的依赖，主动发现“执行中发生但没有解释”的关键设计选择。
3. **Evidence Applicability**：实现 safety spec 原定 Phase 2，区分证据是否适用于当前宿主、条件和用途。

仍遵守：`Trace → Challenge → Bound`。本阶段不进入 Phase 3 Change Impact，不做 safe/unsafe、综合风险分或 Assurance Case。

## 2. 锁定边界

- Evidence Trace 继续是 **read-only sidecar**；不得修改 DNA 输入、planner、Handler、执行参数、Validation 语义或 authoritative artifact。
- `events.jsonl` 继续是事实源；新视图/评估均为可重建派生结果。
- 不记录/推断 hidden chain-of-thought。发现漏记时显示 gap，**禁止事后自动补 rationale**。
- Phase 1 历史 trace 必须兼容。
- UI 必须由确定性代码实现，宿主 LLM 不能根据 `design.md` 每次自由生成页面。

## 3. Workstream A — Decision-centered Evidence Chain

默认视图从“全局关系图”改为**主干 + 可展开旁支**：

`Requirement → Decision → Claim → Validation → Artifact`

Evidence / Applicability 作为旁支挂在 Decision/Claim 上。默认聚合 Supporting / Limiting / Opposing / Context，只预览少量证据；点击进入 Focus Mode，仅展开当前 Decision 的局部链。完整 Evidence Graph 降级为 Advanced View。

Review Queue 改为按 Decision 聚合，例如：

- `D4 选择 promoter X`：1 条证据培养条件不同；
- `D7 stop-codon policy`：实际执行但没有记录 rationale；
- `D9 assembly strategy`：1 个来源未核验。

具体视觉和交互以 [design.md](design.md) 为开发规范。

## 4. Workstream B — Decision Capture Coverage

### 4.1 Observed Design Choice

从 ConstructionTask、Pipeline、Recipe 的真实执行输入/计划中提取**已发生的关键设计事实**，例如 source、component、boundary、orientation、stop policy、mutation、method、fragment order、topology、关键参数。

建议新增事件：`design_choice_observed`。

它表示“程序看到本次执行用了这个选择”，**不是 Decision，也不是 rationale**。

### 4.2 Coverage matching

将 Observed Choice 与已有 `Decision.targets / step / parameter / source` 做匹配：

- matched → `explained`
- 有 Decision 但关联弱/模糊 → `needs review`
- 无 Decision → `unexplained design choice`

不要用封闭 decision_kind 规则限制 LLM。优先根据实际对象/字段映射；无法可靠映射时保留 unknown。

UI 优先显示：`8 observed · 6 explained · 2 need review`，不要把 Coverage 做成“安全百分数”。

### 4.3 Host capture protocol

更新宿主工作流：设计开始建立 trace context；关键 Decision 发生时立即提交；修订则追加 revision；执行前运行 coverage check；缺口可由宿主补充**当时真实存在**的 Decision，不能为凑完整率伪造解释。

## 5. Workstream C — Evidence Applicability

给 Evidence Statement 和当前 Claim 保存/派生可比较 Context。首版只处理结构明确、能解释的维度，例如：

`organism / strain / host-or-chassis / construct context / temperature / medium / assay / intended use`

逐维比较：`MATCH / DIFFERENT / PARTIAL / UNKNOWN`，再给出 `direct / partial / extrapolated / unknown` applicability，并保存理由/声明者。

必须分开：

- Source identity verification
- Evidence Statement 内容
- computed context match
- declared/assessed applicability
- Claim / Decision

自动结果不得伪装成“系统理解了全部生物学外推”。无法机械判断时显示 `Needs interpretation`。

建议新增事件/派生记录：`applicability_assessed`。若实现自动比较，保存输入 context、逐维结果、算法版本和解释；不做综合风险分。

## 6. 建议代码职责

可在现有 `evidence_trace/` 增加：

- `chain.py`：Decision-centered chain projection / focus branch
- `coverage.py`：Observed Choice + Decision coverage
- `applicability.py`：context comparison
- `render.py`：按 `design.md` 重构固定 UI

文件名可调整，但不得把这些能力塞回 DNA planner/Handler。

## 7. 实施顺序

1. **先重构 UI**：Main Chain、折叠旁支、Focus Mode、Decision Review Queue、Advanced Graph；旧 trace 可直接打开。
2. **实现 Observed Choice / Coverage**：三个入口覆盖；漏记只报 gap。
3. **更新 host capture protocol**：让关键 Decision 更稳定地在发生时入 Trace。
4. **实现 Applicability**：context 结构、逐维比较、partial/extrapolated/unknown。
5. **合并 UI**：Applicability 直接进入 Decision 的证据旁支和 Detail，不另造一套复杂页面。
6. **真实案例验收**：使用多 Decision、多 Evidence、条件不完全匹配且含一个漏记 Decision 的任务。

## 8. 验收标准

- 不看 JSON/全局 Graph，研究者能从默认页回答：做了什么决定、为什么、证据支持/限制什么、适用性如何、程序检查了什么、产物是什么、哪里没解释。
- 一个 Decision 即使关联 10–20 条 Evidence，也不会默认形成蜘蛛网；复杂关系仍可展开查看。
- 同一 Evidence Statement 对同一 Claim 的不同 aspect/strength/limitations 不被错误合并。
- 宿主漏记关键 Decision 时，系统能从实际执行发现 unexplained choice，但不生成假的 rationale。
- Applicability 的 direct/partial/extrapolated/unknown 能追到具体 context comparison / declarer；source verified 不自动变成 claim/decision verified。
- Phase 1 `events.jsonl` 向后兼容，派生视图可重建。
- Trace on/off A/B 继续保持 DNA sequence、topology、annotations、primers、preparation、Validation 语义和 authoritative artifact 一致。
- normal 模式下 Chain/Coverage/Applicability/renderer 故障不得改变 DNA 主任务结果。

## 9. 明确不做

本阶段不做：Safety Score、safe/unsafe、危险序列综合判定、自动 Change Impact、Assumption/Defeater/Mitigation、Assurance Case、Conclusion Boundary、生态预测、IUCN/WHO/NIH/NIST Framework Providers。

Phase 2 完成后再单独规划 Phase 3：**设计发生变化后，哪些 Decision / Evidence / Validation 需要重新检查。**
