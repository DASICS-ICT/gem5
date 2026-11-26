# SPDX-License-Identifier: BSD-3-Clause
"""Measure the same aligned glibc memcpy behind two v5_full DASICS gates."""

import argparse
import csv
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Use the same SE configuration, ROI statistics parser and timing conventions
# as the paired glibc printf experiment.
sys.path.insert(0, str(HERE.with_name("riscv-dasics-printf")))
import measure_roi as roi

LENGTHS = (1, 2, 15, 16, 64, 4096)
PC_NAMES = (
    "gate_call",
    "b_memcpy",
    "b_wordcopy_fwd_aligned",
    "b_wordcopy_fwd_dest_aligned",
    "gate_return",
    "roi_begin",
    "roi_end",
)


def addresses(elf):
    nm = os.environ.get("CROSS_COMPILE", "riscv64-linux-gnu-") + "nm"
    symbols = {}
    for line in subprocess.check_output(
        [nm, "-n", elf], text=True
    ).splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] in PC_NAMES:
            symbols[fields[2]] = int(fields[0], 16)
    roi.require(set(symbols) == set(PC_NAMES), f"Missing PC symbols in {elf}")
    return symbols


def simulate(directory, mode, size, calls, elf, pcs):
    directory.mkdir()
    out = directory / "m5out"
    command = [
        roi.REPO / "build/RISCV_DASICS/gem5.opt",
        "--listener-mode=off",
        f"--outdir={out}",
        roi.CONFIG,
        "--work-roi",
        "--workdir",
        directory,
        "--stdout",
        directory / "guest.out",
        "--stderr",
        directory / "guest.err",
    ]
    for name in PC_NAMES:
        command.extend(("--retired-pc", f"{name}={pcs[name]:#x}"))
    command.extend((elf, str(size), str(calls)))
    result = dict(
        mode=mode,
        bytes=size,
        calls=calls,
        warmup=roi.WARMUP,
        elf=elf.name,
        status="FAIL",
    )
    try:
        with (directory / "gem5.log").open("w") as stream:
            subprocess.run(
                command,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=600,
            )
        work = json.loads((out / "roi.json").read_text())
        roi.require(
            work["status"] == "PASS" and work["guest_exit_code"] == 0,
            f"Guest data checks or work interval failed: {directory}",
        )
        for name in ("guest.out", "guest.err"):
            roi.require(
                (directory / name).stat().st_size == 0,
                f"Unexpected output: {directory / name}",
            )
        visits = roi.WARMUP + calls
        expected = dict(
            gate_call=visits,
            b_memcpy=visits,
            gate_return=visits,
            roi_begin=1,
            roi_end=1,
            b_wordcopy_fwd_dest_aligned=0,
            b_wordcopy_fwd_aligned=visits if size >= 16 else 0,
        )
        observed = json.loads((out / "retired-pcs.json").read_text())
        roi.require(
            observed == expected, f"Unexpected retired PCs: {observed}"
        )
        stats = roi.roi_stats(out / "roi-stats.txt")
        ticks = work["end_tick"] - work["start_tick"]
        period = work["clock_period_ticks"]
        roi.require(
            period > 0
            and ticks > 0
            and ticks == stats["simTicks"] == stats[roi.CPU_CYCLES] * period
            and stats[roi.CPU_CYCLES] == work["elapsed_cycles"],
            f"ROI cycles disagree with its tick boundaries: {directory}",
        )
        result.update(
            status="PASS", stats=stats, roi=work, retired_pcs=observed
        )
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        subprocess.SubprocessError,
    ) as exc:
        result.update(error=str(exc))
    roi.write_json(directory / "result.json", result)
    return result


def pair(size, calls, sw, hw):
    counts = {}
    for name, key, expected in (
        ("instructions", "numInsts", 81),
        ("loads", "numLoadInsts", 24),
        ("stores", "numStoreInsts", 24),
    ):
        left, right = sw[roi.COMMIT + key], hw[roi.COMMIT + key]
        delta = left - right
        roi.require(
            delta == expected * calls,
            f"{size} B, {calls} calls: {key} delta {delta}; expected {expected*calls}",
        )
        counts.update(
            {f"sw_{name}": left, f"hw_{name}": right, f"{name}_saved": delta}
        )
    left, right = sw[roi.CPU_CYCLES], hw[roi.CPU_CYCLES]
    return dict(
        bytes=size,
        calls=calls,
        sw_cycles=left,
        hw_cycles=right,
        sw_cycles_per_call=left / calls,
        hw_cycles_per_call=right / calls,
        saved_cycles_per_call=(left - right) / calls,
        saved_percent=100 * (left - right) / left,
        **counts,
    )


def measure(outdir, short):
    outdir.mkdir(parents=True)
    counts = (4,) if short else roi.COUNTS
    jobs = list(product(LENGTHS, counts, roi.POLICIES))
    elfs = {
        mode: (HERE / "build" / f"{mode}.elf").resolve(strict=True)
        for mode in roi.POLICIES
    }
    symbols = {mode: addresses(elf) for mode, elf in elfs.items()}
    roi.require(symbols["sw"] == symbols["hw"], "Paired marker PCs differ")
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {
            (size, calls, mode): pool.submit(
                simulate,
                outdir / f"{size}B-{mode}-{calls}",
                mode,
                size,
                calls,
                elfs[mode],
                symbols[mode],
            )
            for size, calls, mode in jobs
        }
        results = {job: future.result() for job, future in futures.items()}
    failed = [
        f"{size}B-{mode}-{calls}: {result['error']}"
        for (size, calls, mode), result in results.items()
        if result["status"] != "PASS"
    ]
    if failed:
        raise ValueError("\n".join(failed))
    pairs = [
        pair(
            size,
            calls,
            *(results[size, calls, mode]["stats"] for mode in roi.POLICIES),
        )
        for size, calls in product(LENGTHS, counts)
    ]
    roi.write_json(outdir / "pairs.json", pairs)
    with (outdir / "pairs.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(pairs[0]))
        writer.writeheader()
        writer.writerows(pairs)
    for row in pairs:
        print(
            "{bytes:4d} B {calls:4d} calls: SW {sw_cycles_per_call:.5f} "
            "HW {hw_cycles_per_call:.5f} saved {saved_cycles_per_call:.5f} "
            "cycles/call ({saved_percent:.5f}%)".format(**row),
            flush=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outdir", type=Path, required=True, help="New batch directory"
    )
    parser.add_argument(
        "--short",
        action="store_true",
        help="Measure four calls per size before the formal sweep",
    )
    args = parser.parse_args()
    measure(args.outdir.resolve(), args.short)
