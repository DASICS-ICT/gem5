# riscv-dasics-csr

[English](README.en.md) | [复现命令](../../../../docs/dasics.md#riscv-dasics-csr)

## 测试配置

| 项目 | 值 |
| --- | --- |
| 目标 CSR | `DASICS_MAIN_CALL_ENTRY` |
| CSR 地址 | `0x8B0` |
| 架构 | RV64 |
| hart 数量 | 1 |
| 特权级 | M 态 |
| CPU | `RiscvAtomicSimpleCPU` |
| 运行方式 | 裸机全系统 |
| 退出接口 | Semihosting |

## 检查项

| 用例 | 操作 | 预期结果 |
| --- | --- | --- |
| 冷初始化 | 首次读取 CSR | 返回 `0` |
| 64 位读写 | 写入 `P = 0xFEDCBA9876543217` 后读回 | 完整返回 P，包含高 32 位、bit 63 和低 3 位 |
| 读写交换 | 使用 `CSRRW` 写入 `Q = 0x0123456789ABCDE3`，随后读取 | `CSRRW` 返回旧值 P，后续读取返回 Q |

## 测试退出码

`Exit code:` 为测试进程的原始退出码；GNU Make 自身以 0/非 0 报告整体成功或失败。

| 测试退出码 | 含义 | 终端提示 |
| --- | --- | --- |
| `0` | 全部断言通过 | 绿色 `[OK]` |
| `1` | 冷初始化值非零 | 红色 `[FAIL]` |
| `2` | 写入 P 后读回不一致 | 红色 `[FAIL]` |
| `3` | `CSRRW` 返回的旧值不等于 P | 红色 `[FAIL]` |
| `4` | `CSRRW` 写入后读回的新值不等于 Q | 红色 `[FAIL]` |
| `5` | 意外异常；`mcause` 保留在 `a3` 中 | 红色 `[FAIL]` |
| `124` | 宿主运行超时 | 红色 `[FAIL]` |

## 源码

- [汇编程序](src/riscv-dasics-csr.S)
- [Makefile](src/Makefile)

## 验证结果

证据：用户提供的运行输出。

| 项目 | 记录 |
| --- | --- |
| 日期 | 2026-11-02 |
| gem5 版本 | `26.0.0.0` |
| 结束 tick | `55000` |
| 退出码 | `0` |
| 结果 | 通过 |
