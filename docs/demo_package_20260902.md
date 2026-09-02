> Public archive note: application/process names are aliases. Board identifiers,
> image delivery paths, and local filesystem paths are sanitized.

# glibc 内存优化 Demo 演示包

- 日期：2026-09-02
- 用途：演示日入口说明；图文总入口是可离线发送的
  [`demo_report.html`](demo_report.html)，本文件保留讲解顺序、命令和问答脚本
- 现场依赖：本仓库、Python 3；L1 演示不连接任何板端
- 完整复现手册：[`HQ Demo 复现指南`](demo_reproduction_guide_20260901.md)
- 一键复现：[`tools/reproduce/reproduce.sh`](../tools/reproduce/reproduce.sh)

<a id="delivery-contracts"></a>
## 0. 交付合同

| 交付要求 | 可审计实现 | 验收入口 |
|---|---|---|
| 有力复现步骤 | L1 从公开紧凑证据逐数字复算；L2 从身份门、资产哈希到板端清理给出可照抄命令 | [`HTML 复现入口`](demo_report.html#reproduce)、[`指南快速通道`](demo_reproduction_guide_20260901.md#workflow-fast-path)、[`workflow verify`](../tools/reproduce/README.md) |
| 同板同镜像多组对照 | S4 在同一 RPI4/Tizen 镜像上含两个锚点格与 `trim/none` 对照；gst 含两臂各三重复 | [`HTML S4`](demo_report.html#s4)、[`HTML gst`](demo_report.html#gst)、[`workflow board`](demo_reproduction_guide_20260901.md#l2-run) |
| 结果说明价值 | 反信号先排除无需重复回收的对象，M7 阳性后才在释放相位 trim；效果、faults、业务 p99 与边界同时报告 | [`HTML 自动归还`](demo_report.html#finding-one)、[`HTML 门控效果`](demo_report.html#s4)、[`HTML 边界`](demo_report.html#boundaries) |
| 同条件复现同数据 | payload、页对齐、majflt、zram 和 OOM/LMK 按确定性项验收；回收字节不作硬门，S4 B 按每档三重复中位 `±5 pp`，时延与 p99 按预登记带。彩排的 rep2 约 `1 MB` 台阶说明同 seed 不钉 arena 指派 | [`HTML 边界`](demo_report.html#boundaries)、[`L2 验收带`](demo_reproduction_guide_20260901.md#l2-acceptance)、[`机器配置`](../tools/reproduce/acceptance_bands.json) |

离线 HTML、手工指南与 workflow 是同一合同的三个入口：HTML 用于演示，指南是流程
权威参考，workflow 将其机械化并给出可机读判定；三者不各自维护第二套统计口径。

## 1. 建议演示流程

按以下顺序演示，主讲内容直接使用第 1 周叙事的对应章节：

1. **先定问题，不先讲 trim。** 用
   [`问题定位`](demo_narrative_20260901.md#1-问题定位tv-内存压力与-glibc-层机会)
   说明 glibc 只覆盖 ptmalloc 管理、应用已经 free、页面仍驻留的部分。
2. **用 ServiceA 讲清反信号。** 展示
   [`自动归还归因`](demo_narrative_20260901.md#2-核心发现一自动归还是反信号)：PD 实跌、
   zram 平坦、majflt 恒零、other-anon 无镜像迁移，所以周期峰谷不是待 trim 的收益。
3. **把镜头移到 retained floor。** 用
   [`候选表型`](demo_narrative_20260901.md#3-核心发现二滞留表型才是作用面)说明 a/b/c/N/U
   分类和候选登记，强调 floor 只是待 M7 验证的 surface。
4. **展示门控链已有的测试板证据。** 用
   [`S4 门控链`](demo_narrative_20260901.md#4-门控链与测试板实证)说明“反信号排除 → M7
   确认 → valley trim → faults/健康门”。
5. **补上第 2 周真实多线程目标。** 展示
   [`GStreamer 业务代价报告 §6`](gst_trim_cost_20260901.md#6-判断)：按预登记 p99 门，本批
   代价未越过基线重复离散；同时明确 trim 位于 NULL release 后，没有测到并发分配线程
   被全 arena 锁直接阻塞的时长。
6. **以产品决策门收尾。** 用
   [`何时 trim`](demo_narrative_20260901.md#5-决策门何时-trim何时不-trim)和
   [`产品 M7 推荐顺序`](product_m7_feasibility_20260902.md#7-路径对照与推荐排序)说明：
   自动下降、M7 阴性、ownership 不明或代价未过门时都不启用。

## 2. 现场可跑的 L1 复算

先在仓库根目录准备临时输出目录：

```sh
OUT=$(mktemp -d /tmp/glibc-memopt-demo.XXXXXX)
python3 --version
```

所有命令均为 host-only，只读 `data/raw/`，不会修改已发布证据。

### 演示 A：ServiceA 自动归还判别链（数秒）

```sh
python3 data/raw/cyclic_fall_mechanism_attribution_20260831/recompute_cyclic.py \
  --timeseries data/raw/product_cyclic_target_probe_20260814/raw/timeseries.tsv \
  --keys data/raw/product_cyclic_target_probe_20260814/raw/key_timeline.tsv \
  --output "$OUT/cyclic"
```

重点读最后三行：`median_P-V_kB 6212.0`、全窗口 zram 总变化，以及
`missing_rows 0`/各目标 PID 不变。再运行：

```sh
python3 -c 'import json; q=json.load(open("data/raw/cyclic_fall_mechanism_attribution_20260831/cyclic_quality.json")); x=q["target_counters"]["ServiceA"]; print("ServiceA majflt=%d->%d delta=%d"%(x["majflt_first"],x["majflt_last"],x["majflt_delta"]))'
```

预期原文为 `ServiceA majflt=167->167 delta=0`。完整输出和逐轮解释见
[`L1 ServiceA`](demo_reproduction_guide_20260901.md#l1-servicea)。

### 演示 B：候选 retained floor 普查（数秒）

```sh
python3 tools/runners/cyclic_fall_attribution_20260901/audit_phenotypes.py \
  --repo-root . --output "$OUT/phenotypes"
cmp "$OUT/phenotypes/release_ratio_phenotypes.tsv" \
  data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv
cmp "$OUT/phenotypes/plateau_cyclic_crosscheck.tsv" \
  data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv
```

两个 `cmp` 应静默成功。随后可直接展示已复算表中的 a+b `enlightenment`、b
`ServiceH`、c `ServiceE`、N `AppProcD` 和 U `ServiceB`；字段解释与抽取命令见
[`L1 表型普查`](demo_reproduction_guide_20260901.md#l1-phenotypes)。

### 演示 C：S4 门控 trim 的效果与 faults（数秒）

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

预期逐行原文见 [`L1 S4`](demo_reproduction_guide_20260901.md#l1-s4)。现场只需强调回收、
调用时间、下一周期 minflt、majflt 和健康门必须同批出现。

### 演示 D：GStreamer 公开 cycle 单文件复算（数秒）

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

预期输出：

```text
replayed cells=6 cycles=306 primary=300
delta_p99_ms=6.228611 none_dispersion_ms=6.784167 visible=false
```

三个 `cmp` 应静默成功。trim 分布与首次 release 的同输入复算命令见
[`L1 gst`](demo_reproduction_guide_20260901.md#l1-gst-trim-cost)。

## 3. 演示数字总表

| 演示数字 | 结论用途 | 证据 | L1 复算 |
|---|---|---|---|
| ServiceA 峰谷中位 `6212 kB`（`6.2 MB`） | 自动归还反信号案例的下降体量 | [`serviceA_fall_recheck.tsv`](../data/raw/cyclic_fall_attribution_20260901/serviceA_fall_recheck.tsv) | [ServiceA](demo_reproduction_guide_20260901.md#l1-servicea) |
| ServiceA 首次观测释放完成上界 `5.223693–8.910626 s`；旧 `19.683240 s` 撤销时长解释 | 不上 20 s 延迟钩子的依据 | [`summary.json`](../data/raw/cyclic_fall_attribution_20260901/summary.json) | [ServiceA](demo_reproduction_guide_20260901.md#l1-servicea) |
| `enlightenment +1736 kB` a+b floor | 最大 retained-floor 候选之一，另带自动归还能力告警 | [`release_ratio_phenotypes.tsv`](../data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv) | [表型](demo_reproduction_guide_20260901.md#l1-phenotypes) |
| `ServiceH 2360/+868/+580 kB`、`ServiceA +788 kB` | 平台上界、跨探针 floor 与谷底残渣候选 | [`plateau_cyclic_crosscheck.tsv`](../data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv)、[`release_ratio_phenotypes.tsv`](../data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv) | [表型](demo_reproduction_guide_20260901.md#l1-phenotypes) |
| 批量释放 `48.9451% / 1.359375 MiB`，同表型扩到 8 进程 | 已有 M7 的真实释放相位类别 | [`batch_release_phase.tsv`](../data/raw/demo_reproduction_20260901/batch_release_phase.tsv) | [批量相位](demo_reproduction_guide_20260901.md#l1-batch-release) |
| S4 锚点 `51.074077% / 50.387886%` | 新镜像机制锚点 | [`a_cells.tsv`](../data/raw/s4_retention_20260901/a_cells.tsv) | [S4](demo_reproduction_guide_20260901.md#l1-s4) |
| S4 回收/released `80.175875%–85.453954%`；调用 `1.233269/1.218361 ms`；下一周期 `+1351/+1465 minflt`、`majflt=0` | 合成驻留表型的效果与再激活代价 | [`b_cycles.tsv`](../data/raw/s4_retention_20260901/b_cycles.tsv)、[`b_cells.tsv`](../data/raw/s4_retention_20260901/b_cells.tsv) | [S4](demo_reproduction_guide_20260901.md#l1-s4) |
| gst p99 差 `+6.228611 ms`，none 重复离散 `6.784167 ms`，裁决 `false` | 真实多线程 pipeline 的预登记业务代价门 | [`cycles.tsv`](../data/raw/gst_trim_cost_20260901/cycles.tsv)、[`comparison.json`](../data/raw/gst_trim_cost_20260901/comparison.json) | [gst](demo_reproduction_guide_20260901.md#l1-gst-trim-cost) |
| gst trim p50/p95/p99/max `0.671556/0.818315/0.842185/0.856944 ms` | release-point 调用分布；不等于并发分配锁停顿 | [`cycles.tsv`](../data/raw/gst_trim_cost_20260901/cycles.tsv) | [gst](demo_reproduction_guide_20260901.md#l1-gst-trim-cost) |
| gst 首次 release `51.014041%–51.406250% / 1.277344–1.285156 MiB` | 与既有批量释放机制量级相容 | [`cycles.tsv`](../data/raw/gst_trim_cost_20260901/cycles.tsv) | [gst](demo_reproduction_guide_20260901.md#l1-gst-trim-cost) |

这些数字来自不同板、探针、PID 合同或代理，不能相加成产品收益。

## 4. Q&A 预案

### Q1：自动归还为什么不是坏事？

自动归还正是优化想达到的结果：应用 free 后页面已经离开 Private_Dirty，不再需要额外
trim。`ServiceA` 的下降分量有 PD 实跌、zram 无正增量、majflt 恒零和桶迁移排除链
([归因证据](cyclic_fall_mechanism_attribution_v2_20260901.md#2-决定性归因链))。把它标成
“反信号”不是否定 glibc，而是避免在已经完成的回收上重复付出锁和 refault 代价。

### Q2：为什么不在操作结束约 20 s 后触发？

旧 `19.683240 s` 是从首次跌出峰值带到尾窗最小值落点的算法间隔，不是实际释放时长。
逐轮正式代理显示页面在峰后首次观测 `≤约 9 s` 内基本完成，因此 20 s 定时器会追赶一个
已经结束的下降，还可能制造无收益 trim。撤销记录和替代口径见
[`归因 v2 §3–§4`](cyclic_fall_mechanism_attribution_v2_20260901.md#3-f3下降沿伪影与正式替代口径)。

### Q3：当前“代价不可见”能否解释为零代价？

不能。GStreamer 的 `+6.228611 ms` 没有严格超过 `6.784167 ms` 基线重复离散，只表示
按预登记门“本批未检出”；每重复只有 50 个主样本，nearest-rank p99 就是最大值
([正式裁决](gst_trim_cost_20260901.md#a-每循环-release-trim-的业务代价是否可见))。trim 又在
pipeline NULL release 后执行，不能量化其他线程仍在分配时的直接锁停顿。S4 的约
`1.2 ms` 也只是合成代理调用时间，不是产品 SLA。

### Q4：下一步产品侧怎么走？

正式主线是让目标 owner 提供受控签名构建，在真实释放相位低频导出 M7；测试板代理可
并行校准 harness；debugger attach 只在产品安全明确授权时做一次性筛选。三条路径的
前置、成本、证据强度和三门覆盖见
[`产品 M7 可行性评估`](product_m7_feasibility_20260902.md)。取得产品 M7 阳性之前，候选
floor 不换算收益，也不进入 trim A/B。

## 5. 已知边界：一页说明

1. **产品 live/bin 缺口。** 产品候选目前只有 smaps floor；M7 未取得，无法知道其中
   有多少是 live 对象、多少是 bins。路径评估不等于候选已经通过
   ([M7 可行性结论](product_m7_feasibility_20260902.md#8-对落点建议三门的最终影响))。
2. **业务代价缺口。** S4 是单进程合成代理；GStreamer 补了真实多线程 pipeline 的下一
   循环 p50/p95/p99、trim 分布和 faults，但没有量到 concurrent allocation 时每线程被
   全 arena 锁阻塞的直接 stall、帧时延或能耗
   ([gst 未关闭项](gst_trim_cost_20260901.md#d-是否填上并发线程代价未知))。
3. **跨板外推缺口。** 测试板与产品板的镜像、内存环境和工作负载不同；测试板百分比只
   支持机制与量级，产品收益必须按同一三门合同重建
   ([Demo 原边界](demo_narrative_20260901.md#6-边界与未决))。
4. **gst NULL 后触发限制。** PLAYING 阶段观察到多线程 pipeline，但 trim 在 NULL release
   完成后调用；当前证据说明 release-point 调用和下一轮后效，没有证明业务线程仍执行时
   的锁竞争安全性
   ([报告边界](gst_trim_cost_20260901.md#b-与-s4-单线程约-12-ms-的关系))。

演示结论应停在“门控机制已在测试板闭合，产品候选与直接并发锁停顿仍需证据”，不得
升级为产品收益承诺。
