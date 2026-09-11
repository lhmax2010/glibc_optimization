"""Construct synthetic endpoints at runtime; never store real project addresses."""
import ipaddress
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from tools.privacy import scan_endpoints as scanner


class EndpointScannerTests(unittest.TestCase):
    def setUp(self):
        self.address = ipaddress.IPv4Address(bytes((192, 168, 77, 9)))
        self.mapped = ipaddress.IPv6Address(b'\0'*10 + b'\xff\xff' + self.address.packed)

    def tokens(self):
        v4 = self.address.packed
        v6 = self.mapped.packed
        native = (ipaddress.ip_network('fc00::/7').network_address + 0x1234).packed
        little = lambda raw: b''.join(raw[n:n+4][::-1] for n in range(0,len(raw),4)).hex()
        return [str(self.address), v4.hex(), v4[::-1].hex(), '0x'+v4.hex(),
                str(int(self.address)), str(int.from_bytes(v4,'little')),
                str(self.mapped), v6.hex(), little(v6), little(native), native.hex()]

    def test_all_encodings_tcp_tcp6_udp_and_decimal_files_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            for index,token in enumerate(self.tokens()):
                with self.subTest(index=index):
                    path = root/'sample.txt'
                    path.write_text('header\n  1: '+token+':65F5 00000000:0000 01 9 0\nRC=0\nDONE\n')
                    result = scanner.scan(root,[pathlib.Path(path.name)])
                    self.assertEqual(result['verdict'],'FAIL')
                    self.assertEqual(result['count'],1,result)
                    self.assertEqual(result['findings'][0]['line'],2)
                    self.assertNotIn(token,json.dumps(result))

    def test_redaction_preserves_line_structure_ports_states_and_alias(self):
        for index,token in enumerate(self.tokens()):
            with self.subTest(token_index=index):
                text = 'header\n\t'+token+':65F5 00000000:0000 01 9 0\nRC=0\nDONE\n'
                redacted,edits = scanner.redact_endpoints(text,{str(self.address):'<TEST_BOARD_IP>'})
                alias = '<TEST_BOARD_IP>' if index < 9 else '<INTERNAL_ENDPOINT>'
                self.assertEqual(redacted,text.replace(token,alias))
                self.assertTrue(edits)
                self.assertEqual(scanner.find_endpoints(redacted),[])
                self.assertEqual(scanner.redact_endpoints(redacted),(redacted,[]))

    def test_decimal_without_port_and_json_string_are_detected(self):
        for token in (str(int(self.address)),str(int.from_bytes(self.address.packed,'little'))):
            for text in ('ip='+token,json.dumps({'peer':token})):
                self.assertEqual(len(scanner.find_endpoints(text)),1)

    def test_case_independence(self):
        token = self.address.packed[::-1].hex()
        for value in (token.lower(),token.upper(),'0X'+token.upper()):
            self.assertEqual(len(scanner.find_endpoints(value)),1)

    def test_no_hash_substrings_or_loopback_or_unspecified_false_hits(self):
        token = self.address.packed.hex()
        for text in ('a'+token+'b'*31,'a'+token+'b'*55,'127.0.0.1:443',
                     '00000000:0000','0100007F:65F5','0','4294967296','::1'):
            self.assertEqual(scanner.find_endpoints(text),[],text)

    def test_cidr_policy_is_not_an_endpoint_but_host_bits_cannot_hide(self):
        self.assertEqual(scanner.find_endpoints('192.168.0.0/16 fc00::/7 fe80::/10'),[])
        self.assertTrue(scanner.find_endpoints(str(self.address)+'/24'))
        self.assertTrue(scanner.find_endpoints(str(self.address)+'/999'))
        self.assertTrue(scanner.find_endpoints(str(self.address)+'/32'))
        native = ipaddress.ip_network('fc00::/7').network_address + 1
        self.assertTrue(scanner.find_endpoints(str(native)+'/128'))

    def test_ambiguous_measurement_or_checksum_is_detected_but_never_edited(self):
        for text in (json.dumps({'rss_bytes': int(self.address)}),
                     'crc32='+self.address.packed.hex(), str(int(self.address))):
            self.assertTrue(scanner.find_endpoints(text))
            with self.assertRaisesRegex(ValueError, 'ambiguous'):
                scanner.redact_endpoints(text)

    def test_integer_endpoint_json_keeps_parse_and_unrelated_numeric_values(self):
        for value in (int(self.address),str(int(self.address)),self.address.packed.hex()):
            text=json.dumps({'peer':value,'rss_bytes':8117408})
            redacted,_=scanner.redact_endpoints(text)
            self.assertEqual(json.loads(redacted),{'peer':'<INTERNAL_ENDPOINT>','rss_bytes':8117408})

    def test_explicit_alias_extends_documentation_address_scope(self):
        address = ipaddress.IPv4Address('192.0.2.1')
        token = address.packed[::-1].hex()
        self.assertEqual(scanner.find_endpoints(token),[])
        self.assertEqual(scanner.redact_endpoints('ip='+token,{str(address):'<TEST_BOARD_IP>'})[0],'ip=<TEST_BOARD_IP>')
        with self.assertRaises(ValueError):
            scanner.redact_endpoints(token,{str(address):'reversible-value'})

    def test_file_types_and_json_output_do_not_hide_ascii_endpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root/'binary').write_bytes(b'\x00\xff peer='+str(self.address).encode())
            self.assertEqual(scanner.scan(root,[pathlib.Path('binary')])['count'],1)

    def test_missing_symlink_traversal_and_nonrepo_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            for path in ('missing','../outside',str(root/'absolute')):
                with self.subTest(path=path),self.assertRaises(ValueError):
                    scanner.scan(root,[pathlib.Path(path)])
            (root/'target').write_text('none')
            (root/'link').symlink_to(root/'target')
            with self.assertRaises(ValueError):scanner.scan(root,[pathlib.Path('link')])
            with self.assertRaises(ValueError):scanner.scan(root)

    def test_cli_return_codes_and_nonempty_safe_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            path = root/'sample.txt';path.write_text(str(int(self.address)))
            cmd=[sys.executable,scanner.__file__,'--repo-root',str(root),'--json','sample.txt']
            bad=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(bad.returncode,1)
            self.assertEqual(json.loads(bad.stdout)['count'],1)
            self.assertNotIn(str(int(self.address)),bad.stdout+bad.stderr)
            path.write_text('<INTERNAL_ENDPOINT>')
            good=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(good.returncode,0)
            self.assertEqual(json.loads(good.stdout)['verdict'],'PASS')
            missing=subprocess.run(cmd+['missing'],capture_output=True,text=True)
            self.assertEqual(missing.returncode,2)
            self.assertIn('FAIL endpoint-scan',missing.stderr)

    def test_published_redaction_hash_chain_and_original_identity(self):
        root=pathlib.Path(__file__).resolve().parents[2]
        record=json.loads((root/'data/raw/demo_v12_delivery_20260911/weekend/redaction.json').read_text())
        self.assertEqual(sum(r['endpoint_tokens'] for r in record['files']),14)
        self.assertEqual(sum(len(r['lines']) for r in record['files']),7)
        for row in record['files']:
            path=root/row['path'];manifest=path.parent/'manifest.json'
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),row['public_sha256'])
            self.assertEqual(hashlib.sha256(manifest.read_bytes()).hexdigest(),row['manifest_after_sha256'])
            entry=next(r for r in json.loads(manifest.read_text())['files'] if r['path']=='TCP.txt')
            self.assertEqual(entry['original_sha256'],row['original_sha256'])
            self.assertEqual(entry['public_sha256'],row['public_sha256'])


if __name__ == '__main__':
    unittest.main()
