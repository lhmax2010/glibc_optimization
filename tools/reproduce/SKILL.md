---
name: reproduce
description: Verify or rerun the Tizen glibc gated-trim Demo from its public evidence and frozen RPI4 workflows. Use when an engineer needs the Demo L1 host checks, the complete S4 and GStreamer board replay, or an acceptance verdict.
---

# Demo reproduction wrapper

Run from the repository root:

- Host verification: `bash tools/reproduce/reproduce.sh` (or `verify`).
- Full board replay: `bash tools/reproduce/reproduce.sh board --ip <address>`.

Interpret `PASS`, observed-waiver `EXPECTED`, unobserved
`REGISTERED/NOT-EVALUATED`, direction-only `REPORT_ONLY`, and `FAIL` using
[`README.md`](README.md) and the machine-readable
[`acceptance_bands.json`](acceptance_bands.json). Do not change frozen runner
parameters or duplicate their analysis logic; follow links to the HQ guide when a
board prerequisite is missing.
