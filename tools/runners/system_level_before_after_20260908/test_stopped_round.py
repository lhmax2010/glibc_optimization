"""Stopped-round safeguards; no SDB command is ever executed by these tests."""
import pathlib
import subprocess
import unittest

HERE = pathlib.Path(__file__).resolve().parent


class StoppedRound(unittest.TestCase):
    def test_execution_without_required_parameters_is_rejected(self):
        for name in ("capture_point.sh", "run_cell_remote.sh"):
            with self.subTest(name=name):
                p = subprocess.run(["sh", str(HERE / name)], text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=5)
                self.assertEqual(p.returncode, 2)
                self.assertIn("required", p.stdout)
                self.assertNotIn("DONE_CELL", p.stdout)

    def test_contract_and_analyzer_remain_frozen(self):
        repo = HERE.parents[2]
        for name in ("contract.json", "analyze_system_level.py"):
            relative = (HERE / name).relative_to(repo).as_posix()
            frozen = subprocess.check_output(["git", "show", "system-before-after-contract-20260908:" + relative], cwd=repo)
            self.assertEqual((HERE / name).read_bytes(), frozen)


if __name__ == "__main__":
    unittest.main()
