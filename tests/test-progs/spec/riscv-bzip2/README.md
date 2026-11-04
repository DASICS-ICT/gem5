# riscv-bzip2

[公共说明](../README.md) | [gem5 SE 配置](../../../../configs/spec/README.md)

SPEC CPU2006 `401.bzip2`：压缩与解压缩，处理程序、图像和文本输入。

三种规模分别使用 `data/test/`、`data/train/`、`data/ref/`；公共输入位于
`data/all/`。调用和比较规则以 [workload.json](workload.json) 为准。

## 输入与调用

| `input` | 调用序号 | 程序参数 | 标准输入 | 标准输出 |
| --- | ---: | --- | --- | --- |
| `test` | 1 | `input.program 5` | — | `input.program.out` |
| `test` | 2 | `dryer.jpg 2` | — | `dryer.jpg.out` |
| `train` | 1 | `input.program 10` | — | `input.program.out` |
| `train` | 2 | `byoudoin.jpg 5` | — | `byoudoin.jpg.out` |
| `train` | 3 | `input.combined 80` | — | `input.combined.out` |
| `ref` | 1 | `input.source 280` | — | `input.source.out` |
| `ref` | 2 | `chicken.jpg 30` | — | `chicken.jpg.out` |
| `ref` | 3 | `liberty.jpg 30` | — | `liberty.jpg.out` |
| `ref` | 4 | `input.program 280` | — | `input.program.out` |
| `ref` | 5 | `text.html 280` | — | `text.html.out` |
| `ref` | 6 | `input.combined 200` | — | `input.combined.out` |

## 输出比较

调用序号与上表对应。参数为空时使用 specdiff 默认比较，不额外放宽容差。

| `input` | 调用序号 | 比较输出 | specdiff 参数 |
| --- | ---: | --- | --- |
| `test` | 2 | `dryer.jpg.out` | 默认比较 |
| `test` | 1 | `input.program.out` | 默认比较 |
| `train` | 2 | `byoudoin.jpg.out` | 默认比较 |
| `train` | 3 | `input.combined.out` | 默认比较 |
| `train` | 1 | `input.program.out` | 默认比较 |
| `ref` | 2 | `chicken.jpg.out` | 默认比较 |
| `ref` | 6 | `input.combined.out` | 默认比较 |
| `ref` | 4 | `input.program.out` | 默认比较 |
| `ref` | 1 | `input.source.out` | 默认比较 |
| `ref` | 3 | `liberty.jpg.out` | 默认比较 |
| `ref` | 5 | `text.html.out` | 默认比较 |

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
make spec06-test TEST=riscv-bzip2 input=test \
  config=riscv_se_v5_full.py
make spec06-clean TEST=riscv-bzip2
```

`train/ref` 默认完整运行；`SMOKE=1` 只检查启动与进展，不比较完整输出。
依赖、资产准备、产物目录及结果状态见[公共说明](../README.md)。
多配置与 `all` 用法见[公共说明](../README.md#多配置运行)。
