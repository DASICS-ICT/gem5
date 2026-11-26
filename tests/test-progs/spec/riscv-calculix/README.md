# riscv-calculix

[公共说明](../README.md) | [gem5 SE 配置](../../../../configs/spec/README.md)

SPEC CPU2006 `454.calculix`：有限元结构分析，按作业输入计算结构响应。

三种规模分别使用 `data/test/`、`data/train/`、`data/ref/`；公共输入位于
`data/all/`。调用和比较规则以 [workload.json](workload.json) 为准。

## 输入与调用

| `input` | 调用序号 | 程序参数 | 标准输入 | 标准输出 |
| --- | ---: | --- | --- | --- |
| `test` | 1 | `-i beampic` | — | `beampic.log` |
| `train` | 1 | `-i stairs` | — | `stairs.log` |
| `ref` | 1 | `-i hyperviscoplastic` | — | `hyperviscoplastic.log` |

## 输出比较

调用序号与上表对应。参数为空时使用 specdiff 默认比较，不额外放宽容差。

| `input` | 调用序号 | 比较输出 | specdiff 参数 |
| --- | ---: | --- | --- |
| `test` | 1 | `SPECtestformatmodifier_z.txt`<br>`beampic.dat` | `--abstol 1e-9 --reltol 1e-9 --obiwan` |
| `train` | 1 | `SPECtestformatmodifier_z.txt`<br>`stairs.dat` | `--abstol 1e-9 --reltol 1e-9 --obiwan` |
| `ref` | 1 | `SPECtestformatmodifier_z.txt`<br>`hyperviscoplastic.dat` | `--abstol 1e-9 --reltol 1e-9 --obiwan` |

## 独立构建与运行

在本目录执行：

```bash
make -j48
make run input=test
make check input=test
make clean
```

```bash
make run input=train SMOKE=1 TIMEOUT=15
make run input=ref SMOKE=1 TIMEOUT=15
```

## gem5 SE

在 gem5 仓库根目录执行：

```bash
make spec06-test TEST=riscv-calculix input=test \
  config=riscv_se_v5_full.py
make spec06-clean TEST=riscv-calculix
```

`train/ref` 默认完整运行；`SMOKE=1` 只检查启动与进展，不比较完整输出。
依赖、资产准备、产物目录及结果状态见[公共说明](../README.md)。
多配置与 `all` 用法见[公共说明](../README.md#多配置运行)。

### 统计 `beampic` 的 `_gfortran_string_len_trim` 调用次数

从 gem5 仓库根目录运行。将 `ORDINARY_CASE` 指向含普通版 `build/calculix.elf`、SPEC 输入和参考输出的用例目录；与其同级的 `tools/specdiff-runtime` 提供比较工具。

```bash
case_dir=tests/test-progs/spec/riscv-calculix
mkdir -p "$case_dir/build/runs"
batch=$(mktemp -d "$case_dir/build/runs/len-trim-XXXXXX")
python3 -B "$case_dir/count_len_trim.py" \
    --ordinary-case "${ORDINARY_CASE:-$case_dir}" --outdir "$batch/count"
```

脚本从随批次保存的 ELF 提取目标入口、返回指令和可静态解析的直接转移点，在普通 `v5_full` Linux SE 配置中从程序启动到退出统计其退休次数。`main` 用作正对照。验收要求客体正常退出、两份 `specdiff` 通过，并且目标入口计数、返回指令计数之和、直接调用点计数之和三者相等。`_gfortran_string_len_trim_char4` 是单独的函数。

`result.json` 给出总数和校验状态，`callsites.csv` 与 `callers.csv` 分别按调用点和调用者统计并保留零命中项。原始退休 PC 计数在 `m5out/retired-pcs.json`。[地址提取](len_trim_sites.py) · [运行与校验](count_len_trim.py)

### 保护 `getnewline_` 的 1 字节热点

在 `v5_full` 的 `beampic` 输入上，93,148 次热点调用平均节省 47.0011 周期/次，硬件门相对同策略软件门使整程序周期减少 3.2170%。[实验记录](experiments/2026-11-26-len-trim.md) · [计数与周期汇总](experiments/2026-11-26-len-trim-summary.json)

软件门与硬件门都只接管普通 ELF 中 `0xb4108` 对应的调用。构建脚本在 `getnewline.o` 的副本中替换一条重定位，并从交叉工具链的 `libgfortran.a` 提取 B 的真实 `_gfortran_string_len_trim`。链接后重新定位各标记，验证 B 函数体与原实现、逐个检查直接调用点及两版布局。[构建规则](protected/len-trim/Makefile) · [布局校验](protected/len-trim/layout_check.py)

A 将当前字符复制到独立的 8 字节授权区，B 取得该区的只读权限及私有栈的读写权限。两种门均保存并恢复 `s0–s11/fs0–fs11`，只清零 `t0–t6/ft0–ft6`。窗口从 A 的调用指令退休开始，到 A 的续执行指令退休结束，包含复制字符、设置与撤销权限、B 的函数体以及门内的寄存器操作。[调用门](protected/len-trim/gate.S)

从仓库根目录运行。将 `BASELINE` 指向上一节生成的 `count/` 目录，`ORDINARY_CASE` 须包含该基线使用的普通 ELF 和对象文件。

```bash
case_dir="$PWD/tests/test-progs/spec/riscv-calculix"
gate="$case_dir/protected/len-trim"
mkdir -p "$case_dir/build/runs"
batch=$(mktemp -d "$case_dir/build/runs/len-trim-gate-XXXXXX")
make -j8 -C "$gate" ORDINARY_CASE="${ORDINARY_CASE:-$case_dir}" OUT="$batch/elfs" &&
    python3 -B "$gate/run_pair.py" --ordinary-case "${ORDINARY_CASE:-$case_dir}" \
        --baseline "$BASELINE" --batch "$batch" &&
    python3 -B "$gate/compare.py" --batch "$batch"
```

`layout.json` 给出实际计数的地址。每个版本的 `result.json` 保存退出状态、两份 `specdiff` 结果及退休计数。`paired-calls.csv.gz` 按调用序号记录两版起止 tick 和周期；`summary.json` 汇总窗口内、窗口外及整程序周期差额。[配对分析](protected/len-trim/compare.py)

### DASICS SE 启动回归

在仓库根目录运行以下回归。

```bash
make -j5 -C tests/test-progs/dasics/riscv-dasics-se-init check
```

该回归使用小型 RV64 Linux ELF，分别检查可信区执行、B 区拒绝、缺失符号、
区间重叠和普通配置默认关闭。受保护配置为
[`riscv_se_dasics_v5_full.py`](../../../../configs/spec/riscv_se_dasics_v5_full.py)。
加载器读取静态 ELF 的 `__dasics_trusted_start`、`__dasics_trusted_end`、
`__dasics_untrusted_start`、`__dasics_untrusted_end` 和
`__dasics_context_base`。代码区间按 8 字节对齐，包含起点，不含终点。
每个用例的日志位于测试目录的
`build/runs/<case>/gem5.log`。

### 保护 `fmod` 的完整 CalculiX 测试

2026-11-24 的实验记录收录了布局对齐前后的整程序差异，以及 585 次调用的逐次比较。[实验记录与配对数据](experiments/2026-11-24-fmod.md)

使用普通版 CalculiX 的对象文件、`test/beampic` 输入和公共 specdiff 运行库。
在仓库根目录执行

```bash
case_dir=tests/test-progs/spec/riscv-calculix
make -j46 -C "$case_dir"
make -j2 -C "$case_dir/protected" check
```

普通版已在其他工作区编译时，可在第二条 make 命令中传入
`ORDINARY_CASE=/path/to/tests/test-progs/spec/riscv-calculix`。
`OUT` 可指定受保护 ELF 的构建目录，`RUN_DIR` 可指定本次结果目录。
默认结果位于 `build/protected-fmod/runs/` 下独立的批次目录中。

`make check` 在启动仿真前比较两份 ELF 的布局。单独检查可执行
`make -j2 -C "$case_dir/protected" check-layout`，普通版对象位于其他工作区时
同样传入 `ORDINARY_CASE`。两种门各占 640 字节，填充位于最终 `ret` 之后。
检查覆盖调用方的调用及返回地址、门入口、B 的代码、查找表、GOT 表项和私有栈。
门内部的指令地址随保护实现而异。除门占用的空间和 GNU build ID 内容外，
两份 ELF 的已分配节须具有相同的布局和内容。

软件门（`sw`）和 G+F 门（`gf`）分别运行完整的 `beampic`。调用
`fmod(x, y)` 时，`fa0` 传入被除数，`fa1` 传入除数，`fa0` 返回浮点余数。B 使用私有栈，
可以读取辅助函数的 256 字节查找表和一个 8 字节 GOT 表项。
本实验覆盖该输入的数值路径，进入数学错误处理入口会终止仿真。

每个版本的 `result.json` 记录两份 SPEC 输出比较及退休 PC 计数。
`DASICSCALL`、真实 `fmod` 入口、可信返回门的入口和末尾均应各退休 585 次。
G+F 门的 `PROREG.G.I`、`PROREG.F.I`、`LEAVE` 也应各退休 585 次，
数学错误入口应为 0。计数来自 gem5 O3 的 `RetiredInstsPC`。

### 逐次测量 `fmod` 往返周期

在仓库根目录执行。复用已有对齐基线时，第二条 make 命令可省略，计时运行的
`OUT` 和 `BASELINE` 分别指向基线的 ELF 目录和含 `sw/`、`gf/` 的结果目录。

```bash
case_dir="$PWD/tests/test-progs/spec/riscv-calculix"
elf_dir="$case_dir/build/protected-fmod"
batch="$case_dir/build/runs/fmod-$(date +%Y%m%d-%H%M%S)"
make riscv-dasics
make -j2 -C "$case_dir/protected" check OUT="$elf_dir" RUN_DIR="$batch/reference"
make -j2 -C "$case_dir/protected" time-calls OUT="$elf_dir" \
    BASELINE="$batch/reference" RUN_DIR="$batch/timed"
```

每个窗口从调用方的调用指令提交开始，到返回后第一条调用方指令提交结束。
按调用点和执行序号配对，节省周期按软件门减去 G+F 门计算。
`paired-calls.csv` 保存逐次结果，`paired-summary.json` 保存总体和分调用点的统计。
同一版本启用跟踪后的整程序周期数和提交指令数须与其参考运行一致。
