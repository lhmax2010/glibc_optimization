# Override examples:
#   make armv7l ARMV7L_ROOT=/path/to/GBS/scratch.armv7l.0
#   make armv7l ARMV7L_CC=/path/to/armv7l-tizen-linux-gnueabi-gcc
#   make armv7l ARMV7L_CC=/path/to/gcc ARMV7L_SYSROOT=/path/to/sysroot

HOST_CC ?= gcc
ARMV7L_ROOT ?= <USER_HOME>/GBS-ROOT-TIZEN-UNIFIED-LLVM-MLGO/local/BUILD-ROOTS/scratch.armv7l.0
ARMV7L_CC ?= bwrap --tmpfs / --dir /home --bind /home /home --dir /tmp --bind /tmp /tmp --ro-bind $(ARMV7L_ROOT)/usr /usr --ro-bind $(ARMV7L_ROOT)/lib /lib --proc /proc --ro-bind $(ARMV7L_ROOT)/emul /emul $(ARMV7L_ROOT)/emul/usr/bin/armv7l-tizen-linux-gnueabi-gcc -B/usr/lib/gcc/armv7l-tizen-linux-gnueabi/14.2.0/
ARMV7L_SYSROOT ?=

COMMON_CFLAGS := -std=c99 -O2 -g -Wall -Wextra -Werror -D_GNU_SOURCE
HOST_CFLAGS ?=
ASAN_CFLAGS ?= -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer
ARMV7L_CFLAGS ?= -O2 -g
ARMV7L_BUILD_DIR ?= .build/armv7l
ARMV7L_REPRO_CFLAGS := -fdebug-prefix-map=$(CURDIR)=.
LDLIBS := -pthread

SRC := alloc_bench.c
HOST_BIN := alloc_bench.host
ASAN_BIN := alloc_bench.host-asan
ARMV7L_BIN := alloc_bench.armv7l
ARMV7L_BUILD_BIN := $(ARMV7L_BUILD_DIR)/alloc_bench.armv7l

.PHONY: all host host-asan armv7l clean

all: host

host: $(HOST_BIN)

host-asan: $(ASAN_BIN)

armv7l: $(ARMV7L_BIN)

$(HOST_BIN): $(SRC)
	$(HOST_CC) $(COMMON_CFLAGS) $(HOST_CFLAGS) -o $@ $< $(LDLIBS)

$(ASAN_BIN): $(SRC)
	$(HOST_CC) -std=c99 -Wall -Wextra -Werror -D_GNU_SOURCE $(ASAN_CFLAGS) -o $@ $< $(LDLIBS)

$(ARMV7L_BIN): $(ARMV7L_BUILD_BIN)
	cp $< $@

$(ARMV7L_BUILD_BIN): $(SRC)
	mkdir -p $(ARMV7L_BUILD_DIR)
	$(ARMV7L_CC) $(COMMON_CFLAGS) $(ARMV7L_CFLAGS) $(ARMV7L_REPRO_CFLAGS) $(if $(ARMV7L_SYSROOT),--sysroot=$(ARMV7L_SYSROOT),) -o $@ $< $(LDLIBS)

clean:
	rm -f $(HOST_BIN) $(ASAN_BIN) $(ARMV7L_BIN) $(ARMV7L_BUILD_BIN)
