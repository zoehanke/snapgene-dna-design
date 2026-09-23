# GitLab 迁移准备

本地开发分支为 codex/real-workflow-readiness-20260907，GitHub origin为 zoehanke/snapgene-dna-design。基线有main、recovery分支和v1.0.0标签；所有历史保留。公开 `gitlab.igem.org/2026/tianjin` 是Wiki仓库，不把它当已提交的软件仓库。专属软件URL仍需团队确认。

## 本轮已做

只读检查 remotes/branches/tags/对象大小/忽略规则/追踪文件；本轮没有新增remote、推送、发布或表单操作。待确认资产列于[attribution](../attribution.md)。本机用户DNA/环境/生成日志不会因Git忽略而自动从旧历史消失，因此迁移前还要检查历史。

本轮扫描864个不超过2MB的可达历史blob，私钥、GitHub/OpenAI token三类模式未命中；[结果](../../results/engineering-audit-20260922/history-secret-scan.json)。这是有限模式核查，不能证明历史中没有任何秘密或未授权生物数据；迁移前的权属审核仍保留。

## 获授权后的操作

1. 在官方Dashboard创建/确认专属软件仓库、权限和目标分支；确认已获许可内容及历史。
2. 记录所有本地branch/tag及tip；`git bundle create ../snapgene-history.bundle --all` 保存离线恢复副本。
3. 使用本地最终仓库克隆迁移副本，保留完整Git对象；不要仅上传ZIP，也不要 squash/filter-repo 清理历史。
4. 在迁移副本添加已确认的 iGEM remote；只推明确审核的分支和标签，不使用会删除远端refs的 `push --mirror`，不force覆盖对方已有工作。
5. 用 `git ls-remote` 对比目标refs和本地commit，重新克隆官方仓库，执行公开quick-start及测试，再核对Wiki链接和Dashboard回执。

带参数的示意命令（不能在URL未确认时执行）：

```text
git remote add igem <confirmed-software-repository-url>
git push igem codex/real-workflow-readiness-20260907:reviewed-development
git push igem tag v1.0.0
```

具体是否把审定开发分支合入官方main、哪些recovery refs需保留，由所有者在迁移清单中确定。完整历史中的代码/图片/外部序列权属未清楚时先解决权限，不自动重写过去或宣称迁移完成。
