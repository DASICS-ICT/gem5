# riscv-dasics-control-flow

[中文版](README.md) | [Reproduction](../../../../docs/dasics.en.md#riscv-dasics-control-flow)

## Scope

Test DASICS target checks for RV64 non-virtualized U/S `JALR` and `BEQ`,
delegation to M/S handlers, and exception return. The configuration uses one
O3 hart, bare-metal full-system simulation, Bare address translation, and
Semihosting. Other conditional branches, compressed instructions, and O3
wrong-path execution are outside this test's coverage.

| Case | Probe | Source | DASICS handler mode | Target authorization | Branch outcome |
| --- | --- | --- | --- | --- | --- |
| 1 | JALR | U | M | Allow | — |
| 2 | JALR | U | M | Deny | — |
| 3 | JALR | U | S | Allow | — |
| 4 | JALR | U | S | Deny | — |
| 5 | JALR | S | M | Allow | — |
| 6 | JALR | S | M | Deny | — |
| 7 | JALR | S | S | Allow | — |
| 8 | JALR | S | S | Deny | — |
| 9 | BEQ | U | M | Deny | Not taken |
| 10 | BEQ | U | M | Deny | Taken |
| 11 | BEQ | U | S | Deny | Not taken |
| 12 | BEQ | U | S | Deny | Taken |
| 13 | BEQ | S | M | Deny | Not taken |
| 14 | BEQ | S | M | Deny | Taken |
| 15 | BEQ | S | S | Deny | Not taken |
| 16 | BEQ | S | S | Deny | Taken |

Allowed JALR and not-taken BEQ cases execute the marker code without a DASICS
trap, then use an ordinary ECALL to return to M. Denied JALR and taken BEQ
cases enter the configured M/S handler, resume at an explicit label through
MRET/SRET, and then use an ordinary ECALL to return to M.
Exit status `0` requires all sixteen cases to complete.

## Configuration and layout

- M mode disables interrupts and sets direct MTVEC/STVEC, Bare translation,
  and a PMP TOR region `[0, 0x90000000)` with read/write/execute permissions.
- MainCfg=`0x1DF`: UENA/SENA are set and CUFT/CSFT are clear. U/S ECALL and
  ordinary load/store checks are disabled to isolate control-flow checks.
- UMainBound is `[0, 0)`. SMainBound covers
  `[supervisor_trusted_begin, supervisor_trusted_end)`, including the entire
  S handler. Probe, target, and resume code lie outside that trusted range.
- JumpBound0 is `[target_entry, target_end)`. JumpCfg is `1` for allowed
  JALR cases and `0` for every other case. The other three groups are invalid;
  all three special target addresses are zero.
- Each case writes exactly `0`, `1<<24`, or `1<<25` to MEDELEG and checks
  readback. ECALL delegation bits remain clear.

The first eight cases share `jalr ra, a1, 0` at `jump_probe`. Its input is
`a1=target_entry|1`; the resolved target and fault TVAL must be `target_entry`.
All instructions use uncompressed encodings. `jump_link` is the address
immediately after the probe. The harness uses no `call/ret`, preserving
`ra` for checks in the handlers and after exception return.

The final eight cases share `beq s4, zero, target_entry` at `beq_probe`.
`target_entry` immediately follows at `beq_probe+4`: the fall-through address
and taken target are identical and unauthorized. With `s4=1`, the branch is
not taken and must not trigger a DASICS target check. With `s4=0`, it is taken
and must trap. This tests the actual branch outcome even when the next
instruction address is unchanged. BEQ and JALR share target code, markers,
and `target_ecall`. A NOP before the probe keeps `target_entry` eight-byte
aligned.

## Checks

JALR checks:

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

BEQ checks:

| State | Not taken | Taken |
| --- | --- | --- |
| First exception | ECALL: U=`8`, S=`9`, handled in M | DASICS: U=`24`, S=`25`, handled in the configured M/S mode |
| First EPC | `target_ecall` | `beq_probe` |
| DASICS TVAL | Not applicable | `target_entry` |
| FReason | Sentinel `5` remains | Becomes `4`; the subsequent ordinary ECALL preserves it |
| `ra` | Sentinel `0xA5A5A5A5A5A5A5A5` remains | Sentinel `0xA5A5A5A5A5A5A5A5` remains |
| Target GPR and memory markers | Both `0x1234` | Both remain zero |
| Resume marker | Remains zero | Becomes `0x5678` after returning to `resume_entry` |
| DASICS trap count | Zero | Exactly one |

The M handler checks MPP and the S handler checks SPP against the source
privilege. Paths that take a DASICS trap set MEPC/SEPC to `resume_entry`;
the subsequent ECALL must originate at `resume_ecall` in the original privilege
mode.
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

Nonzero status is `case_id * 15 + reason`. Case IDs `1..16` identify the rows
above; case ID `0` identifies initialization. Reasons remain `1..12`, so the
maximum status is `252`, within the eight-bit process exit status.

| Reason | Failed check |
| --- | --- |
| 1 | MEDELEG readback |
| 2 | MPP/SPP source privilege |
| 3 | M/S exception route |
| 4 | Stage, expected presence of a DASICS trap, or trap count |
| 5 | Cause |
| 6 | EPC |
| 7 | TVAL |
| 8 | FReason |
| 9 | Link/`ra` |
| 10 | Target GPR marker |
| 11 | Target memory marker |
| 12 | Resume marker |

Each case-table entry is 32 bytes with four 64-bit fields: source, delegation,
completion-without-DASICS flag, and probe kind (`0` for JALR, `1` for BEQ).

`s0` holds the case pointer; `s1` the case ID; `s2/s3` the source and delegation.
`s4` indicates completion without a DASICS trap: `1` for allowed JALR or
not-taken BEQ, `0` for denied JALR or taken BEQ. `s5` is the stage (`0` setup,
`1` probe, `2` resume), and `s6` counts accepted DASICS traps. `s7/s8` hold
target/resume markers; `s9` points to the memory marker. `s10` holds the probe
kind, `s11` the probe PC, and `a3` the expected `ra` after a successful probe
(the JALR link or BEQ sentinel). M mode sets these expectations, and the
handlers preserve them.
`a2` carries the failure reason and final exit status.
