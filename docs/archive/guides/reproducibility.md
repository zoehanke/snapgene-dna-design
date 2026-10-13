# 复现

本轮基线为 b87a1d8；新结果对应最终本地提交与工作树状态，记录于[最终报告](../reviews/final-remediation-report.md)。环境在 results/engineering-audit-20260922/，原始本机诊断留 output/audit-20260922/。后者不是可发布数据集。

先用 requirements.txt；同平台精确重复可使用 requirements-tested.txt。该文件固定核心依赖及当前实际需要的传递依赖，不把 Windows/Python 3.12 的环境说成所有平台通用锁文件。可选 Torch/模型/OpenCL 有单独版本和可用性。

合成测试固定随机种子，用源碱基身份、实际文件读回和独立要求作预期。参数回放可复现程序结果，不能复现或证明宿主模型内部理由。Trace 保存事实与版本，确定性重建测试跨进程比较。

## 发布源选择

Git checkout 默认只打包被跟踪文件的当前内容。新增代码先经审核再纳入索引；本地用户DNA、秘密和生成目录不应跟踪。非 Git 树需要审核过的 JSON 相对文件清单：

```text
python scripts/build_release.py source-directory output/packages --source-list reviewed-files.json
```

从已有发行包重打包使用其 RELEASE-MANIFEST。禁止路径越界和文件符号链接；`.env` 不作为发行源码。默认打包不改开发 manifest。生成包仍需运行 check_redistributable 和解包测试；内容排除不是法律许可证明。

本轮不改变已安装的 Codex/DSH 包，也不推送远程。另一团队复现时先用公开合成输入，再替换成有权使用的实际材料。

2026-09-22 对 requirements-tested.txt 的13个精确核心版本查询 [OSV API](https://google.github.io/osv.dev/post-v1-querybatch/)，未返回已知条目，原始摘要在 [dependency-advisories.json](../../../results/engineering-audit-20260922/dependency-advisories.json)。这不覆盖任意可选环境、未知漏洞或手工二进制，也不证明许可证合规。未因此盲目升级依赖。
