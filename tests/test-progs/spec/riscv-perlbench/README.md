# riscv-perlbench

[公共说明](../README.md) | [gem5 SE 配置](../../../../configs/spec/README.md)

SPEC CPU2006 `400.perlbench`：Perl 解释器，执行字符串、脚本语言及邮件处理负载。

三种规模分别使用 `data/test/`、`data/train/`、`data/ref/`；公共输入位于
`data/all/`。调用和比较规则以 [workload.json](workload.json) 为准。

## 输入与调用

| `input` | 调用序号 | 程序参数 | 标准输入 | 标准输出 |
| --- | ---: | --- | --- | --- |
| `test` | 1 | `-I. -I./lib attrs.pl` | — | `attrs.out` |
| `test` | 2 | `-I. -I./lib gv.pl` | — | `gv.out` |
| `test` | 3 | `-I. -I./lib makerand.pl` | — | `makerand.out` |
| `test` | 4 | `-I. -I./lib pack.pl` | — | `pack.out` |
| `test` | 5 | `-I. -I./lib redef.pl` | — | `redef.out` |
| `test` | 6 | `-I. -I./lib ref.pl` | — | `ref.out` |
| `test` | 7 | `-I. -I./lib regmesg.pl` | — | `regmesg.out` |
| `test` | 8 | `-I. -I./lib test.pl` | — | `test.out` |
| `train` | 1 | `-I./lib diffmail.pl 2 550 15 24 23 100` | — | `diffmail.2.550.15.24.23.100.out` |
| `train` | 2 | `-I./lib perfect.pl b 3` | — | `perfect.b.3.out` |
| `train` | 3 | `-I./lib splitmail.pl 535 13 25 24 1091` | — | `splitmail.535.13.25.24.1091.out` |
| `train` | 4 | `-I. -I./lib scrabbl.pl` | `scrabbl.in` | `scrabbl.out` |
| `train` | 5 | `-I. -I./lib suns.pl` | — | `suns.out` |
| `ref` | 1 | `-I./lib checkspam.pl 2500 5 25 11 150 1 1 1 1` | — | `checkspam.2500.5.25.11.150.1.1.1.1.out` |
| `ref` | 2 | `-I./lib diffmail.pl 4 800 10 17 19 300` | — | `diffmail.4.800.10.17.19.300.out` |
| `ref` | 3 | `-I./lib splitmail.pl 1600 12 26 16 4500` | — | `splitmail.1600.12.26.16.4500.out` |

## 输出比较

调用序号与上表对应。参数为空时使用 specdiff 默认比较，不额外放宽容差。

| `input` | 调用序号 | 比较输出 | specdiff 参数 |
| --- | ---: | --- | --- |
| `test` | 8 | `append.out`<br>`args.out`<br>`arith.out`<br>`array.out`<br>`auto.out`<br>`base_cond.out`<br>`base_pat.out`<br>`base_term.out`<br>`bless.out`<br>`bop.out`<br>`bproto.out`<br>`chars.out`<br>`chop.out`<br>`cmdopt.out`<br>`cmp.out`<br>`comp_term.out`<br>`concat.out`<br>`context.out`<br>`decl.out`<br>`defins.out`<br>`delete.out`<br>`die.out`<br>`do.out`<br>`each.out`<br>`eval.out`<br>`exists_sub.out`<br>`exp.out`<br>`fh.out`<br>`grep.out`<br>`hashwarn.out`<br>`if.out`<br>`inc.out`<br>`index.out`<br>`int.out`<br>`join.out`<br>`length.out`<br>`lex.out`<br>`list.out`<br>`loopctl.out`<br>`lop.out`<br>`method.out`<br>`my.out`<br>`nothr5005.out`<br>`oct.out`<br>`op_cond.out`<br>`op_pat.out`<br>`ord.out`<br>`override.out`<br>`package.out`<br>`pos.out`<br>`push.out`<br>`quotemeta.out`<br>`range.out`<br>`recurse.out`<br>`regexp.out`<br>`regexp_noamp.out`<br>`repeat.out`<br>`reverse.out`<br>`rs.out`<br>`sleep.out`<br>`sort.out`<br>`splice.out`<br>`study.out`<br>`sub_lval.out`<br>`subst.out`<br>`subst_amp.out`<br>`subst_wamp.out`<br>`tr.out`<br>`undef.out`<br>`unshift.out`<br>`vec.out`<br>`wantarray.out` | 默认比较 |
| `test` | 1 | `attrs.out` | 默认比较 |
| `test` | 2 | `gv.out` | 默认比较 |
| `test` | 3 | `makerand.out` | 默认比较 |
| `test` | 4 | `pack.out` | 默认比较 |
| `test` | 5 | `redef.out` | 默认比较 |
| `test` | 6 | `ref.out` | 默认比较 |
| `test` | 7 | `regmesg.out` | 默认比较 |
| `train` | 1 | `diffmail.2.550.15.24.23.100.out` | 默认比较 |
| `train` | 2 | `perfect.b.3.out` | 默认比较 |
| `train` | 4 | `scrabbl.out` | 默认比较 |
| `train` | 3 | `splitmail.535.13.25.24.1091.out` | 默认比较 |
| `train` | 5 | `suns.out`<br>`validate` | 默认比较 |
| `ref` | 1 | `checkspam.2500.5.25.11.150.1.1.1.1.out` | 默认比较 |
| `ref` | 2 | `diffmail.4.800.10.17.19.300.out` | 默认比较 |
| `ref` | 3 | `splitmail.1600.12.26.16.4500.out` | 默认比较 |

`test` 的第 8 次调用 `test.pl` 依赖 `fork/waitpid`，当前单 hart gem5 SE
入口将该调用及其关联比较标为 `[UNSUPPORTED]`，整体返回 `77`；其余调用继续。
QEMU 路径执行完整清单。

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
make spec06-test TEST=riscv-perlbench input=test \
  config=riscv_se_v5_full.py
make spec06-clean TEST=riscv-perlbench
```

`train/ref` 默认完整运行；`SMOKE=1` 只检查启动与进展，不比较完整输出。
依赖、资产准备、产物目录及结果状态见[公共说明](../README.md)。
多配置与 `all` 用法见[公共说明](../README.md#多配置运行)。
