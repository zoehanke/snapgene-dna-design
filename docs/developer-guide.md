# 开发指南

先读 AGENTS、对应 spec、当前计划和 history。检查 Git 状态，保留他人修改。复现用户问题后建立最小独立正反例，再改生产代码；同一示例变绿不是完成标准。

## 常用命令

```text
python -X utf8 -B -m unittest discover -s tests
python -X utf8 -B scripts/run_test_suite.py
python -X utf8 -B scripts/property_tests.py --quick --out-dir output/property
python -X utf8 -B scripts/run_scenario_suite.py --out-dir output/scenarios
python -X utf8 -B benchmarks/runtime.py output/benchmarks.json
python -X utf8 -B scripts/build_release.py . output/packages
```

发布 runner 要求真实 Primer3 测试启用。PowerShell：`$env:SNAPGENE_RUN_PRIMER3='1'`；bash：`export SNAPGENE_RUN_PRIMER3=1`。其他真实后端另需各自资源，不伪造 flag 代替程序。

项目没有配置全仓库 mypy/ruff 门限，也没有 JavaScript 构建器。Python AST/实际导入、`node --check evidence_trace/view.js` 和实际浏览器分别检查语法与交互，不把语法检查写成类型检查或 UX 验收。

## 调试

从用户入口向下跟踪：CLI→runtime/Recipe→工具→保存文件→验证→gate。同时读输入和输出，不只看返回布尔值。Trace 可提供日志，但它本身也要测失败；正常模式不能拖死已正确的 DNA 操作。

变更契约要同步 spec；说明原因写 history；执行证据写计划/结果。当前审计按用户要求只作本地提交，不自动推送远程。测试资料、密钥和临时环境不能入包。
