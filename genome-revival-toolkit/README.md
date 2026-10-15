# Genome Revival Toolkit

一个面向Genome Revival研究的Skill，帮助AI完成明确范围内的分子设计、遗传鉴别和证据整理。

| 你要解决什么 | 使用哪个Kit | 得到什么 |
|---|---|---|
| 从手头模板制备标记供体并核查结构 | Construct | 实际制备链、完整引物及质量、供体文件、两侧鉴别和Core回执 |
| 比较两种参考的指定区域，评估PCR能否区分 | Genome Identity | 当前比对、逐参考扩增预测、候选质量和鉴别条件 |
| 整理实验组/对照、菌落及遗传检测 | Revival Evidence | 观察比较、证据支持范围、反证和未检测项目 |
| 检查或替换已有gRNA，准备敲除质粒 | CRISPR | 候选因素、方向/PAM、自切检查、计划制备、完整引物、条件性筛选映射及文件 |

Toolkit v0.2.2复用DNA Design Core 2.2.5，Evidence Trace为0.3.5。没有训练新的模型权重，也没有另一套DNA算法。开发源码共用底座，独立包携带同版运行代码。

官方 GitLab CI 未执行。GitHub测试、本地工程验证、文件回读与湿实验是不同证据；当前软件文件和制备模拟不证明实验成功。

## 安装和开始使用

解压完整包，将整个`genome-revival-toolkit`目录安装到宿主的Skills目录。只需一个Skill，内部包含四个Kit。先在Skill目录安装受测依赖：

```text
python -X utf8 -m pip install -r requirements.txt
python -X utf8 -B scripts/run_toolkit.py --help
```

正常使用时把研究需求和实际材料交给AI。示例请求：

> 请比较提供的两个参考区域，设计能鉴别它们的PCR。检查完整引物、各参考的预测结果和鉴别条件，交付报告与检测候选。结论只限定于给定区域。

AI以项目Context连接实际文件，查询所选Kit的输入形状后运行。不需要研究者手写DNA算法。最短程序路径：

```text
python -X utf8 -B scripts/run_toolkit.py inspect --context project-context.json
python -X utf8 -B scripts/run_toolkit.py describe identity
python -X utf8 -B scripts/run_toolkit.py identity --context project-context.json --request request.json --out-dir results
python -X utf8 -B scripts/run_toolkit.py verify --out-dir results --receipt-sha256 RETURNED_SHA
```

[输入说明](references/workflows.md)解释各Kit字段；[项目Context样式](assets/project-context-template.json)只提供结构，不能代替真实材料。

CRISPR 使用 `describe crispr` 查询字段，再通过 `crispr --context ... --request ... --out-dir ...` 运行。检查已有构建使用 `operation: check`；替换需明确20 nt间隔序列。输入菌株基因型和已有标记，才能判断条件性筛选兼容；未提供就保持未知。构建路线与引物经过序列模拟，实验仍为 PLANNED/NOT_PERFORMED，不声称已验证可用或已实现敲除。

## 怎么读结果

先看`summary.md`及返回的实际文件入口。`result.json`保留完整计算结果，`context-snapshot.json`保留本次来源和范围。Construct正式DNA与订单使用同一次Core回执；Toolkit的文件回执只补核报告及输入版本，不增加DNA正确性裁判。

Trace开启时，`evidence-trace/index.html`和`report.md`展示实际过程。来源、理由、检查和文件保持对应，技术记录在独立文件中。泳道图记录执行顺序与声明；实线只表示程序核验输出与声明输入文件的SHA-256相等，其他关系用虚线，不认证科学支持、物理使用或因果。记录完整性、程序检查和实验科学结论分别表达。报告可从日志重建：

```text
python -X utf8 -B scripts/run_toolkit.py rebuild-report --trace-dir results/evidence-trace
```

Off/Observed/Full控制之后的采集；normal记录故障保留主任务结果，strict缺少所需记录准确停止/报告，已生成DNA文件不会被回滚。

## 当前范围

支持显式区域和材料下的供体计算准备、给定参考的PCR鉴别，以及提交实验记录的受限比较。参考序列不证明实验株基因型。SY14 URA3位点未被程序默认确定；局部PCR不证明全基因组消除；计算制备不等于湿实验成功。

当前包是本地候选。正式iGEM源码、Wiki和提交状态须由团队负责核查及提交。程序不能强制拥有任意文件权限的宿主只呈现受检文件。

## 来源和扩展

四个子Skill位于`kits/<name>/`，各自拥有SKILL.md、kit.json、脚本、来源规则、合成例子与源树测试。项目共享Context/样式及旧导入兼容入口位于`revival/`，不维护第二份Kit名单。命令入口位于`scripts/`；`vendor/dna-design-core/`是构建时从唯一上游源码复制的同版Core，修改上游再构建，不另维护算法。完整包只有一个顶层安装目录，不发布单Kit包，测试玩具不进入包。项目开发规范、测试与官方交付资料在源码仓库的`specs/`、`docs/`和`tests/`，不进入运行包。

Kit v2支持既有工具、线性Pipeline模板、必跑gate及逐行来源规则。CRISPR接入方向/PAM/自切gate与筛选规则；四个现有Kit未使用Pipeline模板。继承输入模板的Core诊断仍可能阻止正式交付，CRISPR不启用任何豁免。完整包的通用接口可通过`vendor/dna-design-core/scripts/run_kit.py list --kit-dir kits`查询；安装包契约位于`vendor/dna-design-core/references/kit-contract.md`，开发源码对应`snapgene-dna-design/references/kit-contract.md`。

MIT许可及依赖归属见[LICENSE](LICENSE)、[第三方来源](THIRD_PARTY_NOTICE.md)。程序计算和AI协助均需如实披露；实验或独立真人验证须有各自证据。
