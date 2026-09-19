# Evidence Trace 三层重构：开发设计

**r2 · 2026-09-19 · 目标模块 v0.3.1 · 设计已更新，业务代码尚未实施。**

[人工解释版](safety-phase-3-three-layer-review-v0.3.1.md)与本文逐章对应；[机器结果示例](safety-phase-3-process-example-v0.3.1.json)是模拟结构，不是实际运行证明。

## 1. 决定、范围与前序

r2 根据后续讨论修正 r1 的核心分工：**数据层需要 AI／人完成语义组织，程序负责事实和结构核对；完整过程与报告编排分开保存。** 不再把 nodes/relations 列表当作已经整理完成的设计过程。

| 状态 | 内容 |
|---|---|
| 已确认方向 | 三层；完整机器结果；AI 语义组织与报告编排；程序核对及固定渲染；原始事实与后来判断分开 |
| 本文工程建议 | 字段、CLI、事件类型、模块拆分及执行顺序，实施时可简化但需同步文档 |
| 当前实现 | 三个主入口、原日志与 reader 已存在；新组织包、编排提交和完整机器结果尚未实现 |

先读[索引](README.md)、[安全 spec](../../specs/safety-module.md)、[Core spec](../../specs/core-skill.md)、[Phase 3.1 计划](safety-phase-3-readability-v0.3.1.md)及[前序交接](safety-phase-3-change-impact-v0.3.md)。依据包括[真实使用审查](../EVIDENCE-TRACE-REAL-USE-AUDIT-20260915.md)、[可信度研究](../EVIDENCE-TRACE-TRUST-ARCHITECTURE-20260914.md)、[Archify 对照](../ARCHIFY-REFERENCE-REVIEW-20260919.md)。

本轮已 fetch，开发分支 `codex/real-workflow-readiness-20260907` 与远端一致。业务基线 d52165b，r1 文档 f6310e9。实施前重新核对，保护用户 Reader Demo 未提交修改，不修改 main。r2 是同一设计的修订；r1 留在 Git，不重新计算历史完成状态，不进入 Phase 4。

继续保留旁路、单一事件源、一套 Skill、全局 Off/Observed/Full 和独立 normal/strict。不改变 DNA 参数、planner、Handler、Core Validation 或正式产物，不增加模型服务、图数据库、风险评分或自动科学裁判。

## 2. 三层及其实际执行者

```text
真实工具行为、用户/AI公开提交、可取得原材料
                    ↓
              采集层：原始记录
                    ↓
       数据层：程序事实索引 → AI／人语义组织
                         → 程序核对与保存版本
                    ↓
        graph.json：完整过程＋报告编排
                    ↓
       报告层：按编排输出 HTML / Markdown
```

| 主体 | 职责 | 边界 |
|---|---|---|
| 采集程序 | 真实输入输出、文件、失败、原文位置及原始提交 | 不推断内部动机 |
| 设计 AI／用户 | 原要求、设计决定、当时公开理由、声明的依据 | 不手写程序检查和产物事实 |
| 整理 AI／研究者 | 阶段、分支、过程解释和有来源的语义关系 | 不把后来理解写成当时理由 |
| 数据核对程序 | 引用、版本、执行对应、约束、记录去向及组织状态 | 不认证自然语言科学论证 |
| 报告编排者 | 标题、摘要、重点、分组及展开安排 | 不改变完整过程及其事实 |
| 渲染程序 | 固定布局、关系显示、交互和导出 | 每次生成页面不重新调用模型 |

AI 整理与编排可以在同次宿主响应完成，但确实有 token、时间和工具成本。三层是职责，不是三个服务；Python 不内置调用模型 API，并不等于数据层不需要 AI 工作。

## 3. 数据层最终交付什么

### 3.1 完整机器结果

升级现有 graph.json，使其保存已经形成的设计过程，而非仅为画图准备的简图。

| 字段 | 内容与来源 |
|---|---|
| schema_version | `design-process-v1`，与模块版本分开 |
| snapshot | trace_id、记录截止序号、组织版本、报告版本及新旧状态，由程序填写 |
| task | 已记录的目标、约束、材料和交付要求，附原引用 |
| source_records | 按确切节点版本/事件 ID 索引的完整已采集信息，由程序装配，不让 AI 重新誊写 |
| fact_relations | 实际输入、返回、文件生成、检查对象等可计算关系及依据 |
| design_process | 有阶段、步骤、分支、解释和未决项的完整过程 |
| report_plan | 供正文、导图和导出执行的编排，引用完整过程 ID |
| coverage | 每份记录的去向、未归类项、不可取得材料及来源缺口 |
| findings | 真实设计问题与记录/来源问题分开，附对象和版本 |

完整性针对已采集的相关信息。原材料可通过引用保留；大 DNA 文件不重复塞入 JSON，内容不可取得时明确标记。未知事件也保留载荷，不因程序不理解就删除。完整保存不要求一次向模型发送全部内容。

source_records 表示 basis 范围内的原始设计记录；组织/编排事件通过 snapshot 中的确切版本引用访问，不递归嵌入自身。旧组织版本仍可从日志回查。graph.json 是派生结果，render 应从日志和指定组织版本装配，不能把手工改过的缓存当成新的原始事实。

### 3.2 design_process

| 字段 | 必要信息 |
|---|---|
| stages | id、title、purpose、step_ids、可选 branches 与 source_refs |
| steps | 按 id 索引；kind、完整 content、source_refs；可有 reason、limitations、input_refs、outcome_refs |
| relations | id、from、to、kind、meaning、source_refs，作者和来源身份随提交保留 |
| paths | 命名路径及 step_ids；注明逻辑组织、计划还是实际调用顺序 |
| unresolved | id、具体问题、相关步骤/记录和来源 |
| detail_refs | 不放入主要步骤但保留供复核的材料引用 |

step.kind 使用 requirement/choice/program_result/artifact。具体程序数值、文件角色和检查状态由原记录解析，AI 不提供替代值。每个阶段要说明所解决的子问题；没有论文、替代方案或用户否决时不强行补齐。

集合的明确形状：stages/relations/paths/unresolved/detail_refs 为数组，steps 为 ID 到对象的映射。stage.branches 若存在，包含 id、label、step_ids、source_refs；path.order_kind 取 logical_process/planned/recorded_order。recorded_order 需要可比较的原调用顺序。source_refs 只能引用原记录；step_refs、relation_refs 则引用本过程对象，命名空间不得冲突。

reason 为 `text / source_refs / origin` 对象。origin 区分 original_statement、organized_summary、later_interpretation、unknown。摘要和新解释不覆盖原说明。

### 3.3 关系分类

fact_relations 是程序从实际记录建立的关系；design_process.relations 是 AI／人提供的语义组织。二者都须能回查依据。

| 关系 | 语义范围 |
|---|---|
| input_reference / produced_by / stage_result | 程序确认的输入、生成及调用生命周期 |
| target_matches_input | 已提交目标值与真实调用参数匹配，不证明选择理由正确 |
| responds_to | 声称回应要求，不等于实际满足 |
| declared_reason_for_change | 有公开说明作为依据，不认证内部因果 |
| supports / opposes / constrains / contextualizes | 提交者对具体方面的科学判断，保留条件和来源 |
| grouped_with / part_of | 组织者提出的过程结构，不冒充运行事实 |
| revises_plan | 根据明确说明组织出的方案修订关系；原记录的程序版本修订仍另行保留 |

AI 可以引用已有 fact_relation_ids，但不能新建程序身份的 produced_by、Validation 或文件事实。阅读顺序不自动生成关系；相邻节点没有边时只能显示分组。

## 4. 采集层保留和补齐哪些路径

### 4.1 第一批入口

| 入口 | 采集位置 |
|---|---|
| run_construction_task.py | 现有 task/plan/execute/validate/finalize |
| run_pipeline.py | 原组合工作流及返回，不在每个 Handler 埋点 |
| run_recipe.py | 实际参数、制备、检查、候选和提升 |
| inspect_plasmid.py | 有 trace-dir 时包装 inspect_single_file；无 Trace 的独立检查用法保持 |
| annotate_primers.py | 两种格式的 add/remove/replace/clear，输入与 result.source/output |
| convert.py | convert_file，批量逐文件保留成功和失败 |
| export_delivery_bundle.py | build_bundle 的真实清单，保持 preview/convenience 身份 |

未接入的临时脚本、其他工具或宿主活动明确在范围外。目录中出现文件，不是该文件生成过程的证据。

### 4.2 共用程序观察

复用 TraceRun、traced_run、observe，增加文件调用 helper：

```python
def observe_files(stage, fn, *, args=(), kwargs=None,
                  input_paths=(), output_paths, artifact_role): ...
```

output_paths(result) 是确定的输出提取函数。业务函数以原参数调用一次；输入版本在写入前取得，返回后只检查明确输出。annotate 取 output，convert 取返回路径，bundle 取 bundle_dir/files/manifest。复用 file_digest，不增加哈希链。

原地编辑记录新旧文件身份；DNA 相同不等于注释相同。失败后残留文件只能记录为失败调用后的观察，不能算成功产物。原来存在且未变的文件不冒充新生成。聚合返回重复提及文件复用原记录；不同真实调用仍区分。

七入口统一 trace-dir/trace-input/trace-mode。输出根采用原解析结果的文件父目录或批量目录；只读检查有明确 Trace 时仅保存运行位置元数据。原返回、stdout、退出语义和 Core 错误保持，Trace 诊断走旁路。

### 4.3 原材料与公开提交

保留 record 和 trace-input 接收原七类记录、证据关系和后补说明。新增 observe --input：local_text 按 1 起始、两端包含的行范围读取 UTF-8/UTF-8-BOM 文件；submitted_text 保存提供者文字。后者不能自标已核实原消息。

最小字段为 kind、path/text、start_line/end_line，可选 source_uri、declared_role、declared_occurred_at。event_id、采集时间、capture_channel 由程序填写。返回的事件 ID 用于 origin_refs。支持批量，逐条返回成功或错误，不回滚已追加事实。

出处可定位、原文匹配、内容支持、作者和原发生时间是不同核查。原文/摘要分开；只有确切片段匹配才能建立 quotes_from，引用 ID 存在不够。只允许换行规范化，不能通过改写消除差异。

暂不建设网页抓取、PDF 平台或通用宿主适配。可靠宿主原事件以后可以接入同一入口；无接口就保留实际范围。“本地检查”这样的描述不是可核对事件标识。

### 4.4 文件交付核对

handoff 接收明确清单，采集当次存在性、内容标识和提交用途；数据层计算 linked/untraced/missing/changed/ambiguous。linked 必须有对应的成功生成或修改记录；presence_only 再次匹配也不能升级为已追溯。

不调用 Core finalize、不移动文件、不提高正式等级。Trace 日志和自身派生报告不放进 DNA/制备/QC 清单。完全没有提交的交付内容无法被清单核对自动发现。

### 4.5 故障和隐私

保留 normal/strict，普通 Trace 故障不阻塞成功 DNA 工作，严格模式只在原边界停止，不回滚文件。一个 Trace 一个写入者，用标准库非阻塞进程锁落实；冲突时普通模式停采并报告、严格模式调用前停止，嵌套观察复用，进程退出释放，不做锁服务。

凭据和长序列省略规则沿用，省略范围要说明；不默认保存无关聊天或完整 DNA 副本。旧文件移走/覆盖后无法恢复就明确标记。继续遵守序列上传同意和许可规则。

## 5. AI 整理动作与提交接口

### 5.1 谁发起

宿主 AI／人是组织者；SKILL.md 明确要求其在主要阶段结束、重大调整后或交付前组织已有记录。不是每次工具调用后追问一次理由，不是在渲染函数里隐藏一个 API 调用。

### 5.2 调用流程

1. inspect --data 输出固定事实快照：trace_id、through_sequence、运行、记录索引、事实关系、交付核对和缺口。
2. 宿主先读任务和索引，再按引用读取相关原记录；长任务可按阶段处理，但完整记录不丢失。
3. 写 organization.json，提交 basis、design_process 和可选 report_plan。**AI 不重写 source_records 或 fact_relations。**
4. organize --input 检查并追加组织版本，程序装配完整 graph.json。
5. 仅调整读法时用 report-plan --process-ref --input，保持原过程不变。
6. render 消费已保存结果，导出、打开、缩放和切换视图均不调用模型。

### 5.3 提交包形状

```json
{
  "schema_version": "trace-organization-v1",
  "id": "ORG-main",
  "basis": {"trace_id": "example-trace", "through_sequence": 5},
  "design_process": {
    "stages": [], "steps": {}, "relations": [],
    "paths": [], "unresolved": [], "detail_refs": []
  },
  "report_plan": {
    "title": "结构示例", "sections": [],
    "diagram": {"reading_order": [], "relation_refs": [], "short_labels": {}},
    "default_expanded_refs": [], "detail_refs": []
  }
}
```

这是字段形状，空数组不代表真实任务可验收；完整实例见附带 JSON。basis 来自程序，不猜序号；id 为组织逻辑 ID，revision、写入时间、作者通道由程序保存。

有设计记录的任务提交 organize 时，至少有一个目的明确的阶段和一个有真实引用的步骤；空包不能获得“已组织”输出。局部组织可以保存，但剩余内容必须进入详情或 unassigned，当前快照匹配不等于全部语义已组织完成。组织中提出的新设计建议只能标为后来建议；需要成为新的实际设计选择时，先通过原 Decision 提交路径记录。

AI 输出前检查阶段目的、真实分支、取舍依据、执行与计划区别；未知和未归类保留。新科学解释标为 later_interpretation，不能声称当时模型已经考虑过。

### 5.4 模式与成本

| 模式 | 目标行为 |
|---|---|
| Off | 不追加 Trace/组织事件；可以读取已有记录和编排 |
| Observed | 自动事实和已有提交，不默认额外 AI 理由或整理；明确请求整理时可组织已有材料，标明后来整理并计成本 |
| Full | 保留设计时短说明；宿主在阶段结束/交付前提交过程与编排，可同次响应完成 |

没有独立模型服务不等于没有 AI 工作。组织与编排确实增加 token、时间和工具轮次；联合输出只减少单独往返，不自动消除成本。开发默认 Full，发布默认待实测。

## 6. 程序核对与机器结果构建

### 6.1 三个明确的程序职责

```python
def build_facts(events, errors=(), *, through_sequence=None) -> dict: ...
def validate_organization(packet, facts) -> dict: ...
def build_process_result(facts, organization, report_plan=None) -> dict: ...
```

build_facts 处理原节点、执行关系、范围、目标匹配、已有适用性与变化影响；它是纯函数，不调用模型或读写 DNA。validate_organization 核对提交结构，不认证科学论证。build_process_result 汇合完整记录和组织结果，不能在没有 AI 组织时自动写出一份完整研究解释。

### 6.2 程序能检查什么

| 检查 | 规则 |
|---|---|
| 引用 | source_refs 指向快照已有确切记录；阶段、步骤、关系 ID 唯一且可解析 |
| 版本 | 节点、文件、组织和编排版本固定；不静默引用未来记录或最新文件 |
| 来源 | 原文和摘要分开；出处不存在、类型不符、原文不匹配分别报告 |
| 程序事实 | AI 不可新增 runtime Validation、produced_by 或覆盖原数值；只能引用原记录 |
| 关系 | 语义声明与程序关系分开；同运行或普通顺序不是科学因果 |
| 去向 | 相关记录进入过程、详情、技术类别或未归类；不能因未归类而消失 |
| 编排 | 章节、短标签及导图只能引用已有过程和关系，绑定确切组织版本 |

引用真实不证明解读正确。程序只能报告结构/引用检查结果；文字忠实度和科学支持须由明确的 AI／人复核，不能被结构通过替代。

### 6.3 完整信息的去向

程序以快照内全部已采集记录为分母，从步骤和 detail_refs 的引用、固定技术类别、未归类项计算 coverage。技术类别只包括行政性事件，不允许 AI 将失败、要求或交付文件随意改成噪声。

同一记录可多处引用，全文保留一份。未理解的内容进入 unassigned_refs；不可取得的大文件保留位置与状态。“记录都有去向”不证明归类正确，也不证明全部宿主活动已经采集。

### 6.4 陈旧组织

组织 basis 固定到事件前缀。新增要求、文件、检查或其他设计事实后，旧组织保留但标 stale；单纯组织/编排事件不算新设计事实。组织状态为 absent/current/stale；current 仅指快照匹配，不代表科学正确。

基于旧快照的结构有效提交可保存为历史版本，但不能替换当前组织。默认当前报告对新增未整理事实单列显示，并明确旧组织范围；不能把旧摘要套在新产物上。无组织时只给有限事实视图，不声称已完成设计逻辑整理。

## 7. 报告编排与确定性输出

### 7.1 报告编排是明确的 AI／人工工作

| 字段 | 含义 |
|---|---|
| title | 面向读者的标题，不扩大任务或结果 |
| sections | 标题、step_refs、摘要及其 source_refs |
| diagram.reading_order | 阅读顺序，不产生新的执行边 |
| diagram.relation_refs | 显示哪些既有事实/语义关系 |
| diagram.short_labels | 图中的短标题，不修改完整 content |
| default_expanded_refs | 默认展开的步骤、依据或问题 |
| detail_refs | 收起但仍能回查的完整内容 |

数据语义组织与报告编排可由同一宿主 AI 在同次响应提出。报告的重点、摘要和分组不是程序自动理解出来的；程序执行已经保存的编排。

### 7.2 省略的边界

不在概览显示，不等于从 graph.json 或日志删除。所有摘要保留引用；用户可从短标签进入完整步骤及原始材料。无有效编排时回退到固定事实视图或返回具体问题，不暗中调用模型。

程序固定展示所选文件的真实角色、原检查状态、当前影响结果的未解决问题和采集范围。report_plan 不能把 candidate 改称 authoritative，或隐藏缺失文件。已解决的历史失败可折叠但可回查；未请求检查不制造失败。

### 7.3 页面与导出

Document/Mind Map/Split 共用一个过程版本、report_plan、选中步骤和展开状态。AI 提供语义分组和短文案，程序决定尺寸、间距、线条和交互。相邻阅读节点没有关系时显示分组，不补边。

HTML 是主形式，Markdown 使用同一内容；PDF 暂缓。导出、主题、缩放和展开不调用模型。换受众或改重点时可仅更新 report_plan。视觉规则只维护在 design.md；外部原文和模型文本作为数据转义，不执行。

## 8. 保存方式和版本

| 文件/事件 | 作用 |
|---|---|
| events.jsonl | 原始观察、提交、修订，以及 AI／人的组织和编排版本，均追加 |
| organization_recorded | design_process、basis、逻辑 ID、程序分配的 revision、提交来源 |
| report_plan_recorded | 编排、确切 process_ref 和作者；可同次提交或单独修订 |
| graph.json | 完整机器结果，可由原事件和组织版本重新装配 |
| index.html / report.md | 固定渲染的阅读产物 |
| TRACE-MANIFEST.json | 原索引加记录截止范围、组织和编排版本 |

取消 r1 中 report.json 必须独立落盘的要求；渲染中间对象留内存。这样完整过程和编排在同一机器结果中，不维护重复组织。

新事件使用 evidence-trace-v0.2，读取器兼容旧 v0.1 和混合日志。数据格式版本、模块版本、组织 revision 分开。原作者角色仍是来源声明，不因写入程序而变成身份认证。

organize 先校验整包：结构错误不给新成功结果、不覆盖上个有效版本。有效时追加组织及可选编排；同一个写入者处理，部分写入失败保持可诊断，不谎称两部分都保存。记录缺动机可以保留 unknown；不要求编一个理由才能通过格式检查。

相同事件前缀、组织/编排版本和算法版本应得到稳定内容与排序；不要每次重建都给关系随机 ID。示例中所有引用可解析，但新方案没有执行证据，只显示“未记录执行”，不能变为 PASS。

## 9. 模块、CLI 与迁移

| 文件 | 目标职责 |
|---|---|
| runtime.py | 实际调用、文件、原材料和交付状态采集 |
| recorder.py | 追加、编号、版本及轻量引用索引，不每次运行全分析/renderer |
| models.py / provenance.py | 新旧字段、来源和说明身份、程序专有字段校验 |
| 新增 projection.py | build_facts，集中现有事实关系、计算与缺口 |
| 新增 process.py | 组织包和编排核对、版本处理、build_process_result；无模型 API |
| coverage.py / applicability.py / impact.py | 保留已有有限计算，不充当自然语言科学裁判 |
| reader.py | 消费完整过程及编排形成阅读对象，提供明确标识的事实视图回退 |
| render.py / view.js / view.css | 固定 HTML/Markdown 和交互，不再首次组织研究逻辑 |
| chain.py | 迁移有效计算后淘汰旧单 Decision 阅读组织，避免双实现 |
| trace_design.py | 快照读取、组织接收、核对、交付和渲染入口 |
| SKILL.md / references/evidence-trace.md | 实施时写清宿主何时读取快照、提交组织/编排、处理陈旧版本；详细字段集中在 reference，不把未实现命令提前教给当前使用者 |

projection 和 process 的区分是“事实索引”与“AI组织提交”的输入契约不同，不是另建自动科学引擎。原材料观察和文件状态的 I/O 留在 runtime；关系核对留在数据程序；报告不能反向修改事实。

| CLI 目标接口 | 行为 |
|---|---|
| config/record/coverage/compare | 保持现有含义，扩展必要字段 |
| observe --input | 原材料观察，返回事件 ID |
| inspect --data | 固定事实快照和完整记录索引 |
| organize --input | 校验保存 design_process 和可选 report_plan |
| report-plan --process-ref --input | 单独修订确切过程版本的读法 |
| handoff --input | 明确文件清单的来源核对，不执行提升 |
| reader [--run-id/--handoff-id] | 输出所选范围机器结果；缺组织时标事实视图 |
| render --format html/markdown/both | 固定渲染，默认 HTML，无 AI 调用 |

run-id 和 handoff-id 互斥。当时视图不纳入未来事实；完整历史中可查看旧决定的后来说明。编排不匹配过程版本时不自动换版本。

聚焦某次运行或文件时，不得裁掉 AI 摘要的部分依据后原样声称结论仍适用。普通聚焦保留完整过程作为背景并标明范围；严格历史截止只使用与该事实前缀匹配的组织/编排，没有则给事实视图或另行整理。程序不能为适配筛选自动改写科学叙述。此情况必须有专门回归。

公共入口结束后可以更新事实索引和已有报告，但不能自动启动模型；旧组织 stale 必须明显标识。保持原业务返回和异常，自动出报告的 on_finished 由上层提供，采集模块不导入 renderer。

旧日志保留，不倒填原消息或同期时间。新数据字段尚未实施，代码帮助、调用方、测试及映射须同次更新；当前 graph.reader 消费者改用完整结果和 reader 入口，旧派生文件可重建，不覆盖原日志。

## 10. 开发顺序及验收

| 步骤 | 交付与通过条件 |
|---|---|
| 1. 定机器结果契约 | 示例、组织包与引用校验明确；完整结果、AI提交、编排三者不混 |
| 2. 补采集 | 七入口、原材料与交付核对；新版 QC 文件有真实生成链 |
| 3. 接组织流程 | 程序快照 → 宿主组织 JSON → 核对保存 → 完整 graph；原记录有去向 |
| 4. 接报告编排 | 支持联合提交和单独修订；HTML/Markdown同源，重复导出无 AI 调用 |
| 5. 真实任务检查 | 对照原活动、机器结果和报告，检查信息保留及人类理解 |

### 工程验收

- 保留现有 Trace 回归，通过实际 CLI 验证，不能只用手造理想图。
- 固定相同 DNA 输入比较 Off/Observed/Full 的序列、拓扑、特征、完整引物、制备、检查语义和正式文件。
- 组织包不能新增程序事实；坏引用、错版本、未知步骤、未归类和陈旧组织均有明确行为。
- 重建不改变原事件；隐藏展示不删除记录；修改 report_plan 不修改 design_process 或 Core 结果。
- 原地编辑、失败残留、同名文件、转换部分失败和写入冲突按实际结果处理。
- 离线、键盘、窄屏、转义检查与内容忠实度分开报告。

### 真实任务验收

使用 2026-09-15 案例的新输出目录，不改旧 Trace，不要求 AI 故意失败或复述旧脚本。旧失败另作固定回归。

1. 最后四份 QC 文件能从交付清单追到标注动作和原文件。
2. 至少一项关键依据保留真实原资料/工具输出片段和位置，不以全部 unknown 代替来源能力。
3. 宿主实际产出阶段、分支、完整说明与依据对应，不以节点列表冒充已整理过程。
4. 重要组织判断能回查；后解释单列；缺动机不补造。
5. 短标签与摘要不改变结论，候选身份、检查范围和关键未决清楚。
6. 所有已采集相关记录都在过程、详情、技术记录或未归类中可查。

原 CDS 注释交付阻塞单列主线修复。Trace 可以证明准确记录失败，但该 DNA 工作流可发布仍要求解决交付；不能删失败特征、放宽 gate 或改目标取得绿灯。

### 人工与成本

人工分别检查机器结果和报告能否说明目标、取舍、依据、变化、实际结果和未知项，并回查出处。记录原回答、卡点和版本。静态稿原接受记录保留，新机器结构与最终报告仍需本轮检查。

统计组织次数、模型输入输出 token、工具轮次、时间与任务完成情况。联合生成过程/编排、单独修订编排分开统计。长记录按索引读取，完整保存不受一次模型输入限制；零渲染调用不等于零 AI 成本。

## 11. 交接与开放项

| 前序事项 | r2 处置 |
|---|---|
| Phase 1 日志、真实结果、normal/strict | 保留 |
| Phase 2 条件比较和字段覆盖 | 保留范围，不升级为完整语义整理 |
| Phase 3 Change Impact | 保留，不自动重跑或重新作科学结论 |
| Phase 3.1 第四步 reader | 复用事实整理和阅读组件，调整职责，历史完成记录不抹去 |
| 旧 HTML | 使用完整过程及编排替换旧组织，不长期维护两套主阅读逻辑 |
| Archify | 借鉴作者组织与固定编译，不照搬视觉容量限制或引入 Node 编译器 |
| 宿主外活动和来源声明 | 保留实际范围，依赖明确提交或可靠接口，不宣传全自动完整观察 |
| 真实案例正式交付阻塞 | 单列主线缺陷，不能用 Trace 掩盖 |
| 后续治理阶段 | 继续延期 |

待验证：阶段粒度、大记录组织成本、发布默认 level、换受众时编排修改成本。字段和 CLI 可在实施时简化，但不能退回“没有组织产物、只有散点关系”。

完成后更新本设计、当前计划、索引和接口映射，记录测试、失败、跳过与限制，提交开发分支并检查对应 CI。本轮只更新文档，不宣称任何新接口已实现。
