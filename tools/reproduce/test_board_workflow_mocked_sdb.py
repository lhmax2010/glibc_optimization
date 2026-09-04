#!/usr/bin/env python3
"""Host-only SHA-source contract tests for the board workflow."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
WORKFLOW = HERE / "board_workflow.sh"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BoardWorkflowShaContractTests(unittest.TestCase):
    def test_remote_runners_require_injected_sha_contracts(self) -> None:
        value = "a" * 64
        s4 = subprocess.run(
            ["sh", str(REPO / "tools/runners/s4_retention_20260901/run_s4_remote.sh"), "--sha-contract-only"],
            env={**os.environ, "EXPECTED_ALLOC_SHA": value}, text=True, capture_output=True, check=False,
        )
        self.assertEqual(s4.returncode, 0, s4.stderr)
        self.assertIn(f"alloc_bench.armv7l={value}", s4.stdout)
        gst = subprocess.run(
            ["sh", str(REPO / "tools/runners/gst_trim_cost_20260901/run_gst_trim_cost_remote.sh"), "--sha-contract-only"],
            env={
                **os.environ,
                "EXPECTED_GST_SHA": "b" * 64,
                "EXPECTED_RECLAIM_SHA": "c" * 64,
                "EXPECTED_MEDIA_SHA": "d" * 64,
            },
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(gst.returncode, 0, gst.stderr)
        self.assertIn(f"gst_loop_decode.armv7l={'b' * 64}", gst.stdout)
        self.assertIn(f"reclaim_probe.armv7l={'c' * 64}", gst.stdout)
        self.assertIn(f"small_320x240.mp4={'d' * 64}", gst.stdout)

    def test_all_manifest_sha_sources_reach_both_remote_invocations(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glibc-memopt-mocked-sdb-") as directory:
            root = Path(directory)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            names = (
                "alloc_bench.armv7l",
                "gst_loop_decode.armv7l",
                "reclaim_probe.armv7l",
                "small_320x240.mp4",
            )
            for index, name in enumerate(names, 1):
                (artifacts / name).write_bytes((f"mock-artifact-{index}\n").encode())

            mock_bin = root / "bin"
            mock_bin.mkdir()
            mock_sdb = mock_bin / "sdb"
            mock_sdb.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$*\" >>\"$MOCK_SDB_LOG\"\n"
                "case \"${1:-}\" in\n"
                "  version) echo 'Smart Development Bridge 4.2.25'; exit 0;;\n"
                "  connect) echo \"connected ${2:-}\"; exit 0;;\n"
                "  devices) echo 'mock-board device'; exit 0;;\n"
                "esac\n"
                "case \"$*\" in\n"
                "  *run_s4_remote.sh*) echo RC=0; echo DONE_S4_SHA_CONTRACT;;\n"
                "  *run_gst_trim_cost_remote.sh*) echo RC=0; echo DONE_GST_SHA_CONTRACT;;\n"
                "  *) echo RC=1; echo FAIL_MOCK_SDB; exit 1;;\n"
                "esac\n",
                encoding="utf-8",
            )
            mock_sdb.chmod(0o755)

            manifest = root / "manifest.json"
            expected = {name: digest(artifacts / name) for name in names}
            for source in ("frozen", "reproducible", "gbs"):
                with self.subTest(source=source):
                    source_field = {
                        "frozen": "frozen_sha256",
                        "reproducible": "reproducible_build_sha256",
                        "gbs": "gbs_build_sha256",
                    }[source]
                    artifact_rows = []
                    for name in names:
                        row = {
                            "name": name,
                            "frozen_sha256": expected[name] if name == "small_320x240.mp4" else "0" * 64,
                            "reproducible_build_sha256": None if name == "small_320x240.mp4" else "1" * 64,
                            "gbs_build_sha256": None if name == "small_320x240.mp4" else "2" * 64,
                        }
                        if name != "small_320x240.mp4":
                            row[source_field] = expected[name]
                        artifact_rows.append(row)
                    manifest.write_text(json.dumps({"schema": "test.v2", "artifacts": artifact_rows}), encoding="utf-8")
                    output = root / f"output-{source}"
                    log = root / f"sdb-{source}.log"
                    result = subprocess.run(
                        [
                            "sh", str(WORKFLOW), "--ip", "mock-board", "--output", str(output),
                            "--artifact-dir", str(artifacts), "--artifact-source", source,
                            "--contract-check-only",
                        ],
                        env={
                            **os.environ,
                            "PATH": f"{mock_bin}:{os.environ['PATH']}",
                            "MOCK_SDB_LOG": str(log),
                            "DEMO_DELIVERABLES_MANIFEST": str(manifest),
                        },
                        text=True, capture_output=True, check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                    self.assertIn(f"sha_source={source}", result.stdout)
                    invocation = log.read_text(encoding="utf-8")
                    self.assertIn("EXPECTED_ALLOC_SHA=", invocation)
                    self.assertIn(expected["alloc_bench.armv7l"], invocation)
                    self.assertIn("EXPECTED_GST_SHA=", invocation)
                    self.assertIn(expected["gst_loop_decode.armv7l"], invocation)
                    self.assertIn("EXPECTED_RECLAIM_SHA=", invocation)
                    self.assertIn(expected["reclaim_probe.armv7l"], invocation)
                    self.assertIn("EXPECTED_MEDIA_SHA=", invocation)
                    self.assertIn(expected["small_320x240.mp4"], invocation)
                    manifest_text = (output / "artifact_manifest.tsv").read_text(encoding="utf-8")
                    self.assertIn(f"alloc_bench.armv7l\t{source}\t", manifest_text)


if __name__ == "__main__":
    unittest.main()
