# SPDX-License-Identifier: BSD-3-Clause

SHELL := /bin/bash
.DEFAULT_GOAL := riscv

# Define shared repository paths before invoking test Makefiles.
GEM5_REPO_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
LOG_DIR := $(abspath $(GEM5_REPO_DIR)/../build-logs)
DASICS_CONFIG_DIR := $(GEM5_REPO_DIR)/configs/dasics
DASICS_TEST_DIR = $(GEM5_REPO_DIR)/tests/test-progs/dasics/$(TEST)
DASICS_OUT_DIR = $(DASICS_TEST_DIR)/build/m5out-o3
DASICS_CPUS := V2_minimal V2_nanhug V2_default v5_full v5_stress
CPU ?= v5_full

# Separate SPEC CPU2006 outputs by workload, model and input size.
SPEC06_TEST_DIR = $(GEM5_REPO_DIR)/tests/test-progs/spec/$(TEST)
SPEC06_CONFIG_DIR := $(GEM5_REPO_DIR)/configs/spec
SPEC06_CONFIGS := riscv_se_V2_minimal.py riscv_se_V2_nanhug.py \
	riscv_se_V2_default.py riscv_se_v5_full.py riscv_se_v5_stress.py
SPEC06_OUT_DIR = $(SPEC06_TEST_DIR)/build/m5out-o3
input ?= test

# Budget 2 GiB per compiler process, up to the available CPU count.
JOBS ?= $(shell /usr/bin/awk -v n="$$(/usr/bin/nproc)" \
	'/MemAvailable:/ {j=int($$2/2097152); print (j<1 ? 1 : (j<n ? j : n))}' \
	/proc/meminfo)

.PHONY: riscv riscv-dasics clean clean-riscv-dasics \
	dasics-test dasics-clean dasics-check dasics-cpu-check \
	spec06-test spec06-clean spec06-check
# SCons owns build parallelism; serialize the build and cleanup targets.
.NOTPARALLEL:

# Keep each build target tied to its own configuration and extension state.
riscv: override BUILD_CONFIG := RISCV
riscv: override DASICS_CONFIG := n
riscv-dasics: override BUILD_CONFIG := RISCV_DASICS
riscv-dasics: override DASICS_CONFIG := y

# Always invoke SCons so it can check source, header, and command dependencies.
# Keep system Python and Protobuf together to avoid Conda library conflicts.
riscv riscv-dasics:
	@mkdir -p "$(LOG_DIR)"
	@set -o pipefail; \
	cd "$(GEM5_REPO_DIR)" || exit; \
	log="$(LOG_DIR)/$@-$$(TZ=Asia/Shanghai date +%Y%m%d-%H%M%S)-$$$$.log"; \
	printf 'Build log: %s\n' "$$log"; \
	run_scons() { \
		env -u PYTHONPATH -u LD_LIBRARY_PATH -u LIBRARY_PATH \
			-u PKG_CONFIG_PATH -u CPATH \
			PATH=/usr/bin:/bin \
			PYTHON_CONFIG=/usr/bin/python3-config \
			PROTOC=/usr/bin/protoc \
			/usr/bin/scons "$$@"; \
	}; \
	{ \
		printf 'Started: %s\nJobs: %s\nDASICS: %s\n' \
			"$$(TZ=Asia/Shanghai date -Iseconds)" "$(JOBS)" \
			"$(DASICS_CONFIG)"; \
		status=0; \
		if [ ! -f "build/$(BUILD_CONFIG)/gem5.build/config" ]; then \
			run_scons defconfig "build/$(BUILD_CONFIG)" \
				"build_opts/$(BUILD_CONFIG)" || status=$$?; \
		fi; \
		if [ "$$status" -eq 0 ]; then \
			run_scons setconfig "build/$(BUILD_CONFIG)" \
				"USE_DASICS=$(DASICS_CONFIG)" || status=$$?; \
		fi; \
		if [ "$$status" -eq 0 ]; then \
			run_scons "build/$(BUILD_CONFIG)/gem5.opt" -j "$(JOBS)"; \
			status=$$?; \
		fi; \
		printf 'Finished: %s\nExit code: %s\n' \
			"$$(TZ=Asia/Shanghai date -Iseconds)" "$$status"; \
		exit "$$status"; \
	} 2>&1 | /usr/bin/tee "$$log"

clean:
	rm -rf -- "$(GEM5_REPO_DIR)/build/RISCV"

clean-riscv-dasics:
	rm -rf -- "$(GEM5_REPO_DIR)/build/RISCV_DASICS"

# Each test owns its run target and output layout.
# run-result.txt preserves simulator exit codes across recursive make calls.
dasics-test: override GEM5_BINARY := \
	$(GEM5_REPO_DIR)/build/RISCV_DASICS/gem5.opt
dasics-test: dasics-check dasics-cpu-check
	@$(MAKE) --no-print-directory \
		-C "$(DASICS_TEST_DIR)/src" \
		all || { \
			printf '\033[1;31m[FAIL] %s build\033[0m\n' "$(TEST)" >&2; \
			exit 1; \
		}; \
	models="$(CPU)"; \
	if [ "$$models" = all ]; then models="$(DASICS_CPUS)"; fi; \
	status=0; first=1; results=(); \
	for cpu in $$models; do \
		if [ "$$first" -eq 0 ]; then \
			printf '%s\n' '-------------------------------'; \
		fi; \
		first=0; \
		printf 'CPU: %s\n' "$$cpu"; \
		result_file="$(DASICS_OUT_DIR)/$$cpu/run-result.txt"; \
		rm -f "$$result_file" || exit; \
		$(MAKE) --no-print-directory \
			-C "$(DASICS_TEST_DIR)/src" \
			GEM5_REPO_DIR="$(GEM5_REPO_DIR)" \
			GEM5_BINARY="$(GEM5_BINARY)" CPU="$$cpu" \
			GEM5_CONFIG="$(DASICS_CONFIG_DIR)/riscv_dasics_o3_$$cpu.py" \
			GEM5_OUTDIR="$(DASICS_OUT_DIR)/$$cpu" \
			run; \
		dasics_rc=$$?; \
		raw_rc=; cycles=N/A; extra=; \
		if [ -f "$$result_file" ]; then \
			read -r raw_rc cycles extra < "$$result_file" || true; \
		fi; \
		if ! [[ "$$raw_rc" =~ ^[0-9]+$$ && -z "$$extra" && \
			( "$$cycles" = N/A || "$$cycles" =~ ^[0-9]+$$ ) ]]; then \
			raw_rc=; cycles=N/A; \
		fi; \
		if [ "$$dasics_rc" -eq 0 ] && [ "$$raw_rc" = 0 ]; then \
			dasics_result=OK; \
		elif [ "$$raw_rc" = 124 ]; then \
			dasics_result=TIMEOUT; cycles=N/A; status=1; \
		else \
			dasics_result=FAIL; cycles=N/A; status=1; \
		fi; \
		results+=("$$cpu $$dasics_result $$cycles"); \
	done; \
	printf '\nTest summary: %s\n' "$(TEST)"; \
	printf '%-14s %-9s %12s\n' CPU Result Cycles; \
	for result in "$${results[@]}"; do \
		read -r cpu dasics_result cycles <<< "$$result"; \
		printf '%-14s %-9s %12s\n' "$$cpu" "$$dasics_result" "$$cycles"; \
	done; \
	if [ "$$status" -eq 0 ]; then \
		printf '\033[1;32m[OK] %s\033[0m\n' "$(TEST)"; \
	else \
		printf '\033[1;31m[FAIL] %s\033[0m\n' "$(TEST)" >&2; \
	fi; \
	exit "$$status"

dasics-clean: dasics-check
	@$(MAKE) --no-print-directory \
		-C "$(DASICS_TEST_DIR)/src" clean

# Both actions require an existing test before invoking its Makefile.
dasics-check:
	@test -n "$(TEST)" || { \
		printf '\033[1;31m[FAIL] Set TEST=<test-name>.\033[0m\n' >&2; \
		exit 2; \
	}
	@test -f \
		"$(DASICS_TEST_DIR)/src/Makefile" || { \
		printf '\033[1;31m[FAIL] Unknown DASICS test: %s\033[0m\n' \
			"$(TEST)" >&2; exit 2; \
	}

dasics-cpu-check:
	@case "$(CPU)" in \
		V2_minimal|V2_nanhug|V2_default|v5_full|v5_stress|all) ;; \
		*) printf '\033[1;31m[FAIL] Unknown CPU: %s\033[0m\n' \
			"$(CPU)" >&2; \
			printf 'Choose CPU=%s or all.\n' "$(DASICS_CPUS)" >&2; \
			exit 2 ;; \
	esac

spec06-test: override GEM5_BINARY := \
	$(GEM5_REPO_DIR)/build/RISCV_DASICS/gem5.opt
spec06-test: export SPEC06_INPUT = $(input)
spec06-test: export SPEC06_CONFIG_NAMES = $(config)
spec06-test: spec06-check
	@case "$$SPEC06_INPUT" in \
		test|train|ref) ;; \
		*) printf '\033[1;31m[FAIL] Set input=test, train or ref.\033[0m\n' \
			>&2; exit 2 ;; \
	esac
	@read -r -a configs <<< "$$SPEC06_CONFIG_NAMES"; \
		if [ "$${#configs[@]}" -eq 0 ] || \
			[[ "$$SPEC06_CONFIG_NAMES" = *$$'\n'* ]]; then \
			printf '\033[1;31m[FAIL] Set config="<filename.py> ..." or all.\033[0m\n' \
				>&2; exit 2; \
		fi; \
		if [ "$${#configs[@]}" -eq 1 ] && [ "$${configs[0]}" = all ]; then \
			read -r -a configs <<< "$(SPEC06_CONFIGS)"; \
		fi; \
		for config_name in "$${configs[@]}"; do \
			if ! [[ " $(SPEC06_CONFIGS) " = *" $$config_name "* ]]; then \
				printf '\033[1;31m[FAIL] Unknown SPEC CPU2006 config: %s\033[0m\n' \
					"$$config_name" >&2; exit 2; \
			fi; \
			test -f "$(SPEC06_CONFIG_DIR)/$$config_name" || { \
				printf '\033[1;31m[FAIL] Missing SPEC CPU2006 config: %s\033[0m\n' \
					"$$config_name" >&2; exit 2; \
			}; \
		done; \
		status=0; smoke=0; first=1; results=(); \
		for config_name in "$${configs[@]}"; do \
			if [ "$$first" -eq 0 ]; then \
				printf '%s\n' '-------------------------------'; \
			fi; \
			first=0; \
			printf 'Config: %s\n' "$$config_name"; \
			outdir="$(SPEC06_OUT_DIR)/$${config_name%.py}/$(input)"; \
			rm -f "$$outdir/run-result.txt" "$$outdir/result.json" || exit; \
			$(MAKE) --no-print-directory -j "$(JOBS)" \
				-C "$(SPEC06_TEST_DIR)" JOBS="$(JOBS)" \
				input="$(input)" config="$$config_name" \
				GEM5_BINARY="$(GEM5_BINARY)" \
				GEM5_CONFIG="$(SPEC06_CONFIG_DIR)/$$config_name" \
				GEM5_OUTDIR="$$outdir" gem5-test; \
			make_rc=$$?; raw_rc=; cycles=N/A; extra=; \
			if [ -f "$$outdir/run-result.txt" ]; then \
				read -r raw_rc cycles extra < "$$outdir/run-result.txt" || true; \
			fi; \
			json_result=$$(/usr/bin/python3 -c \
				'import json, sys; r=json.load(open(sys.argv[1])); print(r["status"], r["returncode"])' \
				"$$outdir/result.json" 2>/dev/null) || json_result=; \
			read -r result json_rc json_extra <<< "$$json_result"; \
			if ! [[ "$$raw_rc" =~ ^[0-9]+$$ && -z "$$extra" && \
				"$$json_rc" = "$$raw_rc" && -z "$$json_extra" && \
				( "$$cycles" = N/A || "$$cycles" =~ ^[0-9]+$$ ) ]]; then \
				result=FAIL; raw_rc=$$make_rc; cycles=N/A; \
			fi; \
			case "$$result:$$raw_rc:$$make_rc" in \
				OK:0:0) ;; \
				SMOKE:0:0) cycles=N/A; smoke=1 ;; \
				TIMEOUT:124:*) cycles=N/A; status=1 ;; \
				UNSUPPORTED:77:*) cycles=N/A; status=1 ;; \
				*) result=FAIL; cycles=N/A; status=1; \
					if [ "$$raw_rc" = 0 ]; then \
						raw_rc=$$make_rc; \
						if [ "$$raw_rc" = 0 ]; then raw_rc=1; fi; \
					fi ;; \
			esac; \
			results+=("$$config_name $$result $$raw_rc $$cycles"); \
		done; \
		printf '\nTest summary: %s (%s)\n' "$(TEST)" "$(input)"; \
		printf '%-27s %-12s %9s %14s\n' Configuration Result 'Exit code' Cycles; \
		for row in "$${results[@]}"; do \
			read -r config_name result raw_rc cycles <<< "$$row"; \
			printf '%-27s %-12s %9s %14s\n' \
				"$$config_name" "$$result" "$$raw_rc" "$$cycles"; \
		done; \
		if [ "$$status" -ne 0 ]; then \
			printf '\033[1;31m[FAIL] %s\033[0m\n' "$(TEST)" >&2; \
		elif [ "$$smoke" -ne 0 ]; then \
			printf '\033[1;33m[SMOKE] %s\033[0m\n' "$(TEST)"; \
		else \
			printf '\033[1;32m[OK] %s\033[0m\n' "$(TEST)"; \
		fi; \
		exit "$$status"

spec06-clean: spec06-check
	@$(MAKE) --no-print-directory -C "$(SPEC06_TEST_DIR)" clean

spec06-check: export SPEC06_TEST_NAME = $(TEST)
spec06-check:
	@[[ "$$SPEC06_TEST_NAME" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$$ ]] || { \
		printf '\033[1;31m[FAIL] Set TEST=<test-name> without path components.\033[0m\n' \
			>&2; exit 2; \
	}
	@test -f "$(SPEC06_TEST_DIR)/Makefile" || { \
		printf '\033[1;31m[FAIL] Unknown SPEC CPU2006 test: %s\033[0m\n' \
			"$$SPEC06_TEST_NAME" >&2; exit 2; \
	}
