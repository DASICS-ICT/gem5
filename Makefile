# SPDX-License-Identifier: BSD-3-Clause

SHELL := /bin/bash
.DEFAULT_GOAL := riscv

# Define shared repository paths before invoking test Makefiles.
GEM5_REPO_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
LOG_DIR := $(abspath $(GEM5_REPO_DIR)/../build-logs)

# Budget 2 GiB per compiler process, up to the available CPU count.
JOBS ?= $(shell /usr/bin/awk -v n="$$(/usr/bin/nproc)" \
	'/MemAvailable:/ {j=int($$2/2097152); print (j<1 ? 1 : (j<n ? j : n))}' \
	/proc/meminfo)

.PHONY: riscv clean dasics-test dasics-clean dasics-check
# SCons owns build parallelism; serialize the build and cleanup targets.
.NOTPARALLEL:

# Always invoke SCons so it can check source, header, and command dependencies.
# Keep system Python and Protobuf together to avoid Conda library conflicts.
riscv:
	@mkdir -p "$(LOG_DIR)"
	@set -o pipefail; \
	cd "$(GEM5_REPO_DIR)" || exit; \
	log="$(LOG_DIR)/riscv-$$(TZ=Asia/Shanghai date +%Y%m%d-%H%M%S)-$$$$.log"; \
	printf 'Build log: %s\n' "$$log"; \
	{ \
		printf 'Started: %s\nJobs: %s\n' \
			"$$(TZ=Asia/Shanghai date -Iseconds)" "$(JOBS)"; \
		env -u PYTHONPATH -u LD_LIBRARY_PATH -u LIBRARY_PATH \
			-u PKG_CONFIG_PATH -u CPATH \
			PATH=/usr/bin:/bin \
			PYTHON_CONFIG=/usr/bin/python3-config \
			PROTOC=/usr/bin/protoc \
			/usr/bin/scons build/RISCV/gem5.opt -j "$(JOBS)"; \
		status=$$?; \
		printf 'Finished: %s\nExit code: %s\n' \
			"$$(TZ=Asia/Shanghai date -Iseconds)" "$$status"; \
		exit "$$status"; \
	} 2>&1 | /usr/bin/tee "$$log"

clean:
	rm -rf -- "$(GEM5_REPO_DIR)/build/RISCV"

# Each test owns its run target and output layout.
dasics-test: dasics-check
	@$(MAKE) --no-print-directory \
		-C "$(GEM5_REPO_DIR)/tests/test-progs/dasics/$(TEST)/src" \
		GEM5_REPO_DIR="$(GEM5_REPO_DIR)" run; \
		dasics_rc=$$?; \
		if [ "$$dasics_rc" -ne 0 ]; then \
			printf '\n\033[1;31m[FAIL] %s\033[0m\n' "$(TEST)" >&2; \
			exit "$$dasics_rc"; \
		fi
	@printf '\n\033[1;32m[OK] %s\033[0m\n' "$(TEST)"

dasics-clean: dasics-check
	@$(MAKE) --no-print-directory \
		-C "$(GEM5_REPO_DIR)/tests/test-progs/dasics/$(TEST)/src" clean

# Both actions require an existing test before invoking its Makefile.
dasics-check:
	@test -n "$(TEST)" || { \
		printf '\033[1;31m[FAIL] Set TEST=<test-name>.\033[0m\n' >&2; \
		exit 2; \
	}
	@test -f \
		"$(GEM5_REPO_DIR)/tests/test-progs/dasics/$(TEST)/src/Makefile" || { \
		printf '\033[1;31m[FAIL] Unknown DASICS test: %s\033[0m\n' \
			"$(TEST)" >&2; exit 2; \
	}
