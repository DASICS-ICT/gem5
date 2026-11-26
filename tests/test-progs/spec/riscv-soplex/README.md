# riscv-soplex

[公共说明](../README.md) | [gem5 SE 配置](../../../../configs/spec/README.md)

SPEC CPU2006 `450.soplex`：线性规划，使用单纯形法求解 MPS 问题。

[实验记录：数据行解析中 glibc strtok 的寄存器保护开销](experiments/2026-11-26-strtok.md)

三种规模分别使用 `data/test/`、`data/train/`、`data/ref/`；公共输入位于
`data/all/`。调用和比较规则以 [workload.json](workload.json) 为准。

## 输入与调用

| `input` | 调用序号 | 程序参数 | 标准输入 | 标准输出 |
| --- | ---: | --- | --- | --- |
| `test` | 1 | `-m10000 test.mps` | — | `test.out` |
| `train` | 1 | `-s1 -e -m5000 pds-20.mps` | — | `pds-20.mps.out` |
| `train` | 2 | `-m1200 train.mps` | — | `train.out` |
| `ref` | 1 | `-s1 -e -m45000 pds-50.mps` | — | `pds-50.mps.out` |
| `ref` | 2 | `-m3500 ref.mps` | — | `ref.out` |

## 输出比较

调用序号与上表对应。参数为空时使用 specdiff 默认比较，不额外放宽容差。

| `input` | 调用序号 | 比较输出 | specdiff 参数 |
| --- | ---: | --- | --- |
| `test` | 1 | `test.out` | `--abstol 1e-5 --reltol 0.0001 --obiwan` |
| `test` | 1 | `test.stderr` | `--abstol 20 --reltol 10 --obiwan` |
| `train` | 1 | `pds-20.mps.out` | `--abstol 1e-5 --reltol 20 --obiwan` |
| `train` | 1 | `pds-20.mps.stderr` | `--abstol 20 --reltol 0.0001 --obiwan` |
| `train` | 2 | `train.out` | `--abstol 1e-5 --reltol 20 --obiwan` |
| `train` | 2 | `train.stderr` | `--abstol 20 --reltol 0.0001 --obiwan` |
| `ref` | 1 | `pds-50.mps.out` | `--abstol 1e-5 --reltol 0.02 --obiwan` |
| `ref` | 1 | `pds-50.mps.stderr` | `--abstol 20 --reltol 0.0001 --obiwan` |
| `ref` | 2 | `ref.out` | `--abstol 1e-5 --reltol 0.02 --obiwan` |
| `ref` | 2 | `ref.stderr` | `--abstol 20 --reltol 0.0001 --obiwan` |

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
make spec06-test TEST=riscv-soplex input=test \
  config=riscv_se_v5_full.py
make spec06-clean TEST=riscv-soplex
```

`train/ref` 默认完整运行；`SMOKE=1` 只检查启动与进展，不比较完整输出。
依赖、资产准备、产物目录及结果状态见[公共说明](../README.md)。
多配置与 `all` 用法见[公共说明](../README.md#多配置运行)。

## 统计 `test.mps` 的 `strtok` 首调与续调

从 gem5 仓库根目录执行。将 `ORDINARY_CASE` 指向含普通静态 `build/soplex.elf`、SPEC 输入和参考输出的用例目录，同级的 `tools/specdiff-runtime` 提供输出比较工具。

```bash
case_dir=tests/test-progs/spec/riscv-soplex
mkdir -p "$case_dir/build/runs"
batch=$(mktemp -d "$case_dir/build/runs/strtok-count-XXXXXX")
python3 -B "$case_dir/count_strtok.py" \
    --ordinary-case "${ORDINARY_CASE:-$case_dir}" --outdir "$batch/count"
```

普通 `v5_full` Linux SE 配置完整运行 `-m10000 test.mps`。从实际 ELF 提取 `MPSInput::readLine` 的调用点、`strtok` 入口及其尾跳目标 `__strtok_r`。对 `AUIPC+JALR`，记录实际转移的 `JALR` 地址。检查器通过 `__strtok_r` 中仅在首个参数为 NULL 时执行的游标加载区分续调，并单列绕过 `strtok` 直接调用该辅助函数的情况。[位点提取](strtok_sites.py) · [退休序列核对](strtok_sequences.py)

一次非 NULL 输入开始一个分词序列，随后对 `strtok(NULL, …)` 的调用沿用该序列的游标。调用次数包含返回空指针的调用。`count/callsites.csv` 按调用点列出首调与续调次数；`count/result.json` 给出序列长度、调用路径分布及 `test.out`、`test.stderr` 的 `specdiff` 验收结果。`count/m5out/retire.log` 和 `retired-pcs.json` 保存原始证据。[运行与验收](count_strtok.py)

## 验证数据行上的受保护 `strtok`

从 gem5 仓库根目录执行。需要 DASICS 版 gem5、普通 SoPlex 的源码与构建产物（含 `.o`、`.d`）、`test` 输入和参考输出，以及同级的 `tools/specdiff-runtime`。

```bash
case_dir="$PWD/tests/test-progs/spec/riscv-soplex"
ordinary="${ORDINARY_CASE:-$case_dir}"
mkdir -p "$case_dir/build/runs"
batch=$(mktemp -d "$case_dir/build/runs/strtok-gate-XXXXXX")
make -j"$(nproc)" -C "$case_dir/protected" ORDINARY_CASE="$ordinary" OUT="$batch/elfs"
python3 -B "$case_dir/protected/run_pair.py" \
    --ordinary-case "$ordinary" --elf-dir "$batch/elfs" --batch "$batch"
```

`MPSInput::readLine` 的五个数据行调用点共用 B 的 glibc `strtok` 和私有游标，两个区段头调用点使用普通 glibc。B 每次就地切分同一个 8 字节对齐的 256 字节行缓冲区，返回时撤销读写授权。两版均保护 `s0–s11/fs0–fs11` 并清零 `t0–t6/ft0–ft6`，分别使用软件指令和 `PROREG/CLR/LEAVE`。[测试构建](protected/Makefile) · [调用门](protected/gate.S)

两版先运行短输入，再运行完整 `test.mps`。每次返回后，可信侧在原始行的副本上维护独立参考游标，核对 token 指针偏移、NULL 返回和原地写入的字节。`strtok-tokens.csv` 按调用序号记录首调或续调、token 偏移和长度，偏移 `-1` 表示返回 NULL。完整输入每版应有 2,174 次首调、7,422 次续调、12 次普通区段头调用，且 `test.out` 和 `test.stderr` 均通过 `specdiff`。此配置包含逐次功能校验与日志，其周期数不适合用于调用门性能比较。[返回值校验](protected/verify_tokens.c) · [运行与验收](protected/run_pair.py)

## 测量软件门和硬件门的 `strtok` 调用周期

先完成上节功能回归，在同一终端中从仓库根目录执行。此处 `batch` 指向已通过的功能回归批次。

```bash
ref_csv="$batch/test/hw/work/01/strtok-tokens.csv"
perf_batch=$(mktemp -d "$case_dir/build/runs/strtok-roi-XXXXXX")
make -j"$(nproc)" -C "$case_dir/protected" perf ORDINARY_CASE="$ordinary" OUT="$perf_batch/elfs"
python3 -B "$case_dir/protected/run_perf.py" \
    --ordinary-case "$ordinary" --elf-dir "$perf_batch/elfs" \
    --batch "$perf_batch" --reference-csv "$ref_csv"
```

计时版在五个数据行调用点直接调用门。模拟器记录调用指令和返回 A 后第一条指令的退休 tick，再用 `config.ini` 中的 CPU 时钟周期换算。B 内读取持久游标的指令标记续调，设置返回值为 NULL 的指令标记分词结束。两份 ELF 的对应调用点、B 代码、数据和门入口均须同址。[静态检查](protected/perf_sites.py) · [计时入口](protected/run_perf.py)

`paired-calls.csv` 按调用点和动态出现次序列出两版的起止 tick、周期和差额。`summary.json` 按首调返回 token、续调返回 token、续调返回 NULL 汇总，同时给出整程序及窗口外周期差、实际与预期的退休指令和访存指令差额。每类节省比例以该类软件门窗口的总周期为分母。[配对和统计](protected/perf_compare.py)
