# SPDX-License-Identifier: BSD-3-Clause
CROSS_COMPILE ?= riscv64-linux-gnu-
CC := $(CROSS_COMPILE)gcc
AR := $(CROSS_COMPILE)ar
LD := $(CROSS_COMPILE)ld
OBJCOPY := $(CROSS_COMPILE)objcopy
ABI := -march=rv64gc -mabi=lp64d
LIBC := $(shell $(CC) $(ABI) -print-file-name=libc.a)
BUILD := build

.DELETE_ON_ERROR:
.PHONY: all
all: $(BUILD)/sw.elf $(BUILD)/hw.elf

$(BUILD):
	mkdir -p $@

# Keep the real libc implementation and its word-copy helpers in B. Renaming
# the public symbols leaves trusted libc startup on its own copy of memcpy.
$(BUILD)/private-memcpy.o: $(LIBC) Makefile | $(BUILD)
	cd $(BUILD) && $(AR) x "$(abspath $(LIBC))" memcpy.o wordcopy.o
	$(LD) -r -o $(BUILD)/libc-members.o $(BUILD)/memcpy.o $(BUILD)/wordcopy.o
	$(OBJCOPY) --rename-section .text=.dasics.memcpy.text \
	    --rename-section .rodata=.dasics.memcpy.ro \
	    --redefine-sym memcpy=b_memcpy \
	    --redefine-sym _wordcopy_fwd_aligned=b_wordcopy_fwd_aligned \
	    --redefine-sym _wordcopy_fwd_dest_aligned=b_wordcopy_fwd_dest_aligned \
	    --redefine-sym _wordcopy_bwd_aligned=b_wordcopy_bwd_aligned \
	    --redefine-sym _wordcopy_bwd_dest_aligned=b_wordcopy_bwd_dest_aligned \
	    $(BUILD)/libc-members.o $@

$(BUILD)/main.o: main.c | $(BUILD)
	$(CC) $(ABI) -O2 -Wall -Wextra -fno-builtin-memcpy -c -o $@ $<

$(BUILD)/roi_loop.o: roi_loop.S ../../../../include/gem5/asm/generic/m5ops.h | $(BUILD)
	$(CC) $(ABI) -I../../../../include -c -o $@ $<

$(BUILD)/gate-sw.o: software := 1
$(BUILD)/gate-hw.o: software := 0
$(BUILD)/gate-sw.o $(BUILD)/gate-hw.o: gate.S ../riscv-dasics-printf/full_policy.inc ../riscv-dasics-reg-protection/src/context.h | $(BUILD)
	$(CC) $(ABI) -DSOFTWARE_REGS=$(software) -c -o $@ $<

$(BUILD)/%.elf: $(BUILD)/gate-%.o $(BUILD)/main.o $(BUILD)/roi_loop.o $(BUILD)/private-memcpy.o layout.ld
	$(CC) $(ABI) -static -no-pie -Wl,-T,layout.ld,-Map,$@.map -o $@ $(filter %.o,$^)
