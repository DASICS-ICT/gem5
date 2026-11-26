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
