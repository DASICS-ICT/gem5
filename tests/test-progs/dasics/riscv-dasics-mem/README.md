# riscv-dasics-mem

[English](README.en.md) | [复现命令](../../../../docs/dasics.md#riscv-dasics-mem)

## 测试范围

验证 RV64 普通标量访存的 DASICS 数据边界、权限、旁路条件、异常路由和异常返回。
配置为单 hart O3、裸机全系统、Bare 地址翻译和 Semihosting 退出。
当前 [O3 模型](../../../../configs/dasics/README.md)使用 `RVA20S64`，
额外启用 `Zba/Zbb/Zbc/Zbs/V`；本用例覆盖 27 种整数、F/D 和 RV64C 访存指令。
只有全部 226 个场景完成才以状态 `0` 退出。

Zfh、Zcb 和仅适用于 RV32 的形式未纳入运行测试。AMO、LR/SC、向量访存、
预取、Hypervisor、CBO、分页页故障及 O3 错误路径不在本用例范围内。

## 场景分组

前 108 例按以下探针顺序排列。指令索引为 `i` 时，`4*i+1..4*i+4` 依次为
U 允许、U 拒绝、S 允许、S 拒绝；U 异常进入 M，S 异常进入 S。

| 指令索引 | 探针顺序 |
| --- | --- |
| 0–6 | `lb, lbu, lh, lhu, lw, lwu, ld` |
| 7–10 | `sb, sh, sw, sd` |
| 11–14 | `flw, fld, fsw, fsd` |
| 15–20 | `c.lw, c.ld, c.fld, c.sw, c.sd, c.fsd` |
| 21–26 | `c.lwsp, c.ldsp, c.fldsp, c.swsp, c.sdsp, c.fsdsp` |

| 编号 | 检查 |
| --- | --- |
| 1–108 | 27 种指令各四例：U 允许/U 拒绝（异常进入 M）、S 允许/S 拒绝（异常进入 S） |
| 109–116 | `ld/sd` 补充 U→S、S→M 的允许/拒绝路由 |
| 117–118 | M 态绕过 DASICS 数据检查 |
| 119–126 | 本域 enable 关闭时允许；关闭另一域不能绕过本域检查 |
| 127–134 | 对应 load/store close 位允许；另一操作的 close 位不能绕过检查 |
| 135–138 | 另一域的同类 close 位不能绕过检查 |
| 139–142 | 可信 PC 绕过数据检查 |
| 143–154 | R/W 权限隔离、U 保留位和无效 V 位 |
| 155–178 | 空区间、反转区间、下界外、上界外、末字节恰好在区间内、跨上界 |
| 179–182 | 边界 CSR 低三位掩码 |
| 183–186 | 高位虚拟地址拒绝时保留原始 TVAL |
| 187–218 | `ld/sd/fld/fsd` 在 U/S 态组合 DASICS 拒绝/允许与 misalignment/PMP 拒绝 |
| 219–222 | 相邻的两组边界不能拼接授权一次访问 |
| 223–226 | 索引 15 的边界组读写授权 |

## 检查契约

- M 态配置异常入口、PMP、MainCfg/MainBound 和 LibCfg/LibBound，再进入
  指定来源域执行探针。异常通过 M/S handler 检查并恢复。
- 非可信 U/S 访问需要同一有效边界组覆盖全部访问字节，并具备相应 R/W 权限；
  边界为 `[lo, hi)`。U 保留位不授予读写权限。
- M 态、可信 PC、本域 enable 关闭或本域相应 load/store close 位可以绕过
  DASICS 数据检查；另一域或另一操作的开关不能代替对应配置。
- 拒绝时检查来源域、M/S 路由、cause、EPC、原始有效地址 TVAL、FReason、
  目的寄存器和目标内存的架构状态，以及异常恢复后的标记。
- 每例把 GPR 目的寄存器 `a0` 设为 `0x0123456789ABCDEF`，浮点目的寄存器
  `fa0` 设为 `0x8877665544332211`，64 字节测试内存逐字节设为 `0xF1`。
  拒绝或普通故障时，目的寄存器和全部测试内存均应保持初值。
- 允许的整数 load 按位宽检查有/无符号扩展；FLW 检查 NaN-boxing 后的
  `0xFFFFFFFFF1F1F1F1`，FLD 及其压缩形式检查 `0xF1F1F1F1F1F1F1F1`。
  整数 store 源为 `0x0807060504030201`，浮点 store 源为
  `0x1817161514131211`；按访问宽度检查写入字节，其他字节保持 `0xF1`。
- 每例从 FS=`Clean(2)` 开始；允许的浮点 load 变为 `Dirty(3)`，其余场景
  保持 `Clean(2)`。M handler 在用 `fmv.x.d` 读取浮点目的值前检查 FS，
  S handler 不执行浮点指令。
- DASICS 拒绝时，U/S cause 分别为 `24/25`，FReason 为 load=`2`、store=`3`，
  EPC 为故障探针 PC，TVAL 为原始有效地址。正常完成及普通故障保持 FReason
  哨兵 `5`；完成 ECALL 不委托到 S，异常恢复经 `resume_entry/resume_ecall`。

本轮 gem5 实现选择先进行 DASICS 检查，再进行 alignment/PMP 检查。
冲突场景通过异常 cause 区分该顺序：DASICS 拒绝应保持 DASICS 异常，允许后
才暴露普通 alignment/PMP 异常。这是当前实现的优先策略；本用例未用请求轨迹
证明 TLB 或内存请求完全没有发出。内存标记仅检查架构可见副作用。

| DASICS 结果 | 后续条件 | load cause | store cause |
| --- | --- | --- | --- |
| 拒绝 | 地址未对齐或 PMP 拒绝 | U=`24`、S=`25` | U=`24`、S=`25` |
| 允许 | 地址未对齐 | `4` | `6` |
| 允许 | PMP 拒绝 | `5` | `7` |

## 软件构建

在仓库根目录执行：

```bash
make -C tests/test-progs/dasics/riscv-dasics-mem/src
```

产物为本测试目录的 `build/riscv-dasics-mem.elf`；仿真输出位于
`build/m5out-o3/<CPU>/`。运行命令见[使用说明](../../../../docs/dasics.md#riscv-dasics-mem)。

## 诊断

失败时通过 Semihosting `SYS_WRITE0` 打印：

```text
DASICS memory: case=NNN reason=NN
```

`case=001..226` 对应上述场景。失败退出码在 `case<124` 时等于编号，
在 `case>=124` 时等于 `case+1`，即后半段使用 `125..227`；`124` 保留为
宿主超时。初始化失败打印 `case=000` 并以 `255` 退出。
`reason=01..14` 单独报告检查失败原因，消息中的用例编号不受退出码映射影响。

| reason | 检查失败 |
| --- | --- |
| 01 | MEDELEG 读回 |
| 02 | MPP/SPP 来源特权级 |
| 03 | M/S 异常路由 |
| 04 | 执行阶段或已接受的异常次数 |
| 05 | cause |
| 06 | EPC |
| 07 | TVAL |
| 08 | FReason |
| 09 | GPR 目的寄存器 |
| 10 | 浮点目的寄存器 |
| 11 | 64 字节测试内存 |
| 12 | FS 状态 |
| 13 | 探针完成标记 |
| 14 | 异常恢复标记 |

`a1` 保存有效地址，压缩栈形式还将 `sp` 设为该地址，框架不使用栈。
`s1` 为用例编号，`s4` 为预期 cause（`0` 为正常完成），`s5` 为阶段，
`s6` 为已接受的异常数，`s7/s8` 为完成/恢复标记。`s10` 为预期 FReason，
`s11` 为探针 PC，`a7` 为完成 ECALL PC，`t6` 保存失败原因。
