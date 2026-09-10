# Phase 1：Evidence Trace v0.1 开发计划

- 计划编号：`safety-phase-1-trace`
- 模块目标版本：`Evidence Trace v0.1`；主 skill 基线：`v1.0.0`，不表示主产品已升级。
- 文档修订：`r3`，2026-09-10，完成记录：旁路实现、真实任务、回归和浏览器验证；用户试用反馈待确认。
- 状态：工程验收完成，试用反馈待确认；本计划仅执行 Phase 1，下面第 5 节是阶段内部步骤。
- 前序计划：无已执行的 Trace 阶段计划；本文迁自原日期命名文档，内容连续承接。
- 后续计划：尚未创建；Phase 2 至 Phase 6 仅保留在 safety spec 路线图。
- 导航：[开发索引](README.md)。执行前同时读取相关 spec 与本文，不能只看本计划。

依据：用户提供的《AI 生物设计证据链与安全模块开发规划》。产品范围见 [safety-module.md](../../specs/safety-module.md)，主功能约束见 [core-skill.md](../../specs/core-skill.md)。下文标为“建议”的实现可按实际代码调整，不等同于用户锁定的 API。

## 给项目负责人的说明

第一版让研究者点开最终构建，查到对应要求、AI 的关键选择、简要理由、证据来源和真实程序检查。保留 **LLM 理解、创造、比较和决策；程序计算、验证和记录** 的分工。

主线保持 `LLM → ConstructionTask → plan → execute → validate → finalize`。Trace 是只读旁路，不能改变序列、参数、planner、Handler、验证规则或最终 DNA/交付文件，只写自己的事件和派生视图。默认 normal 模式下，即使 Trace 初始化失败，DNA 主任务也继续并报告 `TRACE_INCOMPLETE`。

总方向是 **Trace → Challenge → Bound**，本轮只做 Trace。适用性分析、变更影响、安全论证和生态框架保留在路线图。不重新设计 DNA 引擎，不做风险评分，不把日志完整当成安全证明。

## 1. 范围与现有接入点

交付分层科研决策记录、追加式事件日志、Core 外部接入、三个主要视图和一个高级图视图，以及正常 skill 工作流的实际演示。只记录影响生物学结果的来源、元件、边界、方向、终止密码子、突变、排列和策略选择；mkdir、读取 JSON 等可留在技术日志，不进入主证据链。

| 已核对位置 | 已有能力 | 计划接法 |
|---|---|---|
| `core/__init__.py`、`core/runtime_*.py` | task → plan → execute → validate → finalize，哈希与结果 | 应用层包装调用，保存真实返回值及锚点，不重写核心流程 |
| `scripts/run_construction_task.py` | session、澄清、结构化失败和交付 | 接入同一记录器，保留原澄清、失败语义 |
| `agent/pipeline_agent.py`、`scripts/run_pipeline.py` | Core 调用、task/plan 文件、制备记录、源引物图和交付 | 接入时保留制备文件生成顺序，不能漏源图或提前 finalize |
| `scripts/run_recipe.py` | RecipeResult、自检、goal_check、candidate 与 promotion | 增加薄适配，不强行转换为 ConstructionTask |
| `scripts/provenance.py`、`core/evidence_chain.py` | 来源、组件证据、文件绑定 | 复用真实记录；旧 `verified` 不无条件等同于文献已核验 |
| `scripts/operation_consent.py` | 操作确认记录 | 引用已有决定，不重复询问或新建审批机制 |

建议包名 `evidence_trace/`，避免用户示例 `trace/` 遮蔽已存在的 Python 标准库 `trace.py`。先按职责设置 `models.py`、`recorder.py`、`runtime.py`、`render.py`；落盘和图派生暂留 recorder，确有复杂度再拆 store/graph。文件数量不是验收目标。

建议增加小型 `scripts/trace_design.py`，供宿主跨多次调用追加要求、决策、证据并渲染；已有执行入口接收可选 trace 上下文。不新建 planner、数据库服务、通用插件系统或每个 Handler 的埋点。

## 2. 最小数据契约

建议事件公共字段：`schema_version`、`event_id`、`trace_id`、`run_id`（执行前可空）、`sequence`、`timestamp`、`actor`、`event_type`、`payload`。标识只用于关联与顺序，不引入分布式事件系统。

| 核心节点 | 信息与关系 |
|---|---|
| Requirement | `id`、用户要求原文或可定位摘录、来源；LLM 解释与用户原话分开 |
| Source | `id`、source_type、标题/说明、DOI/PMID/URL 或本地定位、来源核验状态及核验凭据 |
| Evidence Statement | `id`、`source_id`、来源实际报告的内容、章节/图表等定位、原研究宿主/条件/限制、摘录或归纳者；不混入当前任务的外推 |
| Claim | `id`、当前任务中提出的判断、宿主/条件/用途、声明者；关联证据陈述及采用它的 Decision，不自动判真 |
| Decision | `id`、决定、rationale、`responds_to`、`claim_ids`、相关 source/step/parameter；可带 `decision_kind`、模型自述 confidence |
| Validation | 程序检查名称、原始结果、工具/版本、运行和被检查对象；保留 PASS/FAIL、UNKNOWN、跳过等原始含义 |
| Artifact | 文件相对位置、角色、SHA-256、运行、关联 Decision 和 Validation；包含最终文件及实际制备中间体 |

这取代旧版五节点约束，不将 Source、Evidence Statement、Claim 压成单个 Evidence 字段。核心关系：

```text
Source → Evidence Statement → Claim → Decision ← Requirement
                                         ↓
                          实际运行锚点 → Validation / Artifact
```

例如：论文 A → “Promoter X 在 Sc、30°C 下表达较强” → “它在当前任务宿主中预计可工作” → “选择 X”。示例只说明结构，不冒充真实论文证据。来源核实、陈述归纳和任务外推分别可查看；资料缺失允许保留空缺，不能为了凑链编造 Statement 或 Claim。

Phase 1 的 Claim 只是保存“当前任务想判断什么”，不做安全判断、论证求解或证据充分性评估。Phase 4 再围绕这些 Claim 加入 Assumption、Defeater、Mitigation 和完整 Assurance Case。

`decision_kind` 只供 UI、检索和统计，例如 `component_selection`、`boundary_selection`、`method_selection`、`other`。接受自定义或缺省类别，未知类别仍保存并展示，不得用封闭枚举阻断 AI 的决定或 DNA 主任务。

证据来源允许论文、数据库、官方协议、用户材料、实验、程序结果和模型推断。rationale 是对外简短说明，不是隐藏 chain-of-thought。模型推断明确标记，不能冒充外部来源或程序 Validation。

Task、Plan、Execution 用事件 payload 和运行锚点承载。事件包含要求、来源、证据陈述、Claim、决定及关系的创建/修订，计划、执行、验证、产物与失败/结束记录。事件类型服务记录，不是可执行设计规则。

### 证据关系、核验与适用性

- Evidence Statement → Claim 链接建议保存 `statement_id`、`claim_id`、`relation`、`aspect`、`strength`、`applicability`、`conditions`、`limitations`、声明者及说明。关系标签以 `support / oppose / constrain / contextualize` 为基础，不用单个标签代替具体内容；未知关系保留未知和说明。
- 同一 Statement/Claim 对可有多条不同侧面的链接，不按两个端点去重。例如同一来源强烈支持“可表达”，部分支持“表达量合适”，限制“培养条件不同”，同时记录“未覆盖与其他启动子的比较”。未覆盖是缺口，不强行归为反对或支持。
- strength 可以保存声明的定性强弱及解释，缺省为未知；第一版不计算综合分数。conditions/limitations 允许多个具体条件与文本，不提前造条件求解语言。多条冲突关系并存，不能合并成一条“总体支持”。
- `verification_status` 仅用 `unverified` / `verified`。verified 需要来源核验记录：核验者、方法、时间、来源定位和核验范围。只有 DOI 字符串或模型自报 verified 不算外部核验。
- 第一版允许导入人工或外部工具核验凭据，不强制自动文献检索服务。无法核验则保留 unverified，不伪造成功。
- 来源身份核验与“陈述提取准确”“Claim 成立”“决定合理”分开。`direct / partial / extrapolated / unknown` 是独立的适用性声明，允许人工填写，保留声明者及说明；自动判断属于 Phase 2。
- 旧 provenance 的 partial、conflicting、stale 等详情须保留，不能压成 verified 后丢失限制。模型推断不作为外部已核验来源。
- Validation 仅由适配器从真实程序返回值产生。普通决策/证据录入接口不接受模型手写 Validation；这不构成抵御本机任意写权限的安全隔离。

### 决策与实际产物的关联

执行前将本次采用的 Decision 集合绑定到输入快照及 run_id。ConstructionTask 使用 task revision 和已有 task/plan/execution/validation 哈希；Recipe 记录实际参数、来源和结果文件，缺少的 Task/Plan 阶段显示不适用，不补造。

Decision 可指向 source_id、step_id、参数字段或已有区间。只有任务级引用时显示“关联本次构建”；有实际映射证据才显示“影响此序列区间”。哈希证明绑定版本，不证明 rationale 真实、因果关系或生物学正确。

修订追加事件并引用旧版本；执行时固定采用版本。重试使用新 run_id，保留旧运行。事后补录标明时间和性质，不伪装为当时决定。决策未记录时显示缺口，不从最终产物倒推一段理由补齐。首版不做自动变更影响传播。

## 3. 存储与执行

每次执行使用独立输出目录，建议：

```text
<run-output>/
  candidate/ 或 intermediate/、authoritative/、既有制备文件
  evidence-trace/
    events.jsonl
    graph.json
    TRACE-MANIFEST.json
    index.html
```

`events.jsonl` 是唯一事件事实源，追加写入、显式 UTF-8；graph、manifest、HTML 和 timeline 均为派生视图。manifest 保存 trace/run 标识、生成器版本、记录范围、结束状态、派生文件及现有产物锚点，不另造生物验证签章或哈希认证体系。

建议首版单写入者、顺序追加。修订不覆盖事件；截断或悬空引用明确标记记录不完整，不静默丢弃后宣称完整。保留必要摘要、已有结果定位和关系，不默认复制全部 DNA、凭据或整段聊天。

建议的 `traced_run` 负责真实调用和结束处理，不为了记录多执行一次反应：

```text
尝试打开旁路记录 → 关联要求/决策/依据 → 调用原运行路径
→ 记录实际阶段结果、失败或正式交付
→ 关联磁盘产物 → 生成派生视图 → 返回原结果与 trace 状态
```

ConstructionTask 复用现有五步，Recipe 走自身适配。Trace 观察输入/返回值的快照，不就地修改传给 Core 的对象，也不从 Claim/Decision 反向生成或覆盖 Core 参数。包装后保留源图、制备中间体、当前失败结果和 confirmation 条件。不能在 finally 中无条件 finalize，也不能捕获 Core 失败后当 Trace 故障忽略。

`trace_status` 与原生物学状态分开。UI 使用 **“记录完整性：完整” / “Trace integrity: complete”**，只说明约定范围内记录和关联齐全，不表示安全、证据充分或捕获全部内部思考。缺 rationale、来源未核验、程序未通过分别显示，不混成一个总绿灯。

| 模式 | Trace 初始化、追加、派生或渲染失败后的行为 |
|---|---|
| normal，默认 | DNA 主任务继续，保留其原状态与交付结果，通过返回值/控制台明确报告 `TRACE_INCOMPLETE`；能写入的记录保留，不能只依赖已失败的日志报告自身故障 |
| strict，显式选择 | 可在当前 Core 调用返回后的边界停止后续步骤；初始化失败可在 Core 启动前停止。明确标识 Trace 故障，不冒充生物验证失败 |

strict 也不能中断 Core 内部计算、改规则、回滚或删除已产生文件。finalize 已成功而后续渲染失败时保留正式产物，分别报告 DNA 已交付与 Trace 不完整。此处取代旧版“日志初始化失败就默认中止”的建议；Trace 单独故障不改变 normal 模式的原有 DNA 成败语义。

## 4. 用户界面

建议单页离线 HTML，原生交互，无服务器、前端构建链或图库依赖。显示内容来自事件，转义用户文本；不额外调用模型替记录编写总结。

| 视图 | v0.1 行为 |
|---|---|
| Design Timeline | 按关键决定和实际运行阶段排列，使用“来源未核验”“程序检查通过”等具体标签 |
| Decision Detail | 点击展开右侧详情：决定、rationale、要求、Claim、来源与证据陈述、各侧面的强弱/条件/限制/适用性、运行和受影响文件 |
| Review Queue | 聚合显式缺口：缺 rationale/证据、来源未核验、已声明矛盾或适用性限制、程序失败/未知；点击跳转 |
| Evidence Graph | 高级/展示视图，默认可折叠 Source、Statement、Claim，展开查看多条条件化关系；与 timeline 使用同一数据，不做复杂编辑器 |

不采用示例里的笼统“证据充分 ✓”作为自动标签。来源已核验、程序 PASS 和证据充分不是一回事。Review Queue 只呈现已记录信息及结构缺口，不提前实现 Challenge。

从 Artifact 可反向定位 Decision，从运行结果可打开对应页面与文件。不为“点开产物”改写 `.dna` 格式或嵌入全部日志。默认视图也不要求生物研究者直接阅读 JSON。

## 5. 实施顺序

以下是同一次 v0.1 开发的顺序，不是每步重新申请批准。

1. **数据与记录。** 实现 Source/Statement/Claim 分层、关键 Decision、条件化多重关系和真实 Validation/Artifact 关联；保留事件追加、修订和来源核验记录。小案例可重建，无效关联不能伪装成完整链。
2. **真实入口。** 先 ConstructionTask，再 Pipeline 完整制备与交付，最后 Recipe 薄适配。提供宿主录入入口，覆盖成功、澄清、失败和重试；优先验证 normal 模式旁路故障不阻断，不散改 Handler。
3. **四个视图。** 默认 timeline，Decision 详情、queue 跳转及 graph 可用。断网打开，中文和引文正常，用户无需查原始 JSON。
4. **真实演示与发布检查。** 从资料完整的 [论文参照任务](../REAL-WORLD-SKILL-PAPER-EXAM-20260906.md) 选择首条演示，必须包含用户要求、至少两个 AI 关键决定、至少一个真实论文/数据库来源、至少一个程序 Validation、中途一次实际设计修订和最后正式产物。保留修订前后记录，再补另一入口的回归，使 Recipe 和 Pipeline/ConstructionTask 都覆盖。运行相关回归、适用全量检查与解压包入口，更新 `SKILL.md` 和必要使用说明。

## 6. 验收标准

- 必做 Trace 开关 A/B 回归：固定同一用户目标、输入文件、Core 参数、工具版本和设计修订，分别开/关 Trace，不用两次随机 LLM 生成的不同设计比较。DNA 序列、拓扑、注释、完整引物、制备、验证语义及 authoritative artifact 一致；逐项比较正式文件，可复现文件检查字节/哈希。只有格式本身已有的生成时间等易变元数据可单列解释，不能忽略序列、注释或验证差异。
- 注入 Trace 初始化、追加及渲染失败，normal 模式仍完成原本可完成的 DNA 任务并显示 `TRACE_INCOMPLETE`；strict 模式显式停止且保留既有文件。另确认 Core 自身失败仍正常报失败，不被旁路异常处理吞掉。
- 任一所选最终构建能找到要求、已记录关键决定、证据和真实 Validation；文件锚点与磁盘一致，不读取界面绿灯代替复核。
- 未核验引用始终显示未核验，已核验 Source 不自动验证 Statement/Claim/Decision；同一来源不同侧面的 support/oppose/constrain/contextualize、strength、conditions、limitations 和未覆盖项均能保存、重建、查看。自定义 decision_kind 不阻断记录或主任务。
- 改一次边界或来源再运行，新产物关联新决策/运行，旧链保留；缺决策、失败运行和记录故障可见。
- 删除 graph/HTML 后重建，除生成时间等展示元数据外，内容及关联相同；源事件不改变。
- 实际用户通过页面回答“为何这样设计、依据何在、程序查了什么、还有什么未知”。记录问题和额外操作，不虚构复核效率提升。

回归优先复用现有 Recipe、Pipeline、ConstructionTask、制备交付和打包测试，增加必要的 trace 数据/界面检查。不新建大规模基准矩阵，不把拒绝输入计为完成设计，不以新增湿实验扩大本阶段。

## 7. 保留的实现选择

包布局、入口参数和离线 HTML 是当前建议，不冻结 API。实现时在现有接入点确定调用方式，不再另造规格体系。

建议保留旧入口无 trace 的兼容运行；是否默认启用记录仍可按首条真实任务确定，但启用后的故障策略已经确定为 normal，strict 必须显式选择。未接入旧 CLI 和宿主外部行动列为覆盖范围外，不宣称全局监控。

来源核验工具、首条演示任务和视图细节可在开发中选择。自动适用性审查、影响传播算法和框架 providers 不提前选型。

## 8. 完成记录与交接

已实现 `evidence_trace/`、录入/重建 CLI、三个设计入口的旁路观察，以及 Timeline、Decision Detail、Review Queue 和关系图。Core/Handler 无改动，旧结果与交付文件不被 Trace 修改。模块版本 `0.1.0`；主 skill 的历史 v1.0.0 发布不被覆盖。

工程证据保存在本机 `output/evidence-trace-phase1/`，生成物不随源码提交；可通过使用说明和脚本复现：

| 验证 | 实际结果 | 证据 |
|---|---|---|
| 全量回归，启用真实 Primer3 | 750 项，743 通过、7 跳过、0 失败 | `full-regression.log` |
| 收尾 Trace 相关回归 | 15 项通过，包含旧证据关系、历史文件、normal/strict 故障 | `trace-regression.log`，`tests/test_evidence_trace.py` |
| 真实 Recipe 与 PCR Pipeline | 开关两组 .gb/.dna/FASTA 逐字节一致；双突变产物与独立预期一致 | `demo-001/demo-summary.json` |
| ConstructionTask 独立入口 | 三格式 A/B 一致；缺宿主先走原有澄清 | `construction-ab.json`、`construction-on/result.json` |
| 浏览器交互与布局 | 修订详情、复核队列、产物反查、图视图、旧运行过滤；手机无横向溢出 | `browser-check.json`、`desktop.png`、`mobile.png` |
| 独立包 | 解压后在仓库外运行同一演示；最终同步包结果见 `final-package-summary.json` | `packaged-demo-stdout.json`、最终包验证文件 |

两轮测试数量不相加。首次全量未开启两项真实 Primer3 测试，发布 gate 拒绝；随后开启真实后端重跑才得到上述全量结果。收尾修复阻止失败结果中的历史文件被误报为本次产物，15 项相关回归覆盖最终改动。

首个演示包含完整 pBP-eGFP、两个关键决定、真实来源核验记录、实际 inverse PCR、追加 Y145F 的决策修订与正式产物。证据只支撑设计记录及软件行为，不声称荧光或安全性已实测。

已请求用户试用反馈，尚未收到。自动浏览器检查不能替代用户使用评价；这一验收项保留待确认，不虚报为全部验收完成。

交接事项：

| 事项 | 当前处理 | 后续去向 |
|---|---|---|
| 默认记录方式 | skill 新设计默认记录，用户可关闭；直接 CLI 保持可选，normal 默认 | 已同步 spec 和使用说明 |
| 来源核验与演示 | 接收带范围的外部/人工核验记录；Q3 衍生 GFP 两轮改造及 PCR Pipeline | 真实身份/引用检查记录日期为 2026-09-10，后续运行不会自动重新核验 |
| 用户试用 | 已请求反馈，尚未完成实际用户验收 | 收到反馈后处理具体问题，再更新本计划状态 |
| 已知使用限制 | 单写入者；只记录已提交决定/接入入口；搬迁产物后原路径可能需手动定位；不是防篡改认证 | 后续按实际需求处理，不能在宣传中隐去 |
| 自动 Evidence Applicability | 明确延期，不属于本阶段缺陷 | safety spec Phase 2 |
| 自动 Change Impact | 明确延期，手工修订留痕仍属于 Phase 1 | safety spec Phase 3 |
| Assurance Case、结论边界、宏观框架 | 明确延期；轻量 Claim 仍属于 Phase 1 | safety spec Phase 4 至 Phase 6 |

创建下一阶段计划前，逐项核对本节未完成项、使用限制与 spec 的开放问题，写明承接、延期或取消及理由，不能默认清空。已完成的约束与回归也应保留；引用其证据，不把历史结果冒充新版本验证。

后续阶段的完整范围只维护在 [safety spec 路线图](../../specs/safety-module.md#later-direction-not-phase-1-requirements)。本计划验收结束后停止，不自动实施下一阶段。
