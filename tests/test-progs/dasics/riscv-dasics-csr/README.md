# riscv-dasics-csr

[English](README.en.md) | [复现命令](../../../../docs/dasics.md#riscv-dasics-csr)

## 测试配置

| CSR | 地址 |
| --- | --- |
| `DASICS_MAIN_CALL_ENTRY` | `0x8B0` |
| `DASICS_RETURN_PC` | `0x8B1` |
| `DASICS_ACTIVE_ZONE_RETURN_PC` | `0x8B2` |
| `DASICS_FREASON` | `0x8B3` |
| `DASICS_U_MAIN_BOUND_LO` | `0x9E2` |
| `DASICS_U_MAIN_BOUND_HI` | `0x9E3` |
| `DASICS_S_MAIN_BOUND_LO` | `0xBC2` |
| `DASICS_S_MAIN_BOUND_HI` | `0xBC3` |
| `DASICS_U_MAIN_CFG` | `0x9E1` |
| `DASICS_S_MAIN_CFG` | `0xBC0` |
| `DASICS_LIB_CFG` | `0x880` |
| `DASICS_LIB_BOUND_LOi`（`i=0..15`） | `0x890 + 2*i` |
| `DASICS_LIB_BOUND_HIi`（`i=0..15`） | `0x891 + 2*i` |

共 43 个 CSR 地址、42 份 DASICS 状态。UMainCfg/SMainCfg 共享 MainCfg，
读写掩码分别为 `0x3E`、`0x3FF`；U 视图写入保留 S 专属字段 `0x3C1`。

| 项目 | 值 |
| --- | --- |
| 编译配置 | `USE_DASICS=y` |
| 仿真器 | `build/RISCV_DASICS/gem5.opt` |
| 架构 | RV64 |
| hart 数量 | 1 |
| 特权级 | M 态 |
| CPU | `RiscvAtomicSimpleCPU` |
| 运行方式 | 裸机全系统 |
| 退出接口 | Semihosting |

## 检查项

`_start` 初始化 `mtvec` 后，依次调用 `test_csr_initial_values`、
`test_main_call_entry`、`test_return_pc`、`test_active_zone_return_pc`、`test_freason`、
`test_u_main_bound_lo`、`test_u_main_bound_hi`、`test_s_main_bound_lo`、
`test_s_main_bound_hi`、`test_u_main_cfg`、`test_s_main_cfg`、`test_lib_cfg`，
再按 Lo/Hi 交错顺序调用 `test_lib_bound_lo0`、`test_lib_bound_hi0`，
直到 `test_lib_bound_lo15`、`test_lib_bound_hi15`（共 32 个函数），
最后调用 `test_csr_independence`，遇非零返回值立即退出。
各测试均为叶函数，通过 `a0` 返回 `0` 或失败码，沿用单 ELF、无栈和无嵌套调用结构。
32 个 LibBound 函数由 `DEFINE_LIB_BOUND_TEST` 在汇编期展开，CSR 号为编译期常量。

前三个全 64 位 CSR 的测试函数各自准备 `P = 0xFEDCBA9876543217` 和 `Q = 0x0123456789ABCDE3`。
FReason 单独验证低 3 位读写、高位读零及交换、置位和清位。
独立性检查另用 `R = 0x89ABCDEF01234565`，并将 FReason 设为 `2`。
MainBound 交换检查使用对齐值 `PA = 0xFEDCBA9876543210`、`QA = 0x0123456789ABCDE0`。
LibCfg 另用 `~P = 0x0123456789ABCDE8`，完整保存全部 64 位。
本测试仅在 M 态验证存储、读写掩码、共享视图和独立性；
不覆盖授权、特权切换、保护使能效果、PC 可信检查或区间生效。

| 用例 | 操作 | 预期结果 |
| --- | --- | --- |
| 冷初始化 | `test_csr_initial_values` 在任何 DASICS CSR 写入前读取 43 个地址的初值 | 各自返回 `0` |
| 64 位读写 | 前三个 CSR 分别写入 P 后读回 | 各自完整返回 P，包含高 32 位、bit 63 和低 3 位 |
| 读写交换 | 前三个 CSR 分别使用 `CSRRW` 写入 Q，随后读取 | 各自返回旧值 P，后续读取返回 Q |
| FReason 掩码与交换 | 写入 `-1` 后读回，再用 `CSRRW` 写入 `-6`；另检查写入 `0` 和 `-8` | 初次读回 `7`，交换返回旧值 `7`、新值为 `2`；写入 `0` 和 `-8` 均读回 `0` |
| FReason 置位与清位 | 值为 `2` 时以 `-7` 为源执行 `CSRRS`，随后用同一源执行 `CSRRC` | 置位返回旧值 `2`、新值 `3`；清位返回旧值 `3`、新值 `2` |
| MainBound 读写 | 四个函数各自验证对齐、非对齐、高位保留、交换及仅低位写入 | 低 3 位读零，写入向下对齐；交换返回对齐后的旧值，具体输入与错误码见下表 |
| UMainCfg 联动 | `test_u_main_cfg` 自行准备 S 视图初态，再经 U 视图读写、交换和置清位 | U 读写仅影响 `0x3E`，S 专属字段保持；具体值与错误码见下表 |
| SMainCfg 联动 | `test_s_main_cfg` 自行准备共享初态，再经 S 视图读写、交换和置清位 | S 读写影响 `0x3FF`，U 读值始终为共享状态的 `0x3E` 视图 |
| LibCfg 读写与交换 | 写 P、`CSRRW` 写 `~P`，另检查写 `0` 和 `-1` | 完整读回 P/`~P`，交换返回旧 P，`0`/`-1` 也完整读回 |
| LibCfg 置位与清位 | 值为 `~P` 时以 P 为源执行 `CSRRS`，随后用同一源执行 `CSRRC` | 先返回旧 `~P`、新值 `-1`；再返回旧 `-1`、新值 `~P` |
| LibBound 读写 | 32 个函数各自写 P、交换写 Q、再写 `7` | P 读回 PA；交换返回 PA，随后读 QA；写 `7` 读 `0` |
| 存储独立性 | `test_csr_independence` 保留原 Q/P/R/2、四个 MainBound 的 `0x1000/0x2000/0x3000/0x4000` 和 S=`0x155`、U=`0x2A` 的自备数据；另写 LibCfg=`0x13579BDF2468ACE1`，Lo_i=`0x10000 + 0x100*i`、Hi_i=`0x10080 + 0x100*i` | 全部 42 份状态写完后，先核对旧十地址，再读 LibCfg 和 32 个 LibBound；各值保持，S=`0x16B`、U=`0x2A`，不依赖其他函数状态 |

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

四个 MainBound 的失败退出码如下，均显示红色 `[FAIL]`；原退出码 1–27 保持不变。

| 检查 | UMainLo | UMainHi | SMainLo | SMainHi |
| --- | --- | --- | --- | --- |
| 初值（读 `0`） | `28` | `29` | `30` | `31` |
| 对齐写入（`0x1000` → `0x1000`） | `32` | `38` | `44` | `50` |
| 非对齐写入（`0x123F` → `0x1238`） | `33` | `39` | `45` | `51` |
| 高位保留（P → PA） | `34` | `40` | `46` | `52` |
| 交换旧值（写 Q，返回 PA） | `35` | `41` | `47` | `53` |
| 交换新值（读 QA） | `36` | `42` | `48` | `54` |
| 仅低位（写 `7`，读 `0`） | `37` | `43` | `49` | `55` |
| 独立性（分别读 `0x1000/0x2000/0x3000/0x4000`） | `56` | `57` | `58` | `59` |

MainCfg 的失败码及预期值如下，均显示红色 `[FAIL]`；原退出码 1–59 保持不变。
`旧值` 指 CSR 指令返回值，U/S 指读取的视图。

| 检查组 | 操作 | 失败码：预期值 |
| --- | --- | --- |
| 冷初始化 | 分别读取 U/S 初值 | `60`：U=`0`；`61`：S=`0` |
| U 视图 | 先写 S=`0x3FF`，读取 U | `62`：U=`0x3E` |
| U 视图 | 写 U=`0` | `63`：U=`0`；`64`：S=`0x3C1` |
| U 视图 | 写 U=`-1` | `65`：U=`0x3E`；`66`：S=`0x3FF` |
| U 视图 | 重设 S=`0x155`，`CSRRW` 写 U=`0xAAAAAAAAAAAAAAAB` | `67`：旧值=`0x14`；`68`：U=`0x2A`；`69`：S=`0x16B` |
| U 视图 | `CSRRS` 源为 `-1` | `70`：旧值=`0x2A`；`71`：U=`0x3E`；`72`：S=`0x17F` |
| U 视图 | `CSRRC` 源为 `-1` | `73`：旧值=`0x3E`；`74`：U=`0`；`75`：S=`0x141` |
| S 视图 | 写 S=`-1` | `76`：S=`0x3FF`；`77`：U=`0x3E` |
| S 视图 | `CSRRW` 写 S=P | `78`：旧值=`0x3FF`；`79`：S=`0x217`；`80`：U=`0x16` |
| S 视图 | `CSRRS` 源为 `-1` | `81`：旧值=`0x217`；`82`：S=`0x3FF`；`83`：U=`0x3E` |
| S 视图 | `CSRRC` 源为 `-63`（低 10 位为 `0x3C1`） | `84`：旧值=`0x3FF`；`85`：S=`0x3E`；`86`：U=`0x3E` |
| S 视图 | 写 S=`0` | `87`：S=`0`；`88`：U=`0` |
| 存储独立性 | 自行写 S=`0x155`、U=`0x2A` 后，核对两视图 | `89`：S=`0x16B`；`90`：U=`0x2A` |

新增 LibCfg 失败码如下，均显示红色 `[FAIL]`；原退出码 1–90 保持不变，
`124` 仍仅表示宿主超时。

| 检查 | 失败码 | 预期值 |
| --- | --- | --- |
| 冷初始化 | `91` | `0` |
| 写 P 后读回 | `125` | P |
| `CSRRW` 写 `~P` 的旧值 | `126` | P |
| 交换后读回 | `127` | `~P` |
| `CSRRS` 使用 P 的旧值 | `128` | `~P` |
| 置位后读回 | `129` | `-1` |
| `CSRRC` 使用 P 的旧值 | `130` | `-1` |
| 清位后读回 | `131` | `~P` |
| 写 `0` 后读回 | `132` | `0` |
| 写 `-1` 后读回 | `133` | `-1` |
| 存储独立性 | `166` | `0x13579BDF2468ACE1` |

LibBound 的 `i=0..15`；表内公式为各 CSR 的失败退出码，均显示红色 `[FAIL]`。

| 检查 | Lo_i | Hi_i | 范围 |
| --- | --- | --- | --- |
| 冷初始化（读 `0`） | `92 + 2*i` | `93 + 2*i` | 92–123 |
| 读写（P→PA，交换 Q 返回 PA，读 QA，写 `7` 读 `0`） | `134 + 2*i` | `135 + 2*i` | 134–165 |
| 独立性（读各自的 Lo_i/Hi_i 预期值） | `167 + 2*i` | `168 + 2*i` | 167–198 |

每个 LibBound 读写函数的四个断言共用一个失败码，只能定位到 CSR，不能区分具体断言。

## 源码

- [汇编程序](src/riscv-dasics-csr.S)
- [Makefile](src/Makefile)
