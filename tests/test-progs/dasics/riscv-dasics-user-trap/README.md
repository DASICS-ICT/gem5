# riscv-dasics-user-trap

[English](README.en.md) | [复现命令](../../../../docs/dasics.md#riscv-dasics-user-trap)

## 测试范围

验证非虚拟化 RV64 U 态同步异常的 M/S/U 路由，以及 U 态 handler 经 URET
返回的完整流程。使用现有单 hart O3、MSU、裸机全系统配置，Bare 地址翻译、
PMP 放行和直接模式 UTVEC。全部 10 个场景完成后通过 Semihosting 返回 `0`。

| 探针 | 来源代码 | 首个 cause | 首个 TVAL | FReason |
| --- | --- | --- | --- | --- |
| 读取 MSTATUS | 可信 U 态 | `2` | 探针的原始 32 位指令编码 | 保持哨兵 `5` |
| ECALL | 非可信 U 态 | `24` | `0` | 更新为 `1` |

本用例不覆盖 U 态中断、虚拟化、M/U-only 直接委托、非法 URET、UTVEC 向量模式，
也不替代完整的 CSR 指令和访问权限测试。

## 场景表

下表的 MEDELEG、SEDELEG 均指当前探针 cause 对应的位。UPIE 初值与 UIE 相反，
用于区分入口保存与旧值残留。

| 编号 | 探针 | MEDELEG | SEDELEG 存储 | 处理态 | 初始 UIE / UPIE |
| --- | --- | --- | --- | --- | --- |
| 1 | 读取 MSTATUS | `0` | `0` | M | `1 / 0` |
| 2 | 读取 MSTATUS | `1` | `0` | S | `1 / 0` |
| 3 | 读取 MSTATUS | `1` | `1` | U | `1 / 0` |
| 4 | 读取 MSTATUS | `0` | `1` | M | `1 / 0` |
| 5 | ECALL | `0` | `0` | M | `1 / 0` |
| 6 | ECALL | `1` | `0` | S | `1 / 0` |
| 7 | ECALL | `1` | `1` | U | `1 / 0` |
| 8 | ECALL | `0` | `1` | M | `1 / 0` |
| 9 | 读取 MSTATUS | `1` | `1` | U | `0 / 1` |
| 10 | ECALL | `1` | `1` | U | `0 / 1` |

每例先清除 SEDELEG，再独立设置两级委托。场景 4、8 先设置 MEDELEG 和 SEDELEG，
再清除 MEDELEG，读回确认 SEDELEG 仍为 `1`。直接在 MEDELEG 为 `0` 时写入
SEDELEG 会被写掩码过滤，不能验证这项入口检查。

## 异常与返回

- M 态配置入口、PMP、边界和状态哨兵，再通过 MRET 进入 U 态探针。
  UENA/SENA 开启；U 态 ECALL 检查开启，普通访存和控制流检查关闭。
- U 可信区包含普通非法 CSR 探针、U handler、URET 和恢复点；ECALL 探针在区外。
  S 可信区包含 S handler 和 SRET，边界按 8 字节对齐。
- 首个异常必须恰好进入预期 handler 一次。检查 cause、精确 EPC、TVAL、FReason，
  并确认探针后的顺序路径未执行、可观察的 GPR 哨兵未被改写。
- U handler 检查 `UIE=0`、`UPIE=原 UIE`，将 UEPC 改为恢复点后执行 URET。
  恢复点检查 `UIE=原 UIE`、`UPIE=1`。
- M/S 路线分别通过 MRET/SRET 返回同一 U 态恢复点，U 态异常 CSR 和 UIE/UPIE
  应保持配置时的值。
- 恢复点设置完成标记，通过始终不委托的普通 EBREAK 回到 M 态。完成异常必须为
  cause `3`，EPC/TVAL 指向完成 EBREAK，来源为 U；随后检查恢复标记和保留状态。

URET 使用固定编码 `0x00200073`，U 态异常 CSR 使用数字地址，沿用现有工具链。
框架使用固定宽度指令和保留寄存器，不实现通用上下文保存恢复。

## 状态观测边界

完成 EBREAK 会覆盖 MEPC/MCAUSE/MTVAL，以及 MSTATUS 的部分字段，不能用这些
最终值证明 U 入口期间的全部 M 态状态保持。本用例检查未被完成异常覆盖的状态，
包括 M/S scratch、入口地址和适用的 S 态异常状态；M/S 路线还检查 U 态异常状态
未被借用。MRET 进入 U 时会清除 MPRV，本用例只检查 `MPRV=0` 的保持，不覆盖
`MPRV=1` 或 H 扩展状态。

## 构建与运行

```bash
make -C tests/test-progs/dasics/riscv-dasics-user-trap/src
make dasics-test TEST=riscv-dasics-user-trap CPU=all
```

ELF 位于 `build/riscv-dasics-user-trap.elf`，配置和统计位于
`build/m5out-o3/<CPU>/`。根 Makefile 自动发现本测试，无需增加独立目标。

## 诊断

失败时打印 `DASICS user-trap: case=NNN reason=NN`，退出码为用例编号
`1～10`；初始化失败以 `255` 退出，`124` 为宿主超时。

| reason | 检查失败 |
| --- | --- |
| 01 | MEDELEG 或 SEDELEG 读回 |
| 02 | MPP/SPP 来源特权级 |
| 03 | M/S/U 首个异常路由 |
| 04 | 执行阶段或首个异常次数 |
| 05 | cause |
| 06 | EPC |
| 07 | TVAL |
| 08 | FReason |
| 09 | `a0/a1/ra` 哨兵 |
| 10 | 意外执行探针后的顺序路径 |
| 11 | 异常返回或恢复标记 |
| 12 | 入口或恢复后的 UIE/UPIE |
| 13 | UCAUSE/UTVAL/UEPC |
| 14 | SCAUSE/STVAL/SEPC |
| 15 | U/S/M scratch 或 trap vector |
| 16 | MPRV |

`s1` 为用例编号，`s2` 为预期处理态，`s3` 为初始 USTATUS，`s4` 为预期 cause，
`s5` 为阶段，`s6` 为首个异常次数，`s7/s8` 为顺序路径/恢复标记。
`s9` 为预期 FReason，`s10/s11` 为探针 PC/TVAL；`t6` 保存失败原因。
表项为六个 64 位字段：探针 PC、cause、最终 MEDELEG 位、SEDELEG 存储位、
处理态、初始 USTATUS，共 48 字节。
