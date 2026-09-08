#!/usr/bin/env python3
"""Export compact transcriptions only after complete-matrix + cleanup PASS.

Public output is parsed evidence, not a claim that full raw files are in Git.
Each original point file and verified pull manifest remains hash-referenced.
"""
import argparse
import hashlib
import json
import pathlib
import re
import tempfile
from collect_cell import ANALYSIS
from replay_compact import CONTRACT, replay


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_manifest(run, raw, name):
    manifest = json.loads((run / (name + ".integrity.json")).read_text())
    if manifest.get("verdict") != "PASS" or not manifest.get("files"):
        raise ValueError("pull manifest is not verified: " + name)
    archive = run / (name + ".tar.gz")
    if archive.is_symlink() or not archive.is_file() or digest(archive) != manifest.get("archive_sha256"):
        raise ValueError("pulled archive changed before publication: " + name)
    for relative, expected in manifest["files"].items():
        parts = pathlib.PurePosixPath(relative)
        if (parts.is_absolute() or ".." in parts.parts or not parts.parts
                or parts.parts[0] != name or not re.fullmatch(r"[a-f0-9]{64}", expected)):
            raise ValueError("unsafe pull manifest entry: " + relative)
        path = raw
        for component in parts.parts:
            path = path / component
            if path.is_symlink():
                raise ValueError("symlink in pulled evidence: " + relative)
        if not path.is_file() or digest(path) != expected:
            raise ValueError("pulled evidence changed before publication: " + relative)
    for point in (raw / name / "points").rglob("*"):
        if point.is_symlink() or (point.is_file() and point.relative_to(raw).as_posix() not in manifest["files"]):
            raise ValueError("point file absent from verified pull manifest: " + str(point.relative_to(raw)))
    return manifest


def publish_to_staging(run, output):
    receipt = json.loads((run / "execution.json").read_text())
    if receipt["verdict"] != "PASS_COMPLETE_MATRIX" or receipt["cleanup"] != "PASS":
        raise ValueError("incomplete/failed matrix must not publish Demo headline evidence")
    raw = run / "raw"
    manifests = {cell["id"]: verified_manifest(run, raw, cell["id"]) for cell in CONTRACT["cells"]}
    rows = ANALYSIS.analyze(raw, CONTRACT)
    source = {"schema": "system-before-after.parsed-points.v1", "contract_tag": CONTRACT["contract_tag"],
              "scope": "parsed transcription; complete raw evidence retained locally and available on request",
              "points": [], "cell_health": {}, "pull_manifests": {}}
    for cell in CONTRACT["cells"]:
        name = cell["id"]
        path = raw / name
        source["cell_health"][name] = json.loads((path / "cell.json").read_text())
        source["pull_manifests"][name] = manifests[name]
        metrics = json.loads((path / "metrics.json").read_text())
        for metric in metrics:
            entry = {"id": name, "cycle": metric["cycle"], "metric": metric, "raw_point_sha256": {}}
            for phase in ("pre", "post"):
                point = path / "points" / ("%02d_%s" % (metric["cycle"], phase))
                entry[phase] = ANALYSIS.read_point(point)
                entry["raw_point_sha256"][phase] = {p.name: digest(p) for p in sorted(point.iterdir()) if p.is_file()}
            if cell["group"] == "G4":
                entry["idle_pre"] = ANALYSIS.proc_stat((path / "idle_stat_start.txt").read_text())
                entry["idle_post"] = ANALYSIS.proc_stat((path / "idle_stat_end.txt").read_text())
            source["points"].append(entry)
    # Observe the existing function's canonical GST input, then run its unchanged
    # statistical implementation. No duplicate quantile/dispersion logic.
    gst_rows = []
    original = ANALYSIS.GST.derive_cycle_summaries
    def capture(values):
        gst_rows.extend(values)
        return original(values)
    ANALYSIS.GST.derive_cycle_summaries = capture
    try:
        ANALYSIS.gst_summaries(raw, rows)
    finally:
        ANALYSIS.GST.derive_cycle_summaries = original
    output.mkdir(parents=True, exist_ok=False)
    (output / "point_source.json").write_text(json.dumps(source, indent=2, allow_nan=False) + "\n")
    ANALYSIS.GST.write_tsv(output / "gst_cycles.tsv", gst_rows)
    with tempfile.TemporaryDirectory(prefix="system-compact-replay-") as directory:
        replay(source, output / "gst_cycles.tsv", pathlib.Path(directory))
        for name in ("cycles.tsv", "summary.tsv", "gst_repetitions.tsv", "gst_arms.tsv", "gst_comparison.json"):
            derived = run / "derived" / name
            rebuilt = pathlib.Path(directory) / name
            if derived.read_bytes() != rebuilt.read_bytes():
                raise ValueError("compact/full derivation byte mismatch: " + name)
            (output / name).write_bytes(derived.read_bytes())
    (output / "execution.json").write_text(json.dumps(receipt, indent=2) + "\n")


def publish(run, output):
    if output.exists():
        raise ValueError("refuse to overwrite public evidence")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".system-publication-", dir=output.parent) as directory:
        staged = pathlib.Path(directory) / "publication"
        publish_to_staging(run, staged)
        staged.rename(output)
    print("PASS public compact/full derivation cmp=5 cells=21 cycles=333")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", required=True, type=pathlib.Path)
    p.add_argument("--output-dir", required=True, type=pathlib.Path)
    a = p.parse_args()
    publish(a.run, a.output_dir)


if __name__ == "__main__":
    main()
