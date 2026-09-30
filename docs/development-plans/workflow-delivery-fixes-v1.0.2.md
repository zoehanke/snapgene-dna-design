# 交付缺陷修复

目标版本 v1.0.2；文档 r1；2026-09-30；状态：源码修复与回归通过，独立包及安装验收中。
前序：[工程修复](../remediation-plan.md)、[实用性修复](workflow-phase-3-usability-repair-v0.3.2.md)。契约：[Core](../../specs/core-skill.md)、[Trace](../../specs/safety-module.md)。分支 `codex/real-workflow-readiness-20260907`，不修改 main。

## 本轮范围

| 问题 | 处理与验收 |
|---|---|
| Codex 安装旧于当前源码 | 完成修复后构建公开包，在独立目录运行，备份旧安装并更新；校验来源提交、清单和实际文件 |
| 酶切裁剪丢失部分 CDS/引物语义 | 已用合法独立源与实际 digest 复现；复用已有记录裁剪，保持序列、链向、部分注释、相位和原源不变 |
| pET/Chr1 正式交付阻塞 | 原失败输入保留；区分程序裁剪错误、明确的蛋白片段和源注释错误。不得自动换遗传密码表、延长 CDS 或删除错误注释 |
| Windows 交付/桌面转换异常 | 通过实际交付、同目录竞争及桌面转换检查复现；只修有明确根因的故障，未复现不写已修复 |

顺序：复现与独立反例 → 根因修复 → 原始公开 CLI 回归与文件检查 → 适用全量测试 → commit → 独立包运行/安装 → push 开发分支及核验 CI。远程连接失败须记录，不能将本机结果当 CI。

宿主任务理解、Trace 提示对照、真人阅读和 Benchmark 留待真实宿主验收；本轮固定参数回放仅为软件回归。Phase 4、比赛提交和当前聊天索引不在本轮范围。

## 实际结果与交接

### 已完成源码与材料回归

- 独立合法 CDS 经实际双酶切后失去 partial、相位及正确翻译归属；截断引物仍被标成完整 primer_bind。反例先失败，复用 `slice_record_interval` 后通过。Type IIS 使用本次反应显式拓扑，FASTA 环状载体的原 CLI 回归通过。没有按 GFP/CDC15 名称或坐标特判。
- 明确 `product` 为蛋白标签或蛋白酶切割位点时采用已有部分蛋白检查；错误翻译、错误完整 CDS、未知碱基仍拒绝。共6项新的注释回归。
- 两次真实 `.dna` 交付竞争同一目录复现 WinError 5。原子提升失败且目标已存在时报告 `GATE_AUTHORITATIVE_ALREADY_EXISTS`；胜出文件/清单哈希正确，失败只清理自身目录。真实转换并发回归先失败后通过。旧测试的异常断言更新为新明确拒绝契约，保留“别人的文件不删除”断言。
- 原 GFP 参数直接运行仍拒绝源 `rop/lacI` 的 table 1/GTG 冲突。另存注释校订副本，仅将这两条明确细菌 CDS 的 `transl_table` 改为11并记录理由；原 DNA、坐标、翻译和原文件字节不变。依据：[NCBI table 11](https://www.ncbi.nlm.nih.gov/Taxonomy/Utils/wprintgc.cgi#SG11)、[原厂 pET-28 描述](https://www.sigmaaldrich.com/US/en/product/mm/70777)。这是具体源材料处理，不是生产自动修复。
- 用该副本完成control及A206K两份6043 bp正式构建。独立用Biopython酶切边界计算整份预期序列，核对GB/DNA/FASTA、manifest及810 bp完整表达ORF；完整标签前缀和目标蛋白一致，A206→K正确。两份产物桌面SnapGene往返均严格元数据一致、无警告。预设路线只证明程序回归，不算宿主盲测。
- 当前默认 `python` 指向缺 sgffp 的 Anaconda；在已有完整依赖的 Python 3.12.4 中验证。新安装记录实际通过 `check_env` 的解释器，Skill读取它而非盲用PATH。
- 完整源码套件944项：943通过，1项在线查询未在该运行启用，434.734秒；实际启用Primer3、两个Cas-OFFinder及预测模型。早期失败日志保留：首轮漏传显式拓扑造成Golden Gate失败；第二轮旧竞争异常断言未更新。最终完整套件及新反例均通过。
- 实际inverse-PCR制备演示正式交付，独立验证序列、蛋白、源标签和Trace文件归属。

证据保存在本机忽略目录 `output/delivery-fixes-20260930/`：原CLI日志、source-corrections.json、independent-product-checks.json、official-roundtrip、full-suite-verified.log、preparation-demo。外部DNA、产物及源副本不进入公开包。

### 仍保留的边界

Chr1 的同源转移注释含未知碱基/缺stop，不批量延长或豁免。程序能够记录供体/局部检查，不因此宣称整条染色体注释已正确。原Windows单次访问异常未独立确定原因；本轮仅确认并修复同目录竞争的一类错误。旧其他SnapGene案例的qualifier差异仍保留，不将本轮两例成功外推为全部无损。

宿主Benchmark、提示对照、独立真人阅读和湿实验未验收。独立包、安装及精确提交CI结果在完成后追加。
