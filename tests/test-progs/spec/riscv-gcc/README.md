# riscv-gcc

[公共说明](../README.md) | [gem5 SE 配置](../../../../configs/spec/README.md)

SPEC CPU2006 `403.gcc`：C 编译器，编译预处理后的 C 输入并生成汇编输出。

三种规模分别使用 `data/test/`、`data/train/`、`data/ref/`；公共输入位于
`data/all/`。调用和比较规则以 [workload.json](workload.json) 为准。

## 输入与调用

| `input` | 调用序号 | 程序参数 | 标准输入 | 标准输出 |
| --- | ---: | --- | --- | --- |
| `test` | 1 | `cccp.i -o cccp.s` | — | `cccp.out` |
| `train` | 1 | `integrate.i -o integrate.s` | — | `integrate.out` |
| `ref` | 1 | `166.i -o 166.s` | — | `166.out` |
| `ref` | 2 | `200.i -o 200.s` | — | `200.out` |
| `ref` | 3 | `c-typeck.i -o c-typeck.s` | — | `c-typeck.out` |
| `ref` | 4 | `cp-decl.i -o cp-decl.s` | — | `cp-decl.out` |
| `ref` | 5 | `expr.i -o expr.s` | — | `expr.out` |
| `ref` | 6 | `expr2.i -o expr2.s` | — | `expr2.out` |
| `ref` | 7 | `g23.i -o g23.s` | — | `g23.out` |
| `ref` | 8 | `s04.i -o s04.s` | — | `s04.out` |
| `ref` | 9 | `scilab.i -o scilab.s` | — | `scilab.out` |

## 输出比较

调用序号与上表对应。参数为空时使用 specdiff 默认比较，不额外放宽容差。

| `input` | 调用序号 | 比较输出 | specdiff 参数 |
| --- | ---: | --- | --- |
| `test` | 1 | `cccp.s` | 默认比较 |
| `train` | 1 | `integrate.s` | 默认比较 |
| `ref` | 1 | `166.s` | 默认比较 |
| `ref` | 2 | `200.s` | 默认比较 |
| `ref` | 3 | `c-typeck.s` | 默认比较 |
| `ref` | 4 | `cp-decl.s` | 默认比较 |
| `ref` | 5 | `expr.s` | 默认比较 |
| `ref` | 6 | `expr2.s` | 默认比较 |
| `ref` | 7 | `g23.s` | 默认比较 |
| `ref` | 8 | `s04.s` | 默认比较 |
| `ref` | 9 | `scilab.s` | 默认比较 |

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
make spec06-test TEST=riscv-gcc input=test \
  config=riscv_se_v5_full.py
make spec06-clean TEST=riscv-gcc
```

`train/ref` 默认完整运行；`SMOKE=1` 只检查启动与进展，不比较完整输出。
依赖、资产准备、产物目录及结果状态见[公共说明](../README.md)。
多配置与 `all` 用法见[公共说明](../README.md#多配置运行)。
