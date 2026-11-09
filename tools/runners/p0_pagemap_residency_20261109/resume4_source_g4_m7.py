"""Sourced by GDB, not a standalone Python CLI. No register convenience variables."""
import os
import pathlib
import re

import gdb


def verify_target():
    pid = os.environ["GLIBC_MEMOPT_TARGET_PID"]
    tick = os.environ["GLIBC_MEMOPT_TARGET_TICK"]
    if not re.fullmatch(r"[1-9][0-9]*", pid) or not re.fullmatch(r"[1-9][0-9]*", tick):
        raise ValueError("FAIL_M7_PID")
    proc = pathlib.Path("/proc") / pid
    if (gdb.selected_inferior().pid != int(pid) or
            (proc / "comm").read_text().strip() != "enlightenment" or
            (proc / "stat").read_text().rsplit(")", 1)[1].split()[19] != tick):
        raise ValueError("FAIL_M7_TARGET_CHANGED")


def capture():
    stream = 0
    failed = False
    try:
        path = os.environ["GLIBC_MEMOPT_M7_PATH"]
        if not re.fullmatch(r"/opt/usr/glibc_memopt/system_level_before_after_20260908/G4_trim_r[123]/malloc_info_pre\.xml", path):
            raise ValueError("FAIL_M7_PATH")
        output = pathlib.Path(path)
        if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
            raise ValueError("FAIL_M7_PATH_EXISTS_OR_SYMLINK")
        verify_target()
        # Store the return value in Python: $fp is an ARM register, and assigning
        # it can fail AFTER fopen has already allocated a FILE/descriptor.
        stream = int(gdb.parse_and_eval('(void*)fopen("%s","w")' % path))
        if stream == 0:
            raise ValueError("FAIL_NULL_FILE")
        result = gdb.parse_and_eval("(int)malloc_info(0,(void*)%d)" % int(stream))
        if int(result) != 0:
            raise ValueError("FAIL_M7_RETURN")
    except Exception as error:
        failed = True
        print("FAIL_M7_CAPTURE " + str(error), flush=True)
    finally:
        # An inferior-call error may leave target state uncertain; never retry
        # malloc_info. Close every known non-NULL FILE exactly once, then detach.
        if stream != 0:
            try:
                if int(gdb.parse_and_eval("(int)fclose((void*)%d)" % int(stream))) != 0:
                    raise ValueError("FAIL_M7_FCLOSE_RETURN")
                print("DONE_M7_FCLOSE RC=0", flush=True)
            except Exception as error:
                failed = True
                print("FAIL_M7_FCLOSE " + str(error), flush=True)
        try:
            gdb.execute("detach")
        except Exception as error:
            failed = True
            print("FAIL_M7_DETACH " + str(error), flush=True)
    print("FAIL_M7" if failed else "DONE_M7 RC=0", flush=True)
    gdb.execute("quit 1" if failed else "quit 0")


def trim():
    failed = False
    try:
        verify_target()  # after attach, before the actual trim, not only M7
        gdb.execute("call (int)malloc_trim(0)")
    except Exception as error:
        failed = True
        print("FAIL_TRIM " + str(error), flush=True)
    finally:
        try:
            gdb.execute("detach")
        except Exception as error:
            failed = True
            print("FAIL_TRIM_DETACH " + str(error), flush=True)
    print("FAIL_TRIM" if failed else "DONE_TRIM RC=0", flush=True)
    gdb.execute("quit 1" if failed else "quit 0")


if os.environ.get("GLIBC_MEMOPT_ACTION", "m7") == "m7":
    capture()
elif os.environ["GLIBC_MEMOPT_ACTION"] == "trim":
    trim()
else:
    print("FAIL_INJECTION_ACTION", flush=True)
    gdb.execute("detach")
    gdb.execute("quit 1")
