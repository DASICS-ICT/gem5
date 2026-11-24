# SPDX-License-Identifier: BSD-3-Clause

CROSS_COMPILE ?= riscv64-linux-gnu-
OUT ?= build
RUN_DIR ?= $(OUT)/runs
GEM5_REPO_DIR ?= $(abspath ../../../..)
GEM5_BINARY ?= $(GEM5_REPO_DIR)/build/RISCV_DASICS/gem5.opt
GEM5_CONFIG ?= $(GEM5_REPO_DIR)/configs/spec/riscv_se_dasics_v5_full.py
ORDINARY_CONFIG ?= $(GEM5_REPO_DIR)/configs/spec/riscv_se_v5_full.py
CHECKS := trusted untrusted missing-context overlap ordinary

.PHONY: all
all: $(OUT)/se-init.elf $(OUT)/missing-context.elf $(OUT)/overlap.elf

$(OUT)/se-init.elf: se-init.S Makefile
	mkdir -p "$(OUT)"
	$(CROSS_COMPILE)gcc -march=rv64gc -mabi=lp64d -static -nostdlib \
		-no-pie -Wl,--build-id=none,--no-relax,-e,_start -o "$@" "$<"

$(OUT)/missing-context.elf: $(OUT)/se-init.elf
	$(CROSS_COMPILE)objcopy --strip-symbol=__dasics_context_base "$<" "$@"

$(OUT)/overlap.elf: $(OUT)/se-init.elf
	$(CROSS_COMPILE)objcopy --strip-symbol=__dasics_untrusted_start \
		--add-symbol=__dasics_untrusted_start=.text:0,global "$<" "$@"

.PHONY: check $(addprefix check-,$(CHECKS))
check: $(addprefix check-,$(CHECKS))

check-ordinary: private override GEM5_CONFIG := $(ORDINARY_CONFIG)
$(addprefix check-,$(CHECKS)): check-%: all
	@ulimit -c 0; python3 check.py "$*" --build "$(OUT)" --outdir "$(RUN_DIR)" \
		--gem5 "$(GEM5_BINARY)" --config "$(GEM5_CONFIG)" --nm "$(CROSS_COMPILE)nm"
