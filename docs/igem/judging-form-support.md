# Judging Form 支撑材料

2026-10-11。供负责人审定后亲自填写，不代操作官方账号。规则只在[官方核对](official-requirements.md)维护。

**Wiki：** `https://2026.igem.wiki/tianjin/software`。**专属软件：** [igem-tianjin2026](https://gitlab.igem.org/2026/software/tianjin/igem-tianjin2026)。URL及团队关联已核实，当前源码尚未上传，表单保存及自荐状态未核实。

## 核心表述

以下英文根据团队提出的研究目标整理，需团队审定，不代表实验已经成功：

> Genome Revival Toolkit supports the molecular work behind our yeast-genome research: preparing defined genetic constructs, distinguishing supplied reference regions and organizing research observations with explicit controls and limits. One Skill combines three focused Kits with the existing DNA Design Core and a shared Evidence Trace. The host or researcher supplies scientific choices; the program computes supported sequence operations and records their actual inputs, checks and outputs. It does not simulate cellular revival, infer complete genome elimination from one locus or certify biosafety. Computational results, model-assisted task outcomes and experimental observations are reported separately.

## 六项评审对应证据

| 维度 | 可以说明什么 | 本轮需要绑定的证据 |
|---|---|---|
| BS1 标准 | 复用GenBank/FASTA/SnapGene及带注释的分子；不宣称已支持SBOL | 实际输入/保存回读；[兼容边界](standards-compatibility.md) |
| BS2 验证 | 独立正反例、真实材料计算、正常宿主和独立包分别验 | 冻结提交/包、运行日志、实际产物及检查；旧Core成绩不能替代Toolkit验证 |
| BS3 复用价值 | 位点供体、区域鉴别和有对照的记录整理可用于相似任务 | 明确支持范围与可复现案例；陌生用户价值尚未核实 |
| BS4 集成 | 一个入口调用同版Core、实际Primer3与公共交付/Trace | 可运行Quick Start及底座来源，不是新模型训练 |
| BS5 易用 | 按任务选Kit，默认报告显示目标、结果、过程、检查与文件 | 正常宿主实际交付、报告链接；真人理解和效率尚未核实 |
| BS6 维护 | 单一Core来源、轻量Context、公开接口、依赖和限制 | 包清单、安装复现、架构、测试及许可；正式GitLab CI待部署核查 |

完整英文正文、素材和待冻结声明见[Wiki稿](software-wiki-draft.md)。现行实施证据由[Toolkit计划](../development-plans/genome-revival-toolkit-v0.1.md)管理，不在表单材料另维护成绩表。

本轮已有受限计算证据：实际CHR1材料经公共Construct入口交付1802 bp供体与8条完整oligo，三档DNA/注释/订单/质量及四scope一致；给定Sc/SY14区域的开发者辅助候选预测650/374 bp且完整质量核对成立，原全区间质量失败保留；无原始实验表的Evidence结果为incomplete/NOT_TESTED。以上不是宿主自主成功或湿实验结果。全量、冻结包及正常宿主验收仍待最终记录。

## 提交前必须确认

- 本轮实际版本、源码和受检包一致；仅使用该版本真实结果，不混合旧版成绩。
- 项目株系、实验角色和实验完成状态来自原记录，不能用PV宣传稿替代；未知身份与SY14 URA3位点如实保留。
- 学生、外部帮助、历史底座和AI用途归属准确；本轮没有新训练/微调权重。
- 官方软件 `main`、Wiki `/software` 和可复现证据可访问；负责人亲自填写并核对表单/自荐回执。

独立外部用户、专家复核及与本软件交付绑定的湿实验目前没有新增证据。不得写“其他团队已受益”“节省多少时间”“提高实验成功率”或“复活已验证”。
