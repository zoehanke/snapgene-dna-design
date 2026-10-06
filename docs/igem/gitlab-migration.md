# GitLab源码与版本交接

2026-10-06更新。本地开发分支为`codex/real-workflow-readiness-20260907`，GitHub origin为`zoehanke/snapgene-dna-design`。已有`gitlab` remote指向[专属软件仓库](https://gitlab.igem.org/2026/software/tianjin/igem-tianjin2026)；它与`gitlab.igem.org/2026/tianjin` Wiki仓库不同。

只读`ls-remote`确认软件仓库HEAD/main为`241b12fcad038e9f56fac563438f717f38e40644`，未发现远端tag。源码树内容、当前Release列表、实际写入权限、Dashboard关联与自动冻结机制尚未确认。配置URL和存在main不等于受测软件已发布。本次只更新日程和交接，未推送GitLab、合并main或发布Release。

2026-10-07进一步只读查询GitLab API：main根目录仅`.claude/`、`CLAUDE.md`、`LICENSE`、`README.md`，未见当前Skill源码目录。Release API返回403，未据此断言Release数量或写入权限。本队README明确要求源码进入本仓库main，并称Wiki Freeze时自动创建评审Release；Dashboard实际任务仍未核实。当前2.1.0测试包/DSH安装与dd293a8实施提交绑定，c921c00为后续开发记录提交且精确CI成功；下一步准备审定源码整合，不将已有GitHub/本机结果称为官方仓库发布。

## 版本交接

具体日期与分工见[单人日程](../development-plans/real-task-readiness-human-plan.md)，不在这里再维护一套日历。准备2.0.2基线归档、修复候选版和最终参赛版：基线如实列开发回归与第2题已知失败；候选用于下载和宿主重测；最终版引用冻结审定代码。版本号随实际兼容性变化确定，公开日期与提交历史如实记录。

每版记录目标commit/来源、源码、可安装包、变更、实际检查及未解决项。GitLab [Release](https://docs.gitlab.com/user/project/releases/)关联tag，可附发布说明和下载资产；只有tag不代表安装和任务验收完成。候选修正后发布新版本，不移动已用作证据的旧tag。

最终审定源码要进入官方main；单独的开发分支或下载ZIP不能代替官方源码交付。官方main已有独立历史时，通过正常审查整合，保留模板及已有工作；记录它与GitHub来源的内容映射，不要求两个tip相同。不force、不mirror、不删除旧历史。

发布准备在修复期间进行。推送指定refs、main整合和公开Release按当时已有明确授权执行；排期更新本身不执行这些操作。自动产生评审快照的模板说明需与本队Dashboard实际规则核对，不能等待未确认的自动行为代替提交。

## 历史准备记录

此前准备仅检查remotes/branches/tags/对象大小/忽略规则/追踪文件；当时没有新增remote、推送、发布或表单操作。待确认资产列于[attribution](../attribution.md)。本机用户DNA/环境/生成日志不会因Git忽略而自动从旧历史消失，因此发布前还要检查纳入内容和历史。

本轮扫描864个不超过2MB的可达历史blob，私钥、GitHub/OpenAI token三类模式未命中；[结果](../../results/engineering-audit-20260922/history-secret-scan.json)。这是有限模式核查，不能证明历史中没有任何秘密或未授权生物数据；迁移前的权属审核仍保留。

## 获授权后的操作

1. 对已存在的软件仓库核对源码、模板、Dashboard关联、权限和目标refs；确认已获许可内容及历史。
2. 记录所有本地branch/tag及tip；`git bundle create ../snapgene-history.bundle --all` 保存离线恢复副本。
3. 使用本地最终仓库克隆迁移副本，保留完整Git对象；不要仅上传ZIP，也不要 squash/filter-repo 清理历史。
4. 使用已存在并核对过的`gitlab` remote，只推明确审核的分支和标签；审定内容按获准流程整合到main，不使用会删除远端refs的`push --mirror`，不force覆盖已有工作。
5. 用 `git ls-remote` 对比目标refs和本地commit，重新克隆官方仓库，执行公开quick-start及测试，再核对Wiki链接和Dashboard回执。

只读核对示例；写入操作以审定refs和已有授权为准：

```text
git remote get-url gitlab
git ls-remote gitlab HEAD refs/heads/main refs/tags/*
```

具体整合方法及哪些recovery refs纳入发布，在审定清单中确定。源码、tag、Release、包、GitLab对应CI和真实下载检查通过后分别记录；GitHub CI不表述为GitLab CI。完整历史中的代码/图片/外部序列权属未清楚时先解决，不自动重写过去或宣称迁移完成。
