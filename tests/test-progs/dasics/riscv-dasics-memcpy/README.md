# glibc memcpy 的 DASICS 调用门周期对照

六档对齐复制的两种批长均测得硬件门平均节省 45 周期/次。[2026-11-26 实验记录](experiments/2026-11-26-memcpy-roi.md) · [配对数据](experiments/2026-11-26-memcpy-roi.csv)

在单线程 RV64 Linux SE 的 `v5_full` O3 上，可信调用者 A 通过 `DASICSCALL.JR ra,ra,0` 进入 B 中真正的 glibc `memcpy(dst, src, len)`。六档复制长度为 1、2、15、16、64、4,096 字节。两组均保存并恢复 `s0–s11/fs0–fs11`，只清零 `t0–t6/ft0–ft6`。软件门使用保存、清零和恢复指令；硬件门使用两条 `PROREG`、两条 `CLR` 和一条 `LEAVE`。[门实现](gate.S) · [共用的保护策略](../riscv-dasics-printf/full_policy.inc)

## 复现

从仓库根目录运行。需要已构建的 `build/RISCV_DASICS/gem5.opt`、RV64 Linux 交叉工具链及静态 glibc、Python `pyelftools`。

```bash
cd tests/test-progs/dasics/riscv-dasics-memcpy
make -j4 all
mkdir -p build/runs
batch=$(mktemp -d build/runs/memcpy-v5-full-XXXXXX)
python3 -B verify_memcpy.py --outdir "$batch/functional" &&
    python3 -B measure.py --short --outdir "$batch/short" &&
    python3 -B measure.py --outdir "$batch/measurements"
```

## 调用和校验

- A 通过 `a0/a1/a2` 传入目的指针、源指针和运行时长度。源和目的均按 64 字节对齐，互不重叠，各有 4 KiB 的有效载荷和两侧的 64 字节哨兵。门按 DASICS 的 8 字节粒度向上取整设置源只读、目的读写的区间，并授予 B 私有栈和复制助手的只读跳转表访问权。[缓冲区与数据检查](main.c)
- 构建从交叉工具链的 `libc.a` 提取 `memcpy.o` 和 `wordcopy.o`，将实现及助手放入 B。短测针对每个长度先经过寄存器探针，再用另一份数据直接进入 `b_memcpy`。客体检查返回指针、源内容、复制字节、未复制的尾部和哨兵。宿主检查两份 ELF 的布局、保护指令与退休路径。[构建规则](Makefile) · [短测](verify_memcpy.py)
- 计时直接进入 `b_memcpy`。每项作业先用同一对缓冲区预热 128 次；A 核对预热结果并换用新的源数据和目的填充值，再开始计时。ROI 包含循环、完整的跨域往返、复制和每次的返回指针检查。最终逐字节核对在 ROI 结束后进行。[计时循环](roi_loop.S)
- 正式批长为 1,024 和 4,096 次，每个长度和批长均配对比较两种门。平均每次节省周期为两版 ROI 总周期差除以计时调用次数，降幅为总周期差除以软件门总周期。脚本核对起止 tick 与 CPU 周期、复制入口和助手的退休次数，以及每次少退休 81 条指令、24 条加载和 24 条存储的预期差额。[测量脚本](measure.py)

`functional/checks.json` 保存六档的功能与路径结果，`measurements/pairs.csv` 保存每档的原始周期、计数与配对差额，每项作业的 `m5out/roi-stats.txt` 保存 ROI 统计。本例测量预热后的重复对齐复制，之前的 `printf` 实验在最外层格式化函数设置调用门；两个实验采用不同的跨域边界。
