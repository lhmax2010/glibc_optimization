#!/usr/bin/env python3
"""Build a validation table for trimmable_estimator from a case manifest."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from trimmable_estimator import EstimatorError, estimate_xml


FIELDS = (
    "case",
    "source_round",
    "profile",
    "cell",
    "validation_status",
    "xml",
    "size_chunk_count",
    "size_histogram_total_bytes",
    "estimate_lower_bytes",
    "estimate_upper_bytes",
    "excluded_unsorted_total_bytes",
    "measured_reclaimed_bytes",
    "lower_error_bytes",
    "upper_error_bytes",
    "measured_within_bounds",
)


def build_rows(manifest: Path, page_size: int = 4096) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with manifest.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {
            "case", "source_round", "profile", "cell", "validation_status",
            "xml", "measured_reclaimed_kb",
        }
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise EstimatorError(f"case manifest missing columns: {sorted(required)}")
        for item in reader:
            status = item["validation_status"]
            if status not in {"paired", "no_trim_invoked", "xml_not_collected"}:
                raise EstimatorError(f"unknown validation_status: {status!r}")
            estimate = None
            if item["xml"] != "-":
                xml_path = manifest.parent / item["xml"]
                estimate = estimate_xml(xml_path, page_size)
            elif status != "xml_not_collected":
                raise EstimatorError(f"{item['case']}: XML required for {status}")

            measured = item["measured_reclaimed_kb"]
            if status == "paired":
                try:
                    measured_bytes = int(measured, 10) * 1024
                except ValueError as exc:
                    raise EstimatorError(
                        f"{item['case']}: paired case needs integer measured_reclaimed_kb"
                    ) from exc
            else:
                if measured != "-":
                    raise EstimatorError(
                        f"{item['case']}: unpaired case must use '-' measured value"
                    )
                measured_bytes = None

            output = {key: item[key] for key in (
                "case", "source_round", "profile", "cell", "validation_status", "xml"
            )}
            if estimate is None:
                output.update({field: "-" for field in FIELDS[6:]})
            else:
                total = estimate["total"]
                lower = int(total["lower_bytes"])
                upper = int(total["upper_bytes"])
                output.update({
                    "size_chunk_count": str(total["chunk_count"]),
                    "size_histogram_total_bytes": str(total["histogram_total_bytes"]),
                    "estimate_lower_bytes": str(lower),
                    "estimate_upper_bytes": str(upper),
                    "excluded_unsorted_total_bytes": str(
                        estimate["excluded_unsorted"]["histogram_total_bytes"]
                    ),
                })
                if measured_bytes is None:
                    output.update({field: "-" for field in FIELDS[11:]})
                else:
                    output.update({
                        "measured_reclaimed_bytes": str(measured_bytes),
                        "lower_error_bytes": str(lower - measured_bytes),
                        "upper_error_bytes": str(upper - measured_bytes),
                        "measured_within_bounds": str(lower <= measured_bytes <= upper).lower(),
                    })
            rows.append(output)
    return rows


def write_rows(rows: list[dict[str, str]], output: Path | None) -> None:
    handle = output.open("w", newline="", encoding="utf-8") if output else sys.stdout
    try:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if output:
            handle.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--page-size", type=int, default=4096)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        rows = build_rows(args.cases, args.page_size)
        write_rows(rows, args.output)
    except (EstimatorError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
