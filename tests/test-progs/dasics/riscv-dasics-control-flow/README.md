# riscv-dasics-control-flow

[English](README.en.md) | [复现命令](../../../../docs/dasics.md#riscv-dasics-control-flow)

## 测试范围

验证 RV64 非虚拟化 U/S 态 `JALR/JAL`、`BEQ/BNE/BLT/BGE/BLTU/BGEU` 的
DASICS 目标检查、M/S 异常委托和异常返回。使用单 hart O3、裸机全系统、
Bare 地址翻译和 Semihosting 退出。只有 80 个场景全部完成才以状态 `0` 退出。
本用例不覆盖压缩指令或 O3 错误路径。

正常场景指 JALR/JAL 目标获准，或条件分支不跳转；执行标记代码后通过普通 ECALL
返回 M 态。异常场景指 JALR/JAL 目标被拒绝，或条件分支跳向未授权目标；进入配置的
M/S handler，经 MRET/SRET 恢复到指定标签，再通过普通 ECALL 返回 M 态。

| 编号 | 探针 | 正常场景的 `(rs1, rs2)` | 异常场景的 `(rs1, rs2)` |
| --- | --- | --- | --- |
| 1–8 | JALR | 目标允许 | 目标拒绝 |
| 9–16 | BEQ | `(1, 0)` | `(0, 0)` |
| 17–24 | BNE | `(1, 1)` | `(1, 0)` |
| 25–32 | BLT | `(1, -1)` | `(-1, 1)` |
| 33–40 | BGE | `(-1, 1)` | `(1, -1)` |
| 41–48 | BLTU | `(-1, 1)` | `(1, -1)` |
| 49–56 | BGEU | `(1, -1)` | `(-1, 1)` |

每组八例的顺序均为：U→M 正常/异常、U→S 正常/异常、S→M 正常/异常、
S→S 正常/异常。箭头表示来源域和 DASICS 异常处理态；正常场景的普通 ECALL
始终进入 M 态。JALR 1–8、BEQ 9–16 的场景顺序保持不变。
`-1` 为 XLEN=64 的全 `1`，用于区分有符号与无符号比较。

相等边界单独覆盖以下四组；每组按 U→M、U→S、S→M、S→S 排列：

| 编号 | 探针 | `(rs1, rs2)` | 分支结果 | DASICS 异常 |
| --- | --- | --- | --- | --- |
| 57–60 | BLT | `(1, 1)` | 不跳转 | 无 |
| 61–64 | BGE | `(1, 1)` | 跳转 | 有 |
| 65–68 | BLTU | `(1, 1)` | 不跳转 | 无 |
| 69–72 | BGEU | `(1, 1)` | 跳转 | 有 |

末尾 73–80 为 JAL，按上述每组八例的顺序排列，各路由分别测试目标允许/拒绝。
已有 1–72 的编号保持不变。

## 配置与布局

- M 态关闭中断，设置直接模式 MTVEC/STVEC、Bare 翻译和 PMP TOR
  区间 `[0, 0x90000000)`，允许测试代码与数据的读、写、执行。
- MainCfg=`0x1DF`：UENA/SENA 均为 `1`，CUFT/CSFT 均为 `0`；
  关闭 U/S 的 ECALL、普通 load/store 检查，使测试框架聚焦控制流。
- UMainBound=`[0, 0)`；SMainBound 覆盖
  `[supervisor_trusted_begin, supervisor_trusted_end)`。
  S handler 的全部指令位于可信区，探针、目标及恢复代码位于区外。
- JumpBound0 使用当前探针描述的 `[target, end)`；仅 JALR/JAL 允许场景设置
  JumpCfg=`1`，其余场景均为 `0`。其余三组无效，三个特殊目标地址均为 `0`。
- 每个场景把 MEDELEG 精确写为 `0`、`1<<24` 或 `1<<25` 并检查读回。
  ECALL 对应位始终为 `0`。

JALR 共用 `jump_probe` 处的 `jalr ra, a1, 0`，输入为 `a1=beq_target|1`；
实际目标和故障 TVAL 均应为 `beq_target`。`jump_link` 是探针后一条指令的地址。
JALR、JAL 与 BEQ 共用 `beq_target`、标记代码、`beq_ecall` 和 `beq_end`。

JAL 使用 `jal_probe` 处的 `jal ra, beq_target`，由 PC 加立即数形成目标。
允许时 `ra=jal_link=jal_probe+4`；拒绝时 EPC=`jal_probe`、
TVAL=`beq_target`，`ra` 保持哨兵。链接地址处安排 ECALL/EBREAK，防止意外
顺序执行被当作成功。

`BRANCH_PROBE` 为每种条件分支生成独立的 `name_probe`、`name_target`、
标记代码和 `name_ecall`。探针使用 `a4/a5` 作为 `rs1/rs2`；各自目标
`name_target=name_probe+4`，并保持 8 字节对齐。所有条件分支目标均未授权。
顺序地址与跳转目标相同：不跳转时不应触发 DASICS 目标检查，跳转时必须触发。
由此检查实际分支结果，而非仅检查下一条指令地址是否改变。
所有指令使用非压缩编码；测试不使用 `call/ret`，以便核对 `ra`。

## 检查内容

| 状态 | 正常完成 | DASICS 拒绝目标 |
| --- | --- | --- |
| 首个异常 | ECALL：U 为 `8`，S 为 `9`，进入 M | DASICS：U 为 `24`，S 为 `25`，进入配置的 M/S handler |
| 首个 EPC | 当前目标的普通 ECALL 地址，见 `a7` | 当前探针 PC，见 `s11` |
| DASICS TVAL | 不适用 | 当前目标地址，见 `a6` |
| FReason | 保持哨兵 `5` | 更新为 `4`，恢复后的普通 ECALL 不再修改它 |
| `ra` | JALR 为 `jump_link`，JAL 为 `jal_link`；条件分支保持 `0xA5A5A5A5A5A5A5A5` | 保持 `0xA5A5A5A5A5A5A5A5` |
| 目标 GPR 与内存标记 | 均为 `0x1234` | 均保持 `0` |
| 恢复标记 | 保持 `0` | 返回 `resume_entry` 后变为 `0x5678` |
| DASICS 异常次数 | `0` | 恰好 `1` |

M handler 检查 MPP，S handler 检查 SPP，均须与来源域一致。
产生 DASICS 异常的路径将 MEPC/SEPC 设置为显式的 `resume_entry`，恢复后的
ECALL 还须位于 `resume_ecall`，来源特权级正确。
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

失败时通过 Semihosting `SYS_WRITE0` 向标准输出打印：

```text
DASICS control-flow: case=NN reason=NN
```

`case=01..80` 对应上述场景，失败退出码为该用例编号。初始化失败打印
`case=00` 并以 `255` 退出；成功退出码为 `0`。原因由消息中的 `reason`
单独给出，不编码在退出码中。

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

用例表每项 48 字节，六个 64 位字段依次为来源、委托、无 DASICS 异常完成标志、
探针类型、`rs1`、`rs2`。探针类型 `0..7` 依次表示
JALR、BEQ、BNE、BLT、BGE、BLTU、BGEU、JAL，`PROBE_JAL=7`。
独立的探针描述表含八项，每项包含五个字段：PC、目标、目标结束地址、普通 ECALL 地址、
正常完成时的 `ra`。M 态按类型读取这些预期状态，共享 handler 保留并核对它们。

`s0` 为用例表指针，`s1` 为用例编号，`s2/s3` 分别为来源和委托。
`s4` 为无 DASICS 异常完成标志：JALR/JAL 允许或条件分支不跳转时为 `1`，
JALR/JAL 拒绝或条件分支跳转时为 `0`。
`s5` 为阶段：`0` 配置、`1` 探针、`2` 恢复；`s6` 为已接受的 DASICS 异常数。
`s7/s8` 为目标/恢复标记，`s9` 指向目标内存标记。`s10` 为探针类型，
`s11` 为探针 PC；`a3` 为正常完成时预期的 `ra`，`a4/a5` 为比较输入，
`a6` 为故障目标，`a7` 为正常 ECALL PC。
`a2` 保存失败原因，打印后改为最终退出码。
