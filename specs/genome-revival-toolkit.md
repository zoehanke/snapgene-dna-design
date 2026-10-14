# Genome Revival Toolkit

2026-10-11。本文件拥有项目专用Skill的产品边界；DNA底座契约仍由[Core spec](core-skill.md)管理，证据记录由[Trace spec](safety-module.md)管理。实施记录（原稿曾公开，现已移出当前树并完整私有备份；历史仍可见）保存本轮实证，[当前交接](../docs/development-plans/README.md)承接未关闭项，不替代本契约。

## 目标与当前授权

为Genome Revival的原生质体融合和遗传学两条研究路线提供可重复的DNA构建、给定区域遗传鉴别、实验记录整理及CRISPR质粒准备。一个独立Skill，四个Kit；领域知识与材料配置专用，DNA算法复用同版Core。不能预测细胞复活成功率，不能将单个位点阳性/阴性解释为整个基因组恢复/消除。

本轮授权本地实施、独立可恢复测试安装、测试、文档和候选打包。未经负责人授权不push远端、改main/GitLab、部署Wiki、发布Release或覆盖现用Skill。

2026-10-14追加授权独立CRISPR Kit分支、验证后推开发分支、英文Trace和私有Wiki交付。第四Kit须在10月15日上午前通过验收才并入冻结包；未完成不降低门槛。官方候选发布授权不延伸至main、Wiki发布、表单、权属或AI披露终审。

## 支持的工作流

| Kit | 输入与实际输出 | 必守边界 |
|---|---|---|
| Construct | 明确参考区域、cargo区间、目标边界和臂长；真实PCR/组装、完整引物及质量、供体和结构鉴别、Core正式交付 | 不猜SY14 URA3位点或实验株系；序列供体模型不冒充实体制备；缺材料、方向歧义或质量失败保留未完成 |
| Genome Identity | 明确版本的参考区域和可选完整引物；实际比对、逐背景PCR预测、鉴别条件与未覆盖范围 | 最佳比对不等于唯一定位；无带、歧义及未检测分开；PCR计算不等于实验检测 |
| Revival Evidence | 有来源的实验组/对照、菌落计数和遗传检测记录；观察比较与结论范围 | 输入是研究者报告的观察，不自动变为已验证实验；生长/荧光/局部PCR不能单独证明基因组复活 |
| CRISPR plasmid | 实际载体/靶标、明确20 nt间隔序列与cassette选择器、用户基因型；候选因素、方向/PAM、载体自切、默认逆向PCR计划与独立模拟、条件性筛选映射及Core文件 | 不推断基因型；名称需完整实际CDS支持并有每行来源；UNKNOWN/冲突不成为兼容。计划/模拟不等于湿实验、完整scaffold功能、敲除效率或全基因组脱靶 |

专业流程可组合成熟Core能力，方法和任务科学取舍仍由宿主决定；不给已有通用能力另造算法实现。

CRISPR筛选总状态仅针对用户声明的受体宿主。其他宿主的扩增标记保留其板和来源，受体行标NOT_APPLICABLE，对应其他宿主板仍为UNKNOWN。未映射的已识别标记不得遗漏。通用APH家族名或单独tetR不能推出抗性；NatMX的nourseothricin对应以公开论文为据。完整ORF只支撑注释结构，不认证基因身份、表达或筛选功能。

## 项目上下文与接口

2026-10-14块K第一阶段：Identity作为首个子Skill试点进入kits/，保留原公开入口、参数、科学边界和业务输出/Trace。其他三Kit不迁移。共享项目Context/报告留在Kit侧，底盘只认识通用Kit接口。机器契约与子Skill说明分开；构建只计划完整Toolkit分发，本阶段不发行或并入冻结候选。运行时加载元数据与旧业务Trace分别验收，不能借规范化隐藏检查、方向、质量、状态、错误或文件角色变化。

共享Project Context采用JSON。菌株和角色、参考文件/版本、元件、两条路线、事实/假设/未验证条件保持来源。实际文件哈希及Molecule版本与声明菌株/版本分开；缺失材料明确列出。引用区域使用0-based half-open，跨多个记录须明确选择，不静默取首个记录。

`genome-revival-toolkit/`拥有入口与专用代码。开发时复用兄弟Core；独立包包含构建时选定的同版运行底座，单一上游源码，不维护复制的DNA实现。包不含私有DNA、考官答案、实际实验原件或本机绝对路径。

## Evidence Trace

四个Kit共用现有Trace采集、追加式日志、组织和确定性HTML/Markdown。程序可整理自己实际执行的流程骨架和返回事实；科学理由只引用用户/AI/研究者明确提交的记录，不自动补原始思考。观察顺序不冒充因果，记录完整性、DNA检查及实验结论分开。

最小文件关联：实际输出SHA-256与另一观察步骤声明的输入SHA-256相等，才生成现有input_reference事实并用grouped_with组织关系绑定fact_relation_ids。交付、回读及报告导出声明实际文件输入/输出；记录较晚的artifact以其真实生成事件定位，不以日志追加顺序替代生成事件。无匹配不补关系，文件内容相等不证明科学支持、实际物料使用或因果。报告区分程序验证的文件关联与声明关系；本项不新增关系类型或改阅读界面。

`original_request`是宿主提交的文本，不自动等于逐字原对话；JSON字段的verbatim引用只能证明该字段。宿主摘要与原会话需分开保存和核对。原AI理由可与后续计算冲突，程序PASS不认证理由。宿主另写的报告、备用候选或外部脚本不自动进入Kit回执和Trace范围。

报告先说明任务与实际结果，再呈现主要过程、依据、当前检查和文件；技术详情独立可达。文件改变和新事实使旧关联/组织陈旧，报告可从日志重建。未观察的宿主脚本、外部编辑与呈现列采集缺口；Full不等于全部捕获。Off/Observed/Full保持相同DNA与质量语义，normal故障不改变Core结果，strict准确报告缺记录。

## 验收与未决

两个P0 Kit须有独立正反例及公共入口实证；至少一条实际构建制备/正式交付成立，一条成功及失败经过Trace，独立包与实际宿主验证支持范围。开发者辅助、已知题和陌生评测分开，不采信执行者自报PASS。

真实SY14/XT2角色、URA3位点和实验完成状态以本轮原件核查为准。缺口不补造；可用独立合成材料验工程但不能称项目实验成功。外部真人理解、湿实验和正式官方提交若未取得证据，保持未验证。

Toolkit 0.2.1 adds optional English reports for all four Kits and observed before/after output directories. Mixed Core delivery retains the manifest-defined final DNA identity; a supporting report cannot demote or promote molecular artifacts. Known scripted synthetic examples and isolated report-reading rehearsal are separate from autonomous host or wet-lab evidence.

0.2.2公共报告契约：Identity的序列比对比较与Evidence的提交计数比较采用各自字段，不按同名comparisons数组假定共同结构。Evidence无分母保留未知，不变为零；没有遗传检测的全基因组消除结论仍NOT_TESTED。合成记录必须明确标为软件测试向量，不作为实验结果或机制证据。
