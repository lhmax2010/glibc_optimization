import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('diagnose', Path(__file__).with_name('diagnose.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class DiagnosisTests(unittest.TestCase):
    def recorder(self, output, port_rc=1, ssh_rc=255):
        recorder = Mock(output=Path(output))
        recorder.tcp.return_value = (port_rc, '', '')
        def command(label, argv, **kwargs):
            if label == 'ssh_uname_a':
                return ssh_rc, '', ''
            if label.startswith('ssh_'):
                return 0, 'sample\nRC=0\nDONE\n', ''
            return (1, 'failed', '') if label.startswith('sdb_connect') else (0, '', '')
        recorder.command.side_effect = command
        return recorder

    def test_closed_ports_skip_ssh_and_banner_no_retry(self):
        with tempfile.TemporaryDirectory() as output:
            r = self.recorder(output)
            d.diagnose(r, '192.0.2.1')
            labels = [c.args[0] for c in r.command.call_args_list]
            self.assertFalse(any(label.startswith('ssh_') for label in labels))
            self.assertEqual(labels.count('sdb_connect_default'), 1)
            self.assertEqual(labels.count('sdb_connect_explicit'), 1)
            self.assertNotIn('sdb_banner', [c.args[0] for c in r.tcp.call_args_list])

    def test_tcp_open_failure_banner_and_single_ssh_attempt(self):
        with tempfile.TemporaryDirectory() as output:
            r = self.recorder(output, 0)
            d.diagnose(r, '192.0.2.1')
            self.assertIn('sdb_banner', [c.args[0] for c in r.tcp.call_args_list])
            self.assertEqual([c.args[0] for c in r.command.call_args_list if c.args[0].startswith('ssh_')],
                             ['ssh_uname_a'])

    def test_ssh_success_exact_read_scope_and_length(self):
        with tempfile.TemporaryDirectory() as output:
            r = self.recorder(output, 0, 0)
            d.diagnose(r, '192.0.2.1')
            calls = [c for c in r.command.call_args_list if c.args[0].startswith('ssh_')]
            self.assertEqual(len(calls), 6)
            self.assertEqual(calls[0].args[1][-1], 'uname -a')
            for call, (_, command) in zip(calls[1:], d.SSH_READS):
                self.assertEqual(call.args[1][-1], d.remote_body(command))
                self.assertLessEqual(len(call.args[1][-1].encode()), 200)
            with self.assertRaises(ValueError):
                d.remote_body('reboot')

    def test_banner_sends_no_bytes(self):
        stream = Mock()
        stream.__enter__ = Mock(return_value=stream)
        stream.__exit__ = Mock(return_value=False)
        stream.recv.return_value = b''
        with patch.object(d.socket, 'create_connection', return_value=stream):
            rc, output = d.tcp_probe('192.0.2.1', 26101, True)
        self.assertEqual(rc, 0)
        stream.send.assert_not_called()
        stream.sendall.assert_not_called()
        self.assertIn('"sent_bytes": 0', output)

    def test_zero_sdb_exit_with_failed_text_still_gets_banner_if_tcp_open(self):
        with tempfile.TemporaryDirectory() as output:
            r = self.recorder(output, 0)
            r.command.side_effect = lambda *args, **kwargs: (0, 'error: failed to connect', '') if args[0].startswith('sdb_connect') else (255, '', '')
            d.diagnose(r, '192.0.2.1')
            self.assertEqual([c.args[0] for c in r.tcp.call_args_list].count('sdb_banner'), 1)

    def test_ssh_missing_remote_marker_stops_further_reads(self):
        with tempfile.TemporaryDirectory() as output:
            r = self.recorder(output, 0, 0)
            r.command.side_effect = lambda *args, **kwargs: (0, '', '')
            d.diagnose(r, '192.0.2.1')
            self.assertEqual([c.args[0] for c in r.command.call_args_list if c.args[0].startswith('ssh_')],
                             ['ssh_uname_a', 'ssh_uname_r'])

    def test_ssh_batch_mode_no_host_key_storage_and_one_connect_attempt(self):
        args = d.ssh_argv('192.0.2.1', 'uname -a')
        for option in ('BatchMode=yes', 'ConnectTimeout=5', 'ConnectionAttempts=1',
                       'UserKnownHostsFile=/dev/null', 'GlobalKnownHostsFile=/dev/null',
                       'ControlMaster=no', 'UpdateHostKeys=no'):
            self.assertIn(option, args)

    def test_output_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as output:
            with self.assertRaises(FileExistsError):
                d.Recorder(Path(output))


if __name__ == '__main__':
    unittest.main()
