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
| `riscv-dasics-ecall` | [README](../tests/test-progs/dasics/riscv-dasics-ecall/README.md) | [命令](#riscv-dasics-ecall) |
| `riscv-dasics-control-flow` | [README](../tests/test-progs/dasics/riscv-dasics-control-flow/README.md) | [命令](#riscv-dasics-control-flow) |
| `riscv-dasics-call` | [README](../tests/test-progs/dasics/riscv-dasics-call/README.md) | [命令](#riscv-dasics-call) |
| `riscv-dasics-mem` | [README](../tests/test-progs/dasics/riscv-dasics-mem/README.md) | [命令](#riscv-dasics-mem) |

## 测试复现

### 全部功能测试（默认 `CPU=v5_full`）

```bash
make riscv-dasics &&
  make dasics-test
```

### 全部功能测试 × 全部 CPU

```bash
make dasics-test CPU=all
```

自动发现 `tests/test-progs/dasics/riscv-dasics-*/src/Makefile`；新增同结构测试
并提供 `all/run/clean` 目标即可纳入，`riscv-reg-protection` 实验除外。
失败或超时后继续其余项目，全部通过才返回 `0`。

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

### riscv-dasics-ecall

```bash
make riscv-dasics &&
  make dasics-test TEST=riscv-dasics-ecall CPU=v5_full
```

```bash
make dasics-test TEST=riscv-dasics-ecall CPU=all
```

#### 清理软件

```bash
make dasics-clean TEST=riscv-dasics-ecall
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

### riscv-dasics-call

```bash
make riscv-dasics &&
  make dasics-test TEST=riscv-dasics-call CPU=v5_full
```

```bash
make dasics-test TEST=riscv-dasics-call CPU=all
```

#### 清理软件

```bash
make dasics-clean TEST=riscv-dasics-call
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
