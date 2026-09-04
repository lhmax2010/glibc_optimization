> 公开归档说明：应用/进程名称使用既有别名；host 侧路径已脱敏，板端运行路径保留。

# `malloc_info` 整页容量估算器验证（2026-09-05）

- 范围：只复算已有 XML 与既有回收值；本节没有连接测试板、没有产生新测量数字。
- 实现：[`trimmable_estimator.py`](../tools/analysis/trimmable_estimator.py)
- 公开输入清单：[`cases.tsv`](../data/raw/trimmable_estimator_20260905/cases.tsv)
- 完整派生表：[`validation.tsv`](../data/raw/trimmable_estimator_20260905/validation.tsv)

## 1. 方法与口径

对 `malloc_info` 的每个 arena，只读取 `<sizes>` 下的
`<size from="…" to="…" total="…" count="…">`。页大小固定为 `P=4096 B`。
设单个空闲块长度为 `s`：

- 最坏起始地址对齐下，块内完整页数下界为
  `max(0, floor((s-(P-1))/P))`；
- 最好对齐下，块内完整页数上界为 `floor(s/P)`；
- 每个区间的下界取 `from`、上界取 `to`，再乘 `count × P`；逐 arena 与全局求和。

解析器还校验 `count × from ≤ total ≤ count × to`，并单列 `<unsorted>` 的
`total` 作为诊断。主估计不把 `<unsorted>` 悄悄并入 `<size>` 口径。输出包含逐 arena
与总计；这只是“未知地址下的几何整页容量”，不是 `malloc_trim(0)` 可回收量预测。

## 2. 验证集和结果

下表的误差定义为“估计减实测”；KiB 均为 `1024 B`。S4 B 的三次重复逐字一致，表中
保留每个 XML/实测对，不用中位掩盖重复。全部原始 XML 已作为紧凑输入随
[`xml/`](../data/raw/trimmable_estimator_20260905/xml/) 入库。

| 来源/格 | `<size>` 估计下界–上界 (KiB) | 实测回收 (KiB) | 下界/上界误差 (KiB) | 实测在区间内 |
|---|---:|---:|---:|---|
| enlightenment E1 | 2272–8044 | 272 | +2000 / +7772 | 否 |
| S4 A mixed | 6692–8732 | 53448 | -46756 / -44716 | 否 |
| S4 A medium-only | 1984–2508 | 54040 | -52056 / -51532 | 否 |
| S4 B mixed rep1–3 cycle 1 | 0–0 | 4496 | -4496 / -4496 | 否（3/3） |
| S4 B mixed rep1–3 cycle 2 | 0–0 | 5332 | -5332 / -5332 | 否（3/3） |
| S4 B medium-only rep1–3 cycle 1 | 0–0 | 5124 | -5124 / -5124 | 否（3/3） |
| S4 B medium-only rep1–3 cycle 2 | 0–0 | 5252 | -5252 / -5252 | 否（3/3） |

共 `15/15` 个严格配对观测落在区间外。偏差也不是可用一个系数修正的单向偏差：E1
连下界都比实测高 `2000 KiB`，而 S4 的 `14/14` 个观测连上界都比实测低。

### 2.1 两项不能伪造的验证缺口

- S2 冻结参数是 `--trim-at none`；其两档 cycle 1 valley XML 可解析，但没有 trim 调用，
  因而没有“已知实测回收”可配对。清单将它们标为 `no_trim_invoked`，不把零调用冒充
  `0 KiB` 回收验证。
- gst trim-cost 轮只采集了 `reclaim_probe` smaps JSON，没有落 `malloc_info` XML；首轮
  trim 有实测回收，但没有本算法所需输入。清单标为 `xml_not_collected`。这是验证覆盖
  缺口，不从其他负载补造 XML。

## 3. 失败模式与裁决

估算失败来自信息不足，不是页取整实现误差：

1. XML 没有空闲块地址，无法知道真实页边界；`from/to` 对宽桶只能形成松散几何界。
2. `<size>` 不覆盖 top chunk，且 S4 B 的 MB 级释放主要仍在 `<unsorted>`；所以主口径会
   系统性低估这些格。把 `<unsorted>` 简单并入也不能解决地址、相邻块合并和 top/arena
   资格缺失。
3. `malloc_trim` 可在保留 allocator chunk/arena 元数据时丢弃其中物理页；反过来，几何上
   含整页也不代表该页已驻留、可由当前 arena 返回或能反映在主堆 Private_Dirty。
4. E1 的宽桶 `975353–3919425 B` 只提供两个块的聚合区间，使上界从根本上过松；其约
   `5.84 MiB rest` 与 `272 KiB` 实测差异不能靠块尺寸直方图消除。

**裁决：不能把该估算器作为产品启用门的量化条件，也不建议冻结阈值。** 它可用于离线
指出“直方图里存在潜在整页容量”以及定位 `<size>`/`<unsorted>` 口径差异；启用门仍需
“M7 定性确认 + 同目标/同相位实际 trim 校准 + 代价门”，估算区间不得替代实际 A/B。

## 4. 复算

仅需仓库与 Python 3：

```sh
python3 tools/analysis/test_trimmable_estimator.py
python3 tools/analysis/validate_trimmable_estimator.py \
  data/raw/trimmable_estimator_20260905/cases.tsv \
  --output /tmp/trimmable-validation.tsv
cmp /tmp/trimmable-validation.tsv \
  data/raw/trimmable_estimator_20260905/validation.tsv
```

预期：host 测试为 `OK`，`cmp` 静默且退出码为 0。算法确定性项是同一 XML/页大小下的
逐字节下界和上界；实测回收属于目标运行时状态，不设跨运行容差带。本报告是 host-only，
不定义板端 governor、zram 或 dmesg 验收项。
