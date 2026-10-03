# Evidence Trace Phase 2 — UI / Interaction Design

> 用途：给开发 AI **第一次实现** Phase 2 页面时使用。本文是设计规范，不是运行时提示词。最终 UI 必须写入确定性的 renderer / 前端代码；宿主 LLM 只能提交结构化 Trace 数据，**不得按本 Markdown 临时生成 HTML/CSS/页面结构**。

视觉参考：[evidence-trace-phase2-reference.svg](evidence-trace-phase2-reference.svg)。参考图定义方向，不要求逐像素照抄。

## 1. 目标

页面必须让生物研究者快速回答：**做了什么决定 → 为什么 → 依据是什么 → 证据是否适用 → 程序检查了什么 → 产物是什么 → 还有什么没解释清楚。**

核心原则：**底层允许复杂，前台必须清楚。** 不把全局 Evidence Graph 当默认阅读界面，不画“蜘蛛网”。

## 2. 默认信息架构

### Main Chain（默认）

主干固定围绕当前选中的 Decision：

`Requirement → Decision → Claim → Validation → Artifact`

Evidence / Applicability 作为 Decision 或 Claim 的**旁支**挂接，不强行塞进一条死直线。

旁支默认聚合：`Supporting n`、`Limiting n`、`Opposing n`、`Context n`。每组只预览最相关的 2–3 条，其余折叠为“查看另外 n 条”。同一证据可对不同 aspect 保留不同关系，不能被 UI 合并成一个“总体支持”。

### Focused Branch

点击 Decision / Claim / Evidence 后，只展开与当前节点有关的局部链，隐藏无关关系。右侧 Detail 显示理由、Claim、证据条件/限制、Applicability、Validation、Affected Output。

### Advanced Graph

完整网络保留为高级视图，仅用于审计和全局探索，不承担默认解释任务。

## 3. 页面结构

顶部只保留 3 个状态摘要：
- **Trace Integrity**：记录是否完整；绝不等于“安全”。
- **Decision Coverage**：`8 explained · 2 need review`，优先显示计数而非百分制。
- **Evidence Applicability**：显示 partial / extrapolated / unknown 的数量。

主体：左侧 Evidence Chain，右侧 Decision Details + Review Queue；底部可显示 Final Output & Validation。Review Queue 必须**按 Decision 聚合**，不要让用户处理 `E17@2` 之类内部节点编号。

## 4. 视觉规范

- 风格：简洁、高级、现代、科学软件；大留白、强层级、低噪音。
- 背景：off-white / 极浅灰；正文深灰蓝；主色 muted blue / teal；amber 仅表示限制/待复核；red 仅表示明确冲突/失败。
- 卡片：细边框 + 极轻阴影，圆角约 10–14 px；避免彩色大面积渐变。
- 间距：采用稳定 8 px grid；主链节点间距明显大于卡片内部间距。
- 字体：系统无衬线；标题与正文靠字号/字重分层，不靠大量颜色。
- 连线：主干线更明确；旁支线更细、更淡、可折叠。禁止大量交叉线。
- 图标：统一线性/轻量风格；不要用装饰性插画抢信息层级。
- 动效：只用于展开、聚焦、状态变化；150–220 ms，克制，不做炫技滚动动画。

## 5. 文案与状态语义

必须使用具体状态：`来源已核验`、`宿主匹配`、`培养条件不同`、`程序检查 PASS`、`未记录 rationale`。

禁止用模糊总绿灯：`Evidence sufficient ✓`、`Safe ✓`、`Verified design ✓`。

`Trace integrity: complete` 只表示约定范围内记录完整；Source verification、Applicability、Claim、Validation、Safety 始终分开。

## 6. 实现约束

1. 页面由版本化代码从 `events.jsonl / graph projection` 确定性生成；同一事实源应得到相同结构。
2. LLM 不拥有布局、颜色、节点位置和页面模板的运行时控制权。
3. 旧 Phase 1 trace 可直接打开；缺新字段时降级显示，不迁移/重写历史事件。
4. 默认 Main Chain + Focused Branch；Advanced Graph 可保留，但不得成为唯一关系视图。
5. Evidence 很多时先聚合再展开；单个 Decision 关联 10–20 条证据也不能形成视觉蜘蛛网。
6. 键盘可聚焦、颜色之外还要有文字/图标状态，保证基本可访问性。

## 7. 第一次实现优先级

先实现：**主干+折叠旁支 → Focus Mode → Decision-based Review Queue → Detail → Advanced Graph**。完成后再精修微交互，不要先堆视觉装饰。
