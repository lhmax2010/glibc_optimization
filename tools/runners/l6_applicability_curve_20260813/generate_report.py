#!/usr/bin/env python3
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "board_results/l6_applicability_curve_20260813"
RUNS = list(csv.DictReader((RAW / "summary/runs.tsv").open(), delimiter="\t"))
CELLS = list(csv.DictReader((RAW / "summary/cells_median.tsv").open(), delimiter="\t"))
ORDER = [
    "pct25", "baseline", "pct75", "pct90", "size_small", "size_medium",
    "live1024", "live16384", "order_interleave", "x_medium90_large",
    "x_small90_large_interleave", "x_mixed75_large_interleave",
]
RUNS.sort(key=lambda r: (ORDER.index(r["cell"]), int(r["rep"])))
CELLS.sort(key=lambda r: ORDER.index(r["cell"]))
BY_CELL = {r["cell"]: r for r in CELLS}


def i(row, key):
    return int(float(row[key]))


def f(row, key, digits=2):
    return f"{float(row[key]):.{digits}f}"


def median_row(row):
    return (
        f"| {row['cell']} | {row['profile']} | {row['release_pct']}% / "
        f"{row['live_set']} / {row['release_order']} | "
        f"{f(row, 'released_payload_kb', 1)} / {f(row, 'theoretical_release_kb', 1)} | "
        f"{i(row, 'glibc_pd_pretrim_kb')} -> {i(row, 'glibc_pd_posttrim_kb')} | "
        f"{i(row, 'a_ceiling_kb')} | {f(row, 'reclaim_pct_of_pretrim')} / "
        f"{f(row, 'return_pct_of_payload')} | {f(row, 'theoretical_to_reclaimed_ratio', 3)} | "
        f"{i(row, 'mi_release_rest_delta_b')} / {i(row, 'mi_release_unsorted_delta_b')} | "
        f"{i(row, 'throughput_ops_s')} | {i(row, 'p99_ns')} | "
        f"{f(row, 'trim_elapsed_ms', 3)} | {i(row, 'posttrim_minflt')} / "
        f"{i(row, 'posttrim_majflt')} |"
    )


def curve_row(label, row):
    return (
        f"| {label} | {i(row, 'a_ceiling_kb')} | "
        f"{f(row, 'reclaim_pct_of_pretrim')} | {f(row, 'return_pct_of_payload')} | "
        f"{f(row, 'trim_elapsed_ms', 3)} | {i(row, 'posttrim_minflt')} / "
        f"{i(row, 'posttrim_majflt')} |"
    )


lines = []
add = lines.append
add("# L6 作用条件的定量刻画（受控扫描）")
add("")
add("状态：**冻结矩阵已完成，36/36 次有效运行**")
add("")
add("记录日期：2026-08-13；板端时间为 KST（`+0900`）。")
add("")
add("原始证据根：`board_results/l6_applicability_curve_20260813/`。本报告只记录事实与派生量，不作上线裁决。")
add("")
add("## 1. 身份门与协变量")
add("")
add("三重身份门通过：")
add("")
add("```text")
add("IDENTITY_OK")
add("Linux localhost 6.12.80-arm-rpi4-v7l ... armv7l GNU/Linux")
add('PRETTY_NAME="Tizen 11.0.0 (Tizen11.0/Unified)"')
add("BUILD_ID=<TEST_IMAGE_B>")
add("glibc-2.40-2.8.armv7l")
add("```")
add("")
add("| 协变量 | 实测 |")
add("|---|---|")
add("| MemTotal / 初始 MemAvailable | 3,976,480 / 3,398,912 kB |")
add("| CPU | `0-3` online，四核 governor 均为 `performance` |")
add("| zram/swap | `/dev/zram0` 1,590,588 kB，初始 Used=0 |")
add("| overcommit / THP | `vm.overcommit_memory=0`；THP 路径不存在 |")
add("| 图形环境 | display-manager PID 2600，active/running，`NRestarts=3050`；`/run/wayland-0` 存在 |")
add("| UI 健康锚 | AppUIB PID 21210；AppUIA PID 23862 |")
add("")
add("矩阵开始/结束时 MemAvailable 为 3,372,708 / 3,387,184 kB；36 次运行前最小值为 "
    f"{min(i(r, 'memavailable_pre_kb') for r in RUNS):,} kB。")
add("")
add("## 2. 工具、smoke 与冻结矩阵")
add("")
add("`alloc_bench.armv7l` SHA-256 为 `b33d727b1550924d623522f3eeb4c2d188ab3548edd5d593086b434663cb98f6`；")
add("扩展版 host 验证仍为 selftest `PASS=12 FAIL=0`。扩展包括 `--release-order`、四阶段 malloc_info、")
add("trim 前后 glibc-heap PD、trim 耗时与 post-trim fault 计数；schema 仍为 `alloc_bench_v1_1`。")
add("")
add("板上 smoke 命令使用 `mixed`、4 线程、duration 5 s、idle 5 s、release 50%、high、trim。结果：")
add("")
add("```text")
add("EXIT=0; schema=alloc_bench_v1_1; idle_trim_ret=1")
add("glibc_heap_pd_kb_pretrim/posttrim/postrefault=108168/58260/59312")
add("released_bytes=44496896; trim_elapsed_ms=11.159797")
add("throughput_ops_per_s=2033431.917; p99_ns=1235")
add("```")
add("")
add("冻结统一参数未改变：")
add("")
add("```text")
add("--threads 4 --seed 20260813 --warmup 5 --duration 20 --idle 15")
add("--idle-trim --post-trim-ops-per-thread 4096")
add("```")
add("")
add("矩阵为 12 格 x 3 轮；未降 live-set、未补跑、未改顺序。每轮间隔 5 s。")
add("")
add("## 3. 36 次运行总表")
add("")
add("`pre/post PD`、`A`、MemAvailable、payload 均为 KiB；rest/unsorted delta 为 byte。")
add("回收率=`A/pretrim glibc PD`；归还率=`A/实际释放 payload`。归还率可超过 100%，因为 PD 下降还包含")
add("chunk/页对齐、allocator 元数据及本次分类区间内非 payload 的已脏页，不等同于应用 payload 守恒。")
add("")
add("| 格 | rep | MemAvail pre | payload | pre/post PD | A | 回收率% | 归还率% | rest delta | unsorted delta | ops/s | p99 ns | trim ms | min/maj faults |")
add("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for r in RUNS:
    add(
        f"| {r['cell']} | {r['rep']} | {i(r, 'memavailable_pre_kb')} | "
        f"{f(r, 'released_payload_kb', 1)} | {i(r, 'glibc_pd_pretrim_kb')}/{i(r, 'glibc_pd_posttrim_kb')} | "
        f"{i(r, 'a_ceiling_kb')} | {f(r, 'reclaim_pct_of_pretrim')} | "
        f"{f(r, 'return_pct_of_payload')} | {i(r, 'mi_release_rest_delta_b')} | "
        f"{i(r, 'mi_release_unsorted_delta_b')} | {i(r, 'throughput_ops_s')} | "
        f"{i(r, 'p99_ns')} | {f(r, 'trim_elapsed_ms', 3)} | "
        f"{i(r, 'posttrim_minflt')}/{i(r, 'posttrim_majflt')} |"
    )
add("")
add("## 4. 每格中位数与 M7")
add("")
add("`payload/theory` 为实际/理论释放 KiB；`理论/A` 为理论 payload 除以实际 PD 回收量。")
add("")
add("| 格 | profile | release/live/order | payload/theory | pre->post PD | A | 回收/归还% | 理论/A | rest/unsorted delta B | ops/s | p99 | trim ms | min/maj |")
add("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
for r in CELLS:
    add(median_row(r))
add("")
add("四阶段 malloc_info 中位数如下，单元为 `fast/rest/unsorted` byte；arena 为 `measure/release/posttrim/idle`：")
add("")
add("| 格 | measure F/R/U | release F/R/U | posttrim F/R/U | idle F/R/U | arenas |")
add("|---|---:|---:|---:|---:|---:|")
for r in CELLS:
    tri = lambda phase: "/".join(str(i(r, f"mi_{phase}_{x}_b")) for x in ("fast", "rest", "unsorted"))
    arenas = "/".join(str(i(r, f"arena_{x}")) for x in ("measure", "release", "posttrim", "idle"))
    add(f"| {r['cell']} | {tri('measure')} | {tri('release')} | {tri('posttrim')} | {tri('idle')} | {arenas} |")
add("")
add("12/12 格的 release rest 与 unsorted 均为正增长，且 12/12 的 `trim_ret=1`；每格 arena 中位数在四阶段均为 5。")
add("")
add("## 5. 四条曲线")
add("")
add("以下均为 n=3 中位数。除表头自变量外，其余条件固定在 baseline。")
add("")
add("### 5.1 释放比例")
add("")
add("| release | A KiB | 回收率% | 归还率% | trim ms | min/maj |")
add("|---:|---:|---:|---:|---:|---:|")
for name, label in (("pct25", "25%"), ("baseline", "50%"), ("pct75", "75%"), ("pct90", "90%")):
    add(curve_row(label, BY_CELL[name]))
add("")
add("### 5.2 尺寸分布")
add("")
add("| 尺寸 | A KiB | 回收率% | 归还率% | trim ms | min/maj |")
add("|---|---:|---:|---:|---:|---:|")
for name, label in (("size_small", "small 16-256 B"), ("baseline", "mixed 16 B-64 KiB"), ("size_medium", "medium 1-16 KiB")):
    add(curve_row(label, BY_CELL[name]))
add("")
add("### 5.3 live-set")
add("")
add("| 对象/线程 | A KiB | 回收率% | 归还率% | trim ms | min/maj |")
add("|---:|---:|---:|---:|---:|---:|")
for name, label in (("live1024", "1024"), ("baseline", "4096"), ("live16384", "16384")):
    add(curve_row(label, BY_CELL[name]))
add("")
add("### 5.4 释放顺序")
add("")
add("| order | A KiB | 回收率% | 归还率% | trim ms | min/maj |")
add("|---|---:|---:|---:|---:|---:|")
for name, label in (("baseline", "high"), ("order_interleave", "interleave")):
    add(curve_row(label, BY_CELL[name]))
add("")
add("## 6. 已测判据表与真实目标定位")
add("")
add("本表是对 12 个实测点的查表，不在未测组合间插值，也不外推到任意应用。")
add("")
add("| 分配画像 | 堆/live 规模 | 释放比例/顺序 | 实测回收率区间 | 实测归还率区间 |")
add("|---|---|---|---:|---:|")
add("| small 16-256 B | 4096/线程 | 50% high | 27.91% | 60.88% |")
add("| small 16-256 B | 16384/线程 | 90% interleave | 67.59% | 66.61% |")
add("| mixed | 4096/线程 | 25-90% high | 29.77-88.47% | 110.82-133.65% |")
add("| mixed | 1024-16384/线程 | 50% high | 40.88-52.30% | 100.50-143.12% |")
add("| mixed | 4096/线程 | 50% high/interleave | 40.58-53.55% | 89.84-115.97% |")
add("| mixed | 16384/线程 | 75% interleave | 74.87% | 86.51% |")
add("| medium 1-16 KiB | 4096/线程 | 50% high | 50.60% | 109.01% |")
add("| medium 1-16 KiB | 16384/线程 | 90% high | 89.06% | 102.40% |")
add("")
add("媒体解码释放相位历史实测为 48.52-49.37%（8 路合计 10.902 MiB）。本曲线中数值最近的单因素点是")
add("medium-only / 4096 / 50% / high 的 50.60%，相差 1.23-2.08 个百分点；baseline mixed 为 53.55%。")
add("这是数值定位，不证明媒体解码具有相同尺寸分布。AppUIB/AppUIA 的历史动作三轮均未确认 M7，")
add("对应本扫描轴上的“没有已确认批量释放”，不是 25% 格；因此本曲线不给它们填名义回收率。")
add("")
add("## 7. 失败、限制与恢复现场")
add("")
add("1. 36/36 退出码为 0，stderr 全空；没有失败、补跑、降规模或参数偏差。")
add("2. 矩阵前后 dmesg 共 654 行且逐行相同，增量 0；没有 LMK/OOM/fatal 事件。")
add("3. fault 是 post-trim 固定 4096 ops/线程后的进程累计增量；全部 majflt=0。它不是单次请求延迟。")
add("4. profile 是合成分配画像，曲线只覆盖冻结的 12 个点；交叉格不足以拟合完整多变量模型。")
add("5. 最终清理确认 `/root/l6_curve` 及相关 `/tmp` 文件不存在，无 alloc_bench 残留；display-manager PID 2600、")
add("   `NRestarts=3050`，AppUIB/AppUIA PID 21210/23862 均保持运行。")
add("")
add("## 8. 历史阻塞记录（保留）")
add("")
add("同日早先执行时，指定 `.26` 对 ICMP、SSH、sdb 均不可达；在线 `.25` 实测为 Raspberry Pi 5/aarch64，")
add("因架构门未用作替代目标。当时完成 0/36，仅冻结矩阵并保留 host selftest。板恢复为 armv7l RPI4 后，")
add("本报告重新执行身份门、smoke 和全部 36 轮；没有复用 aarch64 或 host 数据。历史通道证据仍保留在 `stage0/`。")
add("")
add("## 9. 原始文件清单")
add("")
add("- 身份与协变量：`board_results/l6_applicability_curve_20260813/stage1/shared_environment.txt`")
add("- 冻结输入：`matrix.tsv`、`medium_1k_16k.hist`")
add("- smoke：`smoke/` 与拉回副本 `runs/smoke/`")
add("- 36 轮原始 JSON/XML/命令/内存/zram/dmesg：`runs/matrix/<cell>/rep<N>/`")
add("- 汇总：`summary/runs.tsv`、`summary/cells_median.tsv`")
add("- 矩阵前后内核证据：`runs/matrix/dmesg_before.txt`、`dmesg_after.txt`、`dmesg_delta.txt`")
add("- 最终清理：`final/l6_combined_cleanup_evidence.txt`、`final/l6_final_verify_exact.txt`")
add("- 历史阻塞与 host 验证：`stage0/`、`host_validation/`")

(ROOT / "docs/l6_applicability_curve.md").write_text("\n".join(lines) + "\n")
