# DNA Skill 测试题库

2026-10-02。**第1至9题执行材料已齐；第10题缺原始完整供体，不发题。**本轮补材料，不运行题库，也不把输入核验当成软件测试通过。

## 发题与检查

[评分规则](scoring-v0.1.md)和[检查者评分表](../../benchmarks/host-readiness-v0.1/scores-template.csv)供下一轮使用。首轮为探索性检查，材料通过不等于软件通过。

- [执行材料包 v0.3](../../snapgene-dna-design/dist/dna-skill-test-materials-v0.3-executor.zip)：九题完整源文件和自然请求。每次只提供当前题材料，不给整个仓库或检查者目录。
- [检查者材料包 v0.3](../../snapgene-dna-design/dist/dna-skill-test-materials-v0.3-reviewer.zip)：原始输入、来源映射、编号核对、已有参考答案和验收说明。不要放在执行AI可读的位置。
- [执行题面](executor-tasks-v0.2.md)描述用户目标；[人工答案册](human-answer-key-v0.2.md)描述判断标准；[检查者说明](reviewer-notes-v0.2.md)保存原名和参考线索。
- 第4、8题先发`request.md`。第一轮真正交付后再发送`followup.md`，第二轮以第一轮实际产物继续，不从母本重做。
- 必要背景写进自然请求，只有实际需要的接口规则、编号或材料冲突另附说明。v0.3执行包不再强制inventory。

## 本次补齐

| 题号 | 已补输入 | 单题包 |
|---|---|---|
| 4 | 两份URA3骨架、六份完整启动子/报告/终止子供体 | [下载](../../snapgene-dna-design/dist/dna-skill-test-T04-materials-v0.3.zip) |
| 7 | 完整His6-MBP-TEV骨架、完整sfGFP供体、原标签接口冲突说明 | [下载](../../snapgene-dna-design/dist/dna-skill-test-T07-materials-v0.3.zip) |
| 8 | 完整红荧光母本、未编辑编号参考、两轮请求、编号规则 | [下载](../../snapgene-dna-design/dist/dna-skill-test-T08-materials-v0.3.zip) |
| 9 | 两份完整定位探针供体、URA3骨架、原注释缺口及功能说明 | [下载](../../snapgene-dna-design/dist/dna-skill-test-T09-materials-v0.3.zip) |

## 材料真实性与限制

DNA没有修改、增删、拼接或用相似序列替代。新增14份题目输入，连同原27份共41份完整GenBank；匿名化保留每项feature的类型、坐标、方向、提取序列和关键功能属性。原文件另存。

两份pRS骨架取得官方SnapGene文件，pRS416与NCBI U03450.1全序列交叉一致。其余新增部件来自原官方部件ZIP。第7、8、9题取得官方公开完整viewer的序列和功能注释，再作格式转换；不是AI编写DNA，也不是假称下载到作者原始GB。[本轮来源核对](material-completion-v0.3.md)

完整公开序列和既定突变组合仍可能被识别；匿名化减少快捷答案线索，不证明模型此前没见过材料。源文件本身的注释冲突和缺口保留，不能为了测试顺利而预先修成目标。

旧v0.1是历史选题资料，旧v0.2包是五题版本，均保留。当前发题以v0.3材料和本页状态为准。
