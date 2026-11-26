# SPDX-License-Identifier: BSD-3-Clause

SELF := $(abspath $(lastword $(MAKEFILE_LIST)))
GATE_DIR := $(dir $(SELF))
ORDINARY_CASE ?= $(GATE_DIR)..
APP_DIR := $(abspath $(ORDINARY_CASE))
OUT ?= $(GATE_DIR)../build/protected-strtok
OUT_DIR := $(abspath $(OUT))
PRIVATE := $(OUT_DIR)/private
OVERLAY := $(PRIVATE)/src

CROSS_COMPILE ?= riscv64-linux-gnu-
CC := $(CROSS_COMPILE)gcc
CXX := $(CROSS_COMPILE)g++
ABI := -march=rv64gc -mabi=lp64d
LIBC := $(shell $(CC) $(ABI) -print-file-name=libc.a)
# Use the ordinary SPEC flags and link order for the shared application objects.
APP_FLAGS := -O2 -g -MMD -DSPEC_CPU -DNDEBUG -D_FILE_OFFSET_BITS=64 \
             -DSPEC_CPU_LP64 -static $(ABI)
NAMES := $(basename $(notdir $(sort $(wildcard $(APP_DIR)/src/*.cc))))
OBJECT_DIR := $(APP_DIR)/build/objects/src
LAYOUT_NAMES := mpsinput spxbasis spxmpsread
LAYOUT_OBJECTS := $(addprefix $(PRIVATE)/,$(addsuffix .o,$(LAYOUT_NAMES)))
APP_OBJECTS := $(foreach name,$(NAMES),$(if $(filter $(name),$(LAYOUT_NAMES)),$(PRIVATE),$(OBJECT_DIR))/$(name).o)
# Only the data-row caller differs between the oracle and timed builds.
PERF_CALLER := $(PRIVATE)/mpsinput-perf.o
PERF_OBJECTS := $(patsubst $(PRIVATE)/mpsinput.o,$(PERF_CALLER),$(APP_OBJECTS))
LAYOUT_FILES := mpsinput.h $(addsuffix .cc,$(LAYOUT_NAMES))

.DEFAULT_GOAL := all
.DELETE_ON_ERROR:
.PHONY: all perf

all: $(OUT_DIR)/soplex-sw.elf $(OUT_DIR)/soplex-hw.elf
perf: $(OUT_DIR)/soplex-perf-sw.elf $(OUT_DIR)/soplex-perf-hw.elf

$(PRIVATE) $(OVERLAY):
	mkdir -p "$@"

$(addprefix $(OVERLAY)/,$(LAYOUT_FILES)) &: $(addprefix $(APP_DIR)/src/,$(LAYOUT_FILES)) \
    $(addprefix $(OBJECT_DIR)/,$(addsuffix .d,$(NAMES))) $(GATE_DIR)prepare_sources.py $(SELF) | $(OVERLAY)
	python3 -B "$(GATE_DIR)prepare_sources.py" "$(APP_DIR)" "$(OVERLAY)" $(LAYOUT_NAMES)

$(PRIVATE)/mpsinput.o: private CPPFLAGS += -DSOPLEX_DATA_STRTOK=checked_strtok
$(LAYOUT_OBJECTS): $(PRIVATE)/%.o: $(OVERLAY)/%.cc $(OVERLAY)/mpsinput.h $(SELF)
	$(CXX) $(CPPFLAGS) $(APP_FLAGS) -I"$(APP_DIR)/src" -c "$<" -o "$@"

$(PERF_CALLER): $(OVERLAY)/mpsinput.cc $(OVERLAY)/mpsinput.h $(SELF)
	$(CXX) $(CPPFLAGS) $(APP_FLAGS) -DSOPLEX_DATA_STRTOK=strtok_gate -I"$(APP_DIR)/src" -c "$<" -o "$@"

$(PRIVATE)/body.o: $(LIBC) $(GATE_DIR)prepare_body.py $(GATE_DIR)body_support.c $(SELF) | $(PRIVATE)
	python3 -B "$(GATE_DIR)prepare_body.py" "$(CROSS_COMPILE)" "$<" "$@"

$(PRIVATE)/verify_tokens.o: $(GATE_DIR)verify_tokens.c $(SELF) | $(PRIVATE)
	$(CC) $(ABI) -O2 -c "$<" -o "$@"

$(PRIVATE)/gate-sw.o: software := 1
$(PRIVATE)/gate-hw.o: software := 0
$(PRIVATE)/gate-sw.o $(PRIVATE)/gate-hw.o: $(GATE_DIR)gate.S $(SELF) | $(PRIVATE)
	$(CC) $(ABI) -MMD -DSOFTWARE_REGS=$(software) -c "$<" -o "$@"

LINK_GATE = $(CXX) $(ABI) -O2 -static -Wl,-T,"$(GATE_DIR)layout.ld",-Map,"$@.map" \
            -o "$@" $(filter %.o,$^)

$(OUT_DIR)/soplex-%.elf: $(APP_OBJECTS) $(PRIVATE)/verify_tokens.o $(PRIVATE)/gate-%.o \
    $(PRIVATE)/body.o $(GATE_DIR)layout.ld $(SELF)
	$(LINK_GATE)

$(OUT_DIR)/soplex-perf-%.elf: $(PERF_OBJECTS) $(PRIVATE)/gate-%.o \
    $(PRIVATE)/body.o $(GATE_DIR)layout.ld $(SELF)
	$(LINK_GATE)

-include $(LAYOUT_OBJECTS:.o=.d) $(PERF_CALLER:.o=.d) $(PRIVATE)/gate-sw.d $(PRIVATE)/gate-hw.d
