# Demo rehearsal read-only board audit

This harness reproduces the identity, environment, and hygiene evidence collected
for `docs/demo_rehearsal_20260902.md`. It creates files only in the host output
directory. Every board-side command is read-only and emits a remote `RC=0` plus a
`DONE_*` marker.

It does not push files, create board directories, run workloads, modify governors,
install packages, reboot, or remove reported residue. Cleanup remains a separate,
explicitly approved operation.

```sh
export SDB_SERIAL='<TEST_BOARD_IP>:26101'
mkdir -p board_results/demo_rehearsal_20260902/recheck
sh tools/runners/demo_rehearsal_20260902/read_only_board_audit.sh \
  board_results/demo_rehearsal_20260902/recheck
```

Successful completion writes `IDENTITY_AND_ENV_GATE_PASS` to `gate_verdict.txt`
and `READ_ONLY_HYGIENE_AUDIT_DONE` to `audit_verdict.txt`. Interpret residue only
with the ownership rules in the report; this script deliberately does not decide
or execute cleanup.
