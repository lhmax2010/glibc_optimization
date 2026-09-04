#!/bin/sh
set -u

work=/opt/usr/glibc_memopt/tizen_native_evidence_b2_20260904
asset="$work/small_320x240.mp4"
trim_script="$work/trim_via_gdb.sh"
log="$work/formal_command_log.txt"
samples="$work/formal_samples.tsv"
cells="$work/formal_cells.tsv"
intervals="$work/formal_intervals.tsv"
app_cycles="$work/formal_app_cycles.tsv"
app_id=setting-myaccount-efl
gst_pid=
app_pid=
health_started=0

mark()
{
    printf '%s\n' "$*" | tee -a "$log"
}

capture_stability()
{
    output=$1
    : >"$output" || return 1
    directory=/opt/usr/share/crash/livedump
    if [ -d "$directory" ]; then
        find "$directory" -maxdepth 1 -type f -name '*.zip' | LC_ALL=C sort |
        while IFS= read -r file; do
            bytes=$(wc -c <"$file") || exit 1
            mtime=$(stat -c %Y "$file") || exit 1
            hash=$(sha256sum "$file") || exit 1
            hash=${hash%% *}
            printf '%s\t%s\t%s\t%s\n' "$file" "$bytes" "$mtime" "$hash"
        done >>"$output"
    fi
}

finish()
{
    rc=$?
    trap - EXIT HUP INT TERM
    if [ -n "$gst_pid" ] && kill -0 "$gst_pid" 2>/dev/null; then
        kill "$gst_pid" 2>/dev/null || true
        wait "$gst_pid" 2>/dev/null || true
    fi
    if [ -n "$app_pid" ] && kill -0 "$app_pid" 2>/dev/null; then
        app_launcher -t "$app_id" >>"$work/formal_app_activity.log" 2>&1 || true
    fi
    if [ "$health_started" -eq 1 ]; then
        dmesg >"$work/health/dmesg_after.txt" 2>&1 || true
        cat /sys/block/zram0/mm_stat >"$work/health/zram_after.txt" 2>/dev/null || true
        cat /proc/swaps >"$work/health/swaps_after.txt" 2>/dev/null || true
        capture_stability "$work/health/stability_after.tsv" || true
    fi
    for governor in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
        [ -w "$governor" ] && printf '%s\n' schedutil >"$governor"
    done
    if [ "$health_started" -eq 1 ]; then
        for governor in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
            cat "$governor"
        done >"$work/health/governor_after.txt" 2>&1 || true
        printf 'controller_rc=%s\n' "$rc" >"$work/health/controller_exit.txt"
    fi
    exit "$rc"
}
trap finish EXIT HUP INT TERM

fail()
{
    mark "FAIL_B2_CONTROLLER reason=$1"
    exit 1
}

sample_one()
{
    sample_label=$1
    sample_pid=$2
    [ -r "/proc/$sample_pid/smaps" ] || return 1
    classes=$(awk '
      function flush_mapping(  len,anon) {
        if (!have_mapping) return
        len=end-start
        anon=(name=="" || (substr(name,1,1)=="[" && substr(name,length(name),1)=="]"))
        if (name=="[heap]" || (perms=="rw-p" && name=="" && start%1048576==0 && len>0 && len<=1048576)) g+=pd
        else if (substr(perms,2,1)=="w" && anon) o+=pd
        else f+=pd
        have_mapping=0
      }
      /^[0-9a-fA-F]+-[0-9a-fA-F]+ [rwxps-][rwxps-][rwxps-][rwxps-]/ {
        flush_mapping(); split($1,a,"-"); start=("0x" a[1])+0; end=("0x" a[2])+0; perms=$2
        name=""; for (i=6;i<=NF;i++) name=name (i==6?"":" ") $i
        pd=0; have_mapping=1; next
      }
      /^Private_Dirty:/ {pd=$2; next}
      END {flush_mapping(); printf "%d %d %d %d",g,o,f,g+o+f}
    ' "/proc/$sample_pid/smaps") || return 1
    set -- $classes
    [ "$#" -eq 4 ] || return 1
    g=$1; o=$2; f=$3; total=$4
    stat_payload=$(sed 's/^[^)]*) //' "/proc/$sample_pid/stat") || return 1
    set -- $stat_payload
    [ "$#" -ge 20 ] || return 1
    minflt=$8; majflt=${10}; starttime=${20}
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$sample_label" "$(date -Ins)" "$(date +%s%N)" "$sample_pid" "$starttime" \
        "$g" "$o" "$f" "$total" "$minflt" "$majflt" >>"$samples"
}

save_memps()
{
    memps_label=$1
    memps_pid=$2
    output="$work/memps_${memps_label}.txt"
    memps "$memps_pid" >"$output" 2>&1
    rc=$?
    printf 'RC=%s\n' "$rc" >>"$output"
    if [ "$rc" -eq 0 ]; then
        printf 'DONE_MEMPS_%s\n' "$memps_label" >>"$output"
    else
        printf 'FAIL_MEMPS_%s\n' "$memps_label" >>"$output"
    fi
    [ "$rc" -eq 0 ]
}

memps_heap()
{
    awk '$NF=="[heap]" {sum+=$4} END {print sum+0}' "$1"
}

inject_trim()
{
    trim_label=$1
    trim_pid=$2
    output="$work/gdb_trim_${trim_label}.txt"
    begin=$(date +%s%N)
    "$trim_script" "$trim_pid" >"$output" 2>&1
    rc=$?
    end=$(date +%s%N)
    elapsed=$(awk -v a="$begin" -v b="$end" 'BEGIN {printf "%.6f",(b-a)/1000000}')
    ret=$(awk '/^\$[0-9]+ = [01]$/ {v=$3} END {if (v=="") v="NA"; print v}' "$output")
    printf 'RC=%s\n' "$rc" >>"$output"
    if [ "$rc" -eq 0 ] && [ "$ret" != NA ]; then
        printf 'DONE_GDB_TRIM_%s\n' "$trim_label" >>"$output"
    else
        printf 'FAIL_GDB_TRIM_%s\n' "$trim_label" >>"$output"
        return 1
    fi
    printf '%s %s %s %s\n' "$ret" "$elapsed" "$begin" "$end"
}

inject_malloc_info()
{
    info_label=$1
    info_pid=$2
    xml="$work/malloc_info_${info_label}.xml"
    commands="$work/gdb_malloc_info_${info_label}.commands"
    output="$work/gdb_malloc_info_${info_label}.txt"
    {
        printf 'set pagination off\n'
        printf 'set $stream = (void *) fopen("%s", "w")\n' "$xml"
        printf 'call (int) malloc_info(0, $stream)\n'
        printf 'call (int) fclose($stream)\n'
        printf 'detach\n'
    } >"$commands" || return 1
    gdb -p "$info_pid" -batch -x "$commands" >"$output" 2>&1
    rc=$?
    printf 'RC=%s\n' "$rc" >>"$output"
    if [ "$rc" -eq 0 ] && [ -s "$xml" ] && grep -q '</malloc>' "$xml"; then
        printf 'DONE_GDB_MALLOC_INFO_%s\n' "$info_label" >>"$output"
        return 0
    fi
    printf 'FAIL_GDB_MALLOC_INFO_%s\n' "$info_label" >>"$output"
    return 1
}

wait_until_ns()
{
    due=$1
    python3 -c 'import sys,time
due=int(sys.argv[1])
remaining=(due-time.time_ns())/1_000_000_000
if remaining > 0: time.sleep(remaining)
while time.time_ns() < due: pass' "$due"
}

mkdir -p "$work/health" || fail mkdir_health
: >"$log"
printf 'label\ttimestamp\tepoch_ns\tpid\tstarttime_ticks\tglibc_heap_pd_kb\tother_anon_pd_kb\tfile_backed_pd_kb\ttotal_pd_kb\tminflt\tmajflt\n' >"$samples" || fail samples_header
printf 'group\tcell\tpid\tstarttime_ticks\tproject_pre_kb\tproject_post_kb\tmemps_pre_heap_kb\tmemps_post_heap_kb\ttrim_return\tinjection_ms\tinjection_start_ns\tinjection_end_ns\tminflt_pre\tminflt_post\tmajflt_pre\tmajflt_post\tbuffers_pre\tbuffers_post\tprocess_exit_code\terror_lines\n' >"$cells" || fail cells_header
printf 'cell\tprior_injection_start_ns\tinjection_start_ns\tinterval_ns\tinterval_s\trequirement_s\tpass\n' >"$intervals" || fail intervals_header
printf 'cycle\tapp_id\tpid\tstarttime_ticks\tlaunch_rc\talive_check_ns\talive_after_30s\tterminate_rc\tabsent_after_2s\n' >"$app_cycles" || fail app_cycles_header

kernel=$(uname -r); rc=$?; mark "kernel=$kernel"; mark "RC=$rc"
[ "$rc" -eq 0 ] && case "$kernel" in *rpi4*) : ;; *) fail kernel ;; esac
mark DONE_GATE_KERNEL
arch=$(uname -m); rc=$?; mark "arch=$arch"; mark "RC=$rc"
[ "$rc" -eq 0 ] && [ "$arch" = armv7l ] || fail arch
mark DONE_GATE_ARCH
build=$(awk -F= '/^BUILD_ID=/{print $2; exit}' /etc/os-release); rc=$?
mark "BUILD_ID=$build"; mark "RC=$rc"
[ "$rc" -eq 0 ] && [ "$build" = tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l ] || fail build_id
mark DONE_GATE_BUILD_ID
glibc=$(rpm -q glibc); rc=$?; mark "$glibc"; mark "RC=$rc"
[ "$rc" -eq 0 ] && [ "$glibc" = glibc-2.40-1.6.armv7l ] || fail glibc
mark DONE_GATE_GLIBC
memtotal=$(awk '/^MemTotal:/{print $2}' /proc/meminfo); rc=$?
mark "MemTotal_kB=$memtotal"; mark "RC=$rc"
[ "$rc" -eq 0 ] && [ "$memtotal" = 8117408 ] || fail memtotal
mark DONE_GATE_MEMTOTAL
[ "$(id -u)" -eq 0 ] || fail root
command -v gdb >/dev/null 2>&1 || fail gdb
command -v python3 >/dev/null 2>&1 || fail python3
command -v memps >/dev/null 2>&1 || fail memps
command -v gst-launch-1.0 >/dev/null 2>&1 || fail gst_launch
test "$(sha256sum "$asset" | awk '{print $1}')" = 3df34a234c69d51d543aed8d379aa0e18fe01839e20ac213a1b3061acb67f72d || fail asset_sha
test -x "$trim_script" || fail trim_script
app_launcher -l | grep -F "'$app_id'" >/dev/null 2>&1 || fail app_not_listed
mark 'RC=0'; mark DONE_ASSET_AND_TOOL_GATES

dmesg >"$work/health/dmesg_before.txt" 2>&1 || fail dmesg_before
cat /sys/block/zram0/mm_stat >"$work/health/zram_before.txt" || fail zram_before
cat /proc/swaps >"$work/health/swaps_before.txt" || fail swaps_before
capture_stability "$work/health/stability_before.tsv" || fail stability_before
for governor in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
    cat "$governor"
done >"$work/health/governor_before.txt" || fail governor_before
health_started=1
for governor in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
    printf '%s\n' performance >"$governor" || fail governor_set
done
for governor in /sys/devices/system/cpu/cpu[0-3]/cpufreq/scaling_governor; do
    [ "$(cat "$governor")" = performance ] || fail governor_verify
done
mark 'RC=0'; mark DONE_GOVERNOR_PERFORMANCE

last_injection=0
i=1
while [ "$i" -le 5 ]; do
    if [ "$last_injection" -ne 0 ]; then
        next_launch=$((last_injection + 90000000000))
        wait_until_ns "$next_launch" || fail "T1_${i}_wait"
    fi
    gst_log="$work/gst_T1_${i}.log"
    gst_begin=$(date +%s%N)
    gst-launch-1.0 -m -v filesrc location="$asset" ! decodebin ! \
        identity name=counter silent=false ! fakesink sync=true >"$gst_log" 2>&1 &
    gst_pid=$!
    sleep 30
    kill -0 "$gst_pid" 2>/dev/null || fail "T1_${i}_not_alive_at_30s"
    sample_one "T1_${i}_pre" "$gst_pid" || fail "T1_${i}_sample_pre"
    save_memps "T1_${i}_pre" "$gst_pid" || fail "T1_${i}_memps_pre"
    pre_line=$(tail -n 1 "$samples")
    cell_pid=$(printf '%s\n' "$pre_line" | awk -F '\t' '{print $4}')
    pre_start=$(printf '%s\n' "$pre_line" | awk -F '\t' '{print $5}')
    pre_g=$(printf '%s\n' "$pre_line" | awk -F '\t' '{print $6}')
    pre_min=$(printf '%s\n' "$pre_line" | awk -F '\t' '{print $10}')
    pre_maj=$(printf '%s\n' "$pre_line" | awk -F '\t' '{print $11}')
    pre_memps=$(memps_heap "$work/memps_T1_${i}_pre.txt") || fail "T1_${i}_memps_parse_pre"
    buffers_pre=$(grep -c 'last-message = chain' "$gst_log" 2>/dev/null || true)
    trim_data=$(inject_trim "T1_${i}" "$gst_pid") || fail "T1_${i}_trim"
    set -- $trim_data
    [ "$#" -eq 4 ] || fail "T1_${i}_trim_fields"
    trim_ret=$1; trim_ms=$2; injection_start=$3; injection_end=$4
    if [ "$last_injection" -eq 0 ]; then
        printf 'T1_%s\t-\t%s\t-\t-\t120.000000000\tNA\n' "$i" "$injection_start" >>"$intervals"
    else
        interval_ns=$((injection_start - last_injection))
        interval_s=$(awk -v value="$interval_ns" 'BEGIN {printf "%.9f",value/1000000000}')
        [ "$interval_ns" -ge 120000000000 ] || fail "T1_${i}_interval_under_120s"
        printf 'T1_%s\t%s\t%s\t%s\t%s\t120.000000000\ttrue\n' \
            "$i" "$last_injection" "$injection_start" "$interval_ns" "$interval_s" >>"$intervals"
    fi
    last_injection=$injection_start
    sample_one "T1_${i}_post" "$gst_pid" || fail "T1_${i}_sample_post"
    save_memps "T1_${i}_post" "$gst_pid" || fail "T1_${i}_memps_post"
    post_line=$(tail -n 1 "$samples")
    post_start=$(printf '%s\n' "$post_line" | awk -F '\t' '{print $5}')
    [ "$post_start" = "$pre_start" ] || fail "T1_${i}_starttime_changed"
    post_g=$(printf '%s\n' "$post_line" | awk -F '\t' '{print $6}')
    post_min=$(printf '%s\n' "$post_line" | awk -F '\t' '{print $10}')
    post_maj=$(printf '%s\n' "$post_line" | awk -F '\t' '{print $11}')
    post_memps=$(memps_heap "$work/memps_T1_${i}_post.txt") || fail "T1_${i}_memps_parse_post"
    sleep 2
    kill -0 "$gst_pid" 2>/dev/null || fail "T1_${i}_died_after_trim"
    buffers_post=$(grep -c 'last-message = chain' "$gst_log" 2>/dev/null || true)
    [ "$buffers_post" -gt "$buffers_pre" ] || fail "T1_${i}_buffers_not_increasing"
    wait "$gst_pid"
    gst_rc=$?
    gst_pid=
    gst_end=$(date +%s%N)
    error_lines=$(grep -c 'ERROR' "$gst_log" 2>/dev/null || true)
    [ "$gst_rc" -eq 0 ] || fail "T1_${i}_gst_exit"
    [ "$error_lines" -eq 0 ] || fail "T1_${i}_gst_error"
    printf 'T1\tT1_%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$i" "$cell_pid" "$pre_start" "$pre_g" "$post_g" "$pre_memps" "$post_memps" \
        "$trim_ret" "$trim_ms" "$injection_start" "$injection_end" "$pre_min" "$post_min" "$pre_maj" "$post_maj" \
        "$buffers_pre" "$buffers_post" "$gst_rc" "$error_lines" >>"$cells"
    mark "RC=0"; mark "DONE_T1_${i} gst_begin_ns=$gst_begin gst_end_ns=$gst_end"
    i=$((i + 1))
done

: >"$work/formal_app_activity.log"
i=1
while [ "$i" -le 5 ]; do
    launch_begin=$(date +%s%N)
    launch=$(app_launcher -s "$app_id" 2>&1)
    launch_rc=$?
    printf 'cycle=%s\n%s\nlaunch_rc=%s\n' "$i" "$launch" "$launch_rc" >>"$work/formal_app_activity.log"
    [ "$launch_rc" -eq 0 ] || fail "E4_app_${i}_launch"
    app_pid=$(printf '%s\n' "$launch" | awk '/successfully launched pid =/{print $(NF-3); exit}')
    case "$app_pid" in ''|*[!0-9]*) fail "E4_app_${i}_pid_parse" ;; esac
    app_start=$(sed 's/^[^)]*) //' "/proc/$app_pid/stat" | awk '{print $20}')
    sleep 30
    alive_ns=$(date +%s%N)
    kill -0 "$app_pid" 2>/dev/null || fail "E4_app_${i}_not_alive_30s"
    current_start=$(sed 's/^[^)]*) //' "/proc/$app_pid/stat" | awk '{print $20}')
    [ "$current_start" = "$app_start" ] || fail "E4_app_${i}_starttime_changed"
    app_launcher -t "$app_id" >>"$work/formal_app_activity.log" 2>&1
    term_rc=$?
    [ "$term_rc" -eq 0 ] || fail "E4_app_${i}_terminate"
    sleep 2
    if kill -0 "$app_pid" 2>/dev/null; then absent=false; else absent=true; fi
    [ "$absent" = true ] || fail "E4_app_${i}_still_alive"
    printf '%s\t%s\t%s\t%s\t%s\t%s\ttrue\t%s\t%s\n' \
        "$i" "$app_id" "$app_pid" "$app_start" "$launch_rc" "$alive_ns" "$term_rc" "$absent" >>"$app_cycles"
    app_pid=
    mark "RC=0"; mark "DONE_E4_APP_${i} launch_begin_ns=$launch_begin"
    i=$((i + 1))
done

enlightenment_pid=$(pidof enlightenment 2>/dev/null | awk '{print $1}')
[ -n "$enlightenment_pid" ] || fail enlightenment_absent
[ "$(readlink "/proc/$enlightenment_pid/exe")" = /usr/bin/enlightenment ] || fail enlightenment_exe
inject_malloc_info E4_PRIME "$enlightenment_pid" || fail E4_malloc_info
sample_one E4_PRIME_pre "$enlightenment_pid" || fail E4_sample_pre
save_memps E4_PRIME_pre "$enlightenment_pid" || fail E4_memps_pre
pre_line=$(tail -n 1 "$samples")
pre_start=$(printf '%s\n' "$pre_line" | awk -F '\t' '{print $5}')
pre_g=$(printf '%s\n' "$pre_line" | awk -F '\t' '{print $6}')
pre_min=$(printf '%s\n' "$pre_line" | awk -F '\t' '{print $10}')
pre_maj=$(printf '%s\n' "$pre_line" | awk -F '\t' '{print $11}')
pre_memps=$(memps_heap "$work/memps_E4_PRIME_pre.txt") || fail E4_memps_parse_pre
trim_data=$(inject_trim E4_PRIME "$enlightenment_pid") || fail E4_trim
set -- $trim_data
[ "$#" -eq 4 ] || fail E4_trim_fields
trim_ret=$1; trim_ms=$2; injection_start=$3; injection_end=$4
sample_one E4_PRIME_post "$enlightenment_pid" || fail E4_sample_post
save_memps E4_PRIME_post "$enlightenment_pid" || fail E4_memps_post
post_line=$(tail -n 1 "$samples")
post_start=$(printf '%s\n' "$post_line" | awk -F '\t' '{print $5}')
[ "$post_start" = "$pre_start" ] || fail E4_starttime_changed
post_g=$(printf '%s\n' "$post_line" | awk -F '\t' '{print $6}')
post_min=$(printf '%s\n' "$post_line" | awk -F '\t' '{print $10}')
post_maj=$(printf '%s\n' "$post_line" | awk -F '\t' '{print $11}')
post_memps=$(memps_heap "$work/memps_E4_PRIME_post.txt") || fail E4_memps_parse_post
printf 'E4\tE4_PRIME\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\tNA\tNA\tNA\tNA\n' \
    "$enlightenment_pid" "$pre_start" "$pre_g" "$post_g" "$pre_memps" "$post_memps" \
    "$trim_ret" "$trim_ms" "$injection_start" "$injection_end" "$pre_min" "$post_min" "$pre_maj" "$post_maj" >>"$cells"
[ "$(readlink "/proc/$enlightenment_pid/exe")" = /usr/bin/enlightenment ] || fail enlightenment_restarted
mark 'RC=0'; mark DONE_E4_PRIME
mark 'RC=0'; mark DONE_B2_CONTROLLER
trap - EXIT HUP INT TERM
finish
