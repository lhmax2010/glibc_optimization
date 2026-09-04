> Public archive note: host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# Demo 三工具来源排查与声明（2026-09-03）

## 1. 结论

本轮为 host-only 元数据审计，未连接测试板，也未做新测量。脚本从
[`config/gbs_llvm.conf`](../config/gbs_llvm.conf) 与
[`config/gbs.conf`](../config/gbs.conf) 解析出全部四个 RPM repo URL，下载并校验每仓
`repomd.xml` 指向的 `primary` 与 `filelists`，再按三维独立检索：RPM 包名、RPM
`Provides`、完整文件路径。`alloc_bench` / `alloc-bench`、`gst_loop_decode` /
`gst-loop-decode`、`reclaim_probe` / `reclaim-probe` 三组名称在四仓均为 **零命中**。
逐仓证据见 [`repos.tsv`](../data/raw/tool_provenance_20260903/repos.tsv)，零命中明细文件
[`tool_hits.tsv`](../data/raw/tool_provenance_20260903/tool_hits.tsv) 仅含表头；机器裁决为
[`summary.json`](../data/raw/tool_provenance_20260903/summary.json) 中的
`OUTCOME=ZERO_HITS`。

因此，官方 Tizen Base/Unified RPM 仓没有提供这三个项目工具；它们是本项目自研的
测量/复现工具。这里的“零命中”只陈述本轮列出的四个仓与对应 repodata，不外推到其他
历史仓、私有仓或非 RPM 制品系统。

## 2. 仓库、revision 与三维命中

固定镜像同源基线是 Unified Toolchain `20260814.092727` 及其 Base Toolchain
`20260813.050338`；这也是 [`GBS host 构建记录`](../data/raw/gbs_package_20260903/README.md)
采用的组合。`config/gbs.conf` 的两个 `reference` URL 是移动指针，只用于说明审计日
官方源现状，不能替代固定快照。

| 配置 / repo | repodata revision（UTC） | 包数 | 包名命中 | Provides 命中 | 文件列表命中 |
|---|---:|---:|---:|---:|---:|
| `gbs_llvm.conf` / Base Toolchain `20260813.050338` | `1786696327`（2026-08-14 08:32:07） | 1693 | 0 | 0 | 0 |
| `gbs_llvm.conf` / Unified Toolchain `20260814.092727` | `1786721500`（2026-08-14 15:31:40） | 9607 | 0 | 0 | 0 |
| `gbs.conf` / Base `reference` | `1787894886`（2026-08-28 05:28:06） | 1710 | 0 | 0 | 0 |
| `gbs.conf` / Unified `reference` | `1788399318`（2026-09-03 01:35:18） | 9624 | 0 | 0 | 0 |

每个 revision 对应的 `repomd.xml` SHA-256、`primary`/`filelists` 相对路径与 SHA-256
均逐字段保存在 [`repos.tsv`](../data/raw/tool_provenance_20260903/repos.tsv)，不是根据
网页目录名或 GBS 本地缓存推断。名称比较先转小写，再去掉非字母数字字符，所以
下划线/连字符变体属于同一个检索键；filelists 使用完整路径，亦覆盖工具名出现在
debug/source 目录而不在 basename 的情形。

## 3. 逐工具来源声明

| 工具 | 来源与公开路径 | 引入轮次 | 用途 | 当前源码规模 / 冻结 ELF 规模 |
|---|---|---|---|---:|
| `alloc_bench` | 项目自研；[`tools/alloc_bench/alloc_bench.c`](../tools/alloc_bench/alloc_bench.c) | 2026-07-08 确定性微基准 v1，2026-08-14 增补 cyclic 模式；首次公开迁移 commit `8224138` | 可重复的 ptmalloc 分配画像、释放/trim、S2/S4 代理负载与 JSON/XML 相位证据 | 2883 行 / 102450 B；176656 B |
| `gst_loop_decode` | 项目自研；[`tools/gst_loop_decode/gst_loop_decode.c`](../tools/gst_loop_decode/gst_loop_decode.c) | 2026-08-11 GStreamer 真释放相位，2026-09-01 增补 loop-release trim 控制；首次公开迁移 commit `8224138` | 持久 GStreamer 软解循环、NULL 释放相位与真实并发业务代价采样 | 350 行 / 11116 B；51616 B |
| `reclaim_probe` | 项目自研；[`tools/reclaim_probe/reclaim_probe.c`](../tools/reclaim_probe/reclaim_probe.c) | 2026-08-06 reclaim-ceiling 轮；首次公开迁移 commit `8224138` | 将目标映射分成 glibc heap / other-anon / file-backed，并记录 PD/RSS 或 pageout 证据 | 456 行 / 12833 B；30260 B |

引入轮次分别由 [`INDEX`](INDEX.md)、[`alloc_bench 实现报告`](alloc_bench_impl_report.md)、
[`GStreamer 释放相位报告`](l6_gst_release_phase_probe.md) 与
[`reclaim-ceiling 报告`](reclaim_ceiling_probe.md) 交叉确认。表内源码规模由当前入库
`.c` 文件统计；冻结 ELF 体积来自
[`deliverables_manifest.json`](../tools/reproduce/deliverables_manifest.json)，两者不是
官方仓包大小，也不用于性能结论。

## 4. BuildRequires 独立复核

[`glibc-memopt-tools.spec`](../packaging/glibc-memopt-tools.spec) 的五个
`BuildRequires` 名称在同批官方 repodata 中均存在；固定配置下的 armv7l NVR 与上轮
GBS buildroot 记录一致，没有包名或版本分歧。`reference` 列展示移动源在本轮审计时的
版本，release 变化正是 HQ 复现必须选固定 `gbs_llvm.conf` 的原因。

| BuildRequires | 固定仓 | 固定快照 armv7l NVR | 本轮 `reference` armv7l NVR | 复核 |
|---|---|---|---|---|
| `clang` | Base | `clang-22.1.8-1.6` | `clang-22.1.8-2.3` | 名称有效；固定版本与 buildroot 一致 |
| `pkg-config` | Base | `pkg-config-0.29.2-1.7` | `pkg-config-0.29.2-3.11` | 名称有效；固定版本与 buildroot/构建依赖解析一致 |
| `glibc-devel` | Base | `glibc-devel-2.40-1.6` | `glibc-devel-2.40-13.4` | 名称有效；固定版本与板镜像 glibc 基线一致 |
| `glib2-devel` | Unified | `glib2-devel-2.80.5-0` | `glib2-devel-2.80.5-0` | 名称与版本一致 |
| `gstreamer-devel` | Unified | `gstreamer-devel-1.24.11-38` | `gstreamer-devel-1.24.11-41` | 名称有效；固定版本与 buildroot 一致 |

逐 repo 的 FOUND / NOT-IN-REPO 分布与 epoch/version/release 原值见
[`buildrequires.tsv`](../data/raw/tool_provenance_20260903/buildrequires.tsv)。例如 Base 不承载
`glib2-devel`/`gstreamer-devel`、Unified 不重复承载 Base 的三项，属于两仓组合的正常
分工，不是依赖缺失。

## 5. 第三方复核方法

审计器与 host 测试随本轮入库：
[`tools/runners/tool_provenance_20260903/`](../tools/runners/tool_provenance_20260903/)。
在真实 clone 根目录执行：

```sh
audit_tmp=$(mktemp -d /tmp/glibc-memopt-tool-provenance.XXXXXX)
python3 tools/runners/tool_provenance_20260903/audit_tool_provenance.py \
  --config config/gbs_llvm.conf \
  --config config/gbs.conf \
  --spec packaging/glibc-memopt-tools.spec \
  --cache-dir "$audit_tmp/cache" \
  --output "$audit_tmp/output"
cmp "$audit_tmp/output/repos.tsv" data/raw/tool_provenance_20260903/repos.tsv
cmp "$audit_tmp/output/tool_hits.tsv" data/raw/tool_provenance_20260903/tool_hits.tsv
cmp "$audit_tmp/output/buildrequires.tsv" data/raw/tool_provenance_20260903/buildrequires.tsv
cmp "$audit_tmp/output/summary.json" data/raw/tool_provenance_20260903/summary.json
```

固定快照的四个 `cmp` 应静默；移动 `reference` 发生更新后，`repos.tsv` 与
`buildrequires.tsv` 允许有可解释变化，但新输出必须保留并重新审阅。当前审计原文：

```text
REPOS	4
TOOL_HITS	0
OUTCOME	ZERO_HITS
```

脚本发现任何维度命中时仍会先写出 `tool_hits.tsv`，再以退出码 3 结束；该状态不能写成
“自研零命中”，必须交由 PM 裁决。
