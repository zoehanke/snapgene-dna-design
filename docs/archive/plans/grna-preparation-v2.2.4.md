# gRNA实验构建路线

2026-10-13授权，基线4897f2f/Core2.2.3，沿现有独立开发分支，不动main或原工作区改动。

原行为：replace_grna_spacer直接改20 nt，只返回sequence_model。公共入口确认没有preparation；finalize_workflow拒绝缺失反应链是正确行为。缺陷在于工具未给可执行制备方案，不能把拼接正确字符串当作制备证明。

泛化依据：任意有确定启动子出口/scaffold及20 nt间隔的环状质粒，都可按真实窗口外扩PCR、用新20 nt尾部恢复缺口并环化；设计须基于实际Tm、完整oligo结构及唯一结合。DNA文件不证明母模板甲基化、实际PCR或实验成功。

范围：复用design_overhang_primers、simulate_pcr、ligate_fragments、rotate_sequence；默认设计inverse_pcr，可显式sequence_only。先生成计划/引物，再从原模板与实际完整引物独立模拟并与编辑模型逐位比较。最终分子引用真实模拟链，使现有门禁识别计算preparation_model；不改门限或豁免模板ERR。

NEB Q5/KLD手册2.0_7/20提供背靠背、5-prime添加、KLD与标准脱盐方法；IDT RUO23-1848_001建议克隆/突变考虑PAGE，作为携带20 nt尾部引物的可选纯化建议而非伪造40/60 nt绝对阈值。Tm条件随输出记录；独立Biopython Tm_NN及公开SantaLucia热力学方法交叉核查。

验收：至少两种独立模板/新spacer，正反转录及跨原点；重复spacer警告/重复核心拒绝；poly-T不改序列；高GC不可行不硬做；真实run_step、Trace、finalize与完整订单/文件读回。A/D/E为已知题开发者回放，原失败保留仓库外；不算自主或陌生题成功。原CI账单阻断在本轮重查，不改账号额度。

## 本轮实现与验收

Core2.2.4实现默认inverse_pcr计划及独立模拟；sequence_only可显式保持旧编辑范围。复用原引物搜索、PCR、连接、旋转，最终分子仅在模拟逐位相等后引用其反应祖先。Trace自动捕获这些真实程序调用与PLANNED/NOT_PERFORMED标签；未修改门禁、Trace框架或其他业务模块。

| 检查 | 实际结果 |
|---|---|
| 新回归 | 6项通过，含两组独立模板/不同spacer成功、反向cassette/跨原点、重复spacer提示/重复核心拒绝、poly-T不改、高GC/重复不可行、纯序列不放行及真实CLI最终交付/订单/Trace |
| 独立Tm | 公开Biopython 1.88 Tm_NN和按公开Allawi/SantaLucia常数手写NN/熵盐修正公式交叉核查；手算与Bio结果到6位一致，工具Tm误差≤0.6°C；实际方法/浓度进入输出和设计说明 |
| 原2.2.3范围 | 15项通过；显式sequence_only只隔离原序列/注释测试责任，不改变原断言；默认制备另有公共交付用例 |
| 已知A/D/E回放 | 三项计划PLANNED，PCR/环化模拟PASSED、反应链无缺口、完整oligo质量PASSED，逐位仅指定20 nt替换；源文件指纹未变，原失败保留仓库外 |
| 原模板门禁 | 仍因继承lacZα CDS错误拒绝整体交付；既有validator会把CDS失败传递给综合preparation状态，但details中的链缺口为0且oligo质量通过。独立有效模板四范围全部通过并导出正式计算交付，不称坏模板已放行 |
| 旧A短核心 | 在原诊断条件Na50 mM、Mg0、dNTP0、总oligo200 nM复算20 nt=46.1706°C、28 nt=57.1545°C；新设计使用共享PCR模型条件，数值不直接混用。实际A选正向尾部、D/E选反向尾部，长度/Tm/选择失败理由均保留 |
| 冻结全量 | SNAPGENE_RUN_PRIMER3=1，1223项中1202通过/21跳过/零失败，622.912s；真实Primer3 skip门禁通过。没有源码边跑边改 |
| CLI烟雾 | 95通过/零失败 |
| 独立包 | v2.2.4 redistributable清单/受限材料检查通过；仓库外解包清空PYTHONPATH后重复A/D/E公共入口与实际候选文件检查通过；不含用户DNA/开发测试 |
| Trace三档 | 包内Off/Observed/Full实际产品、检查、完整引物订单、quality、design及最终三格式文件字节一致 |
| 文档 | spec、SKILL、签名、架构、测试、README与历史按职责更新；本地链接检查通过 |

原失败：初轮新测试3 failures/4 errors为缺路线/新参数；第一次实现后2 failures是检查者错误限制只能反向尾部以及把现有订单列tm_C误称binding_core_tm，改为用户要求的任一尾部及实际表格式，保留独立DNA目标/三步重算要求。首轮真实回放检查器误把综合preparation状态与链证据等同，原日志保留；按既有validator字段分别核查，不改程序让错误模板放行。

已验证软件公共入口、模板结合/Tm/结构计算、文件一致性与门禁行为。PCR和环化只做序列模型模拟；DpnI/KLD化学操作与效果只是有来源的计划，没有做湿实验、母模板甲基化检测、转化、实际测序、gRNA活性或全基因组脱靶。未开展陌生题保留评测；开发者回放与合成回归不计原宿主独立成功。

本地实现/验收结束，推送现有独立开发分支codex/crispr-skill-fixes-20261012；main、原工作区改动与现用安装不变。精确提交CI须重查；前序账单限制未解除时，记录未启动而不是测试通过。
