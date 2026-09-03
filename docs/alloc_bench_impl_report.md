> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# alloc_bench implementation report

## 1. 交付文件清单

- `bench/alloc_bench/alloc_bench.c`：单文件 C99 微基准，动态链接 libc + pthread。
- `bench/alloc_bench/Makefile`：目标 `host`、`host-asan`、`armv7l`。
- `bench/alloc_bench/selftest.sh`：一键执行 A1-A5。
- `bench/alloc_bench/README.md`：CLI、四档 profile 参数表、external 直方图格式。

## 2. 验收门执行原文

构建命令：

```text
+ make -C bench/alloc_bench clean host host-asan armv7l
make: Entering directory '<WORKSPACE>/bench/alloc_bench'
rm -f alloc_bench.host alloc_bench.host-asan alloc_bench.armv7l
gcc -std=c99 -O2 -g -Wall -Wextra -Werror -D_GNU_SOURCE  -o alloc_bench.host alloc_bench.c -pthread
gcc -std=c99 -Wall -Wextra -Werror -D_GNU_SOURCE -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -o alloc_bench.host-asan alloc_bench.c -pthread
bwrap --tmpfs / --dir /home --bind /home /home --dir /tmp --bind /tmp /tmp --ro-bind <USER_HOME>/GBS-ROOT-TIZEN-UNIFIED-LLVM-MLGO/local/BUILD-ROOTS/scratch.armv7l.0/usr /usr --ro-bind <USER_HOME>/GBS-ROOT-TIZEN-UNIFIED-LLVM-MLGO/local/BUILD-ROOTS/scratch.armv7l.0/lib /lib --proc /proc --ro-bind <USER_HOME>/GBS-ROOT-TIZEN-UNIFIED-LLVM-MLGO/local/BUILD-ROOTS/scratch.armv7l.0/emul /emul <USER_HOME>/GBS-ROOT-TIZEN-UNIFIED-LLVM-MLGO/local/BUILD-ROOTS/scratch.armv7l.0/emul/usr/bin/armv7l-tizen-linux-gnueabi-gcc -B/usr/lib/gcc/armv7l-tizen-linux-gnueabi/14.2.0/ -std=c99 -O2 -g -Wall -Wextra -Werror -D_GNU_SOURCE -O2 -g  -o alloc_bench.armv7l alloc_bench.c -pthread
make: Leaving directory '<WORKSPACE>/bench/alloc_bench'
```

A1-A5 selftest：

```text
+ ./bench/alloc_bench/selftest.sh
PASS build host
PASS A1 determinism
PASS A2 ASan+UBSan built-in profiles
PASS A3 RSS lower-bound sanity
PASS A4 JSON parse
PASS A5 armv7l ELF 32-bit ARM dynamic
SUMMARY PASS=6 FAIL=0
```

A5 `file` check：

```text
bench/alloc_bench/alloc_bench.armv7l: ELF 32-bit LSB executable, ARM, EABI5 version 1 (SYSV), dynamically linked, interpreter /lib/ld-linux.so.3, BuildID[sha1]=b5365642fe5d390e24416f02158e5cbeefd16947, for GNU/Linux 3.2.0, with debug_info, not stripped
```

Extra host-asan duration gate, shortened parameters `--warmup 1 --duration 5 --idle 2 --threads 4`：

```text
+ env -u GLIBC_TUNABLES ASAN_OPTIONS=abort_on_error=1:detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 bench/alloc_bench/alloc_bench.host-asan --profile small-churn --threads 4 --seed 20260708 --warmup 1 --duration 5 --idle 2 --outdir /tmp/alloc_bench_impl_logs/asan-duration/small-churn
stderr bytes: 0
+ env -u GLIBC_TUNABLES ASAN_OPTIONS=abort_on_error=1:detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 bench/alloc_bench/alloc_bench.host-asan --profile mixed --threads 4 --seed 20260708 --warmup 1 --duration 5 --idle 2 --outdir /tmp/alloc_bench_impl_logs/asan-duration/mixed
stderr bytes: 0
+ env -u GLIBC_TUNABLES ASAN_OPTIONS=abort_on_error=1:detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 bench/alloc_bench/alloc_bench.host-asan --profile large-transient --threads 4 --seed 20260708 --warmup 1 --duration 5 --idle 2 --outdir /tmp/alloc_bench_impl_logs/asan-duration/large-transient
stderr bytes: 0
+ env -u GLIBC_TUNABLES ASAN_OPTIONS=abort_on_error=1:detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 bench/alloc_bench/alloc_bench.host-asan --profile thread-churn --threads 4 --seed 20260708 --warmup 1 --duration 5 --idle 2 --outdir /tmp/alloc_bench_impl_logs/asan-duration/thread-churn
stderr bytes: 0
```

## 3. 偏差清单

无。

## 4. host C0 profile JSON 回显

### small-churn

```json
{"schema":"alloc_bench_v1","profile":"small-churn","mode":"duration","threads":4,"seed":20260708,"warmup_s":1.000000,"duration_s":5.000000,"idle_s":2.000000,"ops_per_thread":0,"live_set_per_thread":256,"churn_period_ms":2000,"large_period_ops":100,"large_hold_ops":100,"avg_size_bytes":99.200,"theoretical_live_kb":99.200,"histogram":[{"size":16,"weight":1},{"size":32,"weight":1},{"size":64,"weight":1},{"size":128,"weight":1},{"size":256,"weight":1}],"measure_elapsed_s":5.000827196,"measure_ops":768326770,"throughput_ops_per_s":153639935.932,"thread_ops":[190419458,189580465,195856081,192470766],"thread_size_hash":["a903c023e9cd6d28","fb391cfe77c4a368","54ea455741e9ab68","b680c2aeb34892a8"],"op_hash_fn":"fnv1a64_size_sequence","latency_ns":{"sample_every":64,"samples":12005108,"p50":110,"p99":119,"bucket_bounds":[100,120,143,172,205,246,294,352,422,505,604,723,866,1037,1241,1486,1778,2129,2548,3051,3652,4371,5233,6264,7499,8977,10746,12864,15399,18434,22067,26416,31623,37855,45316,54247,64938,77737,93057,111397,133352,159634,191095,228757,273842,327812,392419,469759,562341,673170,805842,964662,1154782,1382372,1654817,1980957,2371374,2838736,3398208,4067944,4869675,5829415,6978306,8353625,10000000],"hist":[12000043,3198,1098,370,155,30,2,2,0,0,1,0,7,40,72,50,22,5,1,4,1,3,1,0,0,0,1,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]},"memory":{"measure_rss_kb_samples":[2032,2096,2096],"measure_pss_kb_samples":[418,419,419],"measure_rss_kb_median":2096,"measure_pss_kb_median":419,"idle_rss_kb":2112,"idle_pss_kb":435,"vmhwm_kb":2116,"malloc_info_measure":"/tmp/alloc_bench_impl_logs/host-c0/small-churn/malloc_info_small-churn_140981_measure.xml","malloc_info_idle":"/tmp/alloc_bench_impl_logs/host-c0/small-churn/malloc_info_small-churn_140981_idle.xml"}}
```
### mixed

```json
{"schema":"alloc_bench_v1","profile":"mixed","mode":"duration","threads":4,"seed":20260708,"warmup_s":1.000000,"duration_s":5.000000,"idle_s":2.000000,"ops_per_thread":0,"live_set_per_thread":4096,"churn_period_ms":2000,"large_period_ops":100,"large_hold_ops":100,"avg_size_bytes":6280.960,"theoretical_live_kb":100495.360,"histogram":[{"size":16,"weight":8},{"size":64,"weight":12},{"size":256,"weight":18},{"size":1024,"weight":24},{"size":4096,"weight":18},{"size":16384,"weight":12},{"size":32768,"weight":6},{"size":65536,"weight":2}],"measure_elapsed_s":5.001032128,"measure_ops":384463176,"throughput_ops_per_s":76876765.867,"thread_ops":[94823591,96354511,97006806,96278268],"thread_size_hash":["f5c70bdb246bff1b","e2e60a0fd2b3706d","9ada708356010cc2","95f480b4b1205c66"],"op_hash_fn":"fnv1a64_size_sequence","latency_ns":{"sample_every":64,"samples":6007239,"p50":110,"p99":131,"bucket_bounds":[100,120,143,172,205,246,294,352,422,505,604,723,866,1037,1241,1486,1778,2129,2548,3051,3652,4371,5233,6264,7499,8977,10746,12864,15399,18434,22067,26416,31623,37855,45316,54247,64938,77737,93057,111397,133352,159634,191095,228757,273842,327812,392419,469759,562341,673170,805842,964662,1154782,1382372,1654817,1980957,2371374,2838736,3398208,4067944,4869675,5829415,6978306,8353625,10000000],"hist":[5920822,51618,21840,6992,1995,439,88,35,157,836,1060,521,309,154,153,85,50,18,21,34,9,1,1,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]},"memory":{"measure_rss_kb_samples":[112172,112236,112236],"measure_pss_kb_samples":[110558,110558,110558],"measure_rss_kb_median":112236,"measure_pss_kb_median":110558,"idle_rss_kb":112268,"idle_pss_kb":110590,"vmhwm_kb":112936,"malloc_info_measure":"/tmp/alloc_bench_impl_logs/host-c0/mixed/malloc_info_mixed_141225_measure.xml","malloc_info_idle":"/tmp/alloc_bench_impl_logs/host-c0/mixed/malloc_info_mixed_141225_idle.xml"}}
```
### large-transient

```json
{"schema":"alloc_bench_v1","profile":"large-transient","mode":"duration","threads":4,"seed":20260708,"warmup_s":1.000000,"duration_s":5.000000,"idle_s":2.000000,"ops_per_thread":0,"live_set_per_thread":4096,"churn_period_ms":2000,"large_period_ops":100,"large_hold_ops":100,"avg_size_bytes":6280.960,"theoretical_live_kb":100495.360,"histogram":[{"size":16,"weight":8},{"size":64,"weight":12},{"size":256,"weight":18},{"size":1024,"weight":24},{"size":4096,"weight":18},{"size":16384,"weight":12},{"size":32768,"weight":6},{"size":65536,"weight":2}],"measure_elapsed_s":5.000109145,"measure_ops":340630209,"throughput_ops_per_s":68124554.709,"thread_ops":[85342728,84667489,85287140,85332852],"thread_size_hash":["a739c6eaf0dd60f5","e63be6feb3af82ca","a46d9732f994303e","678b6edb640c3ee8"],"op_hash_fn":"fnv1a64_size_sequence","latency_ns":{"sample_every":64,"samples":5322349,"p50":110,"p99":591,"bucket_bounds":[100,120,143,172,205,246,294,352,422,505,604,723,866,1037,1241,1486,1778,2129,2548,3051,3652,4371,5233,6264,7499,8977,10746,12864,15399,18434,22067,26416,31623,37855,45316,54247,64938,77737,93057,111397,133352,159634,191095,228757,273842,327812,392419,469759,562341,673170,805842,964662,1154782,1382372,1654817,1980957,2371374,2838736,3398208,4067944,4869675,5829415,6978306,8353625,10000000],"hist":[5164043,59834,26718,9146,2792,612,134,30,79,6590,33460,10829,3774,1731,443,111,83,93,390,1053,306,53,9,11,8,7,3,5,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]},"memory":{"measure_rss_kb_samples":[113900,113964,113964],"measure_pss_kb_samples":[112286,112286,112286],"measure_rss_kb_median":113964,"measure_pss_kb_median":112286,"idle_rss_kb":113996,"idle_pss_kb":112318,"vmhwm_kb":115644,"malloc_info_measure":"/tmp/alloc_bench_impl_logs/host-c0/large-transient/malloc_info_large-transient_141460_measure.xml","malloc_info_idle":"/tmp/alloc_bench_impl_logs/host-c0/large-transient/malloc_info_large-transient_141460_idle.xml"}}
```
### thread-churn

```json
{"schema":"alloc_bench_v1","profile":"thread-churn","mode":"duration","threads":4,"seed":20260708,"warmup_s":1.000000,"duration_s":5.000000,"idle_s":2.000000,"ops_per_thread":0,"live_set_per_thread":4096,"churn_period_ms":2000,"large_period_ops":100,"large_hold_ops":100,"avg_size_bytes":6280.960,"theoretical_live_kb":100495.360,"histogram":[{"size":16,"weight":8},{"size":64,"weight":12},{"size":256,"weight":18},{"size":1024,"weight":24},{"size":4096,"weight":18},{"size":16384,"weight":12},{"size":32768,"weight":6},{"size":65536,"weight":2}],"measure_elapsed_s":5.000195949,"measure_ops":283945614,"throughput_ops_per_s":56786897.333,"thread_ops":[71099512,70989238,70846344,71010520],"thread_size_hash":["aa99b0005c90dcd4","e218c25f004e2a1d","f7957a10dc77798b","5a084832a777afb5"],"op_hash_fn":"fnv1a64_size_sequence","latency_ns":{"sample_every":64,"samples":4436655,"p50":110,"p99":133,"bucket_bounds":[100,120,143,172,205,246,294,352,422,505,604,723,866,1037,1241,1486,1778,2129,2548,3051,3652,4371,5233,6264,7499,8977,10746,12864,15399,18434,22067,26416,31623,37855,45316,54247,64938,77737,93057,111397,133352,159634,191095,228757,273842,327812,392419,469759,562341,673170,805842,964662,1154782,1382372,1654817,1980957,2371374,2838736,3398208,4067944,4869675,5829415,6978306,8353625,10000000],"hist":[4368252,40149,17360,5702,1672,424,75,21,89,420,597,412,558,387,169,200,56,38,20,27,16,3,0,1,1,2,1,0,0,0,0,0,2,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]},"memory":{"measure_rss_kb_samples":[112508,112572,112572],"measure_pss_kb_samples":[110767,110768,110768],"measure_rss_kb_median":112572,"measure_pss_kb_median":110768,"idle_rss_kb":112608,"idle_pss_kb":110804,"vmhwm_kb":112624,"malloc_info_measure":"/tmp/alloc_bench_impl_logs/host-c0/thread-churn/malloc_info_thread-churn_141966_measure.xml","malloc_info_idle":"/tmp/alloc_bench_impl_logs/host-c0/thread-churn/malloc_info_thread-churn_141966_idle.xml"}}
```

## 5. 已知限制

- host C0 回显使用 `--threads 4`，用于匹配 rpi4 默认线程规模；host 在线 CPU 数可能不同。
- 延迟 p50/p99 来自固定 64 桶 100 ns-10 ms 对数直方图插值，不是逐样本精确分位数。
- `smaps_rollup` 和 `VmHWM` 依赖 Linux `/proc`；非 Linux host 不支持这些字段。
- armv7l 默认构建依赖本机 GBS scratch root 和 `bwrap`，可用 `ARMV7L_ROOT` 或 `ARMV7L_CC` 覆盖。
- `large-transient` 的精确定义已在 README 固化：每第 100 个 op 使用一个 256 KiB-2 MiB 大块并持有 100 ops。
