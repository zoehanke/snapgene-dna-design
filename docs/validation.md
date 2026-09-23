# 验证范围

验证目标是：实际源与参数能形成指定序列；特征与引物未静默丢失；无效要求不能正式交付；Trace不能把声明/旧文件变成已验证事实。正式实验成功率、宿主适用性、AI动机和生态安全不在这些程序检查内。

## 输入与判据

- 独立合成反例：代码生成序列，预期由源碱基、切点、链向和用户约束计算。正确/错误两侧均测试。
- 公开rich/synthetic fixtures：用于格式和几何，不把标签当功能。
- 外部pBP/私有SnapGene材料：只作明确的本地回归，许可和是否随包分发分开。
- 文献启发90场景：40 executed、11 partial-analysis、39 blocked-as-designed；不是90个实验构建成功。

## 本轮实证

最终完整本机回归：927项全部通过、无跳过；启用全部可用真实后端及在线检查。初次完整回归未配置Cas-OFFinder；随后安装官方2.4.1/3.0.0b3并实跑，含两个模型与3项真实Cas-OFFinder的27项全部通过。单独在线NCBI/Primer3相关32项通过。公开属性测试6600例、12个mutation均符合各自断言。完整日志保留在output/audit-20260922，公开摘要见results/engineering-audit-20260922。

Core反例覆盖异常仍verified、伪造plan元件/空features、源注释丢失、格式读取、负链及同源臂；辅助测试覆盖碱基不变式、反向read、短局部偶合、拒绝前状态不变与假成功；Trace覆盖版本、文件前态、脱敏、关系归属和真实失败。

真实桌面程序自动往返：两个named合成构建的序列、拓扑、特征均保留。SnapGene额外写入默认codon_start/transl_table，strict=false，不称无损；[机器记录](../results/engineering-audit-20260922/snapgene-roundtrip.json)。这是程序转换证据，不是操作者对所有产品的人工查看。

## 完整可重复演示

```text
python -X utf8 -B scripts/demo_engineering_cycle.py --out-dir output/demo-new
```

预设同义密码子任务，实际运行inverse-PCR Recipe，正式产物与原DNA独立比较并核对翻译/源标签，四份交付文件关联到实际操作；再从记录生成报告。该演示明确标为预设方案，未伪装成现场AI盲测或湿实验。

## 尚未支持的结论

没有新增独立真人试读、跨模型意图可靠性或实际湿实验。旧pET/Chr1源注释问题有详单，不能整体豁免或改名求绿。Coverage是另一项诊断，具体结果见[testing](testing.md)；源码被执行不等于科学结论正确。
