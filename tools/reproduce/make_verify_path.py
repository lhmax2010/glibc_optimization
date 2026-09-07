#!/usr/bin/env python3
"""Create a closed command whitelist for default-verify delivery tests."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


COMMANDS = Path(__file__).with_name("verify_commands.txt")


def create(destination: Path, source_path: str, profile: str) -> None:
    commands = COMMANDS.read_text(encoding="utf-8").split()
    resolved = {name: shutil.which(name, path=source_path) for name in commands}
    missing = [name for name, executable in resolved.items() if executable is None]
    if missing:
        raise ValueError("missing default-verify commands: " + ", ".join(missing))
    destination.mkdir(parents=True, exist_ok=False)
    for name, executable in resolved.items():
        (destination / name).symlink_to(Path(executable).resolve())

    def stub(name: str, body: str) -> None:
        target = destination / name
        target.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        target.chmod(0o755)

    poison = ('printf "%s\\n" "$0" >> "${PREDELIVERY_OPTIONAL_TOOL_MARKER:?}"\nexit 97\n')
    if profile in ("present-gbs+present-rpm", "present-gbs+absent-rpm"):
        stub("gbs", poison)
    if profile in ("present-gbs+present-rpm", "absent-gbs+present-rpm"):
        for name in ("rpm", "rpm2cpio", "cpio"):
            stub(name, poison)
        stub("rpmspec", '[ "$#" -eq 2 ] && [ "$1" = "-P" ] || exit 97\ncat "$2"\n')
    if profile == "broken-tools":
        stub("gbs", poison)
        stub("rpmspec", 'printf "fixture: rpmspec environment unusable\\n" >&2\nexit 42\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", required=True, choices=(
        "present-gbs+present-rpm", "absent-gbs+present-rpm",
        "present-gbs+absent-rpm", "minimal-whitelist", "broken-tools",
    ))
    args = parser.parse_args()
    try:
        create(args.output, os.environ.get("PATH", ""), args.profile)
    except (OSError, ValueError) as error:
        parser.exit(2, f"FAIL verify-path: {error}\n")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
