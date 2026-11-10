# DASICS 使用说明

[English](dasics.en.md) | [仓库 README](../README.md)

命令均在仓库根目录执行。

[O3 模型与参数](../configs/dasics/README.md)

## 编译

### 普通版（`build/RISCV/gem5.opt`）

```bash
make riscv
```

### DASICS 版（`build/RISCV_DASICS/gem5.opt`）

```bash
make riscv-dasics
```

## 清理

### 普通版（`build/RISCV/`）

```bash
make clean
```

### DASICS 版（`build/RISCV_DASICS/`）

```bash
make clean-riscv-dasics
```

## 测试名单

| 测试 | 用例说明 | 复现 |
| --- | --- | --- |
| `riscv-dasics-csr` | [README](../tests/test-progs/dasics/riscv-dasics-csr/README.md) | [命令](#riscv-dasics-csr) |
| `riscv-dasics-csr-permission` | [README](../tests/test-progs/dasics/riscv-dasics-csr-permission/README.md) | [命令](#riscv-dasics-csr-permission) |
| `riscv-dasics-control-flow` | [README](../tests/test-progs/dasics/riscv-dasics-control-flow/README.md) | [命令](#riscv-dasics-control-flow) |
| `riscv-dasics-mem` | [README](../tests/test-progs/dasics/riscv-dasics-mem/README.md) | [命令](#riscv-dasics-mem) |

## 测试复现

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

#### 清理软件

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

#### 清理软件

```bash
make dasics-clean TEST=riscv-dasics-csr-permission
```

### riscv-dasics-control-flow

```bash
make riscv-dasics &&
  make dasics-test TEST=riscv-dasics-control-flow CPU=v5_full
```

```bash
make dasics-test TEST=riscv-dasics-control-flow CPU=all
```

#### 清理软件

```bash
make dasics-clean TEST=riscv-dasics-control-flow
```

### riscv-dasics-mem

```bash
make riscv-dasics &&
  make dasics-test TEST=riscv-dasics-mem CPU=v5_full
```

```bash
make dasics-test TEST=riscv-dasics-mem CPU=all
```

#### 清理软件

```bash
make dasics-clean TEST=riscv-dasics-mem
```
