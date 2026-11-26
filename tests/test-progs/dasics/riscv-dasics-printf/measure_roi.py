# SPDX-License-Identifier: BSD-3-Clause
"""Measure paired software and hardware register protection on v5_full."""

import argparse
import csv
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path

from check import (
    EXPECTED,
    REPO,
    require,
)

HERE = Path(__file__).resolve().parent
CONFIG = REPO / "configs/spec/riscv_se_dasics_v5_full.py"
WARMUP = 128
POLICIES = ("sw", "hw")
COUNTS = (1024, 4096)
CPU_CYCLES = "system.cpu.numCycles"
COMMIT = "system.cpu.commitStats0."
COMMIT_STATS = ("numInsts", "numLoadInsts", "numStoreInsts")


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def roi_stats(path):
    text = path.read_text()
    require(
        text.count("Begin Simulation Statistics") == 1
        and text.count("End Simulation Statistics") == 1,
        f"Incomplete or ambiguous ROI statistics: {path}",
    )
    keys = {"simTicks", CPU_CYCLES, *(COMMIT + name for name in COMMIT_STATS)}
    stats = {}
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0] in keys:
            require(
                fields[0] not in stats, f"Duplicate statistic: {fields[0]}"
            )
            stats[fields[0]] = int(fields[1])
    require(set(stats) == keys, f"Missing ROI statistics in {path}")
    return stats


def run_one(outdir, mode, count, full=False):
    directory = outdir / f"{mode}-{count}"
    directory.mkdir()
    m5out = directory / "m5out"
    group = "full" if full else "roi"
    elf = HERE / "build" / f"{group}-{mode}.elf"
    nm = os.getenv("CROSS_COMPILE", "riscv64-linux-gnu-") + "nm"
    symbols = {}
    for line in subprocess.check_output(
        [nm, "-n", elf], text=True
    ).splitlines():
        fields = line.split()
        if len(fields) == 3:
            symbols[fields[2]] = fields[0]
    visits = WARMUP + count
    expected = {
        name: visits
        for name in (
            "gate_call",
            "b_printf",
            "b___vfprintf_internal",
            "gate_return",
        )
    }
    expected.update(roi_begin=1, roi_end=1, emit_buffer=1)
    args = [
        REPO / "build/RISCV_DASICS/gem5.opt",
        "--listener-mode=off",
        f"--outdir={m5out}",
        CONFIG,
        "--workdir",
        directory,
        "--stdout",
        directory / "guest.out",
        "--stderr",
        directory / "guest.err",
        "--work-roi",
    ]
    for name in expected:
        args.extend(("--retired-pc", f"{name}=0x{symbols[name]}"))
    args.extend((elf, str(count)))
    with (directory / "gem5.log").open("w") as log:
        subprocess.run(
            args, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600
        )
    require(
        (directory / "guest.out").read_bytes() == EXPECTED * visits,
        f"Incorrect formatted records: {directory}",
    )
    require(
        (directory / "guest.err").stat().st_size == 0,
        f"Unexpected guest stderr: {directory}",
    )
    require(
        json.loads((m5out / "retired-pcs.json").read_text()) == expected,
        f"Incorrect number of complete calls or ROI markers: {directory}",
    )
    roi = json.loads((m5out / "roi.json").read_text())
    require(
        roi["status"] == "PASS" and roi["guest_exit_code"] == 0,
        f"Guest or ROI failed: {directory}",
    )
    stats = roi_stats(m5out / "roi-stats.txt")
    ticks = roi["end_tick"] - roi["start_tick"]
    period = roi["clock_period_ticks"]
    require(
        period > 0
        and ticks > 0
        and ticks == stats["simTicks"]
        and ticks == stats[CPU_CYCLES] * period
        and stats[CPU_CYCLES] == roi["elapsed_cycles"],
        f"CPU cycles disagree with ROI tick boundaries: {directory}",
    )
    result = dict(
        mode=mode,
        elf=elf.name,
        calls=count,
        warmup=WARMUP,
        stats=stats,
        roi=roi,
    )
    write_json(directory / "result.json", result)
    return result


def measure(outdir, counts, full=False):
    outdir.mkdir(parents=True)
    jobs = list(product(counts, POLICIES))
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = [
            pool.submit(run_one, outdir, mode, n, full) for n, mode in jobs
        ]
        results = {job: future.result() for job, future in zip(jobs, futures)}
    pairs = []
    # Software spills, clears and reloads each saved register. Temporaries
    # need only a clear. Hardware uses two PROREGs, one or two CLRs and LEAVE.
    saved_regs, clear_only, hw_ops = (24, 14, 5) if full else (2, 1, 4)
    expected = (3 * saved_regs + clear_only - hw_ops, saved_regs, saved_regs)
    for n in counts:
        sw, hw = (results[n, mode]["stats"] for mode in POLICIES)
        differences = {}
        for name, delta in zip(COMMIT_STATS, expected, strict=True):
            observed = sw[COMMIT + name] - hw[COMMIT + name]
            require(
                observed == n * delta,
                f"{n} calls: {name} delta {observed}, expected {n * delta}",
            )
            differences[name] = observed
        saved = sw[CPU_CYCLES] - hw[CPU_CYCLES]
        pairs.append(
            dict(
                calls=n,
                sw_cycles=sw[CPU_CYCLES],
                hw_cycles=hw[CPU_CYCLES],
                sw_cycles_per_call=sw[CPU_CYCLES] / n,
                hw_cycles_per_call=hw[CPU_CYCLES] / n,
                saved_cycles_per_call=saved / n,
                saved_percent=100 * saved / sw[CPU_CYCLES],
                retired_instructions_saved=differences["numInsts"],
                retired_loads_saved=differences["numLoadInsts"],
                retired_stores_saved=differences["numStoreInsts"],
            )
        )
    write_json(outdir / "pairs.json", pairs)
    with (outdir / "pairs.csv").open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(pairs[0]))
        writer.writeheader()
        writer.writerows(pairs)
    for pair in pairs:
        print(
            "{calls} calls: SW {sw_cycles_per_call:.5f}, "
            "HW {hw_cycles_per_call:.5f}, "
            "saved {saved_cycles_per_call:.5f} cycles/call "
            "({saved_percent:.5f}%)".format(**pair),
            flush=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outdir",
        type=Path,
        required=True,
        help="New directory for this batch",
    )
    parser.add_argument(
        "--short",
        action="store_true",
        help="Validate one short pair before the full batch",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Protect all s/fs registers and clear t0-t6 and ft0-ft6",
    )
    args = parser.parse_args()
    measure(args.outdir.resolve(), (4,) if args.short else COUNTS, args.full)
