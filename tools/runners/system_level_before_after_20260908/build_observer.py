#!/usr/bin/env python3
"""Build a measurement-only alloc_bench copy; original workload source unchanged."""
import argparse
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[3]
HOOK = r'''
/* Measurement handshake only: stack buffer + read/write, outside trim timing.
 * fd 3 emits PRE/POST <cycle>; fd 4 receives exactly one K acknowledgement.
 * All worker allocation/release commands and CLI parameters remain unchanged. */
static int system_measure_gate(int cycle, int post)
{
    char event[] = "PRE 00\n";
    char after[] = "POST 00\n";
    char ack;
    char *p = post ? after : event;
    size_t n = post ? sizeof(after) - 1 : sizeof(event) - 1;
    p[n - 3] = (char)('0' + (cycle + 1) / 10);
    p[n - 2] = (char)('0' + (cycle + 1) % 10);
    if (write(3, p, n) != (ssize_t)n) return -1;
    if (read(4, &ack, 1) != 1 || ack != 'K') return -1;
    return 0;
}

'''


def instrument(source):
    if "system_measure_gate" in source:
        raise ValueError("source already instrumented")
    def once(old, new):
        nonlocal source
        if source.count(old) != 1:
            raise ValueError("source drift: measurement insertion anchor not unique")
        source = source.replace(old, new, 1)

    once("static int cycle_trim_now(", HOOK + "static int cycle_trim_now(")
    once("        if (cfg->trim_point == TRIM_VALLEY) {\n",
         "        if (system_measure_gate(cycle, 0) != 0) goto fail;\n"
         "        if (cfg->trim_point == TRIM_VALLEY) {\n")
    once("            sleep_seconds(cfg->cycle_valley_s);\n        } else if",
         "            if (system_measure_gate(cycle, 1) != 0) goto fail;\n"
         "            sleep_seconds(cfg->cycle_valley_s);\n        } else if")
    once("            sleep_seconds(cfg->cycle_valley_s);\n        }\n    }\n\n"
         "    cycle_dispatch(&control, CYCLE_STOP, 0.0);",
         "            if (system_measure_gate(cycle, 1) != 0) goto fail;\n"
         "            sleep_seconds(cfg->cycle_valley_s);\n        }\n    }\n\n"
         "    cycle_dispatch(&control, CYCLE_STOP, 0.0);")
    return source


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--toolchain-root", type=pathlib.Path, required=True)
    p.add_argument("--output-dir", type=pathlib.Path, required=True)
    a = p.parse_args()
    tc = a.toolchain_root.resolve()
    out = a.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    src = ROOT / "tools/alloc_bench/alloc_bench.c"
    generated = out / "alloc_bench_observer.c"
    generated.write_text(instrument(src.read_text()))
    elf = out / "alloc_bench_observer.armv7l"
    prefix = ["bwrap", "--tmpfs", "/", "--dir", "/home", "--bind", "/home", "/home",
              "--dir", "/tmp", "--bind", "/tmp", "/tmp", "--ro-bind", str(tc / "usr"), "/usr",
              "--ro-bind", str(tc / "lib"), "/lib", "--proc", "/proc",
              "--ro-bind", str(tc / "emul"), "/emul",
              str(tc / "emul/usr/bin/armv7l-tizen-linux-gnueabi-gcc"),
              "-B/usr/lib/gcc/armv7l-tizen-linux-gnueabi/14.2.0/"]
    version = subprocess.check_output(prefix + ["--version"], text=True)
    subprocess.run(prefix + ["-std=c99", "-O2", "-g", "-Wall", "-Wextra", "-Werror",
                            "-D_GNU_SOURCE", "-fdebug-prefix-map=" + str(out) + "=.",
                            "-fdebug-prefix-map=" + str(tc) + "=/toolchain",
                            "-o", str(elf), str(generated), "-pthread"], check=True)
    h = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    proof = {"source_path": "tools/alloc_bench/alloc_bench.c", "source_sha256": h(src),
             "generated_source_sha256": h(generated), "elf_sha256": h(elf),
             "elf_bytes": elf.stat().st_size, "compiler": version,
             "scope": "measurement-only handshake; identical ELF for trim/none; not a GBS rebaseline"}
    (out / "build_identity.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
