# riscv-soplex

[公共说明](../README.md) | [gem5 SE 配置](../../../../configs/spec/README.md)

SPEC CPU2006 `450.soplex`：线性规划，使用单纯形法求解 MPS 问题。

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
