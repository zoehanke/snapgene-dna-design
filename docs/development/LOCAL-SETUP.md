# 本地使用说明

## 只使用这个目录

`D:\codex_project\github\snapgene-dna-design`

这里是唯一开发目录。不要在 `archive`、`output` 或 `audit` 中修改代码。

## 当前状态

- 版本：`0.9.1-dev1`
- 状态：开发基线，不是 RC，不是正式版
- 当前基线存在三个独立审查指出的 P0 类问题，见
  `BASELINE-STATUS.md`
- 本地 Git 已初始化，当前没有远程仓库，也没有执行推送

## 第一次检查

在 PowerShell 中进入目录后运行：

```powershell
python -X utf8 -B scripts\quick_validate.py
python -X utf8 -B scripts\check_env.py
```

完整依赖写在根目录 `requirements.txt`。缺少依赖时，环境检查或
SnapGene `.dna` 写出测试会失败，不能把这种失败解释为代码通过。

## 目录含义

- `agent/`：自然语言任务入口
- `core/`：统一任务契约、执行、验证和正式产物闸门
- `planning/`：任务规划
- `scripts/`：命令行工具
- `tests/`：测试
- `fixtures/rich/`：可公开的合成夹具
- `docs/`：架构、开发和生物学审查文档
- `third_party/`：带许可证和哈希记录的可选模型文件

真实 DNA、发布包和审查证据不放进这个 Git 仓库。
