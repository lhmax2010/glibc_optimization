#!/usr/bin/env python3
"""Read-only endpoint redaction gate. Reports positions, never address values.

Scope: the project's private IPv4 network, plus IPv6 ULA/link-local endpoints.
Recognizes proc-net little-endian words, network-order hex, mapped IPv4, decimal
IPv4 integers and textual IPs. No network, tag lookup, shell, or privilege use.
"""
from __future__ import annotations

import argparse
import dataclasses
import ipaddress
import json
import pathlib
import re
import subprocess
import sys

KNOWN_V4 = (ipaddress.ip_network('192.168.0.0/16'),)
LOCAL_V6 = (ipaddress.ip_network('fc00::/7'), ipaddress.ip_network('fe80::/10'))
HEX = re.compile(r'(?<![\w])(?:0[xX])?(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{8})(?![\w])')
DECIMAL = re.compile(r'(?<![\w.])(?:0|[1-9][0-9]{0,9})(?![\w.])')
IPV4 = re.compile(r'(?<![\w.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![\w.])')
IPV6 = re.compile(r'(?<![\w:])(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F:.]*(?![\w:])')


@dataclasses.dataclass(frozen=True)
class Finding:
    start: int
    end: int
    encoding: str
    address: object = dataclasses.field(repr=False)


def protected(address, aliases):
    if str(address) in aliases:
        return True
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped:
            return protected(address.ipv4_mapped, aliases)
        return any(address in network for network in LOCAL_V6)
    return any(address in network for network in KNOWN_V4)


def declared_network(text, end, address):
    """Only the exact scanner policy networks are declarations, not endpoints."""
    suffix = re.match(r'/([0-9]{1,3})(?!\d)', text[end:])
    if not suffix:
        return False
    try:
        network = ipaddress.ip_network(str(address) + suffix[0], strict=True)
        return network in (*KNOWN_V4, *LOCAL_V6)
    except ValueError:
        return False


def find_endpoints(text, aliases=None):
    aliases = aliases or {}
    result = []

    def add(match, encoding, address, cidr=False, end=None):
        end = match.end() if end is None else end
        if protected(address, aliases) and not (cidr and declared_network(text, end, address)):
            result.append(Finding(match.start(), end, encoding, address))

    for pattern, encoding, factory in ((IPV6, 'ipv6-text', ipaddress.IPv6Address),
                                       (IPV4, 'ipv4-text', ipaddress.IPv4Address)):
        for match in pattern.finditer(text):
            try:
                add(match, encoding, factory(match[0]), cidr=True)
            except ValueError:
                pass
            # Unbracketed mapped-IPv4 strings can carry a final hex port. Only
            # treat it as such when the prefix is itself an IPv4-mapped address.
            # Native IPv6 text should use [address]:port to avoid ambiguity.
            if encoding == 'ipv6-text' and re.search(r':[0-9a-fA-F]{4}$', match[0]):
                prefix = match[0].rsplit(':', 1)[0]
                try:
                    address = ipaddress.IPv6Address(prefix)
                    if address.ipv4_mapped:
                        add(match, encoding, address, end=match.start()+len(prefix))
                except ValueError:
                    pass
    for match in HEX.finditer(text):
        token = match[0].removeprefix('0x').removeprefix('0X')
        raw = bytes.fromhex(token)
        if len(raw) == 4:
            for value, encoding in ((raw[::-1], 'ipv4-hex-le'), (raw, 'ipv4-hex-be')):
                add(match, encoding, ipaddress.IPv4Address(value))
        else:
            # /proc/net/tcp6 and udp6 print four host-order 32-bit words.
            little = b''.join(raw[n:n+4][::-1] for n in range(0, 16, 4))
            for value, encoding in ((little, 'ipv6-proc-words-le'), (raw, 'ipv6-hex-be')):
                add(match, encoding, ipaddress.IPv6Address(value))
    for match in DECIMAL.finditer(text):
        value = int(match[0])
        if value > (1 << 32) - 1:
            continue
        raw = value.to_bytes(4, 'big')
        for data, encoding in ((raw, 'ipv4-integer-be'), (raw[::-1], 'ipv4-integer-le')):
            add(match, encoding, ipaddress.IPv4Address(data))
    # One report/replacement per token; mapped IPv6 wins over its embedded IPv4.
    ordered = sorted(result, key=lambda item: (item.start, -(item.end-item.start), item.encoding))
    unique = []
    for finding in ordered:
        if not unique or finding.start >= unique[-1].end:
            unique.append(finding)
    return unique


def redact_endpoints(text, aliases=None):
    """Replace endpoints only; ambiguous numeric measurements must fail closed.

    The scanner intentionally flags unlabelled integer/hex candidates. Automatic
    editing additionally requires an endpoint key or proc-style port, so a CRC
    or RSS number cannot silently become an address placeholder.
    """
    aliases = aliases or {}
    if any(not re.fullmatch(r'<[A-Z_]+>', alias) for alias in aliases.values()):
        raise ValueError('endpoint aliases must be irreversible uppercase placeholders')
    findings = find_endpoints(text, aliases)
    try:
        json.loads(text)
        structured = True
    except ValueError:
        structured = False
    strings = [(m.start(), m.end()) for m in re.finditer(r'"(?:\\.|[^"\\])*"', text)]
    replacements = []
    for item in findings:
        if 'hex' in item.encoding or 'integer' in item.encoding or 'proc-words' in item.encoding:
            port = re.match(r':[0-9a-fA-F]{4}(?![\w])', text[item.end:])
            key = re.search(r'''(?ix)(?:^|[\s{,])['"]?(?:ip|addr|address|peer|host|endpoint|local_ip|remote_ip|local_addr|remote_addr)['"]?\s*[:=]\s*['"]?$''', text[:item.start])
            if not port and not key:
                raise ValueError('ambiguous encoded endpoint candidate: manual context review required; no bytes changed')
        address = item.address
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        replacement = aliases.get(str(address), '<INTERNAL_ENDPOINT>')
        if structured and not any(start < item.start and item.end < end for start, end in strings):
            replacement = json.dumps(replacement)
        replacements.append((item, replacement))
    for item, replacement in reversed(replacements):
        text = text[:item.start] + replacement + text[item.end:]
    if structured:
        json.loads(text)
    if find_endpoints(text, aliases):
        raise ValueError('endpoint redaction did not close the gate')
    return text, sorted({item.encoding for item in findings})


def scan(repo_root, paths=None):
    root = pathlib.Path(repo_root).resolve()
    if paths is None:
        command = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'], capture_output=True)
        if command.returncode:
            raise ValueError('cannot enumerate tracked files: a git clone is required')
        paths = [pathlib.Path(name.decode()) for name in command.stdout.split(b'\0') if name]
        if not paths:
            raise ValueError('empty tracked-file set is not an acceptable scan')
    rows = []
    count = 0
    for relative in paths:
        relative = pathlib.Path(relative)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('scan paths must be repository-relative without parent traversal')
        path = root / relative
        if any(part.is_symlink() for part in (path, *path.parents)) or not path.is_file():
            raise ValueError('scan input missing, nonregular, or symlinked: ' + relative.as_posix())
        # Also inspect ASCII tokens embedded in non-UTF8 files, not just .txt files.
        text = path.read_bytes().decode('utf-8', errors='surrogateescape')
        count += 1
        for item in find_endpoints(text):
            line = text.count('\n', 0, item.start) + 1
            column = item.start - text.rfind('\n', 0, item.start)
            rows.append(dict(path=relative.as_posix(), line=line, column=column,
                             encoding=item.encoding))
    return dict(schema='private-endpoint-scan.v1', files=count, findings=rows,
                count=len(rows), verdict='FAIL' if rows else 'PASS',
                scope='current tracked tree only; no historical rewrite; no address values in output')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[2])
    parser.add_argument('--json', action='store_true')
    parser.add_argument('paths', nargs='*', type=pathlib.Path)
    args = parser.parse_args()
    try:
        result = scan(args.repo_root, args.paths or None)
    except (ValueError, OSError) as error:
        print('FAIL endpoint-scan: ' + str(error), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        for row in result['findings']:
            print('FAIL endpoint ' + '{path}:{line}:{column} {encoding}'.format(**row))
        print('{verdict} endpoint-scan files={files} findings={count}'.format(**result))
    return 1 if result['count'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
