# DASICS usage guide

[中文版](dasics.md)

All commands run from the repository root.

[O3 models and parameters](../configs/dasics/README.en.md)

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
| `riscv-dasics-csr-permission` | [Test description](../tests/test-progs/dasics/riscv-dasics-csr-permission/README.en.md) | [Run](#riscv-dasics-csr-permission) |

## Test reproduction

### riscv-dasics-csr

```bash
make riscv-dasics &&
  make dasics-test TEST=riscv-dasics-csr CPU=v5_full
```

```bash
make dasics-test TEST=riscv-dasics-csr CPU=V2_minimal
make dasics-test TEST=riscv-dasics-csr CPU=V2_nanhug
make dasics-test TEST=riscv-dasics-csr CPU=V2_default
make dasics-test TEST=riscv-dasics-csr CPU=v5_stress
```

```bash
make dasics-test TEST=riscv-dasics-csr CPU=all
```

#### Clean software

```bash
make dasics-clean TEST=riscv-dasics-csr
```

### riscv-dasics-csr-permission

```bash
make riscv-dasics &&
  make dasics-test TEST=riscv-dasics-csr-permission CPU=v5_full
```

```bash
make dasics-test TEST=riscv-dasics-csr-permission CPU=all
```

#### Clean software

```bash
make dasics-clean TEST=riscv-dasics-csr-permission
```
