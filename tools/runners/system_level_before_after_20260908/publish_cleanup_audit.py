#!/usr/bin/env python3
"""Publish delayed cleanup logs verbatim except explicit redaction, including STOP."""
import argparse
import datetime
import json
import ipaddress
import pathlib
import re
import tempfile

from publish_execution_log import no_symlink, render_public, sha


def network_endpoints(data, board_ip, host_ip):
    """Explicit routing aliases, including proc-net little-endian encodings."""
    text=data.decode('utf-8')
    edits=[]
    for address,alias,label in ((board_ip,'<TEST_BOARD_IP>','BOARD_ENDPOINT_REPLACED'),
                               (host_ip,'<HOST_IP>','HOST_ENDPOINT_REPLACED')):
        value=ipaddress.IPv4Address(address)
        little=value.packed[::-1].hex().upper()
        for source in ('0000000000000000FFFF0000'+little,little):
            text,n=re.subn(r'(?<![0-9A-Fa-f])'+source+r'(?=:[0-9A-Fa-f]{4}\b)',alias,text,flags=re.I)
            if n and label not in edits:
                edits.append(label)
        if str(value) in text:
            text=text.replace(str(value),alias)
            if label not in edits:
                edits.append(label)
    return text.encode('utf-8'),edits


def publish(run, output, ip, host_home, host_ip=None):
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
            if host_ip is not None:
                public,network_edits=network_endpoints(public,ip,host_ip)
                edits+=network_edits
            path = staged / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(public)
            records.append({"path": relative, "original_sha256": sha(data), "public_sha256": sha(public), "edits": edits})
        (staged / "manifest.json").write_text(json.dumps({
            "schema": "system-before-after.delayed-cleanup-publication.v1",
            "verdict": receipt["verdict"], "scope": "cleanup only; no measurement rerun or changed measurement source",
            "editing": "CR removed; board address and host home mapped; board runtime paths retained" + (
                "; board/host proc-net hexadecimal endpoints mapped, ports/states retained" if host_ip else ""),
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
    parser.add_argument("--host-ip", help="explicit host routing alias; also redact proc-net hexadecimal endpoints")
    args = parser.parse_args()
    publish(args.run, args.output_dir, args.ip, args.host_home, args.host_ip)


if __name__ == "__main__":
    main()
