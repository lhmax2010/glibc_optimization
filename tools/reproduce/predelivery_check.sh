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

Each clone shape is checked under four controlled optional-tool PATH profiles:
  present-gbs+present-rpm, absent-gbs+present-rpm,
  present-gbs+absent-rpm, minimal-git-python
The 3 clone shapes x 4 optional-tool PATH profiles = 12 required verifies.
Presence profiles use fail-if-invoked stubs, proving default verify only detects
optional tools where specified and never executes GBS/RPM payload commands.

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

original_path=$PATH

make_path_profile()
{
    profile=$1
    include_gbs=$2
    include_rpm=$3
    destination="$tmp/path-$profile"
    mkdir "$destination" || return 1
    python3 - "$destination" "$original_path" "$include_gbs" "$include_rpm" <<'PY'
import os
import stat
import sys
from pathlib import Path

destination = Path(sys.argv[1])
source_path = sys.argv[2]
include_gbs = sys.argv[3] == "yes"
include_rpm = sys.argv[4] == "yes"


def optional(name: str) -> bool:
    return name == "gbs" or name == "cpio" or name.startswith("rpm")


for directory_name in source_path.split(os.pathsep):
    directory = Path(directory_name or ".")
    if not directory.is_dir():
        continue
    try:
        entries = list(directory.iterdir())
    except OSError:
        continue
    for source in entries:
        name = source.name
        target = destination / name
        if target.exists() or target.is_symlink() or optional(name):
            continue
        try:
            mode = source.stat().st_mode
        except OSError:
            continue
        if not stat.S_ISREG(mode) or not os.access(source, os.X_OK):
            continue
        try:
            target.symlink_to(source.resolve(strict=True))
        except OSError:
            continue


def executable(name: str, body: str) -> None:
    target = destination / name
    target.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    target.chmod(0o755)


poison = (
    'printf "%s\\n" "$0" >> "${PREDELIVERY_OPTIONAL_TOOL_MARKER:?}"\n'
    "exit 97\n"
)
if include_gbs:
    executable("gbs", poison)
if include_rpm:
    for command in ("rpm", "rpm2cpio", "cpio"):
        executable(command, poison)
    # static_check deliberately exercises rpmspec when discoverable. This
    # portable parser fixture only expands the already hard-gated source text.
    executable(
        "rpmspec",
        '[ "$#" -eq 2 ] && [ "$1" = "-P" ] || exit 97\ncat "$2"\n',
    )
PY
    printf '%s\n' "$destination"
}

profile_full=$(make_path_profile present-gbs+present-rpm yes yes) || exit 2
profile_no_gbs=$(make_path_profile absent-gbs+present-rpm no yes) || exit 2
profile_no_rpm=$(make_path_profile present-gbs+absent-rpm yes no) || exit 2
profile_minimal=$(make_path_profile minimal-git-python no no) || exit 2

failures=0
check_profile()
{
    profile=$1
    profile_path=$2
    expect_gbs=$3
    expect_rpm=$4
    for required in git python3 bash; do
        if ! (PATH=$profile_path; export PATH; command -v "$required" >/dev/null 2>&1); then
            printf 'FAIL\tprofile=%s\tmissing required command=%s\n' "$profile" "$required"
            return 1
        fi
    done
    if (PATH=$profile_path; export PATH; command -v gbs >/dev/null 2>&1); then
        observed_gbs=yes
    else
        observed_gbs=no
    fi
    if (PATH=$profile_path; export PATH; command -v rpm >/dev/null 2>&1 && command -v rpm2cpio >/dev/null 2>&1 && command -v cpio >/dev/null 2>&1); then
        observed_rpm=yes
    else
        observed_rpm=no
    fi
    if [ "$observed_gbs" != "$expect_gbs" ] || [ "$observed_rpm" != "$expect_rpm" ]; then
        printf 'FAIL\tprofile=%s\texpected_gbs=%s observed_gbs=%s expected_rpm=%s observed_rpm=%s\n' \
            "$profile" "$expect_gbs" "$observed_gbs" "$expect_rpm" "$observed_rpm"
        return 1
    fi
}

run_shape()
{
    profile=$1
    verify_path=$2
    shape=$3
    ref=$4
    destination="$tmp/$profile-$shape"
    log="$tmp/$profile-$shape.log"
    optional_tool_marker="$tmp/$profile-$shape.optional-tool-invoked"

    if [ "$shape" = default ]; then
        if ! git clone --quiet "$repo_url" "$destination" >"$log" 2>&1; then
            printf 'FAIL\tprofile=%s shape=%s\tclone failed\n' "$profile" "$shape"
            sed -n '1,120p' "$log"
            failures=$((failures + 1))
            return
        fi
    else
        if ! git clone --quiet --branch "$ref" "$repo_url" "$destination" >"$log" 2>&1; then
            printf 'FAIL\tprofile=%s shape=%s\tref=%s clone failed\n' "$profile" "$shape" "$ref"
            sed -n '1,120p' "$log"
            failures=$((failures + 1))
            return
        fi
    fi

    checked_branch=$(git -C "$destination" branch --show-current 2>/dev/null)
    if [ "$shape" = branch ] && [ "$checked_branch" != "$delivery_branch" ]; then
        printf 'FAIL\tprofile=%s shape=%s\texpected branch=%s observed=%s\n' "$profile" "$shape" "$delivery_branch" "$checked_branch"
        failures=$((failures + 1))
        return
    fi
    if [ "$shape" = tag ]; then
        checked_tag=$(git -C "$destination" describe --tags --exact-match HEAD 2>/dev/null || true)
        tag_type=$(git -C "$destination" cat-file -t "refs/tags/$delivery_tag" 2>/dev/null || true)
        if [ -n "$checked_branch" ] || [ "$checked_tag" != "$delivery_tag" ] || [ "$tag_type" != tag ]; then
            printf 'FAIL\tprofile=%s shape=%s\texpected detached annotated tag=%s branch=%s tag=%s type=%s\n' \
                "$profile" "$shape" "$delivery_tag" "$checked_branch" "$checked_tag" "$tag_type"
            failures=$((failures + 1))
            return
        fi
    fi
    if [ "$shape" = default ] && [ "$checked_branch" != "$default_branch" ]; then
        printf 'FAIL\tprofile=%s shape=%s\texpected default branch=%s observed=%s\n' "$profile" "$shape" "$default_branch" "$checked_branch"
        failures=$((failures + 1))
        return
    fi

    if ! (
        cd "$destination" || exit 2
        PATH=$verify_path
        export PATH
        PREDELIVERY_OPTIONAL_TOOL_MARKER=$optional_tool_marker
        export PREDELIVERY_OPTIONAL_TOOL_MARKER
        unset REPRODUCE_ALLOW_DIRTY REPRODUCE_SKIP_TESTS REPRODUCE_EXPECTED_SHA
        unset DEMO_TOOLCHAIN_ROOT DEMO_GST_SYSROOT
        bash tools/reproduce/reproduce.sh verify
    ) >"$log" 2>&1; then
        printf 'FAIL\tprofile=%s shape=%s\tref=%s verify failed\n' "$profile" "$shape" "$ref"
        sed -n '1,200p' "$log"
        failures=$((failures + 1))
        return
    fi
    if [ -e "$optional_tool_marker" ]; then
        printf 'FAIL\tprofile=%s shape=%s\tdefault verify invoked optional payload command\n' "$profile" "$shape"
        sed -n '1,40p' "$optional_tool_marker"
        failures=$((failures + 1))
        return
    fi
    if ! grep -q '^PASS[[:space:]]host-tests$' "$log" || ! grep -q '^OVERALL[[:space:]]PASS$' "$log"; then
        printf 'FAIL\tprofile=%s shape=%s\tref=%s missing host-tests/OVERALL PASS\n' "$profile" "$shape" "$ref"
        sed -n '1,200p' "$log"
        failures=$((failures + 1))
        return
    fi
    if [ "$shape" != default ] && grep -q '^REPORT_ONLY[[:space:]]delivery-identity' "$log"; then
        printf 'FAIL\tprofile=%s shape=%s\tref=%s delivery identity was report-only\n' "$profile" "$shape" "$ref"
        sed -n '1,200p' "$log"
        failures=$((failures + 1))
        return
    fi

    head=$(git -C "$destination" rev-parse HEAD)
    identity=REQUIRED
    [ "$shape" = default ] && identity=REPORT_ONLY
    printf 'PASS\tprofile=%s shape=%s\tref=%s head=%s identity=%s host-tests=PASS OVERALL=PASS\n' \
        "$profile" "$shape" "$ref" "$head" "$identity"
}

printf 'PREDELIVERY\trepo=%s branch=%s tag=%s default=%s\n' \
    "$repo_url" "$delivery_branch" "$delivery_tag" "$default_branch"
for profile_record in \
    "present-gbs+present-rpm|$profile_full|yes|yes" \
    "absent-gbs+present-rpm|$profile_no_gbs|no|yes" \
    "present-gbs+absent-rpm|$profile_no_rpm|yes|no" \
    "minimal-git-python|$profile_minimal|no|no"
do
    old_ifs=$IFS
    IFS='|'
    set -- $profile_record
    IFS=$old_ifs
    profile=$1
    profile_path=$2
    expect_gbs=$3
    expect_rpm=$4
    if ! check_profile "$profile" "$profile_path" "$expect_gbs" "$expect_rpm"; then
        failures=$((failures + 1))
        continue
    fi
    run_shape "$profile" "$profile_path" branch "$delivery_branch"
    run_shape "$profile" "$profile_path" tag "$delivery_tag"
    run_shape "$profile" "$profile_path" default "$default_branch"
done

if [ "$failures" -ne 0 ]; then
    printf 'OVERALL\tFAIL\tchecks_failed=%s\n' "$failures"
    exit 1
fi
printf 'OVERALL\tPASS\tchecks=12 clone_shapes=3 path_profiles=4\n'
