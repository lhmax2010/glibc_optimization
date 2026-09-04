#!/usr/bin/env python3
"""Validate and adjudicate the prospective four-cell GBS held-out run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def write_tsv(path: Path, rows: list[dict[str, object]]) -> None:
    require(bool(rows), f"refusing empty table: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def safe_manifest_path(root: Path, raw: str) -> Path:
    require(raw.startswith("./"), f"manifest path lacks ./ prefix: {raw}")
    relative = Path(raw[2:])
    require(not relative.is_absolute() and ".." not in relative.parts, f"unsafe manifest path: {raw}")
    return root / relative


def validate_pull_integrity(root: Path) -> None:
    manifest, sizes = root / "board_manifest.sha256", root / "board_file_sizes.tsv"
    require(manifest.is_file() and sizes.is_file(), "missing board manifest/size list")
    actual = {path for path in root.rglob("*") if path.is_file()}
    manifest_files: set[Path] = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        fields = line.split(maxsplit=1)
        require(len(fields) == 2 and re.fullmatch(r"[0-9a-f]{64}", fields[0]) is not None, f"bad manifest row: {line}")
        path = safe_manifest_path(root, fields[1].strip())
        require(path.is_file() and path not in manifest_files, f"missing/duplicate manifest path: {path}")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == fields[0], f"manifest hash mismatch: {path}")
        manifest_files.add(path)
    require(manifest_files == actual - {manifest, sizes}, "manifest file set mismatch")
    size_files: set[Path] = set()
    for line in sizes.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t", 1)
        require(len(fields) == 2 and fields[0].isdigit(), f"bad size row: {line}")
        path = safe_manifest_path(root, fields[1])
        require(path.is_file() and path.stat().st_size == int(fields[0]), f"size mismatch: {path}")
        size_files.add(path)
    require(size_files == actual - {sizes}, "size file set mismatch")


def read_external(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    require(bool(rows), f"empty external sequence: {path}")
    integers = ("sample", "epoch_ns", "pid", "glibc_heap_pd_kb", "other_anon_pd_kb", "file_backed_pd_kb", "total_pd_kb", "minflt", "majflt")
    for row in rows:
        row["elapsed_s"] = float(row["elapsed_s"])
        for key in integers:
            row[key] = int(row[key])
    require([row["sample"] for row in rows] == list(range(len(rows))), f"sample gap: {path}")
    require(all(a["elapsed_s"] < b["elapsed_s"] for a, b in zip(rows, rows[1:])), f"time reversal: {path}")
    require(len({row["pid"] for row in rows}) == 1, f"PID changed: {path}")
    return rows


def dmesg_increment(before: list[str], after: list[str]) -> tuple[list[str], str]:
    if after[: len(before)] == before:
        return after[len(before):], "prefix"
    old = set(before)
    return [line for line in after if line not in old], "set-difference-fallback"


def cell_name(item: dict[str, object]) -> str:
    return f"{int(item['order']):02d}_{item['elf']}_{item['profile']}_rep{item['rep']}"


def adjudicate(rows: list[dict[str, object]], contract: dict[str, object]) -> dict[str, object]:
    require(len(rows) == len(contract["order"]) == 4, f"expected four held-out rows, got {len(rows)}")
    cells = []
    for row, expected in zip(rows, contract["order"]):
        require(
            int(row["order"]) == int(expected["order"])
            and row["elf"] == expected["elf"] == "gbs"
            and row["profile"] == expected["profile"]
            and int(row["rep"]) == int(expected["rep"]),
            f"order/identity mismatch at row {row.get('order')}",
        )
        band = contract["calibration_bands"][row["profile"]]
        value = float(row["reclaim_pct_of_pretrim"])
        in_band = float(band["lower_pct"]) <= value <= float(band["upper_pct"])
        cells.append({
            "order": int(row["order"]), "profile": row["profile"], "rep": int(row["rep"]),
            "observed_pct": round(value, 6), "center_pct": band["center_pct"],
            "plus_minus_pp": band["plus_minus_pp"], "lower_pct": band["lower_pct"],
            "upper_pct": band["upper_pct"], "in_band": in_band,
        })
    passed = sum(bool(cell["in_band"]) for cell in cells)
    return {
        "schema": "glibc-memopt.gbs-heldout-decision.v1",
        "verdict": "PASS" if passed == 4 else "FAIL",
        "passed_cells": passed,
        "total_cells": 4,
        "exclude_from_calibration_samples": True,
        "cells": cells,
    }


def summarize(rows: list[dict[str, object]], contract: dict[str, object], output: Path) -> dict[str, object]:
    decision = adjudicate(rows, contract)
    write_tsv(output / "heldout_cells.tsv", rows)
    (output / "decision.json").write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pull", type=Path)
    source.add_argument("--replay", type=Path, help="rebuild the decision from compact heldout_cells.tsv")
    parser.add_argument("--contract", type=Path, default=Path(__file__).with_name("contract.json"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    if args.replay is not None:
        with args.replay.open(newline="", encoding="utf-8") as stream:
            rows: list[dict[str, object]] = list(csv.DictReader(stream, delimiter="\t"))
        decision = summarize(rows, contract, args.output)
        print(f"replayed cells={len(rows)} verdict={decision['verdict']} passed={decision['passed_cells']}/4")
        return 0

    pull = args.pull
    assert pull is not None
    validate_pull_integrity(pull)
    controller = (pull / "controller.log").read_text(encoding="utf-8", errors="replace")
    completed = re.findall(r"^DONE_CELL_(\S+)$", controller, flags=re.MULTILINE)
    expected_completed = [cell_name(item) for item in contract["order"]]
    require(completed == expected_completed, f"controller cell order mismatch: {completed}")
    require("DONE_HELDOUT_CONTROLLER" in controller, "missing controller completion marker")
    rows: list[dict[str, object]] = []
    for expected in contract["order"]:
        name = cell_name(expected)
        cell = pull / "cells" / name
        status = dict(line.split("=", 1) for line in (cell / "exit_status.txt").read_text(encoding="utf-8").splitlines())
        require(status == {"bench_rc": "0", "sampler_rc": "0"}, f"bad exit status: {name}")
        command = (cell / "command.txt").read_text(encoding="utf-8")
        for token in ("--threads 4", "--seed 20260813", "--warmup 5", "--duration 20", "--idle 15", "--idle-trim", "--post-trim-ops-per-thread 4096", "--live-set 4096", "--idle-release 50", "--release-order high"):
            require(token in command, f"missing fixed token {token}: {name}")
        result = json.loads((cell / "result.json").read_text(encoding="utf-8"))
        require(result.get("mode") == "duration" and result.get("threads") == 4, f"mode/threads mismatch: {name}")
        require(result.get("seed") == 20260813 and result.get("warmup_s") == 5.0, f"seed/warmup mismatch: {name}")
        require(result.get("duration_s") == 20.0 and result.get("idle_s") == 15.0, f"duration/idle mismatch: {name}")
        require(result.get("post_trim_ops_per_thread") == 4096 and result.get("live_set_per_thread") == 4096, f"live/refault mismatch: {name}")
        require(result.get("idle_release_pct") == 50 and result.get("release_order") == "high" and result.get("idle_trim") is True, f"release/trim mismatch: {name}")
        if expected["profile"] == "mixed":
            require(result.get("profile") == "mixed", f"mixed profile mismatch: {name}")
        else:
            require(str(result.get("profile", "")).endswith("/medium_1k_16k.hist"), f"medium profile mismatch: {name}")
        xmls = sorted((cell / "xml").glob("*.xml"))
        require(len(xmls) == 4, f"XML count mismatch: {name}")
        for suffix in ("_measure.xml", "_release.xml", "_posttrim.xml", "_idle.xml"):
            require(sum(path.name.endswith(suffix) for path in xmls) == 1, f"XML phase missing: {name}:{suffix}")
        for path in xmls:
            ET.parse(path)
        samples = read_external(cell / "external_1s.tsv")
        meta = (cell / "external_sampler_meta.txt").read_text(encoding="utf-8").splitlines()
        require(meta.count("RC=0") == 1 and meta.count("DONE_EXTERNAL_SAMPLER") == 1, f"sampler marker mismatch: {name}")
        require([int(line.split("=", 1)[1]) for line in meta if line.startswith("samples=")] == [len(samples)], f"sampler count mismatch: {name}")
        memory, faults = result["memory"], result["memory"]["faults"]
        pre, post = int(memory["glibc_heap_pd_kb_pretrim"]), int(memory["glibc_heap_pd_kb_posttrim"])
        reclaimed, released = pre - post, int(result["idle_released_bytes"])
        require(pre > 0 and reclaimed >= 0 and released > 0, f"bad memory values: {name}")
        require(result["idle_trim_ret"] in (0, 1) and int(memory["trim_elapsed_ns"]) > 0, f"bad trim result: {name}")
        rows.append({
            "order": expected["order"], "elf": "gbs", "profile": expected["profile"], "rep": expected["rep"],
            "pretrim_glibc_pd_kb": pre, "posttrim_glibc_pd_kb": post, "reclaimed_kb": reclaimed,
            "reclaim_pct_of_pretrim": round(reclaimed * 100 / pre, 6),
            "reclaim_pct_of_released": round(reclaimed * 1024 * 100 / released, 6),
            "released_payload_bytes": released, "trim_return": result["idle_trim_ret"],
            "trim_elapsed_ms": round(int(memory["trim_elapsed_ns"]) / 1e6, 6),
            "posttrim_refault_elapsed_ms": round(int(memory["post_trim_elapsed_ns"]) / 1e6, 6),
            "trim_minflt": int(faults["minflt_posttrim"]) - int(faults["minflt_pretrim"]),
            "trim_majflt": int(faults["majflt_posttrim"]) - int(faults["majflt_pretrim"]),
            "refault_minflt": int(faults["minflt_postrefault"]) - int(faults["minflt_posttrim"]),
            "refault_majflt": int(faults["majflt_postrefault"]) - int(faults["majflt_posttrim"]),
            "external_samples": len(samples),
            "external_minflt_delta": int(samples[-1]["minflt"]) - int(samples[0]["minflt"]),
            "external_majflt_delta": int(samples[-1]["majflt"]) - int(samples[0]["majflt"]), "exit_code": 0,
        })

    before = (pull / "dmesg_before.txt").read_text(encoding="utf-8", errors="replace").splitlines()
    after = (pull / "dmesg_after.txt").read_text(encoding="utf-8", errors="replace").splitlines()
    increment, method = dmesg_increment(before, after)
    (args.output / "dmesg_increment.txt").write_text("\n".join(increment) + ("\n" if increment else ""), encoding="utf-8")
    bad_terms = ("out of memory", "oom", "lowmemory", "low memory", "lmk", "killed process")
    bad_lines = [line for line in increment if any(term in line.lower() for term in bad_terms)]
    z_before = [int(value) for value in (pull / "zram_mm_stat_before.txt").read_text().split()]
    z_after = [int(value) for value in (pull / "zram_mm_stat_after.txt").read_text().split()]
    require(len(z_before) >= 3 and len(z_after) >= 3, "short zram mm_stat")
    health = {
        "dmesg_increment_method": method, "dmesg_increment_lines": len(increment), "oom_lmk_matches": bad_lines,
        "zram_original_data_size_delta": z_after[0] - z_before[0],
        "zram_compressed_data_size_delta": z_after[1] - z_before[1],
        "zram_mem_used_total_delta": z_after[2] - z_before[2],
        "governor_restored_schedutil_count": (pull / "governor_after.txt").read_text().count("=schedutil"),
        "trim_majflt_max": max(int(row["trim_majflt"]) for row in rows),
        "refault_majflt_max": max(int(row["refault_majflt"]) for row in rows),
        "reclaimed_4k_aligned_count": sum((int(row["reclaimed_kb"]) * 1024) % 4096 == 0 for row in rows),
        "reclaimed_4k_aligned_total": len(rows),
        "trim_elapsed_ms_max": max(float(row["trim_elapsed_ms"]) for row in rows),
    }
    require(not bad_lines, "OOM/LMK evidence found")
    require(all(health[key] == 0 for key in ("zram_original_data_size_delta", "zram_compressed_data_size_delta", "zram_mem_used_total_delta")), "zram delta is non-zero")
    require(health["governor_restored_schedutil_count"] == 4, "governor restore mismatch")
    require(health["trim_majflt_max"] == health["refault_majflt_max"] == 0, "major fault gate failed")
    require(health["reclaimed_4k_aligned_count"] == len(rows), "reclaim page-alignment gate failed")
    require(health["trim_elapsed_ms_max"] < 20.0, "A-anchor trim time gate failed")
    decision = summarize(rows, contract, args.output)
    (args.output / "health.json").write_text(json.dumps(health, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"validated cells={len(rows)} verdict={decision['verdict']} passed={decision['passed_cells']}/4")
    for item in decision["cells"]:
        print(f"{item['order']:02d} {item['profile']} rep{item['rep']} observed={item['observed_pct']:.6f} band=[{item['lower_pct']:.6f},{item['upper_pct']:.6f}] in_band={str(item['in_band']).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
