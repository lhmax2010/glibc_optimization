> Public archive note: application/process names are aliases. Host-side paths are
> sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is
> intentionally public for reproducibility.

# HQ Demo 复现指南

- 日期：2026-09-01
- 目标：让具备 LLVM/Tizen 工具链基础、但不了解本项目的工程人员分层复现 Demo 数字
- 证据边界：L1 只读公开仓库；L2 重跑测试板合成实验；L3 可选重采产品板只读时序
- 主报告：[`demo_narrative_20260901.md`](demo_narrative_20260901.md)

三个层级相互解耦。L1 可以逐字节核对已发布派生证据；L2 可以独立重跑测试板
S4 与真实多线程 GStreamer release 实验；L3 只在需要重新取得产品侧时序时执行，
不是 L1/L2 的前置。

<a id="workflow-fast-path"></a>
## Workflow 快速通道

仓库提供单入口 [`tools/reproduce/reproduce.sh`](../tools/reproduce/reproduce.sh)，它只编排
本指南链接的既有 harness/分析器，统计逻辑仍由各轮分析器唯一维护：

```sh
# 默认模式；host-only，分钟级
bash tools/reproduce/reproduce.sh

# 与上行等价
bash tools/reproduce/reproduce.sh verify

# 完整 L2；需本节规定的 RPI4、镜像、SDB 与内部产物包，小时级
bash tools/reproduce/reproduce.sh board --ip <addr>
```

入口必须在真实 `git clone` 内运行，GitHub ZIP/source export 不受支持；workflow 会把
`HEAD` 与 [`delivery_refs.json`](../tools/reproduce/delivery_refs.json) 记录的交付引用比较。
仅开发调试可显式设置 `REPRODUCE_ALLOW_DIRTY=1`、`REPRODUCE_SKIP_TESTS=1` 或
`REPRODUCE_EXPECTED_SHA=<commit-or-ref>`；交付验收不得隐式跳过这些门。

`verify` 依次执行全部 L1 复算与 `cmp`、重建离线 HTML、检查本地链接、运行 host
测试，并输出逐项 `PASS/FAIL`；任一失败返回非零。`board` 执行身份/环境/能力门、资产
哈希、S4 与 gst 冻结矩阵、拉回解析、v2 known-alert waiver、精确清理和 governor 复核。两种模式
共同读取机器可读的
[`acceptance_bands.json`](../tools/reproduce/acceptance_bands.json)：未观测预登记告警时输出
`REGISTERED/NOT-EVALUATED`；`EXPECTED` 只表示实际命中登记且板上已完成归档/清理/复核；
`REPORT_ONLY` 表示方向性结果或非我方/归属不明状态，
不做处置；`FAIL` 使总流程失败。手工步骤仍是流程权威参考，可与 workflow 输出互验。

## L1 · 派生数字复算

### 通用环境

在仓库根目录执行，唯一运行时依赖是 Python 3。以下命令不会连接板端，也不会
改写 `data/raw/`。需要输出目录的分析器统一写到 host 临时目录。

```sh
REPO=/path/to/glibc_optimization
cd "$REPO"
OUT=$(mktemp -d /tmp/glibc-memopt-demo.XXXXXX)
python3 --version
```

<a id="l1-servicea"></a>
### ServiceA：峰谷、换出排除与时长伪影

输入是产品周期探针的
[`timeseries.tsv`](../data/raw/product_cyclic_target_probe_20260814/raw/timeseries.tsv)、
[`key_timeline.tsv`](../data/raw/product_cyclic_target_probe_20260814/raw/key_timeline.tsv)，
以及已发布的独立复算程序
[`recompute_cyclic.py`](../data/raw/cyclic_fall_mechanism_attribution_20260831/recompute_cyclic.py)。

```sh
python3 data/raw/cyclic_fall_mechanism_attribution_20260831/recompute_cyclic.py \
  --timeseries data/raw/product_cyclic_target_probe_20260814/raw/timeseries.tsv \
  --keys data/raw/product_cyclic_target_probe_20260814/raw/key_timeline.tsv \
  --output "$OUT/cyclic"
```

预期输出原文如下。这里同时复核逐轮 PD 实跌、zram 没有正增量、majflt
下降窗为零、无缺行和无 PID 变化；中位峰谷为 `6212 KiB`，即 Demo 中的
`6.07 MiB`。这些值也已固化在
[`cyclic_rounds.tsv`](../data/raw/cyclic_fall_mechanism_attribution_20260831/cyclic_rounds.tsv)
与
[`cyclic_quality.json`](../data/raw/cyclic_fall_mechanism_attribution_20260831/cyclic_quality.json)。
下方 `minflt_rise` 是旧复算器保留的字段名，实际口径是
`minflt_start_to_peak`，不是正式的 10%→90% 上升沿；Demo 的归因链不使用该列，口径
修正见
[`归因 v2 §2`](cyclic_fall_mechanism_attribution_v2_20260901.md#2-决定性归因链)。

```text
ServiceA
R1 P-V=9796kB zorig=0B zused=0kB minflt_rise=10652 majflt_fall=0
R2 P-V=6244kB zorig=0B zused=0kB minflt_rise=9436 majflt_fall=0
R3 P-V=8620kB zorig=0B zused=0kB minflt_rise=1238 majflt_fall=0
R4 P-V=6676kB zorig=0B zused=0kB minflt_rise=959 majflt_fall=0
R5 P-V=4032kB zorig=0B zused=0kB minflt_rise=1082 majflt_fall=0
R6 P-V=6180kB zorig=-262144B zused=-256kB minflt_rise=857 majflt_fall=0
R7 P-V=4332kB zorig=0B zused=0kB minflt_rise=9615 majflt_fall=0
R8 P-V=5792kB zorig=0B zused=0kB minflt_rise=5477 majflt_fall=0
median_P-V_kB 6212.0
zram_total -262144 -256
missing_rows 0 pid_changes {'ChannelLoader': 0, 'ServiceA': 0, 'ServiceB': 0, 'WebRuntime': 0}
```

全窗口 `majflt` 的首末计数来自同一质量摘要
([证据](../data/raw/cyclic_fall_mechanism_attribution_20260831/cyclic_quality.json))：

```sh
python3 -c 'import json; q=json.load(open("data/raw/cyclic_fall_mechanism_attribution_20260831/cyclic_quality.json")); x=q["target_counters"]["ServiceA"]; print("ServiceA majflt=%d->%d delta=%d"%(x["majflt_first"],x["majflt_last"],x["majflt_delta"]))'
```

```text
ServiceA majflt=167->167 delta=0
```

F2/F3 使用当前 host 分析器重建，并和提交中的紧凑文件逐字节比较：

```sh
python3 tools/runners/cyclic_fall_attribution_20260901/analyze_attribution.py \
  --timeseries data/raw/product_cyclic_target_probe_20260814/raw/timeseries.tsv \
  --keys data/raw/product_cyclic_target_probe_20260814/raw/key_timeline.tsv \
  --published-analyzer tools/runners/product_cyclic_target_probe_20260814/analyze_cyclic.py \
  --output "$OUT/attribution"
cmp "$OUT/attribution/serviceA_large_steps.tsv" \
  data/raw/cyclic_fall_attribution_20260901/serviceA_large_steps.tsv
cmp "$OUT/attribution/serviceA_fall_recheck.tsv" \
  data/raw/cyclic_fall_attribution_20260901/serviceA_fall_recheck.tsv
cmp "$OUT/attribution/summary.json" \
  data/raw/cyclic_fall_attribution_20260901/summary.json
```

三个 `cmp` 均应静默返回成功。关键预期值见
[`summary.json`](../data/raw/cyclic_fall_attribution_20260901/summary.json)：
`32` 个大步、近等幅互补为 `0`、释放步 total PD 实跌 `14/14`；旧
`fall_edge` 中位 `19.683240 s`，而首次进入谷底 `5%` 带的延迟上界为
`5.223693–8.910626 s`。因此 Demo 只把前者当作算法伪影，不再当释放时长。

<a id="l1-phenotypes"></a>
### 表型普查与候选 retained floor

运行公开判别器并逐字节对照两张提交表：

```sh
python3 tools/runners/cyclic_fall_attribution_20260901/audit_phenotypes.py \
  --repo-root . --output "$OUT/phenotypes"
cmp "$OUT/phenotypes/release_ratio_phenotypes.tsv" \
  data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv
cmp "$OUT/phenotypes/plateau_cyclic_crosscheck.tsv" \
  data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv
```

两个 `cmp` 均应静默返回成功。下列一行 Python 只从这两张表抽取 Demo 字段：

```sh
python3 - <<'PY'
import csv
from pathlib import Path
p = Path("data/raw/cyclic_fall_attribution_20260901")
rr = {r["target"]: r for r in csv.DictReader((p / "release_ratio_phenotypes.tsv").open(), delimiter="\t")}
pc = {r["target"]: r for r in csv.DictReader((p / "plateau_cyclic_crosscheck.tsv").open(), delimiter="\t")}
e = rr["enlightenment"]
print("enlightenment class=%s retained=%+dkB drawdown=%dkB ratio=%s%%" % (e["classification"], int(e["retained_height_kb"]), int(e["max_drawdown_kb"]), e["drawdown_to_retained_pct"]))
print("ServiceH release_floor=%+dkB plateau_upper=%dkB cyclic_floor=%+dkB" % (int(rr["ServiceH"]["retained_height_kb"]), int(pc["ServiceH[ServiceK]"]["max_rise_kb"]), int(pc["ServiceH[ServiceK]"]["cyclic_end_minus_start_kb"])))
print("ServiceA residual=%+dkB" % int(pc["ServiceA"]["cyclic_final_round_floor_delta_kb"]))
print("ServiceE class=%s" % rr["ServiceE"]["classification"])
print("AppProcD class=%s" % rr["AppProcD"]["classification"])
print("ServiceB class=%s" % pc["ServiceB"]["classification"])
PY
```

预期输出原文：

```text
enlightenment class=a-self-reclaim+b-retention retained=+1736kB drawdown=120kB ratio=6.912442%
ServiceH release_floor=+580kB plateau_upper=2360kB cyclic_floor=+868kB
ServiceA residual=+788kB
ServiceE class=c-byte-exact-no-response
AppProcD class=n-subthreshold
ServiceB class=u-cross-probe-unstable
```

<a id="l1-batch-release"></a>
### 批量处理释放相位

公开紧凑输入
[`batch_release_phase.tsv`](../data/raw/demo_reproduction_20260901/batch_release_phase.tsv)
逐行转录自单进程报告和八进程扩展报告；来源说明见同目录
[`README.md`](../data/raw/demo_reproduction_20260901/README.md)。
这些数字来自 `<TEST_IMAGE_B>` / `glibc-2.40-2.8` 的相容性对照，不属于冻结矩阵。
转录一致性可单独运行 `python3 tools/reproduce/check_batch_transcription.py` 验证。

```sh
python3 -c 'import csv,statistics; r=list(csv.DictReader(open("data/raw/demo_reproduction_20260901/batch_release_phase.tsv"),delimiter="\t")); s=[x for x in r if x["series"]=="single"]; m=[x for x in r if x["series"]=="scale"]; print("single median=%.4f%%/%.6fMiB; demo=48.9%%/1.36MiB"%(statistics.median(float(x["reclaim_pct"]) for x in s),statistics.median(float(x["reclaimed_mib"]) for x in s))); print("scale process_count=%d pct_range=%.4f-%.4f%%"%(len(m),min(float(x["reclaim_pct"]) for x in m),max(float(x["reclaim_pct"]) for x in m)))'
```

```text
single median=48.9451%/1.359375MiB; demo=48.9%/1.36MiB
scale process_count=8 pct_range=48.5232-49.3671%
```

<a id="l1-s4"></a>
### S4 锚点、回收效果与代价

输入为
[`a_cells.tsv`](../data/raw/s4_retention_20260901/a_cells.tsv)、
[`b_cells.tsv`](../data/raw/s4_retention_20260901/b_cells.tsv)、
[`b_cycles.tsv`](../data/raw/s4_retention_20260901/b_cycles.tsv) 和
[`health.json`](../data/raw/s4_retention_20260901/health.json)。以下命令保留报告使用的
十进制半入舍出规则：

```sh
python3 - <<'PY'
import csv, json, statistics
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
p = Path("data/raw/s4_retention_20260901")
a = list(csv.DictReader((p / "a_cells.tsv").open(), delimiter="\t"))
b = list(csv.DictReader((p / "b_cells.tsv").open(), delimiter="\t"))
c = list(csv.DictReader((p / "b_cycles.tsv").open(), delimiter="\t"))
h = json.loads((p / "health.json").read_text())
print("A anchors: " + " ".join("{}={:.6f}%".format(r["profile"], float(r["reclaim_pct_of_pretrim"])) for r in a))
v = [r for r in c if r["trim_at"] == "valley"]
print("B reclaim/released range=%.6f-%.6f%%" % (min(float(r["trim_reclaim_pct_of_released"]) for r in v), max(float(r["trim_reclaim_pct_of_released"]) for r in v)))
for profile in ("mixed", "medium-only"):
    cells = {r["trim_at"]: r for r in b if r["profile"] == profile and r["rep"] == "1"}
    extra = int(cells["valley"]["cycle1_next_minflt"]) - int(cells["none"]["cycle1_next_minflt"])
    print("%s next_minflt_extra=%+d" % (profile, extra))
medians = {}
for profile in ("mixed", "medium-only"):
    times = [Decimal(r["trim_elapsed_ms"]) for r in v if r["profile"] == profile]
    medians[profile] = statistics.median(times).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
print("trim_ms_median_by_profile: mixed=%s medium-only=%s" % (medians["mixed"], medians["medium-only"]))
payloads = {}
for r in c:
    payloads.setdefault((r["profile"], int(r["cycle"])), set()).add(int(r["released_payload_bytes"]))
assert all(len(values) == 1 for values in payloads.values())
print("released_payload_bytes: " + " ".join(
    "%s=%s" % (profile, ",".join(str(next(iter(payloads[(profile, cycle)]))) for cycle in (1, 2)))
    for profile in ("mixed", "medium-only")
))
print("reclaimed_4k_aligned=%d/%d" % (sum((int(r["trim_reclaimed_kb"]) * 1024) % 4096 == 0 for r in v), len(v)))
print("majflt_all_zero=%s" % str(all(int(r["next_cycle_majflt"]) == 0 for r in c)).lower())
print("zram_deltas=%d,%d,%d dmesg_increment=%d oom_lmk=%d" % (h["zram_original_data_size_delta"], h["zram_compressed_data_size_delta"], h["zram_mem_used_total_delta"], h["dmesg_increment_lines"], len(h["oom_lmk_matches"])))
PY
```

预期输出原文：

```text
A anchors: mixed=51.074077% medium-only=50.387886%
B reclaim/released range=80.175875-85.453954%
mixed next_minflt_extra=+1351
medium-only next_minflt_extra=+1465
trim_ms_median_by_profile: mixed=1.233269 medium-only=1.218361
released_payload_bytes: mixed=5742256,6566672 medium-only=6288384,6293504
reclaimed_4k_aligned=12/12
majflt_all_zero=true
zram_deltas=0,0,0 dmesg_increment=0 oom_lmk=0
```

<a id="l1-gst-trim-cost"></a>
### GStreamer 真实多线程目标的业务 p99、trim 分布与首次回收

这一入口只读取公开紧凑件
[`cycles.tsv`](../data/raw/gst_trim_cost_20260901/cycles.tsv)。格级 external 样本数、
overrun 与退出码已在每个 cycle 行中重复保存，因此该文件可以独立重建
[`repetitions.tsv`](../data/raw/gst_trim_cost_20260901/repetitions.tsv)、
[`arm_summary.tsv`](../data/raw/gst_trim_cost_20260901/arm_summary.tsv) 和
[`comparison.json`](../data/raw/gst_trim_cost_20260901/comparison.json)，不读取本地
`board_results/` 或其他公开证据文件。

```sh
python3 tools/runners/gst_trim_cost_20260901/analyze_gst_trim_cost.py \
  --replay-cycles data/raw/gst_trim_cost_20260901/cycles.tsv \
  --output "$OUT/gst-trim-cost"
cmp "$OUT/gst-trim-cost/repetitions.tsv" \
  data/raw/gst_trim_cost_20260901/repetitions.tsv
cmp "$OUT/gst-trim-cost/arm_summary.tsv" \
  data/raw/gst_trim_cost_20260901/arm_summary.tsv
cmp "$OUT/gst-trim-cost/comparison.json" \
  data/raw/gst_trim_cost_20260901/comparison.json
```

分析器预期输出原文如下；三个 `cmp` 均应静默返回成功。分位口径仍是
nearest-rank，主统计仍固定取每重复 cycle 2–51 的 50 个样本。

```text
replayed cells=6 cycles=306 primary=300
delta_p99_ms=6.228611 none_dispersion_ms=6.784167 visible=false
```

trim 合并分布与三个首次 release 直接从同一输入逐值复算：

```sh
python3 - <<'PY'
import csv, math
from pathlib import Path
p = Path("data/raw/gst_trim_cost_20260901")
rows = list(csv.DictReader((p / "cycles.tsv").open(), delimiter="\t"))
def nr(values, q):
    values = sorted(values)
    return values[max(1, math.ceil(q * len(values))) - 1]
trim = [float(r["trim_elapsed_ms"]) for r in rows if r["arm"] == "trim-at-loop-release"]
first = [r for r in rows if r["arm"] == "trim-at-loop-release" and r["cycle"] == "1"]
pct = [float(r["reclaim_pct_of_pre"]) for r in first]
mib = [int(r["glibc_pd_reclaimed_kb"]) / 1024 for r in first]
print("gst trim calls=%d p50=%.6f p95=%.6f p99=%.6f max=%.6f ms" %
      (len(trim), nr(trim, .50), nr(trim, .95), nr(trim, .99), max(trim)))
print("gst first-release=%.6f-%.6f%% / %.6f-%.6f MiB" %
      (min(pct), max(pct), min(mib), max(mib)))
PY
```

```text
gst trim calls=153 p50=0.671556 p95=0.818315 p99=0.842185 max=0.856944 ms
gst first-release=51.014041-51.406250% / 1.277344-1.285156 MiB
```

### Demo 数字到公开输入的总表

| Demo 展示值 | 公开输入 | 复算入口 |
|---|---|---|
| ServiceA `6.07 MiB`（精确中位 `6212 KiB`） | [`serviceA_fall_recheck.tsv`](../data/raw/cyclic_fall_attribution_20260901/serviceA_fall_recheck.tsv) | [ServiceA](#l1-servicea) |
| 旧 `19.683240 s` 为伪影 | [`summary.json`](../data/raw/cyclic_fall_attribution_20260901/summary.json) | [ServiceA](#l1-servicea) |
| `enlightenment +1736 KiB` | [`release_ratio_phenotypes.tsv`](../data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv) | [表型](#l1-phenotypes) |
| `ServiceH 2360/+868/+580 KiB` | [`plateau_cyclic_crosscheck.tsv`](../data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv)、[`release_ratio_phenotypes.tsv`](../data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv) | [表型](#l1-phenotypes) |
| `ServiceA +788 KiB` | [`plateau_cyclic_crosscheck.tsv`](../data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv) | [表型](#l1-phenotypes) |
| 批量相位 `48.9% / 1.36 MiB × 8`（`<TEST_IMAGE_B>` / `glibc-2.40-2.8` 相容性对照，非冻结矩阵） | [`batch_release_phase.tsv`](../data/raw/demo_reproduction_20260901/batch_release_phase.tsv) | [批量相位](#l1-batch-release) |
| S4 `51.07% / 50.39%`（各 n=1，of pre-trim heap） | [`a_cells.tsv`](../data/raw/s4_retention_20260901/a_cells.tsv) | [S4](#l1-s4) |
| S4 `80.175875%–85.453954%`、调用中位 mixed `1.233269 ms` / medium-only `1.218361 ms`、`+1351/+1465 minflt` | [`b_cycles.tsv`](../data/raw/s4_retention_20260901/b_cycles.tsv)、[`b_cells.tsv`](../data/raw/s4_retention_20260901/b_cells.tsv) | [S4](#l1-s4) |
| S4 `majflt=0`、zram 三项 `Δ=0`、OOM/LMK `0` | [`health.json`](../data/raw/s4_retention_20260901/health.json) | [S4](#l1-s4) |
| gst p99 `+6.228611 ms` 对 none 离散 `6.784167 ms`，margin `0.555556 ms`（91.8%）；同规则 p50 `+1.870462` 对 `0.173927 ms`；`+359 minflt/循环` | [`cycles.tsv`](../data/raw/gst_trim_cost_20260901/cycles.tsv)、[`arm_summary.tsv`](../data/raw/gst_trim_cost_20260901/arm_summary.tsv) | [gst L1](#l1-gst-trim-cost) |
| gst trim `0.671556/0.818315/0.842185/0.856944 ms`（p50/p95/p99/max） | [`cycles.tsv`](../data/raw/gst_trim_cost_20260901/cycles.tsv) | [gst L1](#l1-gst-trim-cost) |
| gst 首次 release `51.014041%–51.406250% / 1.277344–1.285156 MiB` | [`cycles.tsv`](../data/raw/gst_trim_cost_20260901/cycles.tsv) | [gst L1](#l1-gst-trim-cost) |

## L2 · 测试板实验复跑

<a id="l2-prerequisites"></a>
### 镜像、SDB 与二进制前置

镜像必须在启动后得到
`BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l`，测试批次的
glibc 必须是 `glibc-2.40-1.6.armv7l`；两项原始基线见
[`preflight_and_integrity.txt`](../data/raw/s4_retention_20260901/preflight_and_integrity.txt) 和
[`board_baseline_llvm_image_20260831.md`](board_baseline_llvm_image_20260831.md#3-三重身份门)。

本仓库不分发镜像文件，也没有记录可验证的镜像文件名、镜像 SHA 或专用烧写器。
HQ 应从负责该 Tizen Unified Toolchain 构建的内部镜像交付渠道取得与上述 BUILD_ID
绑定的 RPI4 镜像，核对交付方校验和，再按该镜像包随附的 RPI4 SD/eMMC 烧写说明
写入介质。仓库中记录的 `reference` 软件源是移动指针，不能代替不可变镜像标识；
这一限制见
[`board_baseline_llvm_image_20260831.md`](board_baseline_llvm_image_20260831.md#3-三重身份门)。
烧写完成后只以三重身份门和 BUILD_ID 判定，不以地址或设备名称判板。

SDB 随 Tizen Studio 提供。基线使用
`Smart Development Bridge version 4.2.25`
([证据](../data/raw/s4_retention_20260901/preflight_and_integrity.txt))；将 Tizen Studio
的 `tools/` 加入 `PATH` 后运行 `sdb version` 核对。板只走 SDB，不配置 SSH。

ARM 二进制不入公开仓库，有两条取得路径：

1. 从内部制品交付取得 S2/S4 使用过的 `alloc_bench.armv7l`，先核对 SHA-256 必须为
   `dca27ec8a027356c3eea2962d936d06e688351499ce56a7c66aa69cd1ea761fd`
   ([证据](../data/raw/s4_retention_20260901/preflight_and_integrity.txt))。
2. 通过负责镜像构建的同源 Tizen Unified Toolchain/GBS 工程准备
   `scratch.armv7l.0`；其中编译器基线为 GCC `14.2.0`
   ([构建记录](cyclic_s2_board_replication_20260831.md#3-二进制目录与-governor))。随后按
   [`tools/alloc_bench/README.md`](../tools/alloc_bench/README.md#build) 构建：

```sh
make -C tools/alloc_bench armv7l ARMV7L_ROOT=/path/to/scratch.armv7l.0
file tools/alloc_bench/alloc_bench.armv7l
sha256sum tools/alloc_bench/alloc_bench.armv7l
```

`file` 应报告动态链接的 ARM EABI5 ELF。旧冻结制品 SHA 与当前固定路径、
`-fdebug-prefix-map=<dir>=.` 构建链的可复现 SHA 分开登记，不能混为一个预期值；完整
SHA、体积与交付方式以
[`deliverables_manifest.json`](../tools/reproduce/deliverables_manifest.json) 为唯一 manifest。
可在两条不同 checkout 路径运行以下 host 测试，核验三个可构建 ELF 的路径独立 SHA：

```sh
python3 tools/reproduce/check_reproducible_build_paths.py
```

若当前工具链构建值与 manifest 的 `reproducible_build_sha256` 不同，先核对源码、GCC、
scratch/sysroot 和 flags；仍不一致时登记为新构建批次，不能称为字节级复跑。

因此“全新 clone + 单独使用本仓库”仍不足以启动含媒体输入的 L2。交付方必须在开始前另行提供
带 SHA-256 manifest 的内部产物包（S4 bench，gst bench/probe/media），或提供可用的
scratch root/sysroot 路径。媒体资产的自产/可再分发 provenance 尚未建立，因此不入
公开仓库；由交付方随交付邮件提供获取位置，收到后按 manifest SHA-256 核对。
**没有内部 bundle 时 board 模式不可启动**，必须登记为外部前置阻断，
不得在板上即兴找文件替代。

<a id="l2-gbs-build"></a>
### HQ 首选：GBS 构建三项 ELF

对三项 ELF，HQ 首选从真实 `git clone` 使用仓库内 spec 和固定快照配置构建：

```sh
git clone <repository-url> glibc_optimization
cd glibc_optimization
gbs -c config/gbs_llvm.conf build -A armv7l --overwrite
RPM=/tmp/glibc-memopt-gbs-llvm/local/repos/tizen_unified_standard/armv7l/RPMS/glibc-memopt-tools-1.0.0-1.armv7l.rpm
rpm -qpl "$RPM"
mkdir -p /tmp/glibc-memopt-rpm && cd /tmp/glibc-memopt-rpm
rpm2cpio "$RPM" | cpio -idm --quiet
sha256sum usr/bin/alloc_bench usr/bin/gst_loop_decode usr/bin/reclaim_probe
mkdir -p /path/to/gbs-bundle
cp usr/bin/alloc_bench /path/to/gbs-bundle/alloc_bench.armv7l
cp usr/bin/gst_loop_decode /path/to/gbs-bundle/gst_loop_decode.armv7l
cp usr/bin/reclaim_probe /path/to/gbs-bundle/reclaim_probe.armv7l
# Add the separately delivered, SHA-verified small_320x240.mp4 before board mode.
```

[`glibc-memopt-tools.spec`](../packaging/glibc-memopt-tools.spec) 一次生成
`alloc_bench`、`gst_loop_decode` 和 `reclaim_probe`；
[`gbs_llvm.conf`](../config/gbs_llvm.conf) 固定到与镜像 BUILD_ID 同源的 Unified
`20260814.092727` 和其 build metadata 指向的 Base `20260813.050338`。RPM NVR、体积、
SHA、buildroot 编译器/glibc 版本及三 ELF 的 `gbs_build_sha256` 记录在
[`deliverables_manifest.json`](../tools/reproduce/deliverables_manifest.json) 和
[`GBS 构建记录`](../data/raw/gbs_package_20260903/README.md)。官方四仓按包名、Provides、
filelists 的来源排查及五项 BuildRequires 版本复核见
[`三工具来源声明`](tool_provenance_20260903.md)。`verify` 会静态检查 spec
与 `%files`；有 `gbs` 时还会实跑并核对已登记产物，无 `gbs` 时明确输出 `SKIPPED`。

GBS 三项 ELF 尚待下一轮板上重基线，因此本轮只闭合 host 构建链；在重基线完成前，
L2 正式判定仍默认使用已冻结制品。旧冻结 bundle 与上节固定路径交叉构建均降为备选。
即使三项 ELF 由 GBS 产生，媒体仍须按 manifest 的包外方式交付。要显式试用 GBS
bundle，使用 `reproduce.sh board --artifact-source gbs ...`，不得把它误写成已验证基线。

<a id="l2-run"></a>
### 完整执行命令

冻结规格的唯一来源是
[`S4 §1`](s4_reference_and_retention_trim_20260901.md#1-执行前冻结规格)，可执行合同是
[`tools/runners/s4_retention_20260901/`](../tools/runners/s4_retention_20260901/)。
不要修改 `run_s4_remote.sh` 内参数。以下示例保留脱敏地址；执行人员在自己的 shell
中替换变量值，报告仍写 `<TEST_BOARD_IP>`。

```sh
export SDB_SERIAL='<TEST_BOARD_IP>:26101'
export S4_REMOTE='/opt/usr/glibc_memopt/s4_retention_20260901'
export S4_HOST='board_results/s4_retention_20260901_reproduction'
export S4_BENCH='/path/to/alloc_bench.armv7l'
export S4_EXPECTED_SHA='dca27ec8a027356c3eea2962d936d06e688351499ce56a7c66aa69cd1ea761fd'
mkdir -p "$S4_HOST"

sdb version
sdb connect '<TEST_BOARD_IP>'
sdb devices
SDB_SERIAL="$SDB_SERIAL" sh \
  tools/runners/s4_retention_20260901/preflight_gate.sh "$S4_HOST/preflight"
grep -Fx IDENTITY_AND_ENV_GATE_PASS "$S4_HOST/preflight/gate_verdict.txt"
sha256sum "$S4_BENCH"

sdb -s "$SDB_SERIAL" shell 'd=/opt/usr/share/crash/livedump; if [ -d "$d" ]; then find "$d" -maxdepth 1 -type f -name "*.zip" | LC_ALL=C sort | while IFS= read -r f; do n=$(wc -c < "$f") || exit 1; m=$(stat -c %Y "$f") || exit 1; h=$(sha256sum "$f" | awk "{print \$1}") || exit 1; printf "%s\t%s\t%s\t%s\n" "$f" "$n" "$m" "$h"; done; fi; rc=$?; echo RC=$rc; test $rc -eq 0 && echo DONE_STABILITY_SNAPSHOT || echo FAIL_STABILITY_SNAPSHOT' >"$S4_HOST/stability_before.tsv.raw"
printf 'remote_path\tsize\tmtime_epoch\tsha256\n' >"$S4_HOST/stability_before.tsv"
tr -d '\r' <"$S4_HOST/stability_before.tsv.raw" | awk -F '\t' 'NF==4 && $1 ~ /^\/opt\/usr\/share\/crash\/livedump\// {print}' >>"$S4_HOST/stability_before.tsv"
```

只有上述门全部成功后才创建固定工作目录并推送四个资产：

```sh
sdb -s "$SDB_SERIAL" shell "test ! -e '$S4_REMOTE' && mkdir -p '$S4_REMOTE'; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_CREATE_WORKDIR || echo FAIL_CREATE_WORKDIR" | tee "$S4_HOST/create_workdir.txt"
grep -Fx RC=0 "$S4_HOST/create_workdir.txt"
grep -Fx DONE_CREATE_WORKDIR "$S4_HOST/create_workdir.txt"

sdb -s "$SDB_SERIAL" push "$S4_BENCH" "$S4_REMOTE/alloc_bench.armv7l"
sdb -s "$SDB_SERIAL" push tools/runners/s4_retention_20260901/run_s4_remote.sh "$S4_REMOTE/run_s4_remote.sh"
sdb -s "$SDB_SERIAL" push tools/runners/s4_retention_20260901/sample_smaps_1s.sh "$S4_REMOTE/sample_smaps_1s.sh"
sdb -s "$SDB_SERIAL" push tools/runners/s4_retention_20260901/medium_1k_16k.hist "$S4_REMOTE/medium_1k_16k.hist"

sdb -s "$SDB_SERIAL" shell "chmod 0755 '$S4_REMOTE/alloc_bench.armv7l' '$S4_REMOTE/run_s4_remote.sh' '$S4_REMOTE/sample_smaps_1s.sh' && sha256sum '$S4_REMOTE/alloc_bench.armv7l' '$S4_REMOTE/medium_1k_16k.hist'; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_ASSET_VERIFY || echo FAIL_ASSET_VERIFY" | tee "$S4_HOST/asset_verify.txt"
grep -F 'dca27ec8a027356c3eea2962d936d06e688351499ce56a7c66aa69cd1ea761fd' "$S4_HOST/asset_verify.txt"
grep -F '2082e156db133f4e6e900aec7c202e44a453d2f23b60225c40251de08a27960b' "$S4_HOST/asset_verify.txt"
grep -Fx RC=0 "$S4_HOST/asset_verify.txt"
grep -Fx DONE_ASSET_VERIFY "$S4_HOST/asset_verify.txt"
```

控制器会再次执行身份/环境/哈希门，记录四核 governor，切到 `performance`，按
S4 §1 顺序运行 A/B 全格，并在所有退出路径恢复 `schedutil`：

```sh
sdb -s "$SDB_SERIAL" shell "EXPECTED_ALLOC_SHA='$S4_EXPECTED_SHA' sh '$S4_REMOTE/run_s4_remote.sh'; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_S4_REMOTE_INVOKE || echo FAIL_S4_REMOTE_INVOKE" | tee "$S4_HOST/remote_invoke.txt"
grep -Fx RC=0 "$S4_HOST/remote_invoke.txt"
grep -Fx DONE_S4_REMOTE_INVOKE "$S4_HOST/remote_invoke.txt"
grep -Fx DONE_S4_CONTROLLER "$S4_HOST/remote_invoke.txt"

sdb -s "$SDB_SERIAL" shell 'd=/opt/usr/share/crash/livedump; if [ -d "$d" ]; then find "$d" -maxdepth 1 -type f -name "*.zip" | LC_ALL=C sort | while IFS= read -r f; do n=$(wc -c < "$f") || exit 1; m=$(stat -c %Y "$f") || exit 1; h=$(sha256sum "$f" | awk "{print \$1}") || exit 1; printf "%s\t%s\t%s\t%s\n" "$f" "$n" "$m" "$h"; done; fi; rc=$?; echo RC=$rc; test $rc -eq 0 && echo DONE_STABILITY_SNAPSHOT || echo FAIL_STABILITY_SNAPSHOT' >"$S4_HOST/stability_after.tsv.raw"
printf 'remote_path\tsize\tmtime_epoch\tsha256\n' >"$S4_HOST/stability_after.tsv"
tr -d '\r' <"$S4_HOST/stability_after.tsv.raw" | awk -F '\t' 'NF==4 && $1 ~ /^\/opt\/usr\/share\/crash\/livedump\// {print}' >>"$S4_HOST/stability_after.tsv"
```

自 2026-09-02 起，每个板上轮次还必须在负载前后分别保存
stability-monitor/livedump 的精确文件清单和计数。v1 规则保留为历史判定；v2 新增
“预登记预期告警”类。新增件必须从归档内部 `dump_reason` 与 `info.json` 核对 PID、
进程名、executable path、发生窗口与数量：与预登记的触发理由、窗口、owner 和数量
上界全部匹配时，记录、归档、按精确路径清理并复核后记为 `EXPECTED` 通过；未观测时
只记 `REGISTERED/NOT-EVALUATED`，不能把“已登记”写成“已发生且通过”。可归因
本轮但未登记或超界的告警仍为 `FAIL`；非本轮或归属不明告警只记 `REPORT_ONLY`，
原样报告且不处置。本项与 dmesg OOM/LMK、zram 和 governor 门并列，不得因数值分析
成功而忽略。机器可读规则见
[`acceptance_bands.json`](../tools/reproduce/acceptance_bands.json)，报告模板与归档/清理
命令见 [`health_gate_template.md`](../tools/reproduce/health_gate_template.md)。

首条预登记为 S4 A 组：`alloc_bench.armv7l` 在 `A/mixed/rep1` 与
`A/medium-only/rep1` 窗口因 `cpu.relative` 产生的 livedump 合计至多 `2` 个，适用
known-alert waiver。这里只证明触发理由与窗口可复现，**未做根因证明**；触发理由、
二进制、窗口或数量任一不符都不在该登记覆盖范围内。

运行完成后在固定目录内生成 hash/size 清单，拉回并用发布的分析器验证；任何一项
失败都先保留 host 证据，不把该格记为完成：

```sh
sdb -s "$SDB_SERIAL" shell "cd '$S4_REMOTE' && find . -type f ! -name board_manifest.sha256 ! -name board_file_sizes.tsv | LC_ALL=C sort | while IFS= read -r f; do sha256sum \"\$f\" || exit 1; done > board_manifest.sha256 && find . -type f ! -name board_file_sizes.tsv | LC_ALL=C sort | while IFS= read -r f; do n=\$(wc -c < \"\$f\") || exit 1; printf '%s\\t%s\\n' \"\$n\" \"\$f\"; done > board_file_sizes.tsv; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_MANIFEST || echo FAIL_MANIFEST" | tee "$S4_HOST/manifest.txt"
grep -Fx RC=0 "$S4_HOST/manifest.txt"
grep -Fx DONE_MANIFEST "$S4_HOST/manifest.txt"

test ! -e "$S4_HOST/board_pull"
sdb -s "$SDB_SERIAL" pull "$S4_REMOTE" "$S4_HOST/board_pull"
python3 tools/runners/s4_retention_20260901/analyze_s4.py \
  --pull "$S4_HOST/board_pull" --output "$S4_HOST/derived"
```

分析成功后才清理精确目录；控制器 trap 已恢复 governor，host 再独立复核：

```sh
sdb -s "$SDB_SERIAL" shell "test '$S4_REMOTE' = '/opt/usr/glibc_memopt/s4_retention_20260901' && rm -rf '$S4_REMOTE' && test ! -e '$S4_REMOTE'; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_FINAL_CLEANUP || echo FAIL_FINAL_CLEANUP" | tee "$S4_HOST/cleanup.txt"
grep -Fx RC=0 "$S4_HOST/cleanup.txt"
grep -Fx DONE_FINAL_CLEANUP "$S4_HOST/cleanup.txt"

sdb -s "$SDB_SERIAL" shell "rmdir /opt/usr/glibc_memopt && test ! -e /opt/usr/glibc_memopt; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_EMPTY_PARENT_CLEANUP || echo FAIL_EMPTY_PARENT_CLEANUP" | tee "$S4_HOST/parent_cleanup.txt"
grep -Fx RC=0 "$S4_HOST/parent_cleanup.txt"
grep -Fx DONE_EMPTY_PARENT_CLEANUP "$S4_HOST/parent_cleanup.txt"

sdb -s "$SDB_SERIAL" shell "n=0; for p in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do g=\$(cat \"\$p\") || exit 1; echo \"\$p=\$g\"; test \"\$g\" = schedutil && n=\$((n+1)); done; test \$n -eq 4; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_GOVERNOR_FINAL || echo FAIL_GOVERNOR_FINAL" | tee "$S4_HOST/governor_final.txt"
grep -Fx RC=0 "$S4_HOST/governor_final.txt"
grep -Fx DONE_GOVERNOR_FINAL "$S4_HOST/governor_final.txt"
```

<a id="l2-acceptance"></a>
### 验收带：确定性项、validity gates 与容差项

验收配置只维护在
[`acceptance_bands.json`](../tools/reproduce/acceptance_bands.json)；本节是它的人工可读
解释。唯一确定性数字来自冻结 payload
([逐周期 TSV](../data/raw/s4_retention_20260901/b_cycles.tsv)、
[健康 JSON](../data/raw/s4_retention_20260901/health.json))：

- released payload 字节数必须与相同 profile/cycle 的冻结值逐值一致；公开基准为
  mixed `5742256/6566672 B`、medium-only `6288384/6293504 B`。
- validity gates：trim 回收量必须是 `4 KiB` 页粒度整数倍；下一周期 `majflt=0`；
  zram `orig/compressed/mem_used_total` 三项 `Δ=0`；dmesg OOM/LMK 零命中。

因此“同条件复现同样的数据”的正式含义是：payload 字节逐值一致，容差项落带，且
validity gates 全部通过。回收量字节值本身不是确定性项。bench/sampler/controller 的
远端 `RC=0/DONE_*`、JSON/XML 可解析、manifest 和现场恢复属于流程完整性前置；任一
失败同样终止该格。

容差项是本指南的跨板/跨批次建议判据，不是新增测量值；中心值依据
[`S4 结果`](s4_reference_and_retention_trim_20260901.md#3-a-组结果新镜像锚点)：

- A 组瞬时释放回收率：`49% ±4 pp`；A 格各 `n=1`，分母为 pre-trim heap。
- B 组 trim 回收/已释放：验收单位固定为每个 profile 的三重复中位，即先取每个重复
  两周期的中位、再取三重复中位；mixed 锚定发布值 `81.661264% ±5 pp`，medium-only
  锚定发布值 `84.446566% ±5 pp`。`n=3` 中位能容忍一个离群重复，但不能覆盖两个偏移
  重复；不以单重复或单周期的回收字节值作硬门。
- 每周期 `trim_reclaimed_kb` 是 banded 参考项，相对同 profile/rep/cycle 发布值允许
  `±1024 KiB`；它用于暴露约 1 MiB arena 台阶，不提升为确定性项。
- 释放点 trim（B 组 valley 与 gst loop-release）：每次调用 `<5 ms`。
- A 组瞬时锚点 trim：每次调用 `<20 ms`；它是大释放锚点的完成时延，不是运行时
  钩子代价数字。
- 下一周期 minflt 增量应与回收页数处于同一数量级；仍要求 majflt 为零。

固定 `seed` 决定负载随机序列，但不钉死 glibc arena 指派。因调度与 arena 归属变化，
单重复可出现约 `1 MiB` 的页粒度台阶；HQ 彩排的 medium-only `rep2` 两个周期就是该
实例，其中逐重复中位实测为 `68.169197%`，两周期分别比发布批少 `1024000 B`。这不
改写发布数字，也不把差异“放宽”为任意波动：
预登记协议用每档三重复中位和 `±5 pp` 带吸收该离散，payload 字节、4 kB 对齐、
majflt、zram 与 OOM/LMK validity gates 仍须成立。实例紧凑证据见
[`s4_medium_only_rep2_reclaim.tsv`](../data/raw/demo_rehearsal_20260902/s4_medium_only_rep2_reclaim.tsv)，
解释见 [`彩排报告 §8.2`](demo_rehearsal_20260902.md#82-s4-验收带对照)。

MemTotal 或 kernel 小版本变化不自动否决以上机制判据，但必须记录为批次协变量。
glibc 主版本必须属于 `2.40` 系；若为 `2.41+`，停止沿用本基线，并按
[`状态报告 §2.5`](glibc_memopt_program_status_report_zh.md#25-版本依赖) 的版本告警重新审计。

<a id="l2-gst-trim-cost"></a>
### 真实并发 GStreamer 目标的 trim 代价复跑

本节复跑第 2 周的 2 臂 × 3 重复实验。冻结参数与判定规则以
[`gst_trim_cost_20260901.md §1`](gst_trim_cost_20260901.md#1-建连前冻结规格) 为唯一来源，
可执行合同位于
[`tools/runners/gst_trim_cost_20260901/`](../tools/runners/gst_trim_cost_20260901/)。媒体资产
继续使用 `l6_gst_release_phase_20260811` 的 `small_320x240.mp4`，必须从内部制品归档取得
并核对 SHA-256
`3df34a234c69d51d543aed8d379aa0e18fe01839e20ac213a1b3061acb67f72d`；公开仓库不分发媒体
或 ARM ELF。

instrumented bench 可从内部制品取得，已验 SHA-256 为
`204d64f5d66419025d2d4c4af40c86a9fb5301bd6e7cde2d8cf9e5df5caf62e6`；也可用
GCC `14.2.0` 的 glibc-2.40 scratch root 与含 GStreamer 1.24 armv7l devel/runtime 链接
输入的兼容 sysroot 重建：

```sh
TOOLCHAIN_ROOT=/path/to/toolchain/scratch.armv7l.0 \
GST_SYSROOT=/path/to/gstreamer/scratch.armv7l.0 \
  tools/runners/gst_trim_cost_20260901/build_armv7l.sh \
  /tmp/gst_loop_decode.armv7l
sha256sum tools/gst_loop_decode/gst_loop_decode.c /tmp/gst_loop_decode.armv7l
```

已验源码 SHA-256 为
`4b00e4ad7fb38c5e51c772e1ba0d8a7d7eb44045d45ec34978317ecaae5d9552`。同一 toolchain、
sysroot 和源码通过固定 `.build/armv7l/gst_loop_decode/` 与
`-fdebug-prefix-map=<dir>=.` 重建；预期 canonical SHA 取 manifest 的
`reproducible_build_sha256`，不是旧冻结制品 SHA。不一致时登记为新构建批次并保留 ELF、
编译器、sysroot 与 SHA 记录，不能声称字节级复跑。

先只读执行身份/环境和能力门。能力脚本会列出 GStreamer 核心、六个 element 的 RPM
归属/安装大小，以及 `/`、`/opt/usr` 空间；若缺包，不得跳过本轮报告中的 `1.2 GiB`
根分区余量预算和安装事务记录。

```sh
export SDB_SERIAL='<TEST_BOARD_IP>:26101'
export GST_REMOTE='/opt/usr/glibc_memopt/gst_trim_cost_20260901'
export GST_HOST='board_results/gst_trim_cost_20260901_reproduction'
export GST_BENCH='/tmp/gst_loop_decode.armv7l'
export GST_PROBE='/path/to/reclaim_probe.armv7l'
export GST_MEDIA='/path/to/small_320x240.mp4'
export GST_EXPECTED_SHA='204d64f5d66419025d2d4c4af40c86a9fb5301bd6e7cde2d8cf9e5df5caf62e6'
export GST_PROBE_EXPECTED_SHA='3b0703fd96dfde95a3287129208784f19f74b4929774fbde644b542e16e441e7'
export GST_MEDIA_EXPECTED_SHA='3df34a234c69d51d543aed8d379aa0e18fe01839e20ac213a1b3061acb67f72d'
mkdir -p "$GST_HOST"

sdb version
sdb connect '<TEST_BOARD_IP>'
sdb devices
SDB_SERIAL="$SDB_SERIAL" sh \
  tools/runners/gst_trim_cost_20260901/preflight_gate.sh "$GST_HOST/preflight"
grep -Fx IDENTITY_AND_ENV_GATE_PASS "$GST_HOST/preflight/gate_verdict.txt"
SDB_SERIAL="$SDB_SERIAL" sh \
  tools/runners/gst_trim_cost_20260901/capability_probe.sh "$GST_HOST/capability"
grep -Fx CAPABILITY_GATE_PASS "$GST_HOST/capability/capability_verdict.txt"

sdb -s "$SDB_SERIAL" shell 'd=/opt/usr/share/crash/livedump; if [ -d "$d" ]; then find "$d" -maxdepth 1 -type f -name "*.zip" | LC_ALL=C sort | while IFS= read -r f; do n=$(wc -c < "$f") || exit 1; m=$(stat -c %Y "$f") || exit 1; h=$(sha256sum "$f" | awk "{print \$1}") || exit 1; printf "%s\t%s\t%s\t%s\n" "$f" "$n" "$m" "$h"; done; fi; rc=$?; echo RC=$rc; test $rc -eq 0 && echo DONE_STABILITY_SNAPSHOT || echo FAIL_STABILITY_SNAPSHOT' >"$GST_HOST/stability_before.tsv.raw"
printf 'remote_path\tsize\tmtime_epoch\tsha256\n' >"$GST_HOST/stability_before.tsv"
tr -d '\r' <"$GST_HOST/stability_before.tsv.raw" | awk -F '\t' 'NF==4 && $1 ~ /^\/opt\/usr\/share\/crash\/livedump\// {print}' >>"$GST_HOST/stability_before.tsv"
```

门通过后才创建固定 `/opt/usr` 目录并推送。下列三个资产 SHA 必须分别为
`204d64…f62e6`、`3b0703…41e7`、`3df34a…f72d` 的完整冻结值；执行时必须检查完整
输出而不是只比较此处缩写。

```sh
sdb -s "$SDB_SERIAL" shell "test ! -e '$GST_REMOTE' && mkdir -p '$GST_REMOTE'; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_CREATE_WORKDIR || echo FAIL_CREATE_WORKDIR"
sdb -s "$SDB_SERIAL" push "$GST_BENCH" "$GST_REMOTE/gst_loop_decode.armv7l"
sdb -s "$SDB_SERIAL" push "$GST_PROBE" "$GST_REMOTE/reclaim_probe.armv7l"
sdb -s "$SDB_SERIAL" push "$GST_MEDIA" "$GST_REMOTE/small_320x240.mp4"
sdb -s "$SDB_SERIAL" push tools/runners/gst_trim_cost_20260901/run_gst_trim_cost_remote.sh "$GST_REMOTE/run_gst_trim_cost_remote.sh"
sdb -s "$SDB_SERIAL" push tools/runners/gst_trim_cost_20260901/sample_smaps_1s.sh "$GST_REMOTE/sample_smaps_1s.sh"
sdb -s "$SDB_SERIAL" shell "chmod 0755 '$GST_REMOTE/gst_loop_decode.armv7l' '$GST_REMOTE/reclaim_probe.armv7l' '$GST_REMOTE/run_gst_trim_cost_remote.sh' '$GST_REMOTE/sample_smaps_1s.sh' && cd '$GST_REMOTE' && sha256sum gst_loop_decode.armv7l reclaim_probe.armv7l small_320x240.mp4; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_ASSET_VERIFY || echo FAIL_ASSET_VERIFY"
```

controller 固定运行 `none-r1 → trim-r1 → trim-r2 → none-r2 → none-r3 → trim-r3`，每格
51 轮、每轮 PLAYING `20 s`、NULL valley `1 s`；不要编辑脚本内矩阵：

```sh
sdb -s "$SDB_SERIAL" shell "EXPECTED_GST_SHA='$GST_EXPECTED_SHA' EXPECTED_RECLAIM_SHA='$GST_PROBE_EXPECTED_SHA' EXPECTED_MEDIA_SHA='$GST_MEDIA_EXPECTED_SHA' sh '$GST_REMOTE/run_gst_trim_cost_remote.sh'; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_GST_TRIM_REMOTE_INVOKE || echo FAIL_GST_TRIM_REMOTE_INVOKE" | tee "$GST_HOST/remote_invoke.txt"
grep -Fx RC=0 "$GST_HOST/remote_invoke.txt"
grep -Fx DONE_GST_TRIM_REMOTE_INVOKE "$GST_HOST/remote_invoke.txt"
grep -Fx DONE_GST_TRIM_CONTROLLER "$GST_HOST/remote_invoke.txt"

sdb -s "$SDB_SERIAL" shell 'd=/opt/usr/share/crash/livedump; if [ -d "$d" ]; then find "$d" -maxdepth 1 -type f -name "*.zip" | LC_ALL=C sort | while IFS= read -r f; do n=$(wc -c < "$f") || exit 1; m=$(stat -c %Y "$f") || exit 1; h=$(sha256sum "$f" | awk "{print \$1}") || exit 1; printf "%s\t%s\t%s\t%s\n" "$f" "$n" "$m" "$h"; done; fi; rc=$?; echo RC=$rc; test $rc -eq 0 && echo DONE_STABILITY_SNAPSHOT || echo FAIL_STABILITY_SNAPSHOT' >"$GST_HOST/stability_after.tsv.raw"
printf 'remote_path\tsize\tmtime_epoch\tsha256\n' >"$GST_HOST/stability_after.tsv"
tr -d '\r' <"$GST_HOST/stability_after.tsv.raw" | awk -F '\t' 'NF==4 && $1 ~ /^\/opt\/usr\/share\/crash\/livedump\// {print}' >>"$GST_HOST/stability_after.tsv"
```

运行成功后生成清单、拉回并强制解析所有 JSON；只有分析器成功后才能清理：

```sh
sdb -s "$SDB_SERIAL" shell "cd '$GST_REMOTE' && find . -type f ! -name board_manifest.sha256 ! -name board_file_sizes.tsv | LC_ALL=C sort | while IFS= read -r f; do sha256sum \"\$f\" || exit 1; done > board_manifest.sha256 && find . -type f ! -name board_file_sizes.tsv | LC_ALL=C sort | while IFS= read -r f; do n=\$(wc -c < \"\$f\") || exit 1; printf '%s\\t%s\\n' \"\$n\" \"\$f\"; done > board_file_sizes.tsv; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_MANIFEST || echo FAIL_MANIFEST"
test ! -e "$GST_HOST/board_pull"
sdb -s "$SDB_SERIAL" pull "$GST_REMOTE" "$GST_HOST/board_pull"
python3 tools/runners/gst_trim_cost_20260901/analyze_gst_trim_cost.py \
  --pull "$GST_HOST/board_pull" --output "$GST_HOST/derived"

sdb -s "$SDB_SERIAL" shell "test '$GST_REMOTE' = '/opt/usr/glibc_memopt/gst_trim_cost_20260901' && rm -rf '$GST_REMOTE' && test ! -e '$GST_REMOTE'; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_FINAL_CLEANUP || echo FAIL_FINAL_CLEANUP"
sdb -s "$SDB_SERIAL" shell "rmdir /opt/usr/glibc_memopt && test ! -e /opt/usr/glibc_memopt; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_EMPTY_PARENT_CLEANUP || echo FAIL_EMPTY_PARENT_CLEANUP"
sdb -s "$SDB_SERIAL" shell "ok=1; n=0; for p in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do if g=\$(cat \"\$p\"); then echo \"\$p=\$g\"; test \"\$g\" = schedutil && n=\$((n+1)); else ok=0; fi; done; test \$ok -eq 1 && test \$n -eq 4; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_GOVERNOR_FINAL || echo FAIL_GOVERNOR_FINAL"
```

当前基准批次的分析器预期输出原文为：

```text
validated cells=6 cycles=306 primary=300
delta_p99_ms=6.228611 none_dispersion_ms=6.784167 visible=false
```

可用发布的紧凑输入逐字节复算当前结果：
[`cycles.tsv`](../data/raw/gst_trim_cost_20260901/cycles.tsv)、
[`repetitions.tsv`](../data/raw/gst_trim_cost_20260901/repetitions.tsv)、
[`arm_summary.tsv`](../data/raw/gst_trim_cost_20260901/arm_summary.tsv)、
[`comparison.json`](../data/raw/gst_trim_cost_20260901/comparison.json) 与
[`health.json`](../data/raw/gst_trim_cost_20260901/health.json)。完整解释见
[`实验报告`](gst_trim_cost_20260901.md)。

流程完整性项：资产 SHA 与冻结批次一致；6 格顺序、每格 51 轮、主统计每重复 50 个
样本逐项齐全；none 臂全部是未调用哨兵、trim 臂每格恰有 51 次调用；306 组 pre/post
JSON 均可解析且 PID 恒定；bench/sampler/controller 全部退出 0；dmesg 零 OOM/LMK；四核
最终均为 `schedutil`；板端目录已删除。zram 三列必须取得同批前后值并报告 delta，不把
跨批次绝对值当作常量。

同一 stability-monitor v2 健康门也适用于 gst：运行前后记录告警清单与计数，
对新增件逐一做 PID/进程/可执行路径归因。当前没有 gst 预登记项，因此可归因本轮的
新增告警仍是 `FAIL`；非本轮或归属不明的新增告警记 `REPORT_ONLY`、只报告不动。

当前已执行批次的附加 capture-meta `majflt` 因 POSIX sh `$10` 展开错误而统一为 `S0`；
发布 controller 已改用 `${10}`。分析器只允许整批 306 对均为这一已知缺陷或整批均为
数值，当前批明确标作不可用；目标内逐循环 `getrusage` 与外部 1 s `/proc/stat` majflt
仍是两条强制数值源。复跑发布版 harness 时该字段应为数值，不应再出现 `S0`。

业务 p99 方向是 `REPORT_ONLY`：workflow 只硬校验 nearest-rank、三重复中位、none
`max−min` 离散带和严格 `>` 比较是否正确执行；`visible=true/false` 本身都不触发验收
FAIL。若复跑板上得到“可见”，应保留三重复原值，报告超出 none 离散带的 margin，并
作为该批业务代价发现上报，不改写为 workflow 故障。回收量只与既有
`48.9451% / 1.359375 MiB` 做相容性对照；该值来自 `<TEST_IMAGE_B>` /
`glibc-2.40-2.8`，是相容性参考、非冻结矩阵。
并发 trim 的 p50/p95/p99/max 必须完整报告，并与 S4 合成释放点分档中位
mixed `1.233269 ms` / medium-only `1.218361 ms` 比较，不能
用单个中位数代替尾部。

当前批次的 153 次 trim p50/p95/p99/max 为
`0.671556/0.818315/0.842185/0.856944 ms`；首次 release 为
`51.014041–51.406250% / 1.277344–1.285156 MiB`。这些是复跑的参考结果而非新的硬阈值；
正式输出仍按上面的预登记 p99 规则计算，方向记 `REPORT_ONLY`。

## L3 · 产品板测量复现（可选）

该层需要产品板访问、可用的遥控按键注入环境，以及继续执行“只读采集、不改配置、
不装包、不替换产品二进制”的纪律。产品板地址属于外部依赖，执行前需由 PM 提供
当时地址；报告必须使用既有脱敏代号。

采集合同位于
[`tools/runners/product_cyclic_target_probe_20260814/`](../tools/runners/product_cyclic_target_probe_20260814/)。
先运行 `vk_preflight.sh` 验证按键与生命周期；再并行启动
`collect_timeseries.sh` 和 `run_vk_rounds.sh`。采集脚本固定写入板端
`/tmp/product_cyclic_target_probe_20260814`，拉回后必须清理并复核不存在。

```sh
export PRODUCT_SERIAL='<PRODUCT_BOARD_IP>:26101'
export PRODUCT_HOST='board_results/product_cyclic_target_probe_reproduction'
mkdir -p "$PRODUCT_HOST/scripts"
test ! -e "$PRODUCT_HOST/raw"

sdb -s "$PRODUCT_SERIAL" push tools/runners/product_cyclic_target_probe_20260814/vk_preflight.sh /tmp/vk_preflight.sh
sdb -s "$PRODUCT_SERIAL" push tools/runners/product_cyclic_target_probe_20260814/collect_baseline.sh /tmp/collect_baseline.sh
sdb -s "$PRODUCT_SERIAL" push tools/runners/product_cyclic_target_probe_20260814/collect_timeseries.sh /tmp/collect_timeseries.sh
sdb -s "$PRODUCT_SERIAL" push tools/runners/product_cyclic_target_probe_20260814/run_vk_rounds.sh /tmp/run_vk_rounds.sh
sdb -s "$PRODUCT_SERIAL" shell 'sh /tmp/vk_preflight.sh'
sdb -s "$PRODUCT_SERIAL" shell 'sh /tmp/collect_baseline.sh'
sdb -s "$PRODUCT_SERIAL" shell 'SAMPLES=660 sh /tmp/collect_timeseries.sh' >"$PRODUCT_HOST/collector.stdout" 2>&1 &
collector_host_pid=$!
sdb -s "$PRODUCT_SERIAL" shell 'sh /tmp/run_vk_rounds.sh' >"$PRODUCT_HOST/runner.stdout" 2>&1
wait "$collector_host_pid"
sdb -s "$PRODUCT_SERIAL" pull /tmp/product_cyclic_target_probe_20260814 "$PRODUCT_HOST/raw"
```

已发布分析器依赖原始 `raw/`、脚本 `scripts/` 的同级布局；复制后运行：

```sh
cp tools/runners/product_cyclic_target_probe_20260814/analyze_cyclic.py "$PRODUCT_HOST/scripts/analyze_cyclic.py"
python3 "$PRODUCT_HOST/scripts/analyze_cyclic.py"
python3 tools/runners/cyclic_fall_attribution_20260901/analyze_attribution.py \
  --timeseries "$PRODUCT_HOST/raw/timeseries.tsv" \
  --keys "$PRODUCT_HOST/raw/key_timeline.tsv" \
  --published-analyzer "$PRODUCT_HOST/scripts/analyze_cyclic.py" \
  --output "$PRODUCT_HOST/attribution"
```

拉回和解析完成后，删除上面的精确 `/tmp` 目录和四个辅助脚本，复核目标 PID 未变化、
临时路径不存在，并保存清理原文。L3 不执行，不影响 L1 对已发布数字的逐字节复算，
也不影响 L2 对 S4 Demo 数字的板上独立复跑覆盖。

```sh
sdb -s "$PRODUCT_SERIAL" shell 'test /tmp/product_cyclic_target_probe_20260814 = /tmp/product_cyclic_target_probe_20260814 && rm -rf /tmp/product_cyclic_target_probe_20260814 /tmp/vk_preflight.sh /tmp/collect_baseline.sh /tmp/collect_timeseries.sh /tmp/run_vk_rounds.sh && test ! -e /tmp/product_cyclic_target_probe_20260814; rc=$?; echo RC=$rc; test $rc -eq 0 && echo DONE_PRODUCT_CYCLIC_CLEANUP || echo FAIL_PRODUCT_CYCLIC_CLEANUP'
```

## 后续板上报告的复现合同

自本指南起，任何板上轮次报告都必须自带“复现”小节，并作为 review 检查项：

- 给出该轮 `tools/runners/<轮次目录>/` harness 路径；
- 链接先于结果冻结的参数规格，禁止依据结果回改；
- 分开列确定性验收项、validity gates 与跨板/跨批次容差带；
- 给出身份门、完整性、退出标志、现场恢复与清理的判定方法。
- 给出 stability-monitor 运行前后告警计数与新增归因；按 v2 区分预登记
  实际命中后的 `EXPECTED`、未观测的 `REGISTERED/NOT-EVALUATED`、未登记我方 `FAIL`
  与非我方/不明 `REPORT_ONLY`。预期告警必须满足理由、
  窗口、owner 和数量上界，并完成归档、精确清理与二次复核；登记表与报告字段见
  [`health_gate_template.md`](../tools/reproduce/health_gate_template.md)。
