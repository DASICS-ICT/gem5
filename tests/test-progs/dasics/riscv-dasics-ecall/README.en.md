# riscv-dasics-ecall

[中文版](README.md) | [Reproduction](../../../../docs/dasics.en.md#riscv-dasics-ecall)

## Scope

Test DASICS checks for RV64 non-virtualized U/S ECALL, protection controls,
trusted PCs, M/S trap routing, and exception return, with an M-mode bypass
control. The setup uses one O3 hart, bare-metal full-system simulation, Bare
address translation, and Semihosting. Exit status `0` requires all 41 cases
to complete. Virtualization and O3 wrong-path execution are outside this
test's scope.

## Case groups

| Cases | Check |
| --- | --- |
| 1–8 | Untrusted U/S ECALL: an enabled check produces DASICS; the matching CUET/CSET produces ordinary ECALL; each uses M/S routing |
| 9–16 | Disabling the current domain's enable produces ordinary ECALL; disabling the other domain still produces DASICS; each uses U/S sources and M/S routing |
| 17–20 | The other domain's ECALL close bit does not bypass the check; U/S sources and M/S routing |
| 21–40 | Five PC-boundary positions per U/S source, each using M/S routing |
| 41 | M-mode bypass: setting MEDELEG bits `8/9/24/25` still produces cause `11` in M |

The first two groups run U before S. Within each source mode, the first
configuration in the table precedes the second; each configuration uses
M routing before S routing. Cases 17–20 likewise run U before S, with M
routing before S for each source.

| U cases | S cases | Probe PC position | First exception |
| --- | --- | --- | --- |
| 21–22 | 31–32 | Eight bytes below the lower bound | DASICS |
| 23–24 | 33–34 | Exactly at the lower bound | Ordinary ECALL |
| 25–26 | 35–36 | `+4` within the lower bound's eight-byte block | Ordinary ECALL |
| 27–28 | 37–38 | Inside the interval | Ordinary ECALL |
| 29–30 | 39–40 | Exactly at the upper bound | DASICS |

## Configuration and layout

- M mode sets direct MTVEC/STVEC, disables interrupts, selects Bare
  translation, and grants read/write/execute permission through a PMP TOR
  region `[0, 0x90000000)`.
- MainCfg initially enables UENA/SENA and closes ordinary U/S memory and
  control-flow checks, leaving ECALL checks open. Each case adjusts the
  current or other domain's enable and CUET/CSET controls.
- Main bounds are `[lo, hi)`. Every trusted interval includes the complete
  S handler. ECALL probes at `probe_before`, `probe_half`, and `probe_after`
  use 32-bit encodings.
- Each case sets and checks MEDELEG. Cases routed from U/S to M delegate the
  non-selected cause class, checking that routing follows the actual ECALL or
  DASICS cause. Completion EBREAK cause `3` is never delegated.

## Exceptions and recovery

| Source | Enabled DASICS check with an untrusted PC | Ordinary ECALL path |
| --- | --- | --- |
| U | Cause `24`, FReason=`1` | Cause `8`, FReason remains `5` |
| S | Cause `25`, FReason=`1` | Cause `9`, FReason remains `5` |
| M | DASICS check bypassed | Cause `11`, FReason remains `5` |

The first trap checks source MPP/SPP, M/S routing, the exact probe EPC,
TVAL=`0`, FReason, an unexecuted fall-through marker, and three register
sentinels: `a0=0x0123456789ABCDEF`, `a1=0xFEDCBA9876543210`, and
`ra=0xA5A5A5A5A5A5A5A5`.

The handler sets MEPC/SEPC to `resume_entry` and returns to the original
source mode through MRET/SRET. Resume code sets its marker to `1`, then
executes an ordinary 32-bit EBREAK at `resume_break` to enter M. The
completion trap must have cause `3`, EPC/TVAL equal to `resume_break`, and
MPP matching the original source. Exactly one ECALL trap must have been
accepted, with FReason and register sentinels preserved. This completion
channel avoids recursive ECALL when ordinary ECALL is delegated to S.
S handler failures also use a separate EBREAK to report the preserved
failure reason in M.

## Software build

From the repository root:

```bash
make -C tests/test-progs/dasics/riscv-dasics-ecall/src
```

The executable is this test directory's `build/riscv-dasics-ecall.elf`;
simulation output is under `build/m5out-o3/<CPU>/`. Run commands are in the
[usage guide](../../../../docs/dasics.en.md#riscv-dasics-ecall).

## Diagnostics

Failures print this message through Semihosting `SYS_WRITE0`:

```text
DASICS ecall: case=NNN reason=NN
```

`case=001..041` identifies the scenarios above, and the failure exit status
is the case ID. Initialization failures print `case=000` and exit with
`255`. Status `124` remains reserved for the host timeout.

| Reason | Failed check |
| --- | --- |
| 01 | MEDELEG readback |
| 02 | MPP/SPP source privilege |
| 03 | M/S exception route |
| 04 | Execution stage or ECALL trap count |
| 05 | Cause |
| 06 | EPC |
| 07 | TVAL |
| 08 | FReason |
| 09 | `a0/a1/ra` sentinels |
| 10 | Unexpected fall-through after ECALL |
| 11 | Exception resume marker |

`s1` holds the case ID, `s2/s3` the source mode and expected S route, `s4`
the expected ECALL cause, `s5` the stage, and `s6` the accepted ECALL count.
`s7/s8` hold fall-through/resume markers, `s9` expected FReason, `s10` the
ECALL PC, and `t6` the failure reason. The harness uses no stack and only
uncompressed instructions.
