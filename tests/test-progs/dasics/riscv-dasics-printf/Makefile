# SPDX-License-Identifier: BSD-3-Clause
CROSS_COMPILE ?= riscv64-linux-gnu-
CC := $(CROSS_COMPILE)gcc
ABI := -march=rv64gc -mabi=lp64d
LIBC := $(shell $(CC) $(ABI) -print-file-name=libc.a)
BUILD := build
FULL_MODES := full-sw full-hw full-check-sw full-check-hw

.PHONY: all roi full
all: $(BUILD)/plain.elf $(BUILD)/protected.elf
roi: $(BUILD)/roi-sw.elf $(BUILD)/roi-hw.elf
full: $(addprefix $(BUILD)/,$(addsuffix .elf,$(FULL_MODES)))

$(BUILD):
	mkdir -p $@

$(BUILD)/printf-private.o: private_libc.py $(LIBC) | $(BUILD)
	python3 -B $< "$(CROSS_COMPILE)" "$(LIBC)" "$@"

$(BUILD)/main.o: main.c | $(BUILD)
	$(CC) $(ABI) -O2 -Wall -Wextra -fno-builtin-printf -c -o $@ $<

$(BUILD)/main-roi.o: main.c | $(BUILD)
	$(CC) $(ABI) -O2 -Wall -Wextra -fno-builtin-printf -DPRINTF_ROI=1 -c -o $@ $<

$(BUILD)/roi_loop.o: roi_loop.S ../../../../include/gem5/asm/generic/m5ops.h | $(BUILD)
	$(CC) $(ABI) -I../../../../include -c -o $@ $<

$(BUILD)/gate-plain.o: protected := 0
$(BUILD)/gate-protected.o: protected := 1
$(BUILD)/gate-plain.o $(BUILD)/gate-protected.o: gate.S ../riscv-dasics-reg-protection/src/context.h | $(BUILD)
	$(CC) $(ABI) -DPROTECTED=$(protected) -c -o $@ $<

$(BUILD)/gate-roi-sw.o: software := 1
$(BUILD)/gate-roi-hw.o: software := 0
$(BUILD)/gate-roi-sw.o $(BUILD)/gate-roi-hw.o: gate.S ../riscv-dasics-reg-protection/src/context.h | $(BUILD)
	$(CC) $(ABI) -DPROTECTED=1 -DPRINTF_ROI=1 -DSOFTWARE_REGS=$(software) -c -o $@ $<

$(addprefix $(BUILD)/gate-,$(addsuffix .o,$(FULL_MODES))): gate.S full_policy.inc ../riscv-dasics-reg-protection/src/context.h | $(BUILD)
	$(CC) $(ABI) -DPROTECTED=1 -DPRINTF_ROI=1 -DPRINTF_FULL=1 \
	    -DSOFTWARE_REGS=$(if $(filter %-sw.o,$@),1,0) \
	    -DPRINTF_FULL_CHECK=$(if $(findstring -check-,$@),1,0) -c -o $@ $<

$(BUILD)/full-%.elf: $(BUILD)/gate-full-%.o $(BUILD)/main-roi.o $(BUILD)/roi_loop.o $(BUILD)/printf-private.o layout.ld
	$(CC) $(ABI) -static -no-pie -Wl,-T,layout.ld,-Map,$@.map -o $@ $(filter %.o,$^)

$(BUILD)/roi-%.elf: $(BUILD)/gate-roi-%.o $(BUILD)/main-roi.o $(BUILD)/roi_loop.o $(BUILD)/printf-private.o layout.ld
	$(CC) $(ABI) -static -no-pie -Wl,-T,layout.ld,-Map,$@.map -o $@ $(filter %.o,$^)

$(BUILD)/%.elf: $(BUILD)/gate-%.o $(BUILD)/main.o $(BUILD)/printf-private.o layout.ld
	$(CC) $(ABI) -static -no-pie -Wl,-T,layout.ld,-Map,$@.map -o $@ $(filter %.o,$^)
