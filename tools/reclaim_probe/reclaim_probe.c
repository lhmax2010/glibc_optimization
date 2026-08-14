#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/uio.h>
#include <unistd.h>

#ifndef MADV_PAGEOUT
#define MADV_PAGEOUT 21
#endif

enum mapping_class {
    CLASS_GLIBC_HEAP = 0,
    CLASS_OTHER_ANON,
    CLASS_FILE_BACKED,
    CLASS_COUNT
};

struct mapping {
    uintptr_t start;
    uintptr_t end;
    char perms[5];
    char *name;
    uint64_t rss_bytes;
    uint64_t private_dirty_bytes;
    enum mapping_class class_id;
};

struct mapping_list {
    struct mapping *items;
    size_t len;
    size_t cap;
};

struct class_totals {
    uint64_t segments;
    uint64_t virtual_bytes;
    uint64_t rss_bytes;
    uint64_t private_dirty_bytes;
};

static void usage(FILE *stream)
{
    fprintf(stream,
            "usage:\n"
            "  reclaim_probe profile <pid>\n"
            "  reclaim_probe pageout <pid> <glibc-heap|other-anon|all-anon>\n");
}

static int parse_pid(const char *text, pid_t *pid_out)
{
    char *end = NULL;
    long value;

    errno = 0;
    value = strtol(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || value <= 0
        || value > INT_MAX) {
        return -1;
    }
    *pid_out = (pid_t) value;
    return 0;
}

static char *trim_mapping_name(char *name)
{
    char *end;

    while (*name == ' ' || *name == '\t') {
        name++;
    }
    end = name + strlen(name);
    while (end > name && (end[-1] == '\n' || end[-1] == '\r'
                           || end[-1] == ' ' || end[-1] == '\t')) {
        *--end = '\0';
    }
    return name;
}

static bool is_anonymous_name(const char *name)
{
    size_t len;

    if (name[0] == '\0') {
        return true;
    }
    len = strlen(name);
    return len >= 2 && name[0] == '[' && name[len - 1] == ']';
}

static enum mapping_class classify_mapping(uintptr_t start, uintptr_t end,
                                            const char perms[5],
                                            const char *name)
{
    uintptr_t length = end - start;

    if (strcmp(name, "[heap]") == 0) {
        return CLASS_GLIBC_HEAP;
    }
    if (strcmp(perms, "rw-p") == 0 && name[0] == '\0'
        && start % UINT32_C(0x100000) == 0 && length > 0
        && length <= UINT32_C(0x100000)) {
        return CLASS_GLIBC_HEAP;
    }
    if (perms[1] == 'w' && is_anonymous_name(name)) {
        return CLASS_OTHER_ANON;
    }
    return CLASS_FILE_BACKED;
}

static void free_mapping_list(struct mapping_list *list)
{
    size_t i;

    for (i = 0; i < list->len; i++) {
        free(list->items[i].name);
    }
    free(list->items);
    list->items = NULL;
    list->len = 0;
    list->cap = 0;
}

static int append_mapping(struct mapping_list *list, const struct mapping *item)
{
    struct mapping *new_items;
    size_t new_cap;

    if (list->len == list->cap) {
        new_cap = list->cap == 0 ? 128 : list->cap * 2;
        if (new_cap < list->cap
            || new_cap > SIZE_MAX / sizeof(*list->items)) {
            errno = ENOMEM;
            return -1;
        }
        new_items = realloc(list->items, new_cap * sizeof(*list->items));
        if (new_items == NULL) {
            return -1;
        }
        list->items = new_items;
        list->cap = new_cap;
    }
    list->items[list->len++] = *item;
    return 0;
}

static int finish_mapping(struct mapping_list *list, struct mapping *current,
                          bool *have_current)
{
    if (!*have_current) {
        return 0;
    }
    current->class_id = classify_mapping(current->start, current->end,
                                         current->perms, current->name);
    if (append_mapping(list, current) != 0) {
        free(current->name);
        current->name = NULL;
        return -1;
    }
    memset(current, 0, sizeof(*current));
    *have_current = false;
    return 0;
}

static int parse_smaps(pid_t pid, struct mapping_list *list, char *path,
                       size_t path_size)
{
    FILE *stream;
    char *line = NULL;
    size_t line_cap = 0;
    ssize_t line_len;
    struct mapping current = {0};
    bool have_current = false;
    int result = -1;

    if (snprintf(path, path_size, "/proc/%ld/smaps", (long) pid)
        >= (int) path_size) {
        errno = ENAMETOOLONG;
        return -1;
    }
    stream = fopen(path, "re");
    if (stream == NULL) {
        return -1;
    }

    while ((line_len = getline(&line, &line_cap, stream)) >= 0) {
        unsigned long start;
        unsigned long end;
        unsigned long offset;
        unsigned long inode;
        char perms[5];
        char device[32];
        int consumed = 0;
        uint64_t value_kb;

        (void) line_len;
        if (sscanf(line, "%lx-%lx %4s %lx %31s %lu %n", &start, &end,
                   perms, &offset, device, &inode, &consumed) == 6) {
            char *name;

            (void) offset;
            (void) inode;
            if (finish_mapping(list, &current, &have_current) != 0) {
                goto out;
            }
            name = strdup(trim_mapping_name(line + consumed));
            if (name == NULL) {
                goto out;
            }
            current.start = (uintptr_t) start;
            current.end = (uintptr_t) end;
            memcpy(current.perms, perms, sizeof(current.perms));
            current.name = name;
            have_current = true;
        } else if (have_current
                   && sscanf(line, "Rss: %" SCNu64 " kB", &value_kb) == 1) {
            current.rss_bytes = value_kb * UINT64_C(1024);
        } else if (have_current
                   && sscanf(line, "Private_Dirty: %" SCNu64 " kB",
                             &value_kb) == 1) {
            current.private_dirty_bytes = value_kb * UINT64_C(1024);
        }
    }
    if (ferror(stream)) {
        goto out;
    }
    if (finish_mapping(list, &current, &have_current) != 0) {
        goto out;
    }
    result = 0;

out:
    if (have_current) {
        free(current.name);
    }
    free(line);
    if (fclose(stream) != 0 && result == 0) {
        result = -1;
    }
    return result;
}

static const char *class_name(enum mapping_class class_id)
{
    static const char *const names[CLASS_COUNT] = {
        "glibc-heap", "other-anon", "file-backed"
    };

    return names[class_id];
}

static void collect_totals(const struct mapping_list *list,
                           struct class_totals totals[CLASS_COUNT])
{
    size_t i;

    memset(totals, 0, CLASS_COUNT * sizeof(*totals));
    for (i = 0; i < list->len; i++) {
        const struct mapping *mapping = &list->items[i];
        struct class_totals *total = &totals[mapping->class_id];

        total->segments++;
        total->virtual_bytes += mapping->end - mapping->start;
        total->rss_bytes += mapping->rss_bytes;
        total->private_dirty_bytes += mapping->private_dirty_bytes;
    }
}

static int command_profile(pid_t pid)
{
    struct mapping_list list = {0};
    struct class_totals totals[CLASS_COUNT];
    char path[64];
    int i;

    if (parse_smaps(pid, &list, path, sizeof(path)) != 0) {
        fprintf(stderr, "cannot parse %s: %s\n", path, strerror(errno));
        free_mapping_list(&list);
        return 1;
    }
    collect_totals(&list, totals);

    printf("{\"schema\":\"reclaim_probe.v1\",\"command\":\"profile\","
           "\"pid\":%ld,\"classes\":{", (long) pid);
    for (i = 0; i < CLASS_COUNT; i++) {
        printf("%s\"%s\":{\"segments\":%" PRIu64
               ",\"virtual_bytes\":%" PRIu64
               ",\"rss_bytes\":%" PRIu64
               ",\"private_dirty_bytes\":%" PRIu64 "}",
               i == 0 ? "" : ",", class_name((enum mapping_class) i),
               totals[i].segments, totals[i].virtual_bytes,
               totals[i].rss_bytes, totals[i].private_dirty_bytes);
    }
    printf("},\"total\":{\"segments\":%zu,\"rss_bytes\":%" PRIu64
           ",\"private_dirty_bytes\":%" PRIu64 "}}\n",
           list.len,
           totals[CLASS_GLIBC_HEAP].rss_bytes
               + totals[CLASS_OTHER_ANON].rss_bytes
               + totals[CLASS_FILE_BACKED].rss_bytes,
           totals[CLASS_GLIBC_HEAP].private_dirty_bytes
               + totals[CLASS_OTHER_ANON].private_dirty_bytes
               + totals[CLASS_FILE_BACKED].private_dirty_bytes);
    free_mapping_list(&list);
    return 0;
}

static int call_pidfd_open(pid_t pid)
{
#if defined(SYS_pidfd_open)
    return (int) syscall(SYS_pidfd_open, pid, 0U);
#elif defined(__NR_pidfd_open)
    return (int) syscall(__NR_pidfd_open, pid, 0U);
#else
    (void) pid;
    errno = ENOSYS;
    return -1;
#endif
}

static ssize_t call_process_madvise(int pidfd, const struct iovec *iov,
                                    size_t iov_count)
{
#if defined(SYS_process_madvise)
    return syscall(SYS_process_madvise, pidfd, iov, iov_count,
                   MADV_PAGEOUT, 0U);
#elif defined(__NR_process_madvise)
    return syscall(__NR_process_madvise, pidfd, iov, iov_count,
                   MADV_PAGEOUT, 0U);
#else
    (void) pidfd;
    (void) iov;
    (void) iov_count;
    errno = ENOSYS;
    return -1;
#endif
}

static bool mapping_selected(const struct mapping *mapping,
                             const char *selection)
{
    if (strcmp(selection, "glibc-heap") == 0) {
        return mapping->class_id == CLASS_GLIBC_HEAP;
    }
    if (strcmp(selection, "other-anon") == 0) {
        return mapping->class_id == CLASS_OTHER_ANON;
    }
    return mapping->class_id == CLASS_GLIBC_HEAP
           || mapping->class_id == CLASS_OTHER_ANON;
}

static int command_pageout(pid_t pid, const char *selection)
{
    struct mapping_list list = {0};
    char path[64];
    int pidfd;
    size_t i;
    uint64_t selected_segments = 0;
    uint64_t selected_bytes = 0;
    uint64_t attempted_calls = 0;
    uint64_t successful_calls = 0;
    uint64_t successful_bytes = 0;
    ssize_t last_return = 0;
    int first_errno = 0;

    if (parse_smaps(pid, &list, path, sizeof(path)) != 0) {
        fprintf(stderr, "cannot parse %s: %s\n", path, strerror(errno));
        free_mapping_list(&list);
        return 1;
    }
    pidfd = call_pidfd_open(pid);
    if (pidfd < 0) {
        int saved_errno = errno;

        printf("{\"schema\":\"reclaim_probe.v1\",\"command\":\"pageout\","
               "\"pid\":%ld,\"class\":\"%s\",\"return_value\":-1,"
               "\"successful_bytes\":0,\"errno\":%d,\"error\":\"%s\"}\n",
               (long) pid, selection, saved_errno, strerror(saved_errno));
        free_mapping_list(&list);
        return 1;
    }

    for (i = 0; i < list.len; i++) {
        const struct mapping *mapping = &list.items[i];
        struct iovec iov;
        size_t length;

        if (!mapping_selected(mapping, selection)) {
            continue;
        }
        length = mapping->end - mapping->start;
        if (length == 0) {
            continue;
        }
        selected_segments++;
        selected_bytes += length;
        iov.iov_base = (void *) mapping->start;
        iov.iov_len = length;
        attempted_calls++;
        errno = 0;
        last_return = call_process_madvise(pidfd, &iov, 1);
        if (last_return >= 0) {
            successful_calls++;
            successful_bytes += (uint64_t) last_return;
        } else if (first_errno == 0) {
            first_errno = errno;
        }
    }

    if (close(pidfd) != 0 && first_errno == 0) {
        first_errno = errno;
    }
    printf("{\"schema\":\"reclaim_probe.v1\",\"command\":\"pageout\","
           "\"pid\":%ld,\"class\":\"%s\","
           "\"selected_segments\":%" PRIu64
           ",\"selected_bytes\":%" PRIu64
           ",\"calls_attempted\":%" PRIu64
           ",\"calls_succeeded\":%" PRIu64
           ",\"return_value\":%zd,\"successful_bytes\":%" PRIu64
           ",\"errno\":%d,\"error\":\"%s\"}\n",
           (long) pid, selection, selected_segments, selected_bytes,
           attempted_calls, successful_calls, last_return, successful_bytes,
           first_errno, first_errno == 0 ? "" : strerror(first_errno));
    free_mapping_list(&list);
    return first_errno != 0 && successful_calls == 0 ? 1 : 0;
}

int main(int argc, char **argv)
{
    pid_t pid;

    if (argc < 3 || parse_pid(argv[2], &pid) != 0) {
        usage(stderr);
        return 2;
    }
    if (strcmp(argv[1], "profile") == 0 && argc == 3) {
        return command_profile(pid);
    }
    if (strcmp(argv[1], "pageout") == 0 && argc == 4
        && (strcmp(argv[3], "glibc-heap") == 0
            || strcmp(argv[3], "other-anon") == 0
            || strcmp(argv[3], "all-anon") == 0)) {
        return command_pageout(pid, argv[3]);
    }
    usage(stderr);
    return 2;
}
