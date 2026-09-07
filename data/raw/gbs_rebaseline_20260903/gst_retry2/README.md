# GBS retry2 gst 既有紧凑证据补档

测量日：2026-09-03。公开补档日：2026-09-07（N6-03）。这是旧
[`GBS rebaseline`](../../../../docs/gbs_rebaseline_20260903.md) 的 retry2 六格，
不是本次新测量，也不是后续 alloc_bench held-out 四格。

[`publication.json`](publication.json) 登记完整 pull 的 manifest/大小清单哈希、
实际 GBS gst/reclaim_probe 和媒体 SHA，以及各公开文件 SHA。补档前已从完整 pull
重跑原分析器，逐文件校验 hash/size，并确认六个派生件与原归档逐字节相同。
完整原始件本地留存，可按请求提供。

从公开输入复算（在仓库根目录运行）：

```sh
out=$(mktemp -d)
python3 tools/runners/gst_trim_cost_20260901/analyze_gst_trim_cost.py \
  --replay-cycles data/raw/gbs_rebaseline_20260903/gst_retry2/cycles.tsv \
  --output "$out"
cmp "$out/repetitions.tsv" data/raw/gbs_rebaseline_20260903/gst_retry2/repetitions.tsv
cmp "$out/arm_summary.tsv" data/raw/gbs_rebaseline_20260903/gst_retry2/arm_summary.tsv
cmp "$out/comparison.json" data/raw/gbs_rebaseline_20260903/gst_retry2/comparison.json
```

预期：三条 `cmp` 静默且退出码 0。命令输出由
[`comparison.json`](comparison.json) 对应的原统计口径产生；方向只报告。
[`health.json`](health.json) 是原健康摘要，公开 cycles 重放不重新生成健康观测。
重新从完整归档补档的入口为
[`publish_gst_retry2.py`](../../../../tools/runners/demo_v7_delivery_20260907/publish_gst_retry2.py)。
