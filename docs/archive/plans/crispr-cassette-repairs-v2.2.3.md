# CRISPR cassette修复

2026-10-12授权：在当前开发版确认并修复真实CRISPR测试暴露的三项缺陷及四项相关误读；验证后提交、推送开发分支并核对精确CI。基线750bf48/Core2.2.2。隔离工作树保留原工作区未提交修改。用户DNA、原失败和本轮结果留在仓库外，不进入源码或发行包。

| 项目 | 当前原行为与违反的要求 | 泛化依据与本轮处理 |
|---|---|---|
| Native日期 | 2.2.1的Molecule版本编码不接受datetime，原run_step/get_feature失败。2.2.2已加入typed date/datetime编码，原失败公共CLI现已通过 | 类型缺失发生在统一材料边界，不是特定文件块坏了；保留现有修复，补独立原生packet和另一来源真实.dna入口验证 |
| 换spacer | 仅有特定pML104制备方法，无通用cassette替换 | 用启动子转录出口、骨架实际序列和20 nt间隔定义窗口；不依赖质粒身份；保留其余碱基、记录原新序列及所有重叠注释处置 |
| 查已有guide | 只有候选设计工具，缺实际cassette与靶标双链/PAM核对 | 读取启动子下游实际DNA方向，忽略guide注释作为方向裁判；保留匹配链、PAM、反插候选和多位点证据 |
| 注释方向冲突 | 原guide注释可与转录序列相反 | 单列注释可能有误，序列/PAM结论独立 |
| 假抗性CDS | inspect与backbone只凭名称认抗性，把20 nt spacer当整基因 | 标记须有完整CDS序列支持；不改原注释，冲突警告留在报告 |
| 模板旧ERR | QC没有模板对照，无法说明错误来源 | 显式template对照相同feature内容和诊断，区分继承与新/改变；不降低ERR、不改变通过门槛 |
| 中文GenBank | Core导出已显式UTF-8，外部默认编码读取会失败 | 保持UTF-8契约；独立Bio读回和无UTF8模式公共CLI子进程验证中文路径/注释 |

验收：先运行独立输入回归见红，再修实现；真实原材料按公共run_step/工具重放，逐位检查导出文件。新增合成输入是开发者独立构造的工程回归，不是陌生题保留评测。原A/B/C自主结果不因本轮人工重放而改分。通用任务成功率与湿实验不在本轮验收声明内。

本轮不接续前序多轮突变、Trace界面、Toolkit或正式iGEM发布；原handoff未关闭事项保留。

## 实现与本地验收

Core2.2.3：`core/tools/grna.py`的`replace_grna_spacer`与`check_grna`已注册并进入SKILL/Recipe入口；共同定位不依赖质粒身份。`inspection.selection_marker_evidence`供Core/inspect CLI共享；`validate_construct --template`按实际feature DNA/元数据/诊断区分来源。GenBank写出/读取已有显式UTF-8，新增中文/默认编码入口回归；日期已有9bc9aa3修复，本轮没有重复改codec。

| 检查 | 本轮实际结果 |
|---|---|
| 新公共入口工程回归 | 15项通过：包含独立原生packet、正反转录、跨原点、变体scaffold、20 nt边界/多cassette拒绝、靶链/PAM/反插、注释冲突、假抗性、模板来源与中文读回 |
| 原失败材料开发者回放 | Native get_feature和run_step直接读用户.dna及Biopython独立来源.dna通过；A仅20 nt窗口内12个位置改变，其余序列/非重叠注释及双格式读回一致；B反插；C正确且提示负链注释可能有误；两个模板lacZα ERR均继承，新增/改变ERR为0，仍退出1 |
| 原材料与文件 | SHA256清单八个条目不变；原日志/output未改；用户材料、脚本和结果仅在仓库外 |
| 冻结全量 | `SNAPGENE_RUN_PRIMER3=1 python -X utf8 -B tools/run_test_suite.py`：1217项，1196通过/21跳过/零失败，1130.473s；真实Primer3 skip门禁通过 |
| CLI烟雾 | 95通过/零失败 |
| 独立包 | v2.2.3 redistributable清单、受限材料排除通过；仓库外解包、清空PYTHONPATH后实际公共入口重复原材料回放通过；无开发测试/用户DNA入包 |
| Trace | 独立包Off/Observed/Full的实际产物、注释、检查完全一致 |
| 文档 | 九份受影响文档本地链接无新增断链；spec/SKILL/签名/架构/测试职责分别维护 |

保留失败：初轮新工具缺失与假抗性回归12项失败，模板来源新增测试2项失败。原材料回放01因独立检查者未统一DNA显示大小写而失败；回放02发现运行时来源比较同样按大小写误分类一个旧ERR，增加混合大小写回归后回放03通过。原生记录未改。

第一轮全量1217项出现4 failures/2 errors/21 skips：其中两个旧抗性测试以A-only/random短非ORF当完整标记，原输入保留为负例，另用独立完整toy ORF支持原正向名称断言；工具精确数量随新增两工具改为46。该轮运行期间继续修改源码触发`EXECUTION_CONDITIONS_CHANGED`，连带Toolkit失败；原日志保留，750bf48基线相关用例1项及不再修改源码的当前Toolkit 14项复查通过，最终冻结全量另记，不改写首轮失败。

这些均为已知题开发者回放和独立构造工程输入；没有开展陌生题保留评测，不计原A/B/C自主成功，也不宣称通用成功率提高。替换工具只提供序列编辑，制备仍需实际PCR/连接；scaffold anchor不证明完整RNA功能；继承QC错误不获豁免。21个skip保留，不称全后端覆盖。Windows默认编码外部脚本须显式UTF-8，程序入口已实测。

本轮实现与本地验收已结束。推送独立开发分支`codex/crispr-skill-fixes-20261012`；现有workflow仅监听main/master/recovery/release push及main/master PR，用草稿PR触发精确提交CI，不合并main。远端结果在本记录补记。

首提交b617e25已推送，草稿PR #2触发[CI 38272298772](https://github.com/zoehanke/snapgene-dna-design/actions/runs/38272298772)。Ubuntu三项通过；Windows在旧`test_nested_actual_delivery_is_formal_and_plain_export_is_not`的plain目录比较失败，日志与前序e6dcd14同一断言，1217项仅此失败、23跳过。新增CRISPR回归通过。

CI处置先复现：Windows `GetShortPathNameW`把同一临时目录变成8.3别名，独立`Path.samefile`确认同一目录；原公开路径用例实跑复现`plain=[]`，Trace图里实际两个plain文件已存在且为candidate。测试把canonical Trace路径与未归一化别名字符串相比，违反真实文件身份比较；修正仅对期望目录调用标准库`resolve()`，不改程序、不删产物/角色/数量要求。短名、长名都必须保持正式交付与普通导出的区分。

2026-10-13收尾：短路径修正8b27ae7已推送，本地原文件3项通过、独立8.3别名用例1项通过。该提交的[CI 38274437585](https://github.com/zoehanke/snapgene-dna-design/actions/runs/38274437585)六项在约2秒内结束，`steps=[]`/runner为空，GitHub annotation明确"The job was not started because recent account payments have failed or your spending limit needs to be increased." 因此最终六环境未验收，不能称CI通过。账号Billing & plans处理后须对最终开发分支提交重新运行；本轮不改账单/额度或main。实现、原材料回放、本地冻结全量与包验收已关闭，远端六环境验收作为明确未关闭项交接。

2026-10-13后续核查：前序账单阻断解除后，最终2.2.3文档提交4897f2f的[同run重跑](https://github.com/zoehanke/snapgene-dna-design/actions/runs/38275226154)Ubuntu/Windows × Python3.10/3.11/3.12六项成功，精确headSha匹配。该未关闭项现已关闭；原未启动失败和Windows路径断言失败记录保留，不改写为原轮通过。
