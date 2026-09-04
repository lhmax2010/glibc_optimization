#!/usr/bin/env bash
set -u

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
repo_url=${PREDELIVERY_REPO_URL:-}
delivery_branch=${PREDELIVERY_BRANCH:-demo}
delivery_tag=${PREDELIVERY_TAG:-}
default_branch=${PREDELIVERY_DEFAULT_BRANCH:-main}

usage()
{
    cat <<'EOF'
usage: bash tools/reproduce/predelivery_check.sh [options]

Clone the delivery from its remote in all three HQ checkout shapes and run the
complete host verify (nested host tests are never skipped):
  branch    git clone --branch demo <url>
  tag       git clone --branch <delivery-tag> <url>
  default   git clone <url>  (must check out main)

options:
  --repo-url <url>        remote URL (default: current origin)
  --branch <name>         frozen delivery branch (default: demo)
  --tag <name>            annotated delivery tag (default: delivery_refs.json)
  --default-branch <name> expected default checkout branch (default: main)
  -h, --help              show this help
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --repo-url) [ "$#" -ge 2 ] || { usage >&2; exit 2; }; repo_url=$2; shift 2;;
        --branch) [ "$#" -ge 2 ] || { usage >&2; exit 2; }; delivery_branch=$2; shift 2;;
        --tag) [ "$#" -ge 2 ] || { usage >&2; exit 2; }; delivery_tag=$2; shift 2;;
        --default-branch) [ "$#" -ge 2 ] || { usage >&2; exit 2; }; default_branch=$2; shift 2;;
        -h|--help) usage; exit 0;;
        *) printf 'unknown argument: %s\n' "$1" >&2; usage >&2; exit 2;;
    esac
done

command -v git >/dev/null 2>&1 || { printf 'git is not available\n' >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { printf 'python3 is not available\n' >&2; exit 2; }

if [ -z "$repo_url" ]; then
    repo_url=$(git -C "$repo_root" remote get-url origin 2>/dev/null) || {
        printf 'cannot resolve origin; pass --repo-url <url>\n' >&2
        exit 2
    }
fi
if [ -z "$delivery_tag" ]; then
    delivery_tag=$(python3 -c 'import json,sys; p=json.load(open(sys.argv[1])); print(p["branch_refs"][sys.argv[2]]["ref"])' \
        "$repo_root/tools/reproduce/delivery_refs.json" "$delivery_branch") || {
        printf 'cannot resolve delivery tag from delivery_refs.json\n' >&2
        exit 2
    }
fi

tmp=$(mktemp -d /tmp/glibc-memopt-predelivery.XXXXXX) || exit 2
cleanup()
{
    case "$tmp" in
        /tmp/glibc-memopt-predelivery.*) find "$tmp" -depth -delete 2>/dev/null || true;;
    esac
}
trap cleanup EXIT HUP INT TERM

failures=0
run_shape()
{
    shape=$1
    ref=$2
    destination="$tmp/$shape"
    log="$tmp/$shape.log"

    if [ "$shape" = default ]; then
        if ! git clone --quiet "$repo_url" "$destination" >"$log" 2>&1; then
            printf 'FAIL\t%s\tclone failed\n' "$shape"
            sed -n '1,120p' "$log"
            failures=$((failures + 1))
            return
        fi
    else
        if ! git clone --quiet --branch "$ref" "$repo_url" "$destination" >"$log" 2>&1; then
            printf 'FAIL\t%s\tclone ref=%s failed\n' "$shape" "$ref"
            sed -n '1,120p' "$log"
            failures=$((failures + 1))
            return
        fi
    fi

    checked_branch=$(git -C "$destination" branch --show-current 2>/dev/null)
    if [ "$shape" = branch ] && [ "$checked_branch" != "$delivery_branch" ]; then
        printf 'FAIL\t%s\texpected branch=%s observed=%s\n' "$shape" "$delivery_branch" "$checked_branch"
        failures=$((failures + 1))
        return
    fi
    if [ "$shape" = tag ]; then
        checked_tag=$(git -C "$destination" describe --tags --exact-match HEAD 2>/dev/null || true)
        tag_type=$(git -C "$destination" cat-file -t "refs/tags/$delivery_tag" 2>/dev/null || true)
        if [ -n "$checked_branch" ] || [ "$checked_tag" != "$delivery_tag" ] || [ "$tag_type" != tag ]; then
            printf 'FAIL\t%s\texpected detached annotated tag=%s branch=%s tag=%s type=%s\n' \
                "$shape" "$delivery_tag" "$checked_branch" "$checked_tag" "$tag_type"
            failures=$((failures + 1))
            return
        fi
    fi
    if [ "$shape" = default ] && [ "$checked_branch" != "$default_branch" ]; then
        printf 'FAIL\t%s\texpected default branch=%s observed=%s\n' "$shape" "$default_branch" "$checked_branch"
        failures=$((failures + 1))
        return
    fi

    if ! (
        cd "$destination" || exit 2
        unset REPRODUCE_ALLOW_DIRTY REPRODUCE_SKIP_TESTS REPRODUCE_EXPECTED_SHA
        bash tools/reproduce/reproduce.sh verify
    ) >"$log" 2>&1; then
        printf 'FAIL\t%s\tref=%s verify failed\n' "$shape" "$ref"
        sed -n '1,200p' "$log"
        failures=$((failures + 1))
        return
    fi
    if ! grep -q '^PASS[[:space:]]host-tests$' "$log" || ! grep -q '^OVERALL[[:space:]]PASS$' "$log"; then
        printf 'FAIL\t%s\tref=%s missing host-tests/OVERALL PASS\n' "$shape" "$ref"
        sed -n '1,200p' "$log"
        failures=$((failures + 1))
        return
    fi
    if [ "$shape" != default ] && grep -q '^REPORT_ONLY[[:space:]]delivery-identity' "$log"; then
        printf 'FAIL\t%s\tref=%s delivery identity was report-only\n' "$shape" "$ref"
        sed -n '1,200p' "$log"
        failures=$((failures + 1))
        return
    fi

    head=$(git -C "$destination" rev-parse HEAD)
    identity=REQUIRED
    [ "$shape" = default ] && identity=REPORT_ONLY
    printf 'PASS\t%s\tref=%s head=%s identity=%s host-tests=PASS OVERALL=PASS\n' \
        "$shape" "$ref" "$head" "$identity"
}

printf 'PREDELIVERY\trepo=%s branch=%s tag=%s default=%s\n' \
    "$repo_url" "$delivery_branch" "$delivery_tag" "$default_branch"
run_shape branch "$delivery_branch"
run_shape tag "$delivery_tag"
run_shape default "$default_branch"

if [ "$failures" -ne 0 ]; then
    printf 'OVERALL\tFAIL\tshapes_failed=%s\n' "$failures"
    exit 1
fi
printf 'OVERALL\tPASS\tshapes=3\n'
