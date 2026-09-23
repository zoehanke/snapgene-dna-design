# 格式与标准兼容

| 格式/约定 | 支持 | 导入/导出与实现 | 实证与限制 |
|---|---|---|---|
| GenBank | IMPLEMENTED | input_resolution、sg_common、snapgene_io；保留SeqFeature/qualifiers | Native/GB读回、复合位置/链向测试；错误源注释仍可能被正确拒绝 |
| FASTA | IMPLEMENTED | 单序列Core输入；多记录辅助工具需明确读取 | FASTA没有完整注释/拓扑，不能凭文件格式恢复缺失信息 |
| Native SnapGene .dna | IMPLEMENTED | sgffp写出，原生读取/富集引物元数据 | 二进制内部读回与真实桌面程序是不同证据；未知私有packet不承诺任意往返无损 |
| EMBL | LIMITED | 通用读取层可解析 | 并非每个正式任务入口都声明支持；未作为主交付格式 |
| CompoundLocation | IMPLEMENTED | Biopython提取、ConstructModel变换 | join/order、负链、原点、断裂结合区分别测；不排序修正错误源数据 |
| 坐标 | IMPLEMENTED | Core 0-based half-open；旧CLI部分1-based closed | 输出需带约定，不能交换语义 |
| SBOL | NOT IMPLEMENTED | 无SBOL import/export入口 | 不为奖项补一个假的converter；GB交换满足现有实际需求 |
| 全基因组标识/版本 | LIMITED | source IDs、文件SHA、明确context字段 | 文件版本不是生物学来源鉴定或accession真实性证明 |

公开规则BS1允许多种格式/标准证据，未要求为了参赛必须实现SBOL。具体判据来源见[官方核对](official-requirements.md)。测试入口：test_primer_io_repair、test_preparation_primer_locations、test_final_cds_validation、test_snapgene_compatibility、engineering回归。最终实测范围见[validation](../validation.md)。
