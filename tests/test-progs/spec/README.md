# SPEC CPU2006

[gem5 SE 配置](../../../configs/spec/README.md) | [仓库 README](../../../README.md)

本目录提供 29 项普通版 SPEC CPU2006 的静态 RV64GC、LP64D 构建入口、
QEMU 运行和 specdiff 比较。源码、输入和参考输出使用各用例内的 `src/`、
`data/`，公共构建与运行接口位于 `common.mk`、`run.py`。
复制整个 `spec/` 目录及其本地资产后，可以在各用例目录独立构建和使用 QEMU。

## 依赖

- GNU Make、Python 3、GNU `timeout`、`patch`。
- RISC-V Linux GCC、G++、GFortran、binutils 及对应静态运行库。
- `qemu-riscv64` 用户态模拟器。
- CPU2017 x86-64 specdiff、specperl 及其配套 Perl 文件。
- gem5 SE 另需仓库构建的 `build/RISCV_DASICS/gem5.opt`。

默认工具链前缀为 `riscv64-linux-gnu-`。源码使用普通版 origin，不使用带
LibDASICS 初始化和动态调用依赖的构建目录。Fortran 资产保留 origin 导出的
预处理 Fortran 源文件（含 `.f`/`.f90`）及其 include 文件；`build.mk` 不重新
执行原始 `.F` 预处理。

## 本地资产

```text
spec/
├── common.mk
├── run.py
├── tools/specdiff-runtime/bin/
│   ├── specdiff
│   ├── specperl
│   ├── common/
│   ├── lib/
│   └── harness/{specdiff,compare.pl,util.pl}
└── riscv-<name>/
    ├── Makefile
    ├── build.mk
    ├── Makefile.deps
    ├── workload.json
    ├── src/
    ├── data/{all,test,train,ref}/
    └── build/
```

`src/`、`data/` 和 specdiff 运行库为 Git 忽略的本地资产。`build.mk` 与必要的
`Makefile.deps` 已包含在用例中，不需要复制原构建 Makefile。将下列源目录替换
为对应资产位置，在 `tests/test-progs/spec/` 内执行：

```bash
ORIGIN_ROOT=/path/to/spec2006-lite-origin
WRAPPER_ROOT=/path/to/CPU2006LiteWrapper
SPEC_TOOLS=/path/to/spec2017_slim/bin

for case_dir in riscv-*; do
  benchmark=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["benchmark"])' \
    "$case_dir/workload.json")
  mkdir -p "$case_dir/src" "$case_dir/data"
  cp -a "$ORIGIN_ROOT/$benchmark/src/." "$case_dir/src/"
  cp -a "$WRAPPER_ROOT/$benchmark/data/." "$case_dir/data/"
done
patch -d riscv-cactusadm -p1 < patches/436-cactusadm-pughutils.patch
mkdir -p tools/specdiff-runtime/bin/harness
cp -a "$SPEC_TOOLS/specdiff" "$SPEC_TOOLS/specperl" \
  "$SPEC_TOOLS/common" "$SPEC_TOOLS/lib" tools/specdiff-runtime/bin/
cp -a "$SPEC_TOOLS/harness/specdiff" "$SPEC_TOOLS/harness/compare.pl" \
  "$SPEC_TOOLS/harness/util.pl" tools/specdiff-runtime/bin/harness/
```

CactusADM 的[兼容补丁](patches/436-cactusadm-pughutils.patch)消除 PUGH 日志中
`sprintf` 源与目标缓冲区重叠的未定义行为，保留原比较容差。补丁命令仅用于
新导入的原始源码；当前本地源码已应用时跳过，不能重复应用。

## 测试名单

| SPEC CPU2006 | 目录 | 功能 |
| --- | --- | --- |
| `400.perlbench` | [riscv-perlbench](riscv-perlbench/README.md) | Perl 解释器，执行字符串、脚本语言及邮件处理负载。 |
| `401.bzip2` | [riscv-bzip2](riscv-bzip2/README.md) | 压缩与解压缩，处理程序、图像和文本输入。 |
| `403.gcc` | [riscv-gcc](riscv-gcc/README.md) | C 编译器，编译预处理后的 C 输入并生成汇编输出。 |
| `410.bwaves` | [riscv-bwaves](riscv-bwaves/README.md) | 计算流体力学，求解三维可压缩流动。 |
| `416.gamess` | [riscv-gamess](riscv-gamess/README.md) | 量子化学，按输入文件计算分子电子结构。 |
| `429.mcf` | [riscv-mcf](riscv-mcf/README.md) | 组合优化，使用网络单纯形算法求解最小费用流。 |
| `433.milc` | [riscv-milc](riscv-milc/README.md) | 格点量子色动力学计算。 |
| `434.zeusmp` | [riscv-zeusmp](riscv-zeusmp/README.md) | 天体物理流体计算，执行磁流体动力学负载。 |
| `435.gromacs` | [riscv-gromacs](riscv-gromacs/README.md) | 分子动力学，执行粒子系统的数值积分。 |
| `436.cactusADM` | [riscv-cactusadm](riscv-cactusadm/README.md) | 数值相对论，按参数文件演化引力场。 |
| `437.leslie3d` | [riscv-leslie3d](riscv-leslie3d/README.md) | 计算流体力学，执行三维大涡模拟。 |
| `444.namd` | [riscv-namd](riscv-namd/README.md) | 分子动力学，按指定迭代次数计算分子系统。 |
| `445.gobmk` | [riscv-gobmk](riscv-gobmk/README.md) | 围棋程序，读取 GTP 指令并执行棋局搜索。 |
| `447.dealII` | [riscv-dealii](riscv-dealii/README.md) | 有限元计算，求解偏微分方程并输出网格与数值结果。 |
| `450.soplex` | [riscv-soplex](riscv-soplex/README.md) | 线性规划，使用单纯形法求解 MPS 问题。 |
| `453.povray` | [riscv-povray](riscv-povray/README.md) | 光线追踪，按场景配置生成图像。 |
| `454.calculix` | [riscv-calculix](riscv-calculix/README.md) | 有限元结构分析，按作业输入计算结构响应。 |
| `456.hmmer` | [riscv-hmmer](riscv-hmmer/README.md) | 生物序列分析，执行隐马尔可夫模型搜索与校准。 |
| `458.sjeng` | [riscv-sjeng](riscv-sjeng/README.md) | 国际象棋程序，执行棋局搜索。 |
| `459.GemsFDTD` | [riscv-gemsfdtd](riscv-gemsfdtd/README.md) | 电磁场计算，使用时域有限差分方法。 |
| `462.libquantum` | [riscv-libquantum](riscv-libquantum/README.md) | 量子计算模拟，使用量子寄存器模拟分解计算。 |
| `464.h264ref` | [riscv-h264ref](riscv-h264ref/README.md) | H.264 视频编码，按配置文件处理输入序列。 |
| `465.tonto` | [riscv-tonto](riscv-tonto/README.md) | 量子化学，执行分子轨道相关计算。 |
| `470.lbm` | [riscv-lbm](riscv-lbm/README.md) | 计算流体力学，使用格子玻尔兹曼方法。 |
| `471.omnetpp` | [riscv-omnetpp](riscv-omnetpp/README.md) | 离散事件网络模拟，按配置文件执行网络负载。 |
| `473.astar` | [riscv-astar](riscv-astar/README.md) | 路径搜索，处理地图与河流场景。 |
| `481.wrf` | [riscv-wrf](riscv-wrf/README.md) | 数值天气预报，按工作目录中的模式输入运行。 |
| `482.sphinx3` | [riscv-sphinx3](riscv-sphinx3/README.md) | 语音识别，读取声学模型和音频控制列表。 |
| `483.xalancbmk` | [riscv-xalancbmk](riscv-xalancbmk/README.md) | XML 转换，使用 XSLT 样式表处理 XML 输入。 |

## 独立构建与 QEMU

在所选用例目录执行：

```bash
make -j48
make run input=test
make check input=test
make clean
```

```bash
make -j48 CROSS_COMPILE=riscv64-linux-gnu-
make run input=train QEMU=qemu-riscv64 TIMEOUT=1800
make run input=ref QEMU=qemu-riscv64 TIMEOUT=1800
make run input=train SMOKE=1 TIMEOUT=15
make run input=ref SMOKE=1 TIMEOUT=15
```

`run` 完整执行所选规模的所有调用，并自动比较输出。`check` 只比较已有的
QEMU 输出；失败、启动检查或 ELF、描述文件、数据改变后，需要重新运行。
默认每次调用的宿主超时为 1800 秒。`train/ref` 默认完整运行；只有显式指定
`SMOKE=1` 才使用启动检查，并跳过完整输出比较。

## gem5 SE

在 gem5 仓库根目录执行：

```bash
make riscv-dasics
make spec06-test TEST=riscv-calculix input=test \
  config=riscv_se_v5_full.py
make spec06-test TEST=riscv-calculix input=train \
  config=riscv_se_v5_full.py SMOKE=1 TIMEOUT=15
make spec06-clean TEST=riscv-calculix
```

`TEST` 取测试名单中的目录名，`input` 为 `test/train/ref`，默认 `test`。
`config` 为 `configs/spec/` 下的配置文件名。`clean` 和 `spec06-clean TEST=...`
删除所选用例的整个 `build/`，保留源码、数据和公共工具。

### 多配置运行

```bash
make spec06-test TEST=riscv-calculix input=test \
  config="riscv_se_V2_default.py riscv_se_v5_full.py"
make spec06-test TEST=riscv-calculix input=test config=all
```

可选配置为 `riscv_se_V2_minimal.py`、`riscv_se_V2_nanhug.py`、
`riscv_se_V2_default.py`、`riscv_se_v5_full.py`、`riscv_se_v5_stress.py`。
多选按给定顺序串行运行，`all` 按上述顺序运行。不同配置之间打印
`-------------------------------`；单项失败后继续其余配置，任一失败使整体
返回非零。末尾打印配置、状态和 CPU 周期表。

仅完整运行且比较通过的配置汇总周期，其余配置的周期显示 `N/A`。

每个配置使用独立的 `run-gem5/<config stem>/` 和
`m5out-o3/<config stem>/` 目录；具体硬件参数见
[配置名单](../../../configs/spec/README.md#配置名单)。

## workload.json

| 字段 | 约定 |
| --- | --- |
| `benchmark` | 原 SPEC 标识，如 `454.calculix` |
| `prepare` | 可选输入准备规则：`wrf` 或 `sphinx3` |
| `sizes.test/train/ref.runs` | 按顺序执行的调用列表 |
| `runs[].argv` | ELF 后的参数数组，不经过 shell 解释 |
| `runs[].stdin` | 可选标准输入文件，路径相对于该调用的工作目录 |
| `runs[].stdout/stderr` | 标准输出和标准错误文件 |
| `runs[].unsupported_se` | 可选 SE 限制；QEMU 不跳过该调用 |
| `comparisons[].run` | 关联调用序号，从 1 开始 |
| `comparisons[].file` | 该调用产生的输出文件 |
| `comparisons[].args` | 原比较规则的 specdiff 参数；不统一放宽容差 |
| `comparisons[].unsupported_se` | 可选 SE 比较限制 |

每次调用独立准备工作目录，先复制 `data/all/input/`，再叠加
`data/<input>/input/`；参考输出先查 `data/<input>/output/`，再查
`data/all/output/`。比较对象必须属于成功完成的关联调用，且是本次新生成或
更新的输出。原始输入和参考输出不在工作目录中直接修改。

## 产物与状态

| 产物 | 用例目录中的位置 |
| --- | --- |
| ELF | `build/<name>.elf` |
| 编译对象、模块 | `build/objects/`、`build/modules/` |
| QEMU 调用目录 | `build/run-qemu/<input>/<调用序号>/` |
| gem5 调用目录 | `build/run-gem5/<config stem>/<input>/<调用序号>/` |
| gem5 配置与统计 | `build/m5out-o3/<config stem>/<input>/<调用序号>/` |
| 运行记录及汇总 | 运行目录的 `run-state.json`、`result.json` |
| 比较日志 | 对应输出旁的 `*.specdiff.log` |

调用序号使用 `01`、`02` 等目录。gem5 输出另保存 `gem5.log`；全部成功时，
汇总各调用最后一次 `system.cpu.numCycles`，覆盖进程启动和完整执行，未单独
划分测量区间。失败、超时、未支持或启动检查不报告完整工作负载周期数。

| 状态 | 含义 | runner 退出码 |
| --- | --- | ---: |
| `[OK]` | 所有调用正常结束，全部关联输出比较通过 | 0 |
| `[FAIL]` | 构建、执行、资产或比较失败 | 非零 |
| `[TIMEOUT]` | 完整运行超时，或启动检查未观察到进展 | 124 |
| `[UNSUPPORTED]` | 存在当前 SE 入口不支持的调用或比较 | 77 |
| `[SMOKE]` | 启动检查观察到进展，或程序已正常退出；未作完整比较 | 0 |

`[OK]` 为绿色，失败与超时为红色，`[UNSUPPORTED]` 和 `[SMOKE]` 为黄色。
GNU Make 使用零或非零状态报告整体结果。

## 已知 SE 限制

`400.perlbench` 的 `test.pl` 依赖 `fork/waitpid`，当前单 hart SE 配置不支持。
该调用及关联比较明确标为 `[UNSUPPORTED]`，其他调用继续；不能将该结果当作
整个 Perlbench `test` 通过。QEMU 路径保留完整调用与比较清单。
