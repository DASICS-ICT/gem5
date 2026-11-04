# riscv-dealii

[公共说明](../README.md) | [gem5 SE 配置](../../../../configs/spec/README.md)

SPEC CPU2006 `447.dealII`：有限元计算，求解偏微分方程并输出网格与数值结果。

三种规模分别使用 `data/test/`、`data/train/`、`data/ref/`；公共输入位于
`data/all/`。调用和比较规则以 [workload.json](workload.json) 为准。

## 输入与调用

| `input` | 调用序号 | 程序参数 | 标准输入 | 标准输出 |
| --- | ---: | --- | --- | --- |
| `test` | 1 | `8` | — | `log` |
| `train` | 1 | `10` | — | `log` |
| `ref` | 1 | `23` | — | `log` |

## 输出比较

调用序号与上表对应。参数为空时使用 specdiff 默认比较，不额外放宽容差。

| `input` | 调用序号 | 比较输出 | specdiff 参数 |
| --- | ---: | --- | --- |
| `test` | 1 | `grid-0.eps`<br>`grid-1.eps`<br>`grid-2.eps`<br>`grid-3.eps`<br>`grid-4.eps`<br>`grid-5.eps`<br>`grid-6.eps`<br>`grid-7.eps`<br>`grid-8.eps`<br>`log`<br>`solution-0.gmv`<br>`solution-1.gmv`<br>`solution-2.gmv`<br>`solution-3.gmv`<br>`solution-4.gmv`<br>`solution-5.gmv`<br>`solution-6.gmv`<br>`solution-7.gmv`<br>`solution-8.gmv` | `--abstol 1e-7` |
| `train` | 1 | `grid-0.eps`<br>`grid-1.eps`<br>`grid-10.eps`<br>`grid-2.eps`<br>`grid-3.eps`<br>`grid-4.eps`<br>`grid-5.eps`<br>`grid-6.eps`<br>`grid-7.eps`<br>`grid-8.eps`<br>`grid-9.eps`<br>`log`<br>`solution-0.gmv`<br>`solution-1.gmv`<br>`solution-10.gmv`<br>`solution-2.gmv`<br>`solution-3.gmv`<br>`solution-4.gmv`<br>`solution-5.gmv`<br>`solution-6.gmv`<br>`solution-7.gmv`<br>`solution-8.gmv`<br>`solution-9.gmv` | `--abstol 1e-7` |
| `ref` | 1 | `grid-0.eps`<br>`grid-1.eps`<br>`grid-10.eps`<br>`grid-11.eps`<br>`grid-12.eps`<br>`grid-13.eps`<br>`grid-14.eps`<br>`grid-15.eps`<br>`grid-16.eps`<br>`grid-17.eps`<br>`grid-18.eps`<br>`grid-19.eps`<br>`grid-2.eps`<br>`grid-20.eps`<br>`grid-21.eps`<br>`grid-22.eps`<br>`grid-23.eps`<br>`grid-3.eps`<br>`grid-4.eps`<br>`grid-5.eps`<br>`grid-6.eps`<br>`grid-7.eps`<br>`grid-8.eps`<br>`grid-9.eps`<br>`log`<br>`solution-0.gmv`<br>`solution-1.gmv`<br>`solution-10.gmv`<br>`solution-11.gmv`<br>`solution-12.gmv`<br>`solution-13.gmv`<br>`solution-14.gmv`<br>`solution-15.gmv`<br>`solution-16.gmv`<br>`solution-17.gmv`<br>`solution-18.gmv`<br>`solution-19.gmv`<br>`solution-2.gmv`<br>`solution-20.gmv`<br>`solution-21.gmv`<br>`solution-22.gmv`<br>`solution-23.gmv`<br>`solution-3.gmv`<br>`solution-4.gmv`<br>`solution-5.gmv`<br>`solution-6.gmv`<br>`solution-7.gmv`<br>`solution-8.gmv`<br>`solution-9.gmv` | `--abstol 1e-7` |

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
make spec06-test TEST=riscv-dealii input=test \
  config=riscv_se_v5_full.py
make spec06-clean TEST=riscv-dealii
```

`train/ref` 默认完整运行；`SMOKE=1` 只检查启动与进展，不比较完整输出。
依赖、资产准备、产物目录及结果状态见[公共说明](../README.md)。
多配置与 `all` 用法见[公共说明](../README.md#多配置运行)。
