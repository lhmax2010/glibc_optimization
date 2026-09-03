#!/bin/sh
set -u

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
mode=${1:-verify}

usage()
{
    cat <<'EOF'
usage:
  bash tools/reproduce/reproduce.sh [verify]
  bash tools/reproduce/reproduce.sh board --ip <address> [--output <host-dir>] [--artifact-dir <dir>]
       [--artifact-source frozen|reproducible|gbs]

verify is host-only and is the default. board performs the complete S4 + gst L2
workflow and requires the frozen ARM/media artifact bundle or documented build roots.
EOF
}

if [ "$mode" = board ]; then
    shift
    exec sh "$repo/tools/reproduce/board_workflow.sh" "$@"
fi
if [ "$mode" != verify ]; then
    usage >&2
    exit 2
fi
if [ "$#" -gt 1 ]; then
    usage >&2
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
        if grep -Eq '^(SKIPPED|REPORT_ONLY)[[:space:]]' "$log"; then
            grep -E '^(SKIPPED|REPORT_ONLY)[[:space:]]' "$log"
        else
            printf 'PASS\t%s\n' "$label"
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
    command -v python3 >/dev/null 2>&1 || { printf 'python3 is not available\n' >&2; return 1; }
    command -v git >/dev/null 2>&1 || { printf 'git is not available\n' >&2; return 1; }
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
        expected=$(git -C "$repo" rev-parse "${reference}^{commit}" 2>/dev/null) || { printf 'cannot resolve recorded delivery ref %s\n' "$reference" >&2; return 1; }
    fi
    if [ "$identity_mode" = report_only ]; then
        printf 'REPORT_ONLY\tdelivery-identity\tHEAD=%s is a development snapshot; checkout %s for frozen delivery verification\n' "$head" "$reference"
        return 0
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
    set -- \
      "$repo/README.md" \
      "$repo/docs/INDEX.md" \
      "$repo/docs/demo_package_20260902.md" \
      "$repo/docs/demo_narrative_20260901.md" \
      "$repo/docs/demo_reproduction_guide_20260901.md" \
      "$repo/docs/product_landing_recommendation_20260901.md"
    if [ -f "$repo/README.zh-CN.md" ]; then
        set -- "$@" "$repo/README.zh-CN.md"
    fi
    if [ -f "$repo/docs/demo_report.html" ]; then
        set -- "$@" "$repo/docs/demo_report.html"
    fi
    python3 "$repo/tools/reproduce/check_links.py" "$@"
}

host_tests()
{
    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
      tools/runners/s4_retention_20260901/test_host.py \
      tools/runners/gst_trim_cost_20260901/test_host.py \
      tools/report/test_build_demo_report.py \
      tools/reproduce/test_host.py \
      tools/reproduce/test_board_workflow_mocked_sdb.py
}

cd "$repo" || exit 2
printf 'MODE\thost verify\n'
printf 'SOURCE\t%s\n' "$(git rev-parse HEAD 2>/dev/null || printf unknown)"
check clean-environment clean_environment
check servicea-cyclic-cmp cyclic_replay
check f2-f3-attribution-cmp attribution_replay
check phenotype-cmp phenotype_replay
check batch-release-output batch_replay
check s4-public-replay s4_replay
check gst-public-replay-cmp gst_replay
check acceptance-v3 acceptance_replay
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
