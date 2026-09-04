#!/usr/bin/env python3
"""Estimate page-interior capacity from glibc malloc_info histograms.

The primary estimate intentionally uses only ``<size>`` buckets.  It is a
geometric estimate: for every reported free chunk, the lower bound assumes
the smallest bucket member and worst possible page alignment; the upper bound
assumes the largest bucket member and best possible page alignment.  It does
not claim that malloc_trim can actually return those pages.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_PAGE_SIZE = 4096


class EstimatorError(ValueError):
    """Raised for malformed or unsupported malloc_info input."""


@dataclass(frozen=True)
class Bounds:
    chunk_count: int = 0
    histogram_total_bytes: int = 0
    lower_bytes: int = 0
    upper_bytes: int = 0

    def add(self, other: "Bounds") -> "Bounds":
        return Bounds(
            self.chunk_count + other.chunk_count,
            self.histogram_total_bytes + other.histogram_total_bytes,
            self.lower_bytes + other.lower_bytes,
            self.upper_bytes + other.upper_bytes,
        )


def _integer_attribute(element: ET.Element, name: str) -> int:
    raw = element.get(name)
    if raw is None:
        raise EstimatorError(f"<{element.tag}> is missing {name!r}")
    try:
        value = int(raw, 10)
    except ValueError as exc:
        raise EstimatorError(
            f"<{element.tag}> has non-integer {name!r}: {raw!r}"
        ) from exc
    if value < 0:
        raise EstimatorError(f"<{element.tag}> has negative {name!r}: {value}")
    return value


def _bucket_bounds(element: ET.Element, page_size: int) -> Bounds:
    lower_size = _integer_attribute(element, "from")
    upper_size = _integer_attribute(element, "to")
    total = _integer_attribute(element, "total")
    count = _integer_attribute(element, "count")
    if count == 0:
        if total != 0:
            raise EstimatorError(
                f"<{element.tag}> count=0 but total={total}"
            )
        return Bounds()
    if lower_size > upper_size:
        raise EstimatorError(
            f"<{element.tag}> from={lower_size} exceeds to={upper_size}"
        )
    if not lower_size * count <= total <= upper_size * count:
        raise EstimatorError(
            f"<{element.tag}> total={total} is outside "
            f"[{lower_size * count}, {upper_size * count}]"
        )

    # For a byte interval of length n, an unknown start alignment leaves at
    # most page_size-1 leading bytes before the first wholly-contained page.
    pages_per_chunk_lower = max(0, (lower_size - (page_size - 1)) // page_size)
    pages_per_chunk_upper = upper_size // page_size
    return Bounds(
        chunk_count=count,
        histogram_total_bytes=total,
        lower_bytes=pages_per_chunk_lower * page_size * count,
        upper_bytes=pages_per_chunk_upper * page_size * count,
    )


def _sum_bounds(elements: Iterable[ET.Element], page_size: int) -> Bounds:
    result = Bounds()
    for element in elements:
        result = result.add(_bucket_bounds(element, page_size))
    return result


def estimate_xml(path: Path, page_size: int = DEFAULT_PAGE_SIZE) -> dict:
    """Return per-arena and aggregate estimates for one malloc_info XML."""
    if page_size <= 0:
        raise EstimatorError("page size must be positive")
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise EstimatorError(f"cannot parse {path}: {exc}") from exc
    if root.tag != "malloc":
        raise EstimatorError(f"expected <malloc> root, got <{root.tag}>")

    arenas: list[dict] = []
    total = Bounds()
    excluded_unsorted = Bounds()
    seen_numbers: set[int] = set()
    for heap in root.findall("heap"):
        nr = _integer_attribute(heap, "nr")
        if nr in seen_numbers:
            raise EstimatorError(f"duplicate heap nr={nr}")
        seen_numbers.add(nr)
        sizes = heap.find("sizes")
        size_elements = [] if sizes is None else list(sizes.findall("size"))
        unsorted_elements = [] if sizes is None else list(sizes.findall("unsorted"))
        bounds = _sum_bounds(size_elements, page_size)
        unsorted = _sum_bounds(unsorted_elements, page_size)
        total = total.add(bounds)
        excluded_unsorted = excluded_unsorted.add(unsorted)
        arenas.append(
            {
                "arena": nr,
                **asdict(bounds),
                "excluded_unsorted": asdict(unsorted),
            }
        )

    if not arenas:
        raise EstimatorError("malloc_info XML contains no <heap> entries")
    return {
        "schema": "glibc-memopt.trimmable-estimate.v1",
        "source": str(path),
        "page_size": page_size,
        "method": "size-buckets/from-to/worst-best-alignment",
        "arenas": arenas,
        "total": asdict(total),
        "excluded_unsorted": asdict(excluded_unsorted),
    }


def _print_tsv(estimates: list[dict]) -> None:
    columns = (
        "source",
        "arena",
        "chunk_count",
        "histogram_total_bytes",
        "lower_bytes",
        "upper_bytes",
        "excluded_unsorted_chunk_count",
        "excluded_unsorted_total_bytes",
    )
    print("\t".join(columns))
    for estimate in estimates:
        for arena in estimate["arenas"]:
            unsorted = arena["excluded_unsorted"]
            row = (
                estimate["source"],
                arena["arena"],
                arena["chunk_count"],
                arena["histogram_total_bytes"],
                arena["lower_bytes"],
                arena["upper_bytes"],
                unsorted["chunk_count"],
                unsorted["histogram_total_bytes"],
            )
            print("\t".join(map(str, row)))
        total = estimate["total"]
        unsorted = estimate["excluded_unsorted"]
        row = (
            estimate["source"],
            "TOTAL",
            total["chunk_count"],
            total["histogram_total_bytes"],
            total["lower_bytes"],
            total["upper_bytes"],
            unsorted["chunk_count"],
            unsorted["histogram_total_bytes"],
        )
        print("\t".join(map(str, row)))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xml", nargs="+", type=Path, help="malloc_info XML input")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--format", choices=("json", "tsv"), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        estimates = [estimate_xml(path, args.page_size) for path in args.xml]
    except EstimatorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.format == "tsv":
        _print_tsv(estimates)
    else:
        json.dump(estimates[0] if len(estimates) == 1 else estimates, sys.stdout,
                  ensure_ascii=False, indent=2, sort_keys=True)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
