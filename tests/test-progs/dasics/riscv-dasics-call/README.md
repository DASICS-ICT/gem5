# riscv-dasics-call

[English](README.en.md) | [复现命令](../../../../docs/dasics.md#riscv-dasics-call)

## 测试范围

验证 RV64 DASICSCALL 的目标、链接寄存器、ReturnPC、来源权限、非法指令异常
及普通跳转对照，并检查原有 m5 编码兼容。使用单 hart O3、裸机全系统、
Bare 地址翻译、PMP 和 Semihosting 退出。
只有全部 67 个场景完成才以状态 `0` 退出。
虚拟化和 O3 错误路径压力测试不在本用例范围内。

## 编码与语义

本 gem5 与本测试采用公开
[DASICS-ICT/xiangshan-dasics `dasics-master`](https://github.com/DASICS-ICT/xiangshan-dasics/tree/dasics-master)
所引用的 rocket-chip `cb2690c0a71a` 中的
[Instructions.scala 372–373 行](https://github.com/DASICS-ICT/rocket-chip/blob/cb2690c0a71adb789943ed6321555687c3daa478/src/main/scala/rocket/Instructions.scala#L372-L373)
编码：

| 指令 | opcode | funct3 | 链接目的寄存器 |
| --- | --- | --- | --- |
| DASICSCALL.J | custom-0，`0x0B` | `0` | 固定 `ra` |
| DASICSCALL.JR | custom-0，`0x0B` | `1` | `rd` |

若保护二进制使用 `0x7B` 版本的 DASICS 调用，须按 `0x0B` 编码重新构建。
gem5 m5 伪指令继续使用 `0x7B`。

权限与 ReturnPC 行为采用 NanhuV5 语义：

- J 使用有符号 23 位偶数偏移，范围 `[-0x400000, 0x3FFFFE]`，目标为
  `PC+offset`。其位布局不同于 JAL，指令中的 RD 位属于偏移，链接目的固定为 `ra`。
- JR 使用 I 型有符号 12 位立即数，目标为 `(old_rs1+imm)&~1`。
  `rd==rs1` 时仍使用旧源值；`rd=x0` 不写 GPR，但仍更新 ReturnPC。
- 调用仅允许在已使能、可信、非虚拟化 U/S 域执行；M 态调用非法。
  成功时链接值与 ReturnPC 均为 `PC+4`。
- 非法调用产生 cause `2`，EPC 指向调用，TVAL 为原始指令编码；
  链接寄存器、ReturnPC 和 FReason 不变。

测试通过 `CALL_J/CALL_JR` 宏生成 `.word`，不要求 GNU assembler 识别新助记符。

## 场景分组

前 20 例按下列顺序，每种探针先执行 U 态，再执行 S 态：

| 编号 | 成功探针 |
| --- | --- |
| 1–2 | J 近距离正偏移 |
| 3–4 | J 近距离负偏移 |
| 5–6 | J 最小偏移 `-0x400000` |
| 7–8 | J 最大偶数偏移 `+0x3FFFFE`，目标按半字对齐 |
| 9–10 | JR `rd=ra`，清除源目标最低位 |
| 11–12 | JR `rd=a0`，立即数 `+8` |
| 13–14 | JR `rd=x0`，ReturnPC 仍更新 |
| 15–16 | JR `rd==rs1==a1`，按旧源值取目标 |
| 17–18 | JR 立即数 `-2048` |
| 19–20 | JR 立即数 `+2047` |

| 编号 | 检查 |
| --- | --- |
| 21–24 | J/JR 各 U/S：可信目标第一条指令读取 ReturnPC |
| 25–52 | 来源权限矩阵：本域关闭、非可信、非可信且设置本域 CUFT/CSFT 均非法；仅关闭另一域仍成功 |
| 53–54 | M 态 J/JR 非法，使用最高位为 `1` 的原始指令编码 |
| 55–58 | 未定义 `funct3=7`，U/S 各检查 M/S 非法指令路由 |
| 59–62 | JR `rs1=x0`，仅验证未使能/非可信来源下的非法路径 |
| 63–66 | 普通 JAL/JALR 各 U/S 对照，不更新 ReturnPC |
| 67 | M 态旧 `0x7B` 编码的 `m5_sum(1,2,3,4,5,6)` 返回 `21`，ReturnPC/FReason 不变，不产生 m5 退出事件 |

权限矩阵依次为 J 的 U/S、JR 的 U/S，每组七例：本域未使能、非可信、
非可信且设置本域跳转 close 位三类各走 M/S 路由，最后一例仅关闭另一域。
J 极值通过静态布局覆盖正负边界，不依赖固定的运行地址。

## 状态与恢复

- MainCfg 默认 `0x1DF`，启用两域并关闭 ECALL 和数据检查，保持普通跳转检查。
  每例按配置调整使能、可信区和跳转 close 位；S handler 始终处于可信区。
- JumpCfg、MainCallEntry、ActiveZoneReturnPC 均为 `0`。区外目标通过普通
  `ret/jalr` 返回时，授权来自调用更新后的 ReturnPC。
- 每例将 ReturnPC 设为 `0x1020304050607080`、FReason 设为 `5`，
  `ra=0xA5A5A5A5A5A5A5A5`。常规探针的 `a0=0x0123456789ABCDEF`，
  `a1` 保存探针描述中的旧源值，`a4` 初值为 `0x5566778899AABBCC`；
  m5_sum 例将 `a0..a5` 设为 `1..6`。
- m5_sum 不检查 `a1` 保持，当前 gem5 M5Op 路径会改写它；仍检查 `a0=21`、
  ReturnPC/FReason 和正常完成。J/JR 探针的 `a1` 原值或源/目的别名结果检查不变。
- 成功调用检查目标标记、实际链接目的寄存器和 ReturnPC=`PC+4`；可信目标第一条
  CSR 指令把 ReturnPC 捕获到 `a4`。普通 JAL/JALR 对照捕获原 ReturnPC 哨兵。
- 非法路径先检查 cause `2`、来源 MPP/SPP、M/S 路由、EPC 为调用 PC、
  TVAL 为原始 32 位指令编码，再经 MRET/SRET 到 `resume_entry`。
  链接、源寄存器、ReturnPC、FReason 和捕获哨兵保持，目标标记为 `0`。
- 完成通道为不委托的普通 EBREAK，cause=`3`，EPC/TVAL 为实际断点 PC。
  成功的完成标记为 `1`，非法恢复后为 `2`；非法指令异常数分别为 `0/1`。
  FReason 在全部场景保持 `5`。

## 软件构建

在仓库根目录执行：

```bash
make -C tests/test-progs/dasics/riscv-dasics-call/src
```

产物为本测试目录下的 `build/riscv-dasics-call.elf`，仿真输出位于
`build/m5out-o3/<CPU>/`。运行命令见[使用说明](../../../../docs/dasics.md#riscv-dasics-call)。

## 可选 O3 轨迹

调用保留 `IsNonSpeculative` 和 `IsSerializeAfter`；`xc->setMiscReg` 将隐式
ReturnPC 写入推迟到 O3 提交。预测正确时 Fetch 可以预先取得目标指令，年轻指令
在 Rename 等待调用提交后再推进和发射，成功调用不额外请求 SquashAfter。
预测错误和异常仍走普通 O3 冲刷路径。软件返回 `0` 不能单独证明这些时序关系。

```bash
mkdir -p tests/test-progs/dasics/riscv-dasics-call/build/m5out-o3/v5_full-trace
build/RISCV_DASICS/gem5.opt \
  --outdir=tests/test-progs/dasics/riscv-dasics-call/build/m5out-o3/v5_full-trace \
  --debug-flags=Commit,Fetch,Decode,Rename,IEW,IQ,RiscvMisc \
  --debug-file=dasics-call.trace \
  configs/dasics/riscv_dasics_o3_v5_full.py \
  tests/test-progs/dasics/riscv-dasics-call/build/riscv-dasics-call.elf
```

轨迹位于独立的 `v5_full-trace/dasics-call.trace`，核对时按调用 PC 和序号关联：

1. 由 Fetch 的 `Instruction PC ... created [sn:N]` 和调用助记符定位动态指令，
   对应到 Commit 的 `Committing instruction with PC` 及隐式
   `Setting MiscReg DASICS_RETURN_PC` 写入，区分 M 态初始化的 CSRRW。
2. 检查 Rename 的 `Serialize after instruction encountered.`、
   `Serialize before instruction encountered.` 和序列化等待。按同一线程与序号
   关联 IQ 的 `Issuing instruction PC`，确认序号更大的年轻指令不早于调用提交发射。
3. 成功调用本身不应出现带其序号的 `Executing squash after`；预测正确路径无需
   因调用成功而重新取指。普通 `branch mispred`、Decode 的
   `incorrect branch prediction detected at decode` 及异常冲刷仍可发生，
   其他 CSR 或控制指令的 SquashAfter 也不应误归到该调用。

## 诊断

失败时通过 Semihosting `SYS_WRITE0` 打印：

```text
DASICS call: case=NNN reason=NN
```

`case=001..067` 对应上述场景，失败退出码为用例编号；初始化失败打印
`case=000` 并以 `255` 退出。`124` 保留为宿主超时。

| reason | 检查失败 |
| --- | --- |
| 01 | MEDELEG 读回 |
| 02 | MPP/SPP 来源特权级 |
| 03 | M/S 异常路由 |
| 04 | 执行阶段或非法指令异常数 |
| 05 | cause |
| 06 | EPC |
| 07 | TVAL |
| 08 | FReason |
| 09 | ReturnPC |
| 10 | `ra` |
| 11 | `a0` 目的值或 m5_sum 结果 |
| 12 | `a1` 源值或源/目的别名结果 |
| 13 | 目标标记 |
| 14 | 完成/恢复标记 |
| 15 | `a4` ReturnPC 捕获值或应保持的值 |

`s1` 为用例编号，`s2/s3` 为来源态和非法指令 S 路由，`s4` 表示预期非法，
`s5` 为阶段，`s6` 为已接受的非法指令异常数，`s7/s8` 为目标/完成标记。
`s10` 为调用 PC，`s11` 为预期 ReturnPC，`a7` 为原始指令编码，
`a6` 为 `rd=x0` 目标返回时使用的 `PC+4`，`t6` 保存失败原因。
