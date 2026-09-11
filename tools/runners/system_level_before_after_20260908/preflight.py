#!/usr/bin/env python3
"""Read-only availability gate. Enforces pushed annotated contract + 600 s first."""
import argparse
import datetime
import ipaddress
import json
import pathlib
import re
import subprocess
import time
from sdb_request import check_request

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TAG = "system-before-after-contract-20260908"


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def record_push(path):
    tag = git("rev-parse", TAG)
    commit = git("rev-parse", TAG + "^{commit}")
    if git("cat-file", "-t", tag) != "tag":
        raise ValueError("contract requires annotated tag")
    remote = git("ls-remote", "origin", "refs/tags/" + TAG, "refs/heads/main")
    refs = dict(line.split()[::-1] for line in remote.splitlines())
    if refs.get("refs/tags/" + TAG) != tag or refs.get("refs/heads/main") != commit:
        raise ValueError("contract main/tag not both confirmed on origin")
    receipt = {"schema": "contract-push-receipt.v1", "tag": TAG, "tag_object": tag,
               "commit": commit, "origin_verified_utc": utc(), "epoch_ns": time.time_ns(),
               "monotonic_ns": time.monotonic_ns(),
               "boot_id": pathlib.Path("/proc/sys/kernel/random/boot_id").read_text().strip()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


class Gate:
    def __init__(self, addr, out):
        self.addr = str(ipaddress.IPv4Address(addr))
        self.serial = self.addr + ":26101"
        self.out = out
        self.commands = []

    def run(self, label, argv, timeout=20):
        if pathlib.Path(argv[0]).name == "sdb" and "shell" in argv:
            index = argv.index("shell")
            if len(argv) != index + 2:
                raise ValueError("SDB shell requires one bounded request argument")
            check_request(argv[index + 1])
        started = utc()
        try:
            p = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               timeout=timeout)
            text, rc = p.stdout, p.returncode
        except subprocess.TimeoutExpired as e:
            data = e.stdout or b""
            text = data.decode(errors="replace") if isinstance(data, bytes) else data
            text += "\nHOST_TIMEOUT\n"
            rc = 124
        (self.out / (label + ".txt")).write_text(text)
        self.commands.append({"label": label, "start_utc": started, "end_utc": utc(), "host_rc": rc,
                              "argv": [s.replace(self.addr, "<TEST_BOARD_IP>") for s in argv]})
        (self.out / "commands.json").write_text(json.dumps(self.commands, indent=2) + "\n")
        return rc, text.replace("\r", "")

    def remote(self, label, command):
        body = "( " + command + " ); rc=$?; printf '\\nRC=%s\\n' \"$rc\"; "
        body += "if [ \"$rc\" -eq 0 ]; then echo DONE_" + label + "; else echo FAIL_" + label + "; fi"
        _, text = self.run(label, ["sdb", "-s", self.serial, "shell", body])
        lines = text.splitlines()
        if lines.count("RC=0") != 1 or lines.count("DONE_" + label) != 1 or "FAIL_" + label in lines:
            raise ValueError("remote RC/DONE gate failed: " + label)
        return "\n".join(line for line in lines if line not in ("RC=0", "DONE_" + label)).strip()

    def check(self):
        self.run("sdb_version", ["sdb", "version"])
        rc, text = self.run("connect", ["sdb", "connect", self.addr])
        # sdb exit status is not a positive proof. Every identity probe uses remote markers.
        if re.search(r"failed|unable|cannot|error", text, re.I):
            raise ValueError("board connection failed; no additional connection attempts")
        self.run("devices", ["sdb", "devices"])
        if "rpi4" not in self.remote("UNAME_R", "uname -r"):
            raise ValueError("kernel identity mismatch")
        if self.remote("UNAME_M", "uname -m") != "armv7l":
            raise ValueError("architecture identity mismatch")
        os_release = self.remote("OS_RELEASE", "cat /etc/os-release")
        expected = "BUILD_ID=tizen-unified-toolchain_20260814.092727_tizen-headed-armv7l"
        if expected not in os_release.splitlines():
            raise ValueError("BUILD_ID identity mismatch")
        if self.remote("GLIBC", "rpm -q glibc") != "glibc-2.40-1.6.armv7l":
            raise ValueError("glibc environment drift")
        mem = self.remote("MEMINFO", "cat /proc/meminfo")
        found = re.search(r"^MemTotal:\s+(\d+) kB$", mem, re.M)
        if not found or not 8036234 <= int(found[1]) <= 8198582:
            raise ValueError("MemTotal environment drift")
        if self.remote("UID", "id -u") != "0":
            raise ValueError("root uid unavailable; root-on prohibited")
        governors = self.remote("GOVERNORS", "for n in 0 1 2 3; do p=/sys/devices/system/cpu/cpu$n/cpufreq/scaling_governor; test -w \"$p\" || exit 1; cat \"$p\" || exit 1; done")
        if governors.splitlines() != ["schedutil"] * 4:
            raise ValueError("occupied/unknown: governors not four schedutil")
        self.remote("WORKDIR", '''test -d /opt/usr && test -w /opt/usr || exit 1
p=/opt/usr/glibc_memopt
test ! -L "$p" || exit 1
if [ -e "$p" ]; then
test -d "$p" || exit 1
ls -la "$p" || exit 1
entries=$(ls -A "$p") || exit 1
test -z "$entries" || exit 1
else echo ABSENT; fi''')
        processes = self.remote("PROCESSES", "for p in /proc/[0-9]*; do test -r \"$p/comm\" || continue; printf '%s\\t' \"${p##*/}\"; tr '\\n' ' ' <\"$p/comm\"; printf '\\t'; tr '\\000' ' ' <\"$p/cmdline\" 2>/dev/null; printf '\\n'; done")
        targets = []
        for line in processes.splitlines():
            cols = line.split("\t", 2)
            if len(cols) != 3:
                continue
            name = cols[1].strip()
            if name == "enlightenment":
                targets.append(int(cols[0]))
            if re.search(r"alloc_bench|gst_loop_decode|gst-launch|^gdb$", name):
                raise ValueError("occupied/unknown: foreign workload PID=" + cols[0] + " comm=" + name)
            if name in ("sh", "bash", "python3", "python") and re.search(r"(sample_smaps|run_.*remote|sampler)[^ ]*\.(sh|py)", cols[2]):
                raise ValueError("occupied/unknown: foreign sampler/controller PID=" + cols[0])
        if len(targets) != 1:
            raise ValueError("G4 requires one running enlightenment PID")
        tcp = self.remote("TCP", "cat /proc/net/tcp /proc/net/tcp6")
        established = [line for line in tcp.splitlines() if len(line.split()) > 3
                       and line.split()[1].upper().endswith(":65F5") and line.split()[3] == "01"]
        if len(established) > 1:
            raise ValueError("occupied/unknown: multiple established sdb clients")
        space = self.remote("SPACE", "df -k / /opt/usr")
        rows = [line.split() for line in space.splitlines() if len(line.split()) >= 6]
        opt = [r for r in rows if r[-1] == "/opt/usr"]
        if len(opt) != 1 or not opt[0][3].isdigit() or int(opt[0][3]) < 524288:
            raise ValueError("/opt/usr headroom gate failed")
        self.remote("MEMPS", "command -v memps")
        self.remote("GDB_STATE", "rpm -q gdb; command -v gdb; true")
        self.remote("UPTIME", "date -u; uptime; cat /proc/loadavg")
        self.remote("HEALTH_READONLY", "cat /sys/block/zram0/mm_stat; cat /proc/swaps; dmesg")
        return {"enlightenment_pid": targets[0], "verdict": "PASS_READONLY_AVAILABILITY"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--record-push", type=pathlib.Path)
    p.add_argument("--receipt", type=pathlib.Path)
    p.add_argument("--ip")
    p.add_argument("--output-dir", type=pathlib.Path)
    a = p.parse_args()
    if a.record_push:
        record_push(a.record_push)
        return
    if not all((a.receipt, a.ip, a.output_dir)):
        p.error("gate needs --receipt --ip --output-dir")
    a.output_dir.mkdir(parents=True, exist_ok=False)
    result = {"start_utc": utc(), "verdict": "STOP", "board_mutations": False}
    try:
        receipt = json.loads(a.receipt.read_text())
        require = lambda ok, why: None if ok else (_ for _ in ()).throw(ValueError(why))
        require(receipt["tag"] == TAG and receipt["tag_object"] == git("rev-parse", TAG), "receipt tag mismatch")
        for filename in ("contract.json", "analyze_system_level.py"):
            relative = "tools/runners/system_level_before_after_20260908/" + filename
            frozen = subprocess.check_output(["git", "show", TAG + ":" + relative], cwd=ROOT)
            require(frozen == (ROOT / relative).read_bytes(), "frozen input changed: " + filename)
        require(pathlib.Path("/proc/sys/kernel/random/boot_id").read_text().strip() == receipt["boot_id"], "host boot changed")
        delta = (time.monotonic_ns() - receipt["monotonic_ns"]) / 1e9
        result["push_to_gate_seconds"] = delta
        require(delta >= 600 and time.time_ns() - receipt["epoch_ns"] >= 600000000000, "contract wait shorter than 600 s")
        result.update(Gate(a.ip, a.output_dir).check())
    except (ValueError, OSError, subprocess.SubprocessError) as e:
        result["reason"] = str(e).replace(str(a.ip), "<TEST_BOARD_IP>")
    result["end_utc"] = utc()
    (a.output_dir / "verdict.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["verdict"] == "PASS_READONLY_AVAILABILITY" else 1)


if __name__ == "__main__":
    main()
