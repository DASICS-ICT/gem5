# riscv-h264ref

[公共说明](../README.md) | [gem5 SE 配置](../../../../configs/spec/README.md)

SPEC CPU2006 `464.h264ref`：H.264 视频编码，按配置文件处理输入序列。

三种规模分别使用 `data/test/`、`data/train/`、`data/ref/`；公共输入位于
`data/all/`。调用和比较规则以 [workload.json](workload.json) 为准。

## 输入与调用

| `input` | 调用序号 | 程序参数 | 标准输入 | 标准输出 |
| --- | ---: | --- | --- | --- |
| `test` | 1 | `-d foreman_test_encoder_baseline.cfg` | — | `foreman_test_baseline_encodelog.out` |
| `train` | 1 | `-d foreman_train_encoder_baseline.cfg` | — | `foreman_train_baseline_encodelog.out` |
| `ref` | 1 | `-d foreman_ref_encoder_baseline.cfg` | — | `foreman_ref_baseline_encodelog.out` |
| `ref` | 2 | `-d foreman_ref_encoder_main.cfg` | — | `foreman_ref_main_encodelog.out` |
| `ref` | 3 | `-d sss_encoder_main.cfg` | — | `sss_main_encodelog.out` |

## 输出比较

调用序号与上表对应。参数为空时使用 specdiff 默认比较，不额外放宽容差。

| `input` | 调用序号 | 比较输出 | specdiff 参数 |
| --- | ---: | --- | --- |
| `test` | 1 | `foreman_test_baseline_encodelog.out` | `--cw --floatcompare` |
| `test` | 1 | `foreman_test_baseline_leakybucketparam.cfg` | `--cw --floatcompare --binary` |
| `train` | 1 | `foreman_train_baseline_encodelog.out` | `--cw --floatcompare` |
| `train` | 1 | `foreman_train_baseline_leakybucketparam.cfg` | `--cw --floatcompare --binary` |
| `ref` | 1 | `foreman_ref_baseline_encodelog.out` | `--cw --floatcompare` |
| `ref` | 1 | `foreman_ref_baseline_leakybucketparam.cfg` | `--cw --floatcompare --binary` |
| `ref` | 2 | `foreman_ref_main_encodelog.out` | `--cw --floatcompare` |
| `ref` | 2 | `foreman_ref_main_leakybucketparam.cfg` | `--cw --floatcompare --binary` |
| `ref` | 3 | `sss_main_encodelog.out` | `--cw --floatcompare` |
| `ref` | 3 | `sss_main_leakybucketparam.cfg` | `--cw --floatcompare --binary` |

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
make spec06-test TEST=riscv-h264ref input=test \
  config=riscv_se_v5_full.py
make spec06-clean TEST=riscv-h264ref
```

`train/ref` 默认完整运行；`SMOKE=1` 只检查启动与进展，不比较完整输出。
依赖、资产准备、产物目录及结果状态见[公共说明](../README.md)。
多配置与 `all` 用法见[公共说明](../README.md#多配置运行)。
