"""PM single-operation transport: 200 bytes is a mandate, not a probed limit."""
import re
import shlex

MAX_BODY_BYTES = 200
SUFFIX = ';r=$?;echo;echo RC=$r;test $r = 0 && echo DONE || echo FAIL'


def check_body(body):
    size = len(body.encode('utf-8'))
    if size > MAX_BODY_BYTES:
        raise ValueError('LOCAL_STOP request body %d > 200 bytes; NOT SENT' % size)
    if '\0' in body:
        raise ValueError('NUL request rejected locally')
    return size


def request(argv):
    # One argv -> one operation. No shell programs, loops, pipelines, or eval.
    if not argv or argv[0] not in {'id', 'uname', 'cat', 'rpm', 'stat', 'ps', 'df',
                                  'ls', 'dmesg', 'date', 'uptime', 'sha256sum', 'base64', 'readlink', 'rm', 'rmdir'}:
        raise ValueError('single-operation executable not allowed')
    if any(not isinstance(x, str) or any(c in x for c in '\0\r\n') for x in argv):
        raise ValueError('invalid single-operation argument')
    body = 'LC_ALL=C ' + shlex.join(argv) + SUFFIX
    check_body(body)  # includes all RC/DONE/FAIL framing, not just the operation
    return body


def parse(text):
    lines = text.replace('\r', '').splitlines()
    if len(lines) < 2 or not re.fullmatch(r'RC=(0|[1-9][0-9]{0,2})', lines[-2]):
        raise ValueError('missing remote RC/DONE proof')
    rc = int(lines[-2][3:])
    if rc > 255 or lines[-1] != ('DONE' if rc == 0 else 'FAIL'):
        raise ValueError('inconsistent remote RC/DONE proof')
    if sum(bool(re.fullmatch(r'RC=\d+', line)) for line in lines) != 1:
        raise ValueError('duplicate remote RC proof')
    return rc, '\n'.join(lines[:-2]).strip()


def permission(rc, text):
    return rc != 0 and bool(text) and all(
        line.endswith((': Permission denied', ': Operation not permitted'))
        for line in text.splitlines())


def absent(rc, text):
    return rc == 1 and len(text.splitlines()) == 1 and text.endswith(': No such file or directory')


def absent_listing(rc, text):
    return rc == 2 and len(text.splitlines()) == 1 and text.endswith(': No such file or directory')
