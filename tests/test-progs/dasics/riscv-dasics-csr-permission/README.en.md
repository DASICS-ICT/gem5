# riscv-dasics-csr-permission

[中文版](README.md) | [Run commands](../../../../docs/dasics.en.md#riscv-dasics-csr-permission)

## Scope

The test checks M-to-U and M-to-S transitions, trap return, and S/U-mode
LibCfg (`0x880`) access. Each domain covers all six CSR instructions and
the `rd=x0`, `rs1=x0`, and `zimm=0` forms in 12 entries: 24 instruction
tests and 72 permission scenarios overall. Other CSRs are outside its scope.

The test uses one RV64 hart, bare-metal full-system execution, an O3 model,
and Semihosting termination. Outputs are under `build/m5out-o3/<CPU>/`.

## Execution

1. In M mode, install a direct `mtvec` handler, disable interrupts and trap
   delegation, and select Bare address translation.
2. Configure a PMP TOR region `[0, 0x90000000)` with S/U-mode read, write,
   and execute permissions. At each domain's start, clear SMainCfg and all
   four S/U MainBound registers, then reset the case pointer and stage.
3. Select U mode first, then S mode, with `s3=0` and `s3=1` respectively.
   Clear `mstatus.MPP/MPRV/MIE/MPIE`, set `MPP` to the selected domain,
   and enter that domain using `mret`.
4. Set `a0=0x5678` and execute the first ECALL in the current domain.
   The M-mode handler checks the domain's `mcause` and `MPP`, the exact
   `mepc`, and `a0`, advances `mepc` by 4, then executes `mret`.
5. Increment `a0` and execute the second ECALL in the current domain.
   The handler checks the trap origin, sequence, `mepc`, and `a0=0x5679`,
   then runs that domain's 12 permission entries. After U mode completes,
   S mode starts from the beginning. Success requires completing S mode.

| Domain | `s3` | Enable bit | Trusted bounds | ECALL `mcause` | Trap-entry `MPP` |
| --- | --- | --- | --- | --- | --- |
| U | `0` | `UENA` (bit 1) | UMainBoundLo/Hi | `8` | U |
| S | `1` | `SENA` (bit 0) | SMainBoundLo/Hi | `9` | S |

## LibCfg permission cases

Each instruction entry runs through the stages below. Before stages 2–4,
M mode resets LibCfg to `P=0x13579BDF2468ACEF`, the destination sentinel
to `a0=D=0xA5A5A5A5A5A5A5A5`, and FReason to `5`.
Instructions using `a1` take the source value `Q=0xFEDCBA9876543210`;
the nonzero immediate is `I=0x15`. Both domains reuse the same 12-entry
instruction table and the stages below.

| Stage | Current domain's enable bit | CSR instruction location | Expected result |
| --- | --- | --- | --- |
| 2: Protection disabled | `0` | Trusted region upper bound | Allowed; results below, FReason=`5` |
| 3: Trusted access | `1` | Trusted region lower bound | Allowed; results below, FReason=`5` |
| 4: Untrusted access | `1` | Upper bound; the same instruction as stage 2 | Illegal instruction; `a0=D`, LibCfg=`P`, FReason=`5` |
| 5: Trap return | `1` | ECALL following the untrusted CSR | State remains `a0=D`, LibCfg=`P`, FReason=`5` |

| Entry | Instruction | Allowed `a0` result | Allowed LibCfg result |
| --- | --- | --- | --- |
| 1 | `csrrw a0, 0x880, a1` | `P` | `Q` |
| 2 | `csrrs a0, 0x880, a1` | `P` | `P \| Q` |
| 3 | `csrrc a0, 0x880, a1` | `P` | `P & ~Q` |
| 4 | `csrrwi a0, 0x880, 0x15` | `P` | `I` |
| 5 | `csrrsi a0, 0x880, 0x15` | `P` | `P \| I` |
| 6 | `csrrci a0, 0x880, 0x15` | `P` | `P & ~I` |
| 7 | `csrrw zero, 0x880, a1` | `D` | `Q` |
| 8 | `csrrwi zero, 0x880, 0x15` | `D` | `I` |
| 9 | `csrrs a0, 0x880, zero` | `P` | `P` |
| 10 | `csrrc a0, 0x880, zero` | `P` | `P` |
| 11 | `csrrsi a0, 0x880, 0` | `P` | `P` |
| 12 | `csrrci a0, 0x880, 0` | `P` | `P` |

Each entry has an 8-byte trusted block and an 8-byte untrusted block,
each containing its CSR instruction and following ECALL.
The current domain's MainBoundLo/Hi define `[trustedPC, trustedPC + 8)`;
`untrustedPC = trustedPC + 8` is exactly at its upper bound.
Allowed accesses return to M mode through the following ECALL, which checks
the domain's ECALL cause and `MPP`, the exact `mepc`, and the expected results.
The two `rd=x0` entries must preserve the `a0` sentinel.

Every untrusted access must produce `mcause=2`, `MPP` matching the current
domain, and `mepc=untrustedPC`, with `mtval` equal to the original instruction
encoding at that address. After checking unchanged state, M mode advances
`mepc` by 4 and returns to that domain. The following ECALL must then report
the domain's ECALL cause and `MPP`, `mepc=untrustedPC+4`, and unchanged state.
The read-only and `rd=x0` forms must also be rejected.

Each metadata entry contains five 64-bit fields, totaling 40 bytes:
`trustedPC`, `untrustedPC`, `sourceValue`, `allowedRd`, and `allowedCSR`.
Register `s0` points to the current entry, `s1` records the stage, and
`s2` identifies the entry within each domain: `0` for the initial ECALL pair
and `1–12` for the table above. Together with `s3` (`0=U`, `1=S`), these
registers locate the domain and entry when debugging a failure.

Compressed instructions are disabled, so ECALL return advances by 4 bytes.
The test uses no stack. Registers `ra`, `t0/t1`, `a2/a3`, and `s0/s1/s2/s3` are
reserved for the harness. Registers `a0/a1` hold case operands;
the handler does not implement general context preservation.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | All checks passed |
| `1` | Unexpected trap cause; `a3` holds the actual `mcause` |
| `2` | Trap entry `mstatus.MPP` does not match the current domain |
| `3` | Unexpected trap sequence |
| `4` | Incorrect `mepc` for the first trap |
| `5` | Incorrect `a0` for the first trap |
| `6` | Incorrect `mepc` for the second trap |
| `7` | Incorrect `a0` for the second trap |
| `8` | Incorrect ECALL `mepc` in the disabled case |
| `9` | Incorrect ECALL `mepc` in the trusted case |
| `10` | Unexpected allowed `a0` result, including sentinel preservation with `rd=x0` |
| `11` | Unexpected LibCfg result for an allowed instruction |
| `12` | Allowed access changed FReason |
| `13` | Rejected access `mepc` is not at the expected CSR instruction |
| `14` | Rejected access `mtval` does not match the instruction encoding |
| `15` | Rejected access or trap return changed the `a0` sentinel |
| `16` | Rejected access or trap return changed the initial LibCfg value |
| `17` | Rejected access or trap return changed FReason |
| `18` | Incorrect ECALL `mepc` after returning from the rejected access |
| `124` | Host timeout |
