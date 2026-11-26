# SPDX-License-Identifier: BSD-3-Clause

SELF := $(abspath $(lastword $(MAKEFILE_LIST)))
GATE_DIR := $(dir $(SELF))
ORDINARY_CASE ?= $(GATE_DIR)..
APP_DIR := $(abspath $(ORDINARY_CASE))
OUT ?= $(GATE_DIR)../build/protected-pow
OUT_DIR := $(abspath $(OUT))

CROSS_COMPILE ?= riscv64-linux-gnu-
CC := $(CROSS_COMPILE)gcc
FC := $(CROSS_COMPILE)gfortran
ABI := -march=rv64gc -mabi=lp64d
LIBM := $(shell $(CC) $(ABI) -print-file-name=libm.a)
PRIVATE := $(OUT_DIR)/private
OBJECT_DIR := $(APP_DIR)/build/objects/src

# Preserve the ordinary Fortran link order when substituting the three callers.
NAMES := $(basename $(notdir $(sort $(wildcard $(APP_DIR)/src/*.f))))
CALLERS := flux_lam jacobian_lam shell_lam
APP_OBJECTS := $(foreach name,$(NAMES),$(if $(filter $(name),$(CALLERS)),$(PRIVATE),$(OBJECT_DIR))/$(name).o)

.DEFAULT_GOAL := all
.DELETE_ON_ERROR:
.PHONY: all

all: $(OUT_DIR)/bwaves-sw.elf $(OUT_DIR)/bwaves-hw.elf

$(PRIVATE):
	mkdir -p "$@"

$(addprefix $(PRIVATE)/,$(addsuffix .o,$(CALLERS))): $(PRIVATE)/%.o: $(OBJECT_DIR)/%.o $(SELF) | $(PRIVATE)
	$(CROSS_COMPILE)objcopy --redefine-sym pow=pow_gate "$<" "$@"

$(PRIVATE)/body.o: $(LIBM) $(GATE_DIR)prepare_body.py $(GATE_DIR)body_support.c $(SELF) | $(PRIVATE)
	python3 -B "$(GATE_DIR)prepare_body.py" "$(CROSS_COMPILE)" "$<" "$@"

$(PRIVATE)/gate-sw.o: software := 1
$(PRIVATE)/gate-hw.o: software := 0
$(PRIVATE)/gate-sw.o $(PRIVATE)/gate-hw.o: $(GATE_DIR)gate.S $(SELF) | $(PRIVATE)
	$(CC) $(ABI) -MMD -DSOFTWARE_REGS=$(software) -c "$<" -o "$@"

$(OUT_DIR)/bwaves-%.elf: $(APP_OBJECTS) $(PRIVATE)/gate-%.o $(PRIVATE)/body.o $(GATE_DIR)layout.ld $(SELF)
	$(FC) $(ABI) -O2 -static -Wl,-T,"$(GATE_DIR)layout.ld",-Map,"$@.map" \
	    -o "$@" $(filter %.o,$^)

-include $(PRIVATE)/gate-sw.d $(PRIVATE)/gate-hw.d
