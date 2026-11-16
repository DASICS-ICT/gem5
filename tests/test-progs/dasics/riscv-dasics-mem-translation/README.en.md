# riscv-dasics-mem-translation

[中文版](README.md) | [Reproduction](../../../../docs/dasics.en.md#riscv-dasics-mem-translation)

## Scope

Check 32 U/S-mode `ld/sd/fld/fsd` combinations on a single-hart RV64 MSU
O3 platform: each source mode and operation combine valid/invalid leaf PTEs and
allowed/denied DASICS access. The test requires the DASICS build
(`USE_DASICS=y`), enables data protection for the case's source mode, and
initializes FReason to sentinel `5`.

Bare-metal means that the program uses no operating system. Bare is an
address-translation mode without paging. This bare-metal test instead uses
Sv39 paging with `satp.MODE=8`.

These 32 combinations are covered, without cross-page accesses, exception
delegation, or precise translation wait timing.

## Mapping and execution

Three-level tables use 4 KiB pages: `root_table[1]` points to `level1_table`,
and `level1_table[0]` points to `level0_table`. Intermediate levels and the
code leaf remain valid. All 32 data PTEs use the same physical-page PPN,
with leaf flags selected per case. Each case rewrites its code and data
leaves. Code and valid data leaves set U for U-mode cases and clear it for
S-mode cases; invalid data leaves have zero flags.

| Purpose | Virtual page | Leaf index | PTE PPN source | Leaf flags |
| --- | --- | --- | --- | --- |
| Code | `0x40000000` | `0` | `probe_code_page` | V/R/X/A/D, U selected by source mode |
| Case 1 | `0x40001000` | `1` | `test_data_page` | V/U/R/W/A/D |
| Case 2 | `0x40002000` | `2` | `test_data_page` | V/U/R/W/A/D |
| Case 3 | `0x40003000` | `3` | `test_data_page` | `0`, invalid V |
| Case 4 | `0x40004000` | `4` | `test_data_page` | `0`, invalid V |
| Case 5 | `0x40005000` | `5` | `test_data_page` | V/U/R/W/A/D |
| Case 6 | `0x40006000` | `6` | `test_data_page` | V/U/R/W/A/D |
| Case 7 | `0x40007000` | `7` | `test_data_page` | `0`, invalid V |
| Case 8 | `0x40008000` | `8` | `test_data_page` | `0`, invalid V |
| Case 9 | `0x40009000` | `9` | `test_data_page` | V/U/R/W/A/D |
| Case 10 | `0x4000A000` | `10` | `test_data_page` | V/U/R/W/A/D |
| Case 11 | `0x4000B000` | `11` | `test_data_page` | `0`, invalid V |
| Case 12 | `0x4000C000` | `12` | `test_data_page` | `0`, invalid V |
| Case 13 | `0x4000D000` | `13` | `test_data_page` | V/U/R/W/A/D |
| Case 14 | `0x4000E000` | `14` | `test_data_page` | V/U/R/W/A/D |
| Case 15 | `0x4000F000` | `15` | `test_data_page` | `0`, invalid V |
| Case 16 | `0x40010000` | `16` | `test_data_page` | `0`, invalid V |
| Case 17 | `0x40011000` | `17` | `test_data_page` | V/R/W/A/D |
| Case 18 | `0x40012000` | `18` | `test_data_page` | V/R/W/A/D |
| Case 19 | `0x40013000` | `19` | `test_data_page` | `0`, invalid V |
| Case 20 | `0x40014000` | `20` | `test_data_page` | `0`, invalid V |
| Case 21 | `0x40015000` | `21` | `test_data_page` | V/R/W/A/D |
| Case 22 | `0x40016000` | `22` | `test_data_page` | V/R/W/A/D |
| Case 23 | `0x40017000` | `23` | `test_data_page` | `0`, invalid V |
| Case 24 | `0x40018000` | `24` | `test_data_page` | `0`, invalid V |
| Case 25 | `0x40019000` | `25` | `test_data_page` | V/R/W/A/D |
| Case 26 | `0x4001A000` | `26` | `test_data_page` | V/R/W/A/D |
| Case 27 | `0x4001B000` | `27` | `test_data_page` | `0`, invalid V |
| Case 28 | `0x4001C000` | `28` | `test_data_page` | `0`, invalid V |
| Case 29 | `0x4001D000` | `29` | `test_data_page` | V/R/W/A/D |
| Case 30 | `0x4001E000` | `30` | `test_data_page` | V/R/W/A/D |
| Case 31 | `0x4001F000` | `31` | `test_data_page` | `0`, invalid V |
| Case 32 | `0x40020000` | `32` | `test_data_page` | `0`, invalid V |

Physical addresses come from ELF symbols and differ from their virtual
addresses. Entries with V=`0` do not form valid mappings. M mode permits
code, data, and page-table accesses through PMP and disables interrupts and
delegation. Each case clears MPRV/SUM/MXR, initializes physical data,
configures its PTE and DASICS CSRs, executes `fence rw,rw`, sets SATP,
executes `sfence.vma`, then selects the source-mode MPP and enters the probe
through MRET.

U-mode MainCfg=`0x26` enables UENA and closes ECALL/control-flow checks
through CUET/CUFT. CULT/CUST remain zero, enabling read/write checks.
S-mode MainCfg=`0x241` enables SENA and closes ECALL/control-flow checks
through CSET/CSFT, with CSLT/CSST remaining zero. Empty U/S MainBounds make
the probe PC untrusted. Slot 0 spans the case's data
interval `[VA, VA+8)`; LibCfg=`0xA` allows reads, `0x9` allows writes, and
`0x8` denies the corresponding operation, with all other slots invalid.

Each case has a separate probe and ECALL label: cases 1–4 use
`ld a0,0(a1)`, cases 5–8 use `sd a2,0(a1)`, cases 9–12 use
`fld fa0,0(a1)`, and cases 13–16 use `fsd fa2,0(a1)`.
Cases 1–4 use, in order,
`u_ld_mapped_allow`, `u_ld_mapped_deny`, `u_ld_page_fault_allow`, and
`u_ld_page_fault_deny`. Cases 5–8 use `u_sd_mapped_allow`, `u_sd_mapped_deny`,
`u_sd_page_fault_allow`, and `u_sd_page_fault_deny`. Floating-point probes
use the same suffixes with `u_fld_*` and `u_fsd_*` labels. Cases 17–20,
21–24, 25–28, and 29–32 cover S-mode `ld/sd/fld/fsd`, using the same
suffixes with `s_ld_*`, `s_sd_*`, `s_fld_*`, and `s_fsd_*` labels.
Each group of four is ordered as valid/allowed, valid/denied,
invalid/allowed, and invalid/denied. A completed access sets the marker and
executes ECALL.
Faults enter M without reaching the marker or ECALL. After checking a case,
M starts the next one directly, without resuming U/S instructions after a
fault.

## Check contract

The data value is `LOAD_VALUE=0x1122334455667788`. Each case starts with
`a0=GPR_SENTINEL=0xA5A5A5A5A5A5A5A5` and completion marker `s1=0`.
The store source `a2=STORE_VALUE=0x0807060504030201` remains unchanged
during probe execution and trap-state checks.
Each case also initializes `fa0=FPR_SENTINEL=0x8877665544332211`,
`fa2=STORE_VALUE`, and FS=`Clean (2)`. Only successful `fld` cases 9 and 25 set
`fa0=LOAD_VALUE` and FS=`Dirty (3)`. All other cases retain the `fa0`
sentinel and Clean state; `fa2` remains unchanged in every case.
The M handler reads FS before any FP-check instruction. The subsequent
`fmv.x.d` checks themselves set Dirty, so FS above describes the trap-entry
state.

| Case | Valid leaf | DASICS access | Final cause | FReason | `a0` |
| --- | --- | --- | --- | --- | --- |
| 1 | Yes | Read allowed | `8`, ECALL after a completed load | `5` | `LOAD_VALUE` |
| 2 | Yes | Read denied | `24`, U DASICS fault | `2` | `GPR_SENTINEL` |
| 3 | No | Read allowed | `13`, load page fault | `5` | `GPR_SENTINEL` |
| 4 | No | Read denied | `13`, load page fault takes priority | `5` | `GPR_SENTINEL` |
| 5 | Yes | Write allowed | `8`, ECALL after a completed store | `5` | `GPR_SENTINEL` |
| 6 | Yes | Write denied | `24`, U DASICS fault | `3` | `GPR_SENTINEL` |
| 7 | No | Write allowed | `15`, store page fault | `5` | `GPR_SENTINEL` |
| 8 | No | Write denied | `15`, store page fault takes priority | `5` | `GPR_SENTINEL` |
| 9 | Yes | Read allowed | `8`, ECALL after a completed FP load | `5` | `GPR_SENTINEL` |
| 10 | Yes | Read denied | `24`, U DASICS fault | `2` | `GPR_SENTINEL` |
| 11 | No | Read allowed | `13`, load page fault | `5` | `GPR_SENTINEL` |
| 12 | No | Read denied | `13`, load page fault takes priority | `5` | `GPR_SENTINEL` |
| 13 | Yes | Write allowed | `8`, ECALL after a completed FP store | `5` | `GPR_SENTINEL` |
| 14 | Yes | Write denied | `24`, U DASICS fault | `3` | `GPR_SENTINEL` |
| 15 | No | Write allowed | `15`, store page fault | `5` | `GPR_SENTINEL` |
| 16 | No | Write denied | `15`, store page fault takes priority | `5` | `GPR_SENTINEL` |
| 17 | Yes | Read allowed | `9`, ECALL after a completed load | `5` | `LOAD_VALUE` |
| 18 | Yes | Read denied | `25`, S DASICS fault | `2` | `GPR_SENTINEL` |
| 19 | No | Read allowed | `13`, load page fault | `5` | `GPR_SENTINEL` |
| 20 | No | Read denied | `13`, load page fault takes priority | `5` | `GPR_SENTINEL` |
| 21 | Yes | Write allowed | `9`, ECALL after a completed store | `5` | `GPR_SENTINEL` |
| 22 | Yes | Write denied | `25`, S DASICS fault | `3` | `GPR_SENTINEL` |
| 23 | No | Write allowed | `15`, store page fault | `5` | `GPR_SENTINEL` |
| 24 | No | Write denied | `15`, store page fault takes priority | `5` | `GPR_SENTINEL` |
| 25 | Yes | Read allowed | `9`, ECALL after a completed FP load | `5` | `GPR_SENTINEL` |
| 26 | Yes | Read denied | `25`, S DASICS fault | `2` | `GPR_SENTINEL` |
| 27 | No | Read allowed | `13`, load page fault | `5` | `GPR_SENTINEL` |
| 28 | No | Read denied | `13`, load page fault takes priority | `5` | `GPR_SENTINEL` |
| 29 | Yes | Write allowed | `9`, ECALL after a completed FP store | `5` | `GPR_SENTINEL` |
| 30 | Yes | Write denied | `25`, S DASICS fault | `3` | `GPR_SENTINEL` |
| 31 | No | Write allowed | `15`, store page fault | `5` | `GPR_SENTINEL` |
| 32 | No | Write denied | `15`, store page fault takes priority | `5` | `GPR_SENTINEL` |

- MainCfg/LibCfg readback must match the configuration. SATP must match
  after setup and remain unchanged on M-mode trap entry.
- All traps enter M with MPP matching the source mode (U=`0`, S=`1`).
  Normal completion uses the case's virtual
  ECALL PC and TVAL=`0`; faults use its virtual memory-instruction PC and
  data VA in TVAL.
  Virtual PCs are computed as `0x40000000 + (label - probe_code_page)`.
- The completion marker is `1` normally and `0` on faults. With MPRV=`0`,
  the M handler checks the physical data: only successful store cases 5,
  13, 21, and 29 write `STORE_VALUE`; all other cases retain `LOAD_VALUE`.
  Semihosting exits with status `0` only after all 32 cases finish checking.

After execution, also inspect paging statistics in that run's `stats.txt`:

| Statistic | Expected value |
| --- | --- |
| DTLB `readMisses` | At least `16` |
| DTLB `writeMisses` | At least `16` |
| DTLB walker `num_4kb_walks` | At least `16` |

`num_4kb_walks` counts only walks that successfully reach valid 4 KiB
leaves. Cases 1, 2, 5, 6, 9, 10, 13, 14, 17, 18, 21, 22, 25, 26, 29,
and 30 are expected to contribute;
invalid-leaf page faults in the other cases do not increment it. Statistics
are auxiliary checks, not assembly assertions. Exact wait timing requires
separate correlation of traces by PC, VA, and seqNum.

## Software build

From the repository root:

```bash
make -C tests/test-progs/dasics/riscv-dasics-mem-translation/src
```

The software uses `-march=rv64imafdc_zicsr -mabi=lp64`.

The executable is this test directory's
`build/riscv-dasics-mem-translation.elf`; simulation output is under
`build/m5out-o3/<CPU>/`. Run commands are in the
[usage guide](../../../../docs/dasics.en.md#riscv-dasics-mem-translation).

## Diagnostics

Failures print `DASICS translation: case=NN reason=NN` through Semihosting.
`case=01..32` identifies the combination, with `00` for initialization.
The exit status is `reason=01..12`, rather than the case ID. Status `124`
remains reserved for the host timeout.

| Failure code | Failed check |
| --- | --- |
| `1` | MainCfg/LibCfg readback differs from the configuration |
| `2` | SATP setup or preservation after the trap |
| `3` | Cause differs from the case expectation |
| `4` | MPP differs from the case's expected U/S source mode |
| `5` | EPC differs from the case's virtual memory-instruction or ECALL PC |
| `6` | TVAL differs from the case expectation |
| `7` | Completion marker differs from the case expectation |
| `8` | `a0` or store source `a2` differs from the case expectation |
| `9` | Physical target's eight bytes differ from the case expectation |
| `10` | FReason differs from the case expectation |
| `11` | `fa0` or store source `fa2` differs from the case expectation |
| `12` | FS differs from the case expectation |
