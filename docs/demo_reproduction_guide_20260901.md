> Public archive note: application/process names are aliases. Board identifiers,
> image delivery paths, and local filesystem paths are sanitized.

# HQ Demo 复现指南

- 日期：2026-09-01
- 目标：让具备 LLVM/Tizen 工具链基础、但不了解本项目的工程人员分层复现 Demo 数字
- 证据边界：L1 只读公开仓库；L2 重跑测试板合成实验；L3 可选重采产品板只读时序
- 主报告：[`demo_narrative_20260901.md`](demo_narrative_20260901.md)

三个层级相互解耦。L1 可以逐字节核对已发布派生证据；L2 可以独立重跑测试板
S4 与真实多线程 GStreamer release 实验；L3 只在需要重新取得产品侧时序时执行，
不是 L1/L2 的前置。

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
下降窗为零、无缺行和无 PID 变化；中位峰谷为 `6212 kB`，即 Demo 中的
`6.2 MB`。这些值也已固化在
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
    times = [Decimal(r["trim_elapsed_ms"]) for r in v if r["profile"] == profile]
    cells = {r["trim_at"]: r for r in b if r["profile"] == profile and r["rep"] == "1"}
    extra = int(cells["valley"]["cycle1_next_minflt"]) - int(cells["none"]["cycle1_next_minflt"])
    med = statistics.median(times).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    print("%s trim_ms_median=%s next_minflt_extra=%+d" % (profile, med, extra))
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
mixed trim_ms_median=1.233269 next_minflt_extra=+1351
medium-only trim_ms_median=1.218361 next_minflt_extra=+1465
released_payload_bytes: mixed=5742256,6566672 medium-only=6288384,6293504
reclaimed_4k_aligned=12/12
majflt_all_zero=true
zram_deltas=0,0,0 dmesg_increment=0 oom_lmk=0
```

### Demo 数字到公开输入的总表

| Demo 展示值 | 公开输入 | 复算入口 |
|---|---|---|
| ServiceA `6.2 MB`（精确中位 `6212 kB`） | [`serviceA_fall_recheck.tsv`](../data/raw/cyclic_fall_attribution_20260901/serviceA_fall_recheck.tsv) | [ServiceA](#l1-servicea) |
| 旧 `19.683240 s` 为伪影 | [`summary.json`](../data/raw/cyclic_fall_attribution_20260901/summary.json) | [ServiceA](#l1-servicea) |
| `enlightenment +1736 kB` | [`release_ratio_phenotypes.tsv`](../data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv) | [表型](#l1-phenotypes) |
| `ServiceH 2360/+868/+580 kB` | [`plateau_cyclic_crosscheck.tsv`](../data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv)、[`release_ratio_phenotypes.tsv`](../data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv) | [表型](#l1-phenotypes) |
| `ServiceA +788 kB` | [`plateau_cyclic_crosscheck.tsv`](../data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv) | [表型](#l1-phenotypes) |
| 批量相位 `48.9% / 1.36 MiB × 8` | [`batch_release_phase.tsv`](../data/raw/demo_reproduction_20260901/batch_release_phase.tsv) | [批量相位](#l1-batch-release) |
| S4 `51.074077% / 50.387886%` | [`a_cells.tsv`](../data/raw/s4_retention_20260901/a_cells.tsv) | [S4](#l1-s4) |
| S4 `80.175875%–85.453954%`、`1.233269/1.218361 ms`、`+1351/+1465 minflt` | [`b_cycles.tsv`](../data/raw/s4_retention_20260901/b_cycles.tsv)、[`b_cells.tsv`](../data/raw/s4_retention_20260901/b_cells.tsv) | [S4](#l1-s4) |
| S4 `majflt=0`、zram 三项 `Δ=0`、OOM/LMK `0` | [`health.json`](../data/raw/s4_retention_20260901/health.json) | [S4](#l1-s4) |

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

`file` 应报告动态链接的 ARM EABI5 ELF；SHA 应与上面的已验产物一致。若 SHA 不同，
先核对源文件、GCC、scratch root 和 flags；仍不一致时只能登记为新构建批次，不能把
它称为本 S4 的字节级复跑。

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
mkdir -p "$S4_HOST"

sdb version
sdb connect '<TEST_BOARD_IP>'
sdb devices
SDB_SERIAL="$SDB_SERIAL" sh \
  tools/runners/s4_retention_20260901/preflight_gate.sh "$S4_HOST/preflight"
grep -Fx IDENTITY_AND_ENV_GATE_PASS "$S4_HOST/preflight/gate_verdict.txt"
sha256sum "$S4_BENCH"
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
sdb -s "$SDB_SERIAL" shell "sh '$S4_REMOTE/run_s4_remote.sh'; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_S4_REMOTE_INVOKE || echo FAIL_S4_REMOTE_INVOKE" | tee "$S4_HOST/remote_invoke.txt"
grep -Fx RC=0 "$S4_HOST/remote_invoke.txt"
grep -Fx DONE_S4_REMOTE_INVOKE "$S4_HOST/remote_invoke.txt"
grep -Fx DONE_S4_CONTROLLER "$S4_HOST/remote_invoke.txt"
```

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

sdb -s "$SDB_SERIAL" shell "n=0; for p in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do g=\$(cat \"\$p\") || exit 1; echo \"\$p=\$g\"; test \"\$g\" = schedutil && n=\$((n+1)); done; test \$n -eq 4; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_GOVERNOR_FINAL || echo FAIL_GOVERNOR_FINAL" | tee "$S4_HOST/governor_final.txt"
grep -Fx RC=0 "$S4_HOST/governor_final.txt"
grep -Fx DONE_GOVERNOR_FINAL "$S4_HOST/governor_final.txt"
```

<a id="l2-acceptance"></a>
### 验收带：确定性项与容差项

确定性项来自冻结 payload、页粒度及健康门
([逐周期 TSV](../data/raw/s4_retention_20260901/b_cycles.tsv)、
[健康 JSON](../data/raw/s4_retention_20260901/health.json))：

- released payload 字节数必须与相同 profile/cycle 的冻结值逐值一致；公开基准为
  mixed `5742256/6566672 B`、medium-only `6288384/6293504 B`。
- trim 回收量必须是 `4 kB` 页粒度的整数倍。
- 下一周期 `majflt=0`；zram `orig/compressed/mem_used_total` 三项 `Δ=0`。
- dmesg 增量中 OOM/LMK 必须零命中，bench/sampler/控制器必须均有远端
  `RC=0` 和对应 `DONE_*`。

容差项是本指南的跨板/跨批次建议判据，不是新增测量值；中心值依据
[`S4 结果`](s4_reference_and_retention_trim_20260901.md#3-a-组结果新镜像锚点)：

- A 组瞬时释放回收率：`49% ±4 pp`。
- B 组 trim 回收/已释放：按每个 profile 的重复中位验收 `80% ±5 pp`，不把单格极值
  当作硬上限。
- 单次 trim 调用：`<5 ms`。
- 下一周期 minflt 增量应与回收页数处于同一数量级；仍要求 majflt 为零。

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
sysroot 和源码应重建出上述二进制 SHA；不一致时登记为新构建批次并保留 ELF、编译器、
sysroot 与 SHA 记录，不能声称字节级复跑。

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
sdb -s "$SDB_SERIAL" shell "sh '$GST_REMOTE/run_gst_trim_cost_remote.sh'; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_GST_TRIM_REMOTE_INVOKE || echo FAIL_GST_TRIM_REMOTE_INVOKE" | tee "$GST_HOST/remote_invoke.txt"
grep -Fx RC=0 "$GST_HOST/remote_invoke.txt"
grep -Fx DONE_GST_TRIM_REMOTE_INVOKE "$GST_HOST/remote_invoke.txt"
grep -Fx DONE_GST_TRIM_CONTROLLER "$GST_HOST/remote_invoke.txt"
```

运行成功后生成清单、拉回并强制解析所有 JSON；只有分析器成功后才能清理：

```sh
sdb -s "$SDB_SERIAL" shell "cd '$GST_REMOTE' && find . -type f ! -name board_manifest.sha256 ! -name board_file_sizes.tsv | LC_ALL=C sort | while IFS= read -r f; do sha256sum \"\$f\" || exit 1; done > board_manifest.sha256 && find . -type f ! -name board_file_sizes.tsv | LC_ALL=C sort | while IFS= read -r f; do n=\$(wc -c < \"\$f\") || exit 1; printf '%s\\t%s\\n' \"\$n\" \"\$f\"; done > board_file_sizes.tsv; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_MANIFEST || echo FAIL_MANIFEST"
test ! -e "$GST_HOST/board_pull"
sdb -s "$SDB_SERIAL" pull "$GST_REMOTE" "$GST_HOST/board_pull"
python3 tools/runners/gst_trim_cost_20260901/analyze_gst_trim_cost.py \
  --pull "$GST_HOST/board_pull" --output "$GST_HOST/derived"

sdb -s "$SDB_SERIAL" shell "test '$GST_REMOTE' = '/opt/usr/glibc_memopt/gst_trim_cost_20260901' && rm -rf '$GST_REMOTE' && test ! -e '$GST_REMOTE'; rc=\$?; echo RC=\$rc; test \$rc -eq 0 && echo DONE_FINAL_CLEANUP || echo FAIL_FINAL_CLEANUP"
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

确定性验收项：资产 SHA 与冻结批次一致；6 格顺序、每格 51 轮、主统计每重复 50 个
样本逐项齐全；none 臂全部是未调用哨兵、trim 臂每格恰有 51 次调用；306 组 pre/post
JSON 均可解析且 PID 恒定；bench/sampler/controller 全部退出 0；dmesg 零 OOM/LMK；四核
最终均为 `schedutil`；板端目录已删除。zram 三列必须取得同批前后值并报告 delta，不把
跨批次绝对值当作常量。

当前已执行批次的附加 capture-meta `majflt` 因 POSIX sh `$10` 展开错误而统一为 `S0`；
发布 controller 已改用 `${10}`。分析器只允许整批 306 对均为这一已知缺陷或整批均为
数值，当前批明确标作不可用；目标内逐循环 `getrusage` 与外部 1 s `/proc/stat` majflt
仍是两条强制数值源。复跑发布版 harness 时该字段应为数值，不应再出现 `S0`。

容差/判定项不使用看结果后新增的固定比例：业务 p99 仍严格按预登记门——trim 三重复
p99 的中位数减 none 三重复 p99 的中位数，只有严格超过 none 三重复 p99 的 `max−min`
离散带才判“代价可见”。回收量只与既有 `48.9451% / 1.359375 MiB` 做相容性对照；
并发 trim 的 p50/p95/p99/max 必须完整报告，并与 S4 单线程约 `1.2 ms` 描述比较，不能
用单个中位数代替尾部。

当前批次的 153 次 trim p50/p95/p99/max 为
`0.671556/0.818315/0.842185/0.856944 ms`；首次 release 为
`51.014041–51.406250% / 1.277344–1.285156 MiB`。这些是复跑的参考结果而非新的硬阈值；
正式业务裁决仍只用上面的预登记 p99 离散门。

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
- 分开列确定性验收项与跨板/跨批次容差带；
- 给出身份门、完整性、退出标志、现场恢复与清理的判定方法。
