#!/usr/bin/env python3
"""Audit configured Tizen RPM metadata for Demo-tool provenance."""

from __future__ import annotations

import argparse
import configparser
import csv
import datetime as dt
import gzip
import hashlib
import json
import re
import shutil
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


COMMON = "{http://linux.duke.edu/metadata/common}"
RPM = "{http://linux.duke.edu/metadata/rpm}"
FILELISTS = "{http://linux.duke.edu/metadata/filelists}"
REPO = "{http://linux.duke.edu/metadata/repo}"
TARGETS = {
    "alloc_bench": "allocbench",
    "gst_loop_decode": "gstloopdecode",
    "reclaim_probe": "reclaimprobe",
}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(url: str, path: Path, reuse_cache: bool = False) -> None:
    if reuse_cache and path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "glibc-memopt-provenance-audit/1"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response, path.open("wb") as output:
                shutil.copyfileobj(response, output)
            return
        except Exception:
            path.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def parse_configs(paths: list[Path]) -> list[dict[str, str]]:
    repos: list[dict[str, str]] = []
    for path in paths:
        parser = configparser.ConfigParser(interpolation=None)
        with path.open(encoding="utf-8") as stream:
            parser.read_file(stream)
        for section in parser.sections():
            if section.startswith("repo.") and parser.has_option(section, "url"):
                repos.append(
                    {
                        "config": path.as_posix(),
                        "repo": section,
                        "url": parser.get(section, "url").rstrip("/") + "/",
                    }
                )
    return repos


def parse_buildrequires(spec: Path) -> list[str]:
    requirements: list[str] = []
    for line in spec.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^BuildRequires:\s*([^\s]+)", line)
        if match:
            requirements.append(match.group(1))
    return requirements


def metadata_record(repomd: Path, kind: str) -> dict[str, str]:
    root = ET.parse(repomd).getroot()
    node = root.find(f"{REPO}data[@type='{kind}']")
    if node is None:
        raise ValueError(f"{repomd}: missing {kind} metadata")
    location = node.find(f"{REPO}location")
    checksum = node.find(f"{REPO}checksum")
    if location is None or checksum is None or not checksum.text:
        raise ValueError(f"{repomd}: incomplete {kind} metadata record")
    return {
        "href": location.attrib["href"],
        "checksum_type": checksum.attrib.get("type", ""),
        "checksum": checksum.text.strip(),
    }


def check_metadata_checksum(path: Path, record: dict[str, str]) -> None:
    if record["checksum_type"] != "sha256":
        raise ValueError(f"{path}: unsupported checksum {record['checksum_type']}")
    actual = sha256(path)
    if actual != record["checksum"]:
        raise ValueError(f"{path}: checksum {actual} != {record['checksum']}")


def find_target(value: str) -> list[str]:
    candidate = normalize(value)
    return [name for name, token in TARGETS.items() if token in candidate]


def scan_primary(path: Path, requirements: list[str]) -> tuple[int, list[dict[str, str]], list[dict[str, str]]]:
    package_count = 0
    hits: list[dict[str, str]] = []
    packages: list[dict[str, str]] = []
    with gzip.open(path, "rb") as stream:
        for _, package in ET.iterparse(stream, events=("end",)):
            if package.tag != COMMON + "package":
                continue
            package_count += 1
            name = package.findtext(COMMON + "name") or ""
            arch = package.findtext(COMMON + "arch") or ""
            version = package.find(COMMON + "version")
            version_data = {
                "epoch": version.attrib.get("epoch", "") if version is not None else "",
                "version": version.attrib.get("ver", "") if version is not None else "",
                "release": version.attrib.get("rel", "") if version is not None else "",
            }
            if name in requirements and arch == "armv7l":
                packages.append({"requirement": name, "arch": arch, **version_data})
            for target in find_target(name):
                hits.append({"target": target, "dimension": "package-name", "package": name, "value": name})
            fmt = package.find(COMMON + "format")
            provides = fmt.find(RPM + "provides") if fmt is not None else None
            if provides is not None:
                for entry in provides.findall(RPM + "entry"):
                    provided = entry.attrib.get("name", "")
                    for target in find_target(provided):
                        hits.append(
                            {"target": target, "dimension": "provides", "package": name, "value": provided}
                        )
            package.clear()
    return package_count, hits, packages


def scan_filelists(path: Path) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    with gzip.open(path, "rb") as stream:
        for _, package in ET.iterparse(stream, events=("end",)):
            if package.tag != FILELISTS + "package":
                continue
            name = package.attrib.get("name", "")
            for node in package.findall(FILELISTS + "file"):
                value = node.text or ""
                for target in find_target(value):
                    hits.append({"target": target, "dimension": "file-list", "package": name, "value": value})
            package.clear()
    return hits


def write_tsv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", action="append", required=True, type=Path)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reuse-cache", action="store_true")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    requirements = parse_buildrequires(args.spec)
    repos = parse_configs(args.config)
    repo_rows: list[dict[str, object]] = []
    hit_rows: list[dict[str, object]] = []
    build_rows: list[dict[str, object]] = []

    for index, repo in enumerate(repos, start=1):
        key = f"repo{index}-{Path(repo['config']).stem}-{repo['repo'].removeprefix('repo.')}"
        cache = args.cache_dir / key
        repomd = cache / "repomd.xml"
        fetch(urllib.parse.urljoin(repo["url"], "repodata/repomd.xml"), repomd, args.reuse_cache)
        root = ET.parse(repomd).getroot()
        revision = root.findtext(REPO + "revision") or ""
        revision_utc = ""
        if revision.isdigit():
            revision_utc = dt.datetime.fromtimestamp(int(revision), tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")
        records = {kind: metadata_record(repomd, kind) for kind in ("primary", "filelists")}
        local: dict[str, Path] = {}
        for kind, record in records.items():
            local[kind] = cache / Path(record["href"]).name
            fetch(urllib.parse.urljoin(repo["url"], record["href"]), local[kind], args.reuse_cache)
            check_metadata_checksum(local[kind], record)

        package_count, primary_hits, packages = scan_primary(local["primary"], requirements)
        hits = primary_hits + scan_filelists(local["filelists"])
        for row in sorted(hits, key=lambda item: (item["target"], item["dimension"], item["package"], item["value"])):
            hit_rows.append({**repo, **row})
        package_by_name = {row["requirement"]: row for row in packages}
        for requirement in requirements:
            package = package_by_name.get(requirement)
            build_rows.append(
                {
                    **repo,
                    "requirement": requirement,
                    "status": "FOUND" if package else "NOT-IN-REPO",
                    "arch": package["arch"] if package else "-",
                    "epoch": package["epoch"] if package else "-",
                    "version": package["version"] if package else "-",
                    "release": package["release"] if package else "-",
                    "nvr": f"{requirement}-{package['version']}-{package['release']}" if package else "-",
                }
            )
        repo_rows.append(
            {
                **repo,
                "repomd_revision": revision,
                "repomd_revision_utc": revision_utc,
                "repomd_sha256": sha256(repomd),
                "primary_href": records["primary"]["href"],
                "primary_sha256": records["primary"]["checksum"],
                "filelists_href": records["filelists"]["href"],
                "filelists_sha256": records["filelists"]["checksum"],
                "package_count": package_count,
                "tool_hit_count": len(hits),
            }
        )

    write_tsv(
        args.output / "repos.tsv",
        ["config", "repo", "url", "repomd_revision", "repomd_revision_utc", "repomd_sha256", "primary_href", "primary_sha256", "filelists_href", "filelists_sha256", "package_count", "tool_hit_count"],
        repo_rows,
    )
    write_tsv(
        args.output / "tool_hits.tsv",
        ["config", "repo", "url", "target", "dimension", "package", "value"],
        hit_rows,
    )
    write_tsv(
        args.output / "buildrequires.tsv",
        ["config", "repo", "url", "requirement", "status", "arch", "epoch", "version", "release", "nvr"],
        build_rows,
    )
    summary = {
        "schema": "glibc-memopt-tool-provenance-audit.v1",
        "configs": [path.as_posix() for path in args.config],
        "repositories": len(repo_rows),
        "targets": {name: [name, name.replace("_", "-")] for name in TARGETS},
        "matching": "case-insensitive alphanumeric normalization of package name, Provide name, or complete file path",
        "buildrequires": requirements,
        "tool_hits": len(hit_rows),
        "outcome": "ZERO_HITS" if not hit_rows else "UNEXPECTED_HITS",
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"REPOS\t{len(repo_rows)}")
    print(f"TOOL_HITS\t{len(hit_rows)}")
    print(f"OUTCOME\t{summary['outcome']}")
    return 3 if hit_rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
