# riscv-dasics-mem

[中文版](README.md) | [Reproduction](../../../../docs/dasics.en.md#riscv-dasics-mem)

## Scope

Test DASICS data bounds, permissions, bypass conditions, exception routing,
and exception return for ordinary RV64 scalar memory accesses. The setup uses
one O3 hart, bare-metal full-system simulation, Bare address translation,
and Semihosting. The current [O3 models](../../../../configs/dasics/README.en.md)
use `RVA20S64` with `Zba/Zbb/Zbc/Zbs/V`; this test covers 27 integer, F/D,
and RV64C memory instructions.
Exit status `0` requires all 226 cases to complete.

Zfh, Zcb, and RV32-only forms are not included in the execution tests.
AMO, LR/SC, vector memory accesses, prefetching, Hypervisor, CBO, paged
translation faults, and O3 wrong-path execution are outside this test's scope.

## Case groups

The first 108 cases follow the probe order below. For instruction index `i`,
cases `4*i+1..4*i+4` are U allowed, U denied, S allowed, and S denied,
respectively. U traps enter M; S traps enter S.

| Instruction index | Probe order |
| --- | --- |
| 0–6 | `lb, lbu, lh, lhu, lw, lwu, ld` |
| 7–10 | `sb, sh, sw, sd` |
| 11–14 | `flw, fld, fsw, fsd` |
| 15–20 | `c.lw, c.ld, c.fld, c.sw, c.sd, c.fsd` |
| 21–26 | `c.lwsp, c.ldsp, c.fldsp, c.swsp, c.sdsp, c.fsdsp` |

| Cases | Check |
| --- | --- |
| 1–108 | Four cases per instruction: U allowed/U denied (traps in M), S allowed/S denied (traps in S), across 27 instructions |
| 109–116 | Additional allowed/denied U→S and S→M routes for `ld/sd` |
| 117–118 | M-mode bypass of DASICS data checks |
| 119–126 | Disabling the current domain's enable bypasses its check; disabling the other domain does not |
| 127–134 | The matching load/store close bit bypasses its check; the other operation's close bit does not |
| 135–138 | The other domain's matching close bit does not bypass the check |
| 139–142 | Trusted-PC bypass of data checks |
| 143–154 | R/W isolation, the reserved U bit, and an invalid V bit |
| 155–178 | Empty/reversed ranges, below/above range, final byte exactly inside, and crossing the upper bound |
| 179–182 | Masking of the low three bits in bound CSRs |
| 183–186 | Rejection of high virtual addresses preserves the original TVAL |
| 187–218 | U/S `ld/sd/fld/fsd`: DASICS denied/allowed combined with misalignment/PMP denial |
| 219–222 | Adjacent bound groups cannot combine to authorize one access |
| 223–226 | Read/write permission through bound group index 15 |

## Check contract

- M mode configures exception vectors, PMP, MainCfg/MainBound, and
  LibCfg/LibBound before entering the selected source mode. M/S handlers
  check and recover from exceptions.
- An untrusted U/S access requires one valid group to cover every accessed
  byte and grant the matching R/W permission. Bounds are `[lo, hi)`.
  The reserved U bit does not grant read/write permission.
- M mode, a trusted PC, the current domain's disabled enable, or its matching
  load/store close bit can bypass DASICS data checks. A switch for the other
  domain or operation cannot substitute for the matching configuration.
- Denied cases check source mode, M/S routing, cause, EPC, original effective
  address TVAL, FReason, architectural destination-register and target-memory
  state, and the marker after exception return.
- Each case initializes GPR destination `a0` to `0x0123456789ABCDEF`, FP
  destination `fa0` to `0x8877665544332211`, and every byte of the 64-byte
  test memory to `0xF1`. Rejected accesses and ordinary faults must preserve
  both destinations and all test memory.
- Allowed integer loads check sign/zero extension by width. FLW checks
  NaN-boxed `0xFFFFFFFFF1F1F1F1`; FLD and its compressed forms check
  `0xF1F1F1F1F1F1F1F1`. Integer stores use source `0x0807060504030201`,
  and FP stores use `0x1817161514131211`. Checks cover the written bytes
  at the access width and preserve `0xF1` elsewhere.
- Each case starts with FS=`Clean(2)`. Allowed FP loads change it to
  `Dirty(3)`; every other case preserves `Clean(2)`. The M handler checks FS
  before using `fmv.x.d` to inspect the FP destination. The S handler
  executes no FP instructions.
- DASICS denials use U/S causes `24/25`, with FReason=`2` for loads and `3`
  for stores, EPC at the probe PC, and TVAL holding the original effective
  address. Normal completion and ordinary faults preserve FReason sentinel
  `5`. Completion ECALLs are not delegated to S; exception return uses
  `resume_entry/resume_ecall`.

The current gem5 implementation chooses DASICS checks before alignment/PMP
checks. Conflict cases distinguish this ordering through exception causes:
a DASICS denial must remain a DASICS exception; ordinary alignment/PMP faults
become visible after DASICS allows the access. This is the current
implementation's priority policy. The test does not use request traces to
establish that no TLB or memory request was issued. Memory markers check
architectural side effects only.

| DASICS result | Subsequent condition | Load cause | Store cause |
| --- | --- | --- | --- |
| Denied | Misalignment or PMP denial | U=`24`, S=`25` | U=`24`, S=`25` |
| Allowed | Misalignment | `4` | `6` |
| Allowed | PMP denial | `5` | `7` |

## Software build

From the repository root:

```bash
make -C tests/test-progs/dasics/riscv-dasics-mem/src
```

The executable is this test directory's `build/riscv-dasics-mem.elf`;
simulation output is under `build/m5out-o3/<CPU>/`. Run commands are in the
[usage guide](../../../../docs/dasics.en.md#riscv-dasics-mem).

## Diagnostics

Failures print this message through Semihosting `SYS_WRITE0`:

```text
DASICS memory: case=NNN reason=NN
```

`case=001..226` identifies the scenarios above. Failure exit status equals
the case ID below `124`, and `case+1` for `case>=124`, using `125..227` for
the latter group. Status `124` remains reserved for the host timeout.
Initialization failures print `case=000` and exit with `255`.
`reason=01..14` separately identifies the failed check; the printed case ID
is unaffected by exit-status mapping.

| Reason | Failed check |
| --- | --- |
| 01 | MEDELEG readback |
| 02 | MPP/SPP source privilege |
| 03 | M/S exception route |
| 04 | Execution stage or accepted fault count |
| 05 | Cause |
| 06 | EPC |
| 07 | TVAL |
| 08 | FReason |
| 09 | GPR destination |
| 10 | FP destination |
| 11 | All 64 bytes of test memory |
| 12 | FS state |
| 13 | Probe completion marker |
| 14 | Exception resume marker |

`a1` holds the effective address; compressed stack forms also put it in
`sp`, and the harness needs no stack. `s1` holds the case ID, `s4` the expected
cause (`0` for completion), and `s5` the stage. `s6` counts accepted faults,
`s7/s8` hold completion/resume markers, `s10` holds expected FReason,
`s11` the probe PC, `a7` the completion ECALL PC, and `t6` the failure reason.
