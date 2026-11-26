# riscv-bwaves

[公共说明](../README.md) | [gem5 SE 配置](../../../../configs/spec/README.md)

SPEC CPU2006 `410.bwaves`：计算流体力学，求解三维可压缩流动。

[实验记录：BWaves 四个 libm pow 调用点的寄存器保护开销](experiments/2026-11-26-pow.md)

三种规模分别使用 `data/test/`、`data/train/`、`data/ref/`；公共输入位于
`data/all/`。调用和比较规则以 [workload.json](workload.json) 为准。

## 输入与调用

| `input` | 调用序号 | 程序参数 | 标准输入 | 标准输出 |
| --- | ---: | --- | --- | --- |
| `test` | 1 | 无参数 | — | `bwaves.stdout` |
| `train` | 1 | 无参数 | — | `bwaves.stdout` |
| `ref` | 1 | 无参数 | — | `bwaves.stdout` |

## 输出比较

调用序号与上表对应。参数为空时使用 specdiff 默认比较，不额外放宽容差。

| `input` | 调用序号 | 比较输出 | specdiff 参数 |
| --- | ---: | --- | --- |
| `test` | 1 | `bwaves.out` | `--abstol 1e-16` |
| `test` | 1 | `bwaves2.out` | `--reltol 0.015` |
| `test` | 1 | `bwaves3.out` | `--abstol 1e-6` |
| `train` | 1 | `bwaves.out` | `--abstol 1e-16` |
| `train` | 1 | `bwaves2.out` | `--reltol 0.015` |
| `train` | 1 | `bwaves3.out` | `--abstol 1e-6` |
| `ref` | 1 | `bwaves.out` | `--abstol 1e-16` |
| `ref` | 1 | `bwaves2.out` | `--reltol 0.015` |
| `ref` | 1 | `bwaves3.out` | `--abstol 1e-6` |

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
make spec06-test TEST=riscv-bwaves input=test \
  config=riscv_se_v5_full.py
make spec06-clean TEST=riscv-bwaves
```

`train/ref` 默认完整运行；`SMOKE=1` 只检查启动与进展，不比较完整输出。
依赖、资产准备、产物目录及结果状态见[公共说明](../README.md)。
多配置与 `all` 用法见[公共说明](../README.md#多配置运行)。

## 测量四个 libm `pow` 调用点

在仓库根目录执行。将 `ORDINARY_CASE` 指向含普通静态 `build/bwaves.elf`、Fortran 对象、SPEC 输入及参考输出的 BWaves 用例目录，同级的 `tools/specdiff-runtime` 用于数值比较。普通版计数需要支持插件的 QEMU RISC-V 用户态模拟器及其开发头文件。周期测量使用 DASICS 版 gem5 和 `v5_full`。

```bash
case_dir="$PWD/tests/test-progs/spec/riscv-bwaves"
ordinary="${ORDINARY_CASE:-$case_dir}"
mkdir -p "$case_dir/build/runs"
batch=$(mktemp -d "$case_dir/build/runs/pow-XXXXXX")
python3 -B "$case_dir/protected/ordinary.py" --ordinary-case "$ordinary" --batch "$batch"
make -j"$(nproc)" -C "$case_dir/protected" ORDINARY_CASE="$ordinary" OUT="$batch/elfs"
python3 -B "$case_dir/protected/run_pair.py" --ordinary-case "$ordinary" --batch "$batch"
```

普通 ELF 中，`shell_`、`flux_` 各有一个双精度 `pow(x, 0.75)` 调用点，`jacobian_` 有两个。QEMU 对原始 25 步 `test` 统计四处调用和函数入口，校验三个 SPEC 输出；另以同一网格 `33 × 33 × 16` 运行第一个时间步，生成单步数值参考。[普通版计数](protected/ordinary.py)

两种调用门使用相同的 libm 函数体、只读表和独立栈，保留 `fa0/fa1` 输入和 `fa0` 返回值。每次调用均保护 `s0–s11/fs0–fs11`，清零 `t0–t6/ft0–ft6`。该实验使用域私有浮点环境，跟踪 `pow` 的异常出口；触发需要共享数学错误状态的路径时，检查器会报告该工作负载不满足实验条件。[调用门](protected/gate.S)

两版单步运行的 `bwaves.out`、`bwaves2.out`、`bwaves3.out` 按上表的容差与普通单步参考比较。计时窗口从调用指令退休延伸到调用者返回后的第一条指令退休。按调用点与出现序号配对，`paired-calls.csv.gz` 保存逐次窗口，`summary.json` 汇总各调用点、全部窗口与单步程序的周期差。[配对统计](protected/compare.py)

完整输入应有 3,484,800 次 `pow` 入口执行记录；单步应有 139,392 对窗口，其中 `shell_`、`flux_` 各 17,424 对，`jacobian_` 的两个调用点各 52,272 对。

### 增加直接调用的普通版对照

在同一终端中执行，`batch` 指向上节成功完成的双门批次。

```bash
native_batch=$(mktemp -d "$case_dir/build/runs/pow-native-XXXXXX")
python3 -B "$case_dir/protected/run_native.py" \
    --ordinary-case "$ordinary" --paired-batch "$batch" --batch "$native_batch"
```

普通版使用相同 gem5 和 `v5_full` 模型，直接执行普通 ELF。脚本复用原批次的单步输入与三份数值参考，按 Fortran 调用点及点内序号匹配三份运行记录。`three-way-calls.csv.gz` 保存各次调用的周期，`summary.json` 给出相对普通版的端到端开销。该差额包含调用门、域切换和重链接布局的影响。[三组配对](protected/native_compare.py)
