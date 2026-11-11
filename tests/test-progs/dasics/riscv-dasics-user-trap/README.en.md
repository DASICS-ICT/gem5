# riscv-dasics-user-trap

[中文版](README.md) | [Reproduction commands](../../../../docs/dasics.en.md#riscv-dasics-user-trap)

## Scope

Verify M/S/U routing of synchronous exceptions originating in non-virtualized
RV64 U mode, including a U handler returning through URET. The test uses
the existing single-hart O3 MSU bare-metal full-system configuration, Bare
translation, permissive PMP, and direct-mode UTVEC. Semihosting returns
`0` only after all 10 scenarios complete.

| Probe | Source code | First cause | First TVAL | FReason |
| --- | --- | --- | --- | --- |
| Read MSTATUS | Trusted U | `2` | Original 32-bit probe encoding | Preserve sentinel `5` |
| ECALL | Untrusted U | `24` | `0` | Set to `1` |

This test excludes user interrupts, virtualization, direct delegation in
M/U-only systems, illegal URET execution, and vectored UTVEC. It does not
replace comprehensive CSR instruction and permission tests.

## Scenarios

MEDELEG and SEDELEG below refer to the bit for the selected probe's cause.
UPIE starts opposite to UIE to distinguish entry-time saving from a stale
value.

| ID | Probe | MEDELEG | Stored SEDELEG | Handler | Initial UIE / UPIE |
| --- | --- | --- | --- | --- | --- |
| 1 | Read MSTATUS | `0` | `0` | M | `1 / 0` |
| 2 | Read MSTATUS | `1` | `0` | S | `1 / 0` |
| 3 | Read MSTATUS | `1` | `1` | U | `1 / 0` |
| 4 | Read MSTATUS | `0` | `1` | M | `1 / 0` |
| 5 | ECALL | `0` | `0` | M | `1 / 0` |
| 6 | ECALL | `1` | `0` | S | `1 / 0` |
| 7 | ECALL | `1` | `1` | U | `1 / 0` |
| 8 | ECALL | `0` | `1` | M | `1 / 0` |
| 9 | Read MSTATUS | `1` | `1` | U | `0 / 1` |
| 10 | ECALL | `1` | `1` | U | `0 / 1` |

Each case clears SEDELEG before configuring delegation independently.
Cases 4 and 8 first set both delegation bits, then clear MEDELEG and
confirm that stored SEDELEG remains one. Writing SEDELEG while MEDELEG is
already zero would be filtered and would not test the entry-time check.

## Trap and return checks

- M mode configures handlers, PMP, trusted bounds and state sentinels, then
  enters the U probe through MRET. UENA/SENA and U ECALL protection are
  enabled; ordinary data and control-flow checks are disabled.
- The trusted U interval includes the illegal CSR probe, U handler, URET
  and resume point. The ECALL probe is outside it. The S interval includes
  the S handler and SRET. Bounds are eight-byte aligned.
- Exactly one initial exception must reach the expected handler. Check
  cause, exact EPC, TVAL and FReason, unchanged observable GPR sentinels,
  and absence of execution along the probe's fallthrough path.
- The U handler checks `UIE=0` and `UPIE=original UIE`, sets UEPC to the
  resume point, and executes URET. The resume point checks
  `UIE=original UIE` and `UPIE=1`.
- M/S handlers use MRET/SRET to reach the same U resume point. User trap
  CSRs and UIE/UPIE must retain their configured values on these routes.
- The resume point sets a completion marker and executes an undelegated
  ordinary EBREAK to M mode. The completion trap must have cause `3`,
  EPC/TVAL pointing to that EBREAK, and U origin. The M handler checks the
  resume marker and preserved state before continuing.

URET uses encoding `0x00200073`; user trap CSRs use numeric addresses so
the existing toolchain is sufficient. The harness uses fixed-width
instructions and reserved registers, without general context saving.

## Observation limits

The completion EBREAK overwrites MEPC/MCAUSE/MTVAL and some MSTATUS
fields. Their final values cannot prove preservation of all M-mode state
through U entry. The test checks state not overwritten by completion,
including M/S scratch registers, handler addresses and applicable S trap
state. M/S routes also check that user trap state was not borrowed.
MRET clears MPRV when entering U, so this test checks only preservation
of `MPRV=0`; it does not cover `MPRV=1` or H-extension state.

## Build and run

```bash
make -C tests/test-progs/dasics/riscv-dasics-user-trap/src
make dasics-test TEST=riscv-dasics-user-trap CPU=all
```

The ELF is `build/riscv-dasics-user-trap.elf`. Configuration and statistics
are under `build/m5out-o3/<CPU>/`. The root Makefile discovers this test
automatically; no separate target is required.

## Diagnostics

Failures print `DASICS user-trap: case=NNN reason=NN` and return the case ID
`1–10`. Initialization failure returns `255`; `124` indicates host timeout.

| Reason | Failed check |
| --- | --- |
| 01 | MEDELEG or SEDELEG readback |
| 02 | MPP/SPP source privilege |
| 03 | M/S/U initial trap route |
| 04 | Execution stage or initial trap count |
| 05 | Cause |
| 06 | EPC |
| 07 | TVAL |
| 08 | FReason |
| 09 | `a0/a1/ra` sentinels |
| 10 | Unexpected probe fallthrough |
| 11 | Trap return or resume marker |
| 12 | UIE/UPIE at entry or after return |
| 13 | UCAUSE/UTVAL/UEPC |
| 14 | SCAUSE/STVAL/SEPC |
| 15 | U/S/M scratch registers or trap vectors |
| 16 | MPRV |

`s1` is the case ID, `s2` the expected handler mode, `s3` initial USTATUS,
`s4` expected cause, `s5` the stage, and `s6` the initial trap count.
`s7/s8` hold fallthrough/resume markers, `s9` expected FReason, and
`s10/s11` the probe PC/TVAL. `t6` carries the diagnostic reason.
Each table row contains six 64-bit fields, totaling 48 bytes: probe PC,
cause, final MEDELEG bit, stored SEDELEG bit, handler mode, initial USTATUS.
