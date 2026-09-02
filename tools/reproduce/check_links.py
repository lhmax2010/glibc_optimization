#!/usr/bin/env python3
"""Check repository-local links and anchors in Demo entry documents."""

from __future__ import annotations

import argparse
import re
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path


MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
EXPLICIT_ID = re.compile(r"<a\s+[^>]*id=[\"']([^\"']+)[\"']", re.IGNORECASE)


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.hrefs.append(values["href"] or "")
        if values.get("id"):
            self.ids.add(values["id"] or "")


def markdown_slug(title: str) -> str:
    title = re.sub(r"`([^`]*)`", r"\1", title.strip().lower())
    title = re.sub(r"[^\w\-\s\u4e00-\u9fff]", "", title)
    return re.sub(r"\s+", "-", title)


def anchors(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".html":
        parser = Links(); parser.feed(text)
        return parser.ids
    found = set(EXPLICIT_ID.findall(text))
    counts: dict[str, int] = {}
    for line in text.splitlines():
        match = HEADING.match(line)
        if not match:
            continue
        base = markdown_slug(match.group(1))
        count = counts.get(base, 0)
        counts[base] = count + 1
        found.add(base if count == 0 else f"{base}-{count}")
    return found


def links(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".html":
        parser = Links(); parser.feed(text)
        return parser.hrefs
    return MARKDOWN_LINK.findall(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    failures: list[str] = []
    checked = 0
    for source in args.paths:
        if not source.is_file():
            failures.append(f"missing source: {source}")
            continue
        for raw in links(source):
            target = raw.strip().strip("<>")
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            decoded = urllib.parse.unquote(target)
            file_part, marker, anchor = decoded.partition("#")
            destination = source if not file_part else (source.parent / file_part).resolve()
            checked += 1
            if not destination.exists():
                failures.append(f"{source}: missing {target}")
                continue
            if marker and anchor and destination.is_file() and anchor not in anchors(destination):
                failures.append(f"{source}: missing anchor {target}")
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        print(f"checked={checked} failures={len(failures)}")
        return 1
    print(f"PASS local-links checked={checked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
