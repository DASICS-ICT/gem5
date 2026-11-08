# riscv-dasics-control-flow

[English](README.en.md) | [复现命令](../../../../docs/dasics.md#riscv-dasics-control-flow)

## 测试范围

验证 RV64 非虚拟化 U/S 态 `JALR`、`BEQ` 的 DASICS 目标检查、M/S 异常委托和异常返回。
使用单 hart O3、裸机全系统、Bare 地址翻译和 Semihosting 退出。
本用例不覆盖其他条件分支、压缩指令或 O3 错误路径。

| 编号 | 探针 | 来源 | DASICS 异常处理态 | 目标授权 | 分支结果 |
| --- | --- | --- | --- | --- | --- |
| 1 | JALR | U | M | 允许 | — |
| 2 | JALR | U | M | 拒绝 | — |
| 3 | JALR | U | S | 允许 | — |
| 4 | JALR | U | S | 拒绝 | — |
| 5 | JALR | S | M | 允许 | — |
| 6 | JALR | S | M | 拒绝 | — |
| 7 | JALR | S | S | 允许 | — |
| 8 | JALR | S | S | 拒绝 | — |
| 9 | BEQ | U | M | 拒绝 | 不跳转 |
| 10 | BEQ | U | M | 拒绝 | 跳转 |
| 11 | BEQ | U | S | 拒绝 | 不跳转 |
| 12 | BEQ | U | S | 拒绝 | 跳转 |
| 13 | BEQ | S | M | 拒绝 | 不跳转 |
| 14 | BEQ | S | M | 拒绝 | 跳转 |
| 15 | BEQ | S | S | 拒绝 | 不跳转 |
| 16 | BEQ | S | S | 拒绝 | 跳转 |

JALR 允许场景与 BEQ 不跳转场景不产生 DASICS 异常，执行标记代码后通过
普通 ECALL 返回 M 态。JALR 拒绝场景与 BEQ 跳转场景先进入配置的 M/S
handler，经 MRET/SRET 恢复到指定标签，再通过普通 ECALL 返回 M 态。
只有十六个场景全部完成才以状态 `0` 退出。

## 配置与布局

- M 态关闭中断，设置直接模式 MTVEC/STVEC、Bare 翻译和 PMP TOR
  区间 `[0, 0x90000000)`，允许测试代码与数据的读、写、执行。
- MainCfg=`0x1DF`：UENA/SENA 均为 `1`，CUFT/CSFT 均为 `0`；
  关闭 U/S 的 ECALL、普通 load/store 检查，使测试框架聚焦控制流。
- UMainBound=`[0, 0)`；SMainBound 覆盖
  `[supervisor_trusted_begin, supervisor_trusted_end)`。
  S handler 的全部指令位于可信区，探针、目标及恢复代码位于区外。
- JumpBound0=`[target_entry, target_end)`；JALR 允许场景的 JumpCfg=`1`，
  其余场景为 `0`。其余三组无效，三个特殊目标地址均为 `0`。
- 每个场景把 MEDELEG 精确写为 `0`、`1<<24` 或 `1<<25` 并检查读回。
  ECALL 对应位始终为 `0`。

前八个场景共用 `jump_probe` 处的 `jalr ra, a1, 0`。
输入 `a1=target_entry|1`，实际目标和故障 TVAL 均应为 `target_entry`。
所有指令使用非压缩编码；`jump_link` 是探针后一条指令的地址。
测试不使用 `call/ret`，使 `ra` 在 handler 中和返回后均可直接检查。

后八个场景共用 `beq_probe` 处的 `beq s4, zero, target_entry`。
`target_entry` 紧跟探针，地址为 `beq_probe+4`；不跳转时的顺序地址与跳转目标
相同，且该地址未授权。`s4=1` 时不跳转，不应触发 DASICS 目标检查；
`s4=0` 时跳转，必须触发 DASICS 异常。由此检查实际分支结果，而非仅检查
下一条指令地址是否改变。BEQ 与 JALR 共用目标代码、标记及 `target_ecall`；
探针前的 NOP 布局使 `target_entry` 保持 8 字节对齐。

## 检查内容

JALR 检查：

| 状态 | 允许目标 | 拒绝目标 |
| --- | --- | --- |
| 首个异常 | ECALL：U 为 `8`，S 为 `9`，进入 M | DASICS：U 为 `24`，S 为 `25`，进入配置的 M/S handler |
| 首个 EPC | `target_ecall` | `jump_probe` |
| DASICS TVAL | 不适用 | `target_entry` |
| FReason | 保持哨兵 `5` | 更新为 `4`，恢复后的普通 ECALL 不再修改它 |
| `ra` | `jump_link` | 保持 `0xA5A5A5A5A5A5A5A5` |
| 目标 GPR 与内存标记 | 均为 `0x1234` | 均保持 `0` |
| 恢复标记 | 保持 `0` | 返回 `resume_entry` 后变为 `0x5678` |
| DASICS 异常次数 | `0` | 恰好 `1` |

BEQ 检查：

| 状态 | 不跳转 | 跳转 |
| --- | --- | --- |
| 首个异常 | ECALL：U 为 `8`，S 为 `9`，进入 M | DASICS：U 为 `24`，S 为 `25`，进入配置的 M/S handler |
| 首个 EPC | `target_ecall` | `beq_probe` |
| DASICS TVAL | 不适用 | `target_entry` |
| FReason | 保持哨兵 `5` | 更新为 `4`，恢复后的普通 ECALL 不再修改它 |
| `ra` | 保持 `0xA5A5A5A5A5A5A5A5` | 保持 `0xA5A5A5A5A5A5A5A5` |
| 目标 GPR 与内存标记 | 均为 `0x1234` | 均保持 `0` |
| 恢复标记 | 保持 `0` | 返回 `resume_entry` 后变为 `0x5678` |
| DASICS 异常次数 | `0` | 恰好 `1` |

M handler 检查 MPP，S handler 检查 SPP，均须与来源域一致。
产生 DASICS 异常的路径将 MEPC/SEPC 设置为显式的 `resume_entry`，恢复后的 ECALL
还须位于 `resume_ecall`，来源特权级正确。
S handler 检查失败时通过 `supervisor_failure_ecall` 返回 M 态报告错误。

目标内存标记检查的是架构可见副作用，不证明目标未被推测取指或执行。

## 软件构建

在仓库根目录执行：

```bash
make -C tests/test-progs/dasics/riscv-dasics-control-flow/src
```

产物为 `build/riscv-dasics-control-flow.elf`，仿真输出位于本测试目录的
`build/m5out-o3/<CPU>/`。运行前需重新构建包含控制流检查的 DASICS 版 gem5。

## 诊断

非零退出码为 `case_id * 15 + reason`；`case_id=1..16` 对应上表，
`case_id=0` 表示初始化阶段。`reason=1..12`，最大退出码为 `252`，可由
8 位进程退出状态完整表示。

| reason | 检查失败 |
| --- | --- |
| 1 | MEDELEG 读回 |
| 2 | MPP/SPP 来源特权级 |
| 3 | M/S 异常路由 |
| 4 | 执行阶段、是否应产生 DASICS 异常的预期或异常次数 |
| 5 | cause |
| 6 | EPC |
| 7 | TVAL |
| 8 | FReason |
| 9 | link/`ra` |
| 10 | 目标 GPR 标记 |
| 11 | 目标内存标记 |
| 12 | 恢复标记 |

用例表每项 32 字节，四个 64 位字段依次为来源、委托、无 DASICS 异常完成标志、
探针类型（`0` 为 JALR，`1` 为 BEQ）。

`s0` 为用例表指针，`s1` 为用例编号，`s2/s3` 分别为来源和委托。
`s4` 为无 DASICS 异常完成标志：JALR 允许或 BEQ 不跳转时为 `1`，
JALR 拒绝或 BEQ 跳转时为 `0`。
`s5` 为阶段：`0` 配置、`1` 探针、`2` 恢复；`s6` 为已接受的 DASICS 异常数。
`s7/s8` 为目标/恢复标记，`s9` 指向目标内存标记。`s10` 为探针类型，
`s11` 为探针 PC，`a3` 为探针成功后预期的 `ra`（JALR link 或 BEQ 哨兵）。
这些预期值由 M 态配置，handler 保留。
`a2` 保存失败原因及最终退出码。
