# SnapGene DNA Design v0.9.0 — 独立复审指南

本文件只描述 `v0.9.0` 正式技术发布。所有结论以本版本实际复跑证据为准，不使用 dev2/dev3
历史数字作为当前结果。

## 0. 固定对象

- 工作源码：`D:\codex_project\snapgene-dna-design-v0.9.0-work`
- 最终输出：`D:\codex_project\output\snapgene-dna-design-v0.9.0`
- 旧基线（未修改）：`D:\codex_project\output\snapgene-dna-design-v0.9.0-dev1`
- 版本：`VERSION = 0.9.0`（技术门禁通过，等待真人独立生物学验收）
- 本机 Python：`C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe`（3.12.4，已安装 requirements.txt 与 requirements-optional.txt）
- 本机 SnapGene：`D:\SnapGene\SnapGene.exe`（6.0.2）
- Primer3：`C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\Lib\site-packages\primer3\src\libprimer3\primer3_core.exe`（2.6.1）
- Cas-OFFinder v2：`D:\codex_project\output\dev3-backends\cas-offinder.exe`（2.4.1）
- Cas-OFFinder v3：`D:\codex_project\output\dev3-backends\cas-offinder-3.0.0b3\build\cas-offinder.exe`（3.0.0b3）

## 1. 本轮复审结论

| 门禁 | rc1 实测 |
|---|---|
| 源码 unittest（默认） | Ran 449 tests，OK (skipped=13)，0 failure/error |
| 源码 unittest（真实后端全开） | Ran 449 tests，OK，0 failure/error |
| 经验规则专项 | `tests.test_experience_rules` 22/22 OK；33 条预存规则唯一且通过 Schema |
| smoke core / smoke academic | 均 exit 0 |
| compileall | exit 0 |
| quick_validate | exit 0 |
| coverage default / release-real | 双 `gate: PASS`；release-real 含 90 场景套件 |
| mutation | 12/12 killed |
| property 全规模 | PASS |
| 场景套件 | 90/90 PASS；complete 40 / partial 11 / blocked 39 |
| SnapGene 官方核验 | GUI 已关闭后 `validate_rich_fixtures.py --snapgene-exe D:\SnapGene\SnapGene.exe`：gate PASS；Unicode 第三方规范化差异按声明接受，未写成 lossless |
| 固定代表任务 T1–T5 | 全部 PASS；负例全部失败关闭且不写产物 |
| 最终 ZIP | academic 449 OK(skip 13)；redistributable 421 OK(skip 15)；testzip=None；无路径穿越/pyc/cache；manifest/hash 通过 |

## 2. 默认全量测试复现

```powershell
Set-Location 'D:\codex_project\snapgene-dna-design-v0.9.0-work'
& 'C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 -B -m unittest discover -s tests
```

预期：`Ran 449 tests`，`OK (skipped=13)`；日志 `reports/rc1-final-default-tests.log`。
skip=13 全部为可选外部环境开关（Primer3/Cas-OFFinder/模型/在线），原因在日志中逐条给出。

## 3. 真实后端复现

```powershell
$env:SNAPGENE_RUN_REAL_MODELS='1'
$env:SNAPGENE_RUN_PRIMER3='1'
$env:SNAPGENE_RUN_ONLINE='1'
$env:PRIMER3_CORE='C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\Lib\site-packages\primer3\src\libprimer3\primer3_core.exe'
$env:CAS_OFFINDER_EXE='D:\codex_project\output\dev3-backends\cas-offinder.exe'
$env:CAS_OFFINDER_EXE_V3='D:\codex_project\output\dev3-backends\cas-offinder-3.0.0b3\build\cas-offinder.exe'
$env:CAS_OFFINDER_TMP='D:\codex_project\output\dev3-backends\tmp'
Set-Location 'D:\codex_project\snapgene-dna-design-v0.9.0-work'
& 'C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 -B -m unittest discover -s tests
```

预期：`Ran 449 tests`，`OK`（无 skipped）；日志 `reports/rc1-final-real-tests.log`。

## 4. 门禁复核

```powershell
Set-Location 'D:\codex_project\snapgene-dna-design-v0.9.0-work'
& 'C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 -B scripts\coverage_gate.py --mode default --json
& 'C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 -B scripts\mutation_tests.py --json
& 'C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 -B scripts\property_tests.py --json
& 'C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 -B scripts\run_scenario_suite.py --out-dir reports\scenarios
& 'C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 -B scripts\quick_validate.py --json
```

## 5. SnapGene 官方核验

先确认 SnapGene GUI 已关闭（`tasklist | findstr SnapGene` 为空），然后：

```powershell
& 'C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 -B scripts\validate_rich_fixtures.py --snapgene-exe 'D:\SnapGene\SnapGene.exe' --json --out-dir reports\rich-review
```

预期：`rich declared compatibility gate: PASS`；`snapgene-gb` 官方往返通过，`.dna` 的第三方规范化差异按已声明分类接受。

## 6. 最终 ZIP 复核

```powershell
$a='D:\codex_project\output\snapgene-dna-design-v0.9.0\packages\snapgene-dna-design-v0.9.0-academic-full.zip'
$r='D:\codex_project\output\snapgene-dna-design-v0.9.0\packages\snapgene-dna-design-v0.9.0-redistributable.zip'
& 'C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 -B scripts\validate_release_manifest.py $a --package academic-full --version 0.9.0
& 'C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 -B scripts\validate_release_manifest.py $r --package redistributable --version 0.9.0
& 'C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 -B scripts\check_redistributable.py $a --academic
& 'C:\Users\祝浩淇\AppData\Local\Programs\Python\Python312\python.exe' -X utf8 -B scripts\check_redistributable.py $r
```

预期：两个 manifest `ok=true`；academic 受限哈希 10/10；redistributable 0；`zipfile.testzip() is None`；包内 VERSION=0.9.0。

## 7. 复审判定

若上述命令与数字复现，且 `FINAL-TECHNICAL-VALIDATION.md` 第 4 节 P0/P1 均为 0，则本版本判定 `TECHNICALLY_READY_PENDING_HUMAN_BIOLOGICAL_ACCEPTANCE`。
