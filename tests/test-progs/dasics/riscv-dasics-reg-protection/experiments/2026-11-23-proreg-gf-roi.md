# 仅 G 与 G+F 调用门的配对测量

2026-11-23 · gem5 `v5_full` O3 · 单 hart · RV64 · 2 GHz · Sv39

在整数寄存器已由硬件保护、B 不改写 `fs0–fs11` 的条件下，再用硬件保护这 12 个浮点寄存器，4096 次连续调用中，空函数每次额外节省 **34.9998 周期**，固定计算每次额外节省 **34.9995 周期**。相对仅 G 门，整次调用的平均耗时分别下降 **11.78%** 和 **10.94%**。

## 对照与计时

两组均使用 `PROREG.G.I 0xfff` 保护 `s0–s11`。仅 G 门（`proreg`）用软件保存、清零和恢复 `fs0–fs11`；G+F 门（`proreg_gf`）加入 `PROREG.F.I 0xfff`，返回时两类寄存器共用原来的一条 `LEAVE`。三组 LibBound、B 的独立栈、私有 `fcsr` 及 `fa0` 的参数和返回约定相同。[调用门汇编](../src/gate.inc)

空函数返回整数零和浮点零。固定计算处理四条整数和双精度浮点记录，返回 14 和 20.0。每个作业在同一调用点预热 128 次，再用一对 `m5_work_begin/end` 测量 N 次连续调用。ROI 包含调用循环、入口门、B 和返回门；启动、预热和最终自检在计时区间之外。四对 ELF 均已核对 B 的机器码、ROI 端点、调用循环、门入口及数据区地址。[计时负载](../src/riscv-dasics-reg-roi.S) · [平台与 ROI 配置](../../../../../configs/dasics/riscv_dasics_reg_protection_o3_v5_full.py)

## 配对结果

每次额外节省的周期 =（仅 G 门的 ROI 总周期 − G+F 门的 ROI 总周期）/ N。

| B 负载 | 调用次数 N | 仅 G 总周期 | G+F 总周期 | 仅 G 周期/次 | G+F 周期/次 | 额外节省周期/次 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 空函数 | 1024 | 304161 | 268322 | 297.0322 | 262.0332 | 34.9990 |
| 空函数 | 4096 | 1216545 | 1073186 | 297.0081 | 262.0083 | 34.9998 |
| 固定计算 | 1024 | 327725 | 291887 | 320.0439 | 285.0459 | 34.9980 |
| 固定计算 | 4096 | 1310765 | 1167407 | 320.0110 | 285.0115 | 34.9995 |

四组配对都实测到每次少提交 **35 条指令**。仅 G 门的 12 条浮点保存、12 条清零、12 条恢复，被 G+F 门的一条额外保护指令取代。提交统计中每次也分别少 12 条加载和 12 条存储。8 个作业的客体自检和仿真均通过，ROI 的 tick 差与 `simTicks` 一致，除以 500 ticks/周期后等于 `system.cpu.numCycles`。以 4096 次的节省量为参照，两个批长间的偏差分别为 0.0021% 和 0.0042%，均满足预设的 1% 阈值。[计数与收敛校验](../measure.py)

本批全部 ROI 的 L1D 需求缺失计数均为零。两种计时负载都只使用调用者保存寄存器，因此表中结果描述的是热态下 B 保持 `fs0–fs11` 原映射时的收益。B 改写这些寄存器后的额外收益需要单独测量。

## 复现与原始数据

在仓库根目录运行，使用 DASICS 版 `gem5.opt`。

```bash
test_dir=tests/test-progs/dasics/riscv-dasics-reg-protection
make -j8 -C "$test_dir/src" proreg-gf-roi
python3 "$test_dir/measure.py" --comparison proreg-gf --jobs 8 \
    --outdir "$test_dir/build/runs/proreg-gf-roi-$(date +%Y%m%d-%H%M%S)"
```

本批在 `cmy-zgclab-eda` 并行执行，原始数据保存在测试目录的 `build/runs/20261123-proreg-gf-roi-01/`。其中 `batch.log` 包含 ELF 核对和批次退出码，`measurements/summary.csv` 记录四组配对，`measurements/results.csv` 记录八个作业的计数。每个作业另有 `roi.json`、`roi-stats.txt` 和 `config.ini`。复现命令会在新批次目录生成同名测量文件。
