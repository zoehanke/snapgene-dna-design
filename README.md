# SnapGene DNA Design 项目工作区

这个仓库保存Skill源码和开发资料。Git根与开发工作区在此目录。

| 使用场景 | 入口 |
|---|---|
| 安装、使用Skill | [Skill README](snapgene-dna-design/README.md) |
| AI执行DNA任务 | [SKILL.md](snapgene-dna-design/SKILL.md) |
| AI开发与修复 | [AGENTS.md](AGENTS.md) |
| 产品契约 | [Core spec](specs/core-skill.md)、[Evidence Trace spec](specs/safety-module.md) |
| 开发文档与当前工作 | [统一入口](docs/README.md)、[当前交接](docs/development-plans/README.md) |
| 项目为何演变到现在 | [History](docs/history.md)、[Changelog](CHANGELOG.md) |

`snapgene-dna-design/`是Skill根；`docs/`、`specs/`、`tests/`、`benchmarks/`和`tools/`是开发资料。打包只取Skill目录，不把开发资料、题库、评分工具或历史解题记录交给执行AI。

从项目根执行：

全量测试需启用真实Primer3。PowerShell先设置`$env:SNAPGENE_RUN_PRIMER3='1'`，bash使用`export SNAPGENE_RUN_PRIMER3=1`。

```text
python -m pip install -r snapgene-dna-design/requirements.txt
python -X utf8 -B tools/run_test_suite.py
python -X utf8 -B tools/build_release.py snapgene-dna-design output/packages
```

本次目录迁移保留历史Git对象及原材料；既有本机产物仍在Skill目录内的`output/`、`dist/`，属于忽略项，不进入运行包。
