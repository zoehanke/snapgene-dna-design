# 执行材料补齐记录

2026-10-02 · v0.3。用途：负责人核查来源与准备状态，**不给执行AI**。本轮只补真实完整输入，没有修改DNA、设计参考引物或执行Skill试题。

## 取得了什么

| 题 | 原材料与完整长度 | 来源 |
|---|---|---|
| 4 | pRS416 4898 bp；pRS426 5726 bp | [pRS416官方文件](https://www.snapgene.com/local/fetch.php?set=yeast_plasmids&plasmid=pRS416)、[pRS426官方文件](https://www.snapgene.com/local/fetch.php?set=yeast_plasmids&plasmid=pRS426) |
| 4 | pYTK013/032/053/011/034/054，依次2371/2382/1900/2371/2376/1900 bp | [官方完整部件ZIP](https://media.addgene.org/cms/filer_public/4d/26/4d26f69c-1b8e-4473-8494-a7e993618112/ytk_genbank_files.zip) |
| 7 | 1M 6462 bp；pET28a-sfGFP 5975 bp | [完整viewer 237947](https://www.addgene.org/browse/sequence/237947/)、[完整viewer 169849](https://www.addgene.org/browse/sequence/169849/) |
| 8 | mCherry2-C1 4722 bp；DsRed参考225 aa | [完整viewer 310151](https://www.addgene.org/browse/sequence/310151/)、[UniProt Q9U6Y8](https://rest.uniprot.org/uniprotkb/Q9U6Y8.fasta) |
| 9 | 胞质探针8004 bp；基质探针8202 bp；pRS416 4898 bp | [胞质源](https://www.addgene.org/83238/sequences/)、[基质源](https://www.addgene.org/83240/sequences/)、上述骨架 |

版本、URL、原响应和文件/DNA哈希留在[原始归档](../../output/question-bank-20261002/raw/)及[来源记录](../../output/question-bank-20261002/provenance-t07-t09.md)。两份pRS保存原`.dna`再转GB，pRS416与[U03450.1](https://www.ncbi.nlm.nih.gov/nuccore/U03450.1)环形全序列一致。YTK直接取原ZIP成员，未重建部件。

Addgene完整viewer无需登录即提供显示数据；其广告GBK链接返回404。本轮原样提取公开显示的每个碱基，核对坐标连续、上下链互补、官方完整长度，并转换所有功能feature。完整原JSON保留；格式转换不表示作者原生GB已经取得，也没有访问登录接口。[转换核验](../../output/question-bank-20261002/viewer-conversion-t07-t09-t08.json)

## 不能隐藏的输入事实

- **第7题：**原1M有两处His6，TEV处实际为ENLYFQS。要求切后Gly加完整sfGFP，仍须执行者在设计时实现；准备者没有预改接口。sfGFP供体是负链。原标签端位文字矛盾保留在执行材料说明中。
- **第8题：**参考143/161/163对应实际母本148W/166I/168Q，原密码子TGG/ATC/CAG，质粒1-based坐标分别1093..1095、1147..1149、1153..1155。两个最优全局比对在这些位点一致。DsRed参考第163位自身是K；编号定义位置，Q指实际母本，不得偷改参考。对应关系属于检查者答案，执行包只给未编辑参考和编号规则。[映射核对](../../output/question-bank-20261002/raw/T08-reference-mapping.json)
- [原论文附表S1](https://journals.plos.org/plosone/article/file?type=supplementary&id=10.1371/journal.pone.0171257.s001)明确I161S/Q163E后再加W143L，解决正文一处I163E冲突。实际提供母本不冒称与作者实验库存完全相同，光谱表现不作DNA验收结论。
- **第9题：**原viewer只有骨架和调控feature，缺具名探针CDS。已核查正链完整ORF分别3210..4625与3204..4823，含终止、471/539 aa。执行材料提供功能背景及输入边界，不伪造原注释，也不把两份来源说成只差Su9。

## 第10题为什么仍不发

补查[原作者学位论文](https://openscience.ub.uni-mainz.de/bitstreams/06e45195-a2ff-481c-94e6-a15d3667ae8d/download)，只有构建说明，没有精确完整pKBJ002.1供体。论文与[材料页](https://www.addgene.org/173453/)的pRS背景文字还存在差异，不能据文字拼造输入。原PDF及对应页已归档；未从最终成品反切片段充当原供体。

## 核验与交付范围

九题共41份完整GenBank，原文件哈希未变；匿名副本DNA逐碱基相同、拓扑相同、全部feature几何和提取序列相同。编号参考未编辑。执行包无参考成品、参考引物、作者/DOI、原材料编号、网页链接；必要背景已放自然请求，inventory留在检查者历史材料中。[材料核验记录](../../output/question-bank-20261002/materials-v0.3/validation.json)

第4、7、9题输入现已齐，但没有新增唯一最终序列/引物金标准；人工仍按源文件、目标结构、实际反应及继承关系独立检查。没有把某个构建路线锁成唯一答案。没有运行这些新增题，也没有声称Skill或湿实验通过。
