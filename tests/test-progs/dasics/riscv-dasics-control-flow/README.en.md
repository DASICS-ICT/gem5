# riscv-dasics-control-flow

[中文版](README.md) | [Reproduction](../../../../docs/dasics.en.md#riscv-dasics-control-flow)

## Scope

Test DASICS target checks for RV64 non-virtualized U/S `JALR`, `JAL`, and
`BEQ/BNE/BLT/BGE/BLTU/BGEU`, delegation to M/S handlers, and exception return.
The configuration uses one O3 hart, bare-metal full-system simulation, Bare
address translation, and Semihosting. Exit status `0` requires all 80 cases
to complete. Compressed instructions and O3 wrong-path execution are
outside this test's coverage.

A normal case allows the JALR/JAL target or does not take the conditional
branch.
It executes the marker code and returns to M through an ordinary ECALL.
An exceptional case denies the JALR/JAL target or takes a conditional branch
to an unauthorized target. It enters the configured M/S handler, returns to an
explicit resume label through MRET/SRET, then uses an ordinary ECALL to
return to M.

| Cases | Probe | Normal `(rs1, rs2)` | Exceptional `(rs1, rs2)` |
| --- | --- | --- | --- |
| 1–8 | JALR | Allowed target | Denied target |
| 9–16 | BEQ | `(1, 0)` | `(0, 0)` |
| 17–24 | BNE | `(1, 1)` | `(1, 0)` |
| 25–32 | BLT | `(1, -1)` | `(-1, 1)` |
| 33–40 | BGE | `(-1, 1)` | `(1, -1)` |
| 41–48 | BLTU | `(-1, 1)` | `(1, -1)` |
| 49–56 | BGEU | `(1, -1)` | `(-1, 1)` |

Each group of eight uses this order: U→M normal/exceptional, U→S
normal/exceptional, S→M normal/exceptional, S→S normal/exceptional.
The arrow identifies the source mode and DASICS handler mode; ordinary
ECALLs in normal cases always enter M. JALR cases 1–8 and BEQ cases 9–16
retain their original scenario order. `-1` is all ones at XLEN=64,
distinguishing signed from unsigned comparisons.

Equality boundaries use four groups, each ordered U→M, U→S, S→M, S→S:

| Cases | Probe | `(rs1, rs2)` | Branch outcome | DASICS trap |
| --- | --- | --- | --- | --- |
| 57–60 | BLT | `(1, 1)` | Not taken | No |
| 61–64 | BGE | `(1, 1)` | Taken | Yes |
| 65–68 | BLTU | `(1, 1)` | Not taken | No |
| 69–72 | BGEU | `(1, 1)` | Taken | Yes |

The final cases 73–80 cover JAL in the eight-case order above, testing
allowed/denied targets for each route. Existing case IDs 1–72 are unchanged.

## Configuration and layout

- M mode disables interrupts and sets direct MTVEC/STVEC, Bare translation,
  and a PMP TOR region `[0, 0x90000000)` with read/write/execute permissions.
- MainCfg=`0x1DF`: UENA/SENA are set and CUFT/CSFT are clear. U/S ECALL and
  ordinary load/store checks are disabled to isolate control-flow checks.
- UMainBound is `[0, 0)`. SMainBound covers
  `[supervisor_trusted_begin, supervisor_trusted_end)`, including the entire
  S handler. Probe, target, and resume code lie outside that trusted range.
- JumpBound0 uses the current probe description's `[target, end)`. Only
  allowed JALR/JAL cases set JumpCfg=`1`; every other case sets it to `0`.
  The other three groups are invalid, and all three special targets are zero.
- Each case writes exactly `0`, `1<<24`, or `1<<25` to MEDELEG and checks
  readback. ECALL delegation bits remain clear.

JALR cases share `jalr ra, a1, 0` at `jump_probe`, with
`a1=beq_target|1`. The resolved target and fault TVAL must be `beq_target`.
`jump_link` immediately follows the probe. JALR, JAL, and BEQ share `beq_target`,
marker code, `beq_ecall`, and `beq_end`.

JAL uses `jal ra, beq_target` at `jal_probe`, forming its target from the PC
plus an immediate. An allowed transfer sets `ra=jal_link=jal_probe+4`.
A denied transfer has EPC=`jal_probe` and TVAL=`beq_target`, preserving the
`ra` sentinel. ECALL/EBREAK at the link address prevent unintended
fall-through from being accepted as success.

`BRANCH_PROBE` generates a separate `name_probe`, `name_target`, marker code,
and `name_ecall` for each conditional branch. Probes use `a4/a5` as
`rs1/rs2`; each target is `name_target=name_probe+4` and eight-byte aligned.
All conditional-branch targets are unauthorized. Their fall-through address
and taken target are identical: a not-taken branch must not trigger a DASICS
target check, while a taken branch must trap. This tests the actual branch
outcome even when the next instruction address is unchanged.
All instructions use uncompressed encodings, and the harness uses no
`call/ret`, preserving `ra` for checks.

## Checks

| State | Normal completion | DASICS target denial |
| --- | --- | --- |
| First exception | ECALL: U=`8`, S=`9`, handled in M | DASICS: U=`24`, S=`25`, handled in the configured M/S mode |
| First EPC | Current target's ordinary ECALL address, held in `a7` | Current probe PC, held in `s11` |
| DASICS TVAL | Not applicable | Current target address, held in `a6` |
| FReason | Sentinel `5` remains | Becomes `4`; the subsequent ordinary ECALL preserves it |
| `ra` | `jump_link` for JALR, `jal_link` for JAL; sentinel `0xA5A5A5A5A5A5A5A5` for conditional branches | Sentinel `0xA5A5A5A5A5A5A5A5` remains |
| Target GPR and memory markers | Both `0x1234` | Both remain zero |
| Resume marker | Remains zero | Becomes `0x5678` after returning to `resume_entry` |
| DASICS trap count | Zero | Exactly one |

The M handler checks MPP and the S handler checks SPP against the source
privilege. Paths that take a DASICS trap set MEPC/SEPC to `resume_entry`;
the subsequent ECALL must originate at `resume_ecall` in the original
privilege mode. S handler failures use `supervisor_failure_ecall` to report
the error in M. The memory marker checks architectural side effects; it does
not establish that target instructions were never fetched or executed
speculatively.

## Software build

From the repository root:

```bash
make -C tests/test-progs/dasics/riscv-dasics-control-flow/src
```

The executable is `build/riscv-dasics-control-flow.elf`. Simulation output
is stored under this test's `build/m5out-o3/<CPU>/`. Rebuild the DASICS gem5
binary with control-flow checks before running the test.

## Diagnostics

Failures print this message to standard output through Semihosting
`SYS_WRITE0`:

```text
DASICS control-flow: case=NN reason=NN
```

`case=01..80` identifies the scenarios above, and the failure exit status
is the case ID. Initialization failures print `case=00` and exit with `255`;
success exits with `0`. The message reports `reason` separately rather than
encoding it in the exit status.

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

Each case-table entry is 48 bytes with six 64-bit fields: source, delegation,
completion-without-DASICS flag, probe kind, `rs1`, and `rs2`.
Probe kinds `0..7` identify JALR, BEQ, BNE, BLT, BGE, BLTU, BGEU, and JAL,
respectively (`PROBE_JAL=7`). A separate probe-description table has eight
entries, each with five fields:
PC, target, target end, ordinary ECALL address, and normal-completion `ra`.
M mode reads these expectations by probe kind; shared handlers preserve and
check them.

`s0` holds the case pointer; `s1` the case ID; `s2/s3` the source and delegation.
`s4` indicates completion without a DASICS trap: `1` for allowed JALR/JAL or a
not-taken conditional branch, `0` for denied JALR/JAL or a taken conditional
branch. `s5` is the stage (`0` setup, `1` probe, `2` resume), and `s6` counts
accepted DASICS traps. `s7/s8` hold target/resume markers; `s9` points to the
memory marker. `s10` holds the probe kind, `s11` the probe PC, `a3` the
normal-completion `ra`, `a4/a5` the comparison inputs, `a6` the fault target,
and `a7` the ordinary ECALL PC. `a2` holds the failure reason, then becomes
the final exit status after printing.
