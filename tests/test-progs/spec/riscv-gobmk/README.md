# riscv-gobmk

[公共说明](../README.md) | [gem5 SE 配置](../../../../configs/spec/README.md)

SPEC CPU2006 `445.gobmk`：围棋程序，读取 GTP 指令并执行棋局搜索。

三种规模分别使用 `data/test/`、`data/train/`、`data/ref/`；公共输入位于
`data/all/`。调用和比较规则以 [workload.json](workload.json) 为准。

## 输入与调用

| `input` | 调用序号 | 程序参数 | 标准输入 | 标准输出 |
| --- | ---: | --- | --- | --- |
| `test` | 1 | `--quiet --mode gtp` | `capture.tst` | `capture.out` |
| `test` | 2 | `--quiet --mode gtp` | `connect.tst` | `connect.out` |
| `test` | 3 | `--quiet --mode gtp` | `connect_rot.tst` | `connect_rot.out` |
| `test` | 4 | `--quiet --mode gtp` | `connection.tst` | `connection.out` |
| `test` | 5 | `--quiet --mode gtp` | `connection_rot.tst` | `connection_rot.out` |
| `test` | 6 | `--quiet --mode gtp` | `cutstone.tst` | `cutstone.out` |
| `test` | 7 | `--quiet --mode gtp` | `dniwog.tst` | `dniwog.out` |
| `train` | 1 | `--quiet --mode gtp` | `arb.tst` | `arb.out` |
| `train` | 2 | `--quiet --mode gtp` | `arend.tst` | `arend.out` |
| `train` | 3 | `--quiet --mode gtp` | `arion.tst` | `arion.out` |
| `train` | 4 | `--quiet --mode gtp` | `atari_atari.tst` | `atari_atari.out` |
| `train` | 5 | `--quiet --mode gtp` | `blunder.tst` | `blunder.out` |
| `train` | 6 | `--quiet --mode gtp` | `buzco.tst` | `buzco.out` |
| `train` | 7 | `--quiet --mode gtp` | `nicklas2.tst` | `nicklas2.out` |
| `train` | 8 | `--quiet --mode gtp` | `nicklas4.tst` | `nicklas4.out` |
| `ref` | 1 | `--quiet --mode gtp` | `13x13.tst` | `13x13.out` |
| `ref` | 2 | `--quiet --mode gtp` | `nngs.tst` | `nngs.out` |
| `ref` | 3 | `--quiet --mode gtp` | `score2.tst` | `score2.out` |
| `ref` | 4 | `--quiet --mode gtp` | `trevorc.tst` | `trevorc.out` |
| `ref` | 5 | `--quiet --mode gtp` | `trevord.tst` | `trevord.out` |

## 输出比较

调用序号与上表对应。参数为空时使用 specdiff 默认比较，不额外放宽容差。

| `input` | 调用序号 | 比较输出 | specdiff 参数 |
| --- | ---: | --- | --- |
| `test` | 1 | `capture.out` | 默认比较 |
| `test` | 2 | `connect.out` | 默认比较 |
| `test` | 3 | `connect_rot.out` | 默认比较 |
| `test` | 4 | `connection.out` | 默认比较 |
| `test` | 5 | `connection_rot.out` | 默认比较 |
| `test` | 6 | `cutstone.out` | 默认比较 |
| `test` | 7 | `dniwog.out` | 默认比较 |
| `train` | 1 | `arb.out` | 默认比较 |
| `train` | 2 | `arend.out` | 默认比较 |
| `train` | 3 | `arion.out` | 默认比较 |
| `train` | 4 | `atari_atari.out` | 默认比较 |
| `train` | 5 | `blunder.out` | 默认比较 |
| `train` | 6 | `buzco.out` | 默认比较 |
| `train` | 7 | `nicklas2.out` | 默认比较 |
| `train` | 8 | `nicklas4.out` | 默认比较 |
| `ref` | 1 | `13x13.out` | 默认比较 |
| `ref` | 2 | `nngs.out` | 默认比较 |
| `ref` | 3 | `score2.out` | 默认比较 |
| `ref` | 4 | `trevorc.out` | 默认比较 |
| `ref` | 5 | `trevord.out` | 默认比较 |

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
make spec06-test TEST=riscv-gobmk input=test \
  config=riscv_se_v5_full.py
make spec06-clean TEST=riscv-gobmk
```

`train/ref` 默认完整运行；`SMOKE=1` 只检查启动与进展，不比较完整输出。
依赖、资产准备、产物目录及结果状态见[公共说明](../README.md)。
多配置与 `all` 用法见[公共说明](../README.md#多配置运行)。
