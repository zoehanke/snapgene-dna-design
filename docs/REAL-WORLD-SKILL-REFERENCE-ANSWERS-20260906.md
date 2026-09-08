# SnapGene skill 真实任务参考答案

日期：2026-09-06。对应 `REAL-WORLD-SKILL-PAPER-EXAM-20260906.md`。原始改编题保留在旧稿，不能用本版答案冒充完成原来的所有扩展需求。

## 你需要知道的内容

优先采用作者公开的完整成品；取不到完整成品时，区分原文明确写出的变化与本次独立推导。参考构建没有调用被测 skill 的计算或验证函数。

**三题有完整外部成品可比较：题 1、4、5。题 6 有原文引物和确切编辑要求，但完整编辑产物由本次推导。题 2、3 的完整构建属于改编，不能标成作者实验结果。**

参考答案用于检验后续交付，当前不是 skill 通过测试的报告。还没有执行代理盲测，也没有桌面 SnapGene 或湿实验验证。

## 题 1：URA3 整合受体

**外部成品：pYTK096，Addgene #65203，5,283 bp，环形。** 作者 YTK 包同时提供七份完整源质粒与成品，原始字节已经保存。[论文](https://doi.org/10.1021/sb500366v)，[成品记录](https://www.addgene.org/65203/)。

答案结构：URA3 两侧同源区及条形码、ConS/GFP dropout/ConE、完整 URA3 筛选盒、KanR、ColE1。受体保留用于后续操作的 BsaI/BsmBI 位点；不能错误删除 GFP dropout 或这些位点。

独立参考路线采用七模板 PCR/Gibson，14 条引物、七份实际扩增产物齐全。连接后与作者序列按环形起点对齐，逐碱基相同。NotI 预测为 3,520 + 1,763 bp，BsaI 为 1,030 + 4,253 bp。

完整答案与引物：`output/reference-answers-20260906/q1/README.md`。成品、输入、引物表、标注副本、中间体及独立重放均在该目录。制备路线由本次设计，作者成品提供外部标准。

## 题 2：EcoFlex 三色分层组装

本题的三组启动子、报告基因和终止子组合没有取得作者公开的完整最终质粒。文献提供工具包规则和部件资料，完整组合需要独立推导，不能称作论文原始成品。[Moore et al., 2016](https://doi.org/10.1021/acssynbio.6b00031)，[EcoFlex 官方材料](https://www.addgene.org/kits/freemont-ecoflex-moclo/)。

必须保留的目标顺序：J23100/B0034/eGFP/B0015，J23108/B0034/mCherry/L3S2P21，J23114/B0034/eCFP/L3S1P51。完整源文件中的切位和真实受体末端决定能否组装；补充材料中的理想接头不能覆盖实际输入序列。

公共受体记录的实际 BsmBI 末端为 ATCT/TTAG，而三盒链为 ATCT/GAAG。参考路线先用反向 PCR 将受体右侧 TTAG 改为 GAAG，明确命名为 `reference_pTU2_3TU`，然后分层组装。只允许这两处碱基改变，不能直接拿补充材料的理想序列覆盖输入。

公共 registry 的 `pTU2-B-RFP.gb` 与 `pTU2-b-RFP.gb` 两份 ZIP 成员序列相同，元数据和文件哈希不同；Windows 解压会使两个路径冲突。因此来源身份以 ZIP 内精确成员名及哈希记录。Level 1 骨架为 AmpR，Level 2 为 CmR。具体产物和材料处理结论见 [题 2、3 完整答案](../output/reference-answers-20260906/q2-q3/README.md)。

三个 Level 1 成品分别为 **3,003、2,935、2,902 bp**，Level 2 为 **4,674 bp**。考官另用 Biopython 的实际切位，从完整来源记录重建全部产物，序列与参考文件相同；Level 2 中三个完整报告 CDS 和 660 bp 的 cat 筛选 CDS 均保留。

## 题 3：GFP 变体及 His6-TEV 表达

论文支持 GFP 突变身份；本题的 EcoFlex 编码背景、pET-28a(+) 与 His6-TEV 组合没有取得作者完整成品，所以三份表达载体是独立参考设计。[Heim and Tsien, 1996](https://pubmed.ncbi.nlm.nih.gov/8673464/)。

答案应包含 WT、Y66H、Y66H/Y145F 三个分支，统一融合背景；残基编号先与源蛋白对齐。GFP 前有 N 端 His6 和 TEV，末端有终止密码子，无额外 T7 标签或翻译出的 C 端 His。为实际酶切所需的同义变化必须通过制备步骤引入，并记录在所有分支中。

真实路线需要从完整模板和完整引物推导每份 PCR，再计算插入与骨架的真实双酶切末端。直接替换密码子或删除两个酶识别序列，不是这道题的参考制备路线。

参考路线先经反向 PCR 与环化引入共同 P56 同义变化，再依次分支引入 Y66H、Y145F。三轮模板和产物均为 2,808 bp，完整引物与真实扩增推导已记录。克隆 PCR 为融合标签加入所需序列，经 NcoI/XhoI 双酶切连接至 pET-28a(+)。

三份参考成品均为 **5,995 bp**。完整融合 CDS 762 bp，编码 `MG-His6-ENLYFQG-完整源 GFP`，253 aa 后接 stop；NcoI/XhoI 预测条带为 764 + 5,231 bp。原 C 端 His 编码 DNA 位于 stop 之后，不被翻译；不能声称双酶切还额外删除了那段 DNA。

源 pBP-eGFP 的第 64/65 位实际为 F/G，与常见 EGFP 的 L/T 不同。此处 WT 仅指源文件，不将变体的实验性能套用到另一种 GFP 背景。具体引物和产物见 `q2-q3/README.md`。

另一份独立计算从完整模板和实际引物重建三轮突变 PCR、三份克隆 PCR，并对完整扩增产物计算 NcoI/XhoI 切位，三份最终序列均与参考文件逐碱基相同。详见 [独立复核记录](../output/reference-answers-20260906/q5/Q3-independent-check.md)。

## 题 4：mCherry-mNeonGreen 计时器

**外部成品：pKBJ006，Addgene #173453，5,608 bp，环形。** 作者记录明确给出从 pMaM17 双酶切骨架与 pKBJ002.1 的 PCR 插入进行 Gibson 的路线。[作者记录](https://www.addgene.org/173453/)，[Fung et al., 2022](https://doi.org/10.1007/978-1-0716-1732-8_6)。

已取得完整 pMaM17 骨架与 pKBJ006 成品。pMaM17 为 5,614 bp，SalI/BamHI 切出 1,464 bp，保留骨架 4,150 bp；成品对应区间为 1,458 bp。

成品的 mCherry 为 161..868，linker 为 869..904，mNeonGreen 本体为 905..1612，BamHI 编码的 GS 尾部为 1613..1618，终止密码子为 1619..1621。整体融合为 486 aa 后接 stop。kanMX、AmpR 与复制起点必须保留。

Addgene verified 与 depositor 的两份成品同长，但骨架有三处 SNP；对应 pMaM17 也有同样的版本差异。发题时固定同一版本，不能把不同来源版本的差别误报成 skill 修改。

**原文 pKBJ002.1 完整供体尚未取得，题 4 暂缓盲测。** 成品可作金标准，但从成品反切出“插入片段”只能核对结构，不能证明源模板 PCR 成立。另取公开 mNeonGreen `KC295282.1` 比较，蛋白相同，去 stop 的 DNA 仅 551/708 位一致，不能冒充同序列供体。详细记录见 [题 4 完整答案](../output/reference-answers-20260906/q4/README.md)。原 HTB2 整合、hphMX4 替换及单标签对照不属于这份论文答案。

## 题 5：VAMSyB 四报告双表达质粒

**外部成品：pTS1042，Addgene #169620，7,895 bp，环形。** 输入 pVH1001、pTS1039、pTS1040 与最终质粒的完整公开序列均已保存。[论文](https://doi.org/10.1016/j.ymben.2021.04.003)，[成品记录](https://www.addgene.org/169620/)。

答案结构：A1 为 PhCMV→SEAP→P2A→iRFP670→poly(A)；A2 为 PmPGK1→Igκ 信号→Nluc→P2A→mTagBFP2→poly(A)。A3 空接收背景及细菌骨架保留。

独立三模板 PCR/Gibson 路线已补齐：扩增产物为 1,042、3,600、3,313 bp，包含跨圆形原点的来源片段。按实际引物与重叠组装，得到与公开成品逐碱基相同的 7,895 bp 序列。Addgene 公开 CMV-F/BGH-rev 引物在前体及成品均对应同一 2,802 bp PCR 产物。

GenBank 注释转换使用 1-based inclusive 到 0-based half-open 的正确映射，负链跨原点特征按生物学顺序保存。P2A 57 bp、Nluc 513 bp、iRFP670 930 bp、mTagBFP2 708 bp、AmpR 861 bp；直接翻译检查，不靠换读框掩盖坐标错误。

整条融合翻译另行核对：A1 为 867 aa，A2 为 477 aa，均保留作者构建中报告蛋白之后的 `ASGSTGV` 克隆尾部再接 stop。完整 ORF 注释版为 `q5/pTS1042_complete_ORFs.gb`。

完整答案与六条独立制备引物：`output/reference-answers-20260906/q5/README.md`。制备引物由本次设计，成品序列来自公开记录。

## 题 6：CDC48 R105G 与同义 PAM 修改

原文直接给出 guide 载体的两条 PCR 引物、R105G 的 AGG→GGA，以及阻止原 PAM 识别的 TGG→TCG。[Hu et al., 2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC5868978/)。

从下载的 11,240 bp pML104 和原文引物，独立推导得到 11,258 bp guide 质粒。表达方向上的 guide 为 `TAACAATTTACGTATTAGGC`。

在固定 CDC48 参考中，对应 c.313A>G、c.315G>A、c.318G>C，整条蛋白只有 R105G；PAM 修改保持 Leu106。供体为 90 bp，具体两端位置由本次独立选定，未冒充原文图中的完整寡核苷酸。野生型与编辑型验证 PCR 都是 345 bp，需要测序判别。

局部参考使用 S288C `NC_001136.10:235657-239164`，而论文宿主为 BY4741。此答案证明指定参考上的编辑推导，不证明作者菌株全基因组或全基因组脱靶。辅助质粒没有被混入编辑后基因组记录。

完整答案、原文引物和独立供体：`output/reference-answers-20260906/q6/README.md`。

## 使用这些答案

题 1、4、5 的完整公开成品只给考官。执行者只收到本题需求和完整源文件。引物顺序、额外同义密码子及合理克隆边界可以存在多种解；按需求和实际反应判断，不能要求执行者猜中某一份参考序列 hash。

所有来源和结果目录位于 `output/reference-answers-20260906/`。计算脚本只用于准备独立参考，没有写入项目业务模块。后续测试以交付的真实引物、真实中间体及最终 `.dna` 为检查对象。

## 交付状态

| 题目 | 答案依据 | 当前能用于什么 |
|---|---|---|
| [1：YTK](../output/reference-answers-20260906/q1/README.md) | 作者完整源文件和成品，独立七模板 PCR 路线 | 可发完整输入，检验制备路线与外部成品 |
| [2：EcoFlex](../output/reference-answers-20260906/q2-q3/README.md) | 公开部件及接头规则，改编构建 | 可发完整输入，必须处理实际受体不兼容 |
| [3：GFP 变体](../output/reference-answers-20260906/q2-q3/README.md) | 文献突变身份，独立表达载体设计 | 可发完整输入，检验突变、扩增、双酶切和融合翻译 |
| [4：计时器](../output/reference-answers-20260906/q4/README.md) | 作者完整成品和骨架，原始供体缺失 | 成品结构参照可用，制备路线盲测暂缓 |
| [5：VAMSyB](../output/reference-answers-20260906/q5/README.md) | 作者完整前体与成品，独立三模板 PCR 路线 | 可发完整输入，检验跨原点片段及两个完整融合 ORF |
| [6：CDC48](../output/reference-answers-20260906/q6/README.md) | 原文引物和编辑，固定 RefSeq 上独立推导 | 可检验给定局部参考上的载体、供体与编辑产物 |

参考包包含完整 GenBank/FASTA、来源记录、实际引物和计算重放。它是考官材料，不能整体交给执行代理。五题具备发题材料不等于五题 skill 已通过；最终 `.dna` 的桌面检查仍属于后续真实执行。
