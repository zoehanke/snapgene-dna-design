# 安装

Python 3.10+；本周期本机测试为 Windows/Python 3.12，其他平台结果只引用对应提交 CI，不能自动沿用到新改动。推荐独立环境，避免改动宿主自身 Python。

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -X utf8 -B scripts/check_env.py --json
```

macOS/Linux 使用 `.venv/bin/python`。`requirements-tested.txt` 保存本次核心依赖的精确受测版本，便于同平台复现；`requirements.txt` 是支持范围。可选预测模型另装 `requirements-optional.txt`，不是基础构建的必要科学步骤。

Primer3 通过 primer3-py 安装包中的真实可执行程序或 `PRIMER3_CORE` 发现。环境报告必须显示其实际可用。Cas-OFFinder/OpenCL 与桌面 SnapGene 分别安装，不把路径存在当成功运行。网络序列上传另需逐请求同意。

宿主使用 Skill 时复制完整目录，不能只复制 SKILL.md；相对路径依赖 core/scripts/schemas/references。`agents/openai.yaml` 提供宿主元数据，项目不自带模型或 API 服务。更新已有安装时先备份，使用已验证发行包替换，不能合并残留的旧代码。用清单 SHA-256 核对安装文件；本机 `INSTALL-SOURCE.json` 记录包哈希、源码提交、版本和已通过环境检查的 `python_executable`。宿主对后续调用使用同一解释器，避免 PATH 指向另一份缺依赖的 Python。

先执行[快速开始](quick-start.md)。失败先看[排障](troubleshooting.md)。
