# Archify 实现对照与 Evidence Trace 可借鉴部分

2026-09-19。研究对象：[tt-a1i/archify](https://github.com/tt-a1i/archify)，固定提交 `72c750bb070d95171dbb2244e5b62b1b7da69c12`，该提交 package.json 标记 `2.17.0-dev.1`。

本次读取了具体 schema、工作流示例、编译器、校验器、公共输出方法，并复核来源检查、导览和路径代码。没有运行完整绘图系统、浏览器验收或性能测试，没有安装或修改 Archify。以下代码结论针对该提交；建议不是已经完成的 Evidence Trace 改动。

## 1. 最值得借鉴的共同点

**Archify 先要求 AI／作者把过程组织成有明确字段的 JSON，再让程序校验、布局和输出。** 它不是让程序从没有结构的零散信息中自行理解系统。

其“中间表示”可以理解为：介于原始需求和最后图形之间、机器能读取的结构化说明。这个概念与我们正在确定的数据层输出接近，但 Archify 的中间表示主要为图形编译设计，我们需要保存更完整的来源、历史及科学判断边界。

实际调用链：读取 JSON → 格式与引用检查 → 工作流约束检查 → 计算布局和线条 → 生成 SVG → 填入固定 HTML 模板。[工作流入口](https://github.com/tt-a1i/archify/blob/72c750bb070d95171dbb2244e5b62b1b7da69c12/archify/renderers/workflow/render-workflow.mjs)、[公共加载与输出](https://github.com/tt-a1i/archify/blob/72c750bb070d95171dbb2244e5b62b1b7da69c12/archify/renderers/shared/cli.mjs)。

## 2. 它的数据并不只有节点和连线

实际的工作流示例包含：

| 字段 | 在 Archify 中的作用 | 对我们的启发 |
|---|---|---|
| `nodes` | 具体对象/步骤，含稳定编号和文字 | 记录可被明确引用 |
| `edges` | 作者给定的连接、方向、标签和角色 | 关系本身是数据，不靠显示位置猜测 |
| `lanes` | 按参与者或职责分区 | 用户、AI、程序等视角可以明确，但不是必须每次分成泳道 |
| `phases` | 给列范围命名为阶段 | 数据层应已经说明阶段及阶段目的 |
| `groups` | 指定局部分组 | 把一组相关步骤组织成有意义的单元 |
| `mainPath` | 声明主要阅读路径的节点顺序 | 主线可以显式保存，但不能替代失败和其他分支 |
| `meta.views` | 命名的阅读视角，包含 focus 节点和说明 | 同一完整过程可提供不同读法 |
| `cards` | 补充说明文字 | 文字可以和图共存，但这些卡片不是逐段绑定证据的科学报告 |

例如，其 agent-tool-call 示例同时定义请求到结果、安全与恢复、证据与存储三个视角；view 通过已有节点 ID 指定关注范围。[示例 JSON](https://github.com/tt-a1i/archify/blob/72c750bb070d95171dbb2244e5b62b1b7da69c12/archify/examples/agent-tool-call.workflow.json)。

这正好补充我们此前方案的不足：数据层除了保存事实和关系，还应交出已经组织好的任务、阶段、步骤、分支和过程说明。报告层不应承担首次组织设计逻辑的责任。

## 3. AI 与程序究竟分别做什么

### AI／作者

选择节点和关系，写名称与解释，定义阶段、分组、主路径和导览。代码来源场景要求先检查仓库再写说明。[作者契约](https://github.com/tt-a1i/archify/blob/72c750bb070d95171dbb2244e5b62b1b7da69c12/archify/references/authoring-contract.md)。

### 程序

`validateSchema()` 用预生成的校验器检查字段；公共方法检查导览引用和关系 ID；`compileWorkflow()` 对输入作稳定排序并计算布局。它不会调用一个内置模型去重新理解系统或判断作者的技术解释是否成立。[格式校验](https://github.com/tt-a1i/archify/blob/72c750bb070d95171dbb2244e5b62b1b7da69c12/archify/renderers/shared/validator.mjs)、[编译入口](https://github.com/tt-a1i/archify/blob/72c750bb070d95171dbb2244e5b62b1b7da69c12/archify/renderers/workflow/workflow-compiler.mjs#L4398)。

对我们可借鉴的是这种明确分工：AI／人负责有来源的语义组织，程序负责能够核对的事实、结构和约束，最终输出使用固定代码。不能把“Python 可以连接节点”扩大成“Python 可以独立整理科学设计逻辑”。

## 4. 它的语义校验实际有多强

`semanticContractDiagnostics()` 检查的是作者声明的约束：

- 被引用的节点是否存在；
- 没有入边或出边的节点是否被允许；
- 指定必需连接是否存在；
- 指定两点之间是否存在有向路径。

未提供 semanticChecks 时该项检查直接返回空结果。它能发现声明的流程缺连接，不能验证流程是否真的发生，或某个节点解释是否正确。[具体实现](https://github.com/tt-a1i/archify/blob/72c750bb070d95171dbb2244e5b62b1b7da69c12/archify/renderers/workflow/workflow-compiler.mjs#L638)。

**不能照搬的地方：** 某些修复提示会建议作者增加缺少的边。架构图作者可以补充正确的设计关系，但 Evidence Trace 中缺边可能就是实际缺少证据。我们的修复路径应是找原记录、登记真实观察或保留缺口，不能为了通过检查补出一个关系。

## 5. 它怎样防止交互凭空增加关系

### 导览顺序与实际连线分开

`meta.views` 声明一组节点的阅读顺序。`validateGuidedViews()` 检查 focus 引用是否存在、是否重复；`storyStep()` 再查看相邻节点之间实际有哪些边。若没有边，使用 group，不能据导览顺序补一条执行边。[引用检查](https://github.com/tt-a1i/archify/blob/72c750bb070d95171dbb2244e5b62b1b7da69c12/archify/renderers/shared/cli.mjs#L117)、[导览分类](https://github.com/tt-a1i/archify/blob/72c750bb070d95171dbb2244e5b62b1b7da69c12/viewer/guided-views.js#L641)。

### 路径只沿作者给定的边查询

`shortestDirectedPath()` 在现有有向边上进行广度优先搜索，即按连接数量逐层寻找路径；不可达就返回空结果，不补边。这个结果是图上最少跳数的一条路，不是实际执行历史或唯一因果路径。[路径计算](https://github.com/tt-a1i/archify/blob/72c750bb070d95171dbb2244e5b62b1b7da69c12/viewer/route-probe.js#L265)。

我们的正文、导图与阶段导览也应采用这个区别：研究者可以按研究问题阅读，但“阅读时先看哪个”不得改写为“哪个导致哪个”。从产物反查来源时，也要说明查询了哪类关系，而不是把所有连线混成因果链。

## 6. 它的来源核实值得参考，但范围有限

architecture 图的 `verifyRepositoryEvidence()` 将来源固定到仓库 URL、完整提交 ID、文件路径和可选行范围。程序从指定提交对象读取文件，核对本地 origin、提交存在性、文件类型和行范围，而不是只相信作者填写的 source 字符串。[来源检查实现](https://github.com/tt-a1i/archify/blob/72c750bb070d95171dbb2244e5b62b1b7da69c12/archify/renderers/shared/repository-evidence.mjs#L75)。

应准确理解其边界：无来源的组件被跳过；存在至少一条有效来源引用后可以返回 verified，并附引用数量和对应节点。它不要求全图每个节点都有来源，也不判断该段源码是否支持作者写的解释。本地 origin 一致也不等于远端身份认证。[跳过与返回规则](https://github.com/tt-a1i/archify/blob/72c750bb070d95171dbb2244e5b62b1b7da69c12/archify/renderers/shared/repository-evidence.mjs#L161)。

对应我们的设计，应分别表达：来源能否定位、原文是否对应、内容支持关系是谁提出、哪些节点仍无依据。文件和论文不能只有“已核实”一个总标签。

## 7. 对三层重构的具体建议

| 层 | 借鉴什么 | 保留我们的区别 |
|---|---|---|
| 采集 | 来源有确切位置和版本，而非只有自由文本说明 | 还需真实工具输入输出、文件修改和事件日志；Archify 没有替我们解决这些采集缺口 |
| 数据 | 显式阶段、分组、主路径、分支和稳定关系；有条件的结构校验 | 保存完整过程内容和原始依据，给 AI 整理的语义关系注明来源；不将程序可达性当作科学因果 |
| 报告 | 固定编译、同数据多视角、导览不新增边、错误指向具体对象 | 主形式仍是可读科研报告；不能以小图的简洁限制底层证据数量 |

建议把数据层最终交付进一步明确为：

```text
结构化设计过程
  任务目标与约束
  已组织的阶段、步骤与实际分支
  各步骤完整说明及原记录引用
  执行关系与声明的证据关系
  失败、修改、未采用方案和未知项
  产物、检查范围及交付状态
```

在这份完整结果上，可以保存或派生“看总体路线”“看某个决定”“从文件反查”等阅读视角。它们引用同一批对象，不复制出彼此不一致的科学结论。

AI 辅助形成语义组织时，只能引用已取得的记录，新增整理判断标为整理者判断；程序校验引用、范围和执行一致性。AI 组织结果与程序计算结果应在数据层汇合，不能把最后的语义组织留给 HTML 页面生成。

## 8. 哪些不建议直接搬进来

- **不把 Archify workflow schema 当成完整证据存储格式。** 其 col 限定为 0 至 5，阶段/分组绑定列位置；通用导览最多五项。这些适合其图形产品，不适合作为我们完整过程和证据的容量限制。[workflow schema](https://github.com/tt-a1i/archify/blob/72c750bb070d95171dbb2244e5b62b1b7da69c12/archify/schemas/workflow.schema.json)、[通用导览 schema](https://github.com/tt-a1i/archify/blob/72c750bb070d95171dbb2244e5b62b1b7da69c12/archify/schemas/common.schema.json)。
- **不把完整科学关系交给布局程序推导。** 它的编译器主要解决尺寸、间距、路线和图形质量，不能补齐我们遗漏的原文或真实动作。
- **不把图形验收当作内容忠实度验收。** 交付文档本身也区分确定性检查、浏览器证据和人工视觉判断。这里引用的是其契约，并未执行它的交付流程。[交付契约](https://github.com/tt-a1i/archify/blob/72c750bb070d95171dbb2244e5b62b1b7da69c12/archify/references/delivery-contract.md)。
- **不在本轮直接引入整套 Node 编译器。** 可先借鉴数据组织和交互规则，用现有 Python/HTML 实现；以后若要试用其绘图能力，应作为报告层的有限输出方式，不成为新的事实来源。

代码如有实际复用，保留其 MIT 许可及 Archify、Cocoon AI 的版权声明。[LICENSE](https://github.com/tt-a1i/archify/blob/72c750bb070d95171dbb2244e5b62b1b7da69c12/archify/LICENSE)。

## 9. 对当前设计稿的影响

此前开发稿的纯程序 build_trace 可以继续负责执行事实与可计算关系，但不能单独承担完整科学过程的语义组织。下一次修订应先明确“结构化设计过程”的内容和来源，再安排 AI 提交/整理与程序核对的分工。

本笔记记录参考结论；结构组织与固定渲染的分工现已纳入[三层设计 r2](development-plans/safety-phase-3-three-layer-design-v0.3.1.md)。未复制 Archify 代码，也未把其图形 schema 选为正式数据契约。
