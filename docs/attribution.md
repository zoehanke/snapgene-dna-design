# 归属与许可证

2026-10-11。此文件管理代码、材料和AI贡献来源；官方规则由[要求核对](igem/official-requirements.md)管理。声明用途不等于已确认许可、贡献或完成官方表单。

原项目代码已有 MIT LICENSE，版权主体目前写作 iGEM Team。请 Tianjin 团队确认作者及雇佣/学校贡献权属，再决定是否补署名；本轮不替第三方重新授权。

| 内容 | 来源/许可证 | 当前处理 |
|---|---|---|
| 原项目代码、Toolkit及本轮修复 | 仓库 LICENSE / MIT | 保留底座来源、历史与版权文字，团队确认贡献归属；不因领域特化声称新训练模型 |
| Azimuth 转换代码/模型 | third_party/azimuth/LICENSE，BSD-3-Clause | 保留notice、上游manifest |
| DeepCpf1权重 | CRISPRseek来源，Artistic-2.0 | 保留对应license和来源 |
| Primer3/primer3-py | GPL-2.0-or-later | 用户环境安装；通过外部进程调用，不把它重新标MIT |
| SnapGene集合及派生真实fixtures | SnapGene条款 | 不进redistributable；哈希检查只识别已知集合 |
| tests/data/pBP-eGFP.gb | Polizzi实验室/EcoFlex/Addgene来源 | 外部来源许可待核实，不进redistributable |
| docs/archive/plans/assets参考图 | 用户提供设计参考 | 发布权属待确认，不进redistributable |
| 本轮合成反例/性能数据 | 自行生成 | 保留脚本、种子和范围，无湿实验声明 |
| Genome Revival实验原件和私有DNA | 团队提供，本轮仅在本机审查 | 不入源码或再分发包；公开案例需单独审定 |
| 公共参考基因组 | 原数据库、accession及版本 | 来源/版本与实际株系身份分开；保留原数据库条款，不重新标MIT |

## AI使用披露

| 已有记录 | 实际用途 | 核查及边界 |
|---|---|---|
| OpenAI Codex | 代码实施、审查、测试设计、资料核对及文稿组织/翻译 | 本轮宿主实际model id未取得，子代理继承宿主且无override；不按astra等昵称推断；程序检查不称为专家或人类独立背书 |
| DeepSeek Flash，maximum reasoning | 官方DSH隔离profile的Core测试及单轮Toolkit给定区域Identity试用 | 自然请求、实际工具、原始日志与产物保留；Toolkit117个公开调用、13.76分钟，独立验收与旧Core结果分开，零退出不等于任务完成 |
| 既有其他AI模型/工具 | 仅在有实际会话或团队记录时填写 | 未核实模型和用途不能据讨论记录自动列为已使用 |

本轮未训练或微调新语言模型；闭源宿主的训练数据不由团队持有，未知部分如实披露。Toolkit运行可以使用宿主模型，但其DNA计算复用确定性Core；不把模型生成说明当原始实验事实或私有思维证明。

本轮宿主主候选526/250 bp及四份程序结果独立核对成立，额外两报告未绑定且有确定文字错误，旧Tm理由保留复核。宿主JSON原请求是摘要，逐字原对话另在真实记录；不声称Trace自动获得完整宿主过程或思想。一次已知项目pilot不是heldout，也不证明少脚本、省token或通用成功率提高。

Wiki稿依据团队提供的研究目标与核实的实现/计算记录整理。项目科学内容、参考、代码和结果须由队员理解并审定，不能把AI写出的新科学故事仅经润色就称团队原工作。AI生成或修改的图像不能冒充实验/计算证据；软件图用实际结构或文档化计算生成，截图来自真实运行。

正式Attributions需负责人核实人员、外部帮助、AI用途和人的核查。AI使用填独立栏，不伪装外部人类贡献者。表单2026在团队页直接展示，不要求Wiki iframe。个人账号操作和最终提交由负责人亲自完成，不由代理代提交。[规则](https://teams.igem.org/go/deliverables/attributions/requirements)、[AI政策](https://igem.org/legal?tab=ai-policy)

完整文件与来源见[THIRD_PARTY_NOTICE](../snapgene-dna-design/THIRD_PARTY_NOTICE.md)及 third_party/UPSTREAM-MANIFEST.json。MIT 是 OSI 批准许可，但已有 MIT 文本不是所有外部素材均有授权的证明。许可证问题未解决前，不能仅凭包名宣称任意用途均可分发。

软件源码的MIT与Wiki的CC-BY4.0分开；官方软件模板Apache-2.0不自动改变已有代码许可。候选包须携带底座版本及必要notice，最终公开内容由团队审定。
