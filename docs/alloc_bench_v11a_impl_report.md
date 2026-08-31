> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# alloc_bench v1.1a implementation report

## 1. 交付清单

- `bench/alloc_bench/alloc_bench.c`: 新增 `--idle-trim`；释放后、idle 前按需调用 `malloc_trim(0)`；JSON schema 仍为 `alloc_bench_v1_1`，新增顶层字段 `idle_trim`、`idle_trim_ret`、`idle_free_bytes_measure`、`idle_free_bytes_idle`。
- `bench/alloc_bench/selftest.sh`: 原 A7 替换为 A7a + A7b；A7a 使用进程内 free-byte 字段，不再解析 XML 求和；A7b 验证 opt-in trim 后 OS 级 RSS 回收。
- `bench/alloc_bench/README.md`: 同步 `--idle-trim`、新增 JSON 字段、A7a/A7b 验收说明。

## 2. 验收门复跑摘要

### selftest A1-A6/A7a/A7b/A8/A9

命令：

```text
bench/alloc_bench/selftest.sh > /tmp/alloc_bench_v11a_impl_logs/selftest.out 2>&1
```

输出摘录：

```text
SELFTEST_RC=0
PASS build host
PASS A1 determinism
PASS A2 ASan+UBSan six built-in profiles
PASS A3 RSS lower-bound sanity
PASS A4 JSON parse
PASS A5 armv7l ELF 32-bit ARM dynamic
A6_FAST_BYTES=51424 EXPECTED_BYTES=40960 THRESHOLD_BYTES=20480
PASS A6 burst-free-small fastbin residual
A7A_FREE_DELTA_BYTES=26523104 RELEASE_BYTES=25726812 FREE_THRESHOLD_BYTES=18008769 RSS_DELTA_KB=4.0 RSS_THRESHOLD_KB=2512.4
PASS A7a mixed idle-release retained free bytes
A7B_RECLAIMED_KB=29988.0 RELEASE_KB=25123.8 THRESHOLD_KB=7537.2 IDLE_TRIM_RET=1
PASS A7b mixed idle-release idle-trim OS reclaim
PASS A8 new-profile determinism
A9_OLD_FIELD_STRUCTURES_OK=4
PASS A9 v1 profile old-field compatibility
SUMMARY PASS=11 FAIL=0
```

### A7a 独立样本

命令：

```text
bench/alloc_bench/alloc_bench.host --profile mixed --threads 2 --seed 20260709 --warmup 1 --duration 3 --idle 1 --idle-release 50 --outdir /tmp/alloc_bench_v11a_impl_logs/a7a
```

实测：

```text
a7a: idle_trim=False idle_trim_ret=-1
a7a: release_bytes=25726812 release_kb=25123.8
a7a: idle_free_bytes_measure=6169265 idle_free_bytes_idle=31413146 free_delta_bytes=25243881
a7a: measure_rss_kb_median=57272 idle_rss_kb=57040 rss_reclaimed_kb=232 rss_abs_delta_kb=232
```

A7a 判定：free-byte 增量 `25243881` bytes >= 70% 阈值 `18008768` bytes；RSS 绝对差 `232 KiB` < 10% 阈值 `2512.4 KiB`。

### A7b 独立样本

命令：

```text
bench/alloc_bench/alloc_bench.host --profile mixed --threads 2 --seed 20260709 --warmup 1 --duration 3 --idle 1 --idle-release 50 --idle-trim --outdir /tmp/alloc_bench_v11a_impl_logs/a7b
```

实测：

```text
a7b: idle_trim=True idle_trim_ret=1
a7b: release_bytes=25726812 release_kb=25123.8
a7b: idle_free_bytes_measure=6528641 idle_free_bytes_idle=32065011 free_delta_bytes=25536370
a7b: measure_rss_kb_median=56936 idle_rss_kb=26944 rss_reclaimed_kb=29992 rss_abs_delta_kb=29992
```

A7b 判定：OS 级回收 `29992 KiB` >= 30% 阈值 `7537.2 KiB`。这是 `--idle-trim`/L6 仪器的 host 侧定量预览。

### host-asan idle-trim

命令：

```text
env -u GLIBC_TUNABLES ASAN_OPTIONS=abort_on_error=1:detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 \
  bench/alloc_bench/alloc_bench.host-asan --profile mixed --threads 4 --seed 20260709 \
  --warmup 1 --duration 5 --idle 2 --idle-release 50 --idle-trim \
  --outdir /tmp/alloc_bench_v11a_impl_logs/asan_idle_trim
```

结果：

```text
ASAN_RC=0
stderr_bytes=0
schema=alloc_bench_v1_1
idle_trim=True
```

注：ASan allocator 环境下 RSS 回收量不用于 A7b 裁决；本门只要求零 sanitizer 报告。

### A5 armv7l

命令：

```text
make -C bench/alloc_bench armv7l
file bench/alloc_bench/alloc_bench.armv7l
```

输出：

```text
bench/alloc_bench/alloc_bench.armv7l: ELF 32-bit LSB executable, ARM, EABI5 version 1 (SYSV), dynamically linked, interpreter /lib/ld-linux.so.3, BuildID[sha1]=84b64a818b140ba3b07acc931b83bc8a754fecb7, for GNU/Linux 3.2.0, with debug_info, not stripped
```

## 3. JSON 字段核对

新增字段位于 JSON 顶层：

```text
idle_trim
idle_trim_ret
idle_free_bytes_measure
idle_free_bytes_idle
```

`idle_free_bytes_*` 在进程内从 `malloc_info()` XML 的进程级 top-level `<total type="fast">` 与 `<total type="rest">` 最后一组汇总计算；XML 文件仍照常落盘。

## 4. 偏差清单

无。

## 5. 已知限制

- `--idle-trim` 只在同时设置 `--idle-release PCT>0` 时生效；单独传入不会调用 `malloc_trim(0)`，JSON 中 `idle_trim=false`、`idle_trim_ret=-1`。
- A7b 的 host 数字是板前预览，不替代 Batch 2.5/板上 L6 数据。
