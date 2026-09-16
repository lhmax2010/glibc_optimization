import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('board_script', HERE/'run_board_script.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

SMAPS = ('00100000-00110000 rw-p 00000000 00:00 0\nPrivate_Dirty: 12 kB\n'
         '00201000-00210000 rw-p 00000000 00:00 0 [heap]\nPrivate_Dirty: 8 kB\n'
         '00301000-00310000 rw-p 00000000 00:00 0\nPrivate_Dirty: 4 kB\n'
         '00401000-00410000 r--p 00000000 00:00 1 /lib/file\nPrivate_Dirty: 2 kB\n')


class BoardScriptTests(unittest.TestCase):
    def fake_proc(self, root, pid=1, name='init'):
        target = root/str(pid)
        target.mkdir()
        fields = ['S']+['0']*24
        fields[7], fields[9], fields[19] = '9', '2', '123'
        (target/'stat').write_text(str(pid)+' ('+name+') '+' '.join(fields)+'\n')
        (target/'smaps').write_text(SMAPS)
        return target

    def probe(self, root, mode, target=None):
        script = (HERE/'board_probe.sh').read_text().replace('proc_root=/proc', 'proc_root='+str(root))
        script = script.replace('sys_root=/sys', 'sys_root='+str(root/'sys'))
        path = root/'probe.sh'; path.write_text(script)
        return subprocess.run(['sh', str(path), mode, *([target] if target else [])], capture_output=True, text=True, timeout=5)

    def test_board_parser_matches_frozen_python_parser(self):
        with tempfile.TemporaryDirectory() as out:
            root = Path(out); self.fake_proc(root)
            result = self.probe(root, 'proc', 'Example:1:123')
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = result.stdout.strip().split('\t')
            self.assertEqual(list(map(int, fields[6:10])), list(m.old.smaps(SMAPS).values()))
            self.assertEqual(fields[10:], ['9', '2'])

    def test_inventory_parentheses_and_empty_live_smaps(self):
        with tempfile.TemporaryDirectory() as out:
            root = Path(out); target = self.fake_proc(root, name='name ) with spaces')
            result = self.probe(root, 'inventory')
            self.assertEqual(result.returncode, 0, result.stderr)
            selected = m.select_inventory(result.stdout, {'Example': 'name ) with spaces'})
            self.assertEqual(selected['selected'][0]['target'], 'Example_1')
            (target/'smaps').write_text('')
            failed = self.probe(root, 'inventory')
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn('empty or unreadable live smaps', failed.stderr)

    def test_missing_pd_or_pid_start_rejected(self):
        with tempfile.TemporaryDirectory() as out:
            root = Path(out); target = self.fake_proc(root)
            self.assertNotEqual(self.probe(root, 'proc', 'Example:1:999').returncode, 0)
            (target/'smaps').write_text(SMAPS.replace('Private_Dirty: 12 kB\n', ''))
            self.assertNotEqual(self.probe(root, 'proc', 'Example:1:123').returncode, 0)

    def test_global_three_zram_bytes_and_missing_not_zero(self):
        with tempfile.TemporaryDirectory() as out:
            root = Path(out)
            (root/'meminfo').write_text('MemAvailable: 1234 kB\n')
            (root/'swaps').write_text('Filename Type Size Used Priority\n/dev/zram0 partition 100 3 -2   \n')
            zram = root/'sys/block/zram0'; zram.mkdir(parents=True)
            (zram/'mm_stat').write_text('4096 123 8192 0 0\n')
            result = self.probe(root, 'globals')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip().split('\t')[3:], ['1234', '3', '4096', '123', '8192'])
            (zram/'mm_stat').unlink()
            self.assertNotEqual(self.probe(root, 'globals').returncode, 0)

    def board(self, out):
        b = m.Board('192.0.2.1', Path(out))
        b.call = Mock(side_effect=[(0, 'version'), (0, 'connected'), (0, '192.0.2.1:26101 device TV')])
        return b

    def test_strict_product_arch_gate_stops_before_os(self):
        with tempfile.TemporaryDirectory() as out:
            b = self.board(out); b.read = Mock(side_effect=[(0, '6.12.60'), (0, 'aarch64')])
            with self.assertRaisesRegex(ValueError, 'ARCH'):
                b.identity()
            self.assertEqual(b.read.call_count, 2)

    def test_rpi4_first_gate_and_product_version_support(self):
        with tempfile.TemporaryDirectory() as out:
            b = self.board(out); b.read = Mock(return_value=(0, '6.12-rpi4'))
            with self.assertRaisesRegex(ValueError, 'TEST_BOARD'):
                b.identity()
            self.assertEqual(b.read.call_count, 1)
        self.assertTrue(m.product_release('PRETTY_NAME="Tizen10/TV product"'))
        self.assertFalse(m.product_release('PRETTY_NAME="Tizen10 TV unified-toolchain"'))
        self.assertFalse(m.product_release('PRETTY_NAME="Tizen10"'))

    def test_vk_missing_not_veto_kernel_deviation_recorded(self):
        with tempfile.TemporaryDirectory() as out:
            b = self.board(out)
            b.read = Mock(side_effect=[(0, '6.13.1'), (0, 'armv7l'), (0, 'PRETTY_NAME="Tizen10 TV"'), (1, '')])
            value = b.identity()
            self.assertEqual(value['kernel'], '6.13.1')
            self.assertEqual(value['vk_send'][0], 1)

    def test_allowlist_and_200_byte_bound(self):
        path = '/tmp/pf_20260916_0123456789ab.sh'
        for op in ('hash', 'absent', 'symlink', 'remove', 'run'):
            self.assertLessEqual(len(m.script_body(op, path, 'collect').encode()), 200)
        for bad in ('/tmp/other.sh', '/tmp/pf_20260916_0123456789ab.sh;reboot', '/etc/os-release'):
            with self.assertRaises(ValueError): m.script_body('remove', bad)
        for argv in (['sdb', 'root', 'on'], ['rpm', '-e', 'gdb'], ['vk_send'], ['sh', '-c', 'id']):
            with self.assertRaises(ValueError): m.extra_body(argv)

    def test_cleanup_requires_own_exact_hash_and_no_active_probe(self):
        b = Mock(); path = '/tmp/pf_20260916_0123456789ab.sh'
        b.call.return_value = (0, 'root 1 0 init\nroot 2 1 sh '+path)
        with patch.object(m, 'operation') as op, self.assertRaisesRegex(ValueError, 'still be running'):
            m.cleanup(b, [dict(path=path, sha256='a'*64)])
        op.assert_not_called()
        b.call.return_value = (0, 'root 1 0 init')
        with patch.object(m, 'operation', side_effect=[(0, ''), (1, ''), (0, 'b'*64+' '+path)]) as op, \
             self.assertRaisesRegex(ValueError, 'hash mismatch'):
            m.cleanup(b, [dict(path=path, sha256='a'*64)])
        self.assertNotIn('remove', [c.args[2] for c in op.call_args_list])

    def test_cleanup_removes_once_and_checks_missing_and_symlink(self):
        with tempfile.TemporaryDirectory() as out:
            b = Mock(output=Path(out)); b.call.return_value = (0, 'root 1 0 init')
            path = '/tmp/pf_20260916_0123456789ab.sh'; sha = 'a'*64
            with patch.object(m, 'operation', side_effect=[(0,''),(1,''),(0,sha+' '+path),(0,''),(1,''),(1,'')]) as op:
                m.cleanup(b, [dict(path=path,sha256=sha)])
            self.assertEqual([c.args[2] for c in op.call_args_list].count('remove'), 1)
            self.assertTrue((Path(out)/'cleanup.json').exists())

    def series(self):
        lines = []
        for i in range(601):
            t = i*1000000000
            lines += [f'G\t{i}\t{t}\t1000\t0\t0\t0\t0',
                      f'P\t{i}\t{t}\tExample\t1\t123\t20\t4\t2\t26\t9\t2',
                      f'T\t{i}\t{t}\t{t+10000000}\t{t}']
        return '\n'.join(lines+['SAMPLING_DONE'])

    def test_stream_complete_and_failure_paths(self):
        targets = [dict(target='Example',pid=1,start_ticks=123)]
        text = self.series()
        rows, timing = m.parse_samples(text, targets)
        self.assertEqual(len(rows), 601)
        self.assertEqual(len(timing), 601)
        for changed in (text.replace('SAMPLING_DONE',''), text+'\nG\t0\t0\t1000\t0\t0\t0\t0',
                        text.replace('T\t0\t0\t10000000\t0', 'T\t0\t0\t1000000000\t0'),
                        text.replace('Example\t1\t123', 'Example\t1\t124', 1)):
            with self.assertRaises(ValueError): m.parse_samples(changed, targets)

    def test_no_owned_scripts_means_zero_cleanup_board_calls(self):
        with tempfile.TemporaryDirectory() as out:
            b = Mock(output=Path(out))
            m.cleanup(b, [])
            b.call.assert_not_called()


if __name__ == '__main__':
    unittest.main()
