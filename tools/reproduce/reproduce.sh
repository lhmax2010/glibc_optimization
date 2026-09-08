#!/bin/bash
# Assignment/keywords first: POSIX special builtins outrank functions. Escaping
# their spelling also prevents alias expansion. No exec/exit/printf command is
# used to carry a refusal: the final real Python process owns its status/output.
POSIXLY_CORRECT=1
_reproduce_functions=
_reproduce_aliases=
_reproduce_enumeration='unavailable (function/alias enumeration failed)'
if \readonly -f builtin 2>/dev/null; then
    _reproduce_enumeration='blocked (builtin function shadows enumeration)'
elif _reproduce_functions=$(\builtin declare -F 2>/dev/null) &&
     _reproduce_aliases=$(\builtin alias -p 2>/dev/null); then
    _reproduce_enumeration=ok
fi

# Filesystem traversal and [[ ]] are not shell command-name lookups. Keep
# malformed/missing PATH and self-links diagnosable without invoking a function.
_reproduce_python=
_reproduce_python_problem=
_reproduce_search=${PATH:-}:
while [[ -n "$_reproduce_search" ]]; do
    _reproduce_dir=${_reproduce_search%%:*}
    _reproduce_search=${_reproduce_search#*:}
    _reproduce_candidate=${_reproduce_dir:-.}/python3
    if [[ -f "$_reproduce_candidate" && -x "$_reproduce_candidate" ]]; then
        if [[ "$_reproduce_candidate" -ef "$0" ]]; then
            _reproduce_python_problem=recursive
        else
            _reproduce_python=$_reproduce_candidate
        fi
        break
    fi
done
if [[ -z "$_reproduce_python" ]]; then
    _reproduce_python_problem=${_reproduce_python_problem:-missing}
    # A system interpreter is used only to print a refusal, never to bypass a
    # missing PATH dependency. If none is installed, the OS itself fails nonzero.
    for _reproduce_candidate in /usr/bin/python3 /usr/local/bin/python3; do
        if [[ -f "$_reproduce_candidate" && -x "$_reproduce_candidate" &&
              ! "$_reproduce_candidate" -ef "$0" ]]; then
            _reproduce_python=$_reproduce_candidate
            break
        fi
    done
fi
if [[ "$_reproduce_python" != /* ]]; then
    _reproduce_python=${PWD}/$_reproduce_python
fi
# Retain the captured table for rejection, but prevent even an absolute-path
# function from intercepting the interpreter. POSIX unset is a special builtin.
\unset -f "$_reproduce_python"

# The original shell never evaluates this workflow. Python alone passes the
# stored body to a fresh shell. Keep this BEFORE the final Python invocation.
\: <<'REPRODUCE_BODY_END'
# REPRODUCE_CLEAN_BODY
set -u
_reproduce_python=$REPRODUCE_RESOLVED_PYTHON

require_executable()
{
    "$_reproduce_python" -c '
import os, shutil, sys
name = sys.argv[1]
resolved = shutil.which(name)
injected = sorted(k for k in os.environ if k.startswith("BASH_FUNC_"))
startup = [k for k in ("BASH_ENV", "ENV") if os.environ.get(k)]
if injected or startup:
    print("FAIL\truntime-injection\tshell function/startup injection refused: " + ",".join(injected + startup), file=sys.stderr)
    sys.exit(1)
if not resolved or not os.path.isfile(resolved) or not os.access(resolved, os.X_OK):
    print("FAIL\truntime-preflight\tmissing default-verify command: " + name +
          " (real executable required; resolved=" + str(resolved) + ")", file=sys.stderr)
    sys.exit(1)
' "$1"
}

require_executable dirname || {
    printf 'OVERALL\tFAIL\n' >&2
    exit 2
}
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
mode=${1:-verify}

usage()
{
    cat <<'EOF'
usage:
  bash tools/reproduce/reproduce.sh [verify]
  bash tools/reproduce/reproduce.sh gbs [--lock-timeout <seconds>] [--output-dir <new-dir>]
  bash tools/reproduce/reproduce.sh board --ip <address> [--output <host-dir>] [--artifact-dir <dir>]
       [--artifact-source frozen|reproducible|gbs]

verify is host-only, normally completes in minutes, and is the default. It applies
static GBS package gates but never starts a real GBS build. gbs explicitly starts
the real build and needs the configured network repositories, root-capable GBS
environment, buildroot disk space, and substantially more time. board performs the
complete S4 + gst L2 workflow; GBS is the default artifact source after its
independent four-cell held-out validation passed.
EOF
}

if ! require_executable python3; then
    printf 'FAIL\truntime-preflight\tpython3 is not available; Python >=3.10 required\nOVERALL\tFAIL\n' >&2
    exit 2
fi

if [ "$mode" = board ]; then
    shift
    exec sh "$repo/tools/reproduce/board_workflow.sh" "$@"
fi
if [ "$mode" = gbs ]; then
    shift
    printf 'MODE\texplicit GBS build\n'
    gbs_rc=0
    python3 "$repo/tools/reproduce/check_gbs_package.py" --repo-root "$repo" --build "$@" || gbs_rc=$?
    if [ "$gbs_rc" -eq 0 ]; then
        printf 'OVERALL\tPASS\n'
        exit 0
    fi
    printf 'OVERALL\tFAIL\tRC=%s\n' "$gbs_rc"
    exit "$gbs_rc"
fi
if [ "$mode" != verify ]; then
    usage >&2
    exit 2
fi
if [ "$#" -gt 1 ]; then
    usage >&2
    exit 2
fi

missing=0
while IFS= read -r required; do
    if ! require_executable "$required"; then
        missing=1
    fi
done < "$repo/tools/reproduce/verify_commands.txt"
if [ "$missing" -ne 0 ]; then
    printf 'OVERALL\tFAIL\n'
    exit 2
fi

tmp=$(mktemp -d /tmp/glibc-memopt-reproduce.XXXXXX) || exit 2
cleanup()
{
    case "$tmp" in /tmp/glibc-memopt-reproduce.*) find "$tmp" -depth -delete 2>/dev/null || true;; esac
}
trap cleanup EXIT HUP INT TERM

failures=0
check()
{
    label=$1
    shift
    log="$tmp/$(printf '%s' "$label" | tr -c 'A-Za-z0-9._-' '_').log"
    if "$@" >"$log" 2>&1; then
        if grep -Eq '^SKIPPED[[:space:]]' "$log"; then
            grep -E '^SKIPPED[[:space:]]' "$log"
        else
            printf 'PASS\t%s\n' "$label"
            grep -E '^(REPORT_ONLY|INFO)[[:space:]]' "$log" || true
        fi
    else
        rc=$?
        printf 'FAIL\t%s\tRC=%s\n' "$label" "$rc"
        sed -n '1,120p' "$log"
        failures=$((failures + 1))
    fi
}

clean_environment()
{
    require_executable python3 || return 1
    require_executable git || return 1
    [ -d "$repo/.git" ] || { printf 'not a git clone: ZIP/source export is unsupported\n' >&2; return 1; }
    [ -f "$repo/data/raw/product_cyclic_target_probe_20260814/raw/timeseries.tsv" ] || { printf 'missing public ServiceA input\n' >&2; return 1; }
    [ -f "$repo/tools/reproduce/acceptance_bands.json" ] || { printf 'missing acceptance_bands.json\n' >&2; return 1; }
    [ -f "$repo/tools/reproduce/delivery_refs.json" ] || { printf 'missing delivery_refs.json\n' >&2; return 1; }
    if [ "${REPRODUCE_ALLOW_DIRTY:-0}" != 1 ]; then
        [ -z "$(git -C "$repo" status --porcelain)" ] || { printf 'working tree is dirty; set REPRODUCE_ALLOW_DIRTY=1 only for development\n' >&2; return 1; }
    fi
    head=$(git -C "$repo" rev-parse HEAD 2>/dev/null) || { printf 'cannot resolve HEAD\n' >&2; return 1; }
    if [ -n "${REPRODUCE_EXPECTED_SHA:-}" ]; then
        expected=$(git -C "$repo" rev-parse "${REPRODUCE_EXPECTED_SHA}^{commit}" 2>/dev/null) || { printf 'cannot resolve REPRODUCE_EXPECTED_SHA=%s\n' "$REPRODUCE_EXPECTED_SHA" >&2; return 1; }
        identity_mode=required
        reference=$REPRODUCE_EXPECTED_SHA
    else
        branch=$(git -C "$repo" branch --show-current 2>/dev/null)
        identity=$(python3 -c 'import json,sys; p=json.load(open(sys.argv[1])); r=p["branch_refs"].get(sys.argv[2],p["default"]); print(r["mode"]+"\t"+r["ref"])' "$repo/tools/reproduce/delivery_refs.json" "$branch") || { printf 'cannot read delivery reference\n' >&2; return 1; }
        identity_mode=${identity%%	*}
        reference=${identity#*	}
    fi
    if [ "$identity_mode" = report_only ]; then
        if expected=$(git -C "$repo" rev-parse "${reference}^{commit}" 2>/dev/null); then
            if [ "$head" = "$expected" ]; then
                printf 'REPORT_ONLY\tdelivery-identity\tthis branch is not the delivery snapshot; checkout %s for required verification\n' "$reference"
            else
                printf 'REPORT_ONLY\tdelivery-identity\tthis is not the delivery snapshot; checkout %s (HEAD=%s, delivery=%s)\n' "$reference" "$head" "$expected"
            fi
        else
            printf 'REPORT_ONLY\tdelivery-identity\tthis is not the delivery snapshot; checkout %s (reference unavailable in this clone)\n' "$reference"
        fi
        return 0
    fi
    if [ -z "${REPRODUCE_EXPECTED_SHA:-}" ]; then
        expected=$(git -C "$repo" rev-parse "${reference}^{commit}" 2>/dev/null) || { printf 'cannot resolve recorded delivery ref %s\n' "$reference" >&2; return 1; }
    fi
    [ "$head" = "$expected" ] || { printf 'HEAD %s does not equal delivery SHA %s\n' "$head" "$expected" >&2; return 1; }
}

cyclic_replay()
{
    out="$tmp/cyclic"
    python3 data/raw/cyclic_fall_mechanism_attribution_20260831/recompute_cyclic.py \
      --timeseries data/raw/product_cyclic_target_probe_20260814/raw/timeseries.tsv \
      --keys data/raw/product_cyclic_target_probe_20260814/raw/key_timeline.tsv \
      --output "$out" || return 1
    cmp "$out/cyclic_rounds.tsv" "$repo/data/raw/cyclic_fall_mechanism_attribution_20260831/cyclic_rounds.tsv" || return 1
    cmp "$out/cyclic_quality.json" "$repo/data/raw/cyclic_fall_mechanism_attribution_20260831/cyclic_quality.json" || return 1
    cmp "$out/serviceA_fault_boundary_comparison.tsv" "$repo/data/raw/cyclic_fall_mechanism_attribution_20260831/serviceA_fault_boundary_comparison.tsv"
}

attribution_replay()
{
    out="$tmp/attribution"
    python3 "$repo/tools/runners/cyclic_fall_attribution_20260901/analyze_attribution.py" \
      --timeseries "$repo/data/raw/product_cyclic_target_probe_20260814/raw/timeseries.tsv" \
      --keys "$repo/data/raw/product_cyclic_target_probe_20260814/raw/key_timeline.tsv" \
      --published-analyzer "$repo/tools/runners/product_cyclic_target_probe_20260814/analyze_cyclic.py" \
      --output "$out" || return 1
    for name in serviceA_large_steps.tsv serviceA_fall_recheck.tsv summary.json; do
        cmp "$out/$name" "$repo/data/raw/cyclic_fall_attribution_20260901/$name" || return 1
    done
}

phenotype_replay()
{
    out="$tmp/phenotypes"
    python3 "$repo/tools/runners/cyclic_fall_attribution_20260901/audit_phenotypes.py" \
      --repo-root "$repo" --output "$out" || return 1
    cmp "$out/release_ratio_phenotypes.tsv" "$repo/data/raw/cyclic_fall_attribution_20260901/release_ratio_phenotypes.tsv" || return 1
    cmp "$out/plateau_cyclic_crosscheck.tsv" "$repo/data/raw/cyclic_fall_attribution_20260901/plateau_cyclic_crosscheck.tsv"
}

batch_replay()
{
    python3 "$repo/tools/reproduce/check_batch_transcription.py" --repo-root "$repo" >/dev/null || return 1
    output=$(python3 -c 'import csv,statistics,sys; r=list(csv.DictReader(open(sys.argv[1]),delimiter="\t")); s=[x for x in r if x["series"]=="single"]; m=[x for x in r if x["series"]=="scale"]; print("single median=%.4f%%/%.6fMiB; demo=48.9%%/1.36MiB"%(statistics.median(float(x["reclaim_pct"]) for x in s),statistics.median(float(x["reclaimed_mib"]) for x in s))); print("scale process_count=%d pct_range=%.4f-%.4f%%"%(len(m),min(float(x["reclaim_pct"]) for x in m),max(float(x["reclaim_pct"]) for x in m)))' "$repo/data/raw/demo_reproduction_20260901/batch_release_phase.tsv") || return 1
    expected='single median=48.9451%/1.359375MiB; demo=48.9%/1.36MiB
scale process_count=8 pct_range=48.5232-49.3671%'
    [ "$output" = "$expected" ]
}

s4_replay()
{
    python3 "$repo/tools/runners/s4_retention_20260901/analyze_s4.py" \
      --replay-public "$repo/data/raw/s4_retention_20260901" --output "$tmp/s4" || return 1
    cmp "$tmp/s4/acceptance_input.json" "$repo/data/raw/s4_retention_20260901/acceptance_input.json"
}

a_anchor_replay()
{
    out="$tmp/a-anchor"
    python3 "$repo/tools/runners/a_anchor_replication_20260904/analyze_a_anchor.py" \
      --replay "$repo/data/raw/a_anchor_replication_20260904/a_cells.tsv" --output "$out" || return 1
    cmp "$out/group_summary.tsv" "$repo/data/raw/a_anchor_replication_20260904/group_summary.tsv" || return 1
    cmp "$out/decision.json" "$repo/data/raw/a_anchor_replication_20260904/decision.json"
}

gbs_heldout_replay()
{
    out="$tmp/gbs-heldout"
    python3 "$repo/tools/runners/gbs_heldout_validation_20260904/analyze_heldout.py" \
      --replay "$repo/data/raw/gbs_heldout_validation_20260904/heldout_cells.tsv" --output "$out" || return 1
    cmp "$out/heldout_cells.tsv" "$repo/data/raw/gbs_heldout_validation_20260904/heldout_cells.tsv" || return 1
    cmp "$out/decision.json" "$repo/data/raw/gbs_heldout_validation_20260904/decision.json"
}

gst_replay()
{
    out="$tmp/gst"
    python3 "$repo/tools/runners/gst_trim_cost_20260901/analyze_gst_trim_cost.py" \
      --replay-cycles "$repo/data/raw/gst_trim_cost_20260901/cycles.tsv" --output "$out" || return 1
    cp "$repo/data/raw/gst_trim_cost_20260901/cycles.tsv" "$out/cycles.tsv" || return 1
    cp "$repo/data/raw/gst_trim_cost_20260901/health.json" "$out/health.json" || return 1
    for name in repetitions.tsv arm_summary.tsv comparison.json; do
        cmp "$out/$name" "$repo/data/raw/gst_trim_cost_20260901/$name" || return 1
    done
    retry2="$repo/data/raw/gbs_rebaseline_20260903/gst_retry2"
    python3 "$repo/tools/runners/gst_trim_cost_20260901/analyze_gst_trim_cost.py" \
      --replay-cycles "$retry2/cycles.tsv" --output "$tmp/gst-retry2" || return 1
    for name in repetitions.tsv arm_summary.tsv comparison.json; do
        cmp "$tmp/gst-retry2/$name" "$retry2/$name" || return 1
    done
}

trimmable_estimator_replay()
{
    out="$tmp/trimmable-validation.tsv"
    python3 "$repo/tools/analysis/validate_trimmable_estimator.py" \
      "$repo/data/raw/trimmable_estimator_20260905/cases.tsv" --output "$out" || return 1
    cmp "$out" "$repo/data/raw/trimmable_estimator_20260905/validation.tsv"
}

acceptance_replay()
{
    [ -f "$tmp/s4/acceptance_input.json" ] || return 1
    python3 "$repo/tools/reproduce/evaluate_acceptance.py" \
      --bands "$repo/tools/reproduce/acceptance_bands.json" \
      --s4-summary "$tmp/s4/acceptance_input.json" \
      --gst-derived "$tmp/gst" \
      --output "$tmp/acceptance.json"
}

report_rebuild()
{
    [ -f "$repo/docs/demo_report.html" ] || return 1
    [ -f "$repo/tools/report/source_commit.txt" ] || return 1
    python3 "$repo/tools/report/build_demo_report.py" --repo-root "$repo" --output "$tmp/demo_report.html" || return 1
    cmp "$tmp/demo_report.html" "$repo/docs/demo_report.html"
}

link_check()
{
    template_root="$tmp/rendered-demo-entry"
    mkdir -p "$template_root" || return 1
    cp "$repo/tools/report/demo_README.md" "$template_root/README.md" || return 1
    cp "$repo/tools/report/demo_README.zh-CN.md" "$template_root/README.zh-CN.md" || return 1
    for directory in docs tools data packaging config; do
        ln -s "$repo/$directory" "$template_root/$directory" || return 1
    done
    set -- \
      "$repo/README.md" \
      "$repo/docs/INDEX.md" \
      "$repo/docs/demo_package_20260902.md" \
      "$repo/docs/demo_narrative_20260901.md" \
      "$repo/docs/demo_reproduction_guide_20260901.md" \
      "$repo/docs/a_anchor_replication_20260904.md" \
      "$repo/docs/gbs_heldout_validation_20260904.md" \
      "$repo/docs/product_landing_recommendation_20260901.md" \
      "$repo/docs/tool_provenance_20260903.md" \
      "$repo/docs/tizen_native_evidence_20260904.md" \
      "$repo/docs/trimmable_estimator_20260905.md" \
      "$template_root/README.md" \
      "$template_root/README.zh-CN.md"
    if [ -f "$repo/README.zh-CN.md" ]; then
        set -- "$@" "$repo/README.zh-CN.md"
    fi
    if [ -f "$repo/docs/demo_report.html" ]; then
        set -- "$@" "$repo/docs/demo_report.html"
    fi
    python3 "$repo/tools/reproduce/check_links.py" "$@" || return 1
    printf 'INFO\ttemplate-entry-links\ttemplates rendered at repository root and all links checked\n'
}

host_tests()
(
    # These are controlled, independent CLI fixtures. All normal child commands
    # retain the recursion guard; only this host-test boundary resets it.
    unset REPRODUCE_ACTIVE_ENTRYPOINT REPRODUCE_SANITIZED_ENTRYPOINT REPRODUCE_RESOLVED_PYTHON
    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
      tools/runners/s4_retention_20260901/test_host.py \
      tools/runners/gst_trim_cost_20260901/test_host.py \
      tools/runners/a_anchor_replication_20260904/test_host.py \
      tools/runners/gbs_heldout_validation_20260904/test_host.py \
      tools/runners/tizen_native_evidence_20260904/test_host.py \
      tools/runners/tizen_native_evidence_b2_20260904/test_host.py \
      tools/analysis/test_trimmable_estimator.py \
      tools/report/test_build_demo_report.py \
      tools/reproduce/test_host.py \
      tools/reproduce/test_board_workflow_mocked_sdb.py \
      tools/runners/tool_provenance_20260903/test_host.py
)

cd "$repo" || exit 2
printf 'MODE\thost verify\n'
printf 'SOURCE\t%s\n' "$(git rev-parse HEAD 2>/dev/null || printf unknown)"
check clean-environment clean_environment
check servicea-cyclic-cmp cyclic_replay
check f2-f3-attribution-cmp attribution_replay
check phenotype-cmp phenotype_replay
check batch-release-output batch_replay
check s4-public-replay s4_replay
check a-anchor-public-replay-cmp a_anchor_replay
check gbs-heldout-public-replay-cmp gbs_heldout_replay
check gst-public-replay-cmp gst_replay
check trimmable-estimator-cmp trimmable_estimator_replay
check acceptance-v4 acceptance_replay
if [ -f "$repo/docs/demo_report.html" ] && [ -f "$repo/tools/report/source_commit.txt" ]; then
    check offline-report-byte-cmp report_rebuild
else
    printf 'SKIP\toffline-report-byte-cmp\tnot checked in yet\n'
fi
check local-link-check link_check
check reproducible-build-paths python3 "$repo/tools/reproduce/check_reproducible_build_paths.py"
check gbs-package python3 "$repo/tools/reproduce/check_gbs_package.py" --repo-root "$repo"
if [ "${REPRODUCE_SKIP_TESTS:-0}" != 1 ]; then
    check host-tests host_tests
fi
printf 'REGISTERED/NOT-EVALUATED\tstability-monitor s4-a-alloc-bench-cpu-relative\tknown-alert waiver max=2; no observation in host verify\n'
if [ "$failures" -ne 0 ]; then
    printf 'OVERALL\tFAIL\titems=%s\n' "$failures"
    exit 1
fi
printf 'OVERALL\tPASS\n'
REPRODUCE_BODY_END

"$_reproduce_python" -c '
import os, shutil, sys
from pathlib import Path

def refuse(label, reason):
    print("FAIL\t" + label + "\t" + reason, file=sys.stderr, flush=True)
    print("OVERALL\tFAIL", file=sys.stderr, flush=True)
    sys.exit(2)

if sys.version_info < (3, 10):
    refuse("python-runtime", "Python >=3.10 required (Path.write_text newline support); found " + sys.version.split()[0])
script, python, problem, enumeration, functions, aliases, *arguments = sys.argv[1:]
if "REPRODUCE_SANITIZED_ENTRYPOINT" in os.environ:
    refuse("runtime-injection", "pre-set sanitation marker refused (including empty values)")
if os.environ.get("REPRODUCE_ACTIVE_ENTRYPOINT") or problem == "recursive":
    refuse("runtime-recursion", "reproduce.sh already active or python3 resolves to entrypoint; recursive invocation refused")
markers = sorted(k for k in os.environ if k.startswith("BASH_FUNC_") or k in ("BASH_ENV", "ENV"))
if enumeration != "ok":
    refuse("runtime-injection", "function/alias enumeration " + enumeration + "; fail closed")
if functions or aliases or markers:
    refuse("runtime-injection", "shell function/startup injection refused: functions=" +
           repr(functions.splitlines()) + "; aliases_present=" + str(bool(aliases)) +
           "; environment markers=" + repr(markers))
if problem:
    refuse("runtime-preflight", "python3 is not available in PATH; Python >=3.10 required")
shell = shutil.which("bash")
if not shell or not os.path.isfile(shell) or not os.access(shell, os.X_OK):
    refuse("runtime-preflight", "missing default-verify command: bash (real executable required)")
try:
    body = Path(script).read_text().split("\n# REPRODUCE_CLEAN_BODY\n", 1)[1].split("\nREPRODUCE_BODY_END\n", 1)[0]
except (OSError, IndexError) as error:
    refuse("runtime-preflight", "cannot read entrypoint body: " + str(error))
environment = {k: v for k, v in os.environ.items()
               if k not in ("BASH_ENV", "ENV", "POSIXLY_CORRECT") and not k.startswith("BASH_FUNC_")}
environment["REPRODUCE_ACTIVE_ENTRYPOINT"] = str(os.getpid())
environment["REPRODUCE_SANITIZED_ENTRYPOINT"] = str(os.getpid())
environment["REPRODUCE_RESOLVED_PYTHON"] = os.path.abspath(python)
print("PASS\tpython-runtime\t" + sys.version.split()[0], flush=True)
os.execve(os.path.abspath(shell), [shell, "--noprofile", "--norc", "-p", "-c", body, script, *arguments], environment)
' "$0" "$_reproduce_python" "$_reproduce_python_problem" "$_reproduce_enumeration" "$_reproduce_functions" "$_reproduce_aliases" "$@"
