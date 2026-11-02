# DASICS usage guide

[中文版](dasics.md)

All commands run from the repository root.

## Build

```bash
make riscv
```

## Cleanup

```bash
make clean
```

## Test inventory

| Test | Description | Reproduction |
| --- | --- | --- |
| `riscv-dasics-csr` | [Test description](../tests/test-progs/dasics/riscv-dasics-csr/README.en.md) | [Run](#riscv-dasics-csr) |

## Test reproduction

### riscv-dasics-csr

```bash
make dasics-test TEST=riscv-dasics-csr
```

#### Clean software

```bash
make dasics-clean TEST=riscv-dasics-csr
```
