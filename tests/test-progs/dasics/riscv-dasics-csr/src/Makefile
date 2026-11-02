# Copyright (c) 2026 Jaeuk Lee
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

CROSS_COMPILE ?= riscv64-linux-gnu-
CC = $(CROSS_COMPILE)gcc
CFLAGS = -march=rv64imac_zicsr -mabi=lp64 -nostdlib -nostartfiles -static
LDFLAGS = -no-pie -Wl,--build-id=none -Wl,-Ttext=0x80000000 -Wl,-e,_start
OUT = ../build/riscv-dasics-csr.elf

.PHONY: all run clean

all: $(OUT)

$(OUT): riscv-dasics-csr.S Makefile
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $<

# The root dispatcher supplies GEM5_REPO_DIR for the run target.
run: $(OUT)
	@test -n "$(GEM5_REPO_DIR)" || { \
		printf 'Use the root dasics-test target to run this test.\n' >&2; \
		exit 2; \
	}
	@test -x "$(GEM5_REPO_DIR)/build/RISCV/gem5.opt" || { \
		printf 'Missing gem5 binary; run make riscv first.\n' >&2; exit 2; \
	}
	@cd "$(GEM5_REPO_DIR)" && \
		timeout 60s build/RISCV/gem5.opt \
		--outdir="$(abspath $(dir $(OUT)))/m5out" \
		tests/gem5/riscv-unittests/riscv_baremetal/configs/riscv_baremetal.py \
		"$(abspath $(OUT))"; \
		dasics_rc=$$?; \
		printf 'Exit code: %s\n' "$$dasics_rc"; \
		exit "$$dasics_rc"

clean:
	rm -f $(OUT)
