"""Conservative SDB shell service byte budget, including remote RC framing."""
import shlex


# Local safety limit, NOT a measured maximum of every SDB implementation.
# Leaves headroom below a 4 KiB service request; never probe by sending oversize.
MAX_SERVICE_BYTES = 3500


def check_request(body):
    size = len(("shell:" + body).encode("utf-8"))
    if size > MAX_SERVICE_BYTES:
        raise ValueError("SDB request rejected locally: %d bytes > %d; not sent" %
                         (size, MAX_SERVICE_BYTES))
    return size


def framed(label, command):
    if not label or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-" for c in label):
        raise ValueError("invalid remote marker label")
    body = "( " + command + " ); rc=$?; printf '\\nWRAPPER_RC_" + label + "=%s\\n' \"$rc\"; "
    return body + 'if [ "$rc" -eq 0 ]; then echo DONE_REMOTE_' + label + "; else echo FAIL_REMOTE_" + label + "; fi"


def residue_command(paths):
    if not paths:
        raise ValueError("empty residue batch")
    for path in paths:
        if not path.startswith("/") or path == "/" or any(c in path for c in "\n\r\t\0"):
            raise ValueError("invalid package path")
        if ".." in path.split("/"):
            raise ValueError("parent traversal in package path")
    selected = " ".join(shlex.quote(p) for p in paths)
    return ('for p in ' + selected + '; do '
            'info=$(LC_ALL=C stat -c "%F" "$p" 2>&1); code=$?; '
            'if [ "$code" -eq 0 ]; then printf "%s\\t%s\\n" "$p" "$info" || exit 1; '
            'elif [ "$code" -eq 1 ]; then case "$info" in '
            '*": No such file or directory") :;; '
            '*) printf "STAT_ERROR %s\\n%s\\n" "$p" "$info"; exit 1;; esac; '
            'else printf "STAT_ERROR_RC=%s %s\\n%s\\n" "$code" "$p" "$info"; exit 1; fi; done')


def residue_batches(paths):
    """Preflight ALL batches before callers send any of them; preserve order."""
    batches, current, offset = [], [], 0
    for path in paths:
        candidate = current + [path]
        label = "PACKAGE_RESIDUE_%04d" % offset
        command = residue_command(candidate)
        if len(("shell:" + framed(label, command)).encode("utf-8")) > MAX_SERVICE_BYTES:
            if not current:
                check_request(framed(label, command))
            batches.append((label, residue_command(current)))
            offset += len(current)
            current = [path]
            check_request(framed("PACKAGE_RESIDUE_%04d" % offset, residue_command(current)))
        else:
            current = candidate
    if current:
        batches.append(("PACKAGE_RESIDUE_%04d" % offset, residue_command(current)))
    for label, command in batches:
        check_request(framed(label, command))
    return batches
