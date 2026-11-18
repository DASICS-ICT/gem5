# SPDX-License-Identifier: BSD-3-Clause

CROSS_COMPILE ?= riscv64-linux-gnu-
CC = $(CROSS_COMPILE)gcc
CFLAGS = -march=rv64imafdc_zicsr -mabi=lp64d -nostdlib -nostartfiles -static
LDFLAGS = -no-pie -Wl,--build-id=none -Wl,-T,link.ld
PROGRAM := riscv-dasics-reg-protection
OUT := ../build/$(PROGRAM)
ELFS := $(OUT).elf $(OUT)-context-read.elf $(OUT)-context-write.elf \
	$(OUT)-stack-read.elf $(OUT)-stack-write.elf
COMMON := context.h runtime.inc gate.inc link.ld
ROI_COUNTS ?= 1024 4096
gate_boundary := GATE_BOUNDARY
gate_save := GATE_SAVE
gate_restore := GATE_RESTORE
gate_software := GATE_SOFTWARE
ROI_ELFS := $(foreach mode,boundary save restore software,\
    $(foreach body,empty compute,\
    $(foreach count,$(ROI_COUNTS),../build/roi/$(mode)-$(body)-$(count).elf)))
roi_fields = $(subst -, ,$(basename $(notdir $@)))

VLEN ?= 128
VEC_BUILD := $(if $(filter 128,$(VLEN)),../build,../build/vlen-$(VLEN))
VEC_CFLAGS := $(subst rv64imafdc,rv64gcv,$(CFLAGS)) -DVECTOR_VLEN=$(VLEN)
VEC_WIDTH_TARGETS := $(addprefix vector-roi-,128 256 512 1024)
VEC_MODES := standard_ref standard_guard variant_ref variant_guard
VEC_ELFS := $(foreach mode,$(VEC_MODES),$(foreach body,empty compute,\
    $(foreach n,$(ROI_COUNTS),$(VEC_BUILD)/roi/$(mode)-$(body)-$(n).elf)))
VEC_CHECKS := $(addprefix $(VEC_BUILD)/vector-check-,standard.elf variant.elf)

.PHONY: all roi vector-roi vector-roi-all $(VEC_WIDTH_TARGETS) run clean

all: $(ELFS)

roi: $(ROI_ELFS)

vector-roi: $(VEC_CHECKS) $(VEC_ELFS)

vector-roi-all: $(VEC_WIDTH_TARGETS)

$(VEC_WIDTH_TARGETS): vector-roi-%:
	$(MAKE) vector-roi VLEN=$*

$(VEC_CHECKS): vector-check.S $(COMMON) $(MAKEFILE_LIST)
	mkdir -p $(dir $@)
	$(CC) $(VEC_CFLAGS) -DVECTOR_ABI=$(if $(findstring variant,$@),2,1) \
		-DVECTOR_PROTECTED=1 $(LDFLAGS) -o $@ $<

$(VEC_ELFS): riscv-dasics-reg-roi.S $(COMMON) $(MAKEFILE_LIST)
	mkdir -p $(dir $@)
	$(CC) $(VEC_CFLAGS) -I../../../../../include \
		-DVECTOR_ABI=$(if $(findstring variant,$@),2,1) \
		-DVECTOR_PROTECTED=$(if $(findstring _guard,$@),1,0) \
		-DROI_WORKLOAD=$(if $(filter compute,$(word 2,$(roi_fields))),1,0) \
		-DROI_ITERATIONS=$(word 3,$(roi_fields)) $(LDFLAGS) -o $@ $<

$(OUT).elf: TEST_SCENARIO = 0
$(OUT)-context-read.elf: TEST_SCENARIO = 1
$(OUT)-context-write.elf: TEST_SCENARIO = 2
$(OUT)-stack-read.elf: TEST_SCENARIO = 3
$(OUT)-stack-write.elf: TEST_SCENARIO = 4

$(ELFS): $(PROGRAM).S $(COMMON) $(MAKEFILE_LIST)
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -DTEST_SCENARIO=$(TEST_SCENARIO) $(LDFLAGS) -o $@ $<

$(ROI_ELFS): riscv-dasics-reg-roi.S $(COMMON) $(MAKEFILE_LIST)
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -I../../../../../include \
		-DGATE_MODE=$(gate_$(word 1,$(roi_fields))) \
		-DROI_WORKLOAD=$(if $(filter compute,$(word 2,$(roi_fields))),1,0) \
		-DROI_ITERATIONS=$(word 3,$(roi_fields)) $(LDFLAGS) -o $@ $<

# Shared paths and the CPU selection come from the root dispatcher.
run: all
	python3 run.py --repo "$(GEM5_REPO_DIR)" --gem5 "$(GEM5_BINARY)" \
		--config "$(GEM5_CONFIG)" --outdir "$(GEM5_OUTDIR)" --cpu "$(CPU)"

clean:
	rm -f $(ELFS) $(ROI_ELFS) \
	    $(foreach dir,../build $(addprefix ../build/vlen-,256 512 1024),\
	      $(addprefix $(dir)/,$(notdir $(VEC_CHECKS))) \
	      $(addprefix $(dir)/roi/,$(notdir $(VEC_ELFS))))
