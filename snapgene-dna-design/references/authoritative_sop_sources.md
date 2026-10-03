# 国际分子生物学经典实验手册与权威文献来源索引 (Authoritative SOP Sources)

> **核心原则**：本索引是 SnapGene DNA Design 所有黄金实验 SOP 配方（Tier 2 Recipes）的单一外部学术来源总表。
> **所有实验参数、同源臂尺寸、酶切保护碱基、退火温度、PAM 突变策略均有据可查，禁止凭大模型记忆捏造。**

---

## 一、 SOP 来源总览表

| 配方名称 | 核心实验类型 | 经典手册 / 奠基文献 | 机构 / 出版社 | DOI / 官方链接 | 核心固化规则 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`recipe_crispr_hdr_donor`** | CRISPR 靶点与 HDR 供体设计 | • *Genome engineering using the CRISPR-Cas9 system* (Ran et al. 2013)<br>• *Efficient introduction of specific homozygous and heterozygous mutations using CRISPR/Cas9* (Paquet et al. 2016)<br>• *Addgene CRISPR Guide* | • **Nature Protocols** (Zhang Lab)<br>• **Nature**<br>• Addgene | [10.1038/nprot.2013.143](https://doi.org/10.1038/nprot.2013.143)<br>[10.1038/nature17664](https://doi.org/10.1038/nature17664) | 1. ssODN 同源臂 40~60 nt；质粒同源臂 500~800 bp<br>2. 破坏 PAM (NGG) 或 Seed 核心区防体内再切割<br>3. U6 启动子转录起始强制 5' G 校验<br>4. 连续 4 个 T (TTTT) Pol III 终止规避 |
| **`recipe_gibson_assembly`** | 同源重叠臂 Gibson / In-Fusion 拼接 | • *Enzymatic assembly of DNA molecules up to several hundred kilobases* (Gibson et al. 2009)<br>• *NEBuilder® HiFi DNA Assembly Master Mix Manual*<br>• *In-Fusion® HD Cloning Plus User Manual* | • **Nature Methods**<br>• New England Biolabs (NEB #E2621)<br>• Takara / Clontech | [10.1038/nmeth.1318](https://doi.org/10.1038/nmeth.1318)<br>[NEB E2621 Protocol](https://www.neb.com/en-us/protocols/2014/11/26/nebuilder-hifi-dna-assembly-reaction-protocol) | 1. 标准同源重叠臂 20~25 bp (GC 40~60%)<br>2. 结合核心区退火温度 $60\pm 2^\circ\text{C}$，$\Delta Tm \le 2^\circ\text{C}$<br>3. 3' 端 GC clamp 锚定<br>4. 短片段 (<200 bp) 防 T5 外切酶嚼毁预警 |
| **`recipe_golden_gate`** | Type IIS 一锅法无痕组装 | • *A One Pot, One Step, PCR-Based Cloning Method for Synthetic Biology* (Engler et al. 2008)<br>• *Comprehensive Profiling of Four Base Overhang Ligation Fidelity by T4 DNA Ligase* (Potapov et al. 2018)<br>• *NEB Golden Gate Assembly Kit Manual* | • **PLoS ONE**<br>• **ACS Synthetic Biology**<br>• New England Biolabs (NEB #E1601) | [10.1371/journal.pone.0003647](https://doi.org/10.1371/journal.pone.0003647)<br>[10.1021/acssynbio.8b00333](https://doi.org/10.1021/acssynbio.8b00333) | 1. BsaI/BsmBI 4-bp 正交无歧义粘端匹配<br>2. 识别位点朝内，组装后完全脱落<br>3. 严格禁止组装产物内部残留识别位点 |
| **`recipe_restriction_cloning`** | 经典限制性双酶切与 T4 连接 | • *Molecular Cloning: A Laboratory Manual*, 4th Ed. (Green & Sambrook 2012)<br>• *Cleavage Close to the End of DNA Fragments*<br>• *NEB T4 DNA Ligase Protocol* | • **Cold Spring Harbor Laboratory Press** (CSHL)<br>• New England Biolabs | [CSHL Press Catalog](https://www.cshlpress.com/)<br>[NEB Cleavage FAQs](https://www.neb.com/en/faqs/cleavage-close-to-the-end-of-dna-fragments) | 1. 引物 5' 端严格按表挂载 2~6 bp 保护碱基<br>2. 载体与插入片段摩尔比 1:3 ~ 1:5<br>3. 单切或平端必须执行去磷酸化 (rSAP) 提示<br>4. 大肠杆菌 Dam/Dcm 甲基化抑制扫描 |
| **`recipe_site_directed_mutagenesis`** | 定点突变与密码子改造 | • *An efficient one-step site-directed and site-saturation mutagenesis protocol* (Zheng et al. 2004)<br>• *Molecular Cloning*, 4th Ed. Ch. 13 (Green & Sambrook 2012)<br>• *QuikChange Site-Directed Mutagenesis Manual* | • **Nucleic Acids Research** (NAR)<br>• **CSHL Press**<br>• Agilent Technologies | [10.1093/nar/gnh110](https://doi.org/10.1093/nar/gnh110)<br>[Agilent Manual](https://www.agilent.com/) | 1. 突变位点居于引物中央，两侧各保留 10~15 bp 完全匹配翼<br>2. 引物退火温度规范 $Tm \ge 78^\circ\text{C}$（QuikChange 专用公式）<br>3. 引物 3' 端以 1~2 个 G/C 封尾 (GC clamp)<br>4. 强制执行 DpnI 消化甲基化母本质粒消除背景 |
| **`recipe_protein_tagging`** | 重组蛋白表达与标签工程 | • *Overview of tag protein fusion: from molecular and biochemical fundamentals to commercial systems* (Terpe 2003)<br>• *Point mutations define a sequence flanking the AUG initiator codon* (Kozak 1986)<br>• *An overview of enzymatic reagents for removal of affinity tags* (Waugh 2011) | • **Applied Microbiology and Biotechnology**<br>• **Cell**<br>• Protein Expression and Purification | [10.1007/s00253-002-1158-6](https://doi.org/10.1007/s00253-002-1158-6)<br>[10.1016/0092-8674(86)90762-2](https://doi.org/10.1016/0092-8674(86)90762-2) | 1. C 端标签融合强制剥离原 CDS 终止密码子<br>2. 柔性 Linker ((G4S)n) 与刚性 Linker (EAAAK) 长度核酸严格整除 3<br>3. 哺乳动物表达载体强制添加 Kozak 共有序列 (`GCCACC`) 紧邻 ATG<br>4. 亲和标签与目的蛋白之间可嵌入特异性蛋白酶切位点 (TEV/3C) |
| **`recipe_cloning_verification`** | 分子质检与测序引物布局 | • *Molecular Cloning: A Laboratory Manual*, 4th Ed. Ch. 1 & 8 (Green & Sambrook 2012)<br>• *DNA sequencing with chain-terminating inhibitors* (Sanger et al. 1977) | • **Cold Spring Harbor Laboratory Press**<br>• **PNAS** | [10.1073/pnas.74.12.5463](https://doi.org/10.1073/pnas.74.12.5463) | 1. **菌落 PCR 黄金法则**：引物必须“一端在载体骨架，一端在插入片段”（跨接缝），严禁双引物均在插入片段内（防假阳性）<br>2. **Sanger 测序避坑法则**：测序引物必须锚定在接缝上游 50~100 bp（避开前 30~50 bp 荧光盲区）<br>3. **限制性双酶切质检**：凝胶电泳预期两条特征带分子量差值 $\ge 15\%$，确保凝胶肉眼清晰可辨 |

---

## 二、 逐项详细规范与学术依据

### 1. CRISPR 基因编辑与 HDR 供体修复规范

* **文献引用**：
  * Ran, F.A., Hsu, P.D., Wright, J., Agarwala, V., Scott, D.A. and Zhang, F. (2013). Genome engineering using the CRISPR-Cas9 system. *Nature Protocols*, 8(11), pp.2281–2308. doi:10.1038/nprot.2013.143.
  * Paquet, D., Kwart, D., Chen, A., Sproul, A., Jacob, S., Teo, S., Runnels, L.W., Zhou, M. and Tessier-Lavigne, M. (2016). Efficient introduction of specific homozygous and heterozygous mutations using CRISPR/Cas9. *Nature*, 533(7601), pp.125–129. doi:10.1038/nature17664.
* **固化的 SOP 参数**：
  * **ssODN 同源臂**：单链寡核苷酸供体两侧同源臂标准取 40~60 nt，总长推荐 120~180 nt。Paquet 2016 实证表明，当点突变距离切割位点 $\le 5$ bp 时，HDR 效率最高；超过 10 bp 效率衰减 $80\%$。
  * **PAM / Seed 阻断**：体内游离 Cas9/sgRNA 会重新切断已修复的靶点或供体质粒。SOP 优先寻找 PAM（`NGG`）中的第 2 或第 3 位 G 进行同义替换；若位于关键氨基酸无法替换，则转向 PAM 上游 1~3 bp 的 Seed 核心区进行同义替换。
  * **人源 U6 pol III 转录规则**：转录必须以 `G` 起始；如果 20-nt spacer 首位不是 G，正向引物必须人为前置 `G`；spacer 内部严禁存在 `TTTT` 终止信号。

---

### 2. Gibson / In-Fusion 同源重叠组装规范

* **文献引用**：
  * Gibson, D.G., Young, L., Chuang, R.Y., Venter, J.C., Hutchison, C.A. and Smith, H.O. (2009). Enzymatic assembly of DNA molecules up to several hundred kilobases. *Nature Methods*, 6(5), pp.343–345. doi:10.1038/nmeth.1318.
  * New England Biolabs. (2023). *NEBuilder® HiFi DNA Assembly Master Mix Protocol (NEB #E2621)*. Ipswich, MA.
* **固化的 SOP 参数**：
  * **重叠长度 (Overlap)**：2~3 片段组装推荐 20~25 bp（NEB 官方推荐下限 15 bp，上限 40 bp）。重叠臂 GC% 限制在 40%~60%，自身退火 Tm 需 $\ge 48^\circ\text{C}$。
  * **引物结合区**：退火温度锁定在 $60\pm 2^\circ\text{C}$（SantaLucia 1998 最近邻热力学公式），正反引物 $\Delta Tm \le 2^\circ\text{C}$，3' 端最后 5 个碱基内至少包含 1~2 个 G/C 作为 GC clamp。
  * **短片段反应保护**：当插入片段 $<200$ bp 时，由于 T5 外切酶活力极高，SOP 必须向用户发出缩短反应时间或增加短片段摩尔比的预警。

---

### 3. Golden Gate Type IIS 一锅法无痕克隆规范

* **文献引用**：
  * Engler, C., Kandzia, R. and Marillonnet, S. (2008). A One Pot, One Step, PCR-Based Cloning Method for Synthetic Biology. *PLoS ONE*, 3(11), p.e3647. doi:10.1371/journal.pone.0003647.
  * Potapov, V., Ong, J.L., Kucera, R.B., Langhorst, B.W., Bilotti, K., Pryor, J.M., Cantor, E.J., Morrison, A.J., Sun, T. and Bilotti, S. (2018). Comprehensive Profiling of Four Base Overhang Ligation Fidelity by T4 DNA Ligase. *ACS Synthetic Biology*, 7(11), pp.2665–2674. doi:10.1021/acssynbio.8b00333.
* **固化的 SOP 参数**：
  * **酶切位点排布**：外侧 BsaI (`GGTCTC(1/5)`) 或 BsmBI (`CGTCTC(1/5)`) 的切割方向必须朝向核心序列，使识别位点与质粒骨架断开；
  * **4-bp 粘端正交性**：相邻接缝的 4-bp overhang 严格杜绝回文对称或自身互补（如 `AAAA`、`ATAT`、`GCGC` 等低保真粘端），保证多片段一次性正确连接。

---

### 4. 经典双酶切定向克隆规范

* **文献引用**：
  * Green, M.R. and Sambrook, J. (2012). *Molecular Cloning: A Laboratory Manual*. 4th ed. Cold Spring Harbor, NY: Cold Spring Harbor Laboratory Press. Chapters 1, 3, and 8.
  * New England Biolabs. (2024). *Cleavage Close to the End of DNA Fragments*. Technical Reference.
* **固化的 SOP 参数**：
  * **5' 保护碱基对照标准**：
    * EcoRI / BamHI / HindIII / XhoI: 推荐 2~3 个保护碱基（默认 `CGC` 或 `GAC`）；
    * NdeI / NotI / XbaI: 推荐 4~6 个保护碱基（默认 `AAGGCC`）；
  * **质粒模板消除**：PCR 扩增质粒来源的基因后，必须在连接/纯化前加入 $1\,\mu\text{L}$ DpnI（$37^\circ\text{C}$，15~30 min）消化大肠杆菌内提提取的甲基化质粒模板，杜绝空载体假阳性背景。

---

### 5. 定点突变与密码子工程规范 (Site-Directed Mutagenesis)

* **文献引用**：
  * Zheng, L., Baumann, U. and Reymond, J.L. (2004). An efficient one-step site-directed and site-saturation mutagenesis protocol. *Nucleic Acids Research*, 32(14), p.e115. doi:10.1093/nar/gnh110.
  * Green, M.R. and Sambrook, J. (2012). *Molecular Cloning: A Laboratory Manual*. 4th ed. Chapter 13: In Vitro Mutagenesis.
* **固化的 SOP 参数**：
  * **引物突变位点对称性**：突变碱基必须处于引物正中央，两侧各保留 10~15 bp 严格配对的野生型翼（Flanking arms），总长推荐 25~45 nt。
  * **退火温度公式**：采用经典 QuikChange 公式计算：$Tm = 81.5 + 0.41(\%GC) - 675 / N - \%mismatch$，确保 $Tm \ge 78^\circ\text{C}$。
  * **DpnI 消化母本**：PCR 扩增完成后，必须加入 $1\,\mu\text{L}$ DpnI 在 $37^\circ\text{C}$ 消化 1 小时，特异性水解 Dam 甲基化的亲实质粒，使背景假阳性降低 100 倍。

---

### 6. 表达标签与融合蛋白工程规范 (Protein Tagging)

* **文献引用**：
  * Terpe, K. (2003). Overview of tag protein fusion: from molecular and biochemical fundamentals to commercial systems. *Applied Microbiology and Biotechnology*, 60(5), pp.523–533. doi:10.1007/s00253-002-1158-6.
  * Kozak, M. (1986). Point mutations define a sequence flanking the AUG initiator codon that modulates translation by eukaryotic ribosomes. *Cell*, 44(2), pp.283-292. doi:10.1016/0092-8674(86)90762-2.
* **固化的 SOP 参数**：
  * **C 端标签前置 Stop 剥离**：C 端融合标签时，必须 100% 自动剥离前置目标基因的终止密码子（`TAA/TAG/TGA`），并在标签后置终止密码子，严防提前终止导致标签脱靶丢失。
  * **Linker 与读码框三倍数校验**：无论是柔性 Linker `(G4S)n` 还是刚性螺旋 Linker `(EAAAK)n`，其核苷酸总数必须整除 3（$mod\,3 == 0$），保证全长三联体读码框不发生移码。
  * **真核翻译起始 Kozak 共有序列**：在哺乳动物表达质粒中，ATG 起始密码子前置标准 `GCCACC` 共有序列，提高核糖体识别与翻译效率。

---

### 7. 分子克隆质检与测序引物布局规范 (Cloning QC & Verification)

* **文献引用**：
  * Green, M.R. and Sambrook, J. (2012). *Molecular Cloning: A Laboratory Manual*. 4th ed. Cold Spring Harbor, NY. Chapters 1 & 8.
  * Sanger, F., Nicklen, S. and Coulson, A.R. (1977). DNA sequencing with chain-terminating inhibitors. *PNAS*, 74(12), pp.5463-5467.
* **固化的 SOP 参数**：
  * **菌落 PCR 跨接缝法则**：一根引物锚定在载体骨架，另一根引物锚定在插入基因内部；或一根跨越重组接缝。产物分子量推荐在 300~800 bp，严禁双引物都在插入片段内部以彻底杜绝母本残留导致的假阳性。
  * **Sanger 测序 50~100 bp 避坑窗**：Sanger 测序毛细管电泳在前 30~50 bp 存在染料杂峰与严重未分离盲区。测序引物必须距离目标克隆接缝或突变位点上游 50~100 bp，确保关键接缝落在峰形最饱满清晰的 100~500 bp 黄金读长区内。
  * **诊断性酶切条带分辨率**：所选单切或双切酶切产生的质粒特征条带，相邻两条带分子量相对差异需 $\ge 15\%$，保证 1% 琼脂糖凝胶肉眼可清晰分辨。


---

## 二、 逐项详细规范与学术依据

### 1. CRISPR 基因编辑与 HDR 供体修复规范

* **文献引用**：
  * Ran, F.A., Hsu, P.D., Wright, J., Agarwala, V., Scott, D.A. and Zhang, F. (2013). Genome engineering using the CRISPR-Cas9 system. *Nature Protocols*, 8(11), pp.2281–2308. doi:10.1038/nprot.2013.143.
  * Paquet, D., Kwart, D., Chen, A., Sproul, A., Jacob, S., Teo, S., Runnels, L.W., Zhou, M. and Tessier-Lavigne, M. (2016). Efficient introduction of specific homozygous and heterozygous mutations using CRISPR/Cas9. *Nature*, 533(7601), pp.125–129. doi:10.1038/nature17664.
* **固化的 SOP 参数**：
  * **ssODN 同源臂**：单链寡核苷酸供体两侧同源臂标准取 40~60 nt，总长推荐 120~180 nt。Paquet 2016 实证表明，当点突变距离切割位点 $\le 5$ bp 时，HDR 效率最高；超过 10 bp 效率衰减 $80\%$。
  * **PAM / Seed 阻断**：体内游离 Cas9/sgRNA 会重新切断已修复的靶点或供体质粒。SOP 优先寻找 PAM（`NGG`）中的第 2 或第 3 位 G 进行同义替换；若位于关键氨基酸无法替换，则转向 PAM 上游 1~3 bp 的 Seed 核心区进行同义替换。
  * **人源 U6 pol III 转录规则**：转录必须以 `G` 起始；如果 20-nt spacer 首位不是 G，正向引物必须人为前置 `G`；spacer 内部严禁存在 `TTTT` 终止信号。

---

### 2. Gibson / In-Fusion 同源重叠组装规范

* **文献引用**：
  * Gibson, D.G., Young, L., Chuang, R.Y., Venter, J.C., Hutchison, C.A. and Smith, H.O. (2009). Enzymatic assembly of DNA molecules up to several hundred kilobases. *Nature Methods*, 6(5), pp.343–345. doi:10.1038/nmeth.1318.
  * New England Biolabs. (2023). *NEBuilder® HiFi DNA Assembly Master Mix Protocol (NEB #E2621)*. Ipswich, MA.
* **固化的 SOP 参数**：
  * **重叠长度 (Overlap)**：2~3 片段组装推荐 20~25 bp（NEB 官方推荐下限 15 bp，上限 40 bp）。重叠臂 GC% 限制在 40%~60%，自身退火 Tm 需 $\ge 48^\circ\text{C}$。
  * **引物结合区**：退火温度锁定在 $60\pm 2^\circ\text{C}$（SantaLucia 1998 最近邻热力学公式），正反引物 $\Delta Tm \le 2^\circ\text{C}$，3' 端最后 5 个碱基内至少包含 1~2 个 G/C 作为 GC clamp。
  * **短片段反应保护**：当插入片段 $<200$ bp 时，由于 T5 外切酶活力极高，SOP 必须向用户发出缩短反应时间或增加短片段摩尔比的预警。

---

### 3. Golden Gate Type IIS 一锅法无痕克隆规范

* **文献引用**：
  * Engler, C., Kandzia, R. and Marillonnet, S. (2008). A One Pot, One Step, PCR-Based Cloning Method for Synthetic Biology. *PLoS ONE*, 3(11), p.e3647. doi:10.1371/journal.pone.0003647.
  * Potapov, V., Ong, J.L., Kucera, R.B., Langhorst, B.W., Bilotti, K., Pryor, J.M., Cantor, E.J., Morrison, A.J., Sun, T. and Bilotti, S. (2018). Comprehensive Profiling of Four Base Overhang Ligation Fidelity by T4 DNA Ligase. *ACS Synthetic Biology*, 7(11), pp.2665–2674. doi:10.1021/acssynbio.8b00333.
* **固化的 SOP 参数**：
  * **酶切位点排布**：外侧 BsaI (`GGTCTC(1/5)`) 或 BsmBI (`CGTCTC(1/5)`) 的切割方向必须朝向核心序列，使识别位点与质粒骨架断开；
  * **4-bp 粘端正交性**：相邻接缝的 4-bp overhang 严格杜绝回文对称或自身互补（如 `AAAA`、`ATAT`、`GCGC` 等低保真粘端），保证多片段一次性正确连接。

---

### 4. 经典双酶切定向克隆规范

* **文献引用**：
  * Green, M.R. and Sambrook, J. (2012). *Molecular Cloning: A Laboratory Manual*. 4th ed. Cold Spring Harbor, NY: Cold Spring Harbor Laboratory Press. Chapters 1, 3, and 8.
  * New England Biolabs. (2024). *Cleavage Close to the End of DNA Fragments*. Technical Reference.
* **固化的 SOP 参数**：
  * **5' 保护碱基对照标准**：
    * EcoRI / BamHI / HindIII / XhoI: 推荐 2~3 个保护碱基（默认 `CGC` 或 `GAC`）；
    * NdeI / NotI / XbaI: 推荐 4~6 个保护碱基（默认 `AAGGCC`）；
  * **质粒模板消除**：PCR 扩增质粒来源的基因后，必须在连接/纯化前加入 $1\,\mu\text{L}$ DpnI（$37^\circ\text{C}$，15~30 min）消化大肠杆菌内提提取的甲基化质粒模板，杜绝空载体假阳性背景。
