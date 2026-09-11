"""Actual remote command fragments executed only against private host fixtures."""
import pathlib
import shlex
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import test_executor_host as fixtures


class RoundFaults(fixtures.ExecutorHost):
    # Inherit fixture setup only, not a second execution of its test methods.
    def test_round_snapshot_enumeration_and_metadata_errors_are_not_empty_success(self):
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("readonly command-fragment fixtures need sh")
        crash = self.root / "crash"
        crash.mkdir()
        archive = crash / "owned.zip"
        archive.write_bytes(b"fixture")
        for failure in ("none", "find", "stat", "sha256sum"):
            with self.subTest(failure=failure):
                def remote(label, command):
                    if not label.endswith("_ALERTS"):
                        return "0 0 0" if label.endswith("_ZRAM") else "boot"
                    command = command.replace("/opt/usr/share/crash/livedump", str(crash))
                    doubles = 'find() { ' + ('return 31;' if failure == "find" else 'printf "%s\\n" ' + shlex.quote(str(archive)) + ';') + ' }\n'
                    doubles += 'stat() { ' + ('return 32;' if failure == "stat" else
                        'if [ "$2" = %F ]; then printf "directory\\n"; else printf "123\\n"; fi;') + ' }\n'
                    doubles += 'sha256sum() { ' + ('return 33;' if failure == "sha256sum" else 'printf "%064d  file\\n" 0;') + ' }\n'
                    result = subprocess.run([shell, "-c", doubles + command], capture_output=True, text=True, timeout=5)
                    if result.returncode:
                        raise ValueError("enumeration/metadata failed")
                    return result.stdout
                with mock.patch.object(self.instance, "remote", side_effect=remote):
                    if failure == "none":
                        self.instance.round_snapshot("fixture")
                    else:
                        with self.assertRaisesRegex(ValueError, "enumeration/metadata"):
                            self.instance.round_snapshot("fixture")

    def test_package_query_database_error_does_not_mean_absent(self):
        shell = shutil.which("sh")
        if not shell:
            self.skipTest("RPM command-fragment fixtures need sh")
        for failure in (False, True):
            commands = []
            def remote(label, command):
                if label == "WORK_OWNER":
                    return "OWNED"
                if label != "GDB_REMOVE":
                    return ""
                commands.append(command)
                double = 'rpm() { printf "error: rpmdb unavailable\\n"; return 1; }\n' if failure else 'rpm() { printf "package %s is not installed\\n" "$2"; return 1; }\n'
                result = subprocess.run([shell, "-c", double + command], capture_output=True, text=True, timeout=5)
                if result.returncode:
                    raise ValueError("RPM query not confirmed absent: " + result.stdout)
                return result.stdout
            self.instance.created = self.instance.install_attempted = True
            with mock.patch.object(self.instance, "remote", side_effect=remote):
                self.assertEqual(self.instance.cleanup(), "FAIL" if failure else "PASS")
            self.assertEqual(len(commands), 1)


# Do not repeat unrelated inherited cases in unittest discovery.
for _name in dir(fixtures.ExecutorHost):
    if _name.startswith("test_") and _name not in RoundFaults.__dict__:
        setattr(RoundFaults, _name, None)


if __name__ == "__main__":
    unittest.main()
