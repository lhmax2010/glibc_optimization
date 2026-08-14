#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>
#include <malloc.h>

#define LAT_BUCKETS 64
#define MAX_DIST 128
#define MAX_RSS_SAMPLES 4096
#define TOUCH_FULL_THRESHOLD (128U * 1024U)
#define BACKGROUND_LIVE_OPS 1
#define BACKGROUND_PHASE_OPS 8
#define FNV_OFFSET 1469598103934665603ULL
#define FNV_PRIME 1099511628211ULL

enum phase {
    PHASE_WARMUP = 0,
    PHASE_MEASURE = 1,
    PHASE_IDLE = 2,
    PHASE_IDLE_RELEASE = 3,
    PHASE_REFAULT = 4,
    PHASE_DONE = 5
};

enum release_order {
    RELEASE_HIGH = 0,
    RELEASE_LOW,
    RELEASE_RANDOM,
    RELEASE_INTERLEAVE
};

enum profile_kind {
    PROFILE_SMALL_CHURN = 0,
    PROFILE_MIXED,
    PROFILE_LARGE_TRANSIENT,
    PROFILE_THREAD_CHURN,
    PROFILE_BURST_FREE_SMALL,
    PROFILE_UNSORTED_DRAIN,
    PROFILE_EXTERNAL
};

enum burst_phase {
    BURST_ACCUM = 0,
    BURST_RELEASE,
    BURST_HOLD
};

enum unsorted_phase {
    UNSORTED_FILL = 0,
    UNSORTED_DRAIN,
    UNSORTED_REQUEST
};

struct bucket {
    size_t size;
    uint32_t weight;
};

struct config {
    enum profile_kind profile_kind;
    char profile[256];
    char external_path[PATH_MAX];
    int threads;
    uint64_t seed;
    double warmup_s;
    double duration_s;
    double idle_s;
    uint64_t ops_per_thread;
    int use_ops_mode;
    size_t live_set;
    int live_set_overridden;
    int churn_period_ms;
    int stagger_churn;
    int large_period_ops;
    int large_hold_ops;
    size_t burst_size;
    uint64_t burst_hold_ops;
    size_t unsorted_batch;
    int touch_full;
    int idle_release_pct;
    int idle_trim;
    enum release_order release_order;
    char release_order_name[16];
    uint64_t post_trim_ops_per_thread;
    char outdir[PATH_MAX];
    struct bucket dist[MAX_DIST];
    int dist_count;
    uint64_t total_weight;
    double avg_size;
};

struct worker_stats {
    uint64_t measure_ops;
    uint64_t size_hash;
    uint64_t latency_hist[LAT_BUCKETS];
};

struct mem_sample {
    long rss_kb;
    long pss_kb;
};

struct heap_sample {
    long glibc_heap_pd_kb;
    long other_anon_pd_kb;
    long file_backed_pd_kb;
    uint64_t glibc_heap_segments;
};

struct fault_sample {
    uint64_t minflt;
    uint64_t majflt;
};

struct malloc_info_stats {
    uint64_t fast_bytes;
    uint64_t rest_bytes;
    uint64_t unsorted_bytes;
    uint64_t arena_count;
};

struct extended_samples {
    struct heap_sample pretrim_heap;
    struct heap_sample posttrim_heap;
    struct heap_sample postrefault_heap;
    struct fault_sample pretrim_faults;
    struct fault_sample posttrim_faults;
    struct fault_sample postrefault_faults;
    struct malloc_info_stats measure_mi;
    struct malloc_info_stats release_mi;
    struct malloc_info_stats posttrim_mi;
    struct malloc_info_stats idle_mi;
    uint64_t trim_elapsed_ns;
    uint64_t post_trim_elapsed_ns;
    uint64_t released_bytes;
    uint64_t released_objects;
    char malloc_release_path[PATH_MAX];
    char malloc_posttrim_path[PATH_MAX];
};

struct rss_series {
    long rss_kb[MAX_RSS_SAMPLES];
    size_t count;
    uint64_t skipped;
};

struct alloc_slot {
    void *ptr;
    uint64_t seq;
    size_t size;
};

struct release_entry {
    uintptr_t addr;
    size_t index;
};

struct slot {
    int ordinal;
    uint64_t generation;
    pthread_t thread;
    int alive;
    volatile int measure_done;
    volatile int idle_release_done;
    volatile int post_trim_done;
    volatile int exit_reason;
    uint64_t idle_released_bytes;
    uint64_t idle_released_objects;
    struct worker_stats arg_stats;
    struct worker_stats accum;
};

struct worker_arg {
    const struct config *cfg;
    struct slot *slot;
    uint64_t seed;
    uint64_t start_hash;
    uint64_t ops_limit;
};

static volatile int g_phase = PHASE_WARMUP;

static int atomic_load_int(volatile int *ptr)
{
    return __atomic_load_n(ptr, __ATOMIC_ACQUIRE);
}

static void atomic_store_int(volatile int *ptr, int value)
{
    __atomic_store_n(ptr, value, __ATOMIC_RELEASE);
}

static const uint64_t latency_bounds[LAT_BUCKETS + 1] = {
    100, 120, 143, 172, 205, 246, 294, 352, 422, 505, 604, 723, 866,
    1037, 1241, 1486, 1778, 2129, 2548, 3051, 3652, 4371, 5233, 6264,
    7499, 8977, 10746, 12864, 15399, 18434, 22067, 26416, 31623,
    37855, 45316, 54247, 64938, 77737, 93057, 111397, 133352, 159634,
    191095, 228757, 273842, 327812, 392419, 469759, 562341, 673170,
    805842, 964662, 1154782, 1382372, 1654817, 1980957, 2371374,
    2838736, 3398208, 4067944, 4869675, 5829415, 6978306, 8353625,
    10000000
};

static uint64_t now_ns(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0)
        return 0;
    return (uint64_t) ts.tv_sec * 1000000000ULL + (uint64_t) ts.tv_nsec;
}

static void sleep_seconds(double seconds)
{
    if (seconds <= 0.0)
        return;
    struct timespec ts;
    ts.tv_sec = (time_t) seconds;
    ts.tv_nsec = (long) ((seconds - (double) ts.tv_sec) * 1000000000.0);
    while (nanosleep(&ts, &ts) != 0 && errno == EINTR)
        ;
}

static uint64_t xorshift64(uint64_t *state)
{
    uint64_t x = *state;
    if (x == 0)
        x = 0x9e3779b97f4a7c15ULL;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    *state = x;
    return x;
}

static uint64_t fnv_size(uint64_t hash, size_t size)
{
    uint64_t x = (uint64_t) size;
    for (int i = 0; i < 8; i++) {
        hash ^= (x & 0xffU);
        hash *= FNV_PRIME;
        x >>= 8;
    }
    return hash;
}

static void touch_alloc(const struct config *cfg, void *ptr, size_t size,
                        uint64_t salt)
{
    unsigned char *p = (unsigned char *) ptr;
    unsigned char v = (unsigned char) (salt & 0xffU);
    if (cfg->touch_full || size >= TOUCH_FULL_THRESHOLD) {
        memset(p, v, size);
        return;
    }
    if (size < 128) {
        memset(p, v, size);
        return;
    }
    memset(p, v, 64);
    memset(p + size - 64, (unsigned char) (v ^ 0xa5U), 64);
}

static int latency_bucket(uint64_t ns)
{
    if (ns <= latency_bounds[0])
        return 0;
    for (int i = 0; i < LAT_BUCKETS; i++) {
        if (ns < latency_bounds[i + 1])
            return i;
    }
    return LAT_BUCKETS - 1;
}

static uint64_t hist_percentile(const uint64_t hist[LAT_BUCKETS], double pct)
{
    uint64_t total = 0;
    for (int i = 0; i < LAT_BUCKETS; i++)
        total += hist[i];
    if (total == 0)
        return 0;

    uint64_t rank = (uint64_t) ((pct / 100.0) * (double) (total - 1)) + 1;
    uint64_t seen = 0;
    for (int i = 0; i < LAT_BUCKETS; i++) {
        uint64_t prev = seen;
        seen += hist[i];
        if (seen >= rank) {
            uint64_t lo = latency_bounds[i];
            uint64_t hi = latency_bounds[i + 1];
            if (hist[i] <= 1)
                return (lo + hi) / 2;
            double in_bucket = (double) (rank - prev - 1) / (double) hist[i];
            return lo + (uint64_t) ((double) (hi - lo) * in_bucket);
        }
    }
    return latency_bounds[LAT_BUCKETS];
}

static void stats_init(struct worker_stats *stats, uint64_t hash)
{
    stats->measure_ops = 0;
    stats->size_hash = hash;
    memset(stats->latency_hist, 0, sizeof(stats->latency_hist));
}

static void stats_merge(struct worker_stats *dst, const struct worker_stats *src)
{
    dst->measure_ops += src->measure_ops;
    dst->size_hash = src->size_hash;
    for (int i = 0; i < LAT_BUCKETS; i++)
        dst->latency_hist[i] += src->latency_hist[i];
}

static size_t sample_dist(const struct config *cfg, uint64_t *rng)
{
    uint64_t r = xorshift64(rng) % cfg->total_weight;
    uint64_t acc = 0;
    for (int i = 0; i < cfg->dist_count; i++) {
        acc += cfg->dist[i].weight;
        if (r < acc)
            return cfg->dist[i].size;
    }
    return cfg->dist[cfg->dist_count - 1].size;
}

static size_t sample_large(uint64_t *rng)
{
    static const size_t sizes[] = { 262144, 524288, 1048576, 2097152 };
    return sizes[xorshift64(rng) % (sizeof(sizes) / sizeof(sizes[0]))];
}

static size_t sample_burst_small(uint64_t *rng)
{
    static const size_t sizes[] = { 16, 24, 32, 40, 48, 56, 64 };
    return sizes[xorshift64(rng) % (sizeof(sizes) / sizeof(sizes[0]))];
}

static size_t sample_unsorted_fill(uint64_t *rng)
{
    static const size_t sizes[] = { 256, 512, 1024, 2048, 4096 };
    return sizes[xorshift64(rng) % (sizeof(sizes) / sizeof(sizes[0]))];
}

static size_t sample_unsorted_request(uint64_t *rng)
{
    static const size_t sizes[] = { 96, 128, 160, 192 };
    return sizes[xorshift64(rng) % (sizeof(sizes) / sizeof(sizes[0]))];
}

static void free_pool(struct alloc_slot *slots, size_t count)
{
    if (!slots)
        return;
    for (size_t i = 0; i < count; i++) {
        free(slots[i].ptr);
        slots[i].ptr = NULL;
        slots[i].size = 0;
    }
}

static void init_order(size_t *order, size_t count)
{
    for (size_t i = 0; i < count; i++)
        order[i] = i;
}

static void shuffle_order(size_t *order, size_t count, uint64_t *rng)
{
    if (count <= 1)
        return;
    for (size_t i = count - 1; i > 0; i--) {
        size_t j = (size_t) (xorshift64(rng) % (uint64_t) (i + 1));
        size_t tmp = order[i];
        order[i] = order[j];
        order[j] = tmp;
    }
}

static void record_op(struct worker_stats *stats, int counted, size_t size,
                      int sample_latency, uint64_t elapsed)
{
    if (!counted)
        return;
    stats->measure_ops++;
    stats->size_hash = fnv_size(stats->size_hash, size);
    if (sample_latency)
        stats->latency_hist[latency_bucket(elapsed)]++;
}

static void *timed_malloc_record(const struct config *cfg, size_t size,
                                 uint64_t salt, struct worker_stats *stats,
                                 int counted)
{
    int sample_latency = counted &&
        ((stats->measure_ops & 63ULL) == 0ULL);
    uint64_t t0 = 0;
    if (sample_latency)
        t0 = now_ns();
    void *p = malloc(size);
    uint64_t elapsed = 0;
    if (sample_latency) {
        uint64_t t1 = now_ns();
        elapsed = t1 > t0 ? t1 - t0 : 0;
    }
    if (!p)
        return NULL;
    touch_alloc(cfg, p, size, salt);
    record_op(stats, counted, size, sample_latency, elapsed);
    return p;
}

static int do_live_op(const struct config *cfg, struct alloc_slot *pool,
                      uint64_t *rng, uint64_t local_op,
                      uint64_t *alloc_seq, struct worker_stats *stats,
                      int counted)
{
    size_t size = sample_dist(cfg, rng);
    void *p = timed_malloc_record(cfg, size, *rng ^ local_op, stats, counted);
    if (!p)
        return -1;

    size_t idx = (size_t) (xorshift64(rng) % cfg->live_set);
    void *old = pool[idx].ptr;
    pool[idx].ptr = p;
    pool[idx].seq = ++(*alloc_seq);
    pool[idx].size = size;
    free(old);
    return 0;
}

static int compare_release_entry(const void *a, const void *b)
{
    const struct release_entry *ea = a;
    const struct release_entry *eb = b;
    if (ea->addr < eb->addr)
        return -1;
    if (ea->addr > eb->addr)
        return 1;
    return 0;
}

static void shuffle_release_entries(struct release_entry *entries,
                                    size_t count, uint64_t *rng)
{
    if (count <= 1)
        return;
    for (size_t i = count - 1; i > 0; i--) {
        size_t j = (size_t) (xorshift64(rng) % (uint64_t) (i + 1));
        struct release_entry tmp = entries[i];
        entries[i] = entries[j];
        entries[j] = tmp;
    }
}

static void release_live_pool_pct(struct alloc_slot *pool, size_t count,
                                  int pct, enum release_order order,
                                  uint64_t release_seed,
                                  struct release_entry *entries,
                                  uint64_t *released_bytes,
                                  uint64_t *released_objects)
{
    *released_bytes = 0;
    *released_objects = 0;
    if (!pool || !entries || pct <= 0)
        return;

    size_t available = 0;
    for (size_t i = 0; i < count; i++) {
        if (pool[i].ptr) {
            entries[available].addr = (uintptr_t) pool[i].ptr;
            entries[available].index = i;
            available++;
        }
    }
    size_t release_count = (count * (size_t) pct) / 100U;
    if (release_count > available)
        release_count = available;

    qsort(entries, available, sizeof(*entries), compare_release_entry);
    if (order == RELEASE_RANDOM) {
        if (release_seed == 0)
            release_seed = UINT64_C(0x9e3779b97f4a7c15);
        shuffle_release_entries(entries, available, &release_seed);
    }

    size_t even_count = (available + 1U) / 2U;
    for (size_t n = 0; n < release_count; n++) {
        size_t pos;
        if (order == RELEASE_HIGH)
            pos = available - 1U - n;
        else if (order == RELEASE_INTERLEAVE)
            pos = n < even_count ? 2U * n :
                2U * (n - even_count) + 1U;
        else
            pos = n;
        size_t idx = entries[pos].index;
        *released_bytes += pool[idx].size;
        (*released_objects)++;
        free(pool[idx].ptr);
        pool[idx].ptr = NULL;
        pool[idx].seq = 0;
        pool[idx].size = 0;
    }
}

static void *worker_main(void *opaque)
{
    struct worker_arg local_arg = *(struct worker_arg *) opaque;
    free(opaque);
    struct worker_arg *arg = &local_arg;
    const struct config *cfg = arg->cfg;
    struct slot *slot = arg->slot;
    uint64_t rng = arg->seed;
    uint64_t local_op = 0;
    uint64_t alloc_seq = 0;
    uint64_t churn_deadline = 0;
    int measure_started = 0;
    int idle_released = 0;
    int post_trim_started = 0;
    uint64_t post_trim_ops = 0;
    struct alloc_slot *pool = NULL;
    struct alloc_slot *large_pool = NULL;
    struct alloc_slot *burst_pool = NULL;
    struct alloc_slot *unsorted_pool = NULL;
    struct alloc_slot *request_pool = NULL;
    size_t *burst_order = NULL;
    size_t *unsorted_order = NULL;
    struct release_entry *release_entries = MAP_FAILED;
    size_t release_entries_size =
        cfg->live_set * sizeof(*release_entries);
    size_t large_slots = (size_t) cfg->large_hold_ops;
    size_t burst_count = 0;
    size_t burst_release_done = 0;
    uint64_t burst_hold_done = 0;
    enum burst_phase burst_phase = BURST_ACCUM;
    size_t unsorted_fill_count = 0;
    size_t unsorted_drain_done = 0;
    size_t unsorted_request_count = 0;
    enum unsorted_phase unsorted_phase = UNSORTED_FILL;
    size_t request_cap = cfg->unsorted_batch / 2U;

    stats_init(&slot->arg_stats, arg->start_hash);
    atomic_store_int(&slot->measure_done, 0);
    atomic_store_int(&slot->idle_release_done, 0);
    atomic_store_int(&slot->post_trim_done, 0);
    atomic_store_int(&slot->exit_reason, 0);
    slot->idle_released_bytes = 0;
    slot->idle_released_objects = 0;

    pool = calloc(cfg->live_set, sizeof(*pool));
    if (!pool) {
        atomic_store_int(&slot->exit_reason, 2);
        return NULL;
    }

    if (cfg->profile_kind == PROFILE_LARGE_TRANSIENT) {
        large_pool = calloc(large_slots, sizeof(*large_pool));
        if (!large_pool) {
            free(pool);
            atomic_store_int(&slot->exit_reason, 2);
            return NULL;
        }
    }

    if (cfg->profile_kind == PROFILE_BURST_FREE_SMALL) {
        burst_pool = calloc(cfg->burst_size, sizeof(*burst_pool));
        burst_order = malloc(cfg->burst_size * sizeof(*burst_order));
        if (!burst_pool || !burst_order) {
            free(pool);
            free(large_pool);
            free(burst_pool);
            free(burst_order);
            atomic_store_int(&slot->exit_reason, 2);
            return NULL;
        }
    }

    if (cfg->profile_kind == PROFILE_UNSORTED_DRAIN) {
        unsorted_pool = calloc(cfg->unsorted_batch, sizeof(*unsorted_pool));
        request_pool = calloc(request_cap, sizeof(*request_pool));
        unsorted_order = malloc(cfg->unsorted_batch * sizeof(*unsorted_order));
        if (!unsorted_pool || !request_pool || !unsorted_order) {
            free(pool);
            free(large_pool);
            free(burst_pool);
            free(burst_order);
            free(unsorted_pool);
            free(request_pool);
            free(unsorted_order);
            atomic_store_int(&slot->exit_reason, 2);
            return NULL;
        }
    }

    release_entries = mmap(NULL, release_entries_size,
                           PROT_READ | PROT_WRITE,
                           MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (release_entries == MAP_FAILED) {
        free(pool);
        free(large_pool);
        free(burst_pool);
        free(burst_order);
        free(unsorted_pool);
        free(request_pool);
        free(unsorted_order);
        atomic_store_int(&slot->exit_reason, 2);
        return NULL;
    }

    if (cfg->profile_kind == PROFILE_THREAD_CHURN) {
        uint64_t period_ns = (uint64_t) cfg->churn_period_ms * 1000000ULL;
        uint64_t offset_ns = 0;
        if (cfg->stagger_churn && cfg->threads > 0)
            offset_ns = (period_ns * (uint64_t) slot->ordinal) /
                        (uint64_t) cfg->threads;
        churn_deadline = now_ns() + period_ns + offset_ns;
    }

    for (;;) {
        int phase = atomic_load_int(&g_phase);
        if (phase == PHASE_DONE)
            break;
        if (phase == PHASE_IDLE || phase == PHASE_IDLE_RELEASE) {
            if (phase == PHASE_IDLE_RELEASE && !idle_released) {
                release_live_pool_pct(pool, cfg->live_set,
                                      cfg->idle_release_pct,
                                      cfg->release_order,
                                      arg->seed ^
                                      UINT64_C(0xd1b54a32d192ed03),
                                      release_entries,
                                      &slot->idle_released_bytes,
                                      &slot->idle_released_objects);
                idle_released = 1;
                atomic_store_int(&slot->idle_release_done, 1);
            }
            atomic_store_int(&slot->measure_done, 1);
            usleep(1000);
            continue;
        }
        if (phase == PHASE_REFAULT) {
            if (!post_trim_started) {
                rng = arg->seed ^ UINT64_C(0x94d049bb133111eb);
                if (rng == 0)
                    rng = UINT64_C(0x2545f4914f6cdd1d);
                post_trim_ops = 0;
                post_trim_started = 1;
            }
            if (post_trim_ops >= cfg->post_trim_ops_per_thread) {
                atomic_store_int(&slot->post_trim_done, 1);
                usleep(1000);
                continue;
            }
            if (do_live_op(cfg, pool, &rng, post_trim_ops, &alloc_seq,
                           &slot->arg_stats, 0) != 0) {
                atomic_store_int(&slot->exit_reason, 2);
                break;
            }
            post_trim_ops++;
            continue;
        }
        if (phase == PHASE_MEASURE && !measure_started) {
            rng = arg->seed;
            local_op = 0;
            alloc_seq = 0;
            free_pool(burst_pool, cfg->burst_size);
            free_pool(unsorted_pool, cfg->unsorted_batch);
            free_pool(request_pool, request_cap);
            burst_count = 0;
            burst_release_done = 0;
            burst_hold_done = 0;
            burst_phase = BURST_ACCUM;
            unsorted_fill_count = 0;
            unsorted_drain_done = 0;
            unsorted_request_count = 0;
            unsorted_phase = UNSORTED_FILL;
            measure_started = 1;
        }

        if (cfg->profile_kind == PROFILE_THREAD_CHURN &&
            cfg->churn_period_ms > 0 && now_ns() >= churn_deadline &&
            phase != PHASE_IDLE) {
            atomic_store_int(&slot->exit_reason, 1);
            free_pool(pool, cfg->live_set);
            free(pool);
            free_pool(large_pool, large_slots);
            free(large_pool);
            free_pool(burst_pool, cfg->burst_size);
            free(burst_pool);
            free(burst_order);
            free_pool(unsorted_pool, cfg->unsorted_batch);
            free(unsorted_pool);
            free_pool(request_pool, request_cap);
            free(request_pool);
            free(unsorted_order);
            munmap(release_entries, release_entries_size);
            return NULL;
        }

        int counted = (phase == PHASE_MEASURE);
        if (counted && arg->ops_limit > 0 &&
            slot->arg_stats.measure_ops >= arg->ops_limit) {
            atomic_store_int(&slot->measure_done, 1);
            usleep(1000);
            continue;
        }

        int rc = 0;
        if (cfg->profile_kind == PROFILE_BURST_FREE_SMALL &&
            (local_op % (BACKGROUND_LIVE_OPS + BACKGROUND_PHASE_OPS)) ==
            BACKGROUND_PHASE_OPS) {
            rc = do_live_op(cfg, pool, &rng, local_op, &alloc_seq,
                            &slot->arg_stats, counted);
        } else if (cfg->profile_kind == PROFILE_BURST_FREE_SMALL) {
            if (burst_phase == BURST_ACCUM) {
                size_t size = sample_burst_small(&rng);
                void *p = timed_malloc_record(cfg, size, rng ^ local_op,
                                              &slot->arg_stats, counted);
                if (!p) {
                    rc = -1;
                } else {
                    burst_pool[burst_count].ptr = p;
                    burst_pool[burst_count].seq = ++alloc_seq;
                    burst_count++;
                    if (burst_count >= cfg->burst_size) {
                        init_order(burst_order, cfg->burst_size);
                        shuffle_order(burst_order, cfg->burst_size, &rng);
                        burst_phase = BURST_RELEASE;
                        burst_release_done = 0;
                    }
                }
            } else if (burst_phase == BURST_RELEASE) {
                size_t release_target = cfg->burst_size / 2U;
                if (burst_release_done < release_target) {
                    size_t idx = burst_order[burst_release_done++];
                    free(burst_pool[idx].ptr);
                    burst_pool[idx].ptr = NULL;
                }
                record_op(&slot->arg_stats, counted, 0, 0, 0);
                if (burst_release_done >= release_target) {
                    burst_phase = BURST_HOLD;
                    burst_hold_done = 0;
                }
            } else {
                record_op(&slot->arg_stats, counted, 0, 0, 0);
                burst_hold_done++;
                if (burst_hold_done >= cfg->burst_hold_ops) {
                    free_pool(burst_pool, cfg->burst_size);
                    burst_count = 0;
                    burst_phase = BURST_ACCUM;
                }
            }
        } else if (cfg->profile_kind == PROFILE_UNSORTED_DRAIN &&
                   (local_op % (BACKGROUND_LIVE_OPS + BACKGROUND_PHASE_OPS)) ==
                   BACKGROUND_PHASE_OPS) {
            rc = do_live_op(cfg, pool, &rng, local_op, &alloc_seq,
                            &slot->arg_stats, counted);
        } else if (cfg->profile_kind == PROFILE_UNSORTED_DRAIN) {
            if (unsorted_phase == UNSORTED_FILL) {
                if (unsorted_fill_count == 0)
                    free_pool(request_pool, request_cap);
                size_t size = sample_unsorted_fill(&rng);
                void *p = timed_malloc_record(cfg, size, rng ^ local_op,
                                              &slot->arg_stats, counted);
                if (!p) {
                    rc = -1;
                } else {
                    unsorted_pool[unsorted_fill_count].ptr = p;
                    unsorted_pool[unsorted_fill_count].seq = ++alloc_seq;
                    unsorted_fill_count++;
                    if (unsorted_fill_count >= cfg->unsorted_batch) {
                        init_order(unsorted_order, cfg->unsorted_batch);
                        shuffle_order(unsorted_order, cfg->unsorted_batch,
                                      &rng);
                        unsorted_phase = UNSORTED_DRAIN;
                        unsorted_drain_done = 0;
                    }
                }
            } else if (unsorted_phase == UNSORTED_DRAIN) {
                if (unsorted_drain_done < cfg->unsorted_batch) {
                    size_t idx = unsorted_order[unsorted_drain_done++];
                    free(unsorted_pool[idx].ptr);
                    unsorted_pool[idx].ptr = NULL;
                }
                record_op(&slot->arg_stats, counted, 0, 0, 0);
                if (unsorted_drain_done >= cfg->unsorted_batch) {
                    unsorted_phase = UNSORTED_REQUEST;
                    unsorted_request_count = 0;
                }
            } else {
                size_t size = sample_unsorted_request(&rng);
                void *p = timed_malloc_record(cfg, size, rng ^ local_op,
                                              &slot->arg_stats, counted);
                if (!p) {
                    rc = -1;
                } else {
                    request_pool[unsorted_request_count].ptr = p;
                    request_pool[unsorted_request_count].seq = ++alloc_seq;
                    unsorted_request_count++;
                    if (unsorted_request_count >= request_cap) {
                        unsorted_phase = UNSORTED_FILL;
                        unsorted_fill_count = 0;
                    }
                }
            }
        } else if (cfg->profile_kind == PROFILE_LARGE_TRANSIENT) {
            size_t size = sample_dist(cfg, &rng);
            int large_op = 0;
            if (cfg->large_period_ops > 0 &&
                (local_op % (uint64_t) cfg->large_period_ops) == 0) {
                size = sample_large(&rng);
                large_op = 1;
            }
            void *p = timed_malloc_record(cfg, size, rng ^ local_op,
                                          &slot->arg_stats, counted);
            if (!p) {
                rc = -1;
            } else if (large_op && large_pool) {
                size_t idx = (size_t) (local_op % large_slots);
                free(large_pool[idx].ptr);
                large_pool[idx].ptr = p;
                large_pool[idx].seq = ++alloc_seq;
            } else {
                size_t idx = (size_t) (xorshift64(&rng) % cfg->live_set);
                void *old = pool[idx].ptr;
                pool[idx].ptr = p;
                pool[idx].seq = ++alloc_seq;
                pool[idx].size = size;
                free(old);
            }
        } else {
            rc = do_live_op(cfg, pool, &rng, local_op, &alloc_seq,
                            &slot->arg_stats, counted);
        }

        if (rc != 0) {
            atomic_store_int(&slot->exit_reason, 2);
            break;
        }
        local_op++;
    }

    free_pool(pool, cfg->live_set);
    free(pool);
    free_pool(large_pool, large_slots);
    free(large_pool);
    free_pool(burst_pool, cfg->burst_size);
    free(burst_pool);
    free(burst_order);
    free_pool(unsorted_pool, cfg->unsorted_batch);
    free(unsorted_pool);
    free_pool(request_pool, request_cap);
    free(request_pool);
    free(unsorted_order);
    munmap(release_entries, release_entries_size);
    return NULL;
}

static int add_bucket(struct config *cfg, size_t size, uint32_t weight)
{
    if (cfg->dist_count >= MAX_DIST || size == 0 || weight == 0)
        return -1;
    cfg->dist[cfg->dist_count].size = size;
    cfg->dist[cfg->dist_count].weight = weight;
    cfg->dist_count++;
    return 0;
}

static int finalize_dist(struct config *cfg)
{
    cfg->total_weight = 0;
    long double weighted = 0.0;
    for (int i = 0; i < cfg->dist_count; i++) {
        cfg->total_weight += cfg->dist[i].weight;
        weighted += (long double) cfg->dist[i].size *
                    (long double) cfg->dist[i].weight;
    }
    if (cfg->total_weight == 0)
        return -1;
    cfg->avg_size = (double) (weighted / (long double) cfg->total_weight);
    return 0;
}

static int load_external_hist(struct config *cfg, const char *path)
{
    FILE *f = fopen(path, "r");
    if (!f) {
        fprintf(stderr, "failed to open histogram '%s': %s\n", path,
                strerror(errno));
        return -1;
    }
    char line[256];
    int lineno = 0;
    while (fgets(line, sizeof(line), f)) {
        lineno++;
        char *p = line;
        while (*p == ' ' || *p == '\t')
            p++;
        if (*p == '\0' || *p == '\n' || *p == '#')
            continue;
        unsigned long long size = 0;
        unsigned long long weight = 0;
        if (sscanf(p, "%llu %llu", &size, &weight) != 2 ||
            size == 0 || weight == 0 || weight > UINT32_MAX) {
            fprintf(stderr, "bad histogram line %d: %s", lineno, line);
            fclose(f);
            return -1;
        }
        if (add_bucket(cfg, (size_t) size, (uint32_t) weight) != 0) {
            fprintf(stderr, "too many histogram buckets or bad line %d\n", lineno);
            fclose(f);
            return -1;
        }
    }
    fclose(f);
    if (cfg->dist_count == 0) {
        fprintf(stderr, "empty histogram '%s'\n", path);
        return -1;
    }
    return finalize_dist(cfg);
}

static int set_profile(struct config *cfg, const char *name)
{
    cfg->dist_count = 0;
    cfg->total_weight = 0;
    cfg->external_path[0] = '\0';
    snprintf(cfg->profile, sizeof(cfg->profile), "%s", name);

    if (strcmp(name, "small-churn") == 0) {
        cfg->profile_kind = PROFILE_SMALL_CHURN;
        if (!cfg->live_set_overridden)
            cfg->live_set = 256;
        add_bucket(cfg, 16, 1);
        add_bucket(cfg, 32, 1);
        add_bucket(cfg, 64, 1);
        add_bucket(cfg, 128, 1);
        add_bucket(cfg, 256, 1);
    } else if (strcmp(name, "mixed") == 0 ||
               strcmp(name, "large-transient") == 0 ||
               strcmp(name, "thread-churn") == 0) {
        if (strcmp(name, "mixed") == 0)
            cfg->profile_kind = PROFILE_MIXED;
        else if (strcmp(name, "large-transient") == 0)
            cfg->profile_kind = PROFILE_LARGE_TRANSIENT;
        else
            cfg->profile_kind = PROFILE_THREAD_CHURN;
        if (!cfg->live_set_overridden)
            cfg->live_set = 4096;
        add_bucket(cfg, 16, 8);
        add_bucket(cfg, 64, 12);
        add_bucket(cfg, 256, 18);
        add_bucket(cfg, 1024, 24);
        add_bucket(cfg, 4096, 18);
        add_bucket(cfg, 16384, 12);
        add_bucket(cfg, 32768, 6);
        add_bucket(cfg, 65536, 2);
    } else if (strcmp(name, "burst-free-small") == 0) {
        cfg->profile_kind = PROFILE_BURST_FREE_SMALL;
        if (!cfg->live_set_overridden)
            cfg->live_set = 256;
        add_bucket(cfg, 16, 1);
        add_bucket(cfg, 24, 1);
        add_bucket(cfg, 32, 1);
        add_bucket(cfg, 40, 1);
        add_bucket(cfg, 48, 1);
        add_bucket(cfg, 56, 1);
        add_bucket(cfg, 64, 1);
    } else if (strcmp(name, "unsorted-drain") == 0) {
        cfg->profile_kind = PROFILE_UNSORTED_DRAIN;
        if (!cfg->live_set_overridden)
            cfg->live_set = 4096;
        add_bucket(cfg, 16, 8);
        add_bucket(cfg, 64, 12);
        add_bucket(cfg, 256, 18);
        add_bucket(cfg, 1024, 24);
        add_bucket(cfg, 4096, 18);
        add_bucket(cfg, 16384, 12);
        add_bucket(cfg, 32768, 6);
        add_bucket(cfg, 65536, 2);
    } else if (strncmp(name, "external:", 9) == 0) {
        cfg->profile_kind = PROFILE_EXTERNAL;
        if (!cfg->live_set_overridden)
            cfg->live_set = 4096;
        snprintf(cfg->external_path, sizeof(cfg->external_path), "%s", name + 9);
        return load_external_hist(cfg, cfg->external_path);
    } else {
        fprintf(stderr, "unknown profile '%s'\n", name);
        return -1;
    }

    return finalize_dist(cfg);
}

static void usage(FILE *out)
{
    fprintf(out,
            "usage: alloc_bench [options]\n"
            "  --profile NAME              small-churn|mixed|large-transient|thread-churn|burst-free-small|unsorted-drain|external:FILE\n"
            "  --threads N                 worker threads (default: online CPUs)\n"
            "  --seed N                    global seed (default: 1)\n"
            "  --warmup S                  warmup seconds (default: 5)\n"
            "  --duration S                measure seconds for duration mode (default: 30)\n"
            "  --idle S                    idle seconds (default: 10)\n"
            "  --ops-per-thread N          fixed-op measure mode; overrides --duration\n"
            "  --live-set N                live objects per thread\n"
            "  --churn-period-ms N         thread-churn generation period (default: 2000)\n"
            "  --stagger-churn             stagger thread-churn deadlines by thread ordinal\n"
            "  --touch-full                fully write-touch every allocation\n"
            "  --idle-release PCT          release PCT%% of live pool at idle entry (default: 0)\n"
            "  --release-order ORDER       high|low|random|interleave (default: high)\n"
            "  --idle-trim                 call malloc_trim(0) after idle release before idle\n"
            "  --post-trim-ops-per-thread N  unmeasured live-pool ops after trim\n"
            "  --burst-size N              burst-free-small burst pool size (default: 2048)\n"
            "  --burst-hold-ops N          burst-free-small hold ops (default: 4096)\n"
            "  --unsorted-batch N          unsorted-drain fill batch size (default: 4096)\n"
            "  --outdir DIR                malloc_info output dir (default: .)\n"
            "  --help\n");
}

static int parse_u64(const char *s, uint64_t *out)
{
    char *end = NULL;
    errno = 0;
    unsigned long long v = strtoull(s, &end, 0);
    if (errno || !end || *end != '\0')
        return -1;
    *out = (uint64_t) v;
    return 0;
}

static int parse_double_arg(const char *s, double *out)
{
    char *end = NULL;
    errno = 0;
    double v = strtod(s, &end);
    if (errno || !end || *end != '\0' || v < 0.0)
        return -1;
    *out = v;
    return 0;
}

static int set_release_order(struct config *cfg, const char *name)
{
    if (strcmp(name, "high") == 0)
        cfg->release_order = RELEASE_HIGH;
    else if (strcmp(name, "low") == 0)
        cfg->release_order = RELEASE_LOW;
    else if (strcmp(name, "random") == 0)
        cfg->release_order = RELEASE_RANDOM;
    else if (strcmp(name, "interleave") == 0)
        cfg->release_order = RELEASE_INTERLEAVE;
    else
        return -1;
    snprintf(cfg->release_order_name, sizeof(cfg->release_order_name),
             "%s", name);
    return 0;
}

static int parse_args(int argc, char **argv, struct config *cfg)
{
    memset(cfg, 0, sizeof(*cfg));
    long cpus = sysconf(_SC_NPROCESSORS_ONLN);
    cfg->threads = cpus > 0 ? (int) cpus : 1;
    cfg->seed = 1;
    cfg->warmup_s = 5.0;
    cfg->duration_s = 30.0;
    cfg->idle_s = 10.0;
    cfg->churn_period_ms = 2000;
    cfg->large_period_ops = 100;
    cfg->large_hold_ops = 100;
    cfg->burst_size = 2048;
    cfg->burst_hold_ops = 4096;
    cfg->unsorted_batch = 4096;
    set_release_order(cfg, "high");
    snprintf(cfg->outdir, sizeof(cfg->outdir), ".");

    const char *profile = "mixed";
    for (int i = 1; i < argc; i++) {
        const char *arg = argv[i];
        const char *val = NULL;
        if (strcmp(arg, "--help") == 0) {
            usage(stdout);
            exit(0);
        } else if (strcmp(arg, "--profile") == 0 && i + 1 < argc) {
            profile = argv[++i];
        } else if (strncmp(arg, "--profile=", 10) == 0) {
            profile = arg + 10;
        } else if (strcmp(arg, "--threads") == 0 && i + 1 < argc) {
            val = argv[++i];
            uint64_t x;
            if (parse_u64(val, &x) != 0 || x == 0 || x > 1024)
                return -1;
            cfg->threads = (int) x;
        } else if (strncmp(arg, "--threads=", 10) == 0) {
            val = arg + 10;
            uint64_t x;
            if (parse_u64(val, &x) != 0 || x == 0 || x > 1024)
                return -1;
            cfg->threads = (int) x;
        } else if (strcmp(arg, "--seed") == 0 && i + 1 < argc) {
            if (parse_u64(argv[++i], &cfg->seed) != 0)
                return -1;
        } else if (strncmp(arg, "--seed=", 7) == 0) {
            if (parse_u64(arg + 7, &cfg->seed) != 0)
                return -1;
        } else if (strcmp(arg, "--warmup") == 0 && i + 1 < argc) {
            if (parse_double_arg(argv[++i], &cfg->warmup_s) != 0)
                return -1;
        } else if (strncmp(arg, "--warmup=", 9) == 0) {
            if (parse_double_arg(arg + 9, &cfg->warmup_s) != 0)
                return -1;
        } else if (strcmp(arg, "--duration") == 0 && i + 1 < argc) {
            if (parse_double_arg(argv[++i], &cfg->duration_s) != 0)
                return -1;
        } else if (strncmp(arg, "--duration=", 11) == 0) {
            if (parse_double_arg(arg + 11, &cfg->duration_s) != 0)
                return -1;
        } else if (strcmp(arg, "--idle") == 0 && i + 1 < argc) {
            if (parse_double_arg(argv[++i], &cfg->idle_s) != 0)
                return -1;
        } else if (strncmp(arg, "--idle=", 7) == 0) {
            if (parse_double_arg(arg + 7, &cfg->idle_s) != 0)
                return -1;
        } else if (strcmp(arg, "--ops-per-thread") == 0 && i + 1 < argc) {
            if (parse_u64(argv[++i], &cfg->ops_per_thread) != 0 ||
                cfg->ops_per_thread == 0)
                return -1;
            cfg->use_ops_mode = 1;
        } else if (strncmp(arg, "--ops-per-thread=", 17) == 0) {
            if (parse_u64(arg + 17, &cfg->ops_per_thread) != 0 ||
                cfg->ops_per_thread == 0)
                return -1;
            cfg->use_ops_mode = 1;
        } else if (strcmp(arg, "--live-set") == 0 && i + 1 < argc) {
            uint64_t x;
            if (parse_u64(argv[++i], &x) != 0 || x == 0)
                return -1;
            cfg->live_set = (size_t) x;
            cfg->live_set_overridden = 1;
        } else if (strncmp(arg, "--live-set=", 11) == 0) {
            uint64_t x;
            if (parse_u64(arg + 11, &x) != 0 || x == 0)
                return -1;
            cfg->live_set = (size_t) x;
            cfg->live_set_overridden = 1;
        } else if (strcmp(arg, "--churn-period-ms") == 0 && i + 1 < argc) {
            uint64_t x;
            if (parse_u64(argv[++i], &x) != 0 || x > INT_MAX)
                return -1;
            cfg->churn_period_ms = (int) x;
        } else if (strncmp(arg, "--churn-period-ms=", 18) == 0) {
            uint64_t x;
            if (parse_u64(arg + 18, &x) != 0 || x > INT_MAX)
                return -1;
            cfg->churn_period_ms = (int) x;
        } else if (strcmp(arg, "--stagger-churn") == 0) {
            cfg->stagger_churn = 1;
        } else if (strcmp(arg, "--touch-full") == 0) {
            cfg->touch_full = 1;
        } else if (strcmp(arg, "--idle-trim") == 0) {
            cfg->idle_trim = 1;
        } else if (strcmp(arg, "--release-order") == 0 && i + 1 < argc) {
            if (set_release_order(cfg, argv[++i]) != 0)
                return -1;
        } else if (strncmp(arg, "--release-order=", 16) == 0) {
            if (set_release_order(cfg, arg + 16) != 0)
                return -1;
        } else if (strcmp(arg, "--post-trim-ops-per-thread") == 0 &&
                   i + 1 < argc) {
            if (parse_u64(argv[++i], &cfg->post_trim_ops_per_thread) != 0)
                return -1;
        } else if (strncmp(arg, "--post-trim-ops-per-thread=", 27) == 0) {
            if (parse_u64(arg + 27, &cfg->post_trim_ops_per_thread) != 0)
                return -1;
        } else if (strcmp(arg, "--idle-release") == 0 && i + 1 < argc) {
            uint64_t x;
            if (parse_u64(argv[++i], &x) != 0 || x > 100)
                return -1;
            cfg->idle_release_pct = (int) x;
        } else if (strncmp(arg, "--idle-release=", 15) == 0) {
            uint64_t x;
            if (parse_u64(arg + 15, &x) != 0 || x > 100)
                return -1;
            cfg->idle_release_pct = (int) x;
        } else if (strcmp(arg, "--burst-size") == 0 && i + 1 < argc) {
            uint64_t x;
            if (parse_u64(argv[++i], &x) != 0 || x < 2 ||
                x > (uint64_t) SIZE_MAX)
                return -1;
            cfg->burst_size = (size_t) x;
        } else if (strncmp(arg, "--burst-size=", 13) == 0) {
            uint64_t x;
            if (parse_u64(arg + 13, &x) != 0 || x < 2 ||
                x > (uint64_t) SIZE_MAX)
                return -1;
            cfg->burst_size = (size_t) x;
        } else if (strcmp(arg, "--burst-hold-ops") == 0 && i + 1 < argc) {
            if (parse_u64(argv[++i], &cfg->burst_hold_ops) != 0)
                return -1;
        } else if (strncmp(arg, "--burst-hold-ops=", 17) == 0) {
            if (parse_u64(arg + 17, &cfg->burst_hold_ops) != 0)
                return -1;
        } else if (strcmp(arg, "--unsorted-batch") == 0 && i + 1 < argc) {
            uint64_t x;
            if (parse_u64(argv[++i], &x) != 0 || x < 2 ||
                (x & 1U) || x > (uint64_t) SIZE_MAX)
                return -1;
            cfg->unsorted_batch = (size_t) x;
        } else if (strncmp(arg, "--unsorted-batch=", 17) == 0) {
            uint64_t x;
            if (parse_u64(arg + 17, &x) != 0 || x < 2 ||
                (x & 1U) || x > (uint64_t) SIZE_MAX)
                return -1;
            cfg->unsorted_batch = (size_t) x;
        } else if (strcmp(arg, "--outdir") == 0 && i + 1 < argc) {
            snprintf(cfg->outdir, sizeof(cfg->outdir), "%s", argv[++i]);
        } else if (strncmp(arg, "--outdir=", 9) == 0) {
            snprintf(cfg->outdir, sizeof(cfg->outdir), "%s", arg + 9);
        } else {
            fprintf(stderr, "unknown or incomplete option '%s'\n", arg);
            return -1;
        }
    }

    if (set_profile(cfg, profile) != 0)
        return -1;
    if (cfg->threads <= 0 || cfg->live_set == 0 ||
        cfg->live_set > SIZE_MAX / sizeof(struct release_entry) ||
        cfg->burst_size < 2 || cfg->unsorted_batch < 2 ||
        (cfg->unsorted_batch & 1U) ||
        (cfg->post_trim_ops_per_thread > 0 &&
         (!cfg->idle_trim || cfg->idle_release_pct == 0)))
        return -1;
    return 0;
}

static int read_smaps_rollup(struct mem_sample *sample)
{
    FILE *f = fopen("/proc/self/smaps_rollup", "r");
    if (!f)
        return -1;
    char line[256];
    sample->rss_kb = -1;
    sample->pss_kb = -1;
    while (fgets(line, sizeof(line), f)) {
        long v;
        if (sscanf(line, "Rss: %ld kB", &v) == 1)
            sample->rss_kb = v;
        else if (sscanf(line, "Pss: %ld kB", &v) == 1)
            sample->pss_kb = v;
    }
    fclose(f);
    return sample->rss_kb >= 0 && sample->pss_kb >= 0 ? 0 : -1;
}

static int mapping_is_anonymous(const char *name)
{
    size_t len = strlen(name);
    return len == 0 || (len >= 2 && name[0] == '[' && name[len - 1] == ']');
}

static void add_mapping_private_dirty(struct heap_sample *sample,
                                      unsigned long start,
                                      unsigned long end,
                                      const char *perms,
                                      const char *name,
                                      long private_dirty_kb)
{
    unsigned long length = end - start;
    if (strcmp(name, "[heap]") == 0 ||
        (strcmp(perms, "rw-p") == 0 && name[0] == '\0' &&
         start % 0x100000UL == 0 && length > 0 && length <= 0x100000UL)) {
        sample->glibc_heap_pd_kb += private_dirty_kb;
        sample->glibc_heap_segments++;
    } else if (perms[1] == 'w' && mapping_is_anonymous(name)) {
        sample->other_anon_pd_kb += private_dirty_kb;
    } else {
        sample->file_backed_pd_kb += private_dirty_kb;
    }
}

static int read_heap_sample(struct heap_sample *sample)
{
    FILE *f = fopen("/proc/self/smaps", "r");
    if (!f)
        return -1;
    memset(sample, 0, sizeof(*sample));
    char line[1024];
    unsigned long start = 0;
    unsigned long end = 0;
    char perms[5] = "";
    char name[PATH_MAX] = "";
    long private_dirty_kb = 0;
    int have_mapping = 0;

    while (fgets(line, sizeof(line), f)) {
        unsigned long new_start;
        unsigned long new_end;
        unsigned long offset;
        unsigned long inode;
        char new_perms[5];
        char device[32];
        int consumed = 0;
        long value;
        if (sscanf(line, "%lx-%lx %4s %lx %31s %lu %n",
                   &new_start, &new_end, new_perms, &offset,
                   device, &inode, &consumed) == 6) {
            if (have_mapping)
                add_mapping_private_dirty(sample, start, end, perms, name,
                                          private_dirty_kb);
            start = new_start;
            end = new_end;
            memcpy(perms, new_perms, sizeof(perms));
            char *mapping_name = line + consumed;
            while (*mapping_name == ' ' || *mapping_name == '\t')
                mapping_name++;
            size_t len = strcspn(mapping_name, "\r\n");
            if (len >= sizeof(name))
                len = sizeof(name) - 1;
            memcpy(name, mapping_name, len);
            name[len] = '\0';
            private_dirty_kb = 0;
            have_mapping = 1;
        } else if (have_mapping &&
                   sscanf(line, "Private_Dirty: %ld kB", &value) == 1) {
            private_dirty_kb = value;
        }
    }
    if (have_mapping)
        add_mapping_private_dirty(sample, start, end, perms, name,
                                  private_dirty_kb);
    int ok = !ferror(f);
    fclose(f);
    return ok ? 0 : -1;
}

static int read_fault_sample(struct fault_sample *sample)
{
    FILE *f = fopen("/proc/self/stat", "r");
    if (!f)
        return -1;
    char *line = NULL;
    size_t cap = 0;
    ssize_t len = getline(&line, &cap, f);
    fclose(f);
    if (len < 0) {
        free(line);
        return -1;
    }
    char *p = strrchr(line, ')');
    if (!p || p[1] != ' ') {
        free(line);
        return -1;
    }
    p += 2;
    char *save = NULL;
    char *tok = strtok_r(p, " ", &save);
    int field = 3;
    int have_minflt = 0;
    int have_majflt = 0;
    while (tok) {
        if (field == 10) {
            sample->minflt = strtoull(tok, NULL, 10);
            have_minflt = 1;
        } else if (field == 12) {
            sample->majflt = strtoull(tok, NULL, 10);
            have_majflt = 1;
            break;
        }
        tok = strtok_r(NULL, " ", &save);
        field++;
    }
    free(line);
    return have_minflt && have_majflt ? 0 : -1;
}

static long read_vmhwm_kb(void)
{
    FILE *f = fopen("/proc/self/status", "r");
    if (!f)
        return -1;
    char line[256];
    long hwm = -1;
    while (fgets(line, sizeof(line), f)) {
        if (sscanf(line, "VmHWM: %ld kB", &hwm) == 1)
            break;
    }
    fclose(f);
    return hwm;
}

static long median3_long(long a, long b, long c)
{
    if (a > b) {
        long t = a; a = b; b = t;
    }
    if (b > c) {
        long t = b; b = c; c = t;
    }
    if (a > b) {
        long t = a; a = b; b = t;
    }
    return b;
}

static void rss_series_add(struct rss_series *series)
{
    if (series->count >= MAX_RSS_SAMPLES) {
        series->skipped++;
        return;
    }
    struct mem_sample sample;
    if (read_smaps_rollup(&sample) != 0) {
        series->skipped++;
        return;
    }
    series->rss_kb[series->count++] = sample.rss_kb;
}

static long rss_series_percentile(const struct rss_series *series, double pct)
{
    if (series->count == 0)
        return -1;
    long tmp[MAX_RSS_SAMPLES];
    memcpy(tmp, series->rss_kb, series->count * sizeof(tmp[0]));
    for (size_t i = 1; i < series->count; i++) {
        long v = tmp[i];
        size_t j = i;
        while (j > 0 && tmp[j - 1] > v) {
            tmp[j] = tmp[j - 1];
            j--;
        }
        tmp[j] = v;
    }
    size_t rank = (size_t) ((pct / 100.0) * (double) (series->count - 1));
    if (rank >= series->count)
        rank = series->count - 1;
    return tmp[rank];
}

static long rss_series_max(const struct rss_series *series)
{
    if (series->count == 0)
        return -1;
    long max = series->rss_kb[0];
    for (size_t i = 1; i < series->count; i++) {
        if (series->rss_kb[i] > max)
            max = series->rss_kb[i];
    }
    return max;
}

static void sanitize_name(const char *in, char *out, size_t outsz)
{
    size_t j = 0;
    for (size_t i = 0; in[i] && j + 1 < outsz; i++) {
        char c = in[i];
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
            (c >= '0' && c <= '9') || c == '-' || c == '_')
            out[j++] = c;
        else
            out[j++] = '_';
    }
    out[j] = '\0';
}

static uint64_t parse_uint_attr(const char *tag, const char *attr)
{
    char pattern[64];
    if (snprintf(pattern, sizeof(pattern), " %s=\"", attr) >=
        (int) sizeof(pattern))
        return 0;
    const char *p = strstr(tag, pattern);
    if (!p)
        return 0;
    p += strlen(pattern);
    errno = 0;
    unsigned long long v = strtoull(p, NULL, 10);
    if (errno)
        return 0;
    return (uint64_t) v;
}

static void malloc_info_parse_stats(const char *xml,
                                    struct malloc_info_stats *stats)
{
    memset(stats, 0, sizeof(*stats));
    const char *p = xml;
    while ((p = strstr(p, "<total type=\"")) != NULL) {
        if (strncmp(p, "<total type=\"fast\"",
                    strlen("<total type=\"fast\"")) == 0)
            stats->fast_bytes = parse_uint_attr(p, "size");
        else if (strncmp(p, "<total type=\"rest\"",
                         strlen("<total type=\"rest\"")) == 0)
            stats->rest_bytes = parse_uint_attr(p, "size");
        p += 13;
    }
    p = xml;
    while ((p = strstr(p, "<unsorted ")) != NULL) {
        stats->unsorted_bytes += parse_uint_attr(p, "total");
        p += 10;
    }
    p = xml;
    while ((p = strstr(p, "<heap nr=\"")) != NULL) {
        stats->arena_count++;
        p += 10;
    }
}

static int dump_malloc_info_file(const struct config *cfg, const char *tag,
                                 char *path, size_t pathsz,
                                 struct malloc_info_stats *stats_out)
{
    char *buf = NULL;
    size_t len = 0;
    FILE *mem = open_memstream(&buf, &len);
    if (!mem)
        return -1;
    int rc = malloc_info(0, mem);
    if (fclose(mem) != 0)
        rc = -1;
    if (rc != 0) {
        free(buf);
        return -1;
    }

    if (stats_out)
        malloc_info_parse_stats(buf, stats_out);

    char safe[256];
    sanitize_name(cfg->profile, safe, sizeof(safe));
    char *tmp_path = NULL;
    if (asprintf(&tmp_path, "%s/malloc_info_%s_%ld_%s.xml",
                 cfg->outdir, safe, (long) getpid(), tag) < 0) {
        free(buf);
        return -1;
    }
    if (strlen(tmp_path) + 1 > pathsz) {
        free(tmp_path);
        free(buf);
        errno = ENAMETOOLONG;
        return -1;
    }
    memcpy(path, tmp_path, strlen(tmp_path) + 1);
    free(tmp_path);
    FILE *out = fopen(path, "wb");
    if (!out) {
        free(buf);
        return -1;
    }
    if (fwrite(buf, 1, len, out) != len) {
        fclose(out);
        free(buf);
        return -1;
    }
    fclose(out);
    free(buf);
    return 0;
}

static int start_slot(struct slot *slot, const struct config *cfg,
                      uint64_t remaining_ops)
{
    struct worker_arg *arg = malloc(sizeof(*arg));
    if (!arg)
        return -1;
    arg->cfg = cfg;
    arg->slot = slot;
    arg->seed = cfg->seed ^ (uint64_t) slot->ordinal;
    arg->start_hash = slot->accum.size_hash;
    arg->ops_limit = remaining_ops;
    atomic_store_int(&slot->measure_done, 0);
    atomic_store_int(&slot->idle_release_done, 0);
    atomic_store_int(&slot->post_trim_done, 0);
    atomic_store_int(&slot->exit_reason, 0);
    slot->generation++;
    if (pthread_create(&slot->thread, NULL, worker_main, arg) != 0) {
        free(arg);
        return -1;
    }
    slot->alive = 1;
    return 0;
}

static void join_slot(struct slot *slot, int merge)
{
    if (!slot->alive)
        return;
    void *ret = NULL;
    pthread_join(slot->thread, &ret);
    (void) ret;
    if (merge)
        stats_merge(&slot->accum, &slot->arg_stats);
    slot->alive = 0;
}

static int try_join_slot(struct slot *slot, int merge)
{
    if (!slot->alive)
        return 0;
    void *ret = NULL;
    int rc = pthread_tryjoin_np(slot->thread, &ret);
    if (rc == 0) {
        (void) ret;
        if (merge)
            stats_merge(&slot->accum, &slot->arg_stats);
        slot->alive = 0;
        return 1;
    }
    return 0;
}

static int manage_churn_slots(struct slot *slots, const struct config *cfg)
{
    if (cfg->profile_kind != PROFILE_THREAD_CHURN)
        return 0;
    for (int i = 0; i < cfg->threads; i++) {
        struct slot *slot = &slots[i];
        if (try_join_slot(slot, 1)) {
            if (atomic_load_int(&slot->exit_reason) == 2)
                return -1;
            int phase = atomic_load_int(&g_phase);
            if (phase == PHASE_WARMUP || phase == PHASE_MEASURE) {
                uint64_t remaining = 0;
                if (cfg->use_ops_mode) {
                    if (slot->accum.measure_ops >= cfg->ops_per_thread)
                        continue;
                    remaining = cfg->ops_per_thread - slot->accum.measure_ops;
                }
                if (start_slot(slot, cfg, remaining) != 0)
                    return -1;
            }
        }
    }
    return 0;
}

static int wait_idle_release(struct slot *slots, const struct config *cfg)
{
    for (;;) {
        int all_done = 1;
        for (int i = 0; i < cfg->threads; i++) {
            struct slot *slot = &slots[i];
            if (try_join_slot(slot, 1)) {
                if (atomic_load_int(&slot->exit_reason) == 2)
                    return -1;
            }
            if (slot->alive &&
                !atomic_load_int(&slot->idle_release_done)) {
                all_done = 0;
            }
        }
        if (all_done)
            return 0;
        usleep(1000);
    }
}

static int wait_post_trim(struct slot *slots, const struct config *cfg)
{
    for (;;) {
        int all_done = 1;
        for (int i = 0; i < cfg->threads; i++) {
            struct slot *slot = &slots[i];
            if (try_join_slot(slot, 1)) {
                if (atomic_load_int(&slot->exit_reason) == 2)
                    return -1;
            }
            if (slot->alive && !atomic_load_int(&slot->post_trim_done))
                all_done = 0;
        }
        if (all_done)
            return 0;
        usleep(1000);
    }
}

static int run_benchmark(const struct config *cfg, struct slot **slots_out,
                         double *measure_elapsed_out,
                         struct mem_sample measure_samples[3],
                         struct rss_series *periodic_rss,
                         struct mem_sample *idle_after_release_sample,
                         struct mem_sample *idle_sample,
                         long *vmhwm_kb,
                         char *malloc_measure_path,
                         size_t malloc_measure_pathsz,
                         char *malloc_idle_path,
                         size_t malloc_idle_pathsz,
                         uint64_t *idle_free_bytes_measure,
                         uint64_t *idle_free_bytes_idle,
                         int *idle_trim_ret,
                         struct extended_samples *extended)
{
    if (mkdir(cfg->outdir, 0777) != 0 && errno != EEXIST) {
        fprintf(stderr, "failed to create outdir '%s': %s\n", cfg->outdir,
                strerror(errno));
        return -1;
    }

    struct slot *slots = calloc((size_t) cfg->threads, sizeof(*slots));
    if (!slots)
        return -1;
    for (int i = 0; i < cfg->threads; i++) {
        slots[i].ordinal = i;
        stats_init(&slots[i].accum, FNV_OFFSET);
    }

    atomic_store_int(&g_phase, PHASE_WARMUP);
    for (int i = 0; i < cfg->threads; i++) {
        uint64_t limit = cfg->use_ops_mode ? cfg->ops_per_thread : 0;
        if (start_slot(&slots[i], cfg, limit) != 0) {
            fprintf(stderr, "pthread_create failed\n");
            atomic_store_int(&g_phase, PHASE_DONE);
            for (int j = 0; j < i; j++)
                join_slot(&slots[j], 0);
            free(slots);
            return -1;
        }
    }

    uint64_t warmup_end = now_ns() + (uint64_t) (cfg->warmup_s * 1000000000.0);
    while (now_ns() < warmup_end) {
        if (manage_churn_slots(slots, cfg) != 0)
            goto fail;
        usleep(1000);
    }

    uint64_t measure_start = now_ns();
    atomic_store_int(&g_phase, PHASE_MEASURE);
    uint64_t next_rss_sample = measure_start + 2000000000ULL;
    if (cfg->use_ops_mode) {
        int all_done = 0;
        while (!all_done) {
            if (manage_churn_slots(slots, cfg) != 0)
                goto fail;
            uint64_t tnow = now_ns();
            if (tnow >= next_rss_sample) {
                rss_series_add(periodic_rss);
                next_rss_sample = tnow + 2000000000ULL;
            }
            all_done = 1;
            for (int i = 0; i < cfg->threads; i++) {
                if (slots[i].alive &&
                    !atomic_load_int(&slots[i].measure_done)) {
                    all_done = 0;
                    break;
                }
                if (!slots[i].alive &&
                    slots[i].accum.measure_ops < cfg->ops_per_thread) {
                    all_done = 0;
                    break;
                }
            }
            usleep(1000);
        }
    } else {
        uint64_t measure_end =
            measure_start + (uint64_t) (cfg->duration_s * 1000000000.0);
        while (now_ns() < measure_end) {
            if (manage_churn_slots(slots, cfg) != 0)
                goto fail;
            uint64_t tnow = now_ns();
            if (tnow >= next_rss_sample) {
                rss_series_add(periodic_rss);
                next_rss_sample = tnow + 2000000000ULL;
            }
            usleep(1000);
        }
    }
    uint64_t measure_end_actual = now_ns();
    *measure_elapsed_out =
        (double) (measure_end_actual - measure_start) / 1000000000.0;
    atomic_store_int(&g_phase, PHASE_IDLE);

    for (int i = 0; i < 3; i++) {
        if (read_smaps_rollup(&measure_samples[i]) != 0) {
            measure_samples[i].rss_kb = -1;
            measure_samples[i].pss_kb = -1;
        }
        if (i != 2)
            usleep(100000);
    }
    if (dump_malloc_info_file(cfg, "measure", malloc_measure_path,
                              malloc_measure_pathsz,
                              &extended->measure_mi) != 0) {
        fprintf(stderr, "malloc_info measure dump failed: %s\n", strerror(errno));
        goto fail;
    }
    *idle_free_bytes_measure = extended->measure_mi.fast_bytes +
        extended->measure_mi.rest_bytes;

    if (cfg->idle_release_pct > 0) {
        atomic_store_int(&g_phase, PHASE_IDLE_RELEASE);
        if (wait_idle_release(slots, cfg) != 0)
            goto fail;
        for (int i = 0; i < cfg->threads; i++) {
            extended->released_bytes += slots[i].idle_released_bytes;
            extended->released_objects += slots[i].idle_released_objects;
        }
        if (dump_malloc_info_file(cfg, "release",
                                  extended->malloc_release_path,
                                  sizeof(extended->malloc_release_path),
                                  &extended->release_mi) != 0) {
            fprintf(stderr, "malloc_info release dump failed: %s\n",
                    strerror(errno));
            goto fail;
        }
        if (read_smaps_rollup(idle_after_release_sample) != 0) {
            idle_after_release_sample->rss_kb = -1;
            idle_after_release_sample->pss_kb = -1;
        }
        if (read_heap_sample(&extended->pretrim_heap) != 0 ||
            read_fault_sample(&extended->pretrim_faults) != 0) {
            fprintf(stderr, "pretrim /proc sampling failed: %s\n",
                    strerror(errno));
            goto fail;
        }
        if (cfg->idle_trim) {
            uint64_t trim_start = now_ns();
            if (idle_trim_ret) {
                *idle_trim_ret = malloc_trim(0);
                extended->trim_elapsed_ns = now_ns() - trim_start;
            }
        }
        if (read_heap_sample(&extended->posttrim_heap) != 0 ||
            dump_malloc_info_file(cfg, "posttrim",
                                  extended->malloc_posttrim_path,
                                  sizeof(extended->malloc_posttrim_path),
                                  &extended->posttrim_mi) != 0 ||
            read_fault_sample(&extended->posttrim_faults) != 0) {
            fprintf(stderr, "posttrim sampling failed: %s\n", strerror(errno));
            goto fail;
        }
        if (cfg->post_trim_ops_per_thread > 0) {
            uint64_t post_trim_start = now_ns();
            atomic_store_int(&g_phase, PHASE_REFAULT);
            if (wait_post_trim(slots, cfg) != 0)
                goto fail;
            extended->post_trim_elapsed_ns = now_ns() - post_trim_start;
            if (read_heap_sample(&extended->postrefault_heap) != 0 ||
                read_fault_sample(&extended->postrefault_faults) != 0) {
                fprintf(stderr, "postrefault sampling failed: %s\n",
                        strerror(errno));
                goto fail;
            }
            atomic_store_int(&g_phase, PHASE_IDLE);
        } else {
            extended->postrefault_heap = extended->posttrim_heap;
            extended->postrefault_faults = extended->posttrim_faults;
        }
    } else {
        *idle_after_release_sample = measure_samples[2];
    }

    sleep_seconds(cfg->idle_s);
    if (read_smaps_rollup(idle_sample) != 0) {
        idle_sample->rss_kb = -1;
        idle_sample->pss_kb = -1;
    }
    if (dump_malloc_info_file(cfg, "idle", malloc_idle_path,
                              malloc_idle_pathsz,
                              &extended->idle_mi) != 0) {
        fprintf(stderr, "malloc_info idle dump failed: %s\n", strerror(errno));
        goto fail;
    }
    *idle_free_bytes_idle = extended->idle_mi.fast_bytes +
        extended->idle_mi.rest_bytes;
    *vmhwm_kb = read_vmhwm_kb();

    atomic_store_int(&g_phase, PHASE_DONE);
    for (int i = 0; i < cfg->threads; i++) {
        join_slot(&slots[i], 1);
        if (atomic_load_int(&slots[i].exit_reason) == 2) {
            fprintf(stderr, "worker allocation failure\n");
            free(slots);
            return -1;
        }
    }
    *slots_out = slots;
    return 0;

fail:
    atomic_store_int(&g_phase, PHASE_DONE);
    for (int i = 0; i < cfg->threads; i++)
        join_slot(&slots[i], 1);
    free(slots);
    return -1;
}

static void json_string(FILE *out, const char *s)
{
    fputc('"', out);
    for (; *s; s++) {
        unsigned char c = (unsigned char) *s;
        switch (c) {
        case '"':
            fputs("\\\"", out);
            break;
        case '\\':
            fputs("\\\\", out);
            break;
        case '\b':
            fputs("\\b", out);
            break;
        case '\f':
            fputs("\\f", out);
            break;
        case '\n':
            fputs("\\n", out);
            break;
        case '\r':
            fputs("\\r", out);
            break;
        case '\t':
            fputs("\\t", out);
            break;
        default:
            if (c < 0x20)
                fprintf(out, "\\u%04x", c);
            else
                fputc(c, out);
        }
    }
    fputc('"', out);
}

static void print_json(const struct config *cfg, const struct slot *slots,
                       double measure_elapsed,
                       const struct mem_sample measure_samples[3],
                       const struct rss_series *periodic_rss,
                       const struct mem_sample *idle_after_release_sample,
                       const struct mem_sample *idle_sample,
                       long vmhwm_kb,
                       const char *malloc_measure_path,
                       const char *malloc_idle_path,
                       uint64_t idle_free_bytes_measure,
                       uint64_t idle_free_bytes_idle,
                       int idle_trim_ret,
                       const struct extended_samples *extended)
{
    uint64_t total_ops = 0;
    uint64_t total_hist[LAT_BUCKETS];
    memset(total_hist, 0, sizeof(total_hist));
    for (int i = 0; i < cfg->threads; i++) {
        total_ops += slots[i].accum.measure_ops;
        for (int b = 0; b < LAT_BUCKETS; b++)
            total_hist[b] += slots[i].accum.latency_hist[b];
    }

    uint64_t latency_samples = 0;
    for (int i = 0; i < LAT_BUCKETS; i++)
        latency_samples += total_hist[i];

    long rss_median = median3_long(measure_samples[0].rss_kb,
                                   measure_samples[1].rss_kb,
                                   measure_samples[2].rss_kb);
    long pss_median = median3_long(measure_samples[0].pss_kb,
                                   measure_samples[1].pss_kb,
                                   measure_samples[2].pss_kb);
    double theoretical_live_kb =
        ((double) cfg->threads * (double) cfg->live_set * cfg->avg_size) / 1024.0;
    double theoretical_release_kb = theoretical_live_kb *
        (double) cfg->idle_release_pct / 100.0;
    double throughput = measure_elapsed > 0.0 ?
        (double) total_ops / measure_elapsed : 0.0;

    fputc('{', stdout);
    fputs("\"schema\":\"alloc_bench_v1_1\",", stdout);
    fputs("\"profile\":", stdout); json_string(stdout, cfg->profile); fputc(',', stdout);
    fputs("\"mode\":", stdout);
    json_string(stdout, cfg->use_ops_mode ? "ops" : "duration");
    fprintf(stdout,
            ",\"threads\":%d,\"seed\":%" PRIu64
            ",\"warmup_s\":%.6f,\"duration_s\":%.6f,\"idle_s\":%.6f"
            ",\"ops_per_thread\":%" PRIu64
            ",\"live_set_per_thread\":%zu"
            ",\"churn_period_ms\":%d"
            ",\"stagger_churn\":%s"
            ",\"large_period_ops\":%d,\"large_hold_ops\":%d"
            ",\"burst_size\":%zu,\"burst_hold_ops\":%" PRIu64
            ",\"unsorted_batch\":%zu"
            ",\"background_live_ops\":%d,\"background_phase_ops\":%d"
            ",\"idle_release_pct\":%d"
            ",\"release_order\":\"%s\""
            ",\"idle_trim\":%s,\"idle_trim_ret\":%d"
            ",\"post_trim_ops_per_thread\":%" PRIu64
            ",\"idle_released_objects\":%" PRIu64
            ",\"idle_released_bytes\":%" PRIu64
            ",\"idle_free_bytes_measure\":%" PRIu64
            ",\"idle_free_bytes_idle\":%" PRIu64
            ",\"avg_size_bytes\":%.3f,\"theoretical_live_kb\":%.3f"
            ",\"theoretical_release_kb\":%.3f,",
            cfg->threads, cfg->seed, cfg->warmup_s, cfg->duration_s,
            cfg->idle_s, cfg->ops_per_thread, cfg->live_set,
            cfg->churn_period_ms, cfg->stagger_churn ? "true" : "false",
            cfg->large_period_ops, cfg->large_hold_ops,
            cfg->burst_size, cfg->burst_hold_ops, cfg->unsorted_batch,
            BACKGROUND_LIVE_OPS, BACKGROUND_PHASE_OPS,
            cfg->idle_release_pct, cfg->release_order_name,
            (cfg->idle_trim && cfg->idle_release_pct > 0) ? "true" : "false",
            idle_trim_ret, cfg->post_trim_ops_per_thread,
            extended->released_objects, extended->released_bytes,
            idle_free_bytes_measure, idle_free_bytes_idle,
            cfg->avg_size, theoretical_live_kb, theoretical_release_kb);
    fputs("\"touch_policy\":", stdout);
    json_string(stdout, cfg->touch_full ? "full" : "ge128k_full_else_edge64");
    fputc(',', stdout);

    fputs("\"histogram\":[", stdout);
    for (int i = 0; i < cfg->dist_count; i++) {
        if (i)
            fputc(',', stdout);
        fprintf(stdout, "{\"size\":%zu,\"weight\":%u}",
                cfg->dist[i].size, cfg->dist[i].weight);
    }
    fputs("],", stdout);

    fprintf(stdout,
            "\"measure_elapsed_s\":%.9f,\"measure_ops\":%" PRIu64
            ",\"throughput_ops_per_s\":%.3f,",
            measure_elapsed, total_ops, throughput);

    fputs("\"thread_ops\":[", stdout);
    for (int i = 0; i < cfg->threads; i++) {
        if (i)
            fputc(',', stdout);
        fprintf(stdout, "%" PRIu64, slots[i].accum.measure_ops);
    }
    fputs("],\"thread_size_hash\":[", stdout);
    for (int i = 0; i < cfg->threads; i++) {
        if (i)
            fputc(',', stdout);
        fprintf(stdout, "\"%016" PRIx64 "\"", slots[i].accum.size_hash);
    }
    fputs("],\"op_hash_fn\":\"fnv1a64_size_sequence\",", stdout);

    fprintf(stdout,
            "\"latency_ns\":{\"sample_every\":64,\"samples\":%" PRIu64
            ",\"p50\":%" PRIu64 ",\"p99\":%" PRIu64 ",\"bucket_bounds\":[",
            latency_samples, hist_percentile(total_hist, 50.0),
            hist_percentile(total_hist, 99.0));
    for (int i = 0; i <= LAT_BUCKETS; i++) {
        if (i)
            fputc(',', stdout);
        fprintf(stdout, "%" PRIu64, latency_bounds[i]);
    }
    fputs("],\"hist\":[", stdout);
    for (int i = 0; i < LAT_BUCKETS; i++) {
        if (i)
            fputc(',', stdout);
        fprintf(stdout, "%" PRIu64, total_hist[i]);
    }
    fputs("]},", stdout);

    fprintf(stdout,
            "\"memory\":{\"measure_rss_kb_samples\":[%ld,%ld,%ld],"
            "\"measure_pss_kb_samples\":[%ld,%ld,%ld],"
            "\"measure_rss_kb_median\":%ld,"
            "\"measure_pss_kb_median\":%ld,"
            "\"measure_rss_kb_p50\":%ld,"
            "\"measure_rss_kb_p95\":%ld,"
            "\"measure_rss_kb_max\":%ld,"
            "\"measure_rss_kb_n_samples\":%zu,"
            "\"measure_rss_kb_sample_failures\":%" PRIu64 ","
            "\"idle_release_pct\":%d,"
            "\"idle_rss_kb_after_release\":%ld,"
            "\"idle_pss_kb_after_release\":%ld,"
            "\"idle_rss_kb\":%ld,\"idle_pss_kb\":%ld,"
            "\"vmhwm_kb\":%ld,"
            "\"glibc_heap_pd_kb_pretrim\":%ld,"
            "\"glibc_heap_pd_kb_posttrim\":%ld,"
            "\"glibc_heap_pd_kb_postrefault\":%ld,"
            "\"other_anon_pd_kb_pretrim\":%ld,"
            "\"other_anon_pd_kb_posttrim\":%ld,"
            "\"file_backed_pd_kb_pretrim\":%ld,"
            "\"file_backed_pd_kb_posttrim\":%ld,"
            "\"glibc_heap_segments_pretrim\":%" PRIu64 ",",
            measure_samples[0].rss_kb, measure_samples[1].rss_kb,
            measure_samples[2].rss_kb, measure_samples[0].pss_kb,
            measure_samples[1].pss_kb, measure_samples[2].pss_kb,
            rss_median, pss_median,
            rss_series_percentile(periodic_rss, 50.0),
            rss_series_percentile(periodic_rss, 95.0),
            rss_series_max(periodic_rss), periodic_rss->count,
            periodic_rss->skipped, cfg->idle_release_pct,
            idle_after_release_sample->rss_kb,
            idle_after_release_sample->pss_kb,
            idle_sample->rss_kb, idle_sample->pss_kb,
            vmhwm_kb,
            extended->pretrim_heap.glibc_heap_pd_kb,
            extended->posttrim_heap.glibc_heap_pd_kb,
            extended->postrefault_heap.glibc_heap_pd_kb,
            extended->pretrim_heap.other_anon_pd_kb,
            extended->posttrim_heap.other_anon_pd_kb,
            extended->pretrim_heap.file_backed_pd_kb,
            extended->posttrim_heap.file_backed_pd_kb,
            extended->pretrim_heap.glibc_heap_segments);
    fputs("\"malloc_info_measure\":", stdout);
    json_string(stdout, malloc_measure_path);
    fputs(",\"malloc_info_release\":", stdout);
    json_string(stdout, extended->malloc_release_path);
    fputs(",\"malloc_info_posttrim\":", stdout);
    json_string(stdout, extended->malloc_posttrim_path);
    fputs(",\"malloc_info_idle\":", stdout);
    json_string(stdout, malloc_idle_path);
    fprintf(stdout,
            ",\"malloc_info_stats\":{"
            "\"measure\":{\"fast_bytes\":%" PRIu64
            ",\"rest_bytes\":%" PRIu64 ",\"unsorted_bytes\":%" PRIu64
            ",\"arena_count\":%" PRIu64 "},"
            "\"release\":{\"fast_bytes\":%" PRIu64
            ",\"rest_bytes\":%" PRIu64 ",\"unsorted_bytes\":%" PRIu64
            ",\"arena_count\":%" PRIu64 "},"
            "\"posttrim\":{\"fast_bytes\":%" PRIu64
            ",\"rest_bytes\":%" PRIu64 ",\"unsorted_bytes\":%" PRIu64
            ",\"arena_count\":%" PRIu64 "},"
            "\"idle\":{\"fast_bytes\":%" PRIu64
            ",\"rest_bytes\":%" PRIu64 ",\"unsorted_bytes\":%" PRIu64
            ",\"arena_count\":%" PRIu64 "}},"
            "\"trim_elapsed_ns\":%" PRIu64 ","
            "\"post_trim_elapsed_ns\":%" PRIu64 ","
            "\"faults\":{\"minflt_pretrim\":%" PRIu64
            ",\"majflt_pretrim\":%" PRIu64
            ",\"minflt_posttrim\":%" PRIu64
            ",\"majflt_posttrim\":%" PRIu64
            ",\"minflt_postrefault\":%" PRIu64
            ",\"majflt_postrefault\":%" PRIu64 "}}}",
            extended->measure_mi.fast_bytes,
            extended->measure_mi.rest_bytes,
            extended->measure_mi.unsorted_bytes,
            extended->measure_mi.arena_count,
            extended->release_mi.fast_bytes,
            extended->release_mi.rest_bytes,
            extended->release_mi.unsorted_bytes,
            extended->release_mi.arena_count,
            extended->posttrim_mi.fast_bytes,
            extended->posttrim_mi.rest_bytes,
            extended->posttrim_mi.unsorted_bytes,
            extended->posttrim_mi.arena_count,
            extended->idle_mi.fast_bytes,
            extended->idle_mi.rest_bytes,
            extended->idle_mi.unsorted_bytes,
            extended->idle_mi.arena_count,
            extended->trim_elapsed_ns, extended->post_trim_elapsed_ns,
            extended->pretrim_faults.minflt,
            extended->pretrim_faults.majflt,
            extended->posttrim_faults.minflt,
            extended->posttrim_faults.majflt,
            extended->postrefault_faults.minflt,
            extended->postrefault_faults.majflt);
    fputc('\n', stdout);
}

int main(int argc, char **argv)
{
    struct config cfg;
    if (parse_args(argc, argv, &cfg) != 0) {
        usage(stderr);
        return 2;
    }

    struct slot *slots = NULL;
    double measure_elapsed = 0.0;
    struct mem_sample measure_samples[3];
    struct rss_series periodic_rss;
    struct mem_sample idle_after_release_sample;
    struct mem_sample idle_sample;
    long vmhwm_kb = -1;
    uint64_t idle_free_bytes_measure = 0;
    uint64_t idle_free_bytes_idle = 0;
    int idle_trim_ret = -1;
    struct extended_samples extended;
    char malloc_measure_path[PATH_MAX];
    char malloc_idle_path[PATH_MAX];
    memset(measure_samples, 0, sizeof(measure_samples));
    memset(&periodic_rss, 0, sizeof(periodic_rss));
    memset(&idle_after_release_sample, 0, sizeof(idle_after_release_sample));
    memset(&idle_sample, 0, sizeof(idle_sample));
    memset(&extended, 0, sizeof(extended));
    malloc_measure_path[0] = '\0';
    malloc_idle_path[0] = '\0';

    if (run_benchmark(&cfg, &slots, &measure_elapsed, measure_samples,
                      &periodic_rss, &idle_after_release_sample,
                      &idle_sample, &vmhwm_kb, malloc_measure_path,
                      sizeof(malloc_measure_path), malloc_idle_path,
                      sizeof(malloc_idle_path), &idle_free_bytes_measure,
                      &idle_free_bytes_idle, &idle_trim_ret,
                      &extended) != 0) {
        free(slots);
        return 1;
    }

    print_json(&cfg, slots, measure_elapsed, measure_samples, &periodic_rss,
               &idle_after_release_sample, &idle_sample, vmhwm_kb,
               malloc_measure_path, malloc_idle_path,
               idle_free_bytes_measure, idle_free_bytes_idle,
               idle_trim_ret, &extended);
    free(slots);
    return 0;
}
