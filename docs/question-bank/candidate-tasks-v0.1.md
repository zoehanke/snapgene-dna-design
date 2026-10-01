# 真实 DNA 设计候选题库

当前材料状态见[题库说明](README.md)：第1至9题可发，第10题不发。以下为保留的原选题记录。

2026-10-01 · v0.1 · 供负责人选题，尚未冻结、尚未开展本轮测试。

**历史选题稿，现仅供检查者查材料与来源。**减泄漏题面见[执行版v0.2](executor-tasks-v0.2.md)，验收与原名称映射见[检查者版v0.2](reviewer-notes-v0.2.md)。下文保留旧稿，不整份发给执行AI。

这份文档先帮助你判断：**任务是否像真实研究需求，材料是否能准备齐，产物是否能独立检查。**正文中的引用块是可复制给测试 AI 的请求。材料准备细节另见[来源与准备记录](source-and-review-notes-v0.1.md)，不需要先读工程文档。

论文和材料是真实来源；题面中新增的组合、对照或迁移要求会明确写为改编。旧资料已有的参考结果不等于当前 Skill 已通过这些题。

材料链接直接列在每题下：**材料页**用于查身份与说明，**完整序列入口**用于取得文件，**本地文件**可直接打开已归档记录。Addgene的部分序列下载需要登录；本地链接不表示材料已完成发题验收。

## 先看这张表

| 题号 | 任务 | 工作量 | 主要观察 | 材料现状 |
|---|---|---|---|---|
| [1](#第1题现成计时器先判断需不需要重新设计) | 现成计时器是否需要重做 | 小 | 能否准确判断材料可复用 | 已有归档，需选定版本 |
| [2](#第2题用七支源质粒构建酵母整合受体) | 七模板构建酵母整合受体 | 大 | 多来源制备、完整骨架、后续接口 | 已有归档 |
| [3](#第3题三色报告质粒分两层组装) | 三色报告分层组装 | 大 | 中间体传递、不同层级的真实接头 | 已有归档 |
| [4](#第4题同一双报告做低拷贝与高拷贝对照) | 双报告加复制子对照 | 大 | 成对设计、后续改造、限定差异 | 部分材料归档，骨架待整理 |
| [5](#第5题把四个报告蛋白放进同一非病毒质粒) | 哺乳动物四报告双表达 | 大 | 长融合、分泌信号、重复调控区 | 已有归档 |
| [6](#第6题酵母点突变同时交付载体供体和验证设计) | 酵母点突变及配套验证 | 大 | guide、修复供体、等位基因分别正确 | 已有归档 |
| [7](#第7题可切除的-mbp-标签融合) | MBP 标签融合与切除边界 | 中到大 | 完整表达阅读框、标签去留 | 来源已定位，待取完整序列 |
| [8](#第8题连续两轮红色荧光蛋白突变) | 连续两轮荧光蛋白突变 | 中到大 | 残基编号、实际中间体、累计变化 | 来源已定位，待比对母本 |
| [9](#第9题胞质和线粒体探针迁移到新筛选背景) | 两种定位探针迁移骨架 | 大 | 材料取舍、成对迁移、来源保真 | 来源已定位，待取完整序列 |
| [10](#第10题替换荧光计时器中的一个模块) | 计时器模块替换 | 中到大 | 完整融合与真实模板来源 | 原论文关键供体缺失，暂不发题 |

**建议先审 2、3、5、7、8、9：**复杂度和关注点不同。第1题作为基本使用题，检验是否无必要地重做设计。第4题适合测试过程中追加需求。第10题保留为资料补齐后的候选。

## 如何使用

现在只选题和调整需求，不给每题强行算一个总分。正式测试时：

1. 每题只给 AI 自然请求、完整源材料和实际实验背景。由 AI 选择路线、编写参数、调用已安装 Skill。
2. 对新构建，通常要求最终 `.dna/.gb`、必要中间体、完整引物表、源文件副本上的引物标注和可执行的制备说明。检查任务按实际需求交付，不强制新建构建。
3. 材料未齐、真正不可实现、软件失败和人工救场分别记录。拒绝一个有效目标不能自动算成功；指出真实材料问题也不能自动算软件失败。
4. 完整答案和检查者材料不交给执行 AI。接受满足要求的不同正确路线，不要求猜中某一套引物。

这份候选已经向开发者公开，适合作为公开回归题。以后真正的保留验收题应另行准备，不能把这些已看过的题称为开发者未见过的盲题。

## 第1题：现成计时器，先判断需不需要重新设计

**研究目的：**准备酵母蛋白更新实验的标签模板，先避免重复构建手里已经有的模块。

**给 AI 的任务：**

> 我已经有 pFA6a-mCherry-mNeonGreen-kanMX 的实体质粒，附上完整文件。后续想把 mCherry 和 mNeonGreen 串联的标签加到酵母蛋白末端。这次先核查：这支质粒是否已经含有所需的完整标签模块和筛选盒，能否作为后续制备模板？如果不需要重新设计，请直接说明已有材料可以怎样使用。若还缺少目标基因信息，指出具体缺什么，不要先重做同样的标签。

**材料：**完整 pKBJ006，Addgene #173453。本地已有网页序列与转换的 GenBank，正式发题须选定同一来源版本。

- pKBJ006：[材料页](https://www.addgene.org/173453/) · [完整序列入口](https://www.addgene.org/173453/sequences/) · [本地 GenBank](D:/codex_project/github/snapgene-dna-design/output/reference-answers-20260906/q4/pKBJ006_addgene_verified.gb)。本地文件由公开网页序列及注释转换。

**为什么值得测：**用户问的是材料判断。软件应分清标签模板、完整表达质粒和基因组整合供体，不能把它们混为一谈。

**出处与性质：**材料页明确记载该质粒含串联计时器；核查需求是本题改编。[原材料页](https://www.addgene.org/173453/)、[Fung 等，2022](https://doi.org/10.1007/978-1-0716-1732-8_6)。

## 第2题：用七支源质粒构建酵母整合受体

**研究目的：**从实验室现有 YTK 部件制备一个可供后续换入表达盒的 URA3 整合受体。

**给 AI 的任务：**

> 我手里只有 pYTK008、pYTK047、pYTK073、pYTK074、pYTK086、pYTK090 和 pYTK092 七支完整源质粒。想构建一个 URA3 整合受体，保留两侧同源区、工具包连接件、GFP 占位模块、完整筛选盒以及细菌复制和筛选功能。后续还要换入表达盒，所以相关组装接口要能继续使用。请用这些现有模板完成设计，给我实际制备路线、全部需要的引物、中间体和最终质粒，并设计能检查结构的验证方案。

**材料：**七份完整源 GenBank。只发源质粒，不发事先扩增好的片段。作者公开成品 pYTK096 留给检查者作参照。

- 工具包：[官方材料页](https://www.addgene.org/kits/moclo-ytk/) · [官方完整 GenBank ZIP](https://media.addgene.org/cms/filer_public/4d/26/4d26f69c-1b8e-4473-8494-a7e993618112/ytk_genbank_files.zip) · [本地 ZIP](D:/codex_project/github/snapgene-dna-design/output/realistic-exam-sources-20260906/ytk_genbank_files.zip)。
- 七份本地原始输入：[pYTK008](D:/codex_project/github/snapgene-dna-design/output/reference-answers-20260906/q1/inputs/pYTK008.gb)、[pYTK047](D:/codex_project/github/snapgene-dna-design/output/reference-answers-20260906/q1/inputs/pYTK047.gb)、[pYTK073](D:/codex_project/github/snapgene-dna-design/output/reference-answers-20260906/q1/inputs/pYTK073.gb)、[pYTK074](D:/codex_project/github/snapgene-dna-design/output/reference-answers-20260906/q1/inputs/pYTK074.gb)、[pYTK086](D:/codex_project/github/snapgene-dna-design/output/reference-answers-20260906/q1/inputs/pYTK086.gb)、[pYTK090](D:/codex_project/github/snapgene-dna-design/output/reference-answers-20260906/q1/inputs/pYTK090.gb)、[pYTK092](D:/codex_project/github/snapgene-dna-design/output/reference-answers-20260906/q1/inputs/pYTK092.gb)。

**为什么值得测：**一次包含多个来源、骨架制备、占位模块和后续接口。只拼出目标序列、没有真实制备链，不能算完成。

**出处与性质：**目标对应作者公开整合受体；制备路线由测试 AI 自选。[Lee 等，2015](https://doi.org/10.1021/sb500366v)、[YTK 材料与完整 GenBank 包](https://www.addgene.org/kits/moclo-ytk/)。

## 第3题：三色报告质粒，分两层组装

**研究目的：**准备含三个独立报告表达盒的细菌质粒，为后续比较表达提供材料。

**给 AI 的任务：**

> 我有 EcoFlex 工具包的单部件质粒，想把三个表达盒放进同一个质粒：J23100-B0034-eGFP-B0015，J23108-B0034-mCherry-L3S2P21，J23114-B0034-eCFP-L3S1P51，顺序照此。请按 EcoFlex 自身的分层规则，先制备三个单表达盒，再组装多表达盒质粒。各层受体从提供的材料里选择。如果真实序列或末端不兼容，说明如何用现有材料处理，并留下相应中间体；不要直接把源文件改成库存。最终给我各层质粒和验证方案。

**材料：**EcoFlex 完整源质粒与其工具包说明。第一层是单个表达盒，第二层是多个表达盒的组合，不混用其他工具包的接口标准。

- EcoFlex：[官方材料与使用说明](https://www.addgene.org/kits/freemont-ecoflex-moclo/) · [官方完整 GenBank ZIP](https://media.addgene.org/cms/filer_public/1a/00/1a00a9f1-608f-453a-937a-7f46cf872dfc/ecoflex-kit-genbank-files.zip) · [本地 ZIP](D:/codex_project/github/snapgene-dna-design/output/realistic-exam-sources-20260906/ecoflex-kit-genbank-files.zip)。
- 从ZIP准备三种启动子、B0034、三个报告基因、三个终止子及各层受体；最终受体选择仍由执行者根据真实文件判断。

**为什么值得测：**同一任务经过多级反应，后一级必须用前一级的真实产物。还要核对文件中的实际切位，不能只根据部件名称推断。

**出处与性质：**工具包及接口规则来自论文；上述三盒组合为改编，没有宣称作者已做过这个完整成品。[Moore 等，2016](https://doi.org/10.1021/acssynbio.6b00031)、[EcoFlex 官方资料](https://www.addgene.org/kits/freemont-ecoflex-moclo/)。

## 第4题：同一双报告，做低拷贝与高拷贝对照

**研究目的：**比较同一表达设计在不同复制子背景下的表现。复制子是质粒在酵母中复制、维持的相关区域。

**给 AI 的任务，第一轮：**

> 我在酿酒酵母中做双报告实验，宿主支持 URA3 筛选。手里有 pRS416、pRS426 和给定的 YTK 供体。先在 pRS416 中加入 pTEF1-mTurquoise2-tADH1 和 pPGK1-mRuby2-tPGK1 两个同向表达盒，保留原有筛选和细菌骨架。请从完整模板设计制备与组装，交付第一版质粒及引物。

**第一版形成后，用户再说：**

> 现在用你刚完成的第一版作实际模板，做一支 2μ 复制子背景的配对质粒，复制子来自我提供的 pRS426。两个表达盒、URA3 和其他骨架保持相同；列出实际改动，并给能区分两版的验证方案。

**材料：**pRS416、pRS426；YTK 的 pYTK013、011、032、034、053、054。正式发题先冻结所有文件版本。第二轮的输入必须是第一轮交付的真实文件。

- pRS416：[材料页与 `.dna` 下载入口](https://www.snapgene.com/plasmids/yeast_plasmids/pRS416) · [GenBank U03450](https://www.ncbi.nlm.nih.gov/nuccore/U03450)。
- pRS426：[材料页与 `.dna` 下载入口](https://www.snapgene.com/plasmids/yeast_plasmids/pRS426)。
- 六份YTK供体：[官方完整 GenBank ZIP](https://media.addgene.org/cms/filer_public/4d/26/4d26f69c-1b8e-4473-8494-a7e993618112/ytk_genbank_files.zip)，按 pYTK013、pYTK011、pYTK032、pYTK034、pYTK053、pYTK054 的完整文件提取。

**为什么值得测：**既检验复杂构建，也检验一次真实用户追加要求；不能把两版互不关联地从头拼出来，或漏掉额外骨架差异。

**出处与性质：**pRS416 是含 URA3 的着丝粒型载体，pRS426 是含 URA3 的游离型载体；双报告及复制子对照为改编需求。[pRS416](https://www.snapgene.com/plasmids/yeast_plasmids/pRS416)、[pRS426](https://www.snapgene.com/plasmids/yeast_plasmids/pRS426)、[YTK](https://www.addgene.org/kits/moclo-ytk/)。

## 第5题：把四个报告蛋白放进同一非病毒质粒

**研究目的：**在哺乳动物细胞中准备两个表达单元，每个单元共表达两个报告蛋白。

**给 AI 的任务：**

> 我有 pVH1001、pTS1039 和 pTS1040 三支完整质粒。希望在同一个非病毒质粒中保留两套表达单元：CMV 驱动 SEAP-P2A-iRFP670，PGK1 驱动 Igκ 分泌信号-Nluc-P2A-mTagBFP2；各自终止区保留。第三个接收位置保持空位，细菌骨架保留。请用现有模板完成构建，不把供体的整套冗余骨架一起带进去。交付完整质粒、制备路线和验证方案，核对两条完整编码序列及连接位置。

**材料：**pVH1001 #169599、pTS1039 #169617、pTS1040 #169618。P2A 是用于一个表达单元内共表达多个蛋白的连接肽；不是两个随意拼接的独立基因。

- pVH1001：[材料页](https://www.addgene.org/169599/) · [完整序列入口](https://www.addgene.org/169599/sequences/) · [本地 GenBank](D:/codex_project/github/snapgene-dna-design/output/reference-answers-20260906/q5/pVH1001_Addgene_169599.gb)。
- pTS1039：[材料页](https://www.addgene.org/169617/) · [完整序列入口](https://www.addgene.org/169617/sequences/) · [本地 GenBank](D:/codex_project/github/snapgene-dna-design/output/reference-answers-20260906/q5/pTS1039_Addgene_169617.gb)。
- pTS1040：[材料页](https://www.addgene.org/169618/) · [完整序列入口](https://www.addgene.org/169618/sequences/) · [本地 GenBank](D:/codex_project/github/snapgene-dna-design/output/reference-answers-20260906/q5/pTS1040_Addgene_169618.gb)。本地三份记录由公开网页数据转换。

**为什么值得测：**长编码区、重复调控区、分泌信号和模块位置同时存在，容易出现读框错误、错误取片段或多带骨架。

**出处与性质：**目标对应作者 pTS1042 的双表达结构，作者成品可供检查者对照；路线不限定为某套参考引物。[Haellman 等，2021](https://doi.org/10.1016/j.ymben.2021.04.003)、[作者成品与结构说明](https://www.addgene.org/169620/)。

## 第6题：酵母点突变，同时交付载体、供体和验证设计

**研究目的：**在给定参考序列上准备 CDC48 R105G 编辑所需的 DNA 材料。

**给 AI 的任务：**

> 我想按 Hu 2018 的 CDC48 R105G 案例准备设计，提供 pML104 完整质粒和固定的 CDC48 局部参考。请制备相应 guide 载体、90 bp 双链修复供体，以及预计编辑后的局部序列；同时做不改变其他氨基酸的 PAM 修改，避免同一识别位点继续被切。给完整引物、必要中间体和验证方案。请分清辅助质粒、供体和基因组产物，说明能否用 PCR 条带大小区分野生型与编辑型。此次按给定参考做计算设计。

**材料：**pML104 #67638；固定版本的 CDC48 局部参考及论文。PAM 是 Cas9 识别所需的短序列；修改它与目标蛋白突变是两项不同要求。

- pML104：[材料页](https://www.addgene.org/67638/) · [完整序列入口](https://www.addgene.org/67638/sequences/) · [本地完整 GenBank](D:/codex_project/github/snapgene-dna-design/output/reference-answers-20260906/q6/inputs/pML104_public_viewer.gb)，由公开网页数据转换。
- CDC48：[NCBI 染色体参考 NC_001136.10](https://www.ncbi.nlm.nih.gov/nuccore/NC_001136.10) · [本地固定局部 GenBank](D:/codex_project/github/snapgene-dna-design/output/reference-answers-20260906/q6/inputs/CDC48-locus-NC_001136.10.gb)。发题使用局部文件，不让执行者另换参考版本。

**为什么值得测：**三个产物身份不同，载体正确不代表供体正确。也检验验证方案是否真能识别这种点突变。

**出处与性质：**R105G 和 PAM 修改来自论文；本地参考版本及供体具体边界是已说明的计算设定，不当作作者菌株全基因组结果。[Hu 等，2018](https://pmc.ncbi.nlm.nih.gov/articles/PMC5868978/)、[pML104](https://www.addgene.org/67638/)。

## 第7题：可切除的 MBP 标签融合

**研究目的：**制备既可纯化融合蛋白、又可切除标签的 sfGFP 表达构建。

**给 AI 的任务：**

> 我有 pET His6 MBP TEV LIC cloning vector (1M) 和 pET28a-sfGFP。想构建 His6-MBP-TEV-sfGFP，去掉 sfGFP 供体自带的 C 端 His6。TEV 切割后应得到一个 Gly 加完整供体 sfGFP 蛋白，其余多余残基不要留下。请核对真实载体标签顺序，再完成构建；给完整文件、实际制备材料、引物和覆盖连接处及整段编码区的验证方案。

**材料：**#29656 与 #85492。His6 用于纯化，MBP 是融合标签，TEV 是标签切除位点。两份完整序列入口已定位，尚未下载核验。

- pET His6 MBP TEV LIC (1M)：[材料页](https://www.addgene.org/29656/) · [完整序列入口](https://www.addgene.org/29656/sequences/)。
- pET28a-sfGFP：[材料页](https://www.addgene.org/85492/) · [完整序列入口](https://www.addgene.org/85492/sequences/)。两份文件待登录取得。

**为什么值得测：**标签自身不能有终止导致融合提前结束；切割前后的蛋白身份都要正确。不能把现成标签注释直接当作完整融合检查。

**出处与性质：**使用真实原始材料，组合需求为改编，没有声称存在作者同款 sfGFP 成品。1M 页面个别标签端位描述与提交者说明有冲突，最终按完整序列核对。[1M 原材料](https://www.addgene.org/29656/)、[sfGFP 供体](https://www.addgene.org/85492/)。

## 第8题：连续两轮红色荧光蛋白突变

**研究目的：**制备论文位点所对应的两个连续中间体，研究激发与发射波长间距变化。

**给 AI 的任务：**

> 我只有 mCherry2-C1 这支母本。按 Shen 2017 的 DsRed 参考编号，先做 I161S/Q163E；得到第一轮质粒后，用它作实际模板，再加 W143L。请先核对论文编号在这份源序列上的对应位置。保留 C1 骨架和其余蛋白序列，两轮质粒都要留下，交付每轮完整引物和验证方案。若实际母本与论文不同，明确列出差异，不要偷偷换模板。

**材料：**mCherry2-C1 #54563、论文及其参考序列/附表。I161S 表示参考第161位由异亮氨酸 I 改为丝氨酸 S；其他记法同理，不能直接当质粒碱基坐标。

- mCherry2-C1：[材料页](https://www.addgene.org/54563/) · [完整序列入口](https://www.addgene.org/54563/sequences/)，待登录取得。
- 论文参考序列与 S1 Table：[全文及补充材料入口](https://pmc.ncbi.nlm.nih.gov/articles/PMC5328254/)，附表下载和母本比对尚未完成。

**为什么值得测：**一题同时检验编号映射、多位点修改、实际中间体和版本差异。最终三处变化正确，也不能掩盖第二轮用了错误模板。

**出处与性质：**论文报道两个中间体，但所选 Addgene 母本尚未证实与论文母本完全相同，当前属于论文位点改编。材料与编号核验完成前不发题。[Shen 等，2017](https://doi.org/10.1371/journal.pone.0171257)、[实际母本](https://www.addgene.org/54563/)。

## 第9题：胞质和线粒体探针，迁移到新筛选背景

**研究目的：**配套质粒已经使用 LEU2，需要为两种定位的报告探针更换选择背景。

**给 AI 的任务：**

> 我在 S. cerevisiae BY4741 做氧化还原报告，配套质粒已经占用了 LEU2。手里有 p415 TEF roGFP2-Tsa2ΔCR 胞质版、p415 TEF Su9-roGFP2-Tsa2ΔCR 线粒体基质版和 pRS416。请把两套完整表达盒分别迁入 pRS416，得到 URA3 低拷贝的两支质粒，保留各自原来的启动子、探针、连接区和终止区，不额外加标签。两支分别使用，不合到一个质粒里。给制备路线、引物和验证设计，报告两版的实际结构差异。

**材料：**胞质版 #83238、基质版 #83240、pRS416。两份源报告质粒都使用 LEU2。Su9 是线粒体定位序列；这里用 URA3 是为了与既有筛选背景区分。

- p415 TEF roGFP2-Tsa2ΔCR：[材料页](https://www.addgene.org/83238/) · [完整序列入口](https://www.addgene.org/83238/sequences/)。
- p415 TEF Su9-roGFP2-Tsa2ΔCR：[材料页](https://www.addgene.org/83240/) · [完整序列入口](https://www.addgene.org/83240/sequences/)。两份探针文件待登录取得。
- pRS416：[原厂 ATCC #87521](https://www.atcc.org/products/87521) · [GenBank U03450](https://www.ncbi.nlm.nih.gov/nuccore/U03450) · [SnapGene材料与文件入口](https://www.snapgene.com/plasmids/yeast_plasmids/pRS416)。

**为什么值得测：**需要真正移走源骨架，而不是给原质粒改名或加一条 URA3 注释。原来源除定位序列外是否还有差异也需核对。

**出处与性质：**探针源于 Morgan 等的研究；此次筛选背景迁移为改编需求，定位和响应不是计算验收已经证明的结果。[Morgan 等，2016](https://doi.org/10.1038/nchembio.2067)、[胞质来源](https://www.addgene.org/83238/)、[基质来源](https://www.addgene.org/83240/)。

## 第10题：替换荧光计时器中的一个模块

**研究目的：**用新的绿色荧光模块改造既有串联计时器，同时保留标签载体背景。

**给 AI 的任务草案，材料补齐后再用：**

> 我有完整 pFA6a-mCherry-sfGFP-kanMX 和 pRS423-mCherry-mNeonGreen-CYC1ter，想得到 pFA6a 背景的 mCherry-linker-mNeonGreen 计时器。保留原 kanMX、细菌骨架以及其余标签接口。请从实际模板完成制备和构建，交付融合翻译、连接处检查和验证方案，不能用最终成品倒切一个片段冒充原模板。

**材料：**pMaM17 #173452；原文 pKBJ002.1 完整供体。作者最终 pKBJ006 可供检查者对照，但不能替代缺失的输入。

- pMaM17：[材料页](https://www.addgene.org/173452/) · [完整序列入口](https://www.addgene.org/173452/sequences/) · [本地 GenBank](D:/codex_project/github/snapgene-dna-design/output/reference-answers-20260906/q4/pMaM17_addgene_verified.gb)，由公开网页数据转换。
- pKBJ002.1：**尚未找到完整公开输入文件，没有可用下载链接**。[作者构建记录](https://www.addgene.org/173453/)仅说明使用了这份供体，不提供它的完整序列。

**为什么值得测：**名称或蛋白相同的供体，DNA 版本也可能不同。能否制备必须根据真实母本和引物判断。

**当前状态：关键供体仍缺，暂不发题。**若之后选择其他公开模板，须改题并重新建立独立答案；不称为原论文路线复现。[作者原材料与构建记录](https://www.addgene.org/173453/)、[论文](https://doi.org/10.1007/978-1-0716-1732-8_6)。

## 选题后再补的内容

正式发题前，逐题整理完整输入包，固定来源版本、实体材料说明及独立检查依据。论文或数据库存在、下载入口存在、拿到完整文件、文件已核对，是不同准备状态。受限来源资料先按其条款在本地准备，不默认并入公开 Skill 包。

本轮只搜集和整理候选，不运行测试，不改软件功能，也不把参考答案程序接进测试 AI 的执行过程。
