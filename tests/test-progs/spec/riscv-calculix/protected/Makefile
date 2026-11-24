# SPDX-License-Identifier: BSD-3-Clause

SELF := $(abspath $(lastword $(MAKEFILE_LIST)))
PROTECTED := $(dir $(SELF))
ORDINARY_CASE ?= $(PROTECTED)..
APP_DIR := $(abspath $(ORDINARY_CASE))
OUT ?= $(PROTECTED)../build/protected-fmod
OUT_DIR := $(abspath $(OUT))
ifndef RUN_DIR
ifneq ($(filter check check-sw check-gf time-calls,$(MAKECMDGOALS)),)
RUN_DIR := $(OUT_DIR)/runs/$(shell date +%Y%m%d-%H%M%S-%N)
endif
endif
.DEFAULT_GOAL := all
.DELETE_ON_ERROR:

# Measure the already linked ELFs at the same paths as the reference run.
.PHONY: time-calls timing-inputs time-calls-sw time-calls-gf
timing-inputs:
	@test -f "$(BASELINE)/sw/result.json" -a -f "$(BASELINE)/gf/result.json" || \
	    { echo "Set BASELINE to the reference directory containing sw/ and gf/"; exit 2; }
	python3 "$(PROTECTED)check_layout.py" "$(OUT_DIR)/calculix-sw.elf" "$(OUT_DIR)/calculix-gf.elf"

time-calls-sw time-calls-gf: time-calls-%: timing-inputs
	python3 "$(PROTECTED)check.py" "$*" --time-calls \
	    --elf "$(OUT_DIR)/calculix-$*.elf" --assets "$(APP_DIR)/.." \
	    --outdir "$(RUN_DIR)/functional/$*"

time-calls: time-calls-sw time-calls-gf
	python3 "$(PROTECTED)paired_calls.py" --runs "$(RUN_DIR)/functional" \
	    --baseline "$(BASELINE)" --outdir "$(RUN_DIR)"

ifneq ($(CURDIR),$(APP_DIR))
# The ordinary build.mk discovers its sources relative to the case directory.
.PHONY: all check check-layout
all check check-layout:
	+$(MAKE) --no-print-directory -C "$(APP_DIR)" -f "$(SELF)" $@ \
	    ORDINARY_CASE="$(APP_DIR)" OUT="$(OUT_DIR)" RUN_DIR="$(abspath $(RUN_DIR))"
else
include $(APP_DIR)/build.mk

CROSS_COMPILE ?= riscv64-linux-gnu-
CC := $(CROSS_COMPILE)gcc
FC := $(CROSS_COMPILE)gfortran
OBJCOPY := $(CROSS_COMPILE)objcopy
ABI := -march=rv64gc -mabi=lp64d
LIBM := $(shell $(CC) $(ABI) -print-file-name=libm.a)
LIBGCC := $(shell $(CC) $(ABI) -print-file-name=libgcc.a)
OBJECT_DIR := $(APP_DIR)/build/objects
SOURCES := $(patsubst ./%,%,$(sort $(SRCS)))
OBJECTS := $(addprefix $(OBJECT_DIR)/,$(addsuffix .o,$(basename $(SOURCES))))
DRAND := $(OBJECT_DIR)/src/SPOOLES/Drand/src
CALLERS := Drand_init.o Drand_util.o
APP_OBJECTS := $(filter-out $(addprefix $(DRAND)/,$(CALLERS)),$(OBJECTS))
PRIVATE := $(OUT_DIR)/private
PRIVATE_OBJECTS := $(addprefix $(PRIVATE)/,body.o clz.o ctz.o table.o $(CALLERS))
.SECONDARY: $(addprefix $(PRIVATE)/,$(CALLERS))

.PHONY: all check check-layout check-sw check-gf
all: $(OUT_DIR)/calculix-sw.elf $(OUT_DIR)/calculix-gf.elf

$(PRIVATE):
	mkdir -p "$@"

$(PRIVATE)/Drand_%.o: $(DRAND)/Drand_%.o $(SELF) | $(PRIVATE)
	$(OBJCOPY) --redefine-sym fmod=dasics_fmod_gate "$<" "$@"

# RV64 libgcc's si2 archive members export the 64-bit __clzdi2/__ctzdi2.
$(PRIVATE)/body.o: member := e_fmod.o
$(PRIVATE)/body.o: section := --rename-section .text=.dasics.fmod.body
$(PRIVATE)/body.o: $(LIBM)
$(PRIVATE)/clz.o: member := _clzsi2.o
$(PRIVATE)/ctz.o: member := _ctzsi2.o
$(PRIVATE)/clz.o $(PRIVATE)/ctz.o: section := --rename-section .text=.dasics.fmod.helper
$(PRIVATE)/table.o: member := _clz.o
$(PRIVATE)/table.o: section := --rename-section .rodata=.dasics.fmod.ro
$(PRIVATE)/clz.o $(PRIVATE)/ctz.o $(PRIVATE)/table.o: $(LIBGCC)
$(PRIVATE)/body.o $(PRIVATE)/clz.o $(PRIVATE)/ctz.o $(PRIVATE)/table.o: \
        $(PROTECTED)private.syms $(SELF) | $(PRIVATE)
	@set -eu; trap 'rm -f "$@.raw"' EXIT; \
	    $(CROSS_COMPILE)ar p "$(filter %.a,$^)" "$(member)" > "$@.raw"; \
	    $(OBJCOPY) --redefine-syms="$(PROTECTED)private.syms" $(section) \
	        "$@.raw" "$@"

$(PRIVATE)/gate-sw.o: hw := 0
$(PRIVATE)/gate-gf.o: hw := 1
$(PRIVATE)/gate-sw.o $(PRIVATE)/gate-gf.o: $(PROTECTED)gate.S \
        $(PROTECTED)../../../dasics/riscv-dasics-reg-protection/src/context.h \
        $(SELF) | $(PRIVATE)
	$(CC) $(ABI) -DUSE_INT_PROREG=$(hw) -DUSE_FP_PROREG=$(hw) -c "$<" -o "$@"

$(OUT_DIR)/calculix-%.elf: $(PRIVATE)/gate-%.o $(PRIVATE_OBJECTS) \
        $(APP_OBJECTS) $(APP_DIR)/build.mk $(PROTECTED)link.ld $(SELF)
	@$(FC) $(ABI) -O2 -static -Wl,-T,"$(PROTECTED)link.ld",-Map,"$@.map" \
	    -o "$@" $(APP_OBJECTS) $(PRIVATE_OBJECTS) "$<" $(LIBS)

check: check-sw check-gf
check-layout: $(OUT_DIR)/calculix-sw.elf $(OUT_DIR)/calculix-gf.elf
	python3 "$(PROTECTED)check_layout.py" $^

check-sw check-gf: check-%: $(OUT_DIR)/calculix-%.elf | check-layout
	python3 "$(PROTECTED)check.py" "$*" --elf "$<" \
	    --outdir "$(RUN_DIR)/$*" --assets "$(APP_DIR)/.."
endif
