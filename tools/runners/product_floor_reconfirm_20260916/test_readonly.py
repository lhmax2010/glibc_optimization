import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('floor_readonly', HERE/'run_readonly.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ReadonlyTests(unittest.TestCase):
    def test_only_single_read_commands_fit_full_200_byte_body(self):
        for command in (['uname', '-r'], ['uname', '-m'], ['id'], ['ps', '-ef'], ['ls', '/proc'],
                        ['uptime'], ['date', '-u'], ['df', '-h'], ['rpm', '-q', 'glibc'], ['rpm', '-q', 'gdb'],
                        *[['cat', p] for p in ('/etc/os-release', '/proc/meminfo', '/proc/swaps', '/proc/uptime',
                            '/proc/1/stat', '/proc/1/smaps', '/proc/1/cmdline',
                            '/proc/sys/kernel/yama/ptrace_scope', '/sys/block/zram0/mm_stat')]):
            body = runner.readonly_body(command)
            self.assertLessEqual(len(body.encode()), 200)
            self.assertIn('RC=$r', body)
        with self.assertRaisesRegex(ValueError, '> 200 bytes; NOT SENT'):
            runner.readonly_body(['cat', '/proc/'+'1'*200+'/smaps'])

    def test_mutations_pipelines_options_and_injection_are_not_sent(self):
        forbidden = (['rm', '/tmp/file'], ['rmdir', '/tmp/file'], ['kill', '123'],
                     ['sh', '-c', 'id'], ['reboot'], ['sdb', 'root', 'on'], ['cat', '/etc/shadow'],
                     ['rpm', '-e', 'gdb'], ['cat', '/proc/1/stat;reboot'], ['cat', '/proc/1/stat\nid'],
                     ['cat', '/proc/1/../1/stat'], ['cat', '/proc/1/stat', '/proc/2/stat'])
        with tempfile.TemporaryDirectory() as out, mock.patch.object(runner.subprocess, 'run') as run:
            board = runner.Board('192.0.2.1', Path(out))
            for command in forbidden:
                with self.subTest(command=command), self.assertRaises(ValueError):
                    board.read('forbidden', command)
            run.assert_not_called()

    def test_rpi4_stops_before_any_other_board_read(self):
        with tempfile.TemporaryDirectory() as out:
            board = runner.Board('192.0.2.1', Path(out))
            with mock.patch.object(board, 'call', return_value=(0, 'connected')) as call, \
                 mock.patch.object(board, 'read', return_value=(0, '6.6.0-rpi4')) as read:
                with self.assertRaisesRegex(ValueError, 'STOP_TEST_BOARD'):
                    board.identity()
                read.assert_called_once_with('uname_r', ['uname', '-r'])
                self.assertEqual(call.call_count, 3)

    def test_development_image_and_unknown_product_stop(self):
        for release in ('BUILD_ID=tizen-unified-toolchain_20260814', 'NAME=Unknown',
                        'PRETTY_NAME="Tizen TV development image"'):
            with tempfile.TemporaryDirectory() as out:
                board = runner.Board('192.0.2.1', Path(out))
                with mock.patch.object(board, 'call', return_value=(0, 'connected')), \
                     mock.patch.object(board, 'read', side_effect=[(0, '5.4-tv'), (0, 'armv7l'), (0, release)]):
                    with self.assertRaisesRegex(ValueError, 'STOP_'):
                        board.identity()

    def test_product_identity_accepts_tv_marker_and_keeps_arch(self):
        with tempfile.TemporaryDirectory() as out:
            board = runner.Board('192.0.2.1', Path(out))
            with mock.patch.object(board, 'call', return_value=(0, 'connected')), \
                 mock.patch.object(board, 'read', side_effect=[(0, '5.4-tv'), (0, 'aarch64'),
                                                            (0, 'PRETTY_NAME="Tizen TV"')]):
                self.assertEqual(board.identity()['arch'], 'aarch64')

    def test_connection_failure_never_retries_or_reads_identity(self):
        with tempfile.TemporaryDirectory() as out:
            board = runner.Board('192.0.2.1', Path(out))
            with mock.patch.object(board, 'call', side_effect=[(0, 'version'), (0, 'failed to connect')]) as call, \
                 mock.patch.object(board, 'read') as read:
                with self.assertRaisesRegex(ValueError, 'connection failed'):
                    board.identity()
                self.assertEqual(call.call_count, 2)
                read.assert_not_called()

    def test_empty_or_nonzero_connect_cannot_pass(self):
        for answer in ((0, ''), (1, '')):
            with tempfile.TemporaryDirectory() as out:
                board = runner.Board('192.0.2.1', Path(out))
                with mock.patch.object(board, 'call', side_effect=[(0, 'version'), answer]), \
                     mock.patch.object(board, 'read') as read, self.assertRaisesRegex(ValueError, 'connection failed'):
                    board.identity()
                read.assert_not_called()

    def test_host_exit_zero_without_remote_proof_fails_and_raw_is_preserved(self):
        for raw in (b'value\n', b'RC=0\nFAIL\n', b'RC=0\nRC=0\nDONE\n'):
            with tempfile.TemporaryDirectory() as out:
                board = runner.Board('192.0.2.1', Path(out))
                with mock.patch.object(runner.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, raw)):
                    with self.assertRaisesRegex(ValueError, 'remote proof'):
                        board.read('id', ['id'])
                self.assertEqual((Path(out)/'raw/id.txt').read_bytes(), raw)
                self.assertIn('proof_error', json.loads((Path(out)/'commands.jsonl').read_text()))

    def test_remote_failure_and_optional_absence_are_explicit(self):
        with tempfile.TemporaryDirectory() as out:
            board = runner.Board('192.0.2.1', Path(out))
            result = subprocess.CompletedProcess([], 0, b'package gdb is not installed\nRC=1\nFAIL\n')
            with mock.patch.object(runner.subprocess, 'run', return_value=result):
                self.assertEqual(board.read('gdb_optional', ['rpm', '-q', 'gdb'], optional=True)[0], 1)
                with self.assertRaisesRegex(ValueError, 'RC=1'):
                    board.read('gdb_hard', ['rpm', '-q', 'gdb'])
                with self.assertRaisesRegex(ValueError, 'prior read failed'):
                    board.read('after_stop', ['id'])

    def test_duplicate_observation_cannot_overwrite_or_reexecute(self):
        with tempfile.TemporaryDirectory() as out:
            board = runner.Board('192.0.2.1', Path(out))
            result = subprocess.CompletedProcess([], 7, b'value\nRC=0\nDONE\n')
            with mock.patch.object(runner.subprocess, 'run', return_value=result) as run:
                self.assertEqual(board.read('id', ['id']), (0, 'value'))
                with self.assertRaisesRegex(ValueError, 'duplicate observation'):
                    board.read('id', ['id'])
                self.assertEqual(run.call_count, 1)

    def test_timeout_is_recorded_and_not_retried(self):
        with tempfile.TemporaryDirectory() as out:
            board = runner.Board('192.0.2.1', Path(out))
            with mock.patch.object(runner.subprocess, 'run', side_effect=subprocess.TimeoutExpired([], 20, b'partial')) as run:
                with self.assertRaises(ValueError):
                    board.read('id', ['id'])
                self.assertEqual(run.call_count, 1)
            self.assertIn(b'HOST_TIMEOUT', (Path(out)/'raw/id.txt').read_bytes())

    def test_process_view_missing_pid1_stops_without_root(self):
        board = mock.Mock()
        board.read.return_value = (0, 'UID PID PPID CMD\nuser 52 1 sh\n')
        with self.assertRaisesRegex(ValueError, 'PID 1 missing'):
            runner.inventory(board, {'enlightenment': 'enlightenment'})
        board.read.assert_called_once_with('process_view', ['ps', '-ef'])

    def test_missing_zram_is_never_zero(self):
        board = mock.Mock()
        board.read.side_effect = [(0, 'MemAvailable: 1234 kB'), (1, 'No such file or directory')]
        with self.assertRaisesRegex(ValueError, 'not zero'):
            runner.globals_at(board, 'sample')

    def test_swap_table_must_exist_and_parse_before_zero_is_possible(self):
        for text in ('', 'Filename Type Size Used Priority\n/dev/zram0 partition NA 0 -1'):
            board = mock.Mock()
            board.read.side_effect = [(0, 'MemAvailable: 1234 kB'), (0, '0 0 0'), (0, text)]
            with self.assertRaisesRegex(ValueError, 'swaps table'):
                runner.globals_at(board, 'sample')
        board = mock.Mock()
        board.read.side_effect = [(0, 'MemAvailable: 1234 kB'), (0, '0 0 0'),
                                 (0, 'Filename Type Size Used Priority')]
        self.assertEqual(runner.globals_at(board, 'sample')['zram_used_kb'], 0)

    def test_proc_listing_omitting_live_pid_is_not_a_complete_ranking(self):
        board = mock.Mock()
        board.read.side_effect = [(0, 'UID PID PPID CMD\nroot 1 0 init\nroot 52 1 worker'),
                                  (0, '1 meminfo swaps'), (0, '52 (worker)')]
        with self.assertRaisesRegex(ValueError, 'omits visible live'):
            runner.inventory(board, {'enlightenment': 'enlightenment'})
        self.assertEqual(board.read.call_count, 3)

    def test_process_identity_change_stops_parallel_new_requests(self):
        board = mock.Mock()
        before = '42 (target) '+' '.join(['S']+['0']*24)
        after = '43 (target) '+' '.join(['S']+['0']*24)
        board.read.side_effect = [(0, before), (0, 'maps'), (0, after)]
        with self.assertRaisesRegex(ValueError, 'PID identity changed'):
            runner.sample_process(board, {'pid': 42, 'start_ticks': 0, 'target': 'sample'}, 0)
        board.stopped.set.assert_called_once()

    def test_sampling_overrun_retains_partial_and_never_runs_analysis(self):
        with tempfile.TemporaryDirectory() as out:
            board = mock.Mock()
            board.output = Path(out)
            with mock.patch.object(runner, 'sample_process', return_value={'sample': 0, 'target': 'example'}), \
                 mock.patch.object(runner, 'globals_at', return_value={'MemAvailable_kb': 1}), \
                 mock.patch.object(runner.time, 'monotonic', side_effect=[0, 0, 0, 1.1, 1.1]), \
                 mock.patch.object(runner, 'analyze') as analyze:
                with self.assertRaisesRegex(ValueError, '1 s sampling deadline missed'):
                    runner.observe(board, [{'pid': 1}])
                analyze.assert_not_called()
            self.assertTrue((Path(out)/'timeseries.tsv').exists())
            self.assertTrue((Path(out)/'sampling_timing.json').exists())
            board.stopped.set.assert_called_once()

    def test_contract_gate_rejects_short_interval_modified_bytes_and_tag_type(self):
        receipt = {
            'tag': runner.TAG, 'tag_object': 'tag-object', 'commit': 'commit', 'boot_id': 'boot',
            'epoch_ns': 1, 'monotonic_ns': 1}
        def git(*args):
            if args == ('cat-file', '-t', runner.TAG): return b'tag\n'
            if args == ('rev-parse', runner.TAG): return b'tag-object\n'
            if args == ('rev-parse', runner.TAG+'^{commit}'): return b'commit\n'
            if args[0] == 'ls-remote': return b'tag-object refs/tags/example\n'
            if args[0] == 'show': return b'content'
            raise AssertionError(args)
        with mock.patch.object(runner, 'git', side_effect=git), \
             mock.patch.object(Path, 'read_bytes', return_value=b'content'), \
             mock.patch.object(Path, 'read_text', return_value='boot'), \
             mock.patch.object(runner.time, 'time_ns', return_value=599000000001), \
             mock.patch.object(runner.time, 'monotonic_ns', return_value=599000000001):
            with self.assertRaisesRegex(ValueError, 'below 600'):
                runner.contract_gate(receipt)
            with mock.patch.object(runner.time, 'time_ns', return_value=600000000001), \
                 mock.patch.object(runner.time, 'monotonic_ns', return_value=600000000001):
                self.assertEqual(runner.contract_gate(receipt)['interval_seconds'], 600)
            with mock.patch.object(Path, 'read_bytes', return_value=b'changed'):
                with self.assertRaisesRegex(ValueError, 'frozen contract/analyzer changed'):
                    runner.contract_gate(receipt)
            with mock.patch.object(runner, 'git', return_value=b'commit'):
                with self.assertRaisesRegex(ValueError, 'annotated'):
                    runner.contract_gate(receipt)


if __name__ == '__main__':
    unittest.main()
