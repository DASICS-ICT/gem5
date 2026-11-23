# riscv-dasics-reg-protection

## 实验记录

- [2026-11-18 · 软件寄存器保护开销（标量分量、两种向量 ABI 与 VLEN）](experiments/2026-11-18-register-protection.md)
- [2026-11-22 · 硬件辅助调用门的周期收益与 B 改写 0、1、6、12 个 s 寄存器的影响](experiments/2026-11-22-proreg-roi.md)

## 测试范围

单 hart、RV64 的 DASICS 寄存器保护功能测试，覆盖 Sv39 下的
`A → B → A` 调用、整数与浮点寄存器保存/清零/恢复，以及 B 对 A 私有数据的非法访问。
标量用例使用整数与浮点指令。向量实验另有普通 ABI 和向量调用变体两套受控 B，B 的内存访问仍走受 DASICS 检查的标量路径。

## 复现

在仓库根目录执行：

```bash
make dasics-test TEST=riscv-dasics-reg-protection CPU=v5_full
```

```bash
make dasics-clean TEST=riscv-dasics-reg-protection
```

使用现有 `build/RISCV_DASICS/gem5.opt` 和
`configs/dasics/riscv_dasics_o3_v5_full.py`。输出位于本目录
`build/m5out-o3/v5_full/`。运行器并行启动七个独立 gem5 进程，每项超时为 60 秒。
每项均要求进程退出码为 0，并出现对应的客体成功标记；全部满足才打印绿色 `OK`，
失败或超时显示红色 `FAIL/TIMEOUT`。

软件门 `normal` 的 `config.ini`、`stats.txt`、`run.log` 和 `case-result.json` 位于上述目录。
两种硬件辅助门 `normal-proreg`、`normal-proreg-gf` 和四个负向用例分别写入同名子目录。`result.json` 汇总七项结果。
根 Makefile 从 `run-result.txt` 读取软件门 `normal` 的总周期，包含启动和自检。
本组用例用于功能验收；软件门的每次调用开销见下文的 ROI 测量。

## 地址与内存布局

ELF 从物理地址 `0x80000000` 开始装载。U 态使用 Sv39，ASID 为 0，
虚拟地址与物理地址数值相同，实际经过三级页表和 4 KiB 叶页翻译。
PTE 的 A/D 位在进入 U 态前设置，页表建立不纳入后续调用测量。

| 区域 | 布局与权限 |
| --- | --- |
| 可信 A 代码 | U 态可读、可执行；UMainBound 只覆盖该代码区 |
| B 代码 | 独立代码页，U 态可读、可执行 |
| `.dasics_context` | 独立 4 KiB 页，U 态可读写、不可执行；开头放置 256 字节保存帧 |
| A 栈 | 独立 4 KiB 页，U 态可读写、不可执行 |
| `.bss.b_stack` | 独立 4 KiB 页，U 态可读写、不可执行；静态分配并复用 |
| 输入、输出 | 独立数据区域，U 态可读写、不可执行；调用时由 LibBound 限制 B 的权限 |
| M 态启动、页表、诊断数据 | 不建立 U 态映射 |
| 代码间及栈周围的保护页 | 不映射 |

两个栈均向低地址增长，初始栈指针指向区域上界，保持 16 字节对齐。
启动时设置 `DASICS_CONTEXT_BASE（0x8B4）` 为上下文页的虚拟地址，
`UMainCfg=0x2`，不关闭 U 域的各项 DASICS 检查，`LibCfg=0`。
M 态一次性设置 `JumpBound0=[untrusted_start, untrusted_end)`、`JumpCfg=1`，
允许 B 在自身代码页内跳转；返回可信门由 `ReturnPC` 授权。
主配置及可信区边界由 M 态初始化和回读；`UMainCfg/UMainBound` 的 CSR 编码要求
至少 S 态权限，可信 U 态也不能直接访问。U 态自检读取 ContextBase、
LibCfg 和 JumpCfg，并对五个数据页使用同一偏移的不同标记检查意外别名。
当前 DASICS 地址比较器仍使用配置默认的 50 位地址宽度，不随 `satp.MODE`
自动切换为 Sv39 的 39 位；本测试使用的低地址在两者下表示一致。

## 上下文保存帧

保存帧位于 `.dasics_context` 页首，CSR 指向其起始地址。
入口门写入保存帧，返回门读取并恢复；每次调用复用同一保存帧。

| 偏移（字节） | 大小（字节） | 内容 |
| --- | --- | --- |
| 0 | 8 | A 的 `ra` |
| 8 | 8 | A 的 `sp` |
| 16 | 8 | A 的 `gp` |
| 24 | 8 | A 的 `tp` |
| 32 | 8 | A 的 `fcsr`，使用 8 字节槽位 |
| 40–135 | 96 | `s0–s11`，每个寄存器 8 字节 |
| 136–231 | 96 | `fs0–fs11`，每个寄存器 8 字节 |
| 232–255 | 24 | 对齐填充 |

## 调用契约

| 寄存器 | 进入 B | 返回 A |
| --- | --- | --- |
| `a0` | 输入缓冲区地址 | 整数校验和 |
| `a1` | 输出缓冲区地址 | 不约定 |
| `a2` | 元素数量 | 不约定 |
| `fa0` | 双精度计算参数 | 浮点校验和 |

入口门保存 A 的上下文，清零不承载授权参数或运行必需状态的寄存器，
切换到 B 栈，并将 B 的私有 `fcsr` 设置为 RNE、异常标志为 0。
三个 LibBound 的地址在 `valid=0` 时更新，随后设置 `LibCfg=0xBBA`：

| 组 | 地址范围 | B 的权限 |
| --- | --- | --- |
| 0 | 输入区前 64 字节 | 只读 |
| 1 | 输出区完整 4 KiB 页 | 读写 |
| 2 | B 栈完整 4 KiB 页 | 读写 |

A 栈及保存区不授予 B。输出页包含测试观察区和计算结果，观察区不属于 A 的保存帧。

`DASICSCALL.J` 自动将 `ra` 和 `ReturnPC` 写为 `PC+4`，可信返回门位于该地址。
链接器计算跨代码段的调用编码，并断言返回门紧邻调用指令。
返回门的第一条指令读取 ContextBase，随后才访问保存帧，不依赖 B 返回时的 `sp/gp/tp`。
返回时以掩码 `0x888` 清除上述三个 LibBound 的 `valid` 位，`LibCfg` 变为 `0x332`，
六个边界地址保留。随后恢复 A 的上下文和 `fcsr`，保留 `a0/fa0` 返回值。
调用期间 ContextBase 保持不变。

## 用例与检查

| 用例 | 操作 | 成功判据 |
| --- | --- | --- |
| `normal` | 软件门连续执行两次受保护调用 | 参数、入口清零、结果、A 上下文恢复及边界撤销均符合预期 |
| `normal-proreg` | 硬件保护 `s0–s11`，软件保护 `fs0–fs11` | 整数槽保留哨兵，浮点槽包含 A 的原始位模式 |
| `normal-proreg-gf` | 硬件同时保护 `s0–s11` 和 `fs0–fs11` | 每次返回的一条 `LEAVE` 恢复全部 24 个寄存器，24 个保存槽均保留哨兵 |
| `context-read` | B 读取 A 保存帧 | 预期的 DASICS 读异常，目的寄存器及目标数据不变 |
| `context-write` | B 写入 A 保存帧 | 预期的 DASICS 写异常，目标数据不变 |
| `stack-read` | B 读取 A 栈 | 预期的 DASICS 读异常，目的寄存器及目标数据不变 |
| `stack-write` | B 写入 A 栈 | 预期的 DASICS 写异常，目标数据不变 |

三个正常用例使用同一段 B 代码和相同的三个 LibBound，连续调用两次，每轮使用不同的寄存器和 `fcsr` 种子。
在 `normal-proreg-gf` 中，可信入口依次执行 `PROREG.G.I 0xfff` 和 `PROREG.F.I 0xfff`，返回门执行一条 `LEAVE`。
A 逐项核对 12 个整数原值和 12 个浮点寄存器的原始 64 位值，
并独立检查保存帧中各槽的内容。三种门均通过软件保存并恢复 `fcsr`。
B 在使用临时寄存器前，将全部 GPR、FPR 和入口 `fcsr` 记录到授权输出区；
A 据此检查授权参数、B 栈指针、返回地址及其余寄存器清零。

输入为四条 `{uint64_t, double}` 记录，两个字段均依次为 1、2、3、4，
浮点参数为 2.0。B 将整数加 1、浮点数乘 2，写入输出记录，返回
`a0=14`、`fa0=20.0`。返回前主动覆盖 `s0–s11`、`fs0–fs11`、`gp/tp`、
`fcsr`，并将 `sp` 置零，检查可信返回门能独立定位保存帧并恢复 A。
A 还检查输入未改变、B 栈可读写、A 栈哨兵不变、三个 `valid` 已清零且边界地址保留。

四项负向用例各自从启动开始运行。故障地址仍有有效 U 态页表映射，必须产生
`mcause=24`、`MPP=U`、精确的故障 `mepc/mtval`，且 `FReason` 为读异常 2
或写异常 3。M 态处理程序核对目的寄存器、A 保存帧和 A 栈目标未改变，
以及调用 CSR 状态后，直接通过 Semihosting 退出，不恢复 A 或继续执行 B。

## ROI 测量

在仓库根目录执行。每次使用新的批次目录保存原始结果。

```bash
test_dir=tests/test-progs/dasics/riscv-dasics-reg-protection
make -j8 -C "$test_dir/src" roi
python3 "$test_dir/measure.py" --jobs 8 --outdir "$test_dir/build/runs/roi-$(date +%Y%m%d-%H%M%S)"
```

四种调用门模式均使用 v5_full O3、Sv39 和三个 LibBound，并保留相同的控制状态处理、独立栈、私有浮点环境及边界设置与撤销。

| 模式 | 进入 B 前的数据保护操作 | 返回后的数据保护操作 |
| --- | --- | --- |
| `boundary`（B） | 无 | 无 |
| `save`（S） | 保存 24 个寄存器 | 无 |
| `restore`（SR） | 保存 24 个寄存器 | 恢复 24 个寄存器 |
| `software`（SCR） | 保存 24 个寄存器，清零 55 个寄存器 | 恢复 24 个寄存器 |

四组的 A 循环、门入口、B 入口、ROI 标记和数据页地址一致。门内指令地址随指令数量变化。前三组仅用于性能归因；完整寄存器保护采用 SCR。计时用 B 仅使用调用者保存寄存器，故 S 组能够在不恢复保存帧的情况下完成相同计算。

空负载直接返回整数零和浮点零。固定计算负载处理四条记录并返回 14 和 20.0。各组在同一调用点预热 128 次，然后在可信 U 态循环外用一对 `m5_work_begin/end` 包围 1024 或 4096 次调用。固定成本包括循环控制和结束前的返回值捕获。初始化、入口快照和结果校验均在计时区间外。BEGIN 事件重置统计并保留缓存和预测器状态，END 事件导出区间统计。

以同一负载和循环长度的 ROI 周期除以调用次数得到各模式的每次调用周期。保存取 S−B，恢复取 SR−S，清零取 SCR−SR。清零的差值包含由保存与恢复间隔改变引起的流水线效应。三个差值之和等于完整保护增量 SCR−B。

运行器核对 tick 差、实际 CPU 时钟周期、`simTicks` 与 `numCycles`。S−B、SR−S、SCR−SR 的每次提交指令差应分别为 24、24、55；各模式下固定计算比空负载多 53 条提交指令。用 1024 与 4096 次调用比较各分量，并以 1% 为总增量收敛阈值。每个作业保留 `run.log`、`config.ini`、`roi.json` 和 `roi-stats.txt`；批次内的 `results.csv` 和 `summary.csv` 分别记录原始统计及差值。

### 整数硬件辅助门配对测量

```bash
test_dir=tests/test-progs/dasics/riscv-dasics-reg-protection
make -j8 -C "$test_dir/src" proreg-roi
python3 "$test_dir/measure.py" --comparison proreg --jobs 8 \
    --outdir "$test_dir/build/runs/proreg-roi-$(date +%Y%m%d-%H%M%S)"
```

在同一批次比较 `software` 和 `proreg` 两种门。空函数和固定计算各预热 128 次，分别测量 1024 和 4096 次调用。
`summary.csv` 的 `saved_cycles_per_call` 为软件门与硬件辅助门的 ROI 周期差除以调用次数。
每个配对应少提交 34 条指令，其中包含 12 条加载和 12 条存储；同一负载以 4096 次调用为参照，两个批长的周期节省量相对偏差应在 1% 以内。

### B 在返回前改写受保护的整数寄存器

两种调用门始终保护全部 `s0–s11`。B 设置好 `a0/fa0` 后执行 12 条独立的整数立即数写，再返回。
前 `k` 条写 `s0` 起的连续寄存器，剩余位置写返回前已用完的临时或参数寄存器。`k` 取 0、1、6、12。
本轮 0 档也执行 12 条写；按同一负载和批长计算相对 0 档的节省量变化。

```bash
test_dir=tests/test-progs/dasics/riscv-dasics-reg-protection
batch="$test_dir/build/runs/clobber-roi-$(date +%Y%m%d-%H%M%S)"
make -j32 -C "$test_dir/src" clobber-roi ROI_COUNTS="4 1024 4096"
python3 "$test_dir/check_clobber.py" --jobs 16 --outdir "$batch/checks" &&
    python3 "$test_dir/measure.py" --comparison clobber --jobs 32 --outdir "$batch/measurements"
```

短用例检查 B 实际提交的写指令和返回后 A 的自检结果。计时用例分别测量 1024 和 4096 次调用，
在 `measurements/summary.csv` 中给出两种门的周期、每次调用的节省量和相对同批 0 档的变化。

### v5_full 热态基线

2026-11-18，单 hart、2 GHz，五项功能回归和八组 ROI 测量通过。单位为周期/次。

| B 负载 | 调用次数 | 完整软件保护 | 边界对照 | 保护增量 |
| --- | ---: | ---: | ---: | ---: |
| 空函数 | 1024 | 325.0322 | 238.0322 | 87.0000 |
| 空函数 | 4096 | 325.0081 | 238.0081 | 87.0000 |
| 固定计算 | 1024 | 347.0449 | 261.0439 | 86.0010 |
| 固定计算 | 4096 | 347.0112 | 261.0110 | 86.0002 |

两种批长的增量偏差分别为 0% 和 0.000852%。八组 ROI 的 L1D demand 访问全部命中，Store Queue 转发均为零。gem5 对值为零的缓存统计可省略输出；解析器以访问数、命中数与缺失数核对。结论适用于该预热负载和配置。

两种模式各用 4 次调用重放，轨迹中均有 4 次完整门调用在 ROI 内提交。计时端点取 marker 触发退出事件的 tick，本次轨迹中 marker 在其后 2 个 CPU 周期提交。详细记录见[测量汇总](build/runs/20261118-roi-02/measurements/summary.csv)和[轨迹验收](build/runs/20261118-roi-02/trace-validation.json)。

### 保存、清零与恢复的配对增量

2026-11-18，本机以最多 8 路并行完成四种模式、两种负载和两种批长，共 16 个作业。表中单位为每次调用增加的 CPU 周期。

| B 负载 | 调用次数 | 保存（S−B） | 清零（SCR−SR） | 恢复（SR−S） | 总计（SCR−B） |
| --- | ---: | ---: | ---: | ---: | ---: |
| 空函数 | 1024 | 24 | 42 | 21 | 87 |
| 空函数 | 4096 | 24 | 42 | 21 | 87 |
| 固定计算 | 1024 | 24 | 41.000977 | 21 | 86.000977 |
| 固定计算 | 4096 | 24 | 41.000244 | 21 | 86.000244 |

各组的 ROI 周期与 tick 区间一致，20 项提交指令差校验全部通过。B 和 SCR 的 8 项总周期逐项复现前次热态基线。16 项的 L1D demand 缺失数和 Store Queue 转发数均为零。4096 次调用时，加入清零使每次调用增加 41–42 个周期，约占总保护增量的 48%。该差值包括清零指令与其他操作在 O3 流水线中的重叠效应。

四组原始周期及配对增量见[分量汇总](build/runs/20261118-components-01/measurements/summary.csv)，与前次基线的逐项对照见[复核记录](build/runs/20261118-components-01/review.json)。

## 向量 ABI 保护

从仓库根目录运行以下命令。每档 VLEN 先验收两套 ABI 的功能，再执行 2 种 ABI × 2 种门 × 2 个负载 × 2 个批长的配对测量。

```bash
test_dir=tests/test-progs/dasics/riscv-dasics-reg-protection
make -j18 -C "$test_dir/src" vector-roi-all
python3 "$test_dir/vector_measure.py" --vlen 128 256 512 1024 --jobs 8 \
    --outdir "$test_dir/build/runs/vector-$(date +%Y%m%d-%H%M%S)"
```

| 接口 | 软件保护门 | 匹配的对照门 |
| --- | --- | --- |
| 普通 LP64D | 进 B 前清零整个 v0–v31，返回时向量数据可被覆盖 | 同一标量接口，省去向量清零 |
| 向量调用变体 | 保存 v1–v7 和 v24–v31，清零除 v8 外的 31 个寄存器，返回时恢复这 15 个寄存器 | 同样用 v8 传参与返回，计时 B 自行遵守该变体的保存约定 |

两套接口都执行完整整数与浮点保护，并保留三个数据边界、独立栈、私有 fcsr。向量实验的门在返回时统一将 vstart 置零。vcsr 在启动时初始化。B 使用 e64、m1 和一个完整向量（vl=VLEN/64），相应有 2、4、8、16 个有效元素。清零门先以 e8、m8、VLMAX 清除整组，然后切回 B 的配置；两条配置指令均计入保护开销。变体保留 v8，在 m1 下分别清除 v9–v15。15 个寄存器单向搬运量为 240、480、960 或 1920 字节，按 8、4、2、1 的自然对齐组保存与恢复。保存区使用独立的 Sv39 私有页，通过 ContextBase 加固定偏移定位。

功能探针给全部寄存器的各个 64 位元素写入互异的非零值，再以 vl=1 调用保护门。B 检查原活动范围之外的元素是否也被清除，变体还逐位检查 v8 入参。B 主动覆盖 15 个保存寄存器并生成新的 v8 返回值，随后 A 检查整组恢复与完整返回值。

在可信 U 态预热 128 次后，测量 1024 或 4096 次调用。变体传入 v8，第 i 个元素为 11+i（i 从 0 起）；空函数原样返回，固定计算函数执行相同的四条标量记录计算，再把每个向量元素加一。普通 ABI 始终通过标量参数和返回值传递计算结果。每个增量均在相同 VLEN、ABI、负载、批长下由保护组减去对照组。输出目录下按 `vlen-<位数>/` 保存作业，根目录的 `summary.csv` 汇总各组增量与收敛情况。

### VLEN=128 的热态结果

2026-11-18，v5_full O3，2 GHz。单位为每次调用的 CPU 周期。对照与保护均已启用整数及浮点寄存器保护。

| ABI | B 负载 | 对照（4096 次） | 保护（4096 次） | 保护增量（4096 次） | 保护增量（1024 次） |
| --- | --- | ---: | ---: | ---: | ---: |
| 普通 | 空函数 | 330.0083 | 344.0100 | 14.0017 | 14.0068 |
| 普通 | 固定计算 | 352.0117 | 361.0144 | 9.0027 | 9.0107 |
| 向量变体 | 空函数 | 331.0081 | 359.0105 | 28.0024 | 28.0098 |
| 向量变体 | 固定计算 | 353.0449 | 377.0144 | 24.0032 | 24.0127 |

两个功能探针与 16 个计时作业通过。普通 ABI 每次多提交 6 条指令和 34 个微操作，向量变体多提交 30 条指令和 73 个微操作。两种批长下各配对增量的最大相对差为 0.090%。本批 ROI 中 L1D demand 缺失和 Store Queue 转发均为零。这里的增量衡量相同 ABI、相同 B 负载下，向量保护对整次调用的影响。详细记录见[结果汇总](build/runs/20261118-vector-abi-01/results/summary.csv)及[动态指令与静态门代码核对](build/runs/20261118-vector-abi-01/review.json)。

### 向量长度对增量的影响

下表来自同一批次，取 N=4096，单位为相对同宽度、同 ABI 对照门的周期/次。128 位是模型默认配置；256、512、1024 位使用同一套 v5_full 参数，仅调整 ISA 的 VLEN。ELEN 和缓存行大小分别固定为 64 位、64 字节。

| VLEN（位） | 变体单向保存量 | 普通：空函数 | 普通：固定计算 | 变体：空函数 | 变体：固定计算 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 128 | 240 B | 14.0017 | 9.0027 | 28.0024 | 24.0032 |
| 256 | 480 B | 14.0017 | 9.0027 | 28.0024 | 24.0032 |
| 512 | 960 B | 14.0017 | 9.0027 | 28.0024 | 24.0032 |
| 1024 | 1920 B | 14.0017 | 9.0027 | 29.0024 | 25.0032 |

8 个全宽功能探针和 64 个计时作业通过。128 位的 16 个作业逐项复现前次已记录的 ROI 计数。1024 与 4096 次调用的增量差异均小于 0.1%。所有 ROI 的 L1D demand 缺失、Store Queue 转发均为零。

普通 ABI 的额外工作始终为 6 条提交指令、34 个微操作。变体始终为 30 条、73 个；宽度改变了每次传输的数据量。VLEN=1024 时，一个寄存器占两条缓存行，变体保护相对自身对照的 L1D demand 访问数从 30 次/调用增至 60 次/调用，两种负载的周期差均增加 1。这些数字描述 gem5 当前向量执行与访存时序下的热态结果。

[测量汇总（含两种批长、对照组与保护组）](build/runs/20261118-vector-widths-01/results/summary.csv) · [4096 次调用的四宽度对比](build/runs/20261118-vector-widths-01/width-comparison.csv) · [最终全宽功能验收](build/runs/20261118-vector-widths-01/final-functional/checks.json)

## 源码阅读

1. [context.h](src/context.h) 和 [link.ld](src/link.ld) 定义保存帧及各页的位置。
2. [runtime.inc](src/runtime.inc) 的 `_start` 建立 Sv39 映射并进入 U 态，`machine_trap_handler` 负责异常检查和退出。
3. [gate.inc](src/gate.inc) 的 `protected_gate` 和 `return_gate` 由功能测试与计时程序共用。[功能测试](src/riscv-dasics-reg-protection.S) 包含 A 的检查和 B 的隔离探针。
4. [计时程序](src/riscv-dasics-reg-roi.S) 的 `roi_loop` 调用门，`roi_work_begin/end` 标记测量区间。[全系统配置](../../../../configs/dasics/riscv_dasics_reg_protection_o3_v5_full.py) 处理事件，[measure.py](measure.py) 配对检查并汇总结果。
