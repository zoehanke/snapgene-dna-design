# Phase 3：Living Evidence Document 与 Change Impact

- 模块目标：Evidence Trace v0.3；文档 r2，2026-09-10；状态：实现及本地工程验收完成。
- 前序：[Phase 2 完成记录](safety-phase-2-applicability-v0.2.md#10-实际实现验证与交接)。
- 长期约束：[safety spec](../../../specs/safety-module.md)、[core spec](../../../specs/core-skill.md)；界面：[design.md](../../trace-report/design.md)。
- 分支：`codex/real-workflow-readiness-20260907`，不修改 main；实现、验证后 commit/push 并核对同一提交 CI。

后续交接（2026-09-11）：用户反馈页面不适合人类阅读，采集与 UI 改进转入 [Phase 3 补救计划](safety-phase-3-readability-v0.3.1.md)。本文保留 v0.3 工程记录；原单 Decision 导图不再作为下一版布局目标，原工程验收不等于阅读验收。

## 目标与边界

Evidence Trace 是 **Living Evidence Document**，不是 Dashboard。Mind Map 是一级阅读模式。Change Impact 只指出需要重新检查的范围，不自动改科学结论、Core 参数、Validation 或产物，不执行建议的重算。

不做 Safety Score、safe/unsafe、Assurance Case 或宏观框架。沿用 Phase 2 的正常模式故障隔离、来源/上下文/Claim 分离和已识别字段覆盖限制。

## Change 与影响契约

- Change 是追加事件：唯一 `id`、`from_revision`、`to_revision`、`changed_field`、`old_value`、`new_value`、`recorded_at`，并记录变更来源、对象/运行引用和记录字段新增/删除状态；观察覆盖缺失单列为 UNKNOWN。
- 自动捕获明确记录的 context/targets/科学声明修订，以及同一 trace 内同一 Task ID/kind 或同一 Recipe 名称的相邻运行的已观察输入变化。支持显式指定两个已记录运行进行比较；不把文件路径/缺失字段猜成新的科学事实。
- 不重新计算新哈希；复用现有记录版本、运行 ID 和 Core 已提供的内容锚点。旧日志没有足够输入时保留限制，不补写历史 Change。
- 影响判断：明确依赖 → `AFFECTED`；可能依赖 → `NEEDS REVIEW`；有明确、完整且可比较的依赖范围证明无关 → `UNAFFECTED`；信息不足 → `UNKNOWN`。没有边不代表无关。
- 处理建议独立保存：`REASSESS` 为 Claim/Decision 重新判断；`RECHECK` 为 Evidence/Applicability 重查；`RERUN` 为 Validation 重跑建议；`STALE` 只表示旧上下文记录；`NEEDS REVIEW` 为影响不能可靠自动判断。它们不是安全等级。
- 明确字段绑定和实质依赖边可传播影响；旧 run-level Validation/Artifact 关联只算可能依赖。依赖字段可以显式声明，只有标明范围完整的声明才支持 UNAFFECTED，且需显示声明来源。
- Applicability 的影响挂在原 statement/claim/link 的评估引用上，不修改原文献内容或 Source verified。

## HTML 实现

一个固定 renderer、一个状态对象、三种投影：`Document / Mind Map / Split`。共享运行、选中 Decision/节点、展开记录及局部阅读位置。切换后仍定位同一 Decision；不使用宿主动态页面生成或新前端依赖。

- Document：Decision 分章，Why → Evidence → Applicability → Validation → Change Impact → Output。默认短正文与关键结果；详情用折叠或 drawer。
- Mind Map：全页 SVG，以当前 Decision 居中；Requirement、Claim、Evidence、Validation、Artifact 处于固定方位，Change/Review 在外围。默认一层，证据先按 Supports/Limits/Conflicts/Context 分组；逐层展开和缩放，不一次铺开完整网络。
- Split：左导图右章节，节点与正文同步选中。共用组件和状态，不维护另一套证据逻辑。
- Review Queue 看待办；Changes 看版本差异；Artifact Trace 反查文件；Advanced Graph 看完整原始关系；Audit Log 看原始追加记录。辅助入口不变成并列 KPI 面板。
- 冷灰白、细线、有限语义色、系统字体，ID/版本/坐标用等宽；无大圆角卡片、渐变、毛玻璃和装饰性 KPI。支持键盘、窄屏、缩放与 reduced motion。

## 实施与验收

1. 先更新本计划、design.md 和 spec；实现 Change 追加与保守依赖判断，测试四种判断与五种建议的独立语义。
2. 实现共用状态和固定 renderer；完成三模式连续定位、证据展开、影响追溯及辅助阅读入口。
3. 真实任务中途修订上下文/来源或边界，最终产物能查到具体 Change 与旧记录；无依赖证据时显示 UNKNOWN。
4. Trace on/off 继续比较序列、拓扑、注释、引物、制备、Validation 与正式三格式；normal 下影响计算/呈现失败不能改变 DNA 结果。
5. 旧 Phase 1/2 事件可重建，无迁移覆盖；新增修订、失败和补录保留历史。用多证据案例测试展开及模式连续性。
6. 浏览器验证 Document/Mind Map/Split 同一选择和展开状态、键盘/窄屏、Changes 到 Decision/证据/产物的可达性。5/15/30 秒是用户任务目标；没有用户计时不能声称达到。

## 前序承接与完成记录

- 承接：Phase 2 UI 阅读负担与只展示信息的限制，改为科研证据文档和一级导图；实现此前延期的 Change Impact。
- 保留限制：结构化字段范围、外部来源核验、单写入者、原产物路径；本轮不做语义论文理解、多人协作或自动撤销科学结论。
- 延期：Assurance Case、Conclusion Boundary、宏观框架至 Phase 4 以后。
- 实际实现、测试、CI 与剩余限制在完成时填写；本轮不自动进入 Phase 4。

## 实际实现与验证

- `impact.py`、`recorder.py`：Change 追加对象、记录修订、同身份运行对照、显式 baseline 比较；复用已有产物锚点记录实际 sequence/topology 变化。影响判断与动作分开，缺失观察保留 UNKNOWN，旧结果不被覆盖。
- `runtime.py`：只增加旁路已知依赖描述和对照调用；原 Core/planner/Handler、执行参数、Validation 返回值和正式文件逻辑未改。
- `render.py`、`view.js`、`view.css`：一份固定模板与共享状态，Document / Mind Map / Split、章节定位、证据及 aspect 连续选择、可平移缩放的 SVG 导图、Changes drawer、Artifact Trace 和原始 Audit Log。
- 已修正浏览器发现的选择覆盖问题：状态属性与按钮动作属性分离；从辅助视图选旧记录可定位到其运行。导图英文标签保持词组、窄 Split 来源节点不被裁掉，同一 Statement 多个 aspect 不被混为一个选择。
- 使用说明和两个 spec 已同步。Phase 2 设计规范保留为 `design-phase-2.md`，不再作为当前页面布局要求。

| 验证 | 结果 | 本机证据 |
|---|---|---|
| 相关回归 | 117 项通过；随后新增“缺失观察不能证明变化”的用例与 Phase 3 全部 11 项一起通过，数量不相加 | `output/evidence-trace-phase3/final-regression.log`；Phase 3 单测 |
| 真实完整模板 PCR 修订 | 6:720 → 6:723，修订前后各自 Trace on/off 的 .gb/.dna/FASTA 和引物表一致；6 个正式 Change，包含实际产物 sequence 变化；旧验证给出 RERUN，UNKNOWN 保留 | `demo-final/demo-summary.json` |
| 旁路故障 | impact 计算失败仍交付与无 Trace 一致的三格式；原 PASS 不被改写 | `tests/test_evidence_trace_phase3.py` |
| 浏览器 | 三模式选择/展开共享、Split 定位、Change 前后值、旧记录、Artifact 回查、Audit、缩放、键盘和窄屏通过 | `browser-check.json`；三模式截图 |
| 20 条关系与旧日志 | 默认仅 8 个角色节点，展开后不超过 13 个节点；所选 aspect 跨模式保留；两个独立进程重建 HTML 字节一致，原事件不变 | `stress-check.json`、`legacy-stress/` |
| CI | commit/push 后核对同一提交的 GitHub 六矩阵；结果以提交关联的 [PR checks](https://github.com/zoehanke/snapgene-dna-design/pull/1/checks) 为准 | 最终答复记录提交和运行链接 |

上述生成物保存在 `output/evidence-trace-phase3/`，不作为源码提交。真实案例通过 `scripts/demo_evidence_trace_phase3.py --template tests/data/pBP-eGFP.gb --out-dir <new-dir>` 复现。早期 demo-001/002 和浏览器失败记录保留；没有重写旧事件以掩盖缺口。

### 限制与交接

- 5/15/30 秒仍是待真实用户计时的目标，浏览器通过不能冒充用户理解效率。
- 依赖是明确结构/字段描述，运行级关联仅为可能依赖；完整范围声明是记录者提供的限定依据，不是普遍生物学独立性证明。未知不自动变成无关。
- 自动运行对照只适用于同 Task ID/kind 或同 Recipe；不同方法/任务的对照需显式选择 baseline。已有观察字段覆盖限制、外部来源核验、单写入者和原文件位置限制仍在。
- 新修订不自动视为已处理旧影响。RERUN 不执行任何程序，不改原 Validation，不创建安全等级。
- 沿用 Phase 2 的 context 比较。Assurance Case、Conclusion Boundary、宏观框架继续延期至 Phase 4 以后，不在本轮展开。
