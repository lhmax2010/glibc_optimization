#!/bin/sh

kernel=$(uname -r)
case "$kernel" in
    *rpi4*) ;;
    *) echo "ABORT: not RPI4, kernel=$kernel" >&2; exit 97 ;;
esac
if grep -qi '<PRODUCT_IMAGE>' /etc/os-release 2>/dev/null; then
    echo "ABORT: TV product image detected" >&2
    exit 98
fi

sleep 300 &
p=$!
echo "PID=$p"
LD_LIBRARY_PATH=/root/l6tfprobe/lldb/lib \
    /root/l6tfprobe/lldb/bin/lldb -b \
    -o "process attach --pid $p" \
    -o 'thread list' \
    -o 'bt all' \
    -o 'thread select 1' \
    -o 'bt' \
    -o 'expr -t 5000000 -- void *$fp = (void *)fopen("/tmp/mi_sleep_test.xml", "w")' \
    -o 'expr -t 5000000 -- (int)malloc_info(0, $fp)' \
    -o 'expr -t 5000000 -- (int)fflush($fp)' \
    -o 'expr -t 5000000 -- (int)fclose($fp)' \
    -o 'detach'
echo "LLDB_RC=$?"
ls -l /tmp/mi_sleep_test.xml
head -12 /tmp/mi_sleep_test.xml
kill "$p" 2>/dev/null
wait "$p" 2>/dev/null
rm -f /tmp/mi_sleep_test.xml
