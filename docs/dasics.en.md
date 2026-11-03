# DASICS usage guide

[中文版](dasics.md)

All commands run from the repository root.

## Build

### Standard (`build/RISCV/gem5.opt`)

```bash
make riscv
```

### DASICS (`build/RISCV_DASICS/gem5.opt`)

```bash
make riscv-dasics
```

## Cleanup

### Standard (`build/RISCV/`)

```bash
make clean
```

### DASICS (`build/RISCV_DASICS/`)

```bash
make clean-riscv-dasics
```

## Test inventory

| Test | Description | Reproduction |
| --- | --- | --- |
| `riscv-dasics-csr` | [Test description](../tests/test-progs/dasics/riscv-dasics-csr/README.en.md) | [Run](#riscv-dasics-csr) |

## Test reproduction

### riscv-dasics-csr

```bash
make riscv-dasics &&
  make dasics-test TEST=riscv-dasics-csr
```

#### Clean software

```bash
make dasics-clean TEST=riscv-dasics-csr
```
