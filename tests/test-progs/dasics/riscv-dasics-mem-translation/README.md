# riscv-dasics-mem-translation

[English](README.en.md) | [复现命令](../../../../docs/dasics.md#riscv-dasics-mem-translation)

## 测试范围

在 RV64 MSU、单 hart O3 平台上检查 U/S 态 `ld/sd/fld/fsd` 的 32 种组合：
每种源态与操作分别组合有效/无效末级 PTE 与 DASICS 允许/拒绝。
使用 DASICS 构建（`USE_DASICS=y`），启用本例源态对应的数据保护，
FReason 初始哨兵为 `5`。

`bare-metal` 表示程序不依赖操作系统；`Bare` 表示关闭分页的地址翻译模式。
本用例为 bare-metal 程序，但使用 `satp.MODE=8` 的 Sv39 分页。

当前覆盖上述 32 组合，不包含跨页访问、异常委托或精确的翻译等待时序。

## 映射与执行

三级页表使用 4 KiB 页：`root_table[1]` 指向 `level1_table`，
`level1_table[0]` 指向 `level0_table`，中间级始终有效。代码页固定有效；
32 个数据 PTE 的 PPN 均取自同一物理页，叶标志按用例配置。
每例重写代码叶及对应数据叶。代码叶和有效数据叶在 U 态用例中置 U 位，
在 S 态用例中清 U 位；无效数据叶标志为 `0`。

| 用途 | 虚拟页 | 末级索引 | PTE PPN 来源 | 叶标志 |
| --- | --- | --- | --- | --- |
| 代码 | `0x40000000` | `0` | `probe_code_page` | V/R/X/A/D，U 按源态配置 |
| 用例 1 | `0x40001000` | `1` | `test_data_page` | V/U/R/W/A/D |
| 用例 2 | `0x40002000` | `2` | `test_data_page` | V/U/R/W/A/D |
| 用例 3 | `0x40003000` | `3` | `test_data_page` | `0`，V 无效 |
| 用例 4 | `0x40004000` | `4` | `test_data_page` | `0`，V 无效 |
| 用例 5 | `0x40005000` | `5` | `test_data_page` | V/U/R/W/A/D |
| 用例 6 | `0x40006000` | `6` | `test_data_page` | V/U/R/W/A/D |
| 用例 7 | `0x40007000` | `7` | `test_data_page` | `0`，V 无效 |
| 用例 8 | `0x40008000` | `8` | `test_data_page` | `0`，V 无效 |
| 用例 9 | `0x40009000` | `9` | `test_data_page` | V/U/R/W/A/D |
| 用例 10 | `0x4000A000` | `10` | `test_data_page` | V/U/R/W/A/D |
| 用例 11 | `0x4000B000` | `11` | `test_data_page` | `0`，V 无效 |
| 用例 12 | `0x4000C000` | `12` | `test_data_page` | `0`，V 无效 |
| 用例 13 | `0x4000D000` | `13` | `test_data_page` | V/U/R/W/A/D |
| 用例 14 | `0x4000E000` | `14` | `test_data_page` | V/U/R/W/A/D |
| 用例 15 | `0x4000F000` | `15` | `test_data_page` | `0`，V 无效 |
| 用例 16 | `0x40010000` | `16` | `test_data_page` | `0`，V 无效 |
| 用例 17 | `0x40011000` | `17` | `test_data_page` | V/R/W/A/D |
| 用例 18 | `0x40012000` | `18` | `test_data_page` | V/R/W/A/D |
| 用例 19 | `0x40013000` | `19` | `test_data_page` | `0`，V 无效 |
| 用例 20 | `0x40014000` | `20` | `test_data_page` | `0`，V 无效 |
| 用例 21 | `0x40015000` | `21` | `test_data_page` | V/R/W/A/D |
| 用例 22 | `0x40016000` | `22` | `test_data_page` | V/R/W/A/D |
| 用例 23 | `0x40017000` | `23` | `test_data_page` | `0`，V 无效 |
| 用例 24 | `0x40018000` | `24` | `test_data_page` | `0`，V 无效 |
| 用例 25 | `0x40019000` | `25` | `test_data_page` | V/R/W/A/D |
| 用例 26 | `0x4001A000` | `26` | `test_data_page` | V/R/W/A/D |
| 用例 27 | `0x4001B000` | `27` | `test_data_page` | `0`，V 无效 |
| 用例 28 | `0x4001C000` | `28` | `test_data_page` | `0`，V 无效 |
| 用例 29 | `0x4001D000` | `29` | `test_data_page` | V/R/W/A/D |
| 用例 30 | `0x4001E000` | `30` | `test_data_page` | V/R/W/A/D |
| 用例 31 | `0x4001F000` | `31` | `test_data_page` | `0`，V 无效 |
| 用例 32 | `0x40020000` | `32` | `test_data_page` | `0`，V 无效 |

物理地址由 ELF 符号确定，与对应虚拟地址不同；V 无效的条目不构成有效映射。
M 态通过 PMP 放行代码、数据和页表，并关闭中断及异常委托。每例清除
MPRV/SUM/MXR，初始化物理数据，配置对应 PTE 和 DASICS CSR，执行
`fence rw,rw`、设置 SATP、执行 `sfence.vma`，设置源态对应的 MPP 后通过 MRET 进入探针。

U 态用例 MainCfg=`0x26`：UENA 开启，CUET/CUFT 关闭 ECALL 和控制流检查，
CULT/CUST 均保持 `0`，开启读写检查。S 态用例 MainCfg=`0x241`：
SENA 开启，CSET/CSFT 关闭 ECALL 和控制流检查，CSLT/CSST 均保持 `0`。
U/S MainBounds 均为空，使探针 PC 非可信。slot 0 边界为本例数据的 `[VA, VA+8)`；
LibCfg=`0xA` 允许读，`0x9` 允许写，`0x8` 拒绝对应操作，其他 slot 均无效。

每例有独立探针及对应 ECALL 标签：1–4 使用 `ld a0,0(a1)`，
5–8 使用 `sd a2,0(a1)`，9–12 使用 `fld fa0,0(a1)`，
13–16 使用 `fsd fa2,0(a1)`。
1–4 依次为
`u_ld_mapped_allow`、`u_ld_mapped_deny`、`u_ld_page_fault_allow`、
`u_ld_page_fault_deny`；5–8 依次为 `u_sd_mapped_allow`、`u_sd_mapped_deny`、
`u_sd_page_fault_allow`、`u_sd_page_fault_deny`。浮点探针按同样后缀分别使用
`u_fld_*` 和 `u_fsd_*` 标签。17–20、21–24、25–28、29–32 分别为 S 态
`ld/sd/fld/fsd`，使用相同后缀的 `s_ld_*`、`s_sd_*`、`s_fld_*`、`s_fsd_*` 标签。
各四例均按有效允许、有效拒绝、无效允许、无效拒绝排序。
正常访存设置完成标记后执行 ECALL；故障例直接陷入 M，不执行标记及后续 ECALL。
M 检查完本例后直接开始下一例，不恢复故障后的 U/S 态指令。

## 检查契约

数据值 `LOAD_VALUE=0x1122334455667788`；每例从
`a0=GPR_SENTINEL=0xA5A5A5A5A5A5A5A5` 和完成标记 `s1=0` 开始。
写入源 `a2=STORE_VALUE=0x0807060504030201`，在探针执行及陷入检查时保持不变。
每例还初始化 `fa0=FPR_SENTINEL=0x8877665544332211`、`fa2=STORE_VALUE`、
FS=`Clean (2)`。仅正常 `fld` 的用例 9、25 将 `fa0` 改为 `LOAD_VALUE`、
FS 改为 `Dirty (3)`；其他用例保持 `fa0` 哨兵和 Clean，`fa2` 始终保持不变。
M handler 在执行任何浮点检查指令前读取 FS；后续 `fmv.x.d` 检查本身会置 Dirty，
因此上述 FS 指陷入时的状态。

| 用例 | 叶有效 | DASICS 读写 | 最终 cause | FReason | `a0` |
| --- | --- | --- | --- | --- | --- |
| 1 | 是 | 读允许 | `8`，正常 load 后的 ECALL | `5` | `LOAD_VALUE` |
| 2 | 是 | 读拒绝 | `24`，U DASICS 异常 | `2` | `GPR_SENTINEL` |
| 3 | 否 | 读允许 | `13`，load page fault | `5` | `GPR_SENTINEL` |
| 4 | 否 | 读拒绝 | `13`，load page fault 优先 | `5` | `GPR_SENTINEL` |
| 5 | 是 | 写允许 | `8`，正常 store 后的 ECALL | `5` | `GPR_SENTINEL` |
| 6 | 是 | 写拒绝 | `24`，U DASICS 异常 | `3` | `GPR_SENTINEL` |
| 7 | 否 | 写允许 | `15`，store page fault | `5` | `GPR_SENTINEL` |
| 8 | 否 | 写拒绝 | `15`，store page fault 优先 | `5` | `GPR_SENTINEL` |
| 9 | 是 | 读允许 | `8`，正常浮点 load 后的 ECALL | `5` | `GPR_SENTINEL` |
| 10 | 是 | 读拒绝 | `24`，U DASICS 异常 | `2` | `GPR_SENTINEL` |
| 11 | 否 | 读允许 | `13`，load page fault | `5` | `GPR_SENTINEL` |
| 12 | 否 | 读拒绝 | `13`，load page fault 优先 | `5` | `GPR_SENTINEL` |
| 13 | 是 | 写允许 | `8`，正常浮点 store 后的 ECALL | `5` | `GPR_SENTINEL` |
| 14 | 是 | 写拒绝 | `24`，U DASICS 异常 | `3` | `GPR_SENTINEL` |
| 15 | 否 | 写允许 | `15`，store page fault | `5` | `GPR_SENTINEL` |
| 16 | 否 | 写拒绝 | `15`，store page fault 优先 | `5` | `GPR_SENTINEL` |
| 17 | 是 | 读允许 | `9`，正常 load 后的 ECALL | `5` | `LOAD_VALUE` |
| 18 | 是 | 读拒绝 | `25`，S DASICS 异常 | `2` | `GPR_SENTINEL` |
| 19 | 否 | 读允许 | `13`，load page fault | `5` | `GPR_SENTINEL` |
| 20 | 否 | 读拒绝 | `13`，load page fault 优先 | `5` | `GPR_SENTINEL` |
| 21 | 是 | 写允许 | `9`，正常 store 后的 ECALL | `5` | `GPR_SENTINEL` |
| 22 | 是 | 写拒绝 | `25`，S DASICS 异常 | `3` | `GPR_SENTINEL` |
| 23 | 否 | 写允许 | `15`，store page fault | `5` | `GPR_SENTINEL` |
| 24 | 否 | 写拒绝 | `15`，store page fault 优先 | `5` | `GPR_SENTINEL` |
| 25 | 是 | 读允许 | `9`，正常浮点 load 后的 ECALL | `5` | `GPR_SENTINEL` |
| 26 | 是 | 读拒绝 | `25`，S DASICS 异常 | `2` | `GPR_SENTINEL` |
| 27 | 否 | 读允许 | `13`，load page fault | `5` | `GPR_SENTINEL` |
| 28 | 否 | 读拒绝 | `13`，load page fault 优先 | `5` | `GPR_SENTINEL` |
| 29 | 是 | 写允许 | `9`，正常浮点 store 后的 ECALL | `5` | `GPR_SENTINEL` |
| 30 | 是 | 写拒绝 | `25`，S DASICS 异常 | `3` | `GPR_SENTINEL` |
| 31 | 否 | 写允许 | `15`，store page fault | `5` | `GPR_SENTINEL` |
| 32 | 否 | 写拒绝 | `15`，store page fault 优先 | `5` | `GPR_SENTINEL` |

- MainCfg/LibCfg 读回与配置一致；SATP 设置后正确，陷入 M 后保持不变。
- 全部异常进入 M，MPP 应与本例源态一致（U=`0`，S=`1`）。
  正常例 EPC 为该例 ECALL 的虚拟地址、TVAL=`0`；
  故障例 EPC 为该例访存指令的虚拟地址、TVAL 为本例数据 VA。
  虚拟 PC 按 `0x40000000 + (label - probe_code_page)` 计算。
- 正常例完成标记为 `1`，故障例为 `0`；M handler 在 MPRV=`0` 下检查物理
  数据页：仅正常 store 的用例 5、13、21、29 应写入 `STORE_VALUE`，
  其他用例保持 `LOAD_VALUE`。全部 32 例检查完成后才以 Semihosting 状态 `0` 退出。

运行后还应另查本次 `stats.txt` 中的分页统计：

| 统计 | 预期 |
| --- | --- |
| DTLB `readMisses` | 至少 `16` |
| DTLB `writeMisses` | 至少 `16` |
| DTLB walker `num_4kb_walks` | 至少 `16` |

`num_4kb_walks` 只统计成功到达有效 4 KiB 叶子的遍历。
用例 1、2、5、6、9、10、13、14、17、18、21、22、25、26、29、30 预期计入，
其余叶无效的页故障不增加该计数。这些统计仅作辅助核对，未由汇编直接断言；
精确等待时序需另按 PC、VA、seqNum 关联轨迹核对。

## 软件构建

在仓库根目录执行：

```bash
make -C tests/test-progs/dasics/riscv-dasics-mem-translation/src
```

软件使用 `-march=rv64imafdc_zicsr -mabi=lp64`。

产物为本测试目录的 `build/riscv-dasics-mem-translation.elf`；仿真输出位于
`build/m5out-o3/<CPU>/`。运行命令见[使用说明](../../../../docs/dasics.md#riscv-dasics-mem-translation)。

## 诊断

失败时通过 Semihosting 打印 `DASICS translation: case=NN reason=NN`。
`case=01..32` 标识组合，初始化阶段为 `00`；退出码为 `reason=01..12`，
而非用例编号。`124` 保留为宿主超时。

| 失败码 | 检查失败 |
| --- | --- |
| `1` | MainCfg/LibCfg 配置读回不符 |
| `2` | SATP 设置错误或陷入后被修改 |
| `3` | cause 不符合本例预期 |
| `4` | MPP 不符合本例预期的 U/S 源态 |
| `5` | EPC 不等于本例虚拟访存指令或 ECALL 地址 |
| `6` | TVAL 不符合本例预期 |
| `7` | 完成标记不符合本例预期 |
| `8` | `a0` 或写入源 `a2` 不符合本例预期 |
| `9` | 物理目标 8 字节不符合本例预期 |
| `10` | FReason 不符合本例预期 |
| `11` | `fa0` 或写入源 `fa2` 不符合本例预期 |
| `12` | FS 不符合本例预期 |
