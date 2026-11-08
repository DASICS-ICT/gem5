# riscv-dasics-control-flow

[中文版](README.md) | [Reproduction](../../../../docs/dasics.en.md#riscv-dasics-control-flow)

## Scope

Test DASICS target checks for RV64 non-virtualized U/S `JALR`, delegation to
M/S handlers, and exception return. The configuration uses one O3 hart,
bare-metal full-system simulation, Bare address translation, and Semihosting.
Conditional branches, compressed instructions, and O3 wrong-path execution
are outside this test's coverage.

| Case | Source | DASICS handler mode | Target authorization |
| --- | --- | --- | --- |
| 1 | U | M | Allow |
| 2 | U | M | Deny |
| 3 | U | S | Allow |
| 4 | U | S | Deny |
| 5 | S | M | Allow |
| 6 | S | M | Deny |
| 7 | S | S | Allow |
| 8 | S | S | Deny |

Allowed transfers reach the target and use an ordinary ECALL to return to M.
Denied transfers enter the configured M/S handler, resume at an explicit
label through MRET/SRET, and then use an ordinary ECALL to return to M.
Exit status `0` requires all eight cases to complete.

## Configuration and layout

- M mode disables interrupts and sets direct MTVEC/STVEC, Bare translation,
  and a PMP TOR region `[0, 0x90000000)` with read/write/execute permissions.
- MainCfg=`0x1DF`: UENA/SENA are set and CUFT/CSFT are clear. U/S ECALL and
  ordinary load/store checks are disabled to isolate control-flow checks.
- UMainBound is `[0, 0)`. SMainBound covers
  `[supervisor_trusted_begin, supervisor_trusted_end)`, including the entire
  S handler. Probe, target, and resume code lie outside that trusted range.
- JumpBound0 is `[target_entry, target_end)`. JumpCfg is `1` for allowed
  targets and `0` for denied targets. The other three groups are invalid;
  all three special target addresses are zero.
- Each case writes exactly `0`, `1<<24`, or `1<<25` to MEDELEG and checks
  readback. ECALL delegation bits remain clear.

All cases share `jalr ra, a1, 0` at `jump_probe`. Its input is
`a1=target_entry|1`; the resolved target and fault TVAL must be `target_entry`.
All instructions use uncompressed encodings. `jump_link` is the address
immediately after the probe. The harness uses no `call/ret`, preserving
`ra` for checks in the handlers and after exception return.

## Checks

| State | Allowed target | Denied target |
| --- | --- | --- |
| First exception | ECALL: U=`8`, S=`9`, handled in M | DASICS: U=`24`, S=`25`, handled in the configured M/S mode |
| First EPC | `target_ecall` | `jump_probe` |
| DASICS TVAL | Not applicable | `target_entry` |
| FReason | Sentinel `5` remains | Becomes `4`; the subsequent ordinary ECALL preserves it |
| `ra` | `jump_link` | Sentinel `0xA5A5A5A5A5A5A5A5` remains |
| Target GPR and memory markers | Both `0x1234` | Both remain zero |
| Resume marker | Remains zero | Becomes `0x5678` after returning to `resume_entry` |
| DASICS trap count | Zero | Exactly one |

The M handler checks MPP and the S handler checks SPP against the source
privilege. Denied transfers set MEPC/SEPC to `resume_entry`; the subsequent
ECALL must originate at `resume_ecall` in the original privilege mode.
S handler failures use `supervisor_failure_ecall` to report the error in M.

The memory marker checks architectural side effects; it does not establish
that target instructions were never fetched or executed speculatively.

## Software build

From the repository root:

```bash
make -C tests/test-progs/dasics/riscv-dasics-control-flow/src
```

The executable is `build/riscv-dasics-control-flow.elf`. Simulation output
is stored under this test's `build/m5out-o3/<CPU>/`. Rebuild the DASICS gem5
binary with control-flow checks before running the test.

## Diagnostics

Nonzero status is `case_id * 16 + reason`. Case IDs `1..8` identify the rows
above; case ID `0` identifies initialization.

| Reason | Failed check |
| --- | --- |
| 1 | MEDELEG readback |
| 2 | MPP/SPP source privilege |
| 3 | M/S exception route |
| 4 | Stage, allow/deny expectation, or trap count |
| 5 | Cause |
| 6 | EPC |
| 7 | TVAL |
| 8 | FReason |
| 9 | Link/`ra` |
| 10 | Target GPR marker |
| 11 | Target memory marker |
| 12 | Resume marker |

`s0` holds the case pointer; `s1` the case ID; `s2/s3/s4` the source,
delegation, and authorization settings. `s5` is the stage (`0` setup,
`1` probe, `2` resume), and `s6` counts accepted DASICS traps. `s7/s8` hold
target/resume markers; `s9` points to the memory marker. `a2` carries the
failure reason and final exit status.
