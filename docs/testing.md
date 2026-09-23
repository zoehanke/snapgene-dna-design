# 测试与结果

基线 b87a1d8：845项，832通过、13跳过。发布runner正确地因未开启真实Primer3项目而失败；不能拿unit绿色替代release gate。单独开启相关开关后原32项通过31、1跳过。

重新打开验收后的完整回归：937项全部通过、无跳过，1697.872秒，包含覆盖统计开销，不是用户任务运行时间。实际启用Primer3、Cas-OFFinder v2/v3、两个模型及在线检查；此前893项/7跳过是尚未启用全部后端的中间结果。原错误CDS降级后通过的断言被纠正为保留CDS并拒绝；源码和失败材料保留。短core失败的mock现在检查坏pair不被使用以及实际可行替代pair，而不要求有解任务永远失败。

```powershell
$env:SNAPGENE_RUN_PRIMER3='1'
python -X utf8 -B scripts/run_test_suite.py
python -X utf8 -B scripts/property_tests.py --out-dir output/property
python -X utf8 -B scripts/mutation_tests.py --out-dir output/mutation
python -X utf8 -B scripts/run_scenario_suite.py --out-dir output/scenarios
```

每项命令的退出码和内部状态都要读。场景runner、inspect、convert、batch发生失败现会返回非零；不会把打印了error但exit0误算成功。Mutation工具已从旧转发文件定位到真实Core源码，先证明未修改的检查通过，再测试mutant，12/12捕获；未降低90%阈值。

新增工程测试分为core/trace/auxiliary/release和planning restriction，各从实际接口或必要窄seam验证，不以同一被测函数的返回值生成参考答案。对外部不可用环境保留skip/unavailable；无私有文件时不伪造数据。

## Coverage

本轮修正了漏测Core/Trace、同名模块混淆及行/分支百分比混算。f6b5904曾仅52/54达标；继续修复旧预览并取消覆盖运行少跑场景后，**54/54达标，总门槛PASS**，所有执行套件退出0。原阈值保留；[当前机器结果](../results/engineering-audit-20260922/coverage-summary.json)包含各模块明细。

原失败记录在output/audit-20260922/coverage-closed，关闭结果在coverage-r3，包含完整日志与coverage.data。冷导入修正另跑9项针对性回归通过。跨平台远程CI仍未运行；本机通过不能替代云端矩阵。

## 其他检查

公开包在仓库外、仅安装核心依赖的环境中完整运行909项：897通过、12跳过，无失败。必需Trace/PCR契约使用公开合成材料；两项原pBP材料集成单独保留。初次包的13处缺文件错误已修，原日志保留，未靠整组跳过掩盖。

Python AST、JS语法、MD链接、用户入口、UTF-8中文路径、隔离环境安装和发行包校验分开记录。没有设置mypy/ruff等全项目类型/lint工具，因此不声称这类门限通过。没有本轮远程CI，因为用户禁止推送；旧b87 CI只属于旧提交。
