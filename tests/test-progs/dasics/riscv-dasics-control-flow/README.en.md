# riscv-dasics-control-flow

[中文版](README.md) | [Reproduction](../../../../docs/dasics.en.md#riscv-dasics-control-flow)

## Scope

Test DASICS target checks for 13 RV64 non-virtualized U/S ordinary and
compressed jump/conditional-branch types, delegation to M/S handlers, and
exception return.
The configuration uses one O3 hart, bare-metal full-system simulation, Bare
address translation, and Semihosting. Exit status `0` requires all 120 cases
to complete. O3 wrong-path tests are deferred. RV32 C.JAL, Zcmp/Zcmt, and
xRET are not instructions under test here.

A normal case allows an unconditional jump target or does not take the
conditional branch. It executes the marker code and returns to M through an
ordinary ECALL.
An exceptional case denies an unconditional jump target or takes a conditional
branch to an unauthorized target. It enters the configured M/S handler,
returns to an explicit resume label through MRET/SRET, then uses an ordinary
ECALL to return to M.

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

The following eight-case groups use the same route order. Unconditional
jumps test allowed/denied targets; compressed conditional branches test
not-taken/taken outcomes. Existing case IDs 1–88 are unchanged.

| Cases | Probe | Normal case | Exceptional case |
| --- | --- | --- | --- |
| 73–80 | JAL | Allowed target | Denied target |
| 81–88 | C.JALR | Allowed target | Denied target |
| 89–96 | C.J | Allowed target | Denied target |
| 97–104 | C.JR | Allowed target | Denied target |
| 105–112 | C.BEQZ | `a4=1`, not taken | `a4=0`, taken |
| 113–120 | C.BNEZ | `a4=0`, not taken | `a4=1`, taken |

Compressed conditional branches use only `a4`. Their case-table `rs2` field
is zero and is not consumed by the comparison.

## Configuration and layout

- M mode disables interrupts and sets direct MTVEC/STVEC, Bare translation,
  and a PMP TOR region `[0, 0x90000000)` with read/write/execute permissions.
- MainCfg=`0x1DF`: UENA/SENA are set and CUFT/CSFT are clear. U/S ECALL and
  ordinary load/store checks are disabled to isolate control-flow checks.
- UMainBound is `[0, 0)`. SMainBound covers
  `[supervisor_trusted_begin, supervisor_trusted_end)`, including the entire
  S handler. Probe, target, and resume code lie outside that trusted range.
- JumpBound0 uses the current probe description's `[target, end)`. Only
  allowed unconditional jumps set JumpCfg=`1`; every other case sets it
  to `0`.
  The other three groups are invalid, and all three special targets are zero.
- Each case writes exactly `0`, `1<<24`, or `1<<25` to MEDELEG and checks
  readback. ECALL delegation bits remain clear.

JALR cases share `jalr ra, a1, 0` at `jump_probe`, with
`a1=beq_target|1`. The resolved target and fault TVAL must be `beq_target`.
`jump_link` immediately follows the probe. Unconditional jumps and BEQ
share `beq_target`, marker code, `beq_ecall`, and `beq_end`.

JAL uses `jal ra, beq_target` at `jal_probe`, forming its target from the PC
plus an immediate. An allowed transfer sets `ra=jal_link=jal_probe+4`.
A denied transfer has EPC=`jal_probe` and TVAL=`beq_target`, preserving the
`ra` sentinel. ECALL/EBREAK at the link address prevent unintended
fall-through from being accepted as success.

C.JALR uses an explicit `c.jalr a1` at `cjalr_probe`, with
`a1=beq_target|1`, resolving to `beq_target`. An allowed transfer sets
`ra=cjalr_link=cjalr_probe+2`. A denied transfer has EPC=`cjalr_probe` and
TVAL=`beq_target`, preserving the `ra` sentinel and using the same recovery
checks. A two-byte C.NOP after an eight-byte boundary places the probe PC
two bytes beyond a four-byte boundary, with `cjalr_link` four-byte aligned.
MRET enters the probe directly without executing the padding. ECALL/EBREAK
at the link address remain uncompressed to reject unintended fall-through.

C.J uses an explicit `c.j beq_target`, forming its target from the PC plus
an immediate. C.JR uses `c.jr a1` with `a1=beq_target|1` and clears bit zero
of the resolved target. Neither instruction writes `ra`, whether allowed
or denied; both check that its sentinel remains. Each has a two-byte C.NOP
after an eight-byte boundary, followed by its two-byte probe. MRET enters
the halfword-aligned probe directly. Noncompressed ECALL/EBREAK guards at
`cj_fallthrough` and `cjr_fallthrough` reject unintended fall-through.

`BRANCH_PROBE` generates a separate `name_probe`, `name_target`, marker code,
and `name_ecall` for each ordinary conditional branch. Probes use `a4/a5` as
`rs1/rs2`; each target is `name_target=name_probe+4` and eight-byte aligned.
`CBRANCH_PROBE` generates the two compressed branch layouts: an eight-byte
boundary followed by a four-byte NOP, a two-byte C.NOP, and a two-byte branch.
Its target is `name_probe+2`, eight-byte aligned; marker code and ECALL
remain 32-bit instructions.
All conditional-branch targets are unauthorized. Their fall-through address
and taken target are identical: a not-taken branch must not trigger a DASICS
target check, while a taken branch must trap. This tests the actual branch
outcome even when the next instruction address is unchanged.
Local `.option push/rvc/pop` encloses only compressed probes and their C.NOP
padding. The remaining harness, ECALL/EBREAK, and Semihosting markers retain
32-bit encodings. C.NOP only controls layout; the harness uses no `call/ret`,
preserving `ra` for checks.

## Checks

| State | Normal completion | DASICS target denial |
| --- | --- | --- |
| First exception | ECALL: U=`8`, S=`9`, handled in M | DASICS: U=`24`, S=`25`, handled in the configured M/S mode |
| First EPC | Current target's ordinary ECALL address, held in `a7` | Current probe PC, held in `s11` |
| DASICS TVAL | Not applicable | Current target address, held in `a6` |
| FReason | Sentinel `5` remains | Becomes `4`; the subsequent ordinary ECALL preserves it |
| `ra` | `jump_link` for JALR, `jal_link` for JAL, `cjalr_link` for C.JALR; sentinel `0xA5A5A5A5A5A5A5A5` for C.J/C.JR and conditional branches | Sentinel `0xA5A5A5A5A5A5A5A5` remains |
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
is stored under this test's `build/m5out-o3/<CPU>/`. Use an existing DASICS
gem5 binary with control-flow checks; changes confined to this test require
rebuilding only its ELF, rather than gem5.

## Diagnostics

Failures print this message to standard output through Semihosting
`SYS_WRITE0`:

```text
DASICS control-flow: case=NNN reason=NN
```

`case=001..120` identifies the scenarios above, and the failure exit status
is the case ID. Initialization failures print `case=000` and exit with `255`;
success exits with `0`. The message reports `reason=01..12` separately rather
than encoding it in the exit status.

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
Probe kinds `0..12` identify JALR, BEQ, BNE, BLT, BGE, BLTU, BGEU, JAL,
and C.JALR, followed by C.J, C.JR, C.BEQZ, and C.BNEZ (kinds `9..12`).
A separate probe-description table has thirteen entries, each 40 bytes with
five fields:
PC, target, target end, ordinary ECALL address, and normal-completion `ra`.
M mode reads these expectations by probe kind; shared handlers preserve and
check them.

`s0` holds the case pointer; `s1` the case ID; `s2/s3` the source and delegation.
`s4` indicates completion without a DASICS trap: `1` for an allowed
unconditional jump or a not-taken conditional branch, `0` for a denied
unconditional jump or a taken conditional branch. `s5` is the stage
(`0` setup, `1` probe, `2` resume), and `s6` counts accepted DASICS traps.
`s7/s8` hold target/resume markers; `s9` points to the memory marker.
`s10` holds the probe kind, and `s11` holds the probe PC. `a3` holds the
normal-completion `ra`; `a4/a5` hold the comparison inputs (compressed
branches use only `a4`); `a6` holds the fault target; and `a7` holds the
ordinary ECALL PC. `a2` holds the failure reason, then becomes the final exit
status after printing.
