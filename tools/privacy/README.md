# Current-tree endpoint gate

```sh
python3 tools/privacy/scan_endpoints.py --json
python3 -m unittest tools.privacy.test_endpoints
```

Default `reproduce.sh verify` runs this hard gate through `test_host.py`.
Only Python 3 and Git are required; no network, tags, board or optional RPM/GBS
tools are used. RC 0: zero findings; RC 1: findings; RC 2: incomplete scan.
Missing/nonregular/symlinked inputs fail closed.

Scope: project private IPv4 `192.168.0.0/16` plus IPv6 ULA/link-local networks.
Text, hex IPv4 (both byte orders), four-word proc IPv6 hex (including mapped IPv4),
and decimal IPv4 integers (both byte orders) are recognized. Only exact policy
CIDRs are exempt, never host `/32` or `/128`. Findings contain positions and
encoding, not addresses. Whole hashes are not searched for embedded substrings.

Scanning never edits. Publishers share `redact_endpoints`: irreversible tokens,
preserved ports/whitespace/lines. Numeric/short-hex tokens require an explicit
endpoint key or port before editing; ambiguous RSS/checksum values fail closed
for context review. Valid JSON must remain parseable. Never change a measurement
to silence a hit. Historical objects are not rewritten. See the
[dated correction](../../docs/weekend_redaction_20260911.md).
