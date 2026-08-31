> Public archive note: application/process names are aliases and board identifiers and paths are sanitized. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains in the private local archive.

# alloc_bench v1.1 implementation report

## 1. 交付清单

- `bench/alloc_bench/alloc_bench.c`: schema 升级到 `alloc_bench_v1_1`；新增 `burst-free-small`、`unsorted-drain`；实现 `--touch-full`、默认 >=128 KiB 全量触碰、周期 RSS 采样、`--idle-release`、`--stagger-churn`。
- `bench/alloc_bench/selftest.sh`: 扩展 A1-A9；A6/A7 打印实测值和阈值。
- `bench/alloc_bench/README.md`: 更新六档 profile 参数表、v1.1 CLI、新触碰策略、周期采样和 idle-release 字段。
- `bench/alloc_bench/Makefile`: 未改动；现有 `host`、`host-asan`、`armv7l` 目标继续使用。

## 2. 验收门执行原文

### selftest.sh A1-A9

命令：

```text
bench/alloc_bench/selftest.sh > /tmp/alloc_bench_v11_impl_logs/selftest.out 2>&1; echo SELFTEST_RC=$?
```

输出：

```text
SELFTEST_RC=1
PASS build host
PASS A1 determinism
PASS A2 ASan+UBSan six built-in profiles
PASS A3 RSS lower-bound sanity
PASS A4 JSON parse
PASS A5 armv7l ELF 32-bit ARM dynamic
A6_FAST_BYTES=51424 EXPECTED_BYTES=40960 THRESHOLD_BYTES=20480
PASS A6 burst-free-small fastbin residual
A7_RECLAIMED_KB=68.0 THEORETICAL_RELEASE_KB=25123.8 THRESHOLD_KB=7537.2
Traceback (most recent call last):
  File "<stdin>", line 8, in <module>
AssertionError: (68, 7537.152)
FAIL A7 mixed idle-release reclaim
+ ./alloc_bench.host --profile mixed --threads 2 --seed 20260709 --warmup 1 --duration 3 --idle 1 --idle-release 50 --outdir /tmp/alloc_bench_selftest.306552/a7
PASS A8 new-profile determinism
A9_OLD_FIELD_STRUCTURES_OK=4
PASS A9 v1 profile old-field compatibility
SUMMARY PASS=9 FAIL=1
```

A6 实测：`A6_FAST_BYTES=51424 EXPECTED_BYTES=40960 THRESHOLD_BYTES=20480`。

A7 实测：`A7_RECLAIMED_KB=68.0 THEORETICAL_RELEASE_KB=25123.8 THRESHOLD_KB=7537.2`，未达阈值；见偏差清单。

### host-asan 六档短跑

参数：`--threads 4 --seed 20260709 --warmup 1 --duration 5 --idle 2`，每档 `env -u GLIBC_TUNABLES ASAN_OPTIONS=abort_on_error=1:detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1`。

```text
PASS small-churn
PASS mixed
PASS large-transient
PASS thread-churn
PASS burst-free-small
PASS unsorted-drain
```

```text
small-churn: stderr_bytes=0
mixed: stderr_bytes=0
large-transient: stderr_bytes=0
thread-churn: stderr_bytes=0
burst-free-small: stderr_bytes=0
unsorted-drain: stderr_bytes=0
```

### A5 armv7l file 检查

命令：

```text
make -C bench/alloc_bench armv7l && file bench/alloc_bench/alloc_bench.armv7l
```

输出：

```text
bench/alloc_bench/alloc_bench.armv7l: ELF 32-bit LSB executable, ARM, EABI5 version 1 (SYSV), dynamically linked, interpreter /lib/ld-linux.so.3, BuildID[sha1]=66ce889448d589857ddfb52b97a011efcb7dbf2b, for GNU/Linux 3.2.0, with debug_info, not stripped
```

### A9 静态旧字段对照

对照对象：`docs/alloc_bench_impl_report.md` 的 v1 四档 JSON vs 本次 v1.1 四档 `seed=20260708` 短跑 JSON；吞吐/延迟/RSS 等运行值按规格豁免。

```text
small-churn: static_old_field_mismatches=0
mixed: static_old_field_mismatches=0
large-transient: static_old_field_mismatches=0
thread-churn: static_old_field_mismatches=0
large-transient note: touch_policy changed to ge128k_full_else_edge64 in v1.1; dynamic throughput/RSS fields intentionally not compared
```

## 3. 偏差清单

- A7 未通过：在 host glibc C0 下，`mixed --idle-release 50` 释放 live pool 后未自动归还足够 RSS。selftest 实测回收 `68.0 KiB`，阈值 `7537.2 KiB`。实现没有加入 `malloc_trim(0)` 或其他主动回收，因为这会污染后续 L3/trim_threshold 自动回收实验的语义。
- 其余 Δ1-Δ6 实现完成；A1-A6/A8/A9 通过。

## 4. 六档 host C0 JSON 回显

统一参数：`env -u GLIBC_TUNABLES bench/alloc_bench/alloc_bench.host --threads 4 --seed 20260709 --warmup 1 --duration 5 --idle 2 --outdir /tmp/alloc_bench_v11_impl_logs/host_c0/<profile>`。

### small-churn

```json
{"schema":"alloc_bench_v1_1","profile":"small-churn","mode":"duration","threads":4,"seed":20260709,"warmup_s":1.000000,"duration_s":5.000000,"idle_s":2.000000,"ops_per_thread":0,"live_set_per_thread":256,"churn_period_ms":2000,"stagger_churn":false,"large_period_ops":100,"large_hold_ops":100,"burst_size":2048,"burst_hold_ops":4096,"unsorted_batch":4096,"background_live_ops":1,"background_phase_ops":8,"idle_release_pct":0,"avg_size_bytes":99.200,"theoretical_live_kb":99.200,"touch_policy":"ge128k_full_else_edge64","histogram":[{"size":16,"weight":1},{"size":32,"weight":1},{"size":64,"weight":1},{"size":128,"weight":1},{"size":256,"weight":1}],"measure_elapsed_s":5.000229519,"measure_ops":691178016,"throughput_ops_per_s":138229257.952,"thread_ops":[169370946,174896573,175392309,171518188],"thread_size_hash":["ba71a9774f828213","50ed42f7b1029288","c2b996121394e0c3","5f2d738a29f393f3"],"op_hash_fn":"fnv1a64_size_sequence","latency_ns":{"sample_every":64,"samples":10799658,"p50":110,"p99":119,"bucket_bounds":[100,120,143,172,205,246,294,352,422,505,604,723,866,1037,1241,1486,1778,2129,2548,3051,3652,4371,5233,6264,7499,8977,10746,12864,15399,18434,22067,26416,31623,37855,45316,54247,64938,77737,93057,111397,133352,159634,191095,228757,273842,327812,392419,469759,562341,673170,805842,964662,1154782,1382372,1654817,1980957,2371374,2838736,3398208,4067944,4869675,5829415,6978306,8353625,10000000],"hist":[10793071,4646,1109,403,179,65,21,4,2,1,1,0,6,32,46,37,23,7,3,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0]},"memory":{"measure_rss_kb_samples":[2152,2152,2152],"measure_pss_kb_samples":[473,473,473],"measure_rss_kb_median":2152,"measure_pss_kb_median":473,"measure_rss_kb_p50":2084,"measure_rss_kb_p95":2084,"measure_rss_kb_max":2152,"measure_rss_kb_n_samples":2,"measure_rss_kb_sample_failures":0,"idle_release_pct":0,"idle_rss_kb_after_release":2152,"idle_pss_kb_after_release":473,"idle_rss_kb":2168,"idle_pss_kb":489,"vmhwm_kb":2172,"malloc_info_measure":"/tmp/alloc_bench_v11_impl_logs/host_c0/small-churn/malloc_info_small-churn_306858_measure.xml","malloc_info_idle":"/tmp/alloc_bench_v11_impl_logs/host_c0/small-churn/malloc_info_small-churn_306858_idle.xml"}}
```

### mixed

```json
{"schema":"alloc_bench_v1_1","profile":"mixed","mode":"duration","threads":4,"seed":20260709,"warmup_s":1.000000,"duration_s":5.000000,"idle_s":2.000000,"ops_per_thread":0,"live_set_per_thread":4096,"churn_period_ms":2000,"stagger_churn":false,"large_period_ops":100,"large_hold_ops":100,"burst_size":2048,"burst_hold_ops":4096,"unsorted_batch":4096,"background_live_ops":1,"background_phase_ops":8,"idle_release_pct":0,"avg_size_bytes":6280.960,"theoretical_live_kb":100495.360,"touch_policy":"ge128k_full_else_edge64","histogram":[{"size":16,"weight":8},{"size":64,"weight":12},{"size":256,"weight":18},{"size":1024,"weight":24},{"size":4096,"weight":18},{"size":16384,"weight":12},{"size":32768,"weight":6},{"size":65536,"weight":2}],"measure_elapsed_s":5.000623514,"measure_ops":361093844,"throughput_ops_per_s":72209764.040,"thread_ops":[91039407,89601073,89629917,90823447],"thread_size_hash":["9977d2fd9fb7fcb3","1d638d62310436eb","d970aefd60f07d99","9030b1eab55525cc"],"op_hash_fn":"fnv1a64_size_sequence","latency_ns":{"sample_every":64,"samples":5642093,"p50":110,"p99":132,"bucket_bounds":[100,120,143,172,205,246,294,352,422,505,604,723,866,1037,1241,1486,1778,2129,2548,3051,3652,4371,5233,6264,7499,8977,10746,12864,15399,18434,22067,26416,31623,37855,45316,54247,64938,77737,93057,111397,133352,159634,191095,228757,273842,327812,392419,469759,562341,673170,805842,964662,1154782,1382372,1654817,1980957,2371374,2838736,3398208,4067944,4869675,5829415,6978306,8353625,10000000],"hist":[5559927,49200,20681,6607,1928,439,104,20,207,784,970,492,256,143,126,64,44,27,32,30,8,4,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]},"memory":{"measure_rss_kb_samples":[112712,112712,112712],"measure_pss_kb_samples":[111033,111033,111033],"measure_rss_kb_median":112712,"measure_pss_kb_median":111033,"measure_rss_kb_p50":111868,"measure_rss_kb_p95":111868,"measure_rss_kb_max":112020,"measure_rss_kb_n_samples":2,"measure_rss_kb_sample_failures":0,"idle_release_pct":0,"idle_rss_kb_after_release":112712,"idle_pss_kb_after_release":111033,"idle_rss_kb":112744,"idle_pss_kb":111065,"vmhwm_kb":113288,"malloc_info_measure":"/tmp/alloc_bench_v11_impl_logs/host_c0/mixed/malloc_info_mixed_306893_measure.xml","malloc_info_idle":"/tmp/alloc_bench_v11_impl_logs/host_c0/mixed/malloc_info_mixed_306893_idle.xml"}}
```

### large-transient

```json
{"schema":"alloc_bench_v1_1","profile":"large-transient","mode":"duration","threads":4,"seed":20260709,"warmup_s":1.000000,"duration_s":5.000000,"idle_s":2.000000,"ops_per_thread":0,"live_set_per_thread":4096,"churn_period_ms":2000,"stagger_churn":false,"large_period_ops":100,"large_hold_ops":100,"burst_size":2048,"burst_hold_ops":4096,"unsorted_batch":4096,"background_live_ops":1,"background_phase_ops":8,"idle_release_pct":0,"avg_size_bytes":6280.960,"theoretical_live_kb":100495.360,"touch_policy":"ge128k_full_else_edge64","histogram":[{"size":16,"weight":8},{"size":64,"weight":12},{"size":256,"weight":18},{"size":1024,"weight":24},{"size":4096,"weight":18},{"size":16384,"weight":12},{"size":32768,"weight":6},{"size":65536,"weight":2}],"measure_elapsed_s":5.000786620,"measure_ops":28210804,"throughput_ops_per_s":5641273.292,"thread_ops":[7054101,7111201,6963201,7082301],"thread_size_hash":["907a52deb743574a","48141dcbec336cda","43d3845c1d8398e1","4c1b1a2c71111fc1"],"op_hash_fn":"fnv1a64_size_sequence","latency_ns":{"sample_every":64,"samples":440796,"p50":110,"p99":223,"bucket_bounds":[100,120,143,172,205,246,294,352,422,505,604,723,866,1037,1241,1486,1778,2129,2548,3051,3652,4371,5233,6264,7499,8977,10746,12864,15399,18434,22067,26416,31623,37855,45316,54247,64938,77737,93057,111397,133352,159634,191095,228757,273842,327812,392419,469759,562341,673170,805842,964662,1154782,1382372,1654817,1980957,2371374,2838736,3398208,4067944,4869675,5829415,6978306,8353625,10000000],"hist":[419316,8169,4822,3249,1834,780,352,141,49,13,105,289,482,492,394,154,49,37,28,19,14,6,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]},"memory":{"measure_rss_kb_samples":[133540,133540,133540],"measure_pss_kb_samples":[131861,131861,131861],"measure_rss_kb_median":133540,"measure_pss_kb_median":131861,"measure_rss_kb_p50":125196,"measure_rss_kb_p95":125196,"measure_rss_kb_max":128808,"measure_rss_kb_n_samples":2,"measure_rss_kb_sample_failures":0,"idle_release_pct":0,"idle_rss_kb_after_release":133540,"idle_pss_kb_after_release":131861,"idle_rss_kb":133572,"idle_pss_kb":131893,"vmhwm_kb":135672,"malloc_info_measure":"/tmp/alloc_bench_v11_impl_logs/host_c0/large-transient/malloc_info_large-transient_306956_measure.xml","malloc_info_idle":"/tmp/alloc_bench_v11_impl_logs/host_c0/large-transient/malloc_info_large-transient_306956_idle.xml"}}
```

### thread-churn

```json
{"schema":"alloc_bench_v1_1","profile":"thread-churn","mode":"duration","threads":4,"seed":20260709,"warmup_s":1.000000,"duration_s":5.000000,"idle_s":2.000000,"ops_per_thread":0,"live_set_per_thread":4096,"churn_period_ms":2000,"stagger_churn":false,"large_period_ops":100,"large_hold_ops":100,"burst_size":2048,"burst_hold_ops":4096,"unsorted_batch":4096,"background_live_ops":1,"background_phase_ops":8,"idle_release_pct":0,"avg_size_bytes":6280.960,"theoretical_live_kb":100495.360,"touch_policy":"ge128k_full_else_edge64","histogram":[{"size":16,"weight":8},{"size":64,"weight":12},{"size":256,"weight":18},{"size":1024,"weight":24},{"size":4096,"weight":18},{"size":16384,"weight":12},{"size":32768,"weight":6},{"size":65536,"weight":2}],"measure_elapsed_s":5.000779309,"measure_ops":278100921,"throughput_ops_per_s":55611516.489,"thread_ops":[69804484,69466638,69070773,69759026],"thread_size_hash":["eca68a895efb5af4","d4f9fcb17ed08615","71b90d6d0ad4b380","c85cb3be6fd07a5e"],"op_hash_fn":"fnv1a64_size_sequence","latency_ns":{"sample_every":64,"samples":4345332,"p50":110,"p99":131,"bucket_bounds":[100,120,143,172,205,246,294,352,422,505,604,723,866,1037,1241,1486,1778,2129,2548,3051,3652,4371,5233,6264,7499,8977,10746,12864,15399,18434,22067,26416,31623,37855,45316,54247,64938,77737,93057,111397,133352,159634,191095,228757,273842,327812,392419,469759,562341,673170,805842,964662,1154782,1382372,1654817,1980957,2371374,2838736,3398208,4067944,4869675,5829415,6978306,8353625,10000000],"hist":[4284717,35482,15190,5006,1481,359,98,42,108,477,572,384,583,332,247,109,34,43,26,19,14,3,0,1,2,3,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]},"memory":{"measure_rss_kb_samples":[112704,112704,112704],"measure_pss_kb_samples":[110899,110899,110899],"measure_rss_kb_median":112704,"measure_pss_kb_median":110899,"measure_rss_kb_p50":112940,"measure_rss_kb_p95":112940,"measure_rss_kb_max":113196,"measure_rss_kb_n_samples":2,"measure_rss_kb_sample_failures":0,"idle_release_pct":0,"idle_rss_kb_after_release":112704,"idle_pss_kb_after_release":110899,"idle_rss_kb":112736,"idle_pss_kb":110931,"vmhwm_kb":113004,"malloc_info_measure":"/tmp/alloc_bench_v11_impl_logs/host_c0/thread-churn/malloc_info_thread-churn_307024_measure.xml","malloc_info_idle":"/tmp/alloc_bench_v11_impl_logs/host_c0/thread-churn/malloc_info_thread-churn_307024_idle.xml"}}
```

### burst-free-small

```json
{"schema":"alloc_bench_v1_1","profile":"burst-free-small","mode":"duration","threads":4,"seed":20260709,"warmup_s":1.000000,"duration_s":5.000000,"idle_s":2.000000,"ops_per_thread":0,"live_set_per_thread":256,"churn_period_ms":2000,"stagger_churn":false,"large_period_ops":100,"large_hold_ops":100,"burst_size":2048,"burst_hold_ops":4096,"unsorted_batch":4096,"background_live_ops":1,"background_phase_ops":8,"idle_release_pct":0,"avg_size_bytes":40.000,"theoretical_live_kb":40.000,"touch_policy":"ge128k_full_else_edge64","histogram":[{"size":16,"weight":1},{"size":24,"weight":1},{"size":32,"weight":1},{"size":40,"weight":1},{"size":48,"weight":1},{"size":56,"weight":1},{"size":64,"weight":1}],"measure_elapsed_s":5.000802934,"measure_ops":1467867381,"throughput_ops_per_s":293526339.744,"thread_ops":[362849124,362744028,372142571,370131658],"thread_size_hash":["05b48ec2c68c9f33","3aee28890217aab3","caf6e9ff8b4897c3","04479c167d61483b"],"op_hash_fn":"fnv1a64_size_sequence","latency_ns":{"sample_every":64,"samples":8373310,"p50":110,"p99":119,"bucket_bounds":[100,120,143,172,205,246,294,352,422,505,604,723,866,1037,1241,1486,1778,2129,2548,3051,3652,4371,5233,6264,7499,8977,10746,12864,15399,18434,22067,26416,31623,37855,45316,54247,64938,77737,93057,111397,133352,159634,191095,228757,273842,327812,392419,469759,562341,673170,805842,964662,1154782,1382372,1654817,1980957,2371374,2838736,3398208,4067944,4869675,5829415,6978306,8353625,10000000],"hist":[8372329,724,37,15,23,2,2,2,0,0,0,0,20,72,53,25,3,1,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]},"memory":{"measure_rss_kb_samples":[2664,2664,2664],"measure_pss_kb_samples":[985,985,985],"measure_rss_kb_median":2664,"measure_pss_kb_median":985,"measure_rss_kb_p50":2600,"measure_rss_kb_p95":2600,"measure_rss_kb_max":2664,"measure_rss_kb_n_samples":2,"measure_rss_kb_sample_failures":0,"idle_release_pct":0,"idle_rss_kb_after_release":2664,"idle_pss_kb_after_release":985,"idle_rss_kb":2680,"idle_pss_kb":1001,"vmhwm_kb":2684,"malloc_info_measure":"/tmp/alloc_bench_v11_impl_logs/host_c0/burst-free-small/malloc_info_burst-free-small_307130_measure.xml","malloc_info_idle":"/tmp/alloc_bench_v11_impl_logs/host_c0/burst-free-small/malloc_info_burst-free-small_307130_idle.xml"}}
```

### unsorted-drain

```json
{"schema":"alloc_bench_v1_1","profile":"unsorted-drain","mode":"duration","threads":4,"seed":20260709,"warmup_s":1.000000,"duration_s":5.000000,"idle_s":2.000000,"ops_per_thread":0,"live_set_per_thread":4096,"churn_period_ms":2000,"stagger_churn":false,"large_period_ops":100,"large_hold_ops":100,"burst_size":2048,"burst_hold_ops":4096,"unsorted_batch":4096,"background_live_ops":1,"background_phase_ops":8,"idle_release_pct":0,"avg_size_bytes":6280.960,"theoretical_live_kb":100495.360,"touch_policy":"ge128k_full_else_edge64","histogram":[{"size":16,"weight":8},{"size":64,"weight":12},{"size":256,"weight":18},{"size":1024,"weight":24},{"size":4096,"weight":18},{"size":16384,"weight":12},{"size":32768,"weight":6},{"size":65536,"weight":2}],"measure_elapsed_s":5.000584199,"measure_ops":368955196,"throughput_ops_per_s":73782418.477,"thread_ops":[91637606,92661631,91515433,93140526],"thread_size_hash":["ae108b825be4c861","1d8a022ac35b269d","cfa8bb65f4bf09eb","35195b96259be812"],"op_hash_fn":"fnv1a64_size_sequence","latency_ns":{"sample_every":64,"samples":3715197,"p50":110,"p99":676,"bucket_bounds":[100,120,143,172,205,246,294,352,422,505,604,723,866,1037,1241,1486,1778,2129,2548,3051,3652,4371,5233,6264,7499,8977,10746,12864,15399,18434,22067,26416,31623,37855,45316,54247,64938,77737,93057,111397,133352,159634,191095,228757,273842,327812,392419,469759,562341,673170,805842,964662,1154782,1382372,1654817,1980957,2371374,2838736,3398208,4067944,4869675,5829415,6978306,8353625,10000000],"hist":[3538039,51203,25819,14256,10732,8419,7600,6719,6086,5937,5332,4934,4434,3511,2978,2525,1584,939,517,245,96,179,442,307,947,7192,4143,82,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]},"memory":{"measure_rss_kb_samples":[138484,138484,138484],"measure_pss_kb_samples":[136805,136805,136805],"measure_rss_kb_median":138484,"measure_pss_kb_median":136805,"measure_rss_kb_p50":138032,"measure_rss_kb_p95":138032,"measure_rss_kb_max":138520,"measure_rss_kb_n_samples":2,"measure_rss_kb_sample_failures":0,"idle_release_pct":0,"idle_rss_kb_after_release":138484,"idle_pss_kb_after_release":136805,"idle_rss_kb":138548,"idle_pss_kb":136869,"vmhwm_kb":139176,"malloc_info_measure":"/tmp/alloc_bench_v11_impl_logs/host_c0/unsorted-drain/malloc_info_unsorted-drain_307143_measure.xml","malloc_info_idle":"/tmp/alloc_bench_v11_impl_logs/host_c0/unsorted-drain/malloc_info_unsorted-drain_307143_idle.xml"}}
```

### burst-free-small malloc_info fastbin 摘录

Summary: `fast_last=210016 bytes`, `unsorted_sum=308 bytes`.

```text
6:<total type="fast" count="0" size="0"/>
7:<total type="rest" count="5" size="118724"/>
24:  <unsorted from="65" to="65" total="65" count="1"/>
26:<total type="fast" count="384" size="20752"/>
27:<total type="rest" count="19" size="1522"/>
42:  <unsorted from="161" to="161" total="161" count="1"/>
44:<total type="fast" count="1260" size="65744"/>
45:<total type="rest" count="12" size="539"/>
63:  <unsorted from="33" to="33" total="33" count="1"/>
65:<total type="fast" count="1275" size="68384"/>
66:<total type="rest" count="6" size="1045"/>
84:  <unsorted from="49" to="49" total="49" count="1"/>
86:<total type="fast" count="1035" size="55136"/>
87:<total type="rest" count="17" size="1552"/>
94:<total type="fast" count="3954" size="210016"/>
95:<total type="rest" count="59" size="123382"/>
96:<total type="mmap" count="0" size="0"/>
```

### unsorted-drain malloc_info unsorted/rest 摘录

Summary: `fast_last=0 bytes`, `rest_last=26665016 bytes`, `unsorted_sum=450516 bytes`.

```text
5:<total type="fast" count="0" size="0"/>
6:<total type="rest" count="1" size="118528"/>
131:  <unsorted from="897" to="11361" total="41660" count="12"/>
133:<total type="fast" count="0" size="0"/>
134:<total type="rest" count="2304" size="6278367"/>
222:  <unsorted from="1169" to="1169" total="1169" count="1"/>
224:<total type="fast" count="0" size="0"/>
225:<total type="rest" count="1488" size="7304303"/>
353:  <unsorted from="49" to="49" total="49" count="1"/>
355:<total type="fast" count="0" size="0"/>
356:<total type="rest" count="1650" size="7613585"/>
461:  <unsorted from="273" to="32785" total="407638" count="150"/>
463:<total type="fast" count="0" size="0"/>
464:<total type="rest" count="2010" size="5350233"/>
471:<total type="fast" count="0" size="0"/>
472:<total type="rest" count="7453" size="26665016"/>
473:<total type="mmap" count="0" size="0"/>
```

## 5. 已知限制

- A7 当前揭示 host C0 自动 trim 行为不足，报告为偏差而非绕过；Batch 2.5 若要观测 L3，仍应在板上用 GLIBC_TUNABLES 对照而不是依赖 host C0 自回收。
- `large-transient` 的默认触碰策略按 v1.1 变更为 >=128 KiB 全量触碰，因此与 v1 的绝对吞吐/RSS 不可直接数值对比；A9 只比较旧静态语义字段。
- 周期 RSS 采样在很短的 `--ops-per-thread` 运行中可能为 0 个样本；正式 duration 模式本次六档短跑均产生 `measure_rss_kb_n_samples=2`。
- host 与 armv7l 的 allocator、时钟、CPU 和页回收行为不同；本任务未上板。
