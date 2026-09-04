# GBS A 锚点 held-out 验证

> 事前合同、分析器与执行 harness 先由提交
> `1b6304c583a7ed2e03790ffe5308dabf158eb30c` 进入 `main`，并由轻量标签
> `gbs-heldout-contract-20260904` 固定；随后才连接 `<TEST_BOARD_IP>`。本报告结果不回灌
> v4 建带样本，也没有补跑替换。

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

## 4. 身份、环境与产物链

三重身份门与环境门原文如下；逐命令的 `RC=0` / `DONE_*` 记录见
[`preflight/`](../data/raw/gbs_heldout_validation_20260904/preflight/)：

```text
6.12.80-arm-rpi4-v7l
armv7l
NAME=Tizen
VERSION="11.0.0 (Tizen11.0/Unified)"
ID=tizen
VERSION_ID=11.0.0
PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"
ANSI_COLOR="0;36"
CPE_NAME="cpe:/o:tizen:tizen:11.0.0"
BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l
glibc-2.40-1.6.armv7l
MemTotal:        8117408 kB
```

产物身份链为：`glibc-memopt-tools-1.0.0-1.armv7l` RPM，RPM SHA-256
`efad4a0d202785f8c201977fd8aef35752af1bddde163f1063151621e0ac4e0e` → 提取的
`alloc_bench.armv7l` SHA-256
`88667139f69aac0e2b729a5ea62d7d6d14ba400dd9eb609fc25dfc5824efcffa` → host 与板端
复核一致。RPM/NVR 链见
[`build_summary.json`](../data/raw/gbs_package_20260903/build_summary.json)，本轮 ELF 记录见
[`artifact_manifest.tsv`](../data/raw/gbs_heldout_validation_20260904/artifact_manifest.tsv)。

## 5. 四格结果与 held-out 裁决

| 顺序 | profile | rep | pre-trim PD (KiB) | post-trim PD (KiB) | 回收 (KiB) | 回收/pre-trim | 相对中心偏差 | v4 闭区间 | 判定 |
|---:|---|---:|---:|---:|---:|---:|---:|---|---|
| 1 | mixed | 1 | 108664 | 54884 | 53780 | 49.492012% | -3.302487 pp | 48.489794%–57.099204% | PASS |
| 2 | medium-only | 1 | 105052 | 50628 | 54424 | 51.806724% | +1.136933 pp | 45.751703%–55.587879% | PASS |
| 3 | mixed | 2 | 109400 | 50032 | 59368 | 54.266910% | +1.472411 pp | 48.489794%–57.099204% | PASS |
| 4 | medium-only | 2 | 105252 | 52988 | 52264 | 49.656064% | -1.013727 pp | 45.751703%–55.587879% | PASS |

机器判定为 **4/4 落带，GBS held-out 验证 PASS**。因此按事前二选一规则，GBS
重基线通过；这四格是既有 v4 校准带之外的独立样本，未用于改变中心或半宽。逐格输入见
[`heldout_cells.tsv`](../data/raw/gbs_heldout_validation_20260904/heldout_cells.tsv)，逐边界判定见
[`decision.json`](../data/raw/gbs_heldout_validation_20260904/decision.json)。

## 6. 健康、告警与现场恢复

| 门 | 本轮值 | 判定 |
|---|---:|---|
| trim/refault majflt 最大值 | 0 / 0 | PASS |
| zram `orig/compr/mem_used` 增量 | 0 / 0 / 0 | PASS |
| dmesg 增量 OOM/LMK | 0 | PASS |
| 4 KiB 回收页对齐 | 4/4 | PASS |
| A 格单次 trim 最大耗时 | 15.046870 ms（<20 ms） | PASS |
| 结束 governor | 4/4 `schedutil` | PASS |
| 工作目录与空父目录 | 均不存在 | PASS |

完整健康摘要见 [`health.json`](../data/raw/gbs_heldout_validation_20260904/health.json)。运行前
livedump 数为 0；四格各出现 1 个 `alloc_bench cpu.relative`，总数 4，均匹配事前登记。
四件已拉回本地 `board_results/` 并按 SHA-256 校验，随后逐件清理；清理后二次快照为空。
这是 known-alert waiver 的 `EXPECTED`，仅证明触发理由、PID/窗口、数量和处置符合合同，
不构成根因或无害性证明。公开的分类与归档哈希见
[`stability_final.json`](../data/raw/gbs_heldout_validation_20260904/stability_final.json)，完整归档件
仍仅在本地保存，可按请求提供。

## 7. Workflow 发现与结论

本轮直接运行预提交的 host runner；身份/环境、host/板端哈希、四格固定顺序、外部 1 s
采样、拉回 manifest、分析、告警归档/清理、工作目录删除和 governor 恢复全部一次完成。
没有发现需要修改合同、参数、门或清理逻辑的 workflow 缺陷。

结论：**GBS 重基线通过，GBS `git clone → gbs build → 提取三项 ELF → board workflow`
恢复为 HQ 首选 L2 路径。** 冻结件仍是可审计备选。该结论仅覆盖指定镜像、glibc 2.40、
本轮 GBS ELF 与现行验收合同；不把 held-out 四格写回 v4 校准带，也不外推产品内存收益。

## 8. 复现

事前合同 tag：`gbs-heldout-contract-20260904`；harness：
[`tools/runners/gbs_heldout_validation_20260904/`](../tools/runners/gbs_heldout_validation_20260904/)。
板上按相同合同运行：

```sh
bash tools/runners/gbs_heldout_validation_20260904/run_heldout_host.sh \
  --ip <TEST_BOARD_IP> \
  --output board_results/gbs_heldout_validation_20260904/workflow \
  --gbs /path/to/gbs/alloc_bench.armv7l
```

只复算公开紧凑件：

```sh
tmp=$(mktemp -d)
python3 tools/runners/gbs_heldout_validation_20260904/analyze_heldout.py \
  --replay data/raw/gbs_heldout_validation_20260904/heldout_cells.tsv --output "$tmp"
cmp "$tmp/heldout_cells.tsv" data/raw/gbs_heldout_validation_20260904/heldout_cells.tsv
cmp "$tmp/decision.json" data/raw/gbs_heldout_validation_20260904/decision.json
```

预期原文为 `replayed cells=4 verdict=PASS passed=4/4`，两条 `cmp` 静默。确定性检查是合同
顺序与 GBS/直方图 SHA；validity gates 是页对齐、majflt、zram 与 OOM/LMK 精确为零，
governor/清理复核通过；容差项是每个 held-out 格独立落入其 profile 的 v4 闭区间，A 格
单次 trim `<20 ms`。回收 payload/字节不作为确定性项，本轮也不改变建带样本。
