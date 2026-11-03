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

# The root dispatcher selects the model and supplies shared paths.
run: $(OUT)
	@test -n "$(GEM5_REPO_DIR)" && test -n "$(GEM5_BINARY)" && \
		test -n "$(GEM5_CONFIG)" && test -n "$(GEM5_OUTDIR)" && \
		test -n "$(CPU)" || { \
		printf 'Use the root dasics-test target to run this test.\n' >&2; \
		exit 2; \
	}
	@test -x "$(GEM5_BINARY)" || { \
		printf 'Missing gem5 binary; run make riscv-dasics first.\n' \
			>&2; exit 2; \
	}
	@test -f "$(GEM5_CONFIG)" || { \
		printf '\033[1;31m[FAIL] Missing CPU config: %s\033[0m\n' \
			"$(GEM5_CONFIG)" >&2; exit 2; \
	}
	@mkdir -p "$(GEM5_OUTDIR)" || exit; \
		rm -f "$(GEM5_OUTDIR)/stats.txt" \
			"$(GEM5_OUTDIR)/run-result.txt" || exit; \
		cd "$(GEM5_REPO_DIR)" || exit; \
		timeout 60s "$(GEM5_BINARY)" \
		--outdir="$(GEM5_OUTDIR)" \
		"$(GEM5_CONFIG)" \
		"$(abspath $(OUT))"; \
		dasics_rc=$$?; \
		cycles=N/A; \
		if [ "$$dasics_rc" -eq 0 ] && \
			[ -f "$(GEM5_OUTDIR)/stats.txt" ]; then \
			cycles=$$(awk '$$1 == "system.cpu.numCycles" {value=$$2} \
				END {print (value ~ /^[0-9]+$$/ ? value : "N/A")}' \
				"$(GEM5_OUTDIR)/stats.txt") || cycles=N/A; \
		fi; \
		printf '%s %s\n' "$$dasics_rc" "$$cycles" \
			> "$(GEM5_OUTDIR)/run-result.txt" || exit; \
		printf 'Exit code: %s\n' "$$dasics_rc"; \
		printf 'CPU cycles: %s\n' "$$cycles"; \
		if [ "$$dasics_rc" -eq 0 ]; then \
			printf '\033[1;32m[OK] %s\033[0m\n' "$(CPU)"; \
		elif [ "$$dasics_rc" -eq 124 ]; then \
			printf '\033[1;31m[TIMEOUT] %s\033[0m\n' "$(CPU)" >&2; \
		else \
			printf '\033[1;31m[FAIL] %s\033[0m\n' "$(CPU)" >&2; \
		fi; \
		exit "$$dasics_rc"

clean:
	rm -f $(OUT)
