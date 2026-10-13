# GitLab源码与版本交接

2026-10-13字节核查补充：精选候选必须原字节继承官方`.gitattributes`，作为明确的最小外层例外，作用是控制checkout换行及声明二进制文件。Windows `core.autocrlf=true`曾使441条清单中的432个文件仅因LF转CRLF而哈希不符，原失败回执保留。禁止用换行归一化放宽FILE-LIST核查；修复后须从真实干净clone逐文件核原始字节、size和SHA，并重新冻结候选。源树大小、clone pack大小与官方quota分别记录。

2026-10-13续授权：安全风险修复与整合后的精选源码可推官方新候选分支。**不推或合并main、不部署Wiki、不发布正式Release。** 以下旧准备记录保留其日期和范围。 官方规则及日期见[官方核对](official-requirements.md)。正式账号和最终提交由负责人亲自操作。

## 已核实状态

| 项目 | 当前事实 |
|---|---|
| 开发仓库 | GitHub `zoehanke/snapgene-dna-design`，分支 `codex/real-workflow-readiness-20260907` |
| 本轮基线/冻结 | Core2.2.1实施`7ebd0cc`、文档`fa0f3cb`；本轮实施冻结`9bc9aa3`，Toolkit0.1.0/Core2.2.2/Trace0.3.3。ZIP SHA `90F4BD9B9664CAF0C36FD3DBD8051A6DDA3DC37EA7975CC8C1D9D0A52547AF5F`，252 payload |
| 软件GitLab | [专属仓库](https://gitlab.igem.org/2026/software/tianjin/igem-tianjin2026)，本地remote名`gitlab`；匿名团队API已确认关联 |
| 官方源码 | main为`0c764c6`，已有Toolkit0.1.0/Core2.2.2/Trace0.3.3候选源码；[精确流水线748177成功](https://gitlab.igem.org/2026/software/tianjin/igem-tianjin2026/-/pipelines/748177)。本轮版本尚未在main，不能借旧CI认证新版 |
| CI准备 | 官方CI已有Python3.12.4、wheel预备、八个互斥分片及构包。新版保留分片并合入准确通过/skip计数、JSON回执及即时失败详情；Node用于查看器真实JS语义检查。每个新候选提交必须核对自己的流水线 |
| Wiki | [独立Wiki源码](https://gitlab.igem.org/2026/tianjin)，不与软件仓库混用 |
| 未核实 | 写权限、Release完整列表、正式表单与上传回执；无tag响应不等于已查完所有Release |

官方模板要求软件源码在`main`，并说明Wiki Freeze自动生成评审Release。自动冻结不能代替提前上传、从官方仓库复现和回执核对。本机源码、GitHub CI、ZIP或受测安装均不是官方已接收证据。

## 候选目录与发布清单

保留既有开发Git历史，发布前本地归档。准备可审阅的软件源树，至少包含两个Skill源码、三个Kit、同版Core/Trace、公共README与安装/Quick Start、依赖固定文件、LICENSE/第三方notice、必要测试和可运行GitLab CI。独立Toolkit包在构建时包含同版底座，不在源码树维护第二套DNA实现。

候选同时记录：Toolkit/Core/Trace版本、源提交及未提交项状态、包SHA-256/文件清单、实际依赖/后端、独立包与宿主结果、计算案例和限制。私有DNA、实验原件、考官资料、凭据、编译程序和大媒体不随源码提交；公开演示材料须有分发依据。仓库须小于50MB，最终以官方仓库实际大小核对；当前本地Git对象约7.1MiB仅是准备依据。

本机`audit-output/genome-revival-toolkit-20261011/igem/`已准备逐文件源码清单、排除原因和大小记录。当前所选源文件低于50MB，具体字节以带时间的清单为准，不等于冻结源码或官方Git仓库大小。最终提交后重新生成；旧历史、公开文档链接和外部权属保留人工审定，不能只按路径过滤就宣称可任意分发。

源r1保留104条排除导致的链接缺口。r2新目录纳入38份必要且经有限DNA/凭据筛查的历史Markdown，99处不能分发的引用改为非点击内部记录说明并保留原引用；504文件、6.352MiB，零相对断链。独立本地Git没有remote，现行套件实际1202项中1179通过、23跳过、0失败，830.875秒；真实Primer3未skip，实际builder退出0。额外资源skip不计为成功；正式Linux/GitLab CI仍未运行。最终r3根据文档收尾SHA生成，只再核源码/252 payload、链接和必要入口，不重复同一全量。技术准备、许可批准及官方接收分开记录。

原代码采用MIT，官方软件模板当前Apache-2.0。整合时保留各部分来源和许可，团队确认原代码权属后决定顶层许可，不能用模板许可重新授权所有第三方。Wiki继续原CC-BY4.0 LICENSE，不删除或改成软件MIT。

## 负责人操作顺序

1. 审定本地候选、科学表述、许可、公开材料及AI披露。保存代码/包/评分冻结记录和本地历史备份。
2. 从官方软件仓库取得新工作副本，保留模板和远端历史。把审定源文件及来源提交映射作为正常提交/审查整合到`main`；不要force、mirror或覆盖旧历史。无需为交付而移植所有私有开发数据或强求两仓库tip相同。
3. 核对官方`main`内容、GitLab CI、README命令、仓库大小。重新从官方源码安装，核对实际版本和案例输出。GitHub CI不能代称GitLab CI。
4. 将审定Wiki正文、代码生成图和真实截图整合进Wiki现有源工程，维持`.gitlab-ci.yml`、固定依赖及原LICENSE；媒体上传iGEM托管，去掉外部运行请求。不要用外仓库`.git`覆盖Wiki历史。
5. 本人核对软件关联、Wiki标准页、Attributions/AI披露、奖项自荐与其他必需交付，保存真实回执。核对官方生成的评审快照，不能只等自动行为。

若另建公开tag/Release，保留原证据版本，不移动旧tag；下载资产须从实际产出包重新检查。源码、CI、包、安装、Wiki和回执各自记录，不能互相替代。

## 仅只读核对

```text
git remote get-url gitlab
git ls-remote gitlab HEAD refs/heads/main refs/tags/*
```

已有历史扫描仅覆盖有限秘密模式，不证明所有权属和隐私均合规。旧扫描记录保留在[工程审查归档](../archive/reviews/final-remediation-report.md)，当前外部资产边界见[归属](../attribution.md)。正式操作前由负责人审阅候选纳入内容。

## 2026-10-13精选新候选

范围为Core2.2.4、Toolkit0.1.1和Trace0.3.4，开发分支为`codex/crispr-skill-fixes-20261012`。官方候选分支为`codex/candidate-core-2.2.4-toolkit-0.1.1-trace-0.3.4-20261013`。按明确Git提交构造，不直接把开发工作树推到官方。

当前已按用户要求通过 Edge 网页提交 [42590dbe](https://gitlab.igem.org/2026/software/tianjin/igem-tianjin2026/-/commit/42590dbe27757fc377c6c256e161964a76dfb7ec)，没有 Git 远程推送或 main 操作。首次网页保存保留10个CRLF及1个额外LF，独立回读拒绝后正常追加修正提交；原失败保留，不做换行归一化验收。最新实际源 ZIP 与服务器干净 clone 的443文件/442条清单原字节全部相符，clone含Git元数据总容量7,993,922字节。最新[流水线752345](https://gitlab.igem.org/2026/software/tianjin/igem-tianjin2026/-/pipelines/752345) pending，项目没有在线执行器，未通过官方CI。当前结果与未完成事项由[日期处置表](public-risk-disposition-2026-10-13.md)统一记录。

2026-10-14用户说明官方不允许使用执行器；本轮不新增、注册或恢复执行器。最终任务页确认任务未启动，官方CI记为未执行、未验收；本地完整套件、服务器文件一致性与GitHub CI分别列示，不换算成官方通过。

同日进一步核查：公开 API 返回旧流水线748177的source为push、ref为main，10个任务由组执行器67成功完成；该执行器当前返回online。新候选752345同样已由push触发，但预备任务未开始、runner为空。main为protected，候选分支为非protected；两者差异只提示需要核对执行器限制，尚不证明保护规则就是阻断原因。匿名执行器列表401和未返回的配置字段表示未知，不代表没有执行器或禁用CI。先前用户说明保留来源，不再将其当平台规则已独立证实。

用户明确授权：若官方CI确实无法执行，按GitHub实际检出同一官方提交的CI、本地完整套件及逐文件回读验收后续准备；报告必须保留“官方 GitLab CI 未执行”。新GitHub工作流的控制SHA与受测官方SHA分别记录，逐文件回执与受测提交绑定。若找到符合官方规则的候选触发方法，优先核实并尝试；不改main、不降低执行器保护或索取凭据。

替代证据已取得：[GitHub实际官方源码CI](https://github.com/zoehanke/snapgene-dna-design/actions/runs/38432148990)的控制提交为c07295d，实际检出的受测源码为完整官方42590dbe。八个互斥分片共1271项，1245通过、26跳过、0失败/错误，真实Primer3门槛通过；每个分片都保存443文件的原始哈希回读回执。原本地冻结套件仍为1251通过/20跳过，平台差异单列，不相加或改写来源。独立冻结源到真实服务器克隆的443行CSV另保留，原网页提交11项失配反例仍退出失败。官方GitLab752345尚未执行，组执行器的保护配置仍未知，浏览器操作通道故障阻断登录页面核实；不将未知归因为官方禁令。

两内层程序、公共测试/必要tools闭包、CI、固定依赖、LICENSE与README为主体。AGENTS、开发CLAUDE、specs、开发计划/归档、results、题库、用户DNA、个人路径、稿件和大媒体排除。官方main原有CLAUDE/.claude模板按原字节继承，不用开发副本覆盖；许可文本保留来源。

外层额外项逐项说明：LICENSES和THIRD_PARTY_NOTICE保留上游/模板许可；SOURCE/VERSION/VERSIONS/FILE-LIST及选择回执绑定软件版本、源码及逐文件哈希；自包含examples/run_demo.py让README的完整640 bp合成流程可复现，不复制outer DNA或开发稿。其余工具按实际测试调用闭包选择，publisher自身开发测试不进入官方运行测试树，并记排除理由；既有运行要求、阈值与资源skip条件不降低。

工具`tools/build_official_candidate.py --source-commit <commit> --official-base-dir <clean-official-clone> --candidate-branch <new-candidate-branch> --out-dir <new-export-dir>`输出逐文件纳入/排除与变换理由。`--working-tree`仅诊断，不能称冻结。clean clone核查当前树、软件清单、固定依赖/许可、实际入口及物理Git对象大小；源树payload大小与仓库quota分开，不能用前者冒充后者。不得覆盖既有输出或混入符号链接。

Wiki默认口径：记录执行顺序与作者声明；程序支撑关系仅限真实输出文件与另一步骤声明输入文件的SHA-256相等。它不证明实际物理使用、科学支持或因果。新截图用独立合成公共流程和真实离线浏览器，不复用未批准图或私人材料；两份handoff稿各自记录实际软件文档哈希与路径差异。

GitHub历史只做私有备份和隔离clone演练，绝不执行远端重写、force push或删分支。稿件当前树取舍已获明确移出授权，历史是否改写仍由用户另行决定；缓存/fork不能保证撤回。Attributions、Best Software表单、Wiki发布、权属和AI披露终审保持真人责任。精确候选提交和流水线结果以本次实际回执为准，不借旧main或开发仓库CI。
