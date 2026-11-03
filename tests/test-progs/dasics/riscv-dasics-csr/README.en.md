# riscv-dasics-csr

[中文版](README.md) | [Reproduction commands](../../../../docs/dasics.en.md#riscv-dasics-csr)

## Metadata

| CSR | Address |
| --- | --- |
| `DASICS_MAIN_CALL_ENTRY` | `0x8B0` |
| `DASICS_RETURN_PC` | `0x8B1` |
| `DASICS_ACTIVE_ZONE_RETURN_PC` | `0x8B2` |
| `DASICS_FREASON` | `0x8B3` |
| `DASICS_U_MAIN_BOUND_LO` | `0x9E2` |
| `DASICS_U_MAIN_BOUND_HI` | `0x9E3` |
| `DASICS_S_MAIN_BOUND_LO` | `0xBC2` |
| `DASICS_S_MAIN_BOUND_HI` | `0xBC3` |
| `DASICS_U_MAIN_CFG` | `0x9E1` |
| `DASICS_S_MAIN_CFG` | `0xBC0` |
| `DASICS_LIB_CFG` | `0x880` |
| `DASICS_LIB_BOUND_LOi` (`i=0..15`) | `0x890 + 2*i` |
| `DASICS_LIB_BOUND_HIi` (`i=0..15`) | `0x891 + 2*i` |
| `DASICS_JUMP_CFG` | `0x8C8` |
| `DASICS_JUMP_BOUND_LOi` (`i=0..3`) | `0x8C0 + 2*i` |
| `DASICS_JUMP_BOUND_HIi` (`i=0..3`) | `0x8C1 + 2*i` |

There are 52 CSR addresses and 51 DASICS states. UMainCfg and SMainCfg share
MainCfg state, with read/write masks `0x3E` and `0x3FF`. Writes through the U
view preserve the S-only fields `0x3C1`.

| Field | Value |
| --- | --- |
| Build configuration | `USE_DASICS=y` |
| Simulator | `build/RISCV_DASICS/gem5.opt` |
| ISA | RV64 |
| Execution | Single hart, M-mode |
| CPU | `RiscvO3CPU` |
| Memory mode | `timing` |
| Model selection | `CPU=V2_minimal`, `V2_nanhug`, `V2_default`, `v5_full`, or `v5_stress`; default `v5_full` |
| Model parameters | [O3 model reference](../../../../configs/dasics/README.en.md) |
| Output directory | `build/m5out-o3/<CPU>/` under this test directory |
| System | Full-system bare metal |
| Exit mechanism | Semihosting |

`CPU=all` tests all models sequentially in the order above and prints
`-------------------------------` between models. After each model is
instantiated and before test execution, a list from the newly generated
`config.ini` shows the CPU type, frequency, VLEN, pipeline widths,
ROB/IQ/LQ/SQ capacities, and each cache level's capacity and associativity.
Detailed parameters remain in the model reference and `config.ini`.

Each model reports `system.cpu.numCycles` from the final statistics dump in
that run's `stats.txt`. Failed or timed-out runs and unavailable current
statistics show `N/A`, without using earlier runs' statistics. The count
includes startup and the entire CSR test; it does not represent DASICS
application performance overhead. A failed model does not stop the remaining
models. A final `CPU / Result / Cycles` table is printed, and any failure
makes Make return nonzero.

## Checks

After initializing `mtvec`, `_start` calls `test_csr_initial_values`,
`test_main_call_entry`, `test_return_pc`, `test_active_zone_return_pc`,
`test_freason`, `test_u_main_bound_lo`, `test_u_main_bound_hi`,
`test_s_main_bound_lo`, `test_s_main_bound_hi`, `test_u_main_cfg`,
`test_s_main_cfg`, and `test_lib_cfg` in order, then 32 functions from
`test_lib_bound_lo0`, `test_lib_bound_hi0` through `test_lib_bound_lo15`,
`test_lib_bound_hi15` in interleaved Lo/Hi order, followed by
`test_jump_cfg` and eight interleaved functions from `test_jump_bound_lo0`,
`test_jump_bound_hi0` through `test_jump_bound_lo3`, `test_jump_bound_hi3`.
Finally it calls `test_csr_independence`. A nonzero return exits immediately.
Each test is a leaf function returning `0` or a failure code
in `a0`; the single ELF, stack-free structure has no nested calls.
`DEFINE_BOUND_TEST` expands the 32 LibBound and eight JumpBound functions
at assembly time, with compile-time constant CSR numbers. The four
MainBound functions remain explicitly defined.

The first three, full-width CSR test functions each prepare
`P = 0xFEDCBA9876543217` and `Q = 0x0123456789ABCDE3` independently.
FReason separately checks low-three-bit read/write, zero reads of high bits,
exchange, bit setting, and bit clearing. The independence check also uses
`R = 0x89ABCDEF01234565` and sets FReason to `2`.
MainBound exchange checks use aligned values `PA = 0xFEDCBA9876543210`
and `QA = 0x0123456789ABCDE0`. LibCfg and JumpCfg also use
`~P = 0x0123456789ABCDE8` and preserve all 64 bits. JumpCfg V bits are at
positions 0/16/32/48; all other bits also read back unchanged. This test
does not check how validity bits are consumed. All checks run in
M-mode on `RiscvO3CPU` and cover existing CSR storage, access masks,
shared views, and independent state. Authorization, privilege transitions,
protection-enable effects, PC trust checks, and region enforcement are
outside this test's scope.

| Check | Expected result |
| --- | --- |
| Cold initialization | `test_csr_initial_values` reads all 52 addresses before any DASICS CSR write; each returns `0`. |
| Full 64-bit readback | Writing P to each of the first three CSRs reads back P unchanged, including the high 32 bits, bit 63, and low three bits. |
| CSRRW | Writing Q to each of the first three CSRs returns the old value P; a subsequent read returns Q. |
| FReason masking and exchange | After writing `-1`, readback is `7`; exchanging it for `-6` returns old value `7` and leaves `2`. Writes of `0` and `-8` both read back `0`. |
| FReason bit setting and clearing | Starting at `2`, CSRRS with source `-7` returns `2` and leaves `3`; CSRRC with the same source returns `3` and leaves `2`. |
| MainBound read/write | Each of the four functions checks aligned and unaligned writes, high-bit preservation, exchange, and low-bits-only input. Low three bits read as zero, writes round down, and exchange returns the aligned old value; inputs and failure codes appear below. |
| UMainCfg view interaction | `test_u_main_cfg` prepares shared state through S, then reads, writes, exchanges, sets, and clears through U. Only `0x3E` changes through U; S-only fields remain intact. Values and failure codes appear below. |
| SMainCfg view interaction | `test_s_main_cfg` prepares shared state independently, then reads, writes, exchanges, sets, and clears through S. S updates `0x3FF`; U always reads the `0x3E` view of shared state. |
| LibCfg read/write and exchange | Write P, exchange it for `~P`, and also write `0` and `-1`. Readback preserves P/`~P` in full, exchange returns old P, and writes of `0`/`-1` read back unchanged. |
| LibCfg bit setting and clearing | Starting at `~P`, CSRRS with source P returns `~P` and leaves `-1`; CSRRC with the same source returns `-1` and leaves `~P`. |
| LibBound read/write | Each of the 32 functions prepares its data: writing P reads PA; exchanging it for Q returns PA, followed by readback QA; writing `7` reads `0`. |
| JumpCfg read/write, exchange, and bit operations | Use the same P/`~P`, CSRRW, CSRRS, CSRRC, and writes of `0`/`-1` as LibCfg. All 64 bits are preserved, and old/new values match the corresponding LibCfg checks. |
| JumpBound read/write | Each of the eight functions prepares its data: writing P reads PA; exchanging it for Q returns PA, followed by readback QA; writing `7` reads `0`. |
| Independent storage | `test_csr_independence` prepares the original Q/P/R/2, four MainBound values `0x1000/0x2000/0x3000/0x4000`, and S=`0x155` plus U=`0x2A`. LibCfg=`0x13579BDF2468ACE1`, LibBound Lo_i=`0x10000 + 0x100*i`, and Hi_i=`0x10080 + 0x100*i`; JumpCfg=`0x2468ACE113579BD5`, JumpBound Lo_i=`0x20000 + 0x100*i`, and Hi_i=`0x20080 + 0x100*i`. Only after all 51 states have been written does it read all 52 views. Values remain intact, S reads `0x16B`, U reads `0x2A`, and setup does not rely on other functions' state. |

## Test exit codes

`Exit code:` reports the test process's raw exit code; GNU Make reports
overall success or failure with a zero or nonzero status.
Codes 1–4 apply to MainCallEntry; 6, 7, 9, and 10 to ReturnPC; 12–15 to
ActiveZoneReturnPC; 17–26 to FReason; and 8, 11, 16, and 27 to independent
storage. Code 5 remains reserved for unexpected exceptions.

| Exit code | Meaning | Terminal indicator |
| --- | --- | --- |
| `0` | All checks passed. | Green `[OK]` |
| `1` | The initial value was nonzero. | Red `[FAIL]` |
| `2` | Readback of P did not match. | Red `[FAIL]` |
| `3` | CSRRW did not return the old value P. | Red `[FAIL]` |
| `4` | The new value read after CSRRW was not Q. | Red `[FAIL]` |
| `5` | An unexpected exception occurred; `mcause` is retained in `a3`. | Red `[FAIL]` |
| `6` | The initial ReturnPC value was nonzero. | Red `[FAIL]` |
| `7` | ReturnPC readback after writing P did not match. | Red `[FAIL]` |
| `8` | MainCallEntry was not Q during the independence check. | Red `[FAIL]` |
| `9` | ReturnPC's CSRRW did not return the old value P. | Red `[FAIL]` |
| `10` | The new ReturnPC value read after CSRRW was not Q. | Red `[FAIL]` |
| `11` | ReturnPC was not P during the independence check. | Red `[FAIL]` |
| `12` | The initial ActiveZoneReturnPC value was nonzero. | Red `[FAIL]` |
| `13` | ActiveZoneReturnPC readback after writing P did not match. | Red `[FAIL]` |
| `14` | ActiveZoneReturnPC's CSRRW did not return the old value P. | Red `[FAIL]` |
| `15` | The new ActiveZoneReturnPC value read after CSRRW was not Q. | Red `[FAIL]` |
| `16` | ActiveZoneReturnPC was not R during the independence check. | Red `[FAIL]` |
| `17` | The initial FReason value was nonzero. | Red `[FAIL]` |
| `18` | FReason readback after writing `-1` was not `7`. | Red `[FAIL]` |
| `19` | FReason's CSRRW with input `-6` did not return old value `7`. | Red `[FAIL]` |
| `20` | FReason readback after the exchange was not `2`. | Red `[FAIL]` |
| `21` | FReason's CSRRS with source `-7` did not return old value `2`. | Red `[FAIL]` |
| `22` | FReason readback after setting bits was not `3`. | Red `[FAIL]` |
| `23` | FReason's CSRRC with source `-7` did not return old value `3`. | Red `[FAIL]` |
| `24` | FReason readback after clearing bits was not `2`. | Red `[FAIL]` |
| `25` | FReason readback after writing `0` was nonzero. | Red `[FAIL]` |
| `26` | FReason readback after writing `-8` was nonzero. | Red `[FAIL]` |
| `27` | FReason was not `2` during the independence check. | Red `[FAIL]` |
| `124` | The host timeout expired. | Red `[TIMEOUT]` |

The MainBound failure codes below all display red `[FAIL]`; original codes
1–27 retain their meanings.

| Check | UMainLo | UMainHi | SMainLo | SMainHi |
| --- | --- | --- | --- | --- |
| Initial value (read `0`) | `28` | `29` | `30` | `31` |
| Aligned write (`0x1000` → `0x1000`) | `32` | `38` | `44` | `50` |
| Unaligned write (`0x123F` → `0x1238`) | `33` | `39` | `45` | `51` |
| High-bit preservation (P → PA) | `34` | `40` | `46` | `52` |
| Exchange old value (write Q, return PA) | `35` | `41` | `47` | `53` |
| Exchange new value (read QA) | `36` | `42` | `48` | `54` |
| Low bits only (write `7`, read `0`) | `37` | `43` | `49` | `55` |
| Independent storage (read `0x1000/0x2000/0x3000/0x4000` respectively) | `56` | `57` | `58` | `59` |

MainCfg failure codes and expected values follow; all display red `[FAIL]`.
Original codes 1–59 retain their meanings. The old value is the CSR
instruction's return value; U/S identifies the read view.

| Group | Operation | Failure code: expected value |
| --- | --- | --- |
| Cold initialization | Read initial U/S values | `60`: U=`0`; `61`: S=`0` |
| U view | Seed S=`0x3FF`, then read U | `62`: U=`0x3E` |
| U view | Write U=`0` | `63`: U=`0`; `64`: S=`0x3C1` |
| U view | Write U=`-1` | `65`: U=`0x3E`; `66`: S=`0x3FF` |
| U view | Reset S=`0x155`, then CSRRW U=`0xAAAAAAAAAAAAAAAB` | `67`: old=`0x14`; `68`: U=`0x2A`; `69`: S=`0x16B` |
| U view | CSRRS with source `-1` | `70`: old=`0x2A`; `71`: U=`0x3E`; `72`: S=`0x17F` |
| U view | CSRRC with source `-1` | `73`: old=`0x3E`; `74`: U=`0`; `75`: S=`0x141` |
| S view | Write S=`-1` | `76`: S=`0x3FF`; `77`: U=`0x3E` |
| S view | CSRRW S=P | `78`: old=`0x3FF`; `79`: S=`0x217`; `80`: U=`0x16` |
| S view | CSRRS with source `-1` | `81`: old=`0x217`; `82`: S=`0x3FF`; `83`: U=`0x3E` |
| S view | CSRRC with source `-63` (low ten bits `0x3C1`) | `84`: old=`0x3FF`; `85`: S=`0x3E`; `86`: U=`0x3E` |
| S view | Write S=`0` | `87`: S=`0`; `88`: U=`0` |
| Independent storage | Prepare S=`0x155` and U=`0x2A`, then check both views | `89`: S=`0x16B`; `90`: U=`0x2A` |

New LibCfg failure codes follow; all display red `[FAIL]`. Original codes
1–90 retain their meanings, and `124` remains exclusive to the host timeout.

| Check | Failure code | Expected value |
| --- | --- | --- |
| Cold initialization | `91` | `0` |
| Readback after writing P | `125` | P |
| Old value from CSRRW writing `~P` | `126` | P |
| Readback after exchange | `127` | `~P` |
| Old value from CSRRS with source P | `128` | `~P` |
| Readback after setting bits | `129` | `-1` |
| Old value from CSRRC with source P | `130` | `-1` |
| Readback after clearing bits | `131` | `~P` |
| Readback after writing `0` | `132` | `0` |
| Readback after writing `-1` | `133` | `-1` |
| Independent storage | `166` | `0x13579BDF2468ACE1` |

For LibBound, `i=0..15`. The formulas give each CSR's failure code; all
display red `[FAIL]`.

| Check | Lo_i | Hi_i | Range |
| --- | --- | --- | --- |
| Cold initialization (read `0`) | `92 + 2*i` | `93 + 2*i` | 92–123 |
| Read/write (P→PA, exchange Q returning PA, read QA, write `7` reading `0`) | `134 + 2*i` | `135 + 2*i` | 134–165 |
| Independent storage (read each Lo_i/Hi_i expected value) | `167 + 2*i` | `168 + 2*i` | 167–198 |

Each LibBound read/write function shares one failure code across its four
assertions. The code identifies the CSR but not the individual assertion.

JumpCfg failure codes follow; all display red `[FAIL]`. Original codes
1–198 retain their meanings, and `124` remains exclusive to the host timeout.

| Check | Failure code | Expected value |
| --- | --- | --- |
| Cold initialization | `199` | `0` |
| Readback after writing P | `208` | P |
| Old value from CSRRW writing `~P` | `209` | P |
| Readback after exchange | `210` | `~P` |
| Old value from CSRRS with source P | `211` | `~P` |
| Readback after setting bits | `212` | `-1` |
| Old value from CSRRC with source P | `213` | `-1` |
| Readback after clearing bits | `214` | `~P` |
| Readback after writing `0` | `215` | `0` |
| Readback after writing `-1` | `216` | `-1` |
| Independent storage | `225` | `0x2468ACE113579BD5` |

For JumpBound, `i=0..3`. All failure codes below display red `[FAIL]`.

| Check | Lo_i | Hi_i | Range |
| --- | --- | --- | --- |
| Cold initialization (read `0`) | `200 + 2*i` | `201 + 2*i` | 200–207 |
| Read/write (P→PA, exchange Q returning PA, read QA, write `7` reading `0`) | `217 + 2*i` | `218 + 2*i` | 217–224 |
| Independent storage (read each Lo_i/Hi_i expected value) | `226 + 2*i` | `227 + 2*i` | 226–233 |

Each JumpBound read/write function also shares one failure code across its
four assertions, identifying the CSR only.

## Source links

- [O3 models and parameters](../../../../configs/dasics/README.en.md)
- [Assembly source](src/riscv-dasics-csr.S)
- [Makefile](src/Makefile)
