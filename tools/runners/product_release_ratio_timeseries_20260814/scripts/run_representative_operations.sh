#!/bin/sh
set -u

sock=/tmp/product_board_mux_codex_0814_a
host=root@<PRODUCT_BOARD_IP>
log=<WORKSPACE>/board_results/product_release_ratio_timeseries_20260814/raw/operations.log

board_command()
{
    label=$1
    command=$2
    printf '\n[%s] %s\n' "$(date -Ins)" "$label" >>"$log"
    printf 'COMMAND: %s\n' "$command" >>"$log"
    timeout 20s ssh -S "$sock" "$host" "date -Ins; $command" >>"$log" 2>&1
    rc=$?
    printf 'EXIT=%s\n' "$rc" >>"$log"
    return 0
}

{
    printf 'representative_operations_log\n'
    printf 'host_start=%s\n' "$(date -Ins)"
    printf 'channel=SSH ControlMaster %s\n' "$sock"
    printf 'initial_idle_seconds=65\n'
    printf 'CHANNEL_SWITCH=NOT_EXECUTED: no signed input/remote-control command is installed; /dev/uinput exists but injecting a new helper is outside the read-only boundary.\n'
    printf 'All three candidate appids were verified not running before collection.\n'
} >"$log"

sleep 65
board_command 'Open ServiceK UI (not a channel switch)' \
    'app_launcher -s AppC; app_launcher -r AppC'
sleep 25
board_command 'Close ServiceK UI' \
    'app_launcher -t AppC; app_launcher -r AppC'

sleep 20
board_command 'Open content browser' \
    'app_launcher -s AppA; app_launcher -r AppA'
sleep 35
board_command 'Close content browser and return' \
    'app_launcher -t AppA; app_launcher -r AppA'

sleep 20
board_command 'Open AppUIF' \
    'app_launcher -s AppE; app_launcher -r AppE'
sleep 35
board_command 'Close AppUIF and return' \
    'app_launcher -t AppE; app_launcher -r AppE'

board_command 'Post-operation app state' \
    'for a in AppC AppA AppE; do echo ===$a; app_launcher -r "$a"; done; true'
printf '\nfinal_idle_begins_host=%s\n' "$(date -Ins)" >>"$log"
