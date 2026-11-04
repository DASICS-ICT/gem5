# riscv-bwaves

[公共说明](../README.md) | [gem5 SE 配置](../../../../configs/spec/README.md)

SPEC CPU2006 `410.bwaves`：计算流体力学，求解三维可压缩流动。

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
