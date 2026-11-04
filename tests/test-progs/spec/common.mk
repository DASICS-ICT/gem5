# Copyright (c) 2026 zengsy99
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause

CASE_DIR := $(abspath $(dir $(firstword $(MAKEFILE_LIST))))
SPEC_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PROGRAM := $(patsubst riscv-%,%,$(notdir $(CASE_DIR)))
BUILD_DIR := $(CASE_DIR)/build
DST_DIR := $(BUILD_DIR)/objects
MOD_DIR := $(BUILD_DIR)/modules
ELF := $(BUILD_DIR)/$(PROGRAM).elf

ARCH := riscv64
CROSS_COMPILE ?= riscv64-linux-gnu-
CC := $(CROSS_COMPILE)gcc
CXX := $(CROSS_COMPILE)g++
FC := $(CROSS_COMPILE)gfortran
QEMU ?= qemu-riscv64
PYTHON ?= python3
TIMEOUT ?= 1800
input ?= test

.DEFAULT_GOAL := all
.PHONY: all run check gem5-test clean

$(DST_DIR)/%.o: %.c build.mk ../common.mk
	@mkdir -p "$(dir $@)"
	$(CC) $(CFLAGS) -c -o "$@" "$(abspath $<)"

$(DST_DIR)/%.o: %.C build.mk ../common.mk
	@mkdir -p "$(dir $@)"
	$(CXX) $(CXXFLAGS) -c -o "$@" "$(abspath $<)"

$(DST_DIR)/%.o: %.cc build.mk ../common.mk
	@mkdir -p "$(dir $@)"
	$(CXX) $(CXXFLAGS) -c -o "$@" "$(abspath $<)"

$(DST_DIR)/%.o: %.cpp build.mk ../common.mk
	@mkdir -p "$(dir $@)"
	$(CXX) $(CXXFLAGS) -c -o "$@" "$(abspath $<)"

# Keep module files outside the source tree; dependencies order their producers.
$(DST_DIR)/%.o: %.f build.mk ../common.mk
	@mkdir -p "$(dir $@)" "$(MOD_DIR)"
	cd "$(dir $<)" && $(FC) $(FFLAGS) -c -o "$@" "$(abspath $<)"

$(DST_DIR)/%.o: %.f90 build.mk ../common.mk
	@mkdir -p "$(dir $@)" "$(MOD_DIR)"
	cd "$(dir $<)" && $(FC) $(FFLAGS) -c -o "$@" "$(abspath $<)"

include $(CASE_DIR)/build.mk

# Match the ordinary origin build and use one ISA/ABI for all source languages.
CFLAGS += -O2 -g -MMD -DSPEC_CPU -DNDEBUG -D_FILE_OFFSET_BITS=64 \
          -DSPEC_CPU_LP64 -static -march=rv64gc -mabi=lp64d
CXXFLAGS += $(CFLAGS)
FFLAGS += -O2 $(FFLAGS_EXTRA) -DSPEC_CPU_LP64 -static \
          -march=rv64gc -mabi=lp64d -J$(MOD_DIR)
LDFLAGS += -O2 -static -march=rv64gc -mabi=lp64d

ifeq ($(LD_FORTRAN),1)
LINK := $(FC)
else ifeq ($(LD_CXX),1)
LINK := $(CXX)
else
LINK := $(CC)
endif

SOURCES := $(patsubst ./%,%,$(sort $(SRCS)))
OBJECTS := $(addprefix $(DST_DIR)/,$(addsuffix .o,$(basename $(SOURCES))))
-include $(CASE_DIR)/Makefile.deps
-include $(OBJECTS:.o=.d)

$(ELF): $(OBJECTS)
	$(LINK) $(LDFLAGS) -o "$@" $(OBJECTS) $(LIBS)

all: $(ELF)
	$(PYTHON) "$(SPEC_DIR)/run.py" --case "$(CASE_DIR)" verify-build \
		--readelf "$(CROSS_COMPILE)readelf"

run: all
	$(PYTHON) "$(SPEC_DIR)/run.py" --case "$(CASE_DIR)" qemu \
		--qemu "$(QEMU)" --input "$(input)" --timeout "$(TIMEOUT)" \
		$(if $(filter 1,$(SMOKE)),--smoke,)

check:
	$(PYTHON) "$(SPEC_DIR)/run.py" --case "$(CASE_DIR)" check --input "$(input)"

gem5-test: all
	$(PYTHON) "$(SPEC_DIR)/run.py" --case "$(CASE_DIR)" gem5 \
		--gem5-binary "$(GEM5_BINARY)" --gem5-config "$(GEM5_CONFIG)" \
		--gem5-outdir "$(GEM5_OUTDIR)" --input "$(input)" \
		--timeout "$(TIMEOUT)" $(if $(filter 1,$(SMOKE)),--smoke,)

clean:
	rm -rf -- "$(BUILD_DIR)"
