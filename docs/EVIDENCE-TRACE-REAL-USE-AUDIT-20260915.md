# Evidence Trace 真实使用筛查

2026-09-15。基线 `d52165b440f9c04b79272507f87c4fdb5aafacc8`，开发分支 `codex/real-workflow-readiness-20260907`。本次没有修复业务代码或修改被测 Trace。

## 结论

**程序执行、真实失败和部分设计调整能够记录；完整宿主过程及全部交付文件尚不能可靠追溯。本次没有完成两份正式表达构建的交付。**

两份候选的关键序列、材料制备链及测序位置通过了父代理的独立核对。正式交付被源载体及转换后的 CDS 注释检查阻塞。计算候选正确、正式交付完成、证据链完整，是三个不同结论。

## 任务与测试条件

由 gpt-5.6-luna、max 推理等级独立使用仓库 Skill，完成一项研究者场景任务：用完整 pBP-eGFP 和 pET-28a(+) 设计源 GFP 对照与文献支持的低自聚候选；统一 N 端 His6 背景，保留 GFP stop，不加 C 端融合标签；提供引物、真实中间体、.gb/.dna 和区分两组的验证设计。

研究需求是本次拟定的模拟委托，材料为真实完整质粒记录，检索、工具运行和新文件生成均真实发生，没有湿实验。未预先告诉执行者选择哪个突变或使用哪条路线；禁止读取历史答案、复制旧产物或改库代码。Full 使用独立配置，未改用户全局配置。

父代理提供了目录权限帮助和推进任务的提醒，没有提供生物学答案或让执行者在审查后回填记录。因此这是有少量操作协助的真实使用筛查，不是完全无干预的成功率实验。

执行者选择 A206K，引用 [Zacharias 等，Science 2002](https://pubmed.ncbi.nlm.nih.gov/11988576/)。论文支持研究该类低自聚候选，本例没有验证当前表达条件下的自聚性能。

## 实际经过

| 阶段 | 实际结果 |
|---|---|
| 文献与源检查 | 确认源 GFP 对应残基为 Ala，选择 GCC → AAG；最初选择 NdeI/XhoI |
| 首次克隆 | 插入片段出现两个 NdeI 切点，程序拒绝，未交付错误产物 |
| 更换 NheI/XhoI | 生成 6019 bp 对照候选；正式交付因 CDS 注释检查失败被拒 |
| 保留完整 T7 标签背景 | 添加载体来源的接头，生成 6043 bp 对照候选；序列调整后原 T7 标签注释仍未正确覆盖，正式交付再次被拒 |
| A206K 制备与克隆 | 从完整源质粒生成 2808 bp 突变中间体，再用它生成 6043 bp 表达候选；本次仅请求候选输出，其注释检查也未全部通过 |
| 验证设计 | 两组分别生成 QC；随后用独立引物标注工具生成四份带新增测序引物的 .gb/.dna |

共 7 次被 Trace 记录的运行：3 次 failed，4 次 candidate。candidate 包括中间体及 QC，不能合计成四份成功交付的表达构建。对照两次正式交付请求均被注释检查拒绝，候选组未单独请求正式交付。

## 产物独立检查

父代理直接读取源文件和输出文件，未用 Core 的整体验证结论代替以下检查。

| 检查 | 结果 |
|---|---|
| 两份新版表达候选 | 均为 6043 bp 环形 DNA；.gb/.dna 序列和拓扑一致，各保留 19 个特征 |
| 两组差异 | 全质粒仅 3 个碱基不同；GFP 编码区只改变 A206K，源对照保持原编码序列 |
| 表达边界 | N 端 His6 与下游 GFP 同框，GFP 末端 stop 保留，没有内部提前终止；候选不代表实测表达成功 |
| 骨架 | lacI、KanR、rop、复制起点等所检特征的序列和标签保留；这不表示所有特征坐标与类型都已正确 |
| 三段材料制备 | 正反引物结合核心及尾部一致；独立推导 PCR 产物与保存产物一致，分别为 759、2808、759 bp |
| 中间体使用 | 候选克隆的 PCR 模板序列与实际生成的 A206K 中间体一致，并非另造一个目标序列充当模板 |
| 引物标注 | 三段制备的源记录副本均含两个引物标注，GenBank 与 native DNA 中可读 |
| 测序检查 | 原 QC 测序引物后的 173–175 bp 覆盖三个差异碱基；新增反向测序引物结合正确，也覆盖该位置。两组 PCR 同长，不能仅凭条带长度区分 |
| 源文件 | 与运行前副本逐字节比较，两个原始输入未改变 |

正式交付检查中的具体问题包括：将 thrombin 短位点当作需要终止密码子的完整 CDS；T7 tag 的截断位置与原 translation 不一致；rop/lacI 的 GTG 起始与所声明翻译表不匹配。完整表达序列可同框，并不消除这些注释问题。此次未删除特征、改源 DNA 或关闭检查以绕过交付。

独立核对发现 `ends_compatible=false` 与方向性克隆成功并不矛盾：该字段比较的是两种酶的末端是否彼此相容，不是本次载体和插入片段能否连接。它未被误计为本次缺陷。

## Evidence Trace 的实际表现

最终 `events.jsonl` 有 165 条事件，包含 8 个 Decision、12 个 Validation、40 个 Artifact；另有 2 个 Requirement、1 个 Source、1 个 Statement、1 个 Claim 和 1 条证据关系。计数只说明存储内容，不是完整性或科学正确率。

### 做到了什么

- NdeI 的实际失败被程序自动记录，旧决定未覆盖。
- 新的 `D-cloning-nheI@1` 在 `basis_refs` 中引用前次失败事件 `d16839278981403fb9bd47ae87cdc278` 和旧边界决定。这一修改能追到具体失败，而不只是叙述“后来换了方法”。
- 后续运行显式选择新决定范围，没有把旧 NdeI 方案继续当作正在执行的方案。
- wrapper 内的检查及文件有实际运行记录；候选未被改称正式产物。

### 实际暴露的缺口

| 问题 | 本次可核查事实 | 影响 |
|---|---|---|
| Skill 外的研究过程未自动进入 Trace | 宿主公开记录中有 9 次 `web__run` 调用尝试。Trace 没有对应的原检索事件链，主要靠执行者提交论文记录；部分工具结果还可携带普通引用，但不等于具有检索来源关联 | 仅靠 Trace 不能复核哪些返回片段先被看到、哪些后来用于决定 |
| 原始说明来源仍是自报 | `D-a206k` 的来源为 `public-paper-review-and-local-source-inspection`；其他决定使用 `local-source-inspection`、`skill-route-selection` 等描述 | 这些字符串不能定位原消息。父代理另读宿主公开记录能确认部分说明发生在执行前，但被测系统自身没有建立这项核对 |
| 后续文件处理脱离产物链 | `qc-control-a206k-check/` 和 `qc-candidate-a206k-check/` 中的四份 `verification_with_A206K_seq.gb/.dna` 真实存在，新增引物正确；四份均不在 Trace 的 Artifact 清单 | 最后交给用户的部分文件不能从当前 Trace 追到生成或修改动作 |
| 用户约束被包装为 AI 决定 | `D-terminal`、`D-terminal-nheI` 将“保留 stop、不加 C 端标签”记录成 AI Decision，理由主要是用户已明确要求 | 页面可能夸大 AI 自主取舍，混淆用户要求与设计决定 |
| 文献支持仍靠提交者判断 | 唯一 Statement 的定位为 `paper abstract and reported GFP-variant comparison`，没有绑定所见片段的具体工具返回；Statement 未填写 context，条件比较也不能从空字段恢复实验条件 | 记录了一个支持判断，但读者仍需重新找原文，不能把它当成程序核实的证据支持 |

最终图的 `integrity` 为 `complete`、`issues` 为空，但四份后续 QC 文件仍未进入图。这不违反现有“只表示已记录日志结构完整”的定义，却说明该指标完全不能回答“此次任务是否都记录了”。

## 对后续开发的直接约束

1. 承认现有有效部分：调用前后记录、失败引用、显式运行范围和实际中间体链可以保留，不需要推倒重造。
2. 优先补真实边界：先覆盖此次已证明会产生交付文件的独立工具路径，以及可获得的宿主公开来源；没有来源时保持声明身份。
3. 设计关系继续由 AI/用户明确提交，程序核对对象与版本；不能期待程序从孤立参数恢复科学理由。用户约束应归回要求，不强制凑 Decision。
4. 注释语义及特征转换的交付阻塞应单独修复，保留此次原始失败输入。不能用降低门槛或重新措辞替代修复。
5. HTML 工作不能代替这些问题的处理。本次只保留案例和结论，没有启动修复或修改 spec。

## 文件入口与复核范围

- [执行者交接](../snapgene-dna-design/output/trace-real-use-20260915-01/worker/HANDOFF.md)
- [原始 Trace](../snapgene-dna-design/output/trace-real-use-20260915-01/worker/evidence-trace/events.jsonl)及[当前 HTML](../snapgene-dna-design/output/trace-real-use-20260915-01/worker/evidence-trace/index.html)
- [对照候选 DNA](../snapgene-dna-design/output/trace-real-use-20260915-01/worker/control-clone-nheI-t7repair/candidate/recipe_restriction_cloning.dna)
- [A206K 候选 DNA](../snapgene-dna-design/output/trace-real-use-20260915-01/worker/a206k-clone-nheI-t7repair/candidate/recipe_restriction_cloning.dna)
- [带新增引物的对照 QC](../snapgene-dna-design/output/trace-real-use-20260915-01/worker/qc-control-a206k-check/verification_with_A206K_seq.dna)
- [带新增引物的候选 QC](../snapgene-dna-design/output/trace-real-use-20260915-01/worker/qc-candidate-a206k-check/verification_with_A206K_seq.dna)
- [独立产物检查](../snapgene-dna-design/output/trace-real-use-20260915-01/observer/product-checks.json)及[检查脚本](../snapgene-dna-design/output/trace-real-use-20260915-01/observer/check_products.py)
- [宿主公开事件快照](../snapgene-dna-design/output/trace-real-use-20260915-01/observer/host-public-events.json)：仅本次子任务的公开消息及工具调用，排除内部推理；与被测 Trace 分开保存，不回填。

生成物位于忽略的 output 目录，仅在本机可用，不随报告提交到源码仓库。未执行湿实验或桌面 SnapGene 打开检查；解析往返通过不冒充桌面验收。仅此一项任务，未估计一般成功率、Full 的额外成本或用户阅读效率。
