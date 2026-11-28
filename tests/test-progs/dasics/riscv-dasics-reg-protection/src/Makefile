# SPDX-License-Identifier: BSD-3-Clause

CROSS_COMPILE ?= riscv64-linux-gnu-
CC = $(CROSS_COMPILE)gcc
CFLAGS = -march=rv64imafdc_zicsr -mabi=lp64d -nostdlib -nostartfiles -static
LDFLAGS = -no-pie -Wl,--build-id=none -Wl,-T,link.ld
PROGRAM := riscv-dasics-reg-protection
OUT := ../build/$(PROGRAM)
NORMAL_ELFS := $(OUT).elf $(OUT)-normal-proreg.elf $(OUT)-normal-proreg-gf.elf
ELFS := $(NORMAL_ELFS) $(OUT)-context-read.elf $(OUT)-context-write.elf \
	$(OUT)-stack-read.elf $(OUT)-stack-write.elf
SEQUENCE_ELFS := $(addprefix $(OUT)-sequence-,sw.elf gf.elf b-read-c.elf c-read-b.elf \
	b-jump-c.elf c-jump-b.elf)
SEQUENCE_FULL_ELFS := $(addprefix $(OUT)-sequence-full-,sw.elf gf.elf)
COMMON := context.h runtime.inc gate.inc link.ld
PRF_ELFS := $(addprefix ../build/prf-pressure/,k0.elf k12.elf)
PRF_SOFTWARE_ELFS := $(addprefix ../build/prf-pressure/software/,k0.elf k12.elf)
ROI_COUNTS ?= 1024 4096
SEQUENCE_ROI_ELFS := $(foreach mode,software proreg_gf,\
    $(foreach n,$(sort 4 $(ROI_COUNTS)),../build/roi/sequence/$(mode)-$(n).elf))
SEQUENCE_FULL_ROI_ELFS := $(subst /sequence/,/sequence-full/,$(SEQUENCE_ROI_ELFS))
gate_boundary := GATE_BOUNDARY
gate_save := GATE_SAVE
gate_restore := GATE_RESTORE
gate_software := GATE_SOFTWARE
gate_proreg := GATE_SOFTWARE
gate_proreg_gf := GATE_SOFTWARE
ROI_ELFS := $(foreach mode,boundary save restore software,\
    $(foreach body,empty compute,\
    $(foreach count,$(ROI_COUNTS),../build/roi/$(mode)-$(body)-$(count).elf)))
PROREG_ROI_ELFS := $(foreach body,empty compute,\
    $(foreach count,$(ROI_COUNTS),../build/roi/proreg-$(body)-$(count).elf))
PROREG_GF_ROI_ELFS := $(foreach body,empty compute,\
    $(foreach count,$(ROI_COUNTS),../build/roi/proreg_gf-$(body)-$(count).elf))
clobber_elfs = $(foreach mode,$(1),$(foreach body,empty compute,\
    $(foreach count,$(ROI_COUNTS),$(foreach k,0 1 6 12,\
    ../build/roi/$(mode)-$(body)-$(count)-$(2)$(k).elf))))
CLOBBER_ROI_ELFS := $(call clobber_elfs,software proreg,clobber)
FP_CLOBBER_ROI_ELFS := $(call clobber_elfs,proreg proreg_gf,fpclobber)
SCALAR_ROI_ELFS := $(ROI_ELFS) $(PROREG_ROI_ELFS) $(PROREG_GF_ROI_ELFS) \
    $(CLOBBER_ROI_ELFS) $(FP_CLOBBER_ROI_ELFS)
roi_fields = $(subst -, ,$(basename $(notdir $@)))

VLEN ?= 128
VEC_BUILD := $(if $(filter 128,$(VLEN)),../build,../build/vlen-$(VLEN))
VEC_CFLAGS := $(subst rv64imafdc,rv64gcv,$(CFLAGS)) -DVECTOR_VLEN=$(VLEN)
VEC_WIDTH_TARGETS := $(addprefix vector-roi-,128 256 512 1024)
VEC_MODES := standard_ref standard_guard variant_ref variant_guard
VEC_ELFS := $(foreach mode,$(VEC_MODES),$(foreach body,empty compute,\
    $(foreach n,$(ROI_COUNTS),$(VEC_BUILD)/roi/$(mode)-$(body)-$(n).elf)))
VEC_CHECKS := $(addprefix $(VEC_BUILD)/vector-check-,standard.elf variant.elf)

.PHONY: all roi sequence-roi sequence-full-roi proreg-roi proreg-gf-roi clobber-roi fp-clobber-roi \
    vector-roi vector-roi-all $(VEC_WIDTH_TARGETS) prf-pressure prf-pressure-software run clean

all: $(ELFS) $(SEQUENCE_ELFS) $(SEQUENCE_FULL_ELFS)

roi: $(ROI_ELFS)

prf-pressure: $(PRF_ELFS)

$(PRF_ELFS): ../build/prf-pressure/k%.elf: prf-pressure.S $(COMMON) $(MAKEFILE_LIST)
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -DPRF_CLOBBERS=$* $(LDFLAGS) -o $@ $<

prf-pressure-software: $(PRF_SOFTWARE_ELFS)

$(PRF_SOFTWARE_ELFS): ../build/prf-pressure/software/k%.elf: prf-pressure.S $(COMMON) $(MAKEFILE_LIST)
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -DUSE_INT_PROREG=0 -DPRF_CLOBBERS=$* $(LDFLAGS) -o $@ $<

sequence-roi: $(OUT)-sequence-sw.elf $(OUT)-sequence-gf.elf $(SEQUENCE_ROI_ELFS)

# The narrow ROI images are the layout reference for the full-mask pair.
sequence-full-roi: $(SEQUENCE_FULL_ELFS) $(SEQUENCE_FULL_ROI_ELFS) $(SEQUENCE_ROI_ELFS)

proreg-roi: $(filter ../build/roi/software-%,$(ROI_ELFS)) $(PROREG_ROI_ELFS)

proreg-gf-roi: $(PROREG_ROI_ELFS) $(PROREG_GF_ROI_ELFS)

clobber-roi: $(CLOBBER_ROI_ELFS)

fp-clobber-roi: $(FP_CLOBBER_ROI_ELFS)

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

$(NORMAL_ELFS): TEST_SCENARIO = 0
$(OUT)-normal-proreg.elf $(OUT)-normal-proreg-gf.elf: override CFLAGS += \
    -DUSE_INT_PROREG=1
$(OUT)-normal-proreg-gf.elf: override CFLAGS += -DUSE_FP_PROREG=1
$(OUT)-context-read.elf: TEST_SCENARIO = 1
$(OUT)-context-write.elf: TEST_SCENARIO = 2
$(OUT)-stack-read.elf: TEST_SCENARIO = 3
$(OUT)-stack-write.elf: TEST_SCENARIO = 4

$(ELFS): $(PROGRAM).S $(COMMON) $(MAKEFILE_LIST)
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -DTEST_SCENARIO=$(TEST_SCENARIO) $(LDFLAGS) -o $@ $<

$(OUT)-sequence-sw.elf $(OUT)-sequence-gf.elf $(SEQUENCE_FULL_ELFS): SEQUENCE_DENY := 0
$(OUT)-sequence-sw.elf $(OUT)-sequence-full-sw.elf: override CFLAGS += -DSEQUENCE_SOFTWARE=1
$(SEQUENCE_FULL_ELFS) $(SEQUENCE_FULL_ROI_ELFS): override CFLAGS += -DSEQUENCE_FULL=1
$(OUT)-sequence-b-read-c.elf: SEQUENCE_DENY := 1
$(OUT)-sequence-c-read-b.elf: SEQUENCE_DENY := 2
$(OUT)-sequence-b-jump-c.elf: SEQUENCE_DENY := 3
$(OUT)-sequence-c-jump-b.elf: SEQUENCE_DENY := 4
$(SEQUENCE_ELFS) $(SEQUENCE_FULL_ELFS): sequence.S runtime.inc context.h link.ld $(MAKEFILE_LIST)
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -DSEQUENCE_DENY=$(SEQUENCE_DENY) $(LDFLAGS) -o $@ $<

$(SEQUENCE_ROI_ELFS) $(SEQUENCE_FULL_ROI_ELFS): sequence.S runtime.inc context.h link.ld $(MAKEFILE_LIST)
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -I../../../../../include -DSEQUENCE_ROI=1 \
		-DSEQUENCE_SOFTWARE=$(if $(filter software,$(word 1,$(roi_fields))),1,0) \
		-DROI_ITERATIONS=$(word 2,$(roi_fields)) $(LDFLAGS) -o $@ $<

$(filter ../build/roi/proreg-%,$(SCALAR_ROI_ELFS)): override CFLAGS += -DUSE_INT_PROREG=1
$(filter ../build/roi/proreg_gf-%,$(SCALAR_ROI_ELFS)): override CFLAGS += -DUSE_INT_PROREG=1 -DUSE_FP_PROREG=1
$(CLOBBER_ROI_ELFS): override CFLAGS += -DROI_CLOBBER_COUNT=$(patsubst clobber%,%,$(word 4,$(roi_fields)))
$(FP_CLOBBER_ROI_ELFS): override CFLAGS += -DROI_FP_CLOBBER=1 \
    -DROI_CLOBBER_COUNT=$(patsubst fpclobber%,%,$(word 4,$(roi_fields)))
$(SCALAR_ROI_ELFS): riscv-dasics-reg-roi.S $(COMMON) $(MAKEFILE_LIST)
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
	rm -f $(ELFS) $(PRF_ELFS) $(PRF_SOFTWARE_ELFS) $(SEQUENCE_ELFS) $(SEQUENCE_FULL_ELFS) $(SEQUENCE_ROI_ELFS) \
	    $(SEQUENCE_FULL_ROI_ELFS) $(SCALAR_ROI_ELFS) \
	    $(foreach dir,../build $(addprefix ../build/vlen-,256 512 1024),\
	      $(addprefix $(dir)/,$(notdir $(VEC_CHECKS))) \
	      $(addprefix $(dir)/roi/,$(notdir $(VEC_ELFS))))
