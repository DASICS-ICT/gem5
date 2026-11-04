# SPEC CPU2006 SE 配置

[测试名单、资产与独立运行](../../tests/test-progs/spec/README.md)

本目录使用普通 SE 模式执行静态 RV64 Linux 程序。gem5 模拟用户态指令及
系统调用，不启动 Linux 内核，也不包含内核执行时序。

## 配置名单

| 配置文件 | 硬件模型 |
| --- | --- |
| [riscv_se_V2_minimal.py](riscv_se_V2_minimal.py) | `V2_minimal` |
| [riscv_se_V2_nanhug.py](riscv_se_V2_nanhug.py) | `V2_nanhug` |
| [riscv_se_V2_default.py](riscv_se_V2_default.py) | `V2_default` |
| [riscv_se_v5_full.py](riscv_se_v5_full.py) | `v5_full` |
| [riscv_se_v5_stress.py](riscv_se_v5_stress.py) | `v5_stress` |

| 配置项 | 设定 |
| --- | --- |
| CPU | 单核、单 hart `RiscvO3CPU`，由配置文件选择模型 |
| 频率 | 2 GHz |
| 内存模式 | `timing` |
| 内存 | 8 GiB，单通道 DDR4-2400 |
| ISA | RV64，启用 V 扩展，VLEN 128、ELEN 64 |
| CPU、队列、缓存及预取 | 复用 [DASICS O3 模型](../dasics/README.md)中对应的 `PROFILE` 参数 |
| 工作负载 | 静态 RV64GC、LP64D ELF；参数、输入和比较由各用例 `workload.json` 定义 |
| 退出条件 | 每次进程正常退出且退出码为 `0`，再由 runner 比较输出 |

五个入口由 `spec_platform.run_model(profile)` 共用 SE 执行逻辑，硬件由
`configs/dasics/dasics_platform.py` 的公共接口构造。各 SE 入口与同名
CSR 裸机模型共用硬件参数，保留模型说明中的结构与时序近似。

## 运行

在仓库根目录执行：

```bash
make riscv-dasics
make spec06-test TEST=riscv-calculix input=test \
  config=riscv_se_v5_full.py
make spec06-test TEST=riscv-calculix input=test \
  config="riscv_se_V2_default.py riscv_se_v5_full.py"
make spec06-test TEST=riscv-calculix input=test config=all
make spec06-test TEST=riscv-calculix input=train \
  config=riscv_se_v5_full.py SMOKE=1 TIMEOUT=15
make spec06-clean TEST=riscv-calculix
```

`TEST` 选择 `tests/test-progs/spec/` 下的用例，`input` 可取 `test/train/ref`，
默认 `test`；`config` 可以是单个文件名、引号包围的空格分隔文件名单，或
`all`。多选按给定顺序运行，`all` 按配置名单顺序运行；单项失败后继续其余
配置，任一配置失败使整体返回非零。默认执行完整输入，`SMOKE=1` 显式选择
启动检查；`TIMEOUT` 为每次调用的宿主超时秒数。

运行前打印本次 `config.ini` 的重要参数。每个调用单独实例化模拟器，
配置和统计写入 `build/m5out-o3/<config stem>/<input>/<调用序号>/`；
软件输出位于 `build/run-gem5/<config stem>/<input>/<调用序号>/`。
所有路径相对于所选用例目录。

不同配置的输出使用 `-------------------------------` 分隔。末尾打印各配置的
状态和 CPU 周期表；各配置独立保存工作目录、输出、比较记录和统计。

完整执行和比较成功后汇总 `system.cpu.numCycles`；该值包含各进程的启动，
不是单独划定的性能测量区间。启动检查不比较完整输出，也不产生完整周期结论。
未完整通过的配置在周期表中显示 `N/A`。
`spec06-clean TEST=...` 清理所选用例的整个 `build/`。

## 直接接口

```text
<config.py> --workdir DIR --stdout FILE --stderr FILE \
  [--stdin FILE] [--max-ticks TICKS] BINARY [PROGRAM_ARGS...]
```

`--max-ticks` 到期、异常退出或进程非零退出均视为执行失败。
Perlbench `test.pl` 的 fork/waitpid 限制及完整结果状态见
[公共说明](../../tests/test-progs/spec/README.md#已知-se-限制)。
