# SnapGene DNA Design 项目工作区

这个仓库保存Skill源码和开发资料。Git根与开发工作区在此目录。

| 使用场景 | 入口 |
|---|---|
| 安装、使用Skill | [Skill README](snapgene-dna-design/README.md) |
| Genome Revival项目专用Skill | [Toolkit README](genome-revival-toolkit/README.md)、[Toolkit入口](genome-revival-toolkit/SKILL.md) |
| AI执行DNA任务 | [SKILL.md](snapgene-dna-design/SKILL.md) |
| AI开发与修复 | [AGENTS.md](AGENTS.md) |
| 产品契约 | [Core spec](specs/core-skill.md)、[Evidence Trace spec](specs/safety-module.md)、[Toolkit spec](specs/genome-revival-toolkit.md) |
| 开发文档与当前工作 | [统一入口](docs/README.md)、[当前交接](docs/development-plans/README.md) |
| 项目为何演变到现在 | [History](docs/history.md)、[Changelog](CHANGELOG.md) |

`snapgene-dna-design/`维护通用Core Skill；`genome-revival-toolkit/`维护复用它的项目专用Skill。`docs/`、`specs/`、`tests/`、`benchmarks/`和`tools/`是开发资料。包排除开发资料、题库、评分工具和历史解题记录。

当前官方候选已上传；官方 GitLab CI 未执行。GitHub测试、本地完整套件和官方源码逐文件回读分别记录，不能代称GitLab通过。实际候选、受测提交及未确认的执行器限制见[源码交接](docs/igem/gitlab-migration.md)。

从项目根执行：

全量测试需启用真实Primer3。PowerShell先设置`$env:SNAPGENE_RUN_PRIMER3='1'`，bash使用`export SNAPGENE_RUN_PRIMER3=1`。

```text
python -m pip install -r snapgene-dna-design/requirements.txt
python -X utf8 -B tools/run_test_suite.py
python -X utf8 -B tools/build_release.py snapgene-dna-design output/packages
python -X utf8 -B tools/build_toolkit.py --out-dir output/toolkit-package
```

本次目录迁移保留历史Git对象及原材料；既有本机产物仍在Skill目录内的`output/`、`dist/`，属于忽略项，不进入运行包。

英文纠错报告可从完整源码检出复现。构造器独立决定预期序列；脚本调用公开入口，保留初次失败及纠正后的实际返回，并重新读取文件字节核对哈希关系。输出目录须新建，避免覆盖旧失败。它们是合成工程示例，不是自主宿主或真人试读结果。

```text
python -X utf8 -B examples/generate_evidence_inputs.py --out-dir output/synthetic-corrections
python -X utf8 -B examples/run_evidence_example.py --case core-guide --inputs output/synthetic-corrections
python -X utf8 -B examples/run_evidence_example.py --case kit-construct --inputs output/synthetic-corrections
python -X utf8 -B examples/run_evidence_example.py --case kit-guide --inputs output/synthetic-corrections
```
