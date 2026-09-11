# HQ one-command reproduction

```sh
bash tools/reproduce/reproduce.sh
bash tools/reproduce/reproduce.sh verify
bash tools/reproduce/reproduce.sh gbs
bash tools/reproduce/reproduce.sh board --ip <address>
```

`verify` is the default, is host-only, and finishes in minutes. It must run from a
real `git clone`; GitHub ZIP/source exports are unsupported because delivery
identity is part of the contract. It runs every L1 recalculation, byte comparison,
v4 acceptance check, local-link check, report rebuild, static GBS package contract,
and host test. It never starts a real GBS build. Any failed row makes the process
exit nonzero.

## Default verify system dependencies

Default verify requires Linux, **Python >=3.10**, Git, Bash/POSIX sh, and the
following explicit commands. Base-image utilities are dependencies too; the old
“only Git + Python” wording was incomplete. The Python floor follows the report
builder's `Path.write_text(..., newline=...)` (3.10); code also uses 3.9 string
prefix/suffix methods. Runtime preflight rejects an older interpreter with its
observed version before any replay.

The executable whitelist is [`verify_commands.txt`](verify_commands.txt):

```text
awk bash cat cmp cp date dirname find git grep ln mkdir mktemp python3
sed sh sha256sum sleep sort stat tr wc
```

`awk`, `date`, `sleep` exercise the local sampler tests; `sha256sum`, `wc`, `stat`,
and `sort` exercise archived-file and mocked-workflow integrity; `cat` supplies
CLI output and fixtures. `cmp`, `cp`, `ln`, `mkdir`, `mktemp`, `find` handle replay
and temporary trees; `dirname`, `grep`, `sed`, `tr` support the shell entrypoint.
GNU-compatible `date -Ins/+%s%N` and `stat -c` are required (Ubuntu/Debian coreutils).
Every whitelist command is checked by preflight for resolution to a real,
executable file using Python `shutil.which`, not shell `command -v`. Python is
bootstrapped by filesystem PATH traversal, never by invoking a shell function.
Before ordinary commands run, an assignment enables Bash POSIX lookup: its
[special builtins precede functions](https://www.gnu.org/software/bash/manual/html_node/Special-Builtins.html).
Escaped `readonly -f builtin` therefore checks the enumeration entry without
calling a shadowing `readonly` or `builtin` function. If `builtin` is shadowed,
enumeration is refused; otherwise `builtin declare -F` and `builtin alias -p`
must both succeed. An unavailable enumerator fails closed, never as an empty
table. These tables include **unexported** entries left by a startup file that unset its own
`BASH_ENV`/`ENV` markers or deleted itself. Any such state or exported `BASH_FUNC_*`
marker is `FAIL runtime-injection`, not a misleading missing-command diagnostic.
An actually absent/non-executable command is separately `FAIL runtime-preflight`
with `missing default-verify command: <name>`.

The **last command of the launcher is the resolved absolute Python executable**;
its exit status is naturally the script status. Rejection prints a nonempty
`FAIL runtime-injection` diagnostic and returns RC=2 in Python, without shell
`exec`, `exit`, or `printf`. The inert workflow body precedes that last command;
there is no successful trailing command to overwrite a rejection. POSIX `unset`
also removes an absolute-interpreter-path function after recording the table.
The resolved real Python uses `os.execve` on the accepted path to start a new Bash with
`--noprofile --norc -p`, stripping `BASH_ENV`, `ENV`, every `BASH_FUNC_*` entry,
and bootstrap-only `POSIXLY_CORRECT`.
Only the workflow body from the same entrypoint file is passed to that shell;
there is no trusted-boolean shortcut back through the public launcher. A pre-set
`REPRODUCE_SANITIZED_ENTRYPOINT` (even empty) fails closed before any ordinary
command; `REPRODUCE_ACTIVE_ENTRYPOINT` also rejects self-recursion. Only controlled
host-test fixtures clear these internal markers for independent CLI invocations.
This relies on the installed Bash/Python, enabled POSIX special builtins and
trusted filesystem/PATH. It is not a hostile-host sandbox or proof of code
executed before entrypoint control. If PATH lacks Python, a system Python is used
only to diagnose refusal, never to bypass the dependency gate.

**Environment Modules:** rejection intentionally includes unrelated exported
functions such as `module`, not just whitelist command names. Do not source this
workflow into an interactive session. For a normal host that exports such helpers,
start a clean process (substitute the actual installed absolute paths if needed):

```sh
/usr/bin/env -i PATH="$PATH" HOME="$HOME" /bin/bash --noprofile --norc -p \
  tools/reproduce/reproduce.sh verify
```

This removes startup/function markers before Bash loads them; it does not edit
shell configuration. Explicit GBS/board modes may need additional documented
environment variables; pass only the required trusted ones, not startup hooks.
No other PATH executable is
available in the mandatory minimal profile. Git/Python retain their installed
runtime libraries; this is a command-PATH isolation test, not an OS-container test.
`gbs`, `rpm`, `rpm2cpio`, `cpio`, `rpmspec`, an ARM compiler, SDB, network access,
and root are not default-verify prerequisites. Optional syntax/build checks emit an
explicit `SKIPPED` reason when their environment is absent; their real execution is
reserved for the explicit `gbs` or `board` mode.

Development-only verify overrides are explicit: `REPRODUCE_ALLOW_DIRTY=1` permits a dirty
tree, `REPRODUCE_SKIP_TESTS=1` skips the nested host-test row, and
`REPRODUCE_EXPECTED_SHA=<commit-or-ref>` overrides the recorded delivery reference.
These overrides do not bypass the explicit GBS clean-execution provenance gate.
Without an override, `verify` requires `HEAD` to resolve to the delivery ref in
[`delivery_refs.json`](delivery_refs.json).

## Mandatory pre-delivery clone matrix

After cutting a frozen snapshot and before declaring it ready, run the remote-only
pre-delivery gate:

```sh
bash tools/reproduce/predelivery_check.sh \
  --repo-url "$(git remote get-url origin)" \
  --branch demo \
  --tag demo-v11
```

The script performs three fresh HQ-shaped clones from the supplied remote:

```sh
git clone --branch demo <url>
git clone --branch demo-v11 <url>
git clone <url>                 # remote default must be main
```

Each clone is verified under six environment profiles: GBS/RPM both
discoverable, only RPM discoverable, only GBS discoverable, and neither
discoverable (`minimal-whitelist`), plus `broken-tools` (rpmspec and gbs return
nonzero if invoked), plus `startup-injection` using the minimal whitelist.
The latter runs 43 rejection cases: the original five startup/marker variants,
six function sets × six startup/marker contexts, and two unavailable-enumerator
cases. Function sets cover exec, exit, exec+exit, builtin, builtin+exec+exit,
and combined helper shadowing (readonly/command/declare/compgen/set/export/colon).
Contexts include self-clearing markers, unexported-only functions, self-deleting
startup files, pre-set nonempty/empty markers, and self-delete+pre-set marker.
Every case requires **RC=2, a nonempty explicit rejection diagnostic, zero spoofed
command calls**, no `MODE host verify`, and no `OVERALL PASS`;
it then runs a **real, clean, complete verify**. Rejection is not counted as a
successful replay. [`make_verify_path.py`](make_verify_path.py) symlinks only
the explicit command list above; it does not enumerate or append the host PATH.
Discoverable optional tools are deterministic
fail-if-invoked stubs, so this gate proves that default verify does not execute them;
`rpmspec -P` alone uses a local parser fixture because that optional syntax branch is
intentionally exercised, while a broken rpmspec must emit a reasoned `SKIPPED`.
This is `3 × 6 = 18` complete verifies, plus 129 expected-rejection probes, with nested host
tests enabled. The demo branch and detached tag must pass required delivery identity;
main keeps its recorded `REPORT_ONLY` identity semantics. Every check must print
`host-tests=PASS OVERALL=PASS`, and the final row must be
`OVERALL PASS checks=18`, or the snapshot is not delivery-ready. Future snapshots
pass their new annotated tag with `--tag demo-vN`; the script also defaults that
value from [`delivery_refs.json`](delivery_refs.json).

Delivery also requires one actual `reproduce.sh gbs --output-dir <new-dir>` pass,
separate from the PATH fixtures. Archive its summary in `data/raw/`, including RPM
NVR/SHA, all three ELF hashes, elapsed time, and any buildroot residue. A verify
matrix pass by itself does not establish the actual GBS build path.

## Default host-test dependency audit

2026-09-11 candidate status: the new system-cleanup replay requires a contract
tag by name, but the no-tag delivery-identity fixtures intentionally omit it.
Eight subcases failed; v12 delivery is stopped and demo-v11 remains effective.
This is an unresolved host-replay dependency, not a failed board measurement.
Do not skip these tests to obtain PASS. See the [blocker record](../../docs/demo_v12_delivery_blocker_20260911.md).

The current entrypoint executes thirteen test files (the original eleven groups
plus the accepted-matrix and directory-disposition groups). Their external-command boundary is:

| Test file | Commands beyond Python code | Default-verify treatment |
|---|---|---|
| `tools/runners/s4_retention_20260901/test_host.py` | `python3`, `sh` for a local sampler fixture | Base runtime only; no board command |
| `tools/runners/gst_trim_cost_20260901/test_host.py` | `python3` | Required runtime |
| `tools/runners/a_anchor_replication_20260904/test_host.py` | `python3` | Required runtime |
| `tools/runners/gbs_heldout_validation_20260904/test_host.py` | `python3` | Required runtime |
| `tools/runners/tizen_native_evidence_20260904/test_host.py` | `python3`, `sh -n` | Shell syntax check only; no SDB/gdb |
| `tools/runners/tizen_native_evidence_b2_20260904/test_host.py` | `sh -n` | Shell syntax check only; no SDB/gdb |
| `tools/analysis/test_trimmable_estimator.py` | current Python interpreter | Required runtime |
| `tools/report/test_build_demo_report.py` | `python3`, `git` | Required delivery provenance check |
| `tools/reproduce/test_host.py` | `git`, `python3`, base shell utilities | RPM/GBS paths use self-contained stubs; ARM build check is explicit `SKIPPED` without its environment |
| `tools/reproduce/test_board_workflow_mocked_sdb.py` | `sh`; creates its own `sdb` stub | No real SDB or board connection |
| `tools/runners/tool_provenance_20260903/test_host.py` | `python3`; local XML fixtures | No network or repository download |
| `tools/runners/system_level_before_after_20260908/test_accepted_composition.py` | `python3`, `git`; public compact files | Byte-exact five-file replay, immutable historical STOP, cleanup proofs; no local full archives or board access required |
| `tools/runners/system_level_before_after_20260908/test_directory_disposition.py` | current Python interpreter; mocked SDB transport | Directory/UID/200-byte/health failure paths; no actual SDB or root |

System before-after L1 is included in `verify`: the fixed analyzer replays the
accepted 18+3 parsed points and GST cycles, compares five derived files, and
independently checks the delayed cleanup logs. This does not rerun any accepted
measurement. The nonempty GDB directories remain REPORT_ONLY, not "zero residue".
See the [guide](../../docs/demo_reproduction_guide_20260901.md#l1-system-before-after).

The top-level static GBS check parses the spec and manifest in Python. `rpmspec -P`
is optional and reports `SKIPPED` when absent, non-executable, timed out, or returning
nonzero; the reason includes its error/exit status. Python spec/%files/manifest
checks remain hard gates. The path-reproducibility check requires
`DEMO_TOOLCHAIN_ROOT` and `DEMO_GST_SYSROOT`; without both it reports a reasoned
`SKIPPED`. No test may use `assertIsNotNone(shutil.which(...))` to promote an
optional RPM/GBS/ARM command into a default dependency.

`board` is an hours-scale workflow. It requires an RPI4 running the frozen Tizen
Unified image, SDB, and the internal SHA-256-pinned ARM/media bundle described in
the [deliverables manifest](deliverables_manifest.json) and
[HQ guide](../../docs/demo_reproduction_guide_20260901.md#l2-prerequisites).
It orchestrates the existing S4 and gst runners; it does not copy their workload
or statistical logic. Set `DEMO_ARTIFACT_DIR` or pass `--artifact-dir` for the
bundle. Results default to a new `board_results/demo_workflow_<UTC timestamp>`
directory.

For the fallback fixed-directory cross-build, set both
`DEMO_TOOLCHAIN_ROOT=/path/to/scratch.armv7l.0` and
`DEMO_GST_SYSROOT=/path/to/gstreamer/scratch.armv7l.0`. The first supplies the
ARM compiler/sysroot used by `alloc_bench` and `reclaim_probe`; the second must
contain the GStreamer/GLib ARM headers, pkg-config metadata, and link libraries for
`gst_loop_decode`. `check_reproducible_build_paths.py` builds from two different
checkout paths and compares all three hashes; if either variable is absent it
prints an explicit `SKIPPED` row.

The explicit GBS build entry is
`bash tools/reproduce/reproduce.sh gbs --output-dir /path/to/new-gbs-bundle`, which uses
[`packaging/glibc-memopt-tools.spec`](../../packaging/glibc-memopt-tools.spec) and
produces one RPM with all three ELF files. It requires network access to the pinned
repositories, a root-capable GBS environment, sufficient buildroot disk space, and
substantially more time than the minutes-scale host verify. Its buildroot is unique
per run and protected by a cross-process lock. A missing/broken GBS/RPM command,
unwritable lock or lock timeout emits `NOT-EVALUATED` plus `OVERALL FAIL` (RC=2).
A nonzero GBS result is classified in this explicit priority order:

| Diagnostic (first matching row wins) | Label / exit |
|---|---|
| Definite environment diagnostic: no disk space, permission denied, shared-library loader failure | `NOT-EVALUATED gbs-build-environment`, RC=2 |
| Missing-header diagnostic (`file not found` / `No such file`), even with a source location | `NOT-EVALUATED gbs-build-unknown`, RC=2; **manual second judgment required**, not an environment finding |
| Other explicit source-file/line compiler error | `FAIL gbs-package-artifact`, RC=1 |
| Unrecognized GBS failure | `NOT-EVALUATED gbs-build-unknown`, RC=2; manual judgment, no package-defect claim |

Broken RPM inspection/extraction tools remain environment failures (RC=2).
Missing RPM/ELF, ELF hash drift, or RPM NVR/architecture/%files identity drift
remains hard `FAIL` (RC=1). RPM wrapper metadata SHA drift is `REPORT_ONLY`,
not an ELF reproducibility gate. A successful
static check cannot make an unevaluated explicit build pass. `--output-dir` must be
new; `PASS` requires the RPM and all three ELF files to have been generated,
inspected, copied there and hash-verified. Without this option, the checker chooses
a new local `board_results/gbs_build_*` output directory. The bundle includes a
machine-readable `gbs_build_summary.json`.

### GBS execution provenance

Use a **clean, committed clone**. After taking the lock, before invoking GBS, the
checker creates `execution_provenance.json` in the unique build workspace:
workflow HEAD, `git status --porcelain --untracked-files=all` and its dirty flag,
entrypoint/checker SHA-256, Python version, and UTC timestamp. Schema v2 binds the
complete file set below to `git show <workflow_commit>:<path>` byte hashes in
`committed_file_sha256`, independently of the porcelain summary:

- `tools/reproduce/reproduce.sh` and `tools/reproduce/check_gbs_package.py`;
- `config/gbs_llvm.conf` and `config/gbs.conf`;
- `tools/reproduce/deliverables_manifest.json`;
- every tracked `packaging/*.spec` in that commit.

Dirty state is `FAIL gbs-dirty-snapshot` (RC=1), rejected before GBS. A
`skip-worktree` modification still fails the committed-byte comparison. The checker
captures the proof file's own `provenance_sha256` **before** GBS. After GBS returns,
it reopens the proof without following symlinks, checks the bytes first, then
validates the re-read JSON and snapshot. Rewrite, truncation, deletion or symlink
substitution produces `FAIL gbs-proof-integrity` / `proof rewritten during build`
(RC=1), even when GBS returns zero. It repeats the byte/JSON checks on the output
copy, and once more before a PASS summary is written. The
manifest's `source_commit` remains the separate frozen **payload source** commit.

The [publisher](../runners/demo_v7_delivery_20260907/publish_gbs_build.py) must run
at the same clean HEAD and only validates/copies the execution proof and summary,
byte-for-byte. It never fills in hashes after execution. Publish to an external or
git-ignored directory first, then import the validated records into `data/raw/`
in a later commit. Missing proof, changed HEAD, dirty state or mismatched hashes
refuse publication with nonzero exit; the published proof copy is rechecked too.
The checker also saves raw combined GBS stdout/stderr as `gbs.log`, computes
`gbs_log_sha256`, and verifies the bundle copy. Publisher requires that raw log to
match before publishing the unchanged summary containing its hash; raw logs remain
local because they may contain host paths. Missing/altered/symlinked logs fail.
The filtered `workflow_summary.tsv` is not the raw log and cannot substitute for it.
Delivery host tests compare the current execution record with its recorded Git
objects and delivery bytes. Older v8/v9/v10/v11 proof stays immutable and is checked against
its recorded commit, not represented as a v12 execution. The historical
[v9 real build archive](../../data/raw/demo_v9_delivery_20260907/gbs/README.md)
binds that execution's six files; raw logs stay local and are available on request.
The [v10 real build archive](../../data/raw/demo_v10_delivery_20260908/gbs/README.md)
remains historical, as does the [v11 real build archive](../../data/raw/demo_v11_delivery_20260908/gbs/README.md).
The [v12 candidate real build archive](../../data/raw/demo_v12_delivery_20260911/gbs/README.md)
binds the entrypoint including the accepted-system-matrix L1 replay and the other five
committed files to current main bytes; publication copied the execution proof unchanged.
It does not establish delivery readiness: the independent host-test gate stopped v12.

### Provenance capability boundary

This is a self-recorded (self-attested) local provenance document: it detects
accidental changes and silent file tampering at the checked boundaries, **not a
cryptographically signed remote attestation**. It does not defend against a hostile
host able to replace Python/Git/the checker, forge the record and all its hashes,
or change files after the final verification. `entrypoint_sha256` means **bytes of
the repository entrypoint file**, not proof of the actual caller or launch chain.
Neither unsigned tags nor these hashes establish an independent signing identity.

GBS may leave root-owned files in its unique temporary workspace; an unprivileged
checker cannot always delete them (EPERM). Cleanup failure alone is
`REPORT_ONLY gbs-buildroot-residue <path>` and is included in the summary, even when
artifact gates passed. Inspect the exact generated path from that row and clean it
with `sudo rm -rf -- <path>` (only that run's `/tmp/glibc-memopt-gbs-*` workspace).
The checker never attempts an automatic sudo deletion. A residue cannot turn an
artifact/environment failure into a pass.

The GBS artifacts participated in the fixed-contract H-V calibration sample, so
that sample alone is not independent evidence. A separately tagged four-cell
GBS-only held-out contract, excluded from band construction, passed 4/4. GBS is now
the L2 default; select the archived fallback explicitly with
`--artifact-source frozen`. The media file is never built by either path and must
come from the delivery location supplied with the package. See the
[held-out report](../../docs/gbs_heldout_validation_20260904.md).
The four held-out cells cover **alloc_bench only**. GBS gst_loop_decode/reclaim_probe
have the manifest identity chain; their board behavior comes from the earlier
September 3 retry2, not those held-out cells. Its existing gst compact evidence is
now [publicly replayable](../../data/raw/gbs_rebaseline_20260903/gst_retry2/README.md).

Both modes read [`acceptance_bands.json`](acceptance_bands.json). `PASS` means a
deterministic item, validity gate, or tolerance band passed. `EXPECTED` means an
observed registered stability-monitor alert matched its waiver and was archived,
cleaned, and rechecked; an unobserved registration is
`REGISTERED/NOT-EVALUATED`. The gst p99 direction and foreign/unattributed state are
`REPORT_ONLY`; neither direction can fail acceptance when the fixed-contract
nearest-rank/dispersion rule was executed correctly. If a board reports
`visible=true`, retain the output and all three repeats, report the margin over the
none-arm dispersion, do not relabel it as workflow failure, and escalate it as a
batch-specific business-cost finding.

Acceptance v4 uses the fixed-contract H-V A-anchor calibration shared by frozen and GBS:
mixed `52.794499% ±4.304705 pp` and medium-only
`50.669791% ±4.918088 pp`, each from eight combined observations. The derivation
and public replay are in the
[A-anchor report](../../docs/a_anchor_replication_20260904.md). The values remain
calibration limits; independent GBS status comes from the excluded four-cell
[held-out run](../../docs/gbs_heldout_validation_20260904.md), which passed 4/4
without modifying them.

## Board-round evidence ordering

For every new board round, commit the immutable contract and its analyzer first and
create an **annotated** pre-run tag, retaining the tagger timestamp. Push the
contract commit and tag, record push completion in UTC, and wait at least ten
minutes from that recorded push to the first board operation. Record both times
and their actual interval with the results. A shorter interval needs an explicit
PM decision recorded before execution. Historical lightweight tags remain intact
and are identified as such; do not fabricate retrospective timestamps. Board results,
compact evidence, and conclusions land in a separate later commit. Without the
pre-run commit/tag, historical wording is “fixed-contract replay”, not
“preregistered”.

The board preflight hard-gates remote `id -u=0`, writability of all four governor
controls, and writability of `/opt/usr`. Without the internal bundle described by
the manifest, board mode cannot start. Manual commands and evidence interpretation
remain governed by the [HQ reproduction guide](../../docs/demo_reproduction_guide_20260901.md).

> Public archive note: application/process names are aliases. Host-side paths are
> sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is
> intentionally public for reproducibility.
