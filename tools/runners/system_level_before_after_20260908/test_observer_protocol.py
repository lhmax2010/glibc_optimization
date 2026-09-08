"""Host-only transport smoke test; never a board result or timing evidence."""
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("observer", HERE / "build_observer.py")
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


class ObserverProtocol(unittest.TestCase):
    def test_pre_post_both_arms_complete_without_timer_change(self):
        if not shutil.which("gcc") or not shutil.which("bash"):
            self.skipTest("optional observer compile smoke requires host gcc and bash")
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            src = root / "observer.c"
            src.write_text(observer.instrument((HERE.parents[2] / "tools/alloc_bench/alloc_bench.c").read_text()))
            binary = root / "observer"
            subprocess.run(["gcc", "-std=c99", "-O2", "-D_GNU_SOURCE", "-pthread", "-o", str(binary), str(src)], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for arm in ("valley", "none"):
                out = root / arm
                out.mkdir()
                fifo = out / "ack.fifo"
                os.mkfifo(fifo)
                ack = os.open(fifo, os.O_RDWR)
                event = out / "events.txt"
                result = out / "result.json"
                # Tiny host-only fixture parameters; formal board contract is untouched.
                args = [str(binary), "--profile", "mixed", "--threads", "2", "--seed", "20260814",
                        "--live-set", "32", "--idle-release", "50", "--release-order", "high",
                        "--touch-full", "--cycles", "2", "--cycle-rise", "0.02", "--cycle-peak", "0.02",
                        "--release-duration", "0.02", "--cycle-valley", "0.02", "--warmup", "0",
                        "--trim-at", arm, "--outdir", str(out / "xml")]
                with result.open("w") as stream:
                    process = subprocess.Popen(["bash", "--noprofile", "--norc", "-c",
                        'exec 3>"$1" 4<"$2"; shift 2; exec "$@"', "observer-test", str(event), str(fifo), *args],
                        stdout=stream, stderr=subprocess.PIPE, env={"PATH": os.environ["PATH"], "LC_ALL": "C"})
                    try:
                        expected = ["PRE 01", "POST 01", "PRE 02", "POST 02"]
                        seen = []
                        deadline = time.monotonic() + 15
                        while len(seen) < len(expected) and time.monotonic() < deadline:
                            lines = event.read_text().splitlines() if event.exists() else []
                            if len(lines) > len(seen):
                                self.assertEqual(lines, expected[:len(lines)])
                                for _ in lines[len(seen):]:
                                    os.write(ack, b"K")
                                seen = lines
                            elif process.poll() is not None:
                                break
                            time.sleep(0.01)
                        self.assertEqual(seen, expected)
                        _, err = process.communicate(timeout=15)
                        self.assertEqual(process.returncode, 0, err.decode())
                    finally:
                        os.close(ack)
                        if process.poll() is None:
                            process.kill()
                            process.communicate()
                data = json.loads(result.read_text())
                self.assertEqual(data["trim_at"], arm)
                self.assertEqual(len(data["cycle_data"]), 2)
                for cycle in data["cycle_data"]:
                    self.assertEqual(cycle["trim_elapsed_ns"] == 0, arm == "none")


if __name__ == "__main__":
    unittest.main()
