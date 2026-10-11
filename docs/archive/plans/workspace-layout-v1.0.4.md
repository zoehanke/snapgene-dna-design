# 开发工作区与Skill目录分离

2026年10月3日 · r2 · 产品版本保持v1.0.4 · 本地迁移验收完成

## 目标与布局

负责人指出README本身属于Skill，并授权把工作区上移。项目/Git根为`D:/codex_project/github`；原`snapgene-dna-design/`目录作为Skill根，不改名，保留原材料、产物及运行入口的绝对路径。

外层：AGENTS、项目导航README、specs、开发docs、tests、benchmarks、tools、results、Git配置与CI。内层：Skill README、SKILL、core、实际DNA scripts、references、schemas、依赖、模型、示例及运行使用文档。

开发AI读外层AGENTS/spec/计划；执行AI读Skill内SKILL；用户读Skill内README。运行包只从Skill子目录取文件，排除开发资料和历史记录。

## 实施与保留

- Git bundle已备份并验证完整历史；迁移前HEAD为`899a888`，唯一工作树与开发分支保留。禁止重建Git、改main或重写旧提交。
- 转移`.git`和开发资料到父目录；原材料与既有输出留在原路径，未更改DNA内容。
- 用户Reader Demo及旧zip哈希原样保留，不纳入本次提交。迁移映射保存本机，测试仅改路径与导入，保留原输入、断言、覆盖目标和阈值。
- 项目测试与开发tools通过一份共享路径定义找到Skill根；运行模块不依赖外层helpers。CI从外层运行测试，从Skill根调用真实CLI。
- 打包工具按Git中Skill子树收集受版本管理的文件，仍校验路径与许可。旧重构/开发manifest/升级记录归档，不冒充当前事实。

## 验收

检查Git refs与历史HEAD、原未提交文件字节、全部运行Core代码及源材料哈希；全量测试、源码外解压包、实际CLI输出、Trace三档与包边界检查。旧产物路径不迁移，不把迁移测试称为陌生评测或通用能力提高。

开发工作区在Codex应打开项目外层目录。当前聊天的客户端目录配置不通过修改数据库处理；如果侧栏仍显示旧文件范围，重新打开外层路径。

## 实际结果

首轮路径回归979项出现4失败、2错误和14跳过，原因是少数旧入口仍用外层scripts/fixtures且未启用既有Primer3 flag。已按实际布局修正路径，针对这些入口的40项回归通过；没有降低验收标准。最终结果如下，失败记录保留在本机证据目录。

备份：`D:/codex_project/migration-backups/snapgene-layout-20261003-165219/`。本机迁移证据：`snapgene-dna-design/output/layout-migration-20261003/`，不随源码提交。

| 检查 | 实际结果与范围 |
|---|---|
| Git与材料 | 489个原跟踪路径全部保留；211个运行代码/材料文件字节一致；原Reader Demo和旧包SHA文件原样保留；main未动 |
| 完整套件 | Python 3.12，980项，972通过、8跳过；真实Primer3启用，无失败；跳过不计通过 |
| 开发入口 | smoke_core 95项通过；快速属性回归六类方法全部通过；rich fixtures原有兼容契约通过 |
| 子目录打包 | 新增独立中文/空格目录正反例，排除外层开发资料、相似前缀目录和未跟踪材料；保留旧根目录与非Git边界案例 |
| 独立运行包 | redistributable 254个登记条目；清单、哈希与许可检查通过；包README与Skill README一致；仓库外中文目录实际运行环境检查、接口清单和文件inspect通过 |
| 实际Recipe | 独立合成输入的公开CLI，off/observed/full序列、拓扑、特征、引物与检查语义一致；无效参数拒绝且旧回执失效；这是合成回归，不宣称功能质粒、湿实验或陌生评测通过 |
| 文档与CI | 当前相对链接无缺失，运行文档无外层依赖；CI六环境入口同步新布局；远程结果以本次提交检查为准，最终交接记录精确提交结果 |

另一次默认Python 3.14尝试因缺少sgffp未通过并中止，日志保留；没有安装新依赖或删检查制造成功。有效验证使用既有完整Python 3.12环境。桌面SnapGene官方重读和可选真实模型/全基因组后端不因目录迁移新增验证结论。

后续接手：从项目外层运行开发命令，安装/执行只交付内层Skill；历史计划中的旧命令保留为历史，当前命令看项目README与开发指南。备份可用于恢复，不通过reset/重写历史回退用户修改。
