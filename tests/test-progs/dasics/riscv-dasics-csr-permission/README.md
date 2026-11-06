# riscv-dasics-csr-permission

[English](README.en.md) | [复现命令](../../../../docs/dasics.md#riscv-dasics-csr-permission)

## 测试范围

验证 M→U、M→S 特权切换、异常返回、DASICS CSR 访问门禁及普通 CSR 对照。

| 覆盖范围 | 两域合计 |
| --- | --- |
| LibCfg 的六种 CSR 指令及 `rd=x0`、`rs1=x0`、`zimm=0` 形式 | 24 项指令测试、72 个权限场景 |
| LibCfg 的 PC 边界检查 | 24 个场景 |
| 全部 52 个 DASICS CSR 地址的只读探测 | 312 个场景：285 个门禁场景、27 个普通特权拒绝场景 |
| 普通 CSR 对照 | U/S 各读取 `cycle`，S 态额外读写 `sscratch` |

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
   `mepc` 和 `a0=0x5679`，随后依次执行该域的指令权限表、边界表、全 CSR 地址表和
   普通 CSR 对照。U 域全部完成后从头执行 S 域；S 域全部完成后才能成功退出。

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

## PC 边界用例

边界表复用同一条 8 字节对齐的 `boundary_probe` 指令
`csrrw a0, 0x880, a1`，其 PC 记为 `B`，`boundary_ecall` 紧随于 `B+4`。
M 态为每项重新设置当前域的边界和使能位，以及 `P/Q/D/FReason` 初值。
每种区间先开启保护、再关闭保护；两域使用同一张表。

| 编号（开 / 关） | PC 位置 | 区间 `[lo, hi)` | 开启时 | 关闭时 |
| --- | --- | --- | --- | --- |
| 1 / 2 | `lo - 8` | `[B+8, B+24)` | 拒绝 | 允许 |
| 3 / 4 | `lo` | `[B, B+16)` | 允许 | 允许 |
| 5 / 6 | `hi - 8` | `[B-8, B+8)` | 允许 | 允许 |
| 7 / 8 | `hi` | `[B-16, B)` | 拒绝 | 允许 |
| 9 / 10 | 空区间 | `[B, B)` | 拒绝 | 允许 |
| 11 / 12 | 反向区间 | `[B+8, B-8)` | 拒绝 | 允许 |

允许访问时，通过 ECALL 检查当前域的异常原因和 `MPP`、`mepc=B+4`、
`a0=P`、LibCfg=`Q`、FReason=`5`。拒绝时要求 `mcause=2`、`MPP` 为当前域、
`mepc=B`、`mtval` 为探针原始编码，且 `a0=D`、LibCfg=`P`、FReason=`5`。
M 态跳过故障指令后，必须在 `B+4` 再次收到 ECALL，并重新检查状态保持。

边界元数据表每项包含 `lower`、`upper`、`enabled`、`allowed`
四个 64 位字段，共 32 字节；每域的指令表完成后从边界表第一项继续执行。

## 全 DASICS CSR 地址门禁

地址表按以下顺序覆盖全部 52 个架构 CSR 地址。SMainCfg 与 UMainCfg
共用内部状态，仍作为两个地址分别探测。每项包含 `trustedPC`、
`untrustedPC`、`readerPC`、`minpriv` 四个 64 位字段，共 32 字节。

| 编号 | CSR | 地址 | 最低特权级 |
| --- | --- | --- | --- |
| 1 | LibCfg | `0x880` | U |
| 2～33 | LibBoundLo/Hi 0～15 | `0x890～0x8AF` | U |
| 34～37 | MainCallEntry、ReturnPC、ActiveZoneReturnPC、FReason | `0x8B0～0x8B3` | U |
| 38 | JumpCfg | `0x8C8` | U |
| 39～46 | JumpBoundLo/Hi 0～3 | `0x8C0～0x8C7` | U |
| 47～49 | UMainCfg、UMainBoundLo/Hi | `0x9E1～0x9E3` | S |
| 50～52 | SMainCfg、SMainBoundLo/Hi | `0xBC0`、`0xBC2`、`0xBC3` | M |

各地址使用静态生成的 `csrrs a0, csr, zero` 探针，不写入目标 CSR。
可信块与非可信块各占 8 字节，均由探针和后续 ECALL 组成；
当前域可信区设为 `[trustedPC, untrustedPC)`，非可信探针位于上边界。
同一地址依次运行三种场景：

| `s5` | 当前域保护 | 探针位置 | 普通特权满足时 | 普通特权不满足时 |
| --- | --- | --- | --- | --- |
| `0` | 关闭 | 区外 | 允许 | cause 2 |
| `1` | 开启 | 可信 | 允许 | cause 2 |
| `2` | 开启 | 区外 | cause 2 | cause 2 |

U 态有 46 个地址、S 态有 49 个地址满足普通特权要求，构成
`(46+49)×3=285` 个门禁场景。其余 U 态 6 个、S 态 3 个地址在三种场景下
均因普通特权不足而拒绝，共 27 个场景；这些拒绝不能计为 DASICS 门禁验证。

每个场景在 M 态配置保护开关和边界、重置 LibCfg=`P`、FReason=`5`、
`a0=D` 后，通过该地址的 M 态读函数重新取得目标快照 `s4`。
允许时检查 `a0=s4`；拒绝时检查 `a0=D`。两者均要求目标 CSR 等于快照、
LibCfg=`P`、FReason=`5`，不对随配置变化的 MainCfg/MainBound 假设固定初值。

所有拒绝都检查 `mcause=2`、当前域 `MPP`、精确的探针 `mepc` 和原始编码 `mtval`。
跳过探针后，必须在该探针的 `PC+4` 收到 ECALL，并重新检查状态保持。
允许场景也通过精确的后续 ECALL 返回 M 态检查结果。

## 普通 CSR 对照

地址表完成后，将当前域主区间设为 `[0, 0)` 并开启保护，使对照指令处于区外。
M 态同时设置 `mcounteren.CY` 和 `scounteren.CY`，允许 S/U 读取 `cycle`。

| 当前域 | 指令 | 预期 |
| --- | --- | --- |
| U、S | `csrrs a0, 0xC00, zero` | `a0` 不再等于 `D`；不比较固定计数值 |
| S | `csrrw a0, 0x140, a1` | `sscratch` 从 `P` 更新为 `Q`，`a0=P` |

每项均检查后续 ECALL 的当前域原因、`MPP`、精确 `mepc`，以及
LibCfg=`P`、FReason=`5`。U 态不执行 `sscratch` 对照，因为该 CSR 要求 S 特权。

已知范围：[NanhuV5 FDI ISA](https://aul8ejtumo.feishu.cn/wiki/X3kawI6qoiIKejk3ZUdcebdqnOc)
revision 221 §3.4 要求拒绝非可信 S 态对普通 CSR 的写入，浮点和可写向量 CSR 除外。
当前尚未接入该规则；此处允许写 `sscratch` 仅描述现有实现，不能作为完整 ISA 一致性证明。

## CSR 写后刷新策略

全部 52 个 DASICS CSR 地址的写指令保留 `IsNonSpeculative` 和 `IsSerializeAfter`，
并按写意图增加 `IsSquashAfter`。O3 成功提交时先使 CSR 更新生效，再刷新年轻指令，
从下一条 PC 重新取指。指令具有写意图时，S/U 域保护关闭、实际源值为零或写入值不变
均不取消刷新；`rd=x0` 也不取消写意图。

`CSRRS/CSRRC` 的 `rs1=x0`、`CSRRSI/CSRRCI` 的 `zimm=0` 没有写意图，
仅保留既有序列化；`CSRRW/CSRRWI` 始终有写意图。
写入发生异常时不更新 CSR，按异常路径处理，不额外触发成功写后的刷新。

功能测试返回 `0` 不能单独证明刷新已发生；验证时需通过 `Commit`/`Fetch`
轨迹核对提交、年轻指令刷新及下一条 PC 取指。

## 调试约定

`s0` 指向当前表项，`s1` 记录阶段：`0/1` 为初始 ECALL 框架，
`2～5` 为指令权限用例，`6` 为边界允许访问后的 ECALL，
`7` 为边界拒绝访问，`8` 为边界拒绝返回后的 ECALL；
`9/10/11` 分别为地址表允许 ECALL、拒绝 CSR、拒绝返回后的 ECALL，
`12/13` 分别为普通 `cycle` 和 `sscratch` 对照。
`s2=0` 表示初始框架；指令表和边界表分别编号 `1～12`，地址表编号 `1～52`，
普通对照编号 `1/2`。结合 `s3`（`0=U`、`1=S`）和 `s1` 定位域、表及用例。
地址表额外使用 `s4` 保存目标快照、`s5` 记录场景 `0/1/2`。

所有指令禁用压缩编码，ECALL 返回地址固定增加 4。测试不使用栈，
`ra`、`t0/t1`、`a2/a3` 和 `s0～s5` 为异常框架保留寄存器；
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
| `16` | 应保持的 LibCfg 初值被修改 |
| `17` | 应保持的 FReason 被修改 |
| `18` | 指令权限用例拒绝访问返回后的 ECALL `mepc` 错误 |
| `19` | 边界允许访问后的 ECALL `mepc` 错误 |
| `20` | 边界拒绝访问返回后的 ECALL `mepc` 错误 |
| `21` | 地址表允许访问或拒绝返回后的 ECALL `mepc` 错误 |
| `22` | 地址表允许访问的 `a0` 不等于目标快照 |
| `23` | 地址表目标 CSR 偏离快照 |
| `24` | `cycle` 对照的 ECALL `mepc` 错误 |
| `25` | `cycle` 对照未改变 `a0` 哨兵 |
| `26` | `sscratch` 对照的 ECALL `mepc` 错误 |
| `27` | `sscratch` 对照返回旧值错误 |
| `28` | `sscratch` 对照写入新值错误 |
| `124` | 宿主运行超时 |
