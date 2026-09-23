# 实际集成

| 接口 | 输入/输出 | 实际机制 | 限制/失败 |
|---|---|---|---|
| 宿主 Skill | 请求→CLI 参数/JSON→结果 | SKILL.md + scripts；agents/openai.yaml 为元数据 | 不接管闭源宿主，不保证全部检索可见 |
| Python API | ConstructionTask→plan/execute/validate/finalize | core/__init__.py 导出 | 不是 HTTP 服务 |
| Pipeline 工具 | JSON 参数/SeqRecord→结构化结果 | registry ToolSpec | 不同工具有明确副作用类别 |
| Biopython | FASTA/GB/EMBL/SeqRecord | parser、feature extraction、序列工具 | 格式可读不等于注释正确 |
| Native SnapGene | .dna 与 .gb 双向 | sgffp、snapgene_reader、snapgene_io | Native 解析验证与桌面软件实测分开 |
| Primer3 | Boulder-IO→cores/结构指标 | primer3_core 子进程 | 实际后端缺失不可冒充预测成功 |
| Cas-OFFinder | 参考基因组/guide→命中 | 外部程序与OpenCL | 官方2.4.1/3.0.0b3在本机合成参考运行通过；真实全基因组验证缺证据 |
| Azimuth / DeepCpf1 | 合适上下文→预测分数 | 本地受信任模型与可选依赖 | 训练域外适用性和实验效果未验证 |
| NCBI | 关键词/accession→检索/记录 | urllib eUtils，超时和offline状态 | 关键词连通性不等于所有检索可用 |
| Addgene | 标识→官方链接 | 链接辅助 | 不是完整库存/序列API |

外部序列上传必须遵循 [privacy-and-consent](../references/privacy-and-consent.md)。项目不会因“本地Skill”自动保证宿主不上传数据。外部模型 pickle 仅适用于可信安装内容，不能接收任意下载的模型并宣称安全。

低层脚本还不是独立 pip 包；需要直接调其 helper 时从仓库根目录显式加入 scripts：

```python
import sys
sys.path.insert(0, "scripts")
from primer3_core_backend import probe_primer3_core
print(probe_primer3_core())
```

支持版本、实测环境见[复现](reproducibility.md)，格式测试见[兼容表](igem/standards-compatibility.md)。
