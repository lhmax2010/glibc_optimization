#!/usr/bin/env python3
"""Host tests for the RPM metadata provenance auditor."""

from __future__ import annotations

import csv
import gzip
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
AUDITOR = HERE / "audit_tool_provenance.py"


class ProvenanceAuditTests(unittest.TestCase):
    def test_scans_package_provides_and_filelist_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repodata = repo / "repodata"
            repodata.mkdir(parents=True)
            primary = gzip.compress(
                b'''<?xml version="1.0"?><metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:rpm="http://linux.duke.edu/metadata/rpm" packages="2">
<package type="rpm"><name>alloc-bench</name><arch>armv7l</arch><version epoch="0" ver="1" rel="2"/><format><rpm:provides><rpm:entry name="alloc-bench"/></rpm:provides></format></package>
<package type="rpm"><name>clang</name><arch>armv7l</arch><version epoch="0" ver="22" rel="1"/><format><rpm:provides><rpm:entry name="gst-loop-decode"/></rpm:provides></format></package></metadata>'''
            )
            filelists = gzip.compress(
                b'''<?xml version="1.0"?><filelists xmlns="http://linux.duke.edu/metadata/filelists" packages="1"><package pkgid="x" name="probe-package" arch="armv7l"><version epoch="0" ver="1" rel="1"/><file>/usr/bin/reclaim_probe</file></package></filelists>'''
            )
            primary_name = "primary.xml.gz"
            filelists_name = "filelists.xml.gz"
            (repodata / primary_name).write_bytes(primary)
            (repodata / filelists_name).write_bytes(filelists)
            psha = hashlib.sha256(primary).hexdigest()
            fsha = hashlib.sha256(filelists).hexdigest()
            (repodata / "repomd.xml").write_text(
                f'''<?xml version="1.0"?><repomd xmlns="http://linux.duke.edu/metadata/repo"><revision>1</revision>
<data type="primary"><checksum type="sha256">{psha}</checksum><location href="repodata/{primary_name}"/></data>
<data type="filelists"><checksum type="sha256">{fsha}</checksum><location href="repodata/{filelists_name}"/></data></repomd>''',
                encoding="utf-8",
            )
            config = root / "gbs.conf"
            config.write_text(f"[repo.fixture]\nurl={repo.as_uri()}/\n", encoding="utf-8")
            spec = root / "package.spec"
            spec.write_text("BuildRequires: clang\nBuildRequires: glibc-devel\n", encoding="utf-8")
            output = root / "output"
            result = subprocess.run(
                ["python3", str(AUDITOR), "--config", str(config), "--spec", str(spec), "--cache-dir", str(root / "cache"), "--output", str(output)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
            with (output / "tool_hits.tsv").open(newline="", encoding="utf-8") as stream:
                hits = list(csv.DictReader(stream, delimiter="\t"))
            self.assertEqual({row["dimension"] for row in hits}, {"package-name", "provides", "file-list"})
            with (output / "buildrequires.tsv").open(newline="", encoding="utf-8") as stream:
                requirements = {row["requirement"]: row for row in csv.DictReader(stream, delimiter="\t")}
            self.assertEqual(requirements["clang"]["nvr"], "clang-22-1")
            self.assertEqual(requirements["glibc-devel"]["status"], "NOT-IN-REPO")


if __name__ == "__main__":
    unittest.main()
