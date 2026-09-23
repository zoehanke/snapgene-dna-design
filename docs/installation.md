# 安装

Python 3.10+；本周期本机测试为 Windows/Python 3.12，其他平台结果只引用对应提交 CI，不能自动沿用到新改动。推荐独立环境，避免改动宿主自身 Python。

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -X utf8 -B scripts/check_env.py --json
```

macOS/Linux 使用 `.venv/bin/python`。`requirements-tested.txt` 保存本次核心依赖的精确受测版本，便于同平台复现；`requirements.txt` 是支持范围。可选预测模型另装 `requirements-optional.txt`，不是基础构建的必要科学步骤。

Primer3 通过 primer3-py 安装包中的真实可执行程序或 `PRIMER3_CORE` 发现。环境报告必须显示其实际可用。Cas-OFFinder/OpenCL 与桌面 SnapGene 分别安装，不把路径存在当成功运行。网络序列上传另需逐请求同意。

宿主使用 Skill 时复制完整目录，不能只复制 SKILL.md；相对路径依赖 core/scripts/schemas/references。`agents/openai.yaml` 提供宿主元数据，项目不自带模型或 API 服务。安装到宿主的具体路径及是否需重载依宿主版本；本次只验证隔离包，不覆盖你的现有 Codex/DSH 安装。

先执行[快速开始](quick-start.md)。失败先看[排障](troubleshooting.md)。
