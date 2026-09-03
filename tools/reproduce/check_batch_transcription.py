#!/usr/bin/env python3
"""Require every compact batch row to match its cited source-document row."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--input", type=Path, default=Path("data/raw/demo_reproduction_20260901/batch_release_phase.tsv"))
    args = parser.parse_args()
    root = args.repo_root.resolve()
    input_path = args.input if args.input.is_absolute() else root / args.input
    with input_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    if len(rows) != 11:
        raise ValueError(f"expected 11 compact rows, got {len(rows)}")
    for row in rows:
        relative, line_text = row["source_report_row"].rsplit(":", 1)
        line_number = int(line_text)
        source = (root / relative).read_text(encoding="utf-8").splitlines()
        if line_number < 1 or line_number > len(source):
            raise ValueError(f"source row outside file: {row['source_report_row']}")
        cited = source[line_number - 1]
        expected = (f"{row['reclaimed_mib']} MiB", f"{row['reclaim_pct']}%")
        missing = [value for value in expected if value not in cited]
        if missing:
            raise ValueError(f"transcription mismatch {row['series']}/{row['unit']}: missing {missing} in {row['source_report_row']}")
        print(f"PASS\t{row['series']}/{row['unit']}\t{row['source_report_row']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
