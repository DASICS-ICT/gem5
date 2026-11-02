# DASICS 使用说明

[English](dasics.en.md) | [仓库 README](../README.md)

命令均在仓库根目录执行。

## 编译

```bash
make riscv
```

## 清理

```bash
make clean
```

## 测试名单

| 测试 | 用例说明 | 复现 |
| --- | --- | --- |
| `riscv-dasics-csr` | [README](../tests/test-progs/dasics/riscv-dasics-csr/README.md) | [命令](#riscv-dasics-csr) |

## 测试复现

### riscv-dasics-csr

```bash
make dasics-test TEST=riscv-dasics-csr
```

#### 清理软件

```bash
make dasics-clean TEST=riscv-dasics-csr
```
