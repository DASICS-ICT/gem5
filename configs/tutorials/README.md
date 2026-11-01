# gem5 学习进度与记录

更新日期：2026-11-01。学习基线：官方 gem5 `v26.0.0.0`，分支 `dasics-dev`。

当前主线是逐渐过渡到 **RISC-V Linux 全系统仿真**，为后续 DASICS 的
特权态、异常隔离和性能研究准备环境。SE/FS 与 RiscvBoard 硬件组成的
概念课已通过理解检查，Linux 启动资源角色的理解检查也已通过。
下一课只读核对 workload 引用的具体资源和版本。

RVV 暂停在“同一个 23 元素加法程序适配 VLEN=256 和 VLEN=128”。
恢复时从本文的“RVV 暂停与恢复入口”继续，不必重做已完成的基础课程。

本文保存学习进度、实验索引和续学入口。详细复现流程与分析保留在对应
Git 提交正文中；RVV 概念和代码用法同步整理在
[飞书知识文档][rvv-notes]。

## 当前进度

| 内容 | 状态 | 已到达的位置 |
| --- | --- | --- |
| 构建、Git、SE 基础 | 已练习 | 增量构建、配置脚本、本地 RISC-V 程序 |
| 缓存与统计 | 已完成相关实验 | 容量、行大小、相联度、冲突、预热、ROI |
| O3 性能分析 | 已完成相关实验 | IPC、提交宽度、发射宽度、ALU 延迟与数量 |
| RVV 基础 | 暂停，已有可复跑结果 | 配置 VL、向量加法、分批循环、不同 VLEN |
| RISC-V Linux FS | SE/FS、硬件组成与资源角色已完成；启动未验证 | 下一课：workload 资源元数据 |
| DASICS 移植 | 尚未开展实现 | 待 Linux 基线建立后规划 |

下文的命令和非链接路径以仓库根目录 `gem5/` 为基准。
`build/` 和 `m5out/` 是本地生成产物；它们不随源码提交分发。

## 已完成内容索引

以下按已有实验提交回填，不推断每次学习发生的日期。
每条提交的正文包含当时的流程、参数、结果和分析。
例如，`git show f68edd471b` 可查看最近一次实验记录。

| 记录 | 已学主题 | 主要实验提交 |
| --- | --- | --- |
| 01 | 官方版本、分支与标签；提交、推送和格式钩子；RISC-V 构建入口 | `915c5e0dc5` |
| 02 | Python 配置、m5、CPU/Board 时钟、统计读取和 `rg` | `13eeec95ec` |
| 03 | AtomicSimpleCPU 与 TimingSimpleCPU 的区别 | `1b1f33074c` |
| 04 | 为 TimingSimpleCPU 加入 L1 缓存 | `fc5b38540c` |
| 05 | 缩小 L1D 容量并观察未命中与周期 | `06a992f53f` |
| 06 | 将缓存行从 64 B 改为 32 B | `bb0b5d51a5` |
| 07 | 相联度、组数计算；Hello 对相联度变化不敏感 | `5626b83d0a` |
| 08 | 交叉编译本地 C 程序、ELF 与反汇编 | `5d3bfbc25e` |
| 09 | 构造受控的三条缓存行冲突；比较 2 路和 8 路 | `507de1bb4c` |
| 10 | 使用 m5ops 划定 ROI，排除启动和输出 | `da5d8c96f1` |
| 11 | 预热缓存；重置统计与缓存状态的区别 | `071b340197` |
| 12 | 改变数据布局，消除组冲突 | `f62c73e92d` |
| 13 | CPI/IPC、O3 多发射与乱序执行 | `5267ab9033` |
| 14 | 四宽提交与 `commitEligibleSamples` | `94812fe9be` |
| 15 | 四宽发射；相近 IPC 可以对应不同瓶颈 | `53bc0173fb` |
| 16 | ALU 结果延迟、流水化与循环依赖 | `551fe72c50` |
| 17 | 增加 ALU 数量；结合有效配置与资源忙统计解释结果 | `15f5adb135` |
| 18 | VLEN、ELEN、vlenb；128/256 bit 寄存器探测 | `601dbccdf8` |
| 19 | SEW、LMUL、AVL、VL、VLMAX；vsetvli 与策略标志 | `ca4478f078` |
| 20 | 四个 C intrinsics；加载、逐元素加法和存储 | `b4dbaeb6d2` |
| 21 | 23 元素分批循环；VLEN=256 下处理 8、8、7 个元素 | `4c9efff3fc` |
| 22 | 复用程序适配 VLEN=128；处理 4、4、4、4、4、3 个元素 | `f68edd471b` |

### 代码入口

- 构建：[Makefile](../../Makefile)。`make riscv` 每次调用 SCons 检查依赖，
  由 SCons 决定增量重编译范围；`make clean` 清理 `build/RISCV`。
  入口统一使用系统 Python/Protobuf，并清理可能混入 Conda 的搜索路径；
  持久构建日志位于仓库外的 `../build-logs/`。
- 基础配置：[hello_riscv.py](hello_riscv.py)、
  [hello_riscv_1GHz.py](hello_riscv_1GHz.py)、
  [hello_riscv_timing.py](hello_riscv_timing.py)。Python 配置通过 gem5
  执行并建立 SimObject；`m5` 是仿真控制接口，访客中的 m5ops 用于向
  仿真器请求统计等操作。
- 缓存参数：[hello_riscv_timing_l1.py](hello_riscv_timing_l1.py)、
  [L1D 4 KiB](hello_riscv_timing_l1d4k.py)、
  [32 B 行](hello_riscv_timing_l1d4k_line32.py)、
  [2 路 L1D](hello_riscv_timing_l1d4k_2way.py)。
- 本地负载：[hello.c](../../tests/test-progs/tutorials/hello.c) 与
  [own_hello_riscv.py](own_hello_riscv.py)；冲突负载入口为
  [cache_conflict.c](../../tests/test-progs/tutorials/cache_conflict.c) 和
  [cache_conflict.py](cache_conflict.py)。
- ROI：[cache_conflict_roi.c](../../tests/test-progs/tutorials/cache_conflict_roi.c)
  与 [cache_conflict_roi.py](cache_conflict_roi.py)。当前 C 文件已经包含
  预热，第三个数据位置已经改为偏移 4160；旧冲突布局需要参考对应历史版本。
- O3：[基线](cache_conflict_roi_o3.py)、
  [四宽提交](cache_conflict_roi_o3_commit4.py)、
  [四宽发射](cache_conflict_roi_o3_issue4.py)、
  [三周期 ALU](cache_conflict_roi_o3_alu3.py)、
  [八个三周期 ALU](cache_conflict_roi_o3_alu3_count8.py)。

## 需要保留的实验结论

### 统计与控制变量

- 区分宿主运行时间和模拟系统时间；本批实验的 `simFreq` 为
  `10^12 tick/s`，模拟秒数为 `simTicks / simFreq`。
- 在相同统计区间，CPI = CPU 周期数 / 提交指令数，IPC 为其倒数。
  O3 的平均 IPC 可以大于 1；它描述吞吐率，不能当作单条指令的延迟。
- CPU 与 Board 的时钟分别配置；从生成的 `config.ini` 核对实际参数。
  输出目录名称只是标签。
- `m5_reset_stats(0, 0)` 重置计数器，保留缓存等微体系结构状态。
  ROI 示例在输出结果之前调用 `m5_dump_stats(0, 0)`；退出时还会再次统计，
  比较时取第一段统计，并保留少量边界开销的解释。
- 部分计数器采用 `nozero`，数值为零时省略输出。对这些缓存计数器可用
  `demandAccesses = demandHits + demandMisses` 交叉确认。
- 反汇编用于确认真实访存和循环指令；投机发射、缓存请求与最终提交指令
  统计不同事件，不能直接互换。

读取 ROI 的示例：

```bash
sed -n '1,/End Simulation Statistics/p' \
  m5out/cache-conflict-roi-spread-o3-commit4-2way/stats.txt |
  rg 'simInsts|simTicks|core\.(numCycles|cpi|ipc)\s|commitEligibleSamples'
```

### 缓存冲突与数据布局

以下 ROI 使用 gem5 v26.0.0.0、单核 1 GHz TimingSimpleCPU、3 GHz Board、
32 KiB/8 路 L1I、4 KiB L1D、64 B 行、LRU、8 GiB DDR3-1600，关闭 L1
预取器；循环执行 10000 次，每次加载三个字节，预期和为 60000。

| 布局与预热 | L1D 相联度 | ROI 指令数 | L1D 未命中 | CPU 周期 |
| --- | --- | ---: | ---: | ---: |
| 同组，未显式预热 | 2 | 80012 | 30000 | 1497338 |
| 同组，未显式预热 | 8 | 80012 | 3 | 140447 |
| 同组，已预热 | 2 | 80008 | 30000 | 1497320 |
| 同组，已预热 | 8 | 80008 | 0 | 140009 |
| 第三条行移至另一组，已预热 | 2 | 80008 | 0 | 140009 |

对于该普通组相联配置，组数 = 容量 /（行大小 × 相联度）。4 KiB、64 B、
2 路得到 32 组。原来的 4096 B 对齐数组偏移 0、2048、4096 映射到同组；
把第三个偏移改为 4160 后，三条行分布到组 0、0、1。
容量和相联度不变，也可以通过数据布局消除这组访问的冲突。
预热能够移走首次装入开销，但无法让 2 路的一组同时保留三条行。

原始证据目录依次为 `m5out/cache-conflict-roi-{2way,8way}`、
`m5out/cache-conflict-roi-warm-{2way,8way}`、
`m5out/cache-conflict-roi-spread-2way`；结果适用范围是上述负载与参数。

### O3 吞吐与瓶颈证据

下表使用预热后的分散布局、2 路 L1D 和同一个标量 ROI；其余存储与时钟
条件沿用上表。各次提交指令数均为 80008，L1D 未命中为 0。
O3 基线发射和提交宽度均为 8，整数 ALU 数量为 6、结果延迟为 1 周期。

| 配置 | CPU 周期 | IPC | commitEligibleSamples |
| --- | ---: | ---: | ---: |
| TimingSimpleCPU | 140009 | 0.571449 | 不适用 |
| O3 基线 | 10030 | 7.976869 | 9998 |
| O3，仅提交宽度改为 4 | 20025 | 3.995406 | 20000 |
| O3，仅发射宽度改为 4 | 20028 | 3.994807 | 6666 |
| O3，ALU 结果延迟改为 3 周期 | 30043 | 2.663116 | 9998 |
| O3，三周期 ALU 数量由 6 改为 8 | 30043 | 2.663116 | 9998 |

特别保留：在 [commit.cc](../../src/cpu/o3/commit.cc) 的
`Commit::commitInsts()` 中，`num_committed == commitWidth` 时才递增
`commitEligibleSamples`。它统计达到当前提交带宽上限的周期数。
四宽提交实验中，20025 个 ROI 周期有 20000 个周期提交满 4 个操作，
占 99.875%；该标量 ROI 的指令与微操作恰好一一对应。
结合只改变提交宽度的八宽对照，支持提交带宽是该配置的主要吞吐瓶颈。

解读这个计数器必须同时查看 `commitWidth` 和周期分母：四宽发射实验的
提交宽度仍为 8，6666 统计的是提交满 8 个操作的周期。
高利用率本身不足以独立证明瓶颈，还需控制变量和相关阶段统计。

三周期 ALU 下增加数量没有改善该 ROI；两次 `statFuBusy::IntAlu` 都为 0。
该统计表示就绪操作申请功能单元失败的次数。循环携带依赖仍等待三周期
结果，八条指令一轮的吞吐上界约为 8/3 IPC，与结果相符。
计数分布展示频率，不能从直方图恢复固定的逐周期执行顺序。

## RVV 暂停与恢复入口

已练习的内容：

- VLEN、ELEN、`vlenb`、SEW、LMUL、AVL、VL、VLMAX 的区别与单位；
  `VLMAX = LMUL × VLEN / SEW`。
- `vsetvli` 的普通寄存器操作数、`vtype`/`vl`/`vstart` 的作用；
  `ta/tu/ma/mu` 的概念。尚未做掩码数据运算实验。
- 按返回 VL 编程。规范在部分 AVL 范围内允许不同选择，不能把
  `VL = min(AVL, VLMAX)` 当作所有实现的强制规则。
- `__riscv_vsetvl_e32m1`、`__riscv_vle32_v_u32m1`、
  `__riscv_vadd_vv_u32m1`、`__riscv_vse32_v_u32m1`。
- 逐元素加法、标量结果校验、分批循环、尾批处理和 C 指针元素偏移；
  反汇编中的常量长度 `vsetivli` 与动态长度 `vsetvli`。

入口文件：

| 用途 | 配置 | C 程序 |
| --- | --- | --- |
| 读取 vlenb | [rvv_probe.py](rvv_probe.py) | [rvv_probe.c](../../tests/test-progs/tutorials/rvv_probe.c) |
| vsetvli 配置探测 | [rvv_vl.py](rvv_vl.py) | [rvv_vl.c](../../tests/test-progs/tutorials/rvv_vl.c) |
| 当前分批加法 | [rvv_add.py](rvv_add.py) | [rvv_add.c](../../tests/test-progs/tutorials/rvv_add.c) |

`rvv_probe.py` 和 `rvv_vl.py` 当前为 VLEN=256；`rvv_add.py` 当前为
VLEN=128。修改一个配置文件只影响使用该文件的运行。
最初的单批 8 元素版本保存在 `b4dbaeb6d2`，当前 C 文件已经是 23 元素循环。

### 最近一次 RVV 学习：2026-11-01，适配 VLEN=128

- 目标：复用 23 元素程序，确认循环按运行时返回的 VL 适应较小容量。
- 操作：仅将 `rvv_add.py` 中的 `cpu.isa[0].vlen` 从 256 改为 128，
  使用已有工作负载二进制运行。
- 验证：两次 `config.ini` 分别确认 VLEN=256/128，ELEN 都为 64；
  两次均输出 `PASS: 23 elements` 和 `Guest exit code: 0`。
- 结论：寄存器容量改变了批次大小，SEW=32 和逐元素结果保持一致。
  本次验证功能适配，不据此推断执行时间按 VLEN 成比例变化。
- 实验提交：`f68edd471b`；此前分批循环提交：`4c9efff3fc`。
- 下一步：暂停 RVV，转入 SE 与 FS 的概念学习。

| VLEN | VLMAX，e32/m1 | 各批 VL | 起始下标 | 本地证据目录 |
| --- | ---: | --- | --- | --- |
| 256 bit | 8 | 8、8、7 | 0、8、16 | `m5out/rvv-add-loop-vlen256` |
| 128 bit | 4 | 4、4、4、4、4、3 | 0、4、8、12、16、20 | `m5out/rvv-add-loop-vlen128` |

### 恢复时的最短复跑

先阅读当前 `rvv_add.c` 的循环，确认 `rvv_add.py` 仍为 VLEN=128。
在仓库根目录执行以下命令；单独使用恢复练习的输出目录。

```bash
mkdir -p build/workloads m5out/rvv-add-resume-vlen128
/usr/bin/riscv64-linux-gnu-gcc \
  -std=c11 -O2 -static -march=rv64gcv -mabi=lp64d \
  tests/test-progs/tutorials/rvv_add.c \
  -o build/workloads/rvv_add &&
./build/RISCV/gem5.opt \
  -d m5out/rvv-add-resume-vlen128 \
  configs/tutorials/rvv_add.py \
  > m5out/rvv-add-resume-vlen128/run.log 2>&1

rg '^(offset=|PASS:|Guest exit code:)' \
  m5out/rvv-add-resume-vlen128/run.log
rg '^(vlen|elen)=' m5out/rvv-add-resume-vlen128/config.ini
```

成功判据是六批长度为 4、4、4、4、4、3，23 个结果全部通过，访客退出码为 0，
并确认有效配置为 `vlen=128`、`elen=64`。

以后恢复 RVV 可依次学习 LMUL 分组、实际掩码操作、跨步/索引访存、归约，
再进入向量 ROI 性能及 Linux 向量状态管理。这些均为待学内容，
不作为开始 Linux 基础学习的前置要求。

## Linux 全系统学习计划

采用“每次一个主题、一次理解检查或小实验”的节奏。以下是根据官方资料
和当前版本 RISC-V 示例安排的学习顺序，尚未执行 Linux 启动。

| 顺序 | 学习主题 | 本次动作 | 完成判据 |
| --- | --- | --- | --- |
| 1，已完成 | SE 与 FS 的区别 | 对比现有 SE 配置和官方 FS 入口，只读代码 | 能解释 SE 中谁处理系统调用，以及研究真实内核/特权态为何需要 FS |
| 2，已完成 | 模拟硬件与 RiscvBoard | 识别 CPU、缓存、内存、设备及连接关系 | 能区分硬件配置和待加载的软件资源 |
| 3，角色已完成，元数据待学 | Linux 启动资源 | 先认识固件、内核、设备树、磁盘镜像与根文件系统，再阅读 workload 元数据 | 能说明各资源用途和来源，不混用不同平台资源 |
| 4 | 官方配置与退出事件 | 阅读 set_workload、Simulator 和 ExitHandler | 能区分内核启动、用户态启动脚本、预期仿真结束，以及两种日志 |
| 5 | 启动前准备 | 确认执行主机、资源版本、缓存/日志位置、空间与下载；核对配置 | 得到可复现的资源清单和启动命令 |
| 6 | 第一次 Linux 启动 | 使用配套 RISC-V 官方示例运行并保存控制台输出 | 内核与用户态启动流程完成，发生预期结束事件 |
| 7 | 在 Linux 中运行自己的程序 | 学习工作负载注入、结果回收和统计范围 | 能重复运行并核对访客程序结果，再规划 DASICS 实验 |

### 官方资料与当前版本入口

- [Learning gem5 基础配置][simple-config] 中的 SE/FS 说明用于第一课。
  SE 由仿真器提供系统调用服务；FS 运行访客内核并模拟相应硬件。
- [Standard Library Overview][stdlib] 用于认识 Board、Processor、
  Memory、CacheHierarchy、Resources 与 Simulator 的分工。
- [X86 Full-System Tutorial][fs-tutorial] 用于理解“构建系统、绑定
  workload、处理退出事件”的流程；具体 RISC-V 平台和 API 以本仓库
  v26.0.0.0 示例为准，不直接套用其中的 X86/KVM 配置。
- [gem5 Resources][resources] 用于理解资源标识、版本、内核与磁盘镜像。
  示例最终使用哪个内核、固件与磁盘文件，需要在资源准备时核对元数据。
- 当前 RISC-V 入口是
  [riscv-ubuntu-run.py](../example/gem5_library/riscv-ubuntu-run.py)，
  硬件组件实现可从
  [RiscvBoard](../../src/python/gem5/components/boards/riscv_board.py) 查阅。

已经阅读的官方 RISC-V 脚本使用两个 Timing 核、3 GHz CPU/Board、
3 GiB DDR4，以及 `riscv-ubuntu-24.04-boot` 资源版本 `2.0.0`。
它以启动事件为控制点：内核启动和 `AFTER_BOOT` 事件发生后继续仿真，
`AFTER_BOOT_SCRIPT` 事件发生后结束仿真。
细节参见脚本中的三个 ExitHandler。
访客控制台位于输出目录下的 `board.platform.terminal`，
宿主运行日志用于记录仿真器输出；两者需要分别查看。
这些是配置预期，当前尚无本项目 Linux 启动成功的验证结果。

启动前准备时再确认实际执行主机和资源使用。预计超过几分钟的任务按
项目运行约定使用具名 tmux 会话和持久日志。
Linux 基线建立后，再分别安排内核替换、异常路径、DASICS 与性能验证。

## Linux 逐次学习记录

### 2026-11-01：SE 与 FS 的区别

- 状态：已讲解，理解检查通过。
- 目标：理解此前 RVV 程序为何能在未启动访客 Linux 的情况下执行，
  并判断需要真实 Linux 内核参与的 DASICS 研究应采用哪种模式。
- 学习内容：SE（Syscall Emulation）执行访客用户程序及其用户态库代码，
  由 gem5 提供系统调用仿真；本课程的 Linux FS（Full System）配置让
  模拟硬件运行访客 Linux 内核，由它处理访客程序的系统调用和内核路径。
  宿主系统负责运行 gem5，与模拟机器中的访客系统分开理解。
- CPU 模型：SE/FS 与 Timing/O3 是不同选择。当前 SE 配置和官方 RISC-V
  FS 示例都使用 Timing 核；更换 CPU 模型本身不会加载 Linux。
- 代码入口：[rvv_add.py](rvv_add.py) 使用
  `board.set_se_binary_workload(binary)`；
  [官方 RISC-V FS 示例](../example/gem5_library/riscv-ubuntu-run.py)
  通过 `board.set_workload(...)` 绑定 Linux 启动 workload。
  `set_workload` 是通用接口，具体模式依赖 workload 的配置行为；
  `RiscvBoard` 本身也支持 SE，不能只凭类名判断模式。
- 已核对证据：已有 RVV 输出的 `config.ini` 包含 `full_system=false`。
  核对命令如下，仅用于阅读已有结果：

```bash
rg -n '^\[root\]|^full_system=' \
  m5out/rvv-add-loop-vlen128/config.ini
```

- 理解检查：要观察 DASICS 权限异常发生后 Linux 内核如何
  处理它，应选择 SE 还是 FS？之前的 RVV SE 测试是否已覆盖这条内核路径？
- 回答与判定：学习者选择 FS，并确认此前 SE 测试没有覆盖该路径；
  与本课判据一致，理解检查通过。
- 验证边界：已核对配置与[官方 SE/FS 说明][simple-config]，
  本课没有启动 Linux，也未验证任何 DASICS 内核行为。
- 下一课：认识 RiscvBoard 中的硬件组件。
- 学习记录提交：`6cea300c16`。

### 2026-11-01：RiscvBoard 与硬件组件

- 状态：已讲解，理解检查通过。
- 目标：识别模拟硬件的各个组成部分，并区分硬件参数与 Linux 软件资源。
- 学习内容：Processor 提供 CPU 核；CacheHierarchy 描述 CPU 与主存之间
  的缓存及连接；Memory 描述内存系统；Board 组织这些组件和平台设备。
  这种分工来自[官方标准库概览][stdlib]。
- 代码入口：[riscv-ubuntu-run.py](../example/gem5_library/riscv-ubuntu-run.py)
  中依次定义 `cache_hierarchy`、`memory`、`processor`，并传给
  `RiscvBoard(...)`；后面的 `board.set_workload(...)` 才绑定软件工作负载。
- 已核对参数：两个 3 GHz Timing 核；3 GiB DDR4-2400 内存；缓存构造参数
  为 `l1i_size="16KiB"`、`l1d_size="16KiB"`、`l2_size="256KiB"`。
  这些是脚本的配置值，本课没有运行仿真取得测量结果。
- 平台设备：在 [RiscvBoard](../../src/python/gem5/components/boards/riscv_board.py)
  的 `_setup_board()` FS 分支中，可以看到中断控制、串口和 VirtIO 磁盘等
  平台设施；设备连接由相关 Board 逻辑安排。本课只认识用途，不展开寄存器实现。
- 理解检查：把内存配置从 3 GiB 改为 2 GiB，改变的是模拟主存
  容量还是磁盘镜像容量？仅创建 RiscvBoard 后，是否已经指定要加载的 Linux？
- 回答与判定：学习者回答模拟主存容量，并确认创建 Board 尚未指定 Linux；
  与本课判据一致，理解检查通过。
- 验证边界：已核对当前版本代码与官方概览；没有改变硬件配置或启动 Linux。
- 下一课：分别认识内核、设备树、磁盘镜像等启动资源。
- 学习记录提交：`9c46bd567b`。

### 2026-11-01：Linux 启动资源的角色

- 状态：资源角色已讲解，理解检查通过；具体元数据核对另行记录。
- 目标：区分启动时各类代码、描述数据和存储内容，理解它们如何配合。
- 内核：实际执行的操作系统核心代码，负责进程、内存、系统调用、异常
  处理与驱动等。当前标准库接口把内核资源和磁盘镜像分别指定。
- 设备树：描述硬件的数据，例如 CPU、内存范围、设备地址与中断。
  DTS 是源文本，DTB 是供软件读取的二进制表示；设备树不提供驱动实现。
  依据为 [Linux 设备树文档][linux-devicetree]。
- 磁盘镜像与根文件系统：镜像文件表示模拟磁盘的内容，可能包含分区表
  和文件系统。本课程的磁盘启动路线中，根文件系统通常位于磁盘的一个分区，
  挂载为 `/`，提供用户程序、库和配置文件。见
  [gem5 磁盘镜像说明][disk-images]。
- 启动固件：负责内核之前的启动交接，并可提供底层运行服务；
  [OpenSBI][opensbi] 是 SBI 固件实现的例子。资源可能分别提供固件与内核，
  也可能组合打包；当前 workload 的具体形式留到元数据核对时确认。
- 当前代码证据：
  [KernelDiskWorkload](../../src/python/gem5/components/boards/kernel_disk_workload.py)
  的 `set_kernel_disk_workload()` 接收 `kernel`、`disk_image` 和可选
  `bootloader`；
  [RiscvBoard](../../src/python/gem5/components/boards/riscv_board.py)
  在预实例化阶段调用 `generate_device_tree()`，从硬件配置生成
  `device.dts` 和 `device.dtb`，并将磁盘镜像绑定到模拟磁盘设备。
- 资源版本：官方示例中的 `resource_version="2.0.0"` 是启动 workload
  资源的版本，不是 Linux 内核版本。内核、固件、磁盘的实际资源身份待核对。
- 理解检查：修改 Linux 的异常处理逻辑，应修改并重新编译内核
  还是设备树？描述串口地址和中断号的硬件信息，应放在哪类描述数据里？
- 回答与判定：学习者回答重新编译内核，并将串口硬件描述归入设备树；
  与本课判据一致，理解检查通过。
- 验证边界：已核对上述本地接口及官方文档；未下载资源、生成 FS 设备树
  或启动 Linux。本课不推断启动资源包内尚未读取的具体文件版本。
- 下一课：只读查看 workload 的资源元数据与版本，
  然后进入配置和退出事件学习。

## 以后每次学习如何记录

以后每学完一个主题，就在本文件追加一条带日期的学习记录，并更新
“当前进度”和“下一课”。历史记录保留，新的结论追加适用条件或更正说明。

每条至少包含：

1. 主题与目标：这次要理解或验证什么。
2. 学习内容与入口：相关概念、源文件和配置。
3. 理解检查或实验结果：概念课记录问答确认；实验课记录必要参数、
   命令入口、关键输出和成功判据。分别标明已讲解、已验证、待验证。
4. 分析与边界：结果支持什么结论，哪些问题仍未验证。
5. 提交与证据：已有实验提交、日志路径；必要产物保持可追溯。
6. 下一次从哪里开始：明确一个小主题，或写明暂停与恢复位置。

记录只保留可复用的信息。完整日志留在实验目录，详细流程与分析写入
实验提交；RVV 的通用知识继续维护在飞书。学习记录更新单独提交，
便于区分实验改动与进度整理。

[rvv-notes]: https://aul8ejtumo.feishu.cn/wiki/DdSAwEKWjiEVe4kV4ZVcEDWQnFg
[simple-config]: https://www.gem5.org/documentation/learning_gem5/part1/simple_config/
[stdlib]: https://www.gem5.org/documentation/gem5-stdlib/overview
[fs-tutorial]: https://www.gem5.org/documentation/gem5-stdlib/x86-full-system-tutorial
[resources]: https://www.gem5.org/documentation/general_docs/gem5_resources/
[linux-devicetree]: https://docs.kernel.org/devicetree/usage-model.html
[disk-images]: https://www.gem5.org/documentation/general_docs/fullsystem/disks
[opensbi]: https://github.com/riscv-software-src/opensbi/blob/master/README.md
