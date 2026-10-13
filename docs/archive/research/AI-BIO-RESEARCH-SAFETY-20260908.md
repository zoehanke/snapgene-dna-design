# AI 参与生物学研究的安全问题：针对性文献总结

检索日期：2026-09-08。重点是正常科研目标下，AI 在规划、工具调用、实验操作和解释结果时产生的风险。本次为针对性检索，不是系统综述；不修改软件，也不把讨论中的功能算作已实现。

## 主要结论

这类研究确实存在，不能将其概括为“防止用户用 AI 设计生物武器”。已有工作直接研究实验室危险识别、执行过程约束、实际操作观察和研究结论独立审计。证据层级不同：安全答题、虚拟环境干预、真实实验观察、实际危害降低不能互相替代。

对本项目最关键的新发现是 **LabGuard 已实现自然语言实验规则到运行时约束的转换**。因此，之前讨论的“给代理加一层受控执行”不能直接当作独创贡献；需要明确与已有工作的差别，并验证在实际 DNA 设计工作流中的增量价值。

## 直接相关研究

### 1. LabSafety Bench：正常实验中的风险判断

**Zhou et al. Benchmarking large language models on safety risks in scientific laboratories. Nature Machine Intelligence, 2026.**

19 个受测语言／视觉语言模型在危险识别任务上均未超过 70% 准确率。研究包含选择题和开放场景，评估危险识别、风险判断及后果预测。它证明这些受测模型在设定任务中仍会漏判，不等于测得现实事故率，也不能外推为所有当前模型的表现。[原文](https://www.nature.com/articles/s42256-025-01152-1)

### 2. LabGuard：把规则落实到执行边界

**Yang et al. LabGuard: Grounding Natural-Language Laboratory Rules into Runtime Guards for Embodied Laboratory Agents. arXiv, 2026；核对 v2，2026-07-31。**

将实验室规则转换为可执行约束，在控制器边界监测动作。作者在特定仿真设置报告不安全事件指标由 39.5% 降至 23.8%。全文明确所有运行与压力测试均在虚拟环境，未验证真实实验室安全；超出已有规则表达范围的风险仍会漏检。[摘要及版本](https://arxiv.org/abs/2606.31045)；[全文与局限](https://arxiv.org/html/2606.31045v2)

### 3. Lab Note：用实际操作记录检查偏差

**Skowronek, Nawalgaria & Mann. Multimodal AI agents for capturing and sharing proteomics laboratory practice. Molecular Systems Biology；2025-12-15 在线发表，2026 年卷期。**

用视频与参考流程比较，研究操作错误和遗漏检测。测试包含 70 个预设错误、28 个实验、421 个步骤；召回率 0.74、精确率 0.41，误报明显。仅在作者本实验室验证，属于实际视频观察证据，不是自主执行安全的证明；步骤偏差也不能全算生物安全事件。[原文](https://link.springer.com/article/10.1038/s44320-025-00179-1)

### 4. AI 科学家的系统性风险

**Tang et al. Risks of AI scientists: prioritizing safeguarding over autonomy. Nature Communications, 2025.**

明确区分恶意使用与善意目标下的意外后果，覆盖基础模型、规划、行动、外部工具及记忆／知识。提出关注整段行为和环境反馈，而非只评判回答内容。属于 Perspective，提供问题分解与研究议程，不构成完整生物安全系统的实证证明。[原文](https://www.nature.com/articles/s41467-025-63913-1)

### 5. KOSMOS 独立评估：结果自洽仍需外部检验

**Nusrat & Nusrat. When AI Does Science: Evaluating the Autonomous AI Scientist KOSMOS in Radiation Biology. arXiv, 2025，预印本。**

对三个放射生物学问题引入随机基因等零模型审计，作者归纳出一个得到较强支持、一个不确定、一个错误的假设。样本极小，不能推导模型的一般错误率；它支持独立核查科研结论的必要性，主要属于科学可靠性证据。[原文](https://arxiv.org/abs/2511.13825)

## 补充对照

| 研究 | 能支持的判断 | 不能据此声称 |
|---|---|---|
| [LABSHIELD，2026 公开稿](https://arxiv.org/abs/2603.11987) | 以 164 个操作任务研究多模态实验室风险理解与安全规划 | 等同于真实实验中的事故预防效果 |
| [ABC-Bench，2026 作者稿](https://arxiv.org/abs/2606.11150) | 评估生物代理的工具与 DNA 设计能力，并含三次 DNA 组装湿实验验证 | 完成组装就证明安全机制可靠 |
| [Robin：A multi-agent system for automating scientific discovery，Nature，2026](https://www.nature.com/articles/s41586-026-10652-y) | 真实生物发现系统披露了安全措施；主文有发现能力及组件消融的证据 | 把发现能力验证等同于防护效果验证；本次核对的主文未见安全措施的独立对照验证 |
| [Steering towards safe self-driving laboratories，2025](https://pubmed.ncbi.nlm.nih.gov/40826175/) | 自动化实验室需考虑现实环境、硬件与操作事故；可借鉴其系统安全视角 | 将化学自动化场景的结论直接等同于合成生物学遏制安全 |

## 对当前项目的启发

以下是基于文献的项目判断，不是文献已证明的本项目效果。

1. **先确定研究的是哪一种安全。** 生成错误序列、错误解释统计结果主要属于可靠性；破坏明确的生物安全措施、越过已批准的材料或操作边界，才应进入相应安全指标。
2. **检查对象应包括执行中间过程。** 实际输入来源、工具参数、中间产物和最终分子均可作为独立证据；代理生成的完成说明不能独自承担验收。
3. **要区分规则理解错误与规则覆盖不足。** 一个检查器只认识有限风险时，即使实现完全正确，也可能遗漏范围之外的问题。应显式报告覆盖和未知项。
4. **不能只测拒绝率。** 应同时观察真实安全约束违反、正常任务完成、误拦截与人工负担，并设置没有额外防护的对照。
5. **现阶段不宜承诺通用安全保证。** 可研究一个明确、可复现的 DNA 工作流风险，但其价值需要和 LabGuard 等已有方法比较，不能靠改名或增加审核模型证明创新。

可借鉴的具体研究方法是：LabSafety Bench 的情景化评估、LabGuard 的执行边界对照、Lab Note 的独立实际观察，以及 KOSMOS 审计的外部零模型。它们分别解决不同问题，不能拼接成“全流程已安全”的结论。

## 推荐阅读顺序

先读 **LabSafety Bench**，了解当前风险判断测试已经做到哪里；再读 **LabGuard**，核对执行层防护的已有实现和局限；随后读 **Lab Note**，理解如何让实际过程提供可检查证据。Tang 等的 Perspective 用于组织问题，KOSMOS 评估用于提醒独立验收的重要性。
