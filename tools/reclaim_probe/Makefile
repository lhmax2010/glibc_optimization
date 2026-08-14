# Override examples:
#   make armv7l ARMV7L_ROOT=/path/to/GBS/scratch.armv7l.0
#   make armv7l ARMV7L_CC=/path/to/armv7l-tizen-linux-gnueabi-gcc
#   make armv7l ARMV7L_CC=/path/to/gcc ARMV7L_SYSROOT=/path/to/sysroot

HOST_CC ?= gcc
ARMV7L_ROOT ?= <USER_HOME>/GBS-ROOT-TIZEN-UNIFIED-LLVM-MLGO/local/BUILD-ROOTS/scratch.armv7l.0
ARMV7L_CC ?= bwrap --tmpfs / --dir /home --bind /home /home --dir /tmp --bind /tmp /tmp --ro-bind $(ARMV7L_ROOT)/usr /usr --ro-bind $(ARMV7L_ROOT)/lib /lib --proc /proc --ro-bind $(ARMV7L_ROOT)/emul /emul $(ARMV7L_ROOT)/emul/usr/bin/armv7l-tizen-linux-gnueabi-gcc -B/usr/lib/gcc/armv7l-tizen-linux-gnueabi/14.2.0/
ARMV7L_SYSROOT ?=

COMMON_CFLAGS := -std=c99 -O2 -g -Wall -Wextra -Werror
HOST_CFLAGS ?=
ARMV7L_CFLAGS ?= -O2 -g

SRC := reclaim_probe.c
HOST_BIN := reclaim_probe.host
ARMV7L_BIN := reclaim_probe.armv7l

.PHONY: all host armv7l clean

all: host

host: $(HOST_BIN)

armv7l: $(ARMV7L_BIN)

$(HOST_BIN): $(SRC)
	$(HOST_CC) $(COMMON_CFLAGS) $(HOST_CFLAGS) -o $@ $<

$(ARMV7L_BIN): $(SRC)
	$(ARMV7L_CC) $(COMMON_CFLAGS) $(ARMV7L_CFLAGS) $(if $(ARMV7L_SYSROOT),--sysroot=$(ARMV7L_SYSROOT),) -o $@ $<

clean:
	rm -f $(HOST_BIN) $(ARMV7L_BIN)
