# riscv-cactusadm

[公共说明](../README.md) | [gem5 SE 配置](../../../../configs/spec/README.md)

SPEC CPU2006 `436.cactusADM`：数值相对论，按参数文件演化引力场。

三种规模分别使用 `data/test/`、`data/train/`、`data/ref/`；公共输入位于
`data/all/`。调用和比较规则以 [workload.json](workload.json) 为准。

源码需要应用 [PUGH 兼容补丁](../patches/436-cactusadm-pughutils.patch)，消除
日志格式化时 `sprintf` 源与目标缓冲区重叠的未定义行为；比较容差保持原样。
应用命令见[资产准备](../README.md#本地资产)，已应用的本地源码不重复执行。

## 输入与调用

| `input` | 调用序号 | 程序参数 | 标准输入 | 标准输出 |
| --- | ---: | --- | --- | --- |
| `test` | 1 | `benchADM.par` | — | `benchADM.out` |
| `train` | 1 | `benchADM.par` | — | `benchADM.out` |
| `ref` | 1 | `benchADM.par` | — | `benchADM.out` |

## 输出比较

调用序号与上表对应。参数为空时使用 specdiff 默认比较，不额外放宽容差。

| `input` | 调用序号 | 比较输出 | specdiff 参数 |
| --- | ---: | --- | --- |
| `test` | 1 | `benchADM.out` | `--floatcompare` |
| `train` | 1 | `benchADM.out` | `--floatcompare` |
| `ref` | 1 | `benchADM.out` | `--floatcompare` |

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
make spec06-test TEST=riscv-cactusadm input=test \
  config=riscv_se_v5_full.py
make spec06-clean TEST=riscv-cactusadm
```

`train/ref` 默认完整运行；`SMOKE=1` 只检查启动与进展，不比较完整输出。
依赖、资产准备、产物目录及结果状态见[公共说明](../README.md)。
多配置与 `all` 用法见[公共说明](../README.md#多配置运行)。
