# GitLab源码与版本交接

2026-10-11。**本轮只准备本地候选，不推送、合并main、部署Wiki或发布Release。** 官方规则及日期见[官方核对](official-requirements.md)。正式账号和最终提交由负责人亲自操作。

## 已核实状态

| 项目 | 当前事实 |
|---|---|
| 开发仓库 | GitHub `zoehanke/snapgene-dna-design`，分支 `codex/real-workflow-readiness-20260907` |
| 本轮基线/冻结 | Core2.2.1实施`7ebd0cc`、文档`fa0f3cb`；本轮实施冻结`9bc9aa3`，Toolkit0.1.0/Core2.2.2/Trace0.3.3。ZIP SHA `90F4BD9B9664CAF0C36FD3DBD8051A6DDA3DC37EA7975CC8C1D9D0A52547AF5F`，252 payload |
| 软件GitLab | [专属仓库](https://gitlab.igem.org/2026/software/tianjin/igem-tianjin2026)，本地remote名`gitlab`；匿名团队API已确认关联 |
| 官方源码 | main/HEAD为`241b12fcad038e9f56fac563438f717f38e40644`，树仅`.claude/`、`CLAUDE.md`、`LICENSE`、`README.md`，未包含当前软件 |
| CI准备 | 根`.gitlab-ci.yml`已准备：Python3.12.4、现有固定requirements-tested、共同测试入口及`tools/build_toolkit.py --out-dir dist`；本地YAML及实际CLI形状核对通过，远端GitLab CI未运行 |
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
