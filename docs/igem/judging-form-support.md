# Judging Form 支撑材料

供队伍改写并提交，未代填官方表单。标准Wiki页面：`https://2026.igem.wiki/tianjin/software`；软件GitLab：**NEEDS WEBSITE/DASHBOARD ACTION**，确切URL待确认。

## VERIFIED CLAIMS（范围受证据限制）

软件把宿主提出的设计参数转为实际序列操作、注释文件和计算检查。Recipe/Pipeline支持多步材料传递；Native/GB互操作和引物位置有独立反例测试。Evidence Trace保存可观察事实与声明，固定生成可读报告；不能证明宿主全部内部活动。工程周期修复了真实错误放行、注释/状态丢失与报告关联问题，细节和最终结果见[final report](../archive/reviews/final-remediation-report.md)。

BS1–BS6证据索引：[best-software-evidence](best-software-evidence.md)、[traceability](traceability-matrix.md)。合成benchmark测量的是运行成本，不是实验成功率或用户效率。

可供团队据实改写的英文核心段落：

> SnapGene DNA Design turns explicit design requests and supplied sequence records into inspectable computational constructs through reusable recipes and composable tools. The implementation computes preparation intermediates where the selected route supports them, preserves annotations and full primer information, and checks saved artifacts before formal delivery. Evidence Trace separately records observed execution and sourced public explanations. Our validation combines independent positive and negative sequence cases, real external-tool integrations and extracted-package tests. Computational validation, user effectiveness and experimental outcomes are reported separately.

提交前从最终报告填写最终测试、覆盖与bench数据；选两项与本团队实际需求对应的结果展开，不堆测试总数。标准互操作引用[兼容表](standards-compatibility.md)，外部集成引用[实际接口](../architecture.md)，维护和复现引用[开发指南](../developer-guide.md)。任何“其他队伍已受益”“节省多少时间”“提高安全性”的句子都需要外部记录支持。

## NEEDS HUMAN INPUT

队员贡献与外部帮助归属；对源文件/图片/代码的许可确认；最终表述、项目贡献定位及奖项自荐。

## NEEDS EXTERNAL EVIDENCE

独立用户测试、专家复核、与本系统产物绑定的湿实验、可选硬件环境。[采集要求](external-evidence-needed.md)

## NEEDS WEBSITE/DASHBOARD ACTION

官方软件仓库、Wiki发布、Judging/Attributions/Safety相关表单及截止前状态回执。不要把本文件或本地测试当作官方已接收。
