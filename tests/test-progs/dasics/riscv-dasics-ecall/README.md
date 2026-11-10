# riscv-dasics-ecall

[English](README.en.md) | [复现命令](../../../../docs/dasics.md#riscv-dasics-ecall)

## 测试范围

验证 RV64 非虚拟化 U/S 态 ECALL 的 DASICS 检查、保护开关、可信 PC、
M/S 异常路由和异常返回，并用 M 态验证旁路。配置为单 hart O3、裸机全系统、
Bare 地址翻译与 Semihosting 退出。只有全部 41 个场景完成才以状态 `0` 退出。
本用例不覆盖虚拟化或 O3 错误路径。

## 场景分组

| 编号 | 检查 |
| --- | --- |
| 1–8 | U/S 非可信 ECALL：本域检查开启时产生 DASICS 异常，设置本域 CUET/CSET 后产生普通 ECALL；均测试 M/S 路由 |
| 9–16 | 关闭本域 enable 后为普通 ECALL，关闭另一域 enable 仍产生 DASICS 异常；均测试 U/S 来源和 M/S 路由 |
| 17–20 | 仅设置另一域的 ECALL close 位不能旁路；均测试 U/S 来源和 M/S 路由 |
| 21–40 | U/S 各五种 PC 边界位置，每项均测试 M/S 路由 |
| 41 | M 态旁路：MEDELEG 的 `8/9/24/25` 位均设置，仍由 M 处理 cause `11` |

前两组先执行 U 域，再执行 S 域；每域先执行表中第一种配置，再执行第二种配置，
每种配置均先走 M 路由、再走 S 路由。17–20 同样先 U 后 S、每域先 M 后 S。

| U 编号 | S 编号 | 探针 PC 位置 | 首个异常 |
| --- | --- | --- | --- |
| 21–22 | 31–32 | 下界前 8 字节 | DASICS |
| 23–24 | 33–34 | 恰好位于下界 | 普通 ECALL |
| 25–26 | 35–36 | 下界所在 8 字节块内的 `+4` 位置 | 普通 ECALL |
| 27–28 | 37–38 | 区间内部 | 普通 ECALL |
| 29–30 | 39–40 | 恰好位于上界 | DASICS |

## 配置与布局

- M 态设置直接模式 MTVEC/STVEC、关闭中断、使用 Bare 翻译，并设置 PMP TOR
  区间 `[0, 0x90000000)` 的读写执行权限。
- MainCfg 默认启用 UENA/SENA，关闭 U/S 普通访存和控制流检查，保留 ECALL
  检查；每例按配置调整本域或另一域的 enable、CUET/CSET。
- 主边界为 `[lo, hi)`，所有用例的可信区间均包含完整 S handler。
  测试使用 `probe_before`、`probe_half`、`probe_after` 的 32 位 ECALL 探针。
- 每例设置并检查 MEDELEG。U/S 来源的 M 路由例委托未选中的另一类 cause，检查路由依据
  实际产生的普通 ECALL 或 DASICS cause。完成用 EBREAK 的 cause `3` 始终不委托。

## 异常与恢复

| 来源 | DASICS 检查开启且 PC 非可信 | 普通 ECALL 路径 |
| --- | --- | --- |
| U | cause `24`，FReason=`1` | cause `8`，FReason 保持 `5` |
| S | cause `25`，FReason=`1` | cause `9`，FReason 保持 `5` |
| M | 旁路 DASICS 检查 | cause `11`，FReason 保持 `5` |

首个异常检查来源 MPP/SPP、M/S 路由、精确探针 EPC、TVAL=`0`、FReason、
未执行的顺序路径标记及三个寄存器哨兵：`a0=0x0123456789ABCDEF`、
`a1=0xFEDCBA9876543210`、`ra=0xA5A5A5A5A5A5A5A5`。

handler 将 MEPC/SEPC 设为 `resume_entry`，经 MRET/SRET 恢复到原来源态。
恢复代码设置标记为 `1`，在 `resume_break` 执行普通 32 位 EBREAK 返回 M。
完成异常须为 cause `3`，EPC/TVAL 均为 `resume_break`，MPP 仍对应原来源态；
ECALL 异常计数须恰好为 `1`，FReason 和寄存器哨兵保持不变。
该完成通道避免普通 ECALL 已委托给 S 时再次使用 ECALL 造成递归。
S handler 检查失败也通过独立 EBREAK 返回 M，保留失败原因。

## 软件构建

在仓库根目录执行：

```bash
make -C tests/test-progs/dasics/riscv-dasics-ecall/src
```

产物为本测试目录下的 `build/riscv-dasics-ecall.elf`，仿真输出位于
`build/m5out-o3/<CPU>/`。运行命令见[使用说明](../../../../docs/dasics.md#riscv-dasics-ecall)。

## 诊断

失败时通过 Semihosting `SYS_WRITE0` 打印：

```text
DASICS ecall: case=NNN reason=NN
```

`case=001..041` 对应上述场景，失败退出码为用例编号；初始化失败打印
`case=000` 并以 `255` 退出。`124` 保留为宿主超时。

| reason | 检查失败 |
| --- | --- |
| 01 | MEDELEG 读回 |
| 02 | MPP/SPP 来源特权级 |
| 03 | M/S 异常路由 |
| 04 | 执行阶段或 ECALL 异常计数 |
| 05 | cause |
| 06 | EPC |
| 07 | TVAL |
| 08 | FReason |
| 09 | `a0/a1/ra` 哨兵 |
| 10 | 意外执行 ECALL 后的顺序路径 |
| 11 | 异常恢复标记 |

`s1` 为用例编号，`s2/s3` 为来源态和预期 S 路由，`s4` 为预期 ECALL cause，
`s5` 为阶段，`s6` 为已接受的 ECALL 异常数，`s7/s8` 为顺序路径/恢复标记。
`s9` 为预期 FReason，`s10` 为 ECALL PC，`t6` 保存失败原因。框架不使用栈，
全部指令采用非压缩编码。
