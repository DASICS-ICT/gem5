# riscv-dasics-csr

[中文版](README.md) | [Reproduction commands](../../../../docs/dasics.en.md#riscv-dasics-csr)

## Metadata

| Field | Value |
| --- | --- |
| Target | `DASICS_MAIN_CALL_ENTRY` |
| CSR address | `0x8B0` |
| ISA | RV64 |
| Execution | Single hart, M-mode |
| CPU | `RiscvAtomicSimpleCPU` |
| System | Full-system bare metal |
| Exit mechanism | Semihosting |

## Checks

| Check | Expected result |
| --- | --- |
| Cold initialization | The first CSR read returns `0`. |
| Full 64-bit readback | Writing `P = 0xFEDCBA9876543217` reads back P unchanged, including its high bits and low three bits. |
| CSRRW | Writing `Q = 0x0123456789ABCDE3` returns the old value P; a subsequent read returns Q. |

## Test exit codes

`Exit code:` reports the test process's raw exit code; GNU Make reports
overall success or failure with a zero or nonzero status.

| Exit code | Meaning | Terminal indicator |
| --- | --- | --- |
| `0` | All checks passed. | Green `[OK]` |
| `1` | The initial value was nonzero. | Red `[FAIL]` |
| `2` | Readback of P did not match. | Red `[FAIL]` |
| `3` | CSRRW did not return the old value P. | Red `[FAIL]` |
| `4` | The new value read after CSRRW was not Q. | Red `[FAIL]` |
| `5` | An unexpected exception occurred; `mcause` is retained in `a3`. | Red `[FAIL]` |
| `124` | The host timeout expired. | Red `[FAIL]` |

## Source links

- [Assembly source](src/riscv-dasics-csr.S)
- [Makefile](src/Makefile)

## Verified result

The result below comes from run output provided by the user.

| Field | Result |
| --- | --- |
| Date | 2026-11-02 |
| gem5 version | `26.0.0.0` |
| Final tick | `55000` |
| Exit code | `0` |
| Result | Passed |
