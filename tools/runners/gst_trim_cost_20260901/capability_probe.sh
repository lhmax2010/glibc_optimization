#!/bin/sh
set -u

serial=${SDB_SERIAL:?set SDB_SERIAL to the reviewed board serial/address}
outdir=${1:?usage: capability_probe.sh OUTPUT_DIR}
mkdir -p "$outdir" || exit 2
command_log="$outdir/commands.log"
: >"$command_log" || exit 3

run_remote()
{
    label=$1
    body=$2
    output="$outdir/$3"
    remote="$body; rc=\$?; printf 'RC=%s\n' \"\$rc\"; if [ \"\$rc\" -eq 0 ]; then printf 'DONE_%s\n' '$label'; else printf 'FAIL_%s\n' '$label'; fi"
    printf '+ sdb -s <TEST_BOARD_IP>:26101 shell %s\n' "$remote" >>"$command_log"
    sdb -s "$serial" shell "$remote" >"$output" 2>&1
    tr -d '\r' <"$output" | grep -Fx 'RC=0' >/dev/null 2>&1 || return 1
    tr -d '\r' <"$output" | grep -Fx "DONE_$label" >/dev/null 2>&1 || return 1
}

run_remote GST_TOOLS 'command -v gst-launch-1.0; command -v gst-inspect-1.0; gst-launch-1.0 --version; gst-inspect-1.0 --version' gst_tools.txt || exit 10
run_remote GST_CORE_RPMS 'ok=1; for p in gstreamer gstreamer-utils; do rpm -q "$p" || ok=0; done; test "$ok" -eq 1' gst_core_rpms.txt || exit 11
run_remote GST_PLUGINS 'ok=1; for p in filesrc qtdemux queue mpeg4videoparse avdec_mpeg4 fakesink; do printf "PLUGIN=%s\n" "$p"; gst-inspect-1.0 "$p" || ok=0; done; test "$ok" -eq 1' gst_plugins.txt || exit 12
run_remote GST_PLUGIN_PACKAGES 'export GST_DEBUG_NO_COLOR=1; ok=1; for p in filesrc qtdemux queue mpeg4videoparse avdec_mpeg4 fakesink; do f=$(gst-inspect-1.0 "$p" | awk '\''$1=="Filename" {print $2; found=1; exit} END {if (!found) exit 1}'\'') || ok=0; printf "PLUGIN=%s FILE=%s\n" "$p" "$f"; if test -n "$f" && test -f "$f"; then rpm -qf "$f" || ok=0; else ok=0; fi; done; test "$ok" -eq 1' gst_plugin_packages.txt || exit 13
run_remote GST_PACKAGE_SIZES 'export GST_DEBUG_NO_COLOR=1; ok=1; for p in gstreamer gstreamer-utils; do rpm -q --queryformat "%{NAME}\t%{VERSION}-%{RELEASE}.%{ARCH}\t%{SIZE}\n" "$p" || ok=0; done; for e in filesrc qtdemux queue mpeg4videoparse avdec_mpeg4 fakesink; do f=$(gst-inspect-1.0 "$e" | awk '\''$1=="Filename" {print $2; found=1; exit} END {if (!found) exit 1}'\'') || ok=0; if test -n "$f" && test -f "$f"; then rpm -qf --queryformat "%{NAME}\t%{VERSION}-%{RELEASE}.%{ARCH}\t%{SIZE}\n" "$f" || ok=0; else ok=0; fi; done; test "$ok" -eq 1' gst_package_sizes.txt || exit 14
run_remote FILESYSTEMS 'df -B1 / /opt/usr; df -h / /opt/usr' filesystems.txt || exit 15
run_remote WORKDIR_ABSENT 'test ! -e /opt/usr/glibc_memopt/gst_trim_cost_20260901' workdir_absent.txt || exit 16
run_remote BASE_TOOLS 'ok=1; for p in ldd mkfifo find sha256sum awk sed grep date; do printf "%s=" "$p"; command -v "$p" || ok=0; done; test "$ok" -eq 1' base_tools.txt || exit 17
run_remote OPTIONAL_PARSERS 'for p in python3 jq; do if command -v "$p" >/dev/null 2>&1; then printf "%s=" "$p"; command -v "$p"; else printf "MISSING:%s\n" "$p"; fi; done' optional_parsers.txt || exit 18

printf 'CAPABILITY_GATE_PASS\n' | tee "$outdir/capability_verdict.txt"
