# riscv-dasics-call

[中文版](README.md) | [Reproduction](../../../../docs/dasics.en.md#riscv-dasics-call)

## Scope

Test RV64 DASICSCALL targets, link registers, ReturnPC, source permissions,
illegal-instruction traps, ordinary-jump controls, and existing m5 encoding
compatibility. The setup uses one O3 hart, bare-metal full-system simulation,
Bare address translation, PMP, and Semihosting.
Exit status `0` requires all 67 cases to complete.
Virtualization and O3 wrong-path stress tests are outside this test's scope.

## Encoding and semantics

This gem5 implementation and test use the encoding in rocket-chip commit
`cb2690c0a71a`, referenced by public
[DASICS-ICT/xiangshan-dasics `dasics-master`](https://github.com/DASICS-ICT/xiangshan-dasics/tree/dasics-master):
[Instructions.scala, lines 372–373](https://github.com/DASICS-ICT/rocket-chip/blob/cb2690c0a71adb789943ed6321555687c3daa478/src/main/scala/rocket/Instructions.scala#L372-L373).

| Instruction | Opcode | funct3 | Link destination |
| --- | --- | --- | --- |
| DASICSCALL.J | custom-0, `0x0B` | `0` | Fixed `ra` |
| DASICSCALL.JR | custom-0, `0x0B` | `1` | `rd` |

Protected binaries using a `0x7B` version of DASICS calls must be rebuilt
with `0x0B`. gem5 m5 pseudo-instructions retain `0x7B`.

Permissions and ReturnPC behavior follow the NanhuV5 semantics:

- J uses a signed 23-bit even displacement in
  `[-0x400000, 0x3FFFFE]`, targeting `PC+offset`. Its bit layout differs
  from JAL: encoded RD bits belong to the displacement, and the link
  destination is fixed to `ra`.
- JR uses a signed 12-bit I-type immediate, targeting `(old_rs1+imm)&~1`.
  It uses the old source value when `rd==rs1`. With `rd=x0`, it suppresses
  the GPR write while still updating ReturnPC.
- Calls require enabled, trusted, non-virtualized U/S execution. M-mode
  calls are illegal. Successful link values and ReturnPC equal `PC+4`.
- Illegal calls produce cause `2`, EPC at the call, and the original
  instruction encoding in TVAL. The link register, ReturnPC, and FReason
  remain unchanged.

The test's `CALL_J/CALL_JR` macros emit `.word` encodings, without requiring
GNU assembler support for new mnemonics.

## Case groups

The first 20 cases use the following probe order, running U before S for
each probe:

| Cases | Successful probe |
| --- | --- |
| 1–2 | J with a short positive displacement |
| 3–4 | J with a short negative displacement |
| 5–6 | J minimum displacement `-0x400000` |
| 7–8 | J maximum even displacement `+0x3FFFFE`, with a halfword-aligned target |
| 9–10 | JR `rd=ra`, clearing the target's low bit |
| 11–12 | JR `rd=a0`, immediate `+8` |
| 13–14 | JR `rd=x0`, still updating ReturnPC |
| 15–16 | JR `rd==rs1==a1`, resolving the target from the old source |
| 17–18 | JR immediate `-2048` |
| 19–20 | JR immediate `+2047` |

| Cases | Check |
| --- | --- |
| 21–24 | J/JR in U/S: the trusted target's first instruction reads ReturnPC |
| 25–52 | Source-permission matrix: disabled current domain, untrusted source, and untrusted source with matching CUFT/CSFT are illegal; disabling only the other domain still succeeds |
| 53–54 | Illegal M-mode J/JR with bit 31 set in the original encoding |
| 55–58 | Undefined `funct3=7`, with U/S sources and M/S illegal-instruction routing |
| 59–62 | JR `rs1=x0`: only disabled/untrusted-source rejection paths |
| 63–66 | Ordinary JAL/JALR in U/S, preserving ReturnPC |
| 67 | Existing `0x7B` M-mode `m5_sum(1,2,3,4,5,6)` returns `21`, preserves ReturnPC/FReason, and does not generate an m5 exit event |

The permission matrix runs J in U/S, then JR in U/S. Each seven-case group
tests disabled current domain, untrusted source, and untrusted source with
the matching jump close bit, each routed to M/S. Its final case disables
only the other domain. Static layout covers both J displacement extremes
without depending on fixed runtime addresses.

## State and recovery

- MainCfg defaults to `0x1DF`, enabling both domains and closing ECALL/data
  checks while retaining ordinary jump checks. Each case adjusts enable,
  trust, and jump close controls. The S handler remains trusted.
- JumpCfg, MainCallEntry, and ActiveZoneReturnPC are zero. Ordinary
  `ret/jalr` from targets outside trusted code are authorized by the newly
  written ReturnPC.
- Each case sets ReturnPC=`0x1020304050607080`, FReason=`5`,
  and `ra=0xA5A5A5A5A5A5A5A5`. Regular probes set
  `a0=0x0123456789ABCDEF`; `a1` holds the descriptor's old source value,
  and `a4` starts at `0x5566778899AABBCC`. The m5_sum case sets `a0..a5`
  to `1..6`.
- m5_sum does not check `a1` preservation because the current gem5 M5Op
  path rewrites it. It still checks `a0=21`, ReturnPC/FReason, and normal
  completion. J/JR probes retain their `a1` source-value or alias-result checks.
- Successful calls check target markers, the selected link destination, and
  ReturnPC=`PC+4`. Trusted targets capture ReturnPC into `a4` with their
  first CSR instruction. Ordinary JAL/JALR controls capture the original
  ReturnPC sentinel.
- Rejections check cause `2`, source MPP/SPP, M/S routing, EPC at the call,
  and the original 32-bit instruction in TVAL, then return to `resume_entry`
  through MRET/SRET. Link/source registers, ReturnPC, FReason, and the capture
  sentinel remain unchanged, with a zero target marker.
- Completion uses an undelegated ordinary EBREAK, cause=`3`, with EPC/TVAL
  at the actual breakpoint. Its marker is `1` after success and `2` after
  rejection recovery; accepted illegal-instruction counts are `0/1`.
  FReason remains `5` throughout all cases.

## Software build

From the repository root:

```bash
make -C tests/test-progs/dasics/riscv-dasics-call/src
```

The executable is this test directory's `build/riscv-dasics-call.elf`;
simulation output is under `build/m5out-o3/<CPU>/`. Run commands are in the
[usage guide](../../../../docs/dasics.en.md#riscv-dasics-call).

## Optional O3 traces

Calls use `IsNonSpeculative`, `IsSerializeAfter`, and `IsSquashAfter`.
`xc->setMiscReg` defers the implicit ReturnPC write until O3 commit.
A software exit status of `0` does not independently establish the timing
of the subsequent squash.

```bash
mkdir -p tests/test-progs/dasics/riscv-dasics-call/build/m5out-o3/v5_full-trace
build/RISCV_DASICS/gem5.opt \
  --outdir=tests/test-progs/dasics/riscv-dasics-call/build/m5out-o3/v5_full-trace \
  --debug-flags=Commit,Fetch,RiscvMisc \
  --debug-file=dasics-call.trace \
  configs/dasics/riscv_dasics_o3_v5_full.py \
  tests/test-progs/dasics/riscv-dasics-call/build/riscv-dasics-call.elf
```

The trace is stored separately in `v5_full-trace/dasics-call.trace`.
Correlate events using the call PC and sequence number:

1. Locate the call with `Trying to commit head instruction` and
   `Committing instruction with PC`. Distinguish the initializing M-mode
   CSRRW from the call's implicit `Setting MiscReg DASICS_RETURN_PC` write.
2. Check `Squashing after squash after request` in the subsequent tick and
   Fetch's `Squash from commit`. Distinguish committed SquashAfter from an
   ordinary branch-misprediction redirect.
3. Confirm that post-commit Fetch restarts at the actual call target.
   `PC+4` is the link and ReturnPC, rather than the post-call fetch target.

## Diagnostics

Failures print this message through Semihosting `SYS_WRITE0`:

```text
DASICS call: case=NNN reason=NN
```

`case=001..067` identifies the scenarios above, and the failure exit status
is the case ID. Initialization failures print `case=000` and exit with
`255`. Status `124` remains reserved for the host timeout.

| Reason | Failed check |
| --- | --- |
| 01 | MEDELEG readback |
| 02 | MPP/SPP source privilege |
| 03 | M/S exception route |
| 04 | Stage or accepted illegal-instruction count |
| 05 | Cause |
| 06 | EPC |
| 07 | TVAL |
| 08 | FReason |
| 09 | ReturnPC |
| 10 | `ra` |
| 11 | `a0` destination or m5_sum result |
| 12 | `a1` source or source/destination alias result |
| 13 | Target marker |
| 14 | Completion/resume marker |
| 15 | Captured ReturnPC or preserved value in `a4` |

`s1` holds the case ID, `s2/s3` the source and illegal-instruction S route,
`s4` the expected rejection, `s5` the stage, and `s6` the accepted illegal
trap count. `s7/s8` hold target/completion markers, `s10` the call PC,
`s11` expected ReturnPC, `a7` the original instruction, `a6` the `PC+4` used
to return from the `rd=x0` target, and `t6` the failure reason.
