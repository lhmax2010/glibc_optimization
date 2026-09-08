#!/usr/bin/env python3
"""PM-authorized exact session cleanup, with fresh identity and PID checks."""
import argparse
import json
import pathlib
from preflight import Gate, utc

APPROVED = ((26799, "60331272", "/dev/pts/0"), (27105, "60337550", "/dev/pts/1"))


def foreign_sessions(text):
    collector = [int(line.split("=", 1)[1]) for line in text.splitlines() if line.startswith("COLLECTOR_PID=")]
    if len(collector) != 1:
        raise ValueError("missing collector identity; cannot exclude collection process")
    rows = []
    parsed = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0].isdigit() and fields[1].isdigit():
            pid, parent = map(int, fields[:2])
            parsed.append((pid, parent, fields[2], line))
    # Gate.remote adds a subshell. Exclude its transitive descendants, not every
    # process sharing the PTY (which could hide another interactive session).
    own = set(collector)
    while True:
        expanded = own | {pid for pid, parent, _, _ in parsed if parent in own}
        if expanded == own:
            break
        own = expanded
    rows = [line for pid, _, tty, line in parsed if tty.startswith("pts/") and pid not in own]
    return rows


def close_command(pid, ticks, tty):
    return f'''p={pid}
if [ ! -d /proc/$p ]; then echo ALREADY_ABSENT_PID_$p; exit 0; fi
check_target() {{
s=$(cat /proc/$p/stat) || exit 1
s=${{s##*) }}
set -- $s
[ "${{20}}" = {ticks} ] || {{ echo FAIL_PID_REUSED; exit 1; }}
[ "$(tr '\\000' ' ' </proc/$p/cmdline)" = '/bin/sh -l ' ] || {{ echo FAIL_CMDLINE; exit 1; }}
[ "$(readlink /proc/$p/fd/0)" = {tty} ] || {{ echo FAIL_TTY; exit 1; }}
}}
for signal in TERM KILL; do
check_target
kill -"$signal" "$p" || exit 1
echo ${{signal}}_SENT_PID_$p
n=0
while [ -d /proc/$p ] && [ "$n" -lt 50 ]; do sleep 0.1; n=$((n+1)); done
[ ! -d /proc/$p ] && break
done
[ ! -d /proc/$p ] || {{ echo FAIL_PID_STILL_PRESENT; exit 1; }}
echo VERIFIED_ABSENT_PID_$p'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ip", required=True)
    p.add_argument("--output-dir", type=pathlib.Path, required=True)
    a = p.parse_args()
    a.output_dir.mkdir(parents=True, exist_ok=False)
    gate = Gate(a.ip, a.output_dir)
    result = {"decision_by": "PM", "decision_date": "2026-09-08",
              "basis": "board dedicated to project; two authorized stale login sessions",
              "start_utc": utc(), "verdict": "STOP", "terminated": []}
    try:
        result["preflight"] = gate.check()
        gate.remote("PS_BEFORE", "ps -ef; ps -eo pid,ppid,tty,lstart,etime,args")
        for pid, _, _ in APPROVED:
            gate.remote(f"PID_{pid}_SNAPSHOT", f'''if [ -d /proc/{pid} ]; then
ps -p {pid} -o pid,ppid,tty,lstart,etime,args || exit 1
cat /proc/{pid}/stat || exit 1
printf 'CMDLINE='; tr '\\000' ' ' </proc/{pid}/cmdline || exit 1; printf '\\n'
printf 'CWD='; readlink /proc/{pid}/cwd || echo UNREADABLE
printf 'STDIN='; readlink /proc/{pid}/fd/0 || echo UNREADABLE
sed -n '/^btime /p' /proc/stat || exit 1
getconf CLK_TCK
else echo ALREADY_ABSENT; fi''')
        for pid, ticks, tty in APPROVED:
            gate.remote(f"CLOSE_{pid}", close_command(pid, ticks, tty))
            result["terminated"].append(pid)
        gate.remote("VERIFY_ABSENT", "test ! -d /proc/26799 && test ! -d /proc/27105")
        ps = gate.remote("PS_AFTER", "printf 'COLLECTOR_PID=%s\\n' \"$$\"; ps -ww -eo pid,ppid,tty,lstart,etime,args")
        sessions = foreign_sessions(ps)
        if sessions:
            raise ValueError("remaining interactive PTY sessions: " + repr(sessions))
        post = a.output_dir / "postflight"
        post.mkdir()
        result["postflight"] = Gate(a.ip, post).check()
        result["verdict"] = "PASS_PM_OCCUPANCY_CLOSED"
    except Exception as error:
        result["reason"] = str(error).replace(a.ip, "<TEST_BOARD_IP>")
    result["end_utc"] = utc()
    (a.output_dir / "closure.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["verdict"] == "PASS_PM_OCCUPANCY_CLOSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
