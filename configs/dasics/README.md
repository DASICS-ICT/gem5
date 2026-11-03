# DASICS O3 模型

[English](README.en.md) | [使用命令](../../docs/dasics.md)

本目录提供五套参考南湖 RTL 参数的单核 `RiscvO3CPU` 模型，用于 DASICS
功能验证及相同平台上的相对性能比较。容量和可映射参数按下列 RTL 配置设置；
流水线、调度、预测和存储协议仍采用 gem5 模型，尚未完成 RTL 周期校准。

## 模型入口

| `CPU` | 配置文件 | RTL 配置来源 |
| --- | --- | --- |
| `V2_minimal` | [riscv_dasics_o3_V2_minimal.py](riscv_dasics_o3_V2_minimal.py) | V2 `MinimalConfig` |
| `V2_nanhug` | [riscv_dasics_o3_V2_nanhug.py](riscv_dasics_o3_V2_nanhug.py) | V2 `NanHuGConfig` |
| `V2_default` | [riscv_dasics_o3_V2_default.py](riscv_dasics_o3_V2_default.py) | V2 `DefaultConfig` |
| `v5_full` | [riscv_dasics_o3_v5_full.py](riscv_dasics_o3_v5_full.py) | LinkNan-NG `CoreConfig.full`、full L2、`mini_soc` LLC |
| `v5_stress` | [riscv_dasics_o3_v5_stress.py](riscv_dasics_o3_v5_stress.py) | LinkNan-NG `CoreConfig.stress`、full L2、`mini_soc` LLC |

每个入口集中保存本模型的 `PROFILE`；共用的
[dasics_platform.py](dasics_platform.py) 构造 CPU、缓存、预测器和内存。
`CPU` 值区分大小写，默认 `v5_full`。V5 mini 不在本目录的模型名单中。

```bash
make dasics-test TEST=riscv-dasics-csr CPU=v5_full
make dasics-test TEST=riscv-dasics-csr CPU=all
```

`all` 按表中顺序串行执行，使用独立的 `build/m5out-o3/<CPU>/` 输出目录，
目录相对于所选测试目录。每次模型实例化后、`m5.simulate()` 前，从本次
`config.ini` 以列表打印基本配置：CPU 类型、频率、VLEN、流水线宽度、
ROB/IQ/LQ/SQ 容量，以及各级缓存的容量和相联度。完整参数保留在本说明及
`config.ini` 中。

每个模型结束后打印本次 `stats.txt` 最后一次统计输出中的
`system.cpu.numCycles`。失败、超时或当前统计不可用时显示 `N/A`，不读取
旧运行的周期数。该值包含启动和整个 CSR 用例，不是应用性能测量区间的周期数。

模型间输出以 `-------------------------------` 分隔。单个模型失败后继续
其余模型，最后以 `CPU / Result / Cycles` 表格汇总；任一失败使命令返回非零。

## RTL 参数来源

以下路径相对于各自的 RTL 仓库。

| 仓库 | 文件与符号 | 用途 |
| --- | --- | --- |
| [DASICS-ICT/xiangshan-dasics](https://github.com/DASICS-ICT/xiangshan-dasics)，`xiangshan-sreg-register-protection` | `src/main/scala/top/Configs.scala::{MinimalConfig,NanHuGConfig,DefaultConfig}` | V2 覆盖参数和缓存组合 |
| 同上 | `src/main/scala/xiangshan/Parameters.scala::XSCoreParameters` | 继承的核心、预测器、队列参数 |
| 同上 | `src/main/scala/xiangshan/XSCore.scala::schedulePorts`、`src/main/scala/xiangshan/backend/Scheduler.scala`、`src/main/scala/xiangshan/backend/issue/ReservationStation.scala::addIssuePort` | V2 执行单元和 RS 容量推导 |
| [DASICS-ICT/LinkNan-NG](https://github.com/DASICS-ICT/LinkNan-NG)，`dasics-dev-zsy` FDI 集成源码 | `src/main/scala/linknan/configs/cluster/CoreConfig.scala::{full,stress}` | V5 核心覆盖参数 |
| 同上 | `dep/nanhu/src/main/scala/xiangshan/Parameters.scala::{XSCoreParameters,intSchdParams,vfSchdParams,memSchdParams}` | V5 核心默认值与 IssueBlock 布局 |
| 同上 | `src/main/scala/linknan/configs/cluster/L2CacheConfig.scala::full`、`src/main/scala/linknan/system/island/cluster/CpuClusterParams.scala` | L2 容量、bank 与 MSHR |
| 同上 | `src/main/scala/linknan/configs/{system/SystemConfig,noc/LastLevelCacheConfig}.scala`、`dep/zhujiang/src/main/scala/zhujiang/ZJParameters.scala` | 单核 `mini_soc` LLC 配置 |
| 同上 | `src/main/scala/linknan/system/LNSysParams.scala`、`dep/dramsim3/configs/XiangShan-nanhu.ini` | 地址窗口、名义频率与 DRAM 参考来源 |

V2 数值包含继承的默认值。`NanHuGConfig` 同时组合核心和缓存配置；
`NanHuGCoreConfig` 不能替代完整配置。V5 参数以本地 LinkNan-NG FDI
集成源码及其 `dep/nanhu` 为准，不用旧南湖默认值补填。

## 核心容量

下表列出 RTL 有效参数。`PROFILE` 中保留不能直接映射的字段，便于与
gem5 实际参数区分。

| 参数 | V2 minimal | V2 nanhug | V2 default | v5 full | v5 stress |
| --- | ---: | ---: | ---: | ---: | ---: |
| `FetchWidth` | 4 | 8 | 8 | 8 | 8 |
| Decode / Rename 宽度 | 2 / 2 | 4 / 4 | 6 / 6 | 4 / 4 | 4 / 4 |
| Commit 宽度 | 6 | 6 | 6 | 8 | 8 |
| ROB | 32 | 96 | 256 | 96 | 96 |
| 整数物理寄存器 | 64 | 64 | 192 | 128 | 128 |
| 浮点物理寄存器 | 64 | 64 | 192 | 与向量共享 160 | 与向量共享 160 |
| LQ / Virtual LQ | 16 | 32 | 80 | 56 | 24 |
| SQ | 12 | 24 | 64 | 32 | 20 |
| Store Buffer / threshold | 4 / 3 | 4 / 3 | 16 / 7 | 8 / 7 | 4 / 3 |
| Load RAW / Replay 队列 | — | — | — | 24 / 32 | 12 / 24 |
| FTQ | 8 | 16 | 64 | 48 | 48 |
| IBuffer | 16 | 32 | 48 | 32 | 32 |
| Load / Store 地址流水线 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 1 | 2 / 1 |

| RTL Dispatch Queue | V2 minimal / nanhug | V2 default | v5 full / stress |
| --- | --- | --- | --- |
| Int / FP / LS 容量 | 12 / 12 / 12 | 16 / 16 / 16 | 8 / 12 / 12 |
| Int / FP / LS 出队宽度 | 4 / 4 / 4 | 4 / 4 / 4 | 8 / 6 / 4 |
| Vector 出队宽度 | 不适用 | 不适用 | 6 |

映射与边界：

- Decode/Rename/Commit、ROB、整数 PRF、LQ/SQ 容量映射到对应 gem5 参数。
  V5 Virtual LQ 映射到 gem5 LQ；RAW、Replay 队列仍属于未建模的独立结构。
- 启用压缩指令时，RTL 的 `PredictWidth=2*FetchWidth` 表示半字候选槽。
  gem5 `fetchWidth` 按指令计数，因此设为最大压缩指令数；这是吞吐上限映射，
  不代表两者取指和预测时序相同。
- V5 浮点/向量共享 PRF 在 gem5 中使用分离的浮点和向量 PRF 表示，容量相同
  不代表共享竞争相同；V0/VL PRF、整数/访存寄存器缓存未独立建模。
- RTL Store Buffer、Dispatch Queue、FTQ/IBuffer 与 gem5 对应结构的生命周期、
  微操作计数和背压规则不同，不能仅凭容量认定时序等价。

| gem5 参数 | V2 minimal | V2 nanhug | V2 default | v5 full / stress |
| --- | ---: | ---: | ---: | ---: |
| `fetchWidth`（指令） | 8 | 16 | 16 | 16 |
| `fetchBufferSize`（B） | 16 | 32 | 32 | 32 |
| `fetchQueueSize` | 16 | 32 | 48 | 32 |
| `numFTQEntries` | 8 | 16 | 64 | 48 |
| `numPhysFloatRegs` / `numPhysVecRegs` | 64 / 64 | 64 / 64 | 192 / 64 | 160 / 160 |
| 向量扩展 | VLEN 128、ELEN 64 | VLEN 128、ELEN 64 | VLEN 128、ELEN 64 | VLEN 128、ELEN 64 |

所有模型均启用 V 扩展，默认 VLEN 128、ELEN 64。V2 的 64 项向量 PRF
和相应向量执行资源是统一实验平台扩展，超出旧 V2 标量 RTL 的参考范围。

## 分组发射与执行单元

V2 RS 容量由 `IssQueSize * deq` 推导；`maxRsDeq=2` 时拆分宽类别。
配置使用 gem5 多个 `IQUnit` 保留类别容量，不用单个集中 IQ 替代全部队列。

| V2 RS 类别 | minimal / nanhug | default |
| --- | --- | --- |
| ALU | 16 | 32 + 32 |
| MDU | 8 | 32 |
| JMP / CSR / Fence / I2F | 8 | 16 |
| Load | 16 | 32 |
| Store Address | 16 | 32 |
| Store Data | 16 | 32 |
| FMAC | 8 | 32 + 32 |
| FMISC | 8 | 32 |
| 合计 | 96 | 304 |

| V5 IssueBlock | full / stress |
| --- | --- |
| Int0–Int3 | 各 18 |
| VFMA / VFALU / VFDIV | 16 / 16 / 10 |
| STA / LDU0 / LDU1 / VLSU / STD | 20 / 16 / 16 / 16 / 20 |
| 合计 | 202 |

| RTL 执行资源 | V2 minimal / nanhug | V2 default | V5 full / stress |
| --- | --- | --- | --- |
| 整数 ALU / MDU | 2 / 1 | 4 / 2 | ALU 4；乘除与 BJU 分组共享 |
| Jump / CSR 类 | 1 | 1 | BJU 4，功能按组区分 |
| FMAC / FMISC | 1 / 1 | 4 / 2 | VFMA 2、VFALU 2、VFDIV 1 |
| Load / STA / STD | 2 / 2 / 2 | 2 / 2 / 2 | 2 / 1 / 1，另有 VLSU |

gem5 按 `OpClass` 路由并使用自己的调度和唤醒规则，部分 RTL 复合 FU 的
操作语义在对应 gem5 FU 中合并。独立 STA/STD、向量访存、寄存器读端口仲裁、
旁路及 replay 时序未按 RTL 重建。统一 `issueWidth`、`wbWidth` 和固定
`opLat` 属于显式的模型设定，不能由上述队列总量推导等价性。

以下为全部模型共用的 gem5 FU 延迟，单位为 CPU 周期。表外 `OpClass`
显式使用 `opLat=1, pipelined=True`；gem5 的固定除法延迟不表示 RTL 的变长除法。
向量操作共享所建模的浮点端口，V2 也采用这一实验扩展。

| `OpClass` | `opLat` | `pipelined` |
| --- | ---: | --- |
| `IntAlu`、`System` | 1 | true |
| `IntMult` | 3 | true |
| `IntDiv`、`SimdDiv`、`SimdFloatDiv` | 20 | false |
| `FloatAdd`、`FloatCmp`、`FloatCvt`、`Bf16Cvt`、`SimdFloatAdd` | 2 | true |
| `FloatMult` | 4 | true |
| `FloatMultAcc` | 5 | true |
| `FloatMisc`、`SimdFloatMult`、`SimdFloatMultAcc` | 3 | true |
| `FloatDiv` | 12 | false |
| `FloatSqrt`、`SimdSqrt`、`SimdFloatSqrt` | 24 | false |

## 缓存容量与并发资源

缓存行均为 64 B；容量为所有 bank 的数据总容量。

| 层次 | V2 minimal | V2 nanhug | V2 default | v5 full | v5 stress |
| --- | --- | --- | --- | --- | --- |
| L1I | 16 KiB / 4 路 | 16 KiB / 4 路 | 64 KiB / 4 路 | 64 KiB / 4 路 | 64 KiB / 4 路 |
| L1D | 32 KiB / 8 路 | 32 KiB / 4 路 | 64 KiB / 4 路 | 64 KiB / 4 路 | 16 KiB / 2 路 |
| L2 | 无 | 256 KiB / 8 路 / 4 bank | 1 MiB / 8 路 / 4 bank | 1 MiB / 8 路 / 2 bank | 1 MiB / 8 路 / 2 bank |
| LLC | 512 KiB / 8 路 / 1 bank | 1.5 MiB / 6 路 / 4 bank | 6 MiB / 6 路 / 4 bank | 2 MiB / 16 路 / 2 HNX | 2 MiB / 16 路 / 2 HNX |

V5 stress DCache 的有效容量按 `128 sets * 2 ways * 64 B = 16 KiB`
计算；源码中的“32 kB”注释不作为容量依据。其 ICache 继承 64 KiB/4 路。

V5 full L2 的原始参数为 `512*1024/8/2/64=512` sets；集成时
`CpuClusterParams` 将 sets 乘 2，形成每 Slice 1024 sets。两个 Slice
各有 `1024*8*64=512 KiB`，总容量 1 MiB；每 Slice 16 MSHR，合计 32。
`l2cacheSize` 报告字段未计入两个 Slice，不能用其 512 KiB 报告值替代总容量。

V5 LLC 取 `mini_soc` 的整个 island 总容量 2 MiB，不再乘 HNX 数。
`hnxOutstanding=32` 是 home agent 总资源口径，gem5 LLC MSHR 采用容量近似，
并不等同于 HNX 事务状态。当前使用 classic Cache 和交叉开关，未重建
TileLink/CHI、珠江环网、bank 冲突、目录及 ECC 时序。

L2/LLC 实际构造多个 Cache bank，每 bank 的容量和 MSHR 按总量除 bank
数分配。bank 选择位放在每 bank 的 set 索引位之上：
`bank_low_bit = 6 + log2(sets_per_bank)`，交错粒度为
`sets_per_bank * 64 B`。这样保留每 bank 全部 set 的可达性；该地址映射与
RTL 的 64 B 行交错不同。L1 内部 bank 不独立建模，`PROFILE` 中的 L1 bank
字段仅记录 RTL 组织。各 bank 共用交叉开关，其仲裁和端口时序不能代表 RTL
的完整 bank 结构。

| gem5 bank 交错粒度 | V2 minimal | V2 nanhug | V2 default | v5 full / stress |
| --- | --- | --- | --- | --- |
| L2 | 无 | 8 KiB | 32 KiB | 64 KiB |
| LLC | 单 bank，无交错 | 64 KiB | 256 KiB | 64 KiB |

| gem5 MSHR | V2 minimal | V2 nanhug | V2 default | v5 full | v5 stress |
| --- | ---: | ---: | ---: | ---: | ---: |
| L1I | 2 | 2 | 2 | 4 | 4 |
| L1D | 4 | 16 | 16 | 32 | 4 |
| L2 | — | 56 | 56 | 32 | 32 |
| LLC | 14 | 56 | 56 | 32 | 32 |

V2 Huancun 每 bank 14 个普通 MSHR，另有 2 个 B/C 保留 MSHR；表中按
普通 MSHR 合计映射，未模拟 TileLink 通道专用资源。V5 ICache 独立的
4 个 fetch MSHR 和 10 个 prefetch MSHR 不能用一个 gem5 MSHR 数完整表达。

### 指令预取资源映射限制（暂缓修正）

本问题暂缓修正，当前模型保留既有配置。恢复此项工作时，先结合上方
RTL 参数来源，阅读 V2 的 `frontend/icache/ICacheMissUnit.scala`、
`frontend/icache/IPrefetch.scala`，以及 V5 的
`dep/nanhu/src/main/scala/xiangshan/frontend/icache/ICacheMissUnit.scala`。
V2 的两个路径相对于 `src/main/scala/xiangshan/`。

- `V2_minimal`、`V2_nanhug` 的 RTL 指令预取关闭，当前模型保持关闭。
- `V2_default` 的 RTL 有 2 个需求 miss entry 和 2 个 Hint 发送槽。
  Hint 发送成功后释放槽位，数据准备在 L2，后续需求访问才将数据填入 L1I。
  当前 gem5 使用填入 L1I 的 Tagged 近似，且共享 `mshrs=2`、
  `demand_mshr_reserve=1` 使预取无法发出。
- `v5_full`、`v5_stress` 的 RTL 有独立的 4 个 fetch MSHR 和
  10 个 prefetch MSHR，两类返回均可填入 L1I。当前 gem5 只有
  4 个共享 MSHR，没有表达独立的 10 项预取池及其资源竞争。

[BaseCache](../../src/mem/cache/base.cc) 构造 MSHR 队列时传入
`numReserve=0`；[MSHRQueue::canPrefetch](../../src/mem/cache/mshr_queue.hh)
要求 `allocated < numEntries - (numReserve + 1 + demandReserve)`。
因此当前 `V2_default` 的条件为 `allocated < 0`。挂载预取器不能保证
预取可实际发出，恢复修正时应同时检查 `config.ini` 的资源参数与
`stats.txt` 中的 `pfIssued`、需求 MSHR 命中及取指等待统计。

后续修正需区分需求与预取的分配、准入、仲裁、取消和填充目标。V2 的
Hint 发送槽不能直接加到 L1I 需求 MSHR；V5 的 4+10 项也不能合并成
14 个共享槽后视为 RTL 等价。

现阶段以 `v5_full` 作为后续 DASICS 实验基线，在相同模型、输入和测量
区间内比较 DASICS 模式。结果描述该 gem5 配置下的开销；共享 MSHR 和
预取近似仍可能与 DASICS 行为发生交互，不能假定其影响完全抵消，也不能
据此推导真实 V2/V5 的性能差距。

## 分支预测与预取

| RTL 参数 | V2 minimal | V2 nanhug | V2 default | v5 full / stress |
| --- | --- | --- | --- | --- |
| uBTB / FTB / RAS | 256 / 2048 / 32 | 128 / 1024 / 32 | 256 / 2048 / 32 | 256 / 4096 / 16 |
| `EnableBPD` 字段 | false | true | true | 无此对应字段 |
| `EnableSC` 字段 | true | false | true | false |
| `EnableLoop` 字段 | false | false | true | 未映射 |
| 指令预取 | 关闭 | 关闭 | 开启 | 开启 |
| 核心数据预取 | 无 | SMS → L2 | SMS → L2 | Stream/Stride 与 SMS 协作 |
| L2 本地预取 | 无 | 接收核心请求 | 接收核心请求 | PBOP + VBOP，另接收核心请求 |

gem5 使用 TAGE、BTB 和 RAS 组件作为明确近似。V2 `EnableBPD=false`
在活跃预测路径中未发现有效消费者，不能据字段值声称 RTL TAGE 被移除。
FTB 与普通 BTB、任意历史长度表与 gem5 几何历史长度表的索引/训练并不等价；
SC、Loop、uBTB、ITTAGE 和 V5 推测 RAS 未按原结构建模。

| gem5 预测器参数 | 设定 |
| --- | --- |
| 条件预测 | `TAGE`，4 张历史表，`minHist=8`、`maxHist=119`，几何历史长度 |
| TAGE 每表项数 | V2 4096；V5 2048，基表使用相同项数 |
| TAGE tag / counter / useful 位宽 | 8 / 3 / 2 |
| 历史状态 | 推测更新，path history 16 bit，history buffer `2^21` |
| 第一级 BTB | 容量取 uBTB 字段，4 路、tag 16 bit、延迟 1 周期 |
| 第二级 BTB | 容量取 FTB 字段，4 路、tag 16 bit、延迟 2 周期 |
| RAS | 容量取上表 RAS 字段；未单独构造推测 RAS |
| 间接跳转预测 | gem5 `ITTAGE`，复用上述表数、容量、tag 和历史范围 |
| 指令地址位移 | `instShiftAmt=1` |

预取采用相应 gem5 预取器的显式参数：指令路径为 Tagged 近似，核心 SMS
使用 gem5 SMS，V5 L1D Stream/Stride 使用 Stride 近似，L2 BOP 使用
gem5 BOP。SMS 的 AGT/PHT 组织、PBOP/VBOP 双实例及任意 offset 列表、
核心请求与 L2 本地预取的仲裁、翻译和传输延迟仍存在差异。
RTL 关闭的预取路径在对应配置中保持关闭。

| gem5 预取参数 | 设定 |
| --- | --- |
| 共用队列 / 延迟 | 16 项 / 1 周期，64 B block，4 KiB page，物理地址训练 |
| Tagged | `degree=1` |
| SMS | `ft_size=16`、`pht_size=64`、`region_size=1024 B` |
| Stride | `degree=1`、`distance=0`、2-bit confidence、初值 0、阈值 50% |
| Stride 表 | 16 项、直接映射；RTL 的 10 项映射为 gem5 支持的 2 次幂容量 |
| BOP | `degree=1`、`score_max=31`、`round_max=50`、`bad_score=2` |
| BOP RR / tag / offsets | 256 项 / 12 bit / 46 项，允许负 offset |
| BOP 延迟队列 | 开启，16 项，175 周期 |
| V5 L2 组合 | `MultiPrefetcher(BOP, SMS)`，未复现 RTL 的 PBOP/VBOP/核心请求仲裁 |

SMS 在 gem5 L2 访存路径训练；RTL 的核心训练后向 L2 传输请求的路径没有逐拍
重建。gem5 自动生成 BOP offset 列表，不等同于 RTL 的任意 offset 列表。

## 统一实验平台设定

CPU/总线时钟、DRAM、各阶段延迟和 FU/Cache 延迟在共用 helper 中显式固定。
这些设定用于受控比较，未标为 RTL 已校准时序。V5 `cpuFreq=2 GHz` 是
SoC 名义参数；V2 的 2 GHz 和全部模型的 DRAM 时序属于统一实验设定。

| 项目 | 设定与边界 |
| --- | --- |
| CPU / NoC 等效总线时钟 | 2 GHz |
| 架构与执行 | RV64、单核单 hart、全系统裸机、`timing` 内存模式 |
| ISA 配置 | `RVA20S64`，额外启用 `Zba/Zbb/Zbc/Zbs/V`，VLEN 128、ELEN 64，MSU 特权集 |
| DRAM | 单通道 DDR4-2400、64-bit 总线、8 GiB |
| 内存地址 | 从 `0x80000000` 起；下方单独映射复位向量页 |
| DRAM 依据 | V5 参考文件 `tCK=0.83 ns`；使用 gem5 DDR4-2400 模型，不复现 DRAMsim3 的 2000/1600 协同推进字段 |
| 数据收集 | 每模型独立 `config.ini`、`config.json`、`stats.txt` |

当前 ISA 配置不启用 H 扩展，也不覆盖虚拟化行为。

| gem5 CPU 时序或策略 | 设定 |
| --- | --- |
| `dispatchWidth` | 等于该模型 `renameWidth` |
| `issueWidth` / `wbWidth` | 16 / 16 |
| `fetchTargetWidth` | 等于该模型 `fetchBufferSize` |
| `cacheLoadPorts` / `cacheStorePorts` | V2 为 2 / 2；V5 为 2 / 1 |
| 正向阶段延迟 | `fetchToBacDelay`、`bacToFetchDelay`、`fetchToDecodeDelay`、`decodeToRenameDelay`、`renameToROBDelay`、`issueToExecuteDelay`、`iewToCommitDelay` 均为 1 |
| `renameToIEWDelay` | 2 |
| 反馈延迟 | `decodeToFetchDelay`、`renameToFetchDelay`、`iewToFetchDelay`、`commitToFetchDelay`、`renameToDecodeDelay`、`iewToDecodeDelay`、`commitToDecodeDelay`、`iewToRenameDelay`、`commitToRenameDelay`、`commitToIEWDelay` 均为 1 |
| 异常延迟 | `trapLatency=13`、`fetchTrapLatency=1` |
| 通信缓冲 | `backComSize=5`、`forwardComSize=5` |
| 调度 | `iqInsertionPolicy=FirstMatch`，解耦前端，每周期最多 4 个 fetch target、2 个 taken prediction |
| Store-set 依赖预测 | LFST/SSIT 各 1024 项，SSIT 1 路，清理周期 250000 |
| 访存顺序 | `LSQCheckLoads=True`、`LSQDepCheckShift=4`、`needsTSO=False` |
| 其他物理文件 | VecPred 32、Mat 2、CC 0；属于 gem5 配套资源 |

| 缓存、互连与内存时序 | 设定 |
| --- | --- |
| 各级缓存 tag / data / response | 全部 2 / 2 / 2 周期；三个字段不直接相加作为总命中延迟 |
| 缓存并发 | 每 MSHR 20 target，8 个 write buffer，非顺序 tag/data 访问 |
| 替换与包含策略 | `LRURP`、`mostly_incl`；替代 RTL 的 PLRU/DRRIP 和非包含协议 |
| 数据路径 | `L1I/L1D/MMU walker → L1 XBar → L2 banks（若存在）→ L2 XBar → LLC banks → memory XBar → DRAM` |
| 各缓存交叉开关 | 32 B 宽，frontend/forward/response/header 各 1 周期 |
| Snoop filter | lookup 1 周期，容量 32 MiB |
| MMIO bridge | 50 ns；HiFive 平台 RTC 10 MHz |
| 复位页 | `0x7FFFF000` 起 4 KiB `SimpleMemory`，1 ns、32 GiB/s |
| DRAM 控制器 | FR-FCFS；读/写队列 64 / 128 项；高/低写阈值 85% / 50% |
| 读写切换 | 每批至少 16 次写、16 次读 |
| DDR4 器件 | `DDR4_2400_8x8`，每通道 1 rank、8 个 x8 器件；器件时序见实际 `config.ini` |

修改模型时先修改该入口的 `PROFILE`；共用时序、FU、连接或打印逻辑在
`dasics_platform.py` 修改。实例化后的 `config.ini` 是实际 SimObject 参数依据。
CSR 用例的总运行周期只作该用例的统计，不能代表 DASICS 应用性能开销。

## 尚未建模的 DASICS 微架构成本

当前配置复用既有 CSR 语义。前端可信标签、边界检查延迟、CSR distributed
传播、配置更新后的冲刷、检查端口竞争和投机路径处理需要后续独立实现并验证。
比较 DASICS 开关时应使用相同模型、相同输入和相同测量区间，再报告周期差异。
