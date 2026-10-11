# Evidence Trace：数据层到阅读层的映射

接口 v0.3.2，当前实现参考。当前阅读结构与提交契约见[使用说明](evidence-trace.md#complete-process-and-report-submission)。本表定义数据去向，不增加必填栏目或新的事实源。

本表保留底层事实 reader 的映射；完整输出现由 projection → process → report 形成。`reader` CLI 返回完整机器结果，`--run-id` 在其中增加 focused_reader，不裁掉组织依据。HTML/Markdown 消费 report；缺失或陈旧组织退回明确标注的事实视图。新的字段与提交方式见[使用说明](evidence-trace.md#complete-process-and-report-submission)。旧 chain 仅提供适用性/覆盖/影响与兼容诊断，不再组织默认页面。

## 映射表

| 原始数据 | 阅读层位置 | 转换边界 |
|---|---|---|
| Requirement.text、已提供的 context | 背景与“要求”步骤 | 背景只采用已提交文字，不从文件名/参数编研究目的 |
| requirement_source、request_action | 来源标记、用户修改/确认/否决 | 提交者不等于用户；未知来源保留未知，不能自动制造用户介入 |
| Decision.text、decision_actor | “选择”步骤及类型前缀 | 没有明确归属就标选择者未记录，不按 actor 猜 AI 自主选择 |
| rationale、explanation_origin | 对应选择的理由旁支 | 原文保留，标明用户/AI/未知来源，不自动补理由 |
| Source → Statement → Claim 和条件 link | 对应选择的依据与限制旁支 | 不成为独立主链步骤；保留 aspect、支持/反对/限制关系和具体范围 |
| computed applicability、verification | 依据旁支的条件说明与详情 | 来源真实、条件匹配、当前判断分开；partial/unknown 不自动变成一个待办 |
| explanation_added | 原选择的事后说明旁支 | 保留补录时刻和旧版本，不重写原理由或旧运行视图 |
| design_choice_observed / 旧输入快照 | 匹配的输入放选择旁；尚未关联选择的输入按调用生成“程序结果”摘要 | 完全或部分缺 Decision 都可阅读；相同参数的不同调用不合并；返回后观察不是新的科学选择 |
| 关键 stage_completed、stage_failed | “程序结果”步骤 | 例行日志下沉；被明确引用的发现可以提升为步骤；计划不等于执行 |
| Validation | 按实际返回事件分组的检查步骤 | 同一次检查只出现一次；未请求项只留详情；如实保留失败和未知结果 |
| Artifact | “产物”步骤及附属文件 | 同次返回中同名三格式可合并；不同运行/生成事件不合并版本；候选不升级成正式产物 |
| 后续输入引用的 Artifact | 关键中间产物及材料引用关系 | 优先采用已有路径与内容锚点；歧义保留，不靠文件名猜实际来源 |
| Change、既有 impacts | 相关步骤的变化旁支；必要时生成复核项 | 不重复制造一次修改步骤，不改原检查结果，不运行建议的重算 |
| basis_refs、responds_to、previous | 有来源的关系 | 声明依据、要求响应、版本修订分别标记；均不自动变成已证明的科学因果 |
| run/context_refs/decision_refs、stage_ref | 运行筛选、步骤归属与执行顺序 | 历史依据可以回查，但不算当前运行的新检查；平行产物不强串成一条链 |
| issues、coverage/explanation/association gaps | 记录诊断与来源缺口 | 不直接填满 Review；真正失败、证据冲突及未处理影响需保留 |
| 原始 ID、版本、哈希、完整事件 | 独立技术文件 | 默认摘要不用内部字段作标题；所有摘要仍能追到原记录 |

## 统一投影接口

`graph.reader` 由固定 Python 代码从已记录图、阶段、适用性与影响结果派生；不调用模型、不读写 DNA、不追加事件。

- `version`：阅读投影接口版本。
- `context`：已提交的背景与要求；全历史默认使用最新要求版本，单运行视图使用该运行的记录范围。没有背景就留空，不合成一个研究目的。
- `steps`：所有已记录过程中的唯一阅读步骤，含类型、标题、摘要、来源、旁支及引用。
- `runs`：每次运行的背景、步骤成员和实际结果状态；Document、Mind Map、Split 共享同一套成员。
- `relations`：显式关系及其范围/来源，不自动增加相邻步骤间的因果线。
- `review`：按相关步骤聚合的具体待办；各组 `items` 分别保留依据和运行范围，筛选时不能把后来事项混入旧组。
- `diagnostics`：采集故障、覆盖/说明/关联缺口，与设计待办分开。

步骤含 `kind / label / title`、可选摘要/检查/文件/旁支，以及 `record_refs / event_refs / run_ids`。`position.anchor_sequence` 是排布锚点，不冒充原事件时间；`position.basis` 标明按记录、调用锚点或旧运行摘要定位。步骤 ID 由原节点/事件确定，不新建哈希。

旁支按需包含 reason、evidence、supplements、changes、observed_inputs、basis_refs。声明的直接依据可回查；有用户/程序依据的判断不被强迫再造论文链。`assessment` 等机器细节不是默认栏目。

界面维护选中步骤与展开状态，投影不维护会话。run_ids 只表示记录归属，不能单独证明某个选择被采用。无运行的声明/程序记录仍可呈现，但不会创建假 run；程序记录的作用范围标为未关联运行。

运行筛选必须同时筛选步骤和旁支：后补证据/解释不能进入更早运行的“当时已知”视图。完整历史仍可看到后来补充；选择旧版本时不会跳到新版本。

筛选后的 `related_steps` 只为跨运行关系提供历史对象引用，带 `reference_only=true`、来源与原始记录入口；不计作本次新检查或新产物，也不携带后来追加的旁支。当前步骤和每个 review item 的运行范围同时收窄。完整历史视图仍保留所有关联。

## 顺序与聚合

有调用锚点时，程序输入按对应开始事件定位，返回与失败按原事件定位；缺锚点时保留记录顺序并标明依据。记录序号用于稳定排布，不是生物学因果证据。

同一返回事件的多个检查合为一个程序步骤。文件按运行、角色、目录、名称和生成事件分组，避免同名文件覆盖版本；同运行的同名不同生成记录也有可区分的标题。缺少生成锚点的旧记录保守分开。

常规辅助文件留在运行文件列表；被后续引用或明确作为依据的材料提升为关键中间产物。没有正式交付时，candidate 目录中的现有候选也可呈现，明确标为非正式产物。材料路径和已有内容锚点仍有多个匹配时，只保留歧义诊断，不猜一个生成记录。

有限的固定词表翻译检查名称与状态，不能把一个聚合 PASS 改写成程序未执行过的具体检查。未知输入只能按原参数说明；不自动解释某个突变的科学作用。

Review 保留实际失败/未知检查、明确反对关系、缺失已记录判断依据及相关变化影响。一般性的 partial/unknown 适用性和来源核验状态留在证据旁支，不自动每条生成待办。完整性和覆盖缺口属于 diagnostics；旧运行视图仍显示全局日志故障，不能用筛选隐藏损坏记录。

## 读取方式

```text
python scripts/trace_design.py reader --trace-dir <目录>
python scripts/trace_design.py reader --trace-dir <目录> --run-id <已记录运行>
```

命令只向标准输出提供 JSON，不写回日志、文件或 HTML。正常的 graph.json 派生过程也包含 reader 字段；默认三视图消费 report，底层 reader 保留为事实与兼容诊断。

## 验收重点

简单 Observed 流程、无运行的声明记录、重复检查、并行产物、旧版本选择、晚补证据/说明、无变化和无待办、实际失败与 Trace 故障。三档 DNA 回归仍保持一致。此接口完成不等于第五步 HTML 已重构。


## v0.3.2 默认详情与存储

`report.sources[ref]` 保存 title、type_label、fields（可读标题与正文）、related（明确引用）、links（可操作来源/文件入口），不再带原始 data。普通展开只消费这份投影；未知类型给出有限说明，完整对象仍可在技术文件读取。`recording_gaps` 与科研 review 分开；交付清单中无生成关系的文件也有可读条目。

graph/reader 对外格式为 design-process-v2，重复运行与审计对象用 JSON Pointer 指向 source_records。旧程序可调用 expand_machine 得到 v1 内存布局；原 events 不改。具体引用字段见[使用说明](evidence-trace.md#v032-capture-and-machine-export)。


2026-09-21 补正：默认详情的 evidence 按实际 Decision/Claim/关系成组保存，包含 decision_ref、decision_title 及原证据条件；由全部已记录选择生成，不由正文是否展示该选择决定。正文只取自身 subject 的依据。change_details 提供实际前后值与影响，sources/steps 的 changes 保留对应对象的影响；原机器结果和验证状态不改。问题领域由事实层传递，未识别类型仍可见，不用报告白名单吞掉失败。
