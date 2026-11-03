# DASICS O3 models

[中文版](README.md) | [Usage commands](../../docs/dasics.en.md)

This directory provides five single-core `RiscvO3CPU` models based on Nanhu
RTL parameters for DASICS functional tests and relative performance
comparisons on the same platform. Capacities and directly mappable parameters
follow the RTL configurations below. Pipeline, scheduling, prediction, and
memory protocols still use gem5 models; RTL cycle calibration is pending.

## Model entry points

| `CPU` | Configuration file | RTL configuration source |
| --- | --- | --- |
| `V2_minimal` | [riscv_dasics_o3_V2_minimal.py](riscv_dasics_o3_V2_minimal.py) | V2 `MinimalConfig` |
| `V2_nanhug` | [riscv_dasics_o3_V2_nanhug.py](riscv_dasics_o3_V2_nanhug.py) | V2 `NanHuGConfig` |
| `V2_default` | [riscv_dasics_o3_V2_default.py](riscv_dasics_o3_V2_default.py) | V2 `DefaultConfig` |
| `v5_full` | [riscv_dasics_o3_v5_full.py](riscv_dasics_o3_v5_full.py) | LinkNan-NG `CoreConfig.full`, full L2, `mini_soc` LLC |
| `v5_stress` | [riscv_dasics_o3_v5_stress.py](riscv_dasics_o3_v5_stress.py) | LinkNan-NG `CoreConfig.stress`, full L2, `mini_soc` LLC |

Each entry point keeps its model-specific values in `PROFILE`. The shared
[dasics_platform.py](dasics_platform.py) constructs the CPU, caches,
predictor, and memory. `CPU` values are case-sensitive and default to
`v5_full`. V5 mini is excluded from the model list.

```bash
make dasics-test TEST=riscv-dasics-csr CPU=v5_full
make dasics-test TEST=riscv-dasics-csr CPU=all
```

`all` runs models sequentially in table order, with separate
`build/m5out-o3/<CPU>/` output directories relative to the selected test.
After instantiation and before `m5.simulate()`, a list from that run's
`config.ini` shows the CPU type, frequency, VLEN, pipeline widths,
ROB/IQ/LQ/SQ capacities, and each cache level's capacity and associativity.
Full parameters remain available in this reference and `config.ini`.

Each model ends by reporting `system.cpu.numCycles` from the final statistics
dump in that run's `stats.txt`. Failed or timed-out runs and unavailable
current statistics show `N/A`; cycle counts from earlier runs are not used.
The count includes startup and the entire CSR test, rather than an application
performance measurement region.

Output between models is separated by `-------------------------------`.
Failure of one model does not stop the others. A final `CPU / Result / Cycles`
table summarizes all models; any failure returns a nonzero status.

## RTL parameter sources

Paths below are relative to their respective RTL repositories.

| Repository | File and symbol | Purpose |
| --- | --- | --- |
| [DASICS-ICT/xiangshan-dasics](https://github.com/DASICS-ICT/xiangshan-dasics), `xiangshan-sreg-register-protection` | `src/main/scala/top/Configs.scala::{MinimalConfig,NanHuGConfig,DefaultConfig}` | V2 overrides and cache composition |
| Same repository | `src/main/scala/xiangshan/Parameters.scala::XSCoreParameters` | Inherited core, predictor, and queue defaults |
| Same repository | `src/main/scala/xiangshan/XSCore.scala::schedulePorts`, `src/main/scala/xiangshan/backend/Scheduler.scala`, `src/main/scala/xiangshan/backend/issue/ReservationStation.scala::addIssuePort` | V2 execution units and derived RS capacities |
| [DASICS-ICT/LinkNan-NG](https://github.com/DASICS-ICT/LinkNan-NG), `dasics-dev-zsy` FDI integration | `src/main/scala/linknan/configs/cluster/CoreConfig.scala::{full,stress}` | V5 core overrides |
| Same repository | `dep/nanhu/src/main/scala/xiangshan/Parameters.scala::{XSCoreParameters,intSchdParams,vfSchdParams,memSchdParams}` | V5 core defaults and IssueBlock layout |
| Same repository | `src/main/scala/linknan/configs/cluster/L2CacheConfig.scala::full`, `src/main/scala/linknan/system/island/cluster/CpuClusterParams.scala` | L2 capacity, banks, and MSHRs |
| Same repository | `src/main/scala/linknan/configs/{system/SystemConfig,noc/LastLevelCacheConfig}.scala`, `dep/zhujiang/src/main/scala/zhujiang/ZJParameters.scala` | Single-core `mini_soc` LLC configuration |
| Same repository | `src/main/scala/linknan/system/LNSysParams.scala`, `dep/dramsim3/configs/XiangShan-nanhu.ini` | Address window, nominal frequency, and DRAM reference |

V2 values include inherited defaults. `NanHuGConfig` combines core and cache
configurations; `NanHuGCoreConfig` alone is not the complete configuration.
V5 values follow the local LinkNan-NG FDI integration and its `dep/nanhu`,
without filling gaps from older Nanhu defaults.

## Core capacities

The table lists effective RTL parameters. `PROFILE` retains fields without
direct gem5 equivalents so that RTL metadata and actual gem5 parameters can
be distinguished.

| Parameter | V2 minimal | V2 nanhug | V2 default | v5 full | v5 stress |
| --- | ---: | ---: | ---: | ---: | ---: |
| `FetchWidth` | 4 | 8 | 8 | 8 | 8 |
| Decode / Rename width | 2 / 2 | 4 / 4 | 6 / 6 | 4 / 4 | 4 / 4 |
| Commit width | 6 | 6 | 6 | 8 | 8 |
| ROB | 32 | 96 | 256 | 96 | 96 |
| Integer physical registers | 64 | 64 | 192 | 128 | 128 |
| Floating-point physical registers | 64 | 64 | 192 | 160 shared with vector | 160 shared with vector |
| LQ / Virtual LQ | 16 | 32 | 80 | 56 | 24 |
| SQ | 12 | 24 | 64 | 32 | 20 |
| Store Buffer / threshold | 4 / 3 | 4 / 3 | 16 / 7 | 8 / 7 | 4 / 3 |
| Load RAW / Replay queues | — | — | — | 24 / 32 | 12 / 24 |
| FTQ | 8 | 16 | 64 | 48 | 48 |
| IBuffer | 16 | 32 | 48 | 32 | 32 |
| Load / Store-address pipelines | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 1 | 2 / 1 |

| RTL Dispatch Queue | V2 minimal / nanhug | V2 default | v5 full / stress |
| --- | --- | --- | --- |
| Int / FP / LS capacity | 12 / 12 / 12 | 16 / 16 / 16 | 8 / 12 / 12 |
| Int / FP / LS dequeue width | 4 / 4 / 4 | 4 / 4 / 4 | 8 / 6 / 4 |
| Vector dequeue width | Not applicable | Not applicable | 6 |

Mapping and boundaries:

- Decode/Rename/Commit widths, ROB, integer PRF, and LQ/SQ capacities map to
  their gem5 parameters. The V5 Virtual LQ maps to gem5 LQ; separate RAW and
  Replay queue structures are not modeled.
- With compressed instructions, RTL `PredictWidth=2*FetchWidth` counts
  halfword candidates. gem5 `fetchWidth` counts instructions and is set to
  the maximum compressed-instruction count. This maps a throughput ceiling,
  not identical fetch and prediction timing.
- The shared V5 floating-point/vector PRF is represented by separate gem5
  floating-point and vector files. Matching capacities do not reproduce
  sharing contention. V0/VL PRFs and integer/memory register caches are not
  modeled separately.
- RTL Store Buffer, Dispatch Queues, FTQ, and IBuffer differ from gem5 in
  lifecycle, micro-op counts, and backpressure. Equal capacity does not
  establish equal timing.

| gem5 parameter | V2 minimal | V2 nanhug | V2 default | v5 full / stress |
| --- | ---: | ---: | ---: | ---: |
| `fetchWidth` (instructions) | 8 | 16 | 16 | 16 |
| `fetchBufferSize` (B) | 16 | 32 | 32 | 32 |
| `fetchQueueSize` | 16 | 32 | 48 | 32 |
| `numFTQEntries` | 8 | 16 | 64 | 48 |
| `numPhysFloatRegs` / `numPhysVecRegs` | 64 / 64 | 64 / 64 | 192 / 64 | 160 / 160 |
| Vector extension | VLEN 128, ELEN 64 | VLEN 128, ELEN 64 | VLEN 128, ELEN 64 | VLEN 128, ELEN 64 |

All models enable the V extension with VLEN 128 and ELEN 64 by default.
The 64-entry V2 vector PRF and corresponding vector execution resources
extend the shared experimental platform beyond the older scalar V2 RTL.

## Grouped issue and execution units

V2 RS capacity is derived from `IssQueSize * deq`; wide categories split at
`maxRsDeq=2`. Multiple gem5 `IQUnit` instances preserve category capacities
instead of replacing all queues with one centralized IQ.

| V2 RS category | minimal / nanhug | default |
| --- | --- | --- |
| ALU | 16 | 32 + 32 |
| MDU | 8 | 32 |
| JMP / CSR / Fence / I2F | 8 | 16 |
| Load | 16 | 32 |
| Store Address | 16 | 32 |
| Store Data | 16 | 32 |
| FMAC | 8 | 32 + 32 |
| FMISC | 8 | 32 |
| Total | 96 | 304 |

| V5 IssueBlock | full / stress |
| --- | --- |
| Int0–Int3 | 18 each |
| VFMA / VFALU / VFDIV | 16 / 16 / 10 |
| STA / LDU0 / LDU1 / VLSU / STD | 20 / 16 / 16 / 16 / 20 |
| Total | 202 |

| RTL execution resources | V2 minimal / nanhug | V2 default | V5 full / stress |
| --- | --- | --- | --- |
| Integer ALU / MDU | 2 / 1 | 4 / 2 | 4 ALUs; multiplication/division shared across BJU groups |
| Jump / CSR category | 1 | 1 | 4 BJUs with group-specific functions |
| FMAC / FMISC | 1 / 1 | 4 / 2 | 2 VFMA, 2 VFALU, 1 VFDIV |
| Load / STA / STD | 2 / 2 / 2 | 2 / 2 / 2 | 2 / 1 / 1, plus VLSU |

gem5 routes by `OpClass` and uses its own scheduling and wakeup rules.
Operations from some compound RTL FUs are merged in corresponding gem5 FUs.
Separate STA/STD paths, vector memory execution, register-read arbitration,
bypass, and replay timing have not been recreated from RTL. The unified
`issueWidth`, `wbWidth`, and fixed `opLat` are explicit model choices;
equivalence cannot be derived from queue totals.

The following gem5 FU latencies apply to all models, in CPU cycles.
Other `OpClass` values explicitly use `opLat=1, pipelined=True`. Fixed gem5
division latencies do not represent variable RTL division latency. Vector
operations share the modeled floating-point ports, including the V2
experimental extension.

| `OpClass` | `opLat` | `pipelined` |
| --- | ---: | --- |
| `IntAlu`, `System` | 1 | true |
| `IntMult` | 3 | true |
| `IntDiv`, `SimdDiv`, `SimdFloatDiv` | 20 | false |
| `FloatAdd`, `FloatCmp`, `FloatCvt`, `Bf16Cvt`, `SimdFloatAdd` | 2 | true |
| `FloatMult` | 4 | true |
| `FloatMultAcc` | 5 | true |
| `FloatMisc`, `SimdFloatMult`, `SimdFloatMultAcc` | 3 | true |
| `FloatDiv` | 12 | false |
| `FloatSqrt`, `SimdSqrt`, `SimdFloatSqrt` | 24 | false |

## Cache capacity and concurrency

All cache lines are 64 B. Capacities include data across all banks.

| Level | V2 minimal | V2 nanhug | V2 default | v5 full | v5 stress |
| --- | --- | --- | --- | --- | --- |
| L1I | 16 KiB / 4-way | 16 KiB / 4-way | 64 KiB / 4-way | 64 KiB / 4-way | 64 KiB / 4-way |
| L1D | 32 KiB / 8-way | 32 KiB / 4-way | 64 KiB / 4-way | 64 KiB / 4-way | 16 KiB / 2-way |
| L2 | None | 256 KiB / 8-way / 4 banks | 1 MiB / 8-way / 4 banks | 1 MiB / 8-way / 2 banks | 1 MiB / 8-way / 2 banks |
| LLC | 512 KiB / 8-way / 1 bank | 1.5 MiB / 6-way / 4 banks | 6 MiB / 6-way / 4 banks | 2 MiB / 16-way / 2 HNX | 2 MiB / 16-way / 2 HNX |

V5 stress DCache capacity is calculated as
`128 sets * 2 ways * 64 B = 16 KiB`; the source's “32 kB” comment is not
used as capacity evidence. Its ICache inherits 64 KiB/4-way.

The original V5 full L2 parameter is `512*1024/8/2/64=512` sets.
`CpuClusterParams` multiplies sets by two, producing 1024 sets per Slice.
Each of two Slices holds `1024*8*64=512 KiB`, totaling 1 MiB. Each Slice
has 16 MSHRs, totaling 32. The `l2cacheSize` reporting field omits the two
Slices, so its 512 KiB report is not the total capacity.

The V5 LLC uses the entire `mini_soc` island's 2 MiB capacity, without
multiplying by HNX count again. `hnxOutstanding=32` counts total home-agent
resources. gem5 LLC MSHRs approximate capacity rather than matching HNX
transaction state. Classic caches and crossbars do not recreate
TileLink/CHI, the Zhujiang ring, bank contention, directories, or ECC timing.

L2/LLC banks are separate Cache instances. Each receives total capacity and
MSHR count divided by the number of banks. Bank-selection bits sit above
each bank's set-index bits: `bank_low_bit = 6 + log2(sets_per_bank)`.
The interleaving granularity is `sets_per_bank * 64 B`, keeping every set
reachable. This address mapping differs from RTL's 64 B line interleaving.
L1 internal banks are not modeled separately; the L1 bank fields in
`PROFILE` only record RTL organization. Banks share crossbars whose
arbitration and port timing do not reproduce the complete RTL bank structure.

| gem5 bank interleaving granularity | V2 minimal | V2 nanhug | V2 default | v5 full / stress |
| --- | --- | --- | --- | --- |
| L2 | None | 8 KiB | 32 KiB | 64 KiB |
| LLC | One bank, no interleaving | 64 KiB | 256 KiB | 64 KiB |

| gem5 MSHRs | V2 minimal | V2 nanhug | V2 default | v5 full | v5 stress |
| --- | ---: | ---: | ---: | ---: | ---: |
| L1I | 2 | 2 | 2 | 4 | 4 |
| L1D | 4 | 16 | 16 | 32 | 4 |
| L2 | — | 56 | 56 | 32 | 32 |
| LLC | 14 | 56 | 56 | 32 | 32 |

V2 Huancun has 14 ordinary MSHRs plus two reserved B/C MSHRs per bank. The
table maps totals of ordinary MSHRs without dedicated TileLink channel
resources. The V5 ICache's four fetch and ten prefetch MSHRs cannot be fully
represented by one gem5 MSHR count.

### Known instruction-prefetch limitations

Changes to instruction-prefetch resources and fill targets are deferred.
The RTL sources are listed above; the current differences are:

| Model | RTL behavior | Current gem5 behavior |
| --- | --- | --- |
| V2 minimal / nanhug | Instruction prefetch disabled | Remains disabled |
| V2 default | Two demand entries and two Hint send slots; a slot is released when its Hint is sent, and the prefetch fills L2 rather than L1 | L1 Tagged prefetching uses `mshrs=2` and `demand_mshr_reserve=1` |
| v5 full / stress | Separate pools of four fetch and ten prefetch MSHRs, both filling L1 | Four shared MSHRs; the ten-entry prefetch pool is absent |

[BaseCache](../../src/mem/cache/base.cc) gates prefetch issue through
[MSHRQueue::canPrefetch](../../src/mem/cache/mshr_queue.hh). With
`mshrs=2` and `demand_mshr_reserve=1`, its condition reduces to
`allocated < 0`, so V2 default cannot issue instruction prefetches despite
having a Tagged prefetcher configured. Hint send slots must not be added to
demand MSHRs as equivalent resources. Likewise, replacing V5's separate
four/ten-entry pools with fourteen shared entries would not reproduce its RTL.
Further alignment requires modeling pool separation, admission, arbitration,
cancellation, and fill targets together.
Resume from V2's `frontend/icache/ICacheMissUnit.scala` and
`frontend/icache/IPrefetch.scala`, relative to `src/main/scala/xiangshan/`,
and V5's
`dep/nanhu/src/main/scala/xiangshan/frontend/icache/ICacheMissUnit.scala`.

Use a fixed `v5_full` platform for subsequent DASICS experiments, comparing
protection enabled and disabled with the same input and measurement region.
Report the overhead within this gem5 model, rather than RTL performance or
speed differences across Nanhu generations. Shared modeling differences may
affect the two cases differently and need not cancel completely.

## Branch prediction and prefetching

| RTL parameter | V2 minimal | V2 nanhug | V2 default | v5 full / stress |
| --- | --- | --- | --- | --- |
| uBTB / FTB / RAS | 256 / 2048 / 32 | 128 / 1024 / 32 | 256 / 2048 / 32 | 256 / 4096 / 16 |
| `EnableBPD` field | false | true | true | No corresponding field |
| `EnableSC` field | true | false | true | false |
| `EnableLoop` field | false | false | true | Not mapped |
| Instruction prefetch | Disabled | Disabled | Enabled | Enabled |
| Core data prefetch | None | SMS → L2 | SMS → L2 | Stream/Stride with SMS |
| Local L2 prefetch | None | Receives core requests | Receives core requests | PBOP + VBOP, plus core requests |

gem5 uses TAGE, BTB, and RAS components as explicit approximations. No
effective consumer of V2 `EnableBPD=false` was found in the active prediction
path; the field does not prove that RTL TAGE was removed. FTB versus a BTB,
and arbitrary history tables versus gem5 geometric histories, differ in
indexing and training. SC, Loop, uBTB, ITTAGE, and the V5 speculative RAS are
not modeled with their original structures.

| gem5 predictor parameter | Setting |
| --- | --- |
| Conditional prediction | `TAGE`, four history tables, `minHist=8`, `maxHist=119`, geometric histories |
| TAGE entries per table | V2 4096; V5 2048; base table uses the same entry count |
| TAGE tag / counter / useful widths | 8 / 3 / 2 |
| History state | Speculative updates, 16-bit path history, `2^21` history buffer |
| First-level BTB | Capacity from uBTB field, 4-way, 16-bit tag, 1-cycle latency |
| Second-level BTB | Capacity from FTB field, 4-way, 16-bit tag, 2-cycle latency |
| RAS | Capacity from the RAS field above; no separate speculative RAS |
| Indirect prediction | gem5 `ITTAGE`, reusing table count, capacities, tag, and history range above |
| Instruction address shift | `instShiftAmt=1` |

Prefetching uses explicitly configured gem5 components: Tagged approximates
instruction prefetching, gem5 SMS approximates core SMS, Stride approximates
V5 L1D Stream/Stride, and gem5 BOP approximates L2 BOP. Differences remain in
SMS AGT/PHT organization, dual PBOP/VBOP instances and arbitrary offset lists,
arbitration between core and L2 requests, translation, and transport latency.
Paths disabled by RTL configuration remain disabled in the corresponding
model.

| gem5 prefetch parameter | Setting |
| --- | --- |
| Shared queue / latency | 16 entries / 1 cycle, 64 B blocks, 4 KiB pages, physical-address training |
| Tagged | `degree=1` |
| SMS | `ft_size=16`, `pht_size=64`, `region_size=1024 B` |
| Stride | `degree=1`, `distance=0`, 2-bit confidence, initial value 0, 50% threshold |
| Stride table | 16 entries, direct-mapped; RTL's ten entries map to a supported power-of-two gem5 capacity |
| BOP | `degree=1`, `score_max=31`, `round_max=50`, `bad_score=2` |
| BOP RR / tag / offsets | 256 entries / 12 bits / 46 entries, negative offsets enabled |
| BOP delay queue | Enabled, 16 entries, 175 cycles |
| V5 L2 composition | `MultiPrefetcher(BOP, SMS)`, without RTL PBOP/VBOP/core-request arbitration |

SMS trains on the gem5 L2 access path. The RTL core-training and subsequent
L2-request transport path is not recreated cycle by cycle. gem5 generates its
own BOP offsets rather than using the arbitrary RTL offset lists.

## Shared experimental platform

CPU/bus clocks, DRAM, stage delays, and FU/cache latencies are explicitly
fixed in the shared helper for controlled comparisons. They are not labeled
as calibrated RTL timing. V5 `cpuFreq=2 GHz` is a nominal SoC parameter;
2 GHz for V2 and DRAM timing for all models are shared experimental settings.

| Item | Setting and boundary |
| --- | --- |
| CPU / NoC-equivalent bus clock | 2 GHz |
| ISA and execution | RV64, single core/hart, full-system bare metal, `timing` memory mode |
| ISA configuration | `RVA20S64` plus `Zba/Zbb/Zbc/Zbs/V`, VLEN 128, ELEN 64, MSU privilege set |
| DRAM | Single-channel DDR4-2400, 64-bit bus, 8 GiB |
| Memory address | Starts at `0x80000000`; reset-vector page mapped separately below it |
| DRAM reference | V5 reference file has `tCK=0.83 ns`; gem5 DDR4-2400 is used without reproducing DRAMsim3's 2000/1600 co-simulation frequency fields |
| Artifacts | Separate `config.ini`, `config.json`, and `stats.txt` per model |

The current ISA configuration does not enable H or cover virtualization.

| gem5 CPU timing or policy | Setting |
| --- | --- |
| `dispatchWidth` | The model's `renameWidth` |
| `issueWidth` / `wbWidth` | 16 / 16 |
| `fetchTargetWidth` | The model's `fetchBufferSize` |
| `cacheLoadPorts` / `cacheStorePorts` | V2 2 / 2; V5 2 / 1 |
| Forward-stage delays | `fetchToBacDelay`, `bacToFetchDelay`, `fetchToDecodeDelay`, `decodeToRenameDelay`, `renameToROBDelay`, `issueToExecuteDelay`, `iewToCommitDelay` are all 1 |
| `renameToIEWDelay` | 2 |
| Feedback delays | `decodeToFetchDelay`, `renameToFetchDelay`, `iewToFetchDelay`, `commitToFetchDelay`, `renameToDecodeDelay`, `iewToDecodeDelay`, `commitToDecodeDelay`, `iewToRenameDelay`, `commitToRenameDelay`, `commitToIEWDelay` are all 1 |
| Trap delays | `trapLatency=13`, `fetchTrapLatency=1` |
| Communication buffers | `backComSize=5`, `forwardComSize=5` |
| Scheduling | `iqInsertionPolicy=FirstMatch`, decoupled frontend, at most four fetch targets and two taken predictions per cycle |
| Store-set prediction | LFST/SSIT 1024 entries each, direct-mapped SSIT, clearing period 250000 |
| Memory ordering | `LSQCheckLoads=True`, `LSQDepCheckShift=4`, `needsTSO=False` |
| Other physical files | VecPred 32, Mat 2, CC 0; gem5 supporting resources |

| Cache, interconnect, and memory timing | Setting |
| --- | --- |
| All cache tag / data / response latencies | 2 / 2 / 2 cycles; the fields do not directly sum to total hit latency |
| Cache concurrency | 20 targets per MSHR, eight write buffers, non-sequential tag/data access |
| Replacement and inclusion | `LRURP`, `mostly_incl`; replace RTL PLRU/DRRIP and non-inclusive protocols |
| Data path | `L1I/L1D/MMU walker → L1 XBar → L2 banks (if present) → L2 XBar → LLC banks → memory XBar → DRAM` |
| Cache crossbars | 32 B wide; frontend/forward/response/header latencies are one cycle each |
| Snoop filter | One-cycle lookup, 32 MiB capacity |
| MMIO bridge | 50 ns; HiFive platform RTC 10 MHz |
| Reset page | 4 KiB `SimpleMemory` at `0x7FFFF000`, 1 ns, 32 GiB/s |
| DRAM controller | FR-FCFS; read/write queues 64 / 128 entries; high/low write thresholds 85% / 50% |
| Read/write switching | At least 16 writes and 16 reads per batch |
| DDR4 devices | `DDR4_2400_8x8`, one rank per channel, eight x8 devices; actual device timings are recorded in `config.ini` |

Modify a model's entry-point `PROFILE` for model-specific values. Shared
timing, FUs, connections, and printing are in `dasics_platform.py`.
The instantiated `config.ini` records actual SimObject parameters. Total
cycles of the CSR test describe that test only and do not measure
application-level DASICS overhead.

## DASICS microarchitectural costs pending modeling

These configurations reuse existing CSR semantics. Frontend trust tags,
bound-check latency, distributed CSR propagation, flushes after configuration
updates, check-port contention, and speculative-path handling require separate
implementation and validation. Compare DASICS modes with the same model,
input, and measurement interval before reporting cycle differences.
