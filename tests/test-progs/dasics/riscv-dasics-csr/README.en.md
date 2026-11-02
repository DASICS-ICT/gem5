# riscv-dasics-csr

[中文版](README.md) | [Reproduction commands](../../../../docs/dasics.en.md#riscv-dasics-csr)

## Metadata

| CSR | Address |
| --- | --- |
| `DASICS_MAIN_CALL_ENTRY` | `0x8B0` |
| `DASICS_RETURN_PC` | `0x8B1` |
| `DASICS_ACTIVE_ZONE_RETURN_PC` | `0x8B2` |
| `DASICS_FREASON` | `0x8B3` |

| Field | Value |
| --- | --- |
| ISA | RV64 |
| Execution | Single hart, M-mode |
| CPU | `RiscvAtomicSimpleCPU` |
| System | Full-system bare metal |
| Exit mechanism | Semihosting |

## Checks

After initializing `mtvec`, `_start` calls `test_csr_initial_values`,
`test_main_call_entry`, `test_return_pc`, `test_active_zone_return_pc`,
`test_freason`, and `test_csr_independence` in order, exiting immediately on
a nonzero return value. Each test is a leaf function that returns `0` or a
unique error code in `a0`, without a stack or nested calls.

The first three, full-width CSR test functions each prepare
`P = 0xFEDCBA9876543217` and `Q = 0x0123456789ABCDE3` independently.
FReason separately checks low-three-bit read/write, zero reads of high bits,
exchange, bit setting, and bit clearing. The independence check also uses
`R = 0x89ABCDEF01234565` and sets FReason to `2`.

| Check | Expected result |
| --- | --- |
| Cold initialization | `test_csr_initial_values` reads all four initial values before any DASICS CSR write; each returns `0`. |
| Full 64-bit readback | Writing P to each of the first three CSRs reads back P unchanged, including the high 32 bits, bit 63, and low three bits. |
| CSRRW | Writing Q to each of the first three CSRs returns the old value P; a subsequent read returns Q. |
| FReason masking and exchange | After writing `-1`, readback is `7`; exchanging it for `-6` returns old value `7` and leaves `2`. Writes of `0` and `-8` both read back `0`. |
| FReason bit setting and clearing | Starting at `2`, CSRRS with source `-7` returns `2` and leaves `3`; CSRRC with the same source returns `3` and leaves `2`. |
| Independent storage | `test_csr_independence` writes MainCallEntry=Q, ReturnPC=P, ActiveZoneReturnPC=R, and FReason=2 itself, then reads all four in order. They return Q, P, R, and 2, with distinct low-three-bit values (3, 7, 5, 2), independently of other test functions' state. |

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
| `124` | The host timeout expired. | Red `[FAIL]` |

## Source links

- [Assembly source](src/riscv-dasics-csr.S)
- [Makefile](src/Makefile)

## Verified result

The historical result below comes from run output provided by the user and
covers only the original MainCallEntry checks.

| Field | Result |
| --- | --- |
| Date | 2026-11-02 |
| gem5 version | `26.0.0.0` |
| Final tick | `55000` |
| Exit code | `0` |
| Result | Passed |

The user confirmed validation of the current full test.
