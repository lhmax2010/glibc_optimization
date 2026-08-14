#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path("board_results/batch1")
REPORT = Path("docs/board_ab_batch1_report.md")


def read_text(path: Path) -> str:
    return path.read_text(errors="replace").rstrip()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |"]
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(out)


def code_block(text: str) -> str:
    return "```text\n" + text.rstrip() + "\n```"


measurements = read_tsv(ROOT / "measurements.tsv")
noise = read_tsv(ROOT / "noise.tsv")

noise_by_service: dict[str, list[int]] = {}
noise_unit: dict[str, str] = {}
for row in noise:
    svc = row["service"]
    noise_by_service.setdefault(svc, []).append(int(row["rss_kb"]))
    noise_unit[svc] = row["unit"]

noise_rows = []
for svc in ["ServiceR", "ServiceS", "pass", "pulseaudio", "ServiceV"]:
    samples = noise_by_service.get(svc, [])
    if samples:
        noise_rows.append([
            svc,
            noise_unit.get(svc, ""),
            str(len(samples)),
            ",".join(str(x) for x in samples),
            str(max(samples) - min(samples)),
        ])

c0_by_service = {
    row["service"]: row
    for row in measurements
    if row["grid"] == "C0"
}

main_rows = []
for row in measurements:
    c0 = c0_by_service.get(row["service"])
    if c0:
        rss_delta = int(row["rss_median_kb"]) - int(c0["rss_median_kb"])
        pss_delta = int(row["pss_median_kb"]) - int(c0["pss_median_kb"])
        delta = f"Rss {rss_delta:+d} / Pss {pss_delta:+d}"
    else:
        delta = "NA"
    main_rows.append([
        row["service"],
        row["grid"],
        row["pid"],
        row["e1"],
        row["rss_median_kb"],
        row["pss_median_kb"],
        delta,
        row["arena_count"],
        row["note"],
    ])

unit_rows = [
    ["ServiceR", "ServiceR.service", "touched"],
    ["ServiceS", "central-ServiceS.service", "touched"],
    ["pass", "pass.service", "touched"],
    ["pulseaudio", "pulseaudio.service", "touched"],
    ["ServiceV", "ac.service", "touched; verified by MainPID/ExecStart/cgroup"],
]

ServiceV_rows = [row for row in measurements if row["service"] == "ServiceV"]
ServiceV_noise = noise_by_service.get("ServiceV", [])
ServiceV_c0_e1 = "<no GLIBC_TUNABLES>"
ServiceV_c3_e1 = read_text(ROOT / "ServiceV/C3/e1_environ.txt")
ServiceV_c3_e1 = "\n".join(
    line for line in ServiceV_c3_e1.splitlines() if line.startswith("GLIBC_TUNABLES=")
) or "<no GLIBC_TUNABLES>"
ServiceV_restore_line = ""
restore_inventory = read_text(ROOT / "restore_inventory.tsv")
for line in restore_inventory.splitlines():
    cols = line.split("\t")
    if len(cols) > 3 and cols[1] == "ServiceV":
        ServiceV_restore_line = line
        break

perf_rows = []
for grid in ["C0", "C1", "C2", "C3"]:
    path = ROOT / f"pulseaudio/{grid}/perf_sentinel.txt"
    txt = read_text(path)
    pactl_rc = "NA"
    elapsed = "NA"
    xrun_lines = 0
    for line in txt.splitlines():
        if line.startswith("PACTL_RC="):
            pactl_rc = line.split("=", 1)[1]
        if line.startswith("PACTL_ELAPSED_S="):
            elapsed = line.split("=", 1)[1]
    after = False
    for line in txt.splitlines():
        if line.startswith("---XRUN_JOURNAL---"):
            after = True
            continue
        if after and line.strip():
            xrun_lines += 1
    perf_rows.append(["pulseaudio", grid, pactl_rc, elapsed, str(xrun_lines), str(path)])

sample_paths = "\n".join(str(p) for p in sorted(ROOT.glob("**/run*.txt")))
aux_paths = "\n".join(
    str(p)
    for p in sorted(ROOT.glob("**/*"))
    if p.is_file()
    and (
        p.name in {
            "maps.txt",
            "e1_environ.raw",
            "e1_environ.txt",
            "perf_sentinel.txt",
            "apply.txt",
            "rehearsal.txt",
        }
        or p.name.startswith("restart_round")
    )
)

restore_summary = read_text(ROOT / "restore_inventory_summary.txt")
restore_log = read_text(ROOT / "restore.log")
tmp_cleanup = read_text(ROOT / "tmp_cleanup.log")
exceptions = read_text(ROOT / "exceptions.log")

host_first = ""
host_last = ""
host_lines = read_text(ROOT / "host_run.log").splitlines()
if host_lines:
    host_first = host_lines[0]
    host_last = host_lines[-1]

report = f"""# Tizen glibc 内存优化 Batch 1 A/B 实验执行报告

## 1. 头部

- 日期：2026-07-08（主机时区 Asia/Shanghai）
- 执行窗口：{host_first} -> {host_last}
- Board IP：<TEST_BOARD_IP>
- sdb：`<USER_HOME>/tizen-studio/tools/sdb`
- sdb version：
{code_block(read_text(ROOT / "sdb_version.txt"))}
- root：已获得
{code_block(read_text(ROOT / "root_id.txt"))}
- device：
{code_block(read_text(ROOT / "sdb_devices.txt"))}
- os-release：
{code_block(read_text(ROOT / "os_release.txt"))}
- uname：
{code_block(read_text(ROOT / "uname.txt"))}

### 动过的 unit 清单

{md_table(["矩阵 service", "systemd unit", "状态"], unit_rows)}

完整命令流水见 `board_results/batch1/host_run.log`。unit 映射原文见 `board_results/batch1/unit_mapping.log`。

## 2. 噪声带表

{md_table(["service", "unit", "样本数", "9 个 Rss 样本(kB)", "Rss 极差(kB)"], noise_rows)}

## 3. 主数据表

{md_table(["service", "格", "新 pid", "E1", "Rss 中位数(kB)", "Pss 中位数(kB)", "相对 C0 差值", "E2 arena 近似计数", "备注"], main_rows)}

## 4. 阴性对照：ServiceV 原始证据

### E1 原始证据

ServiceV/C0 `/proc/<pid>/environ` 中 GLIBC_TUNABLES 行：
{code_block(ServiceV_c0_e1)}

ServiceV/C3 `/proc/<pid>/environ` 中 GLIBC_TUNABLES 行：
{code_block(ServiceV_c3_e1)}

### E3 原始组件

{md_table(["service", "格", "pid", "E1", "Rss 中位数(kB)", "Pss 中位数(kB)", "arena", "目录"], [[r["service"], r["grid"], r["pid"], r["e1"], r["rss_median_kb"], r["pss_median_kb"], r["arena_count"], r["dir"]] for r in ServiceV_rows])}

- ServiceV 9 个噪声 Rss 样本(kB)：{",".join(str(x) for x in ServiceV_noise)}
- ServiceV 噪声 Rss 极差(kB)：{(max(ServiceV_noise) - min(ServiceV_noise)) if ServiceV_noise else "NA"}
- ServiceV C3 相对 C0：Rss {int(ServiceV_rows[1]["rss_median_kb"]) - int(ServiceV_rows[0]["rss_median_kb"]):+d} kB / Pss {int(ServiceV_rows[1]["pss_median_kb"]) - int(ServiceV_rows[0]["pss_median_kb"]):+d} kB
- 原始文件：`board_results/batch1/ServiceV/C0/`, `board_results/batch1/ServiceV/C3/`, `board_results/batch1/ServiceV/C0_noise/`
- 复扫 TSV 中 ServiceV 行：
{code_block(ServiceV_restore_line or "<not found>")}

## 5. pulseaudio 性能哨兵原始计数

{md_table(["service", "格", "pactl rc", "elapsed_s", "xrun journal lines", "文件"], perf_rows)}

## 6. 异常记录

{code_block(exceptions if exceptions else "<none>")}

restart 演练文件：
{code_block("\n".join(str(p) for p in sorted(ROOT.glob("*/rehearsal.txt"))))}

## 7. 恢复现场证据

### drop-in 删除与服务 active

{code_block(restore_log)}

### inventory 复扫摘要

{code_block(restore_summary)}

### /tmp 清理后列表

{code_block(tmp_cleanup)}

复扫 TSV：`board_results/batch1/restore_inventory.tsv`

## 8. 原始采样文件路径

### smaps_rollup run*.txt

{code_block(sample_paths)}

### 辅助原始文件

{code_block(aux_paths)}
"""

REPORT.write_text(report)
