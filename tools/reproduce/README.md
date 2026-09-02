# HQ one-command reproduction

```sh
bash tools/reproduce/reproduce.sh
bash tools/reproduce/reproduce.sh verify
bash tools/reproduce/reproduce.sh board --ip <address>
```

`verify` is the default, is host-only, and finishes in minutes. It runs every L1
recalculation, byte comparison, v2 acceptance check, local-link check, report
rebuild, and host test. Any failed row makes the process exit nonzero.

`board` is an hours-scale workflow. It requires an RPI4 running the frozen Tizen
Unified image, SDB, and the internal SHA-256-pinned ARM/media bundle described in
the [HQ guide](../../docs/demo_reproduction_guide_20260901.md#l2-prerequisites).
It orchestrates the existing S4 and gst runners; it does not copy their workload
or statistical logic. Set `DEMO_ARTIFACT_DIR` or pass `--artifact-dir` for the
bundle. Results default to a new `board_results/demo_workflow_<UTC timestamp>`
directory.

Both modes read [`acceptance_bands.json`](acceptance_bands.json). `PASS` means a
hard or tolerance gate passed, `EXPECTED` is a preregistered stability-monitor
alert contract (and on board runs still requires archive/cleanup/recheck),
`REPORT_ONLY` is foreign or unattributed state that was not altered, and `FAIL`
makes the run fail. Manual commands and evidence interpretation remain governed
by the [HQ reproduction guide](../../docs/demo_reproduction_guide_20260901.md).
