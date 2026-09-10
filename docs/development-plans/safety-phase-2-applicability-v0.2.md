# Phase 2：Evidence Applicability & Trace Usability

- 计划编号：`safety-phase-2-applicability`
- 模块目标版本：`Evidence Trace v0.2`
- 文档修订：`r3`，2026-09-10
- 状态：**工程实现及本阶段验收完成**
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

## 10. 实际实现、验证与交接

开发基线：先 fetch 并将 `codex/real-workflow-readiness-20260907` 从 `41ad883` 快进到 `ee3588f`，再读取本计划和 design.md 开始开发。`main` 始终保持 `0236384d3409c4610248fe0978d2b71b6424fe55`。本阶段没有修改 `core/`、planner、Handler 或三个原有设计入口的执行参数/验证/交付逻辑。

### 实际实现

- `chain.py`：按运行冻结的 Decision/Claim/证据关系生成局部主链，按 Decision 汇总复核事项，未关联选择按实际输入对象单列。Validation/Artifact 仍只作运行级关联，不把视觉箭头变成 Claim 的证明。
- `render.py`、`view.js`、`view.css`：固定代码生成离线页面。默认五段主干、四组折叠旁支、每组两条预览、Focus Mode、Detail、Decision Review Queue 和 Advanced Graph；支持键盘与窄屏。源码模板固定，宿主只提交数据。
- `coverage.py`、`runtime.py`：观察真实已接受的 Task/Pipeline 输入及 Recipe 实际参数和默认值，写入 `design_choice_observed`。与 Decision.targets 的字段、值和作用域匹配，保留 explained / needs review / unexplained design choice；不生成 Decision 或 rationale。旧日志可从保存的提交输入派生观察，但不据此认定已经执行成功。
- `applicability.py`：比较 Statement.context 与 Claim.context，保存原始上下文、逐维结果、理由、required_dimensions、评估者和算法版本。默认八维；有限简称、温度单位/范围与集合重合规范化。来源核验和声明 applicability 均保留，不由计算结果覆盖。
- `trace_design.py coverage --design-json ...`：无执行、无日志写入的预检查；即使没有任何 Decision，也能报告缺口。`SKILL.md` 和使用说明已更新记录协议。
- `specs/safety-module.md` 同步 Phase 2 产品决定和比较策略；`specs/core-skill.md` 同步宿主记录/预检查行为与旁路边界。

### 实际测试与案例

证据位于本机 `output/evidence-trace-phase2/`，生成物不提交为源码；可用现有示例脚本、测试和输入重现。

| 检查 | 结果 | 证据 / 复现 |
|---|---|---|
| 最终相关回归 | **91 项通过，0 失败、0 跳过**；包含 Phase 1/2 Trace、Pipeline、ConstructionTask、final 修复、Recipe、README 命令测试 | `final-related-regression.log`；本轮未重跑全仓全部测试 |
| 新 Phase 2 单测 | 八维比较、温度/集合、缺失和别名、direct/partial/extrapolated/unknown、强弱关联、开放 decision_kind、空 trace 预检查、旧日志、多关系及旁路故障；已包含在上述 91 项中，不累加 | `tests/test_evidence_trace_phase2.py` |
| 真实 Recipe 与多步 PCR Pipeline | 复用完整 pBP-eGFP 两轮突变及 PCR 制备；开关两组 .gb/.dna/FASTA 字节相同，双突变符合独立预期 | `real-case/demo-summary.json`；`scripts/demo_evidence_trace.py --template tests/data/pBP-eGFP.gb --out-dir <new-dir>` |
| ConstructionTask 独立入口 | 明确 E. coli 宿主，正式三格式 A/B 字节一致；观察到 11 个已识别字段选择，原稀疏 Decision.targets 未可靠覆盖它们，显示缺口 | `construction-ab.json`、`construction-task.json` |
| 跨宿主声明用途案例 | 在运行前声明将 E. coli 来源作为未来酵母克隆供体候选，报告 extrapolated；当前只是原骨架上的 Y66H 制备，不声称已实现酵母表达。三格式与无 Trace 原任务仍一致 | `cross-context-choices.json`、`cross-context-result.json`、`cross-context/evidence-trace/index.html` |
| 20 条条件化关系呈现 | 默认折叠、两条预览、全部展开后关系未丢失，队列按一个 Decision 聚合 | `ui-stress/`；明确标为合成 UI 测试数据，不冒充 20 篇论文或实验 |
| 实际浏览器 | 主干、Focus、条件详情、漏记选择详情、产物反查、Advanced Graph、折叠/展开、键盘与手机宽度检查通过 | `browser-check.json`、`desktop.png`、`mobile.png` |
| 故障不干预主线 | Chain、Coverage、Applicability 故障时 normal 模式仍产生与无 Trace 相同的正式 DNA；原 Core 失败与 strict 行为仍由已有相关回归验证 | Phase 1/2 Trace 回归，包含在 91 项中 |

Source 核验凭据沿用 Phase 1 记录的历史检查，不声称本轮重新联网验证了所有文献。真实 DNA 任务与合成上下文/UI 压力样例分开统计。浏览器检查证明交互可运行，不代替研究者复核效率或生物安全收益研究。

### 尚未解决的限制

- Coverage 只观察当前识别的结构化输入字段及 Recipe 已解析参数，不覆盖所有内部启发式选择、自由文本意图或所有外部原子调用。弱关联保留复核，不做语义模型猜测；explained 只表示明确关联和已有理由，不证明理由正确。
- Context 比较基于明确声明，不自动读懂论文或补齐未报告条件。有限别名不是完整 taxonomy/strain resolver；没有证明所有匹配维度足以支持真实生物学外推。
- required_dimensions 可显式限定比较范围；direct 只在该范围成立，不能扩大为 Claim 正确或设计安全。
- 沿用单写入者、已接入入口范围、搬迁后原产物路径可能需手动定位、来源核验凭据依赖外部/人工这些 Phase 1 限制。没有新增防篡改认证。
- 未做独立用户效率研究、全仓全部回归、安装包发布或宏观生物安全评估；本阶段没有承诺这些结果。

### 前序承接与后续交接

| 前序事项 | 本阶段处理 | 后续去向 |
|---|---|---|
| Phase 1 UI/Capture 反馈 | 已转化并实现主链、聚焦、Decision 队列和实际输入覆盖 | 后续按真实使用反馈迭代，不能用浏览器通过代替效率验证 |
| Evidence Applicability | 已实现有范围、可解释的结构化比较 | 更广别名、自由文本/论文提取须有新需求与独立评估 |
| 来源核验 | 继续记录凭据，不另造文献爬取/真伪裁定 | 保留外部验证边界 |
| 单写入者、入口范围、产物路径 | 明确保留，未隐去 | 按实际使用问题另行安排 |
| Change Impact | 本轮未实施，不自动标记未来修订失效 | Phase 3 单独计划 |
| Assurance Case / Conclusion Boundary / Macro Framework | 本轮未实施 | Phase 4 至 Phase 6，保留 safety spec 路线图 |

本阶段在这里收束。后续不得把 context match、Source verified、Claim 与 Decision 合并为一个总绿灯，也不得把派生分析接入 DNA 的准入规则。
