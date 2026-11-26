# DASICS 下的 glibc printf 功能回归

在 RV64 Linux SE 的 `v5_full` O3 上运行 `printf("n=%d\n", 7)`。可信调用者 A 使用 `a0/a1` 传入格式串和整数，不可信 B 使用私有栈、独立的 glibc `FILE` 和 256 字节全缓冲区。B 中的 `b_printf`、`b___vfprintf_internal` 及这条十进制格式化路径上的助手函数来自 RISC-V 静态 `libc.a`。[对象提取与符号绑定](private_libc.py) · [代码与数据区间](layout.ld)

## 复现

从仓库根目录执行。需要已构建的 `build/RISCV_DASICS/gem5.opt`、带静态 glibc 的 `riscv64-linux-gnu-` 工具链和 Python `pyelftools`。本批使用 glibc 2.39，构建脚本按该工具链的 archive 成员和 TLS 布局提取固定调用路径。

```bash
cd tests/test-progs/dasics/riscv-dasics-printf
make -j4 all
mkdir -p build/runs
batch=$(mktemp -d build/runs/printf-v5-full-XXXXXX)
python3 -B check.py plain --elf build/plain.elf --outdir "$batch/plain" &&
    python3 -B check.py protected --elf build/protected.elf --outdir "$batch/protected"
```

## 验收

| 检查 | 通过条件 |
|---|---|
| 函数与输出 | 两版 `printf` 均返回 `4`。A 核对 B 缓冲区的写入长度，从该缓冲区输出实际字节。客体 stdout 恰为 `6e 3d 37 0a`，stderr 为空，退出码为零。 |
| B 的入口 | A 给 `s3/fs3/t6` 写入非零值。保护版执行 `PROREG.G.I 0x008`、`PROREG.F.I 0x008` 和 `CLR.G.I 0x040`。B 的入口探针在调用 glibc 前检查三个寄存器都读零。 |
| A 的返回 | glibc 返回后，B 的汇编探针主动改写 `s3/fs3` 并保留 `a0`。A 执行一次 `LEAVE`，逐位核对两个原值。按临时寄存器约定，返回时允许 B 已改写 `t6`。普通版用软件完成对应的清零与恢复。 |
| 执行边界 | 退休轨迹依次经过 B 入口、两个真实 glibc 函数和返回门。从 B 入口到返回的所有退休 PC 都在 B 的代码窗口内，且 B 内的 ECALL 数为零。 |

A 在调用前初始化 B 的流，返回后检查缓冲区边界和游标，使用 `write` 输出一次，再用 `_exit` 退出。B 的数据权限覆盖专用栈、缓冲区、流对象和这条路径所需的常量、指针及私有运行时状态。验证范围为上述固定调用。[调用门和 B 入口](gate.S) · [客体断言与输出](main.c) · [宿主校验](check.py)

每种模式的 `result.json` 记录输出字节、B 区间、ECALL 数和各标记的退休顺序；`guest.out` 保存原始输出，`m5out/commit.trace.gz` 保存完整退休轨迹。

## 同一 DASICS 调用门的周期对照

在保护 `s3/fs3`、只清零 `t6` 的条件下，两种计时批长的配对结果均为硬件门平均节省 1 周期/次。[2026-11-26 实验记录](experiments/2026-11-26-printf-roi.md)

`roi-sw.elf` 和 `roi-hw.elf` 均启用 RV64 DASICS，在 `v5_full` 配置下使用相同的数据授权、私有栈、`DASICSCALL.JR` 和 B 中的 glibc 代码。软件门保存、清零并恢复 `s3/fs3`，只清零 `t6`；硬件门使用两条 `PROREG`、一条 `CLR` 和一条 `LEAVE`。两版在相同地址跳过各自的填充。短回归检查两段保护代码以外的装载布局、B 的入口零值与返回后的恢复值。

在本用例目录运行：

```bash
make -j4 roi
mkdir -p build/runs
batch=$(mktemp -d build/runs/printf-roi-XXXXXX)
python3 -B roi_check.py --outdir "$batch/functional" &&
    python3 -B measure_roi.py --short --outdir "$batch/short" &&
    python3 -B measure_roi.py --outdir "$batch/measurements"
```

每个作业先预热 128 次。短计时圈定 4 次调用，正式计时并行运行两种门各 1,024 和 4,096 次。ROI 包含调用循环、寄存器探针、授权与撤权、格式化和返回；A 在 ROI 之后校验并输出 32 KiB 缓冲区中全部实际记录。`measurements/pairs.csv` 给出每种批长的 ROI 总周期、平均周期和相对软件门的节省比例。每个作业的 `m5out/roi-stats.txt` 保存 ROI 统计，脚本将 `numCycles` 与起止 tick 核对，并检查硬件门每次少退休 3 条指令、2 次 load 和 2 次 store。[计时循环](roi_loop.S) · [配对计算](measure_roi.py)

### 全组保护

在本例的两种计时批长下，硬件门相对软件门平均节省约 39 周期/次（约 5.76%）。[全组实验结果与计数核对](experiments/2026-11-26-printf-roi.md#全组寄存器保护)

全组对照保存并恢复 `s0–s11`、`fs0–fs11`，只清零 `t0–t6`、`ft0–ft6`。两种门均用 `ra` 携带 B 的入口，通过 `DASICSCALL.JR ra,ra,0` 传入 `a0/a1`。功能用例给 38 个寄存器写入非零值，检查 B 的入口视图，并在 B 改写全部 24 个被保存的寄存器后，由 A 逐个检查恢复值。计时用例沿用原有的 glibc 函数体和 B 返回前的 `s3/fs3` 改写探针。

```bash
make -j4 full
mkdir -p build/runs
batch=$(mktemp -d build/runs/printf-full-roi-XXXXXX)
python3 -B roi_check.py --full --outdir "$batch/functional" &&
    python3 -B measure_roi.py --full --short --outdir "$batch/short" &&
    python3 -B measure_roi.py --full --outdir "$batch/measurements"
```

软件策略执行 24 条保存、38 条清零、24 条恢复。硬件策略执行两条 `PROREG`、两条 `CLR` 和一条 `LEAVE`。配对检查要求每次调用的退休指令、加载、存储差额分别为 81、24、24，实测周期汇总在 `measurements/pairs.csv`。
