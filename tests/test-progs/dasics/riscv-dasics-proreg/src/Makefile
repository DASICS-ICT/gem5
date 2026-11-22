# SPDX-License-Identifier: BSD-3-Clause

PROGRAM := riscv-dasics-proreg

# Each privilege mode boots independently with empty restore slots.
BOOTS := U S
ifdef PROREG_BOOT
override OUT := ../build/$(PROGRAM)-$(PROREG_BOOT).elf
include ../../riscv-dasics-csr/src/Makefile
override CFLAGS += -DPROREG_TEST_$(PROREG_BOOT)
ifeq ($(CPU),v5_full)
# Require the reference O3 model to exercise the loop-exit rollback.
GEM5_TEST_RUNNER := python3 "$(abspath check_rollback.py)" "$(CROSS_COMPILE)nm"
endif
else
.PHONY: all $(BOOTS) run clean
all: $(BOOTS)

$(BOOTS):
	$(MAKE) --no-print-directory PROREG_BOOT=$@ all

run: all
	@test -n "$(GEM5_OUTDIR)" || { \
		printf 'Use the root dasics-test target to run this test.\n' >&2; exit 2; }
	@set -e; mkdir -p "$(GEM5_OUTDIR)"; \
	rm -f "$(GEM5_OUTDIR)/run-result.txt"; \
	status=0; total=0; \
	for boot in $(BOOTS); do \
		dir="$(GEM5_OUTDIR)/$$boot"; \
		rm -f "$$dir/run-result.txt"; \
		printf '\nPROREG privilege: %s\n' "$$boot"; \
		make_rc=0; \
		$(MAKE) --no-print-directory PROREG_BOOT=$$boot GEM5_OUTDIR="$$dir" run \
			|| make_rc=$$?; \
		rc=1; cycles=N/A; \
		if [ -s "$$dir/run-result.txt" ]; then \
			read -r rc cycles < "$$dir/run-result.txt"; \
		fi; \
		if [ "$$rc" -eq 0 ]; then rc=$$make_rc; fi; \
		if [ "$$status" -eq 0 ] || [ "$$rc" -eq 124 ]; then status=$$rc; fi; \
		if [ "$$cycles" = N/A ] || [ "$$total" = N/A ]; then total=N/A; \
		else total=$$((total + cycles)); fi; \
	done; \
	if [ "$$status" -ne 0 ]; then total=N/A; fi; \
	printf '%s %s\n' "$$status" "$$total" > "$(GEM5_OUTDIR)/run-result.txt"; \
	printf 'CPU cycles (U and S boots combined): %s\n' "$$total"; \
	exit "$$status"

clean:
	rm -f $(foreach boot,$(BOOTS),../build/$(PROGRAM)-$(boot).elf) \
		../build/$(PROGRAM).elf
endif
