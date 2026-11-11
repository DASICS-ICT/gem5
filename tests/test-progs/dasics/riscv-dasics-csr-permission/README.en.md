# riscv-dasics-csr-permission

[中文版](README.md) | [Run commands](../../../../docs/dasics.en.md#riscv-dasics-csr-permission)

## Scope

The test checks M-to-U and M-to-S transitions, trap return, DASICS CSR
access checks, and ordinary CSR controls.

| Coverage | Total across both domains |
| --- | --- |
| Six LibCfg CSR instructions and `rd=x0`, `rs1=x0`, and `zimm=0` forms | 24 instruction tests, 72 permission scenarios |
| LibCfg PC boundaries | 24 scenarios |
| Read-only probes of the 52 custom DASICS CSR addresses in this table | 312 scenarios: 285 DASICS access scenarios and 27 ordinary privilege rejections |
| Ordinary CSR controls | U/S may read `cycle`; S checks rejection of untrusted `sscratch` CSRRW |

The test uses one RV64 hart, bare-metal full-system execution, an O3 model,
and Semihosting termination. Outputs are under `build/m5out-o3/<CPU>/`.
The address table retains the original 52 custom CSRs; it does not cover
the seven newly added CSRs for U-mode exception support, including
`SEDELEG`, which requires S privilege.

`enable_domain` sets `UENA/CUET` in U mode and `SENA/CSET` in S mode,
disabling the matching domain's ECALL protection. Ordinary cause `8/9`
ECALLs here are only completion/recovery signals for the harness. They do
not test ECALL protection; see the dedicated
[riscv-dasics-ecall](../riscv-dasics-ecall/README.en.md) test.

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
   then runs the domain's instruction table, boundary table, CSR address
   table, and ordinary CSR controls. After U mode completes, S mode starts
   from the beginning. Success requires completing all S-mode checks.

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

## PC-boundary cases

The boundary table reuses one 8-byte-aligned `boundary_probe` instruction,
`csrrw a0, 0x880, a1`. Let its PC be `B`; `boundary_ecall` immediately
follows at `B+4`. For each entry, M mode resets the current domain's bounds,
enable bit, and initial `P/Q/D/FReason` state. Each interval runs with
protection enabled first, then disabled. Both domains use the same table.

| Entries (on / off) | PC position | Interval `[lo, hi)` | Enabled | Disabled |
| --- | --- | --- | --- | --- |
| 1 / 2 | `lo - 8` | `[B+8, B+24)` | Reject | Allow |
| 3 / 4 | `lo` | `[B, B+16)` | Allow | Allow |
| 5 / 6 | `hi - 8` | `[B-8, B+8)` | Allow | Allow |
| 7 / 8 | `hi` | `[B-16, B)` | Reject | Allow |
| 9 / 10 | Empty interval | `[B, B)` | Reject | Allow |
| 11 / 12 | Reversed interval | `[B+8, B-8)` | Reject | Allow |

Allowed accesses return through ECALL and check the domain's cause and
`MPP`, `mepc=B+4`, `a0=P`, LibCfg=`Q`, and FReason=`5`.
Rejected accesses require `mcause=2`, `MPP` matching the current domain,
`mepc=B`, `mtval` equal to the probe's original encoding, and unchanged
`a0=D`, LibCfg=`P`, and FReason=`5`. After M mode skips the faulting
instruction, ECALL must occur at `B+4` and check unchanged state again.

Each boundary metadata entry contains four 64-bit fields, totaling
32 bytes: `lower`, `upper`, `enabled`, and `allowed`. Each domain starts
at the first boundary entry after completing its instruction table.

## DASICS CSR address table

The address table covers the 52 custom DASICS CSR addresses below.
SMainCfg and UMainCfg share internal state but are probed separately.
Each entry contains four 64-bit fields, totaling 32 bytes: `trustedPC`,
`untrustedPC`, `readerPC`, and `minpriv`.

| Entries | CSR | Addresses | Minimum privilege |
| --- | --- | --- | --- |
| 1 | LibCfg | `0x880` | U |
| 2–33 | LibBoundLo/Hi 0–15 | `0x890–0x8AF` | U |
| 34–37 | MainCallEntry, ReturnPC, ActiveZoneReturnPC, FReason | `0x8B0–0x8B3` | U |
| 38 | JumpCfg | `0x8C8` | U |
| 39–46 | JumpBoundLo/Hi 0–3 | `0x8C0–0x8C7` | U |
| 47–49 | UMainCfg, UMainBoundLo/Hi | `0x9E1–0x9E3` | S |
| 50–52 | SMainCfg, SMainBoundLo/Hi | `0xBC0`, `0xBC2`, `0xBC3` | M |

Each address has statically generated `csrrs a0, csr, zero` probes that do
not write the target CSR. The trusted and untrusted blocks each contain a
probe and ECALL in 8 bytes. The current domain's trusted interval is
`[trustedPC, untrustedPC)`, with the untrusted probe at its upper bound.
Each address runs three scenarios:

| `s5` | Current domain's protection | Probe location | Ordinary privilege satisfied | Ordinary privilege insufficient |
| --- | --- | --- | --- | --- |
| `0` | Disabled | Outside | Allow | Cause 2 |
| `1` | Enabled | Trusted | Allow | Cause 2 |
| `2` | Enabled | Outside | Cause 2 | Cause 2 |

U mode satisfies ordinary privilege for 46 addresses and S mode for 49,
giving `(46+49)×3=285` DASICS access scenarios. The other 6 U-mode and
3 S-mode addresses are rejected by ordinary privilege in all three scenarios,
giving 27 rejections. Those rejections do not validate DASICS access checks.

For each scenario, M mode configures protection and bounds, resets
LibCfg=`P`, FReason=`5`, and `a0=D`, then calls that address's M-mode reader
to capture its current value in `s4`. Allowed reads must return `a0=s4`;
rejected reads must preserve `a0=D`. Both require the target CSR to equal
the snapshot, LibCfg=`P`, and FReason=`5`. MainCfg and MainBound values may
depend on the scenario and are not assumed to be fixed constants.

Every rejection checks `mcause=2`, the current domain's `MPP`, the exact
probe `mepc`, and its original encoding in `mtval`. After skipping the probe,
ECALL must occur at its `PC+4` and recheck unchanged state. Allowed scenarios
also check their result through the exact following ECALL in M mode.

## Ordinary CSR controls

After the address table, set the current domain's main interval to `[0, 0)`
and enable protection, so the control instructions run outside trusted code.
M mode sets both `mcounteren.CY` and `scounteren.CY` to allow S/U reads of
`cycle`.

| Domain | Instruction | Expected result |
| --- | --- | --- |
| U, S | `csrrs a0, 0xC00, zero` | `a0` differs from `D`; no fixed counter value is required |
| S | `csrrw a0, 0x140, a1` | Cause `2`, with `a0=D` and `sscratch=P` |

The `cycle` controls check the following ordinary ECALL's domain-specific
cause `8/9`, `MPP`, exact `mepc`, LibCfg=`P`, and FReason=`5`.

The S-mode `sscratch` control enables SENA with an empty S trusted interval
`[0, 0)`. `ordinary_sscratch_probe` must produce cause `2`, `MPP=S`, and
`mepc=ordinary_sscratch_probe`, with the original 32-bit instruction in
`mtval`. State must remain `a0=D`, `sscratch=P`, LibCfg=`P`, and FReason=`5`.
After M mode skips four bytes and returns to S, an ECALL must occur at
`ordinary_sscratch_ecall` with cause `9` and `MPP=S`, rechecking unchanged
state. U mode omits this control because the CSR requires S privilege.

The current DASICS gate protects untrusted S-mode reads and writes to
`SSTATUS`, `STVEC`, `SSCRATCH`, `SEPC`, `SCAUSE`, and `STVAL`. These exception
CSRs are protected, but access restrictions are not yet uniform across all
S-mode CSRs. This test exercises only `SSCRATCH` among these six.

## CSR write flush policy

Writes to the 52 custom CSR addresses in this table retain `IsNonSpeculative` and
`IsSerializeAfter`, and add `IsSquashAfter` according to write intent.
At successful O3 commit, the CSR update takes effect before younger
instructions are squashed and fetch restarts at the next PC.
For instructions with write intent, disabled S/U protection, a zero source
value, or an unchanged written value does not suppress the flush.
Setting `rd=x0` does not remove write intent.

`CSRRS/CSRRC` with `rs1=x0` and `CSRRSI/CSRRCI` with `zimm=0` have no write
intent and retain only the existing serialization. `CSRRW/CSRRWI` always
have write intent. Faulting writes do not update the CSR and follow the
trap path without an additional successful-write flush.

A functional exit code of `0` does not independently prove that a flush
occurred. Validation requires `Commit`/`Fetch` traces showing commit,
younger-instruction squash, and fetch at the next PC.

## Debugging

Register `s0` points to the current table entry. Register `s1` records the
stage: `0/1` for the initial ECALL harness, `2–5` for instruction-permission
entries, `6` for an allowed boundary ECALL, `7` for a rejected boundary CSR,
and `8` for its return ECALL. Stages `9/10/11` identify the address table's
allowed ECALL, rejected CSR, and return ECALL. Stage `12` identifies the
allowed `cycle` control's ECALL, `13` the SSCRATCH illegal-instruction trap,
and `14` its return ECALL.
Register `s2=0` identifies the initial harness; the instruction and boundary
tables are each numbered `1–12`, the address table `1–52`, and the ordinary
controls `1/2`. Use `s3` (`0=U`, `1=S`) and `s1` to locate the domain, table,
and entry. The address table also uses `s4` for the target snapshot and
`s5` for scenario `0/1/2`.

Compressed instructions are disabled, so ECALL return advances by 4 bytes.
The test uses no stack. Registers `ra`, `t0/t1`, `a2/a3`, and `s0–s5` are
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
| `14` | Rejected access `mtval` does not match the original 32-bit instruction |
| `15` | Rejected access or trap return changed the `a0` sentinel |
| `16` | The initial LibCfg value changed when preservation was required |
| `17` | FReason changed when preservation was required |
| `18` | Incorrect ECALL `mepc` after a rejected instruction-permission access |
| `19` | Incorrect ECALL `mepc` after an allowed boundary access |
| `20` | Incorrect ECALL `mepc` after returning from a rejected boundary access |
| `21` | Incorrect ECALL `mepc` after an allowed address probe or rejection return |
| `22` | Allowed address read does not return the target snapshot in `a0` |
| `23` | Address-table target CSR differs from its snapshot |
| `24` | Incorrect ECALL `mepc` in the `cycle` control |
| `25` | The `cycle` control did not change the `a0` sentinel |
| `26` | Incorrect return-ECALL `mepc` in the `sscratch` control |
| `27` | Rejected `sscratch` access or its return changed the `a0` sentinel |
| `28` | The initial `sscratch` value changed |
| `124` | Host timeout |
