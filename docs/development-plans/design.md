# Evidence Trace Phase 3：Living Evidence Document

## 补救设计决定（2026-09-11，尚未实施 HTML）

Evidence Trace 是事实与证据记录系统；Design Decision Trace 是默认的人类可读组织方式。新增默认项必须说明帮助理解哪个设计决定。下一版按完整设计过程组织 Document 与主干式 Mind Map，证据旁支折叠，用户/AI 选择与程序结果分开。三种阅读模式共享步骤选择；原始记录下沉高级信息。

首页先交代研究背景、当前任务和为何需要用户/AI/程序共同参与的证据记录，再进入选择。GFP +3 bp 只作工程案例；[Reader Demo 候选](safety-phase-3-reading-draft.md) 先确认故事完整、选择有意义及证据边界清晰，再进行真人试读。来源不足不自动补写项目背景或用户否决。

实施遵循 [补救计划](safety-phase-3-readability-v0.3.1.md)：静态真实案例稿通过真人试读后才能重构 renderer/HTML。Observed 保留已有理由而不要求额外说明；Full 说明随原设计响应提交；事后解释独立标记。以下规范记录当前 v0.3 页面，单 Decision 环形布局不作为下一版目标。

本文是固定 renderer 的实现规范，不是宿主运行时生成 HTML 的提示词。Phase 2 视觉约束保留在 [历史设计](design-phase-2.md)。当前计划：[Phase 3](safety-phase-3-change-impact-v0.3.md)。

## 信息架构

主界面是一份科研证据文档。顶部为文档标题、当前运行和一行具体待复核状态；不设 KPI 卡片墙。

一级模式：Document / Mind Map / Split。三者是同一 Trace 的投影，使用同一 `selectedDecision`、`selectedNode`、`expanded` 与运行选择。Map 点 D03 后，Document 定位 D03 章节，Split 保留同一对象。变更 drawer 也不能重置阅读状态。

左侧为 Decision 目录和辅助入口：Review Queue、Changes、Artifact Trace、Advanced Graph、Audit Log。默认阅读入口仍是文档，不把辅助工具堆成仪表盘。

## 阅读与导图

Document 每个 Decision 是一章，顺序 Why → Evidence → Applicability → Validation → Change Impact → Output。正文靠版心、行距、编号与留白分层；证据默认摘要，详细条件和原始程序结果可展开。短 ID 与实际理由比大量状态标签优先。

Mind Map 占据主区域，以 Decision 为中心。Requirement 左上，Claim 右上，Evidence 左侧，Validation 右侧，Artifact 右下，Changes 左下，Review 外围。位置稳定、连接稀疏；默认一层。Evidence 先聚合四类关系，再展开来源；长列表有明确的查看更多入口，不一次画出蜘蛛网。

Split 左图右文档；点击任一节点定位右侧相关内容，正文中的引用可回到对应节点。绘制使用原生 SVG，文本仍可键盘选择/聚焦。提供缩放与适配视图，详情由 drawer 或正文承担。

Changes 在正文和图外围显示对应 Change ID、前后版本与建议，点击直接看旧值/新值及依赖路径。STALE 表示旧上下文，不把原 Validation 的 PASS 改成 FAIL。未知依赖显示 UNKNOWN，不隐藏。

## 视觉

采用 Sterile Biosecurity Interface：冷灰白底、深灰蓝正文、细分隔线，结构以排版与留白为主。等宽字体仅用于 ID、版本、坐标和数值。小半径控件，无大圆角卡片、渐变、毛玻璃、假 KPI 或营销式标题。

正文 15–16px、行距约 1.7，版心约 760px；章节明显分隔。颜色只表示选中、明确失败、需要复核或旧上下文。动效限 150–220ms 展开/选中反馈，并支持 reduced motion。

## 交互验收

- Document/Map/Split 来回切换不丢选择和展开状态。
- 默认图不因 20 条证据变成复杂网络；逐层查看时保留不同 aspect/限制。
- 点击 Change 能回到受影响的旧修订，不暗示新修订已完成复核。
- 桌面、窄屏、键盘可完成定位决定、打开来源、查看变化、反查产物。
- 5 秒看到状态、15 秒理解理由、30 秒追到来源需真实用户计时；截图和自动化可达性不能替代这些结果。
