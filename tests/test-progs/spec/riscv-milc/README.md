# riscv-milc

[公共说明](../README.md) | [gem5 SE 配置](../../../../configs/spec/README.md)

SPEC CPU2006 `433.milc`：格点量子色动力学计算。

三种规模分别使用 `data/test/`、`data/train/`、`data/ref/`；公共输入位于
`data/all/`。调用和比较规则以 [workload.json](workload.json) 为准。

## 输入与调用

| `input` | 调用序号 | 程序参数 | 标准输入 | 标准输出 |
| --- | ---: | --- | --- | --- |
| `test` | 1 | 无参数 | `su3imp.in` | `su3imp.out` |
| `train` | 1 | 无参数 | `su3imp.in` | `su3imp.out` |
| `ref` | 1 | 无参数 | `su3imp.in` | `su3imp.out` |

## 输出比较

调用序号与上表对应。参数为空时使用 specdiff 默认比较，不额外放宽容差。

| `input` | 调用序号 | 比较输出 | specdiff 参数 |
| --- | ---: | --- | --- |
| `test` | 1 | `su3imp.out` | `--abstol 2e-7 --reltol 0.0001` |
| `train` | 1 | `su3imp.out` | `--abstol 2e-7 --reltol 0.0001` |
| `ref` | 1 | `su3imp.out` | `--abstol 2e-7 --reltol 0.0001` |

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
make spec06-test TEST=riscv-milc input=test \
  config=riscv_se_v5_full.py
make spec06-clean TEST=riscv-milc
```

`train/ref` 默认完整运行；`SMOKE=1` 只检查启动与进展，不比较完整输出。
依赖、资产准备、产物目录及结果状态见[公共说明](../README.md)。
多配置与 `all` 用法见[公共说明](../README.md#多配置运行)。
