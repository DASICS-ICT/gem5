# riscv-dasics-csr

[English](README.en.md) | [复现命令](../../../../docs/dasics.md#riscv-dasics-csr)

## 测试配置

| CSR | 地址 |
| --- | --- |
| `DASICS_MAIN_CALL_ENTRY` | `0x8B0` |
| `DASICS_RETURN_PC` | `0x8B1` |
| `DASICS_ACTIVE_ZONE_RETURN_PC` | `0x8B2` |
| `DASICS_FREASON` | `0x8B3` |

| 项目 | 值 |
| --- | --- |
| 架构 | RV64 |
| hart 数量 | 1 |
| 特权级 | M 态 |
| CPU | `RiscvAtomicSimpleCPU` |
| 运行方式 | 裸机全系统 |
| 退出接口 | Semihosting |

## 检查项

`_start` 初始化 `mtvec` 后，依次调用 `test_csr_initial_values`、
`test_main_call_entry`、`test_return_pc`、`test_active_zone_return_pc`、`test_freason`、`test_csr_independence`，遇非零返回值立即退出。
各测试均为叶函数，通过 `a0` 返回 `0` 或唯一错误码，不使用栈或嵌套调用。

前三个全 64 位 CSR 的测试函数各自准备 `P = 0xFEDCBA9876543217` 和 `Q = 0x0123456789ABCDE3`。
FReason 单独验证低 3 位读写、高位读零及交换、置位和清位。
独立性检查另用 `R = 0x89ABCDEF01234565`，并将 FReason 设为 `2`。

| 用例 | 操作 | 预期结果 |
| --- | --- | --- |
| 冷初始化 | `test_csr_initial_values` 在任何 DASICS CSR 写入前读取四个初值 | 各自返回 `0` |
| 64 位读写 | 前三个 CSR 分别写入 P 后读回 | 各自完整返回 P，包含高 32 位、bit 63 和低 3 位 |
| 读写交换 | 前三个 CSR 分别使用 `CSRRW` 写入 Q，随后读取 | 各自返回旧值 P，后续读取返回 Q |
| FReason 掩码与交换 | 写入 `-1` 后读回，再用 `CSRRW` 写入 `-6`；另检查写入 `0` 和 `-8` | 初次读回 `7`，交换返回旧值 `7`、新值为 `2`；写入 `0` 和 `-8` 均读回 `0` |
| FReason 置位与清位 | 值为 `2` 时以 `-7` 为源执行 `CSRRS`，随后用同一源执行 `CSRRC` | 置位返回旧值 `2`、新值 `3`；清位返回旧值 `3`、新值 `2` |
| 存储独立性 | `test_csr_independence` 自行写入 MainCallEntry=Q、ReturnPC=P、ActiveZoneReturnPC=R、FReason=2，再依次读取四者 | 分别为 Q、P、R、2，低 3 位也互异（3、7、5、2），不依赖其他函数状态 |

## 测试退出码

`Exit code:` 为测试进程的原始退出码；GNU Make 自身以 0/非 0 报告整体成功或失败。
退出码 1–4 对应 MainCallEntry，6、7、9、10 对应 ReturnPC，12–15 对应 ActiveZoneReturnPC，17–26 对应 FReason，8、11、16、27 对应存储独立性；5 保留为意外异常。

| 测试退出码 | 含义 | 终端提示 |
| --- | --- | --- |
| `0` | 全部断言通过 | 绿色 `[OK]` |
| `1` | 冷初始化值非零 | 红色 `[FAIL]` |
| `2` | 写入 P 后读回不一致 | 红色 `[FAIL]` |
| `3` | `CSRRW` 返回的旧值不等于 P | 红色 `[FAIL]` |
| `4` | `CSRRW` 写入后读回的新值不等于 Q | 红色 `[FAIL]` |
| `5` | 意外异常；`mcause` 保留在 `a3` 中 | 红色 `[FAIL]` |
| `6` | ReturnPC 冷初始化值非零 | 红色 `[FAIL]` |
| `7` | ReturnPC 写入 P 后读回不一致 | 红色 `[FAIL]` |
| `8` | 独立性检查中，MainCallEntry 不等于 Q | 红色 `[FAIL]` |
| `9` | ReturnPC 的 `CSRRW` 返回旧值不等于 P | 红色 `[FAIL]` |
| `10` | ReturnPC 的 `CSRRW` 写入后读回新值不等于 Q | 红色 `[FAIL]` |
| `11` | 独立性检查中，ReturnPC 不等于 P | 红色 `[FAIL]` |
| `12` | ActiveZoneReturnPC 冷初始化值非零 | 红色 `[FAIL]` |
| `13` | ActiveZoneReturnPC 写入 P 后读回不一致 | 红色 `[FAIL]` |
| `14` | ActiveZoneReturnPC 的 `CSRRW` 返回旧值不等于 P | 红色 `[FAIL]` |
| `15` | ActiveZoneReturnPC 的 `CSRRW` 写入后读回新值不等于 Q | 红色 `[FAIL]` |
| `16` | 独立性检查中，ActiveZoneReturnPC 不等于 R | 红色 `[FAIL]` |
| `17` | FReason 冷初始化值非零 | 红色 `[FAIL]` |
| `18` | FReason 写入 `-1` 后读回不等于 `7` | 红色 `[FAIL]` |
| `19` | FReason 的 `CSRRW` 写入 `-6` 时返回旧值不等于 `7` | 红色 `[FAIL]` |
| `20` | FReason 交换后读回不等于 `2` | 红色 `[FAIL]` |
| `21` | FReason 的 `CSRRS` 使用源 `-7` 时返回旧值不等于 `2` | 红色 `[FAIL]` |
| `22` | FReason 置位后读回不等于 `3` | 红色 `[FAIL]` |
| `23` | FReason 的 `CSRRC` 使用源 `-7` 时返回旧值不等于 `3` | 红色 `[FAIL]` |
| `24` | FReason 清位后读回不等于 `2` | 红色 `[FAIL]` |
| `25` | FReason 写入 `0` 后读回非零 | 红色 `[FAIL]` |
| `26` | FReason 写入 `-8` 后读回非零 | 红色 `[FAIL]` |
| `27` | 独立性检查中，FReason 不等于 `2` | 红色 `[FAIL]` |
| `124` | 宿主运行超时 | 红色 `[FAIL]` |

## 源码

- [汇编程序](src/riscv-dasics-csr.S)
- [Makefile](src/Makefile)

## 验证结果

以下历史结果来自用户提供的运行输出，仅覆盖原 MainCallEntry 检查。

| 项目 | 记录 |
| --- | --- |
| 日期 | 2026-11-02 |
| gem5 版本 | `26.0.0.0` |
| 结束 tick | `55000` |
| 退出码 | `0` |
| 结果 | 通过 |

当前完整测试已由用户完成验证。
