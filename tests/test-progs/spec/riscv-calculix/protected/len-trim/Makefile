# SPDX-License-Identifier: BSD-3-Clause

SELF := $(abspath $(lastword $(MAKEFILE_LIST)))
GATE_DIR := $(dir $(SELF))
ORDINARY_CASE ?= $(GATE_DIR)../..
APP_DIR := $(abspath $(ORDINARY_CASE))
OUT ?= $(GATE_DIR)../../build/protected-len-trim
OUT_DIR := $(abspath $(OUT))

.DEFAULT_GOAL := all
.DELETE_ON_ERROR:
.PHONY: all

ifneq ($(CURDIR),$(APP_DIR))
# build.mk discovers its application sources relative to the ordinary case.
all:
	+$(MAKE) --no-print-directory -C "$(APP_DIR)" -f "$(SELF)" all \
	    ORDINARY_CASE="$(APP_DIR)" OUT="$(OUT_DIR)"
else
include $(APP_DIR)/build.mk

CROSS_COMPILE ?= riscv64-linux-gnu-
CC := $(CROSS_COMPILE)gcc
FC := $(CROSS_COMPILE)gfortran
LD := $(CROSS_COMPILE)ld
AR := $(CROSS_COMPILE)ar
OBJCOPY := $(CROSS_COMPILE)objcopy
ABI := -march=rv64gc -mabi=lp64d
LIBGFORTRAN := $(shell $(FC) $(ABI) -print-file-name=libgfortran.a)
PRIVATE := $(OUT_DIR)/private
OBJECT_DIR := $(APP_DIR)/build/objects
SOURCES := $(patsubst ./%,%,$(sort $(SRCS)))
OBJECTS := $(addprefix $(OBJECT_DIR)/,$(addsuffix .o,$(basename $(SOURCES))))
# Preserve the ordinary link order, including the position of getnewline.o.
ORDINARY_CALLER := $(OBJECT_DIR)/src/getnewline.o
APP_OBJECTS := $(patsubst $(ORDINARY_CALLER),$(PRIVATE)/getnewline.o,$(OBJECTS))

all: $(OUT_DIR)/calculix-sw.elf $(OUT_DIR)/calculix-hw.elf

$(PRIVATE):
	mkdir -p "$@"

$(PRIVATE)/getnewline.o: $(ORDINARY_CALLER) $(GATE_DIR)redirect.py $(SELF) | $(PRIVATE)
	@set -eu; trap 'rm -f "$@.tmp"' EXIT; \
	    $(LD) -r -u trim_gate "$<" -o "$@.tmp"; \
	    python3 -B "$(GATE_DIR)redirect.py" "$@.tmp" "$@"

$(PRIVATE)/body.o: $(LIBGFORTRAN) $(SELF) | $(PRIVATE)
	@set -eu; trap 'rm -f "$@.raw"' EXIT; \
	    $(AR) p "$<" string_intrinsics.o > "$@.raw"; \
	    $(OBJCOPY) --only-section=.text._gfortran_string_len_trim \
	      --only-section=.rodata --only-section=.note.GNU-stack \
	      --only-section=.riscv.attributes \
	      --rename-section=.text._gfortran_string_len_trim=.dasics.trim.body \
	      --rename-section=.rodata=.dasics.trim.ro \
	      --redefine-sym=_gfortran_string_len_trim=b_len_trim \
	      --redefine-sym=.LC0=b_trim_space --globalize-symbol=b_trim_space \
	      "$@.raw" "$@"

$(PRIVATE)/gate-sw.o: software := 1
$(PRIVATE)/gate-hw.o: software := 0
$(PRIVATE)/gate-sw.o $(PRIVATE)/gate-hw.o: $(GATE_DIR)gate.S \
    $(GATE_DIR)../../../../dasics/riscv-dasics-printf/full_policy.inc \
    $(GATE_DIR)../../../../dasics/riscv-dasics-reg-protection/src/context.h \
    $(SELF) | $(PRIVATE)
	$(CC) $(ABI) -DSOFTWARE_REGS=$(software) -c "$<" -o "$@"

$(OUT_DIR)/calculix-%.elf: $(PRIVATE)/gate-%.o $(APP_OBJECTS) \
    $(PRIVATE)/body.o $(GATE_DIR)layout.ld $(APP_DIR)/build.mk $(SELF)
	@$(FC) $(ABI) -O2 -static -Wl,-T,"$(GATE_DIR)layout.ld",-Map,"$@.map" \
	    -o "$@" $(APP_OBJECTS) "$(PRIVATE)/body.o" "$<" $(LIBS)
endif
