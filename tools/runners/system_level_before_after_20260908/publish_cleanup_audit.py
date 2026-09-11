#!/usr/bin/env python3
"""Publish delayed cleanup logs verbatim except explicit redaction, including STOP."""
import argparse
import datetime
import json
import pathlib
import tempfile

from publish_execution_log import no_symlink, render_public, sha


def publish(run, output, ip, host_home):
    run, output = pathlib.Path(run).absolute(), pathlib.Path(output).absolute()
    for path in (run, output):
        no_symlink(path)
        if ".." in path.parts:
            raise ValueError("parent traversal rejected")
    if output.exists() or run == output or run in output.parents or output in run.parents:
        raise ValueError("publication must be new and separate from original logs")
    original = (run / "audit.json").read_bytes()
    receipt = json.loads(original)
    if receipt.get("verdict") not in ("STOP", "PASS_READONLY_CLEANUP") or not receipt.get("end_utc"):
        raise ValueError("audit is not terminal")
    if datetime.datetime.fromisoformat(receipt["end_utc"]).tzinfo is None:
        raise ValueError("audit end time must have timezone")
    authority = receipt.get("root_authorization")
    if authority and authority.get("root_off") not in ("PASS_NONROOT", "FAIL"):
        raise ValueError("root lifecycle is not terminal")
    if receipt["verdict"] == "PASS_READONLY_CLEANUP":
        if authority and (authority["root_off"] != "PASS_NONROOT" or authority.get("recording_error")):
            raise ValueError("cannot publish PASS without non-root restoration")
        if not authority and not receipt.get("id_final", "").startswith("uid=5001("):
            raise ValueError("cannot publish PASS without final non-root ID")
    selected = [p for p in sorted(run.rglob("*")) if p.suffix in (".txt", ".json", ".tsv")]
    captured = {}
    for path in selected:
        no_symlink(path)
        if not path.is_file():
            raise ValueError("selected log is not a regular file")
        captured[path.relative_to(run).as_posix()] = path.read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".cleanup-publication-", dir=output.parent) as temporary:
        staged = pathlib.Path(temporary) / "publication"
        staged.mkdir()
        records = []
        for relative, data in captured.items():
            public, edits = render_public(data, ip, host_home)
            path = staged / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(public)
            records.append({"path": relative, "original_sha256": sha(data), "public_sha256": sha(public), "edits": edits})
        (staged / "manifest.json").write_text(json.dumps({
            "schema": "system-before-after.delayed-cleanup-publication.v1",
            "verdict": receipt["verdict"], "scope": "cleanup only; no measurement rerun or changed measurement source",
            "editing": "CR removed; board address and host home mapped; board runtime paths retained",
            "files": records}, indent=2) + "\n")
        for relative, data in captured.items():
            if (run / relative).read_bytes() != data:
                raise ValueError("audit logs changed during publication")
        if (run / "audit.json").read_bytes() != original:
            raise ValueError("terminal receipt changed during publication")
        staged.rename(output)
    print("PASS cleanup log publication files=%d verdict=%s" % (len(records), receipt["verdict"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=pathlib.Path)
    parser.add_argument("--output-dir", required=True, type=pathlib.Path)
    parser.add_argument("--ip", required=True)
    parser.add_argument("--host-home", required=True)
    args = parser.parse_args()
    publish(args.run, args.output_dir, args.ip, args.host_home)


if __name__ == "__main__":
    main()
