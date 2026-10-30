# SPDX-License-Identifier: BSD-3-Clause

SHELL := /bin/bash
.DEFAULT_GOAL := riscv

REPO_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
LOG_DIR := $(abspath $(REPO_DIR)/../build-logs)

# Budget 2 GiB per compiler process, up to the available CPU count.
JOBS ?= $(shell /usr/bin/awk -v n="$$(/usr/bin/nproc)" \
	'/MemAvailable:/ {j=int($$2/2097152); print (j<1 ? 1 : (j<n ? j : n))}' \
	/proc/meminfo)

.PHONY: riscv clean
# SCons owns build parallelism; serialize the build and cleanup targets.
.NOTPARALLEL:

# Always invoke SCons so it can check source, header, and command dependencies.
# Keep system Python and Protobuf together to avoid Conda library conflicts.
riscv:
	@mkdir -p "$(LOG_DIR)"
	@set -o pipefail; \
	cd "$(REPO_DIR)" || exit; \
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
	rm -rf -- "$(REPO_DIR)/build/RISCV"
