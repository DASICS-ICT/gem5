# riscv-dasics-csr-permission

[English](README.en.md) | [复现命令](../../../../docs/dasics.md#riscv-dasics-csr-permission)

## 测试范围

验证 M→U、M→S 特权切换、异常返回，以及 S/U 态 LibCfg（`0x880`）的访问权限。
每域覆盖六种 CSR 指令及 `rd=x0`、`rs1=x0`、`zimm=0` 形式，共 12 项。
两域合计 24 项指令测试、72 个权限场景，不覆盖其他 CSR。

测试采用单 hart、RV64、裸机全系统与 O3 模型，使用 Semihosting 退出。
输出位于本目录的 `build/m5out-o3/<CPU>/`。

## 执行流程

1. M 态设置直接模式 `mtvec`，关闭中断和异常委托，使用 Bare 地址翻译。
2. 设置 PMP TOR 区间 `[0, 0x90000000)`，允许 S/U 态读、写、执行测试代码和数据。
   每域开始时将 SMainCfg 和 S/U 两域的四个 MainBound 清零，并重置用例指针和阶段。
3. 先选择 U 域，再选择 S 域；`s3` 分别为 `0` 和 `1`。清除
   `mstatus.MPP/MPRV/MIE/MPIE` 后，将 `MPP` 设置为当前域，通过 `mret` 进入该域。
4. 当前域设置 `a0=0x5678` 并执行第一次 ECALL；M 态处理程序检查
   当前域对应的 `mcause`、`MPP`、精确 `mepc` 和 `a0`，将 `mepc` 加 4 后执行 `mret`。
5. 当前域将 `a0` 加 1 并执行第二次 ECALL；M 态检查异常来源、顺序、
   `mepc` 和 `a0=0x5679`，随后依次执行该域的 12 项权限用例。
   U 域完成后从头执行 S 域；S 域全部完成后才能成功退出。

| 当前域 | `s3` | 使能位 | 可信区边界 | ECALL `mcause` | 异常入口 `MPP` |
| --- | --- | --- | --- | --- | --- |
| U | `0` | `UENA`（bit 1） | UMainBoundLo/Hi | `8` | U |
| S | `1` | `SENA`（bit 0） | SMainBoundLo/Hi | `9` | S |

## LibCfg 权限用例

每项指令依次经过下表的阶段。阶段 2～4 均由 M 态重新设置
LibCfg 初值 `P=0x13579BDF2468ACEF`、目标寄存器哨兵
`a0=D=0xA5A5A5A5A5A5A5A5` 和 `FReason=5`。
使用 `a1` 的指令取源值 `Q=0xFEDCBA9876543210`，非零立即数为 `I=0x15`。
两域复用同一张 12 项指令表及下面的阶段流程。

| 阶段 | 当前域使能位 | CSR 指令位置 | 预期 |
| --- | --- | --- | --- |
| 2：关闭保护 | `0` | 可信区上边界 | 允许访问，结果见下表；FReason=`5` |
| 3：可信访问 | `1` | 可信区下边界 | 允许访问，结果见下表；FReason=`5` |
| 4：非可信访问 | `1` | 可信区上边界，与阶段 2 为同一条指令 | 非法指令；`a0=D`、LibCfg=`P`、FReason=`5` |
| 5：异常返回 | `1` | 非可信 CSR 后的 ECALL | 返回后状态仍为 `a0=D`、LibCfg=`P`、FReason=`5` |

| 编号 | 指令 | 允许访问后的 `a0` | 允许访问后的 LibCfg |
| --- | --- | --- | --- |
| 1 | `csrrw a0, 0x880, a1` | `P` | `Q` |
| 2 | `csrrs a0, 0x880, a1` | `P` | `P \| Q` |
| 3 | `csrrc a0, 0x880, a1` | `P` | `P & ~Q` |
| 4 | `csrrwi a0, 0x880, 0x15` | `P` | `I` |
| 5 | `csrrsi a0, 0x880, 0x15` | `P` | `P \| I` |
| 6 | `csrrci a0, 0x880, 0x15` | `P` | `P & ~I` |
| 7 | `csrrw zero, 0x880, a1` | `D` | `Q` |
| 8 | `csrrwi zero, 0x880, 0x15` | `D` | `I` |
| 9 | `csrrs a0, 0x880, zero` | `P` | `P` |
| 10 | `csrrc a0, 0x880, zero` | `P` | `P` |
| 11 | `csrrsi a0, 0x880, 0` | `P` | `P` |
| 12 | `csrrci a0, 0x880, 0` | `P` | `P` |

每项的可信块和非可信块各占 8 字节，均由 CSR 指令及紧随的 ECALL 组成。
当前域的 MainBoundLo/Hi 定义半开区间 `[trustedPC, trustedPC + 8)`；
`untrustedPC = trustedPC + 8`，恰好位于右边界。
允许用例通过后续 ECALL 返回 M 态，检查当前域对应的 ECALL 原因、`MPP`、
精确 `mepc` 和对应结果。`rd=x0` 的两项还检查 `a0` 哨兵保持不变。

非可信访问全部要求 `mcause=2`、`MPP` 为当前域、`mepc=untrustedPC`，且
`mtval` 等于该地址处的原始指令编码。M 态检查状态未被修改后，
将 `mepc` 加 4 并返回当前域；随后必须执行紧随的 ECALL，检查
当前域对应的 ECALL 原因、`MPP`、`mepc=untrustedPC+4` 和状态保持。
只读形式和 `rd=x0` 形式同样必须被拒绝。

元数据表每项包含 `trustedPC`、`untrustedPC`、`sourceValue`、
`allowedRd`、`allowedCSR` 五个 64 位字段，共 40 字节。
`s0` 指向当前项，`s1` 记录阶段，`s2` 记录用例编号：
每域中 `0` 表示初始两次 ECALL，`1～12` 对应上表；
结合 `s3`（`0=U`、`1=S`）定位失败域和用例。

所有指令禁用压缩编码，ECALL 返回地址固定增加 4。测试不使用栈，
`ra`、`t0/t1`、`a2/a3` 和 `s0/s1/s2/s3` 为异常框架保留寄存器；
`a0/a1` 保存用例操作数，不提供通用上下文保存恢复。

## 退出码

| 退出码 | 含义 |
| --- | --- |
| `0` | 全部检查通过 |
| `1` | 异常原因不符合当前用例预期；`a3` 保留实际 `mcause` |
| `2` | 异常入口 `mstatus.MPP` 不符合当前域 |
| `3` | 异常顺序错误 |
| `4` | 第一次异常的 `mepc` 错误 |
| `5` | 第一次异常的 `a0` 错误 |
| `6` | 第二次异常的 `mepc` 错误 |
| `7` | 第二次异常的 `a0` 错误 |
| `8` | 关闭保护用例的 ECALL `mepc` 错误 |
| `9` | 可信用例的 ECALL `mepc` 错误 |
| `10` | 允许访问时，`a0` 不符合预期，包括 `rd=x0` 时的哨兵保持 |
| `11` | 允许访问时，LibCfg 不符合对应指令的预期结果 |
| `12` | 允许访问时，FReason 被修改 |
| `13` | 拒绝访问时，`mepc` 未指向预期 CSR 指令 |
| `14` | 拒绝访问时，`mtval` 不等于指令编码 |
| `15` | 拒绝访问或返回后的 `a0` 哨兵被修改 |
| `16` | 拒绝访问或返回后的 LibCfg 初值被修改 |
| `17` | 拒绝访问或返回后的 FReason 被修改 |
| `18` | 拒绝访问返回后的 ECALL `mepc` 错误 |
| `124` | 宿主运行超时 |
