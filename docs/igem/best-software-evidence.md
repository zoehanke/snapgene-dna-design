# Best Software 证据

队伍：Tianjin #6404；项目背景：Nezha yeast genome revival；范围：本软件为通用DNA设计工具，并非基因组功能复活实验本身。规则和资格条件见[官方核对](official-requirements.md)，尚未满足全部提交条件。

后续行动与建议分工见[工作任务表](best-software-task-table.md)。本页的历史工程证据与2026-10首轮真实宿主测试分开，不能据工程套件通过宣称用户任务已经可用。

| 维度 | 本项目贡献与实现 | 支撑证据 | 强项 / 弱项与剩余事项 |
|---|---|---|---|
| BS1 | SeqRecord、GB/FASTA/Native；core/io、models、tools/snapgene_io | test_primer_io_repair、test_preparation_primer_locations、test_final_feature_restoration；[兼容表](standards-compatibility.md) | 注释和坐标可测；无SBOL，不虚构支持 |
| BS2 | 实际制备、保存文件核验、负例门限与Trace旁路 | 新engineering_*测试；[validation](../testing.md)、[benchmark](../testing.md)、结果JSON | 独立正反例优于测试总数；缺本系统对应的湿实验和独立专家评价 |
| BS3 | 不局限酵母；支持多种克隆/验证任务及可复用工具 | Recipes、Pipeline、[user-guide](../../snapgene-dna-design/docs/user-guide.md) | 接口可复用；无外部队伍采用与节省时间数据 |
| BS4 | Python/CLI、Primer3、格式交换；可选本地预测与off-target | [integration](../architecture.md)、后端测试与check_env | Cas-OFFinder v2/v3合成参考及模型参考输出已实跑；未证明任意完整基因组运行 |
| BS5 | 可运行快速开始、明确错误、离线可读Trace | [quick-start](../../snapgene-dna-design/docs/quick-start.md)、浏览器记录、故障测试 | 修复依据实际反馈；缺独立新用户理解/完成任务证据 |
| BS6 | 模块边界、共享记录、测试、版本、许可与发布文档 | [architecture](../architecture.md)、[developer-guide](../developer-guide.md)、[reproducibility](../testing.md) | 有扩展契约；旧入口多，持续维护仍需要负责人掌握 |

本周期修复证据以[最终工程报告](../archive/reviews/final-remediation-report.md)为准。准确的主张是“已测范围内的计算与追溯能力”，不是“任何设计都正确”“AI已完全可解释”或“获得官方安全认证”。
