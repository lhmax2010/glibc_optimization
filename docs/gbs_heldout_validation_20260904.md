# GBS A 锚点 held-out 验证（事前合同）

> 状态：尚未连接测试板、尚未产生结果。本节合同、分析器与执行 harness 必须先进入
> `main` 并由轻量标签 `gbs-heldout-contract-20260904` 固定；板上结果另行提交。

## 1. 固定规格

本轮只使用 manifest 中 `gbs_build_sha256` 所指的 GBS `alloc_bench.armv7l`，哈希为
`88667139f69aac0e2b729a5ea62d7d6d14ba400dd9eb609fc25dfc5824efcffa`。四格不并入
既有建带样本，顺序固定如下；单格失败或出带均不得用补跑替换。

| 顺序 | ELF | profile | 重复 |
|---:|---|---|---:|
| 1 | GBS | mixed | 1 |
| 2 | GBS | medium-only | 1 |
| 3 | GBS | mixed | 2 |
| 4 | GBS | medium-only | 2 |

每格参数固定为：`--threads 4 --seed 20260813 --warmup 5 --duration 20 --idle 15
--idle-trim --post-trim-ops-per-thread 4096 --live-set 4096 --idle-release 50
--release-order high`；mixed 使用内置 `mixed`，medium-only 使用哈希为
`2082e156db133f4e6e900aec7c202e44a453d2f23b60225c40251de08a27960b` 的外部
直方图。机器可读合同见
[`contract.json`](../tools/runners/gbs_heldout_validation_20260904/contract.json)。

## 2. 事前裁决规则

逐格以 pre-trim glibc heap Private_Dirty 为分母：

| profile | v4 校准带中心 | 半宽 | 闭区间 |
|---|---:|---:|---:|
| mixed | 52.794499% | ±4.304705 pp | 48.489794%–57.099204% |
| medium-only | 50.669791% | ±4.918088 pp | 45.751703%–55.587879% |

- 四格全部落入各自闭区间：判定 GBS 重基线通过，并恢复 HQ 首选路径结论。
- 任一格出带：如实判不通过，GBS 路径维持备选，不改带、不补跑刷数。

身份、环境、governor、RC/DONE、zram、dmesg、major fault、页对齐与清理门沿用 A2。
本轮临时登记每格至多一个 `alloc_bench cpu.relative` livedump、总数至多四个；命中
仍须归档、清理并复核，未登记的我方告警硬失败，非我方告警仅报告。

## 3. 事前可执行产物

- Host 编排：[`run_heldout_host.sh`](../tools/runners/gbs_heldout_validation_20260904/run_heldout_host.sh)
- 板端控制：[`run_heldout_remote.sh`](../tools/runners/gbs_heldout_validation_20260904/run_heldout_remote.sh)
- 独立分析：[`analyze_heldout.py`](../tools/runners/gbs_heldout_validation_20260904/analyze_heldout.py)

正式结果提交将追加原始身份链、四格表、健康门、stability-monitor 处置、裁决和复现节；
报告中的板地址只写 `<TEST_BOARD_IP>`。
