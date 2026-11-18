#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

"""Measure vector protection on the same DASICS scalar gate within each ABI."""

import argparse
import configparser
import os
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from itertools import product
from pathlib import Path

import measure

ABIS = ("standard", "variant")
MODES = [f"{abi}_{policy}" for abi, policy in product(ABIS, ("ref", "guard"))]
CHECK_MARKER = "[OK] DASICS register protection: vector ABI check"
CPU = "system.cpu."
CYCLES = CPU + "numCycles"
INSTS = CPU + "commitStats0.numInsts"
OPS = CPU + "commitStats0.numOps"


def check_vlen(directory, expected):
    config = configparser.ConfigParser(interpolation=None)
    with (directory / "config.ini").open() as stream:
        config.read_file(stream)
    vlen = config.getint("system.cpu.isa", "vlen")
    measure.require(vlen == expected, f"Expected VLEN={expected}, got {vlen}")
    return vlen


def functional_check(args, vlen, abi):
    directory = args.outdir / f"vlen-{vlen}" / f"check-{abi}"
    directory.mkdir()
    command = [
        str(measure.REPO / "build/RISCV_DASICS/gem5.opt"),
        "--listener-mode=off",
        f"--outdir={directory}",
        str(measure.REPO / "configs/dasics/riscv_dasics_o3_v5_full.py"),
        str(measure.build_dir(vlen) / f"vector-check-{abi}.elf"),
        "--vlen",
        str(vlen),
    ]
    result = measure.run_process(directory, command, args.timeout)
    result.update(abi=abi, vlen=vlen, status="FAIL")
    try:
        if result["timed_out"]:
            result["status"] = "TIMEOUT"
        measure.require(result["process_exit_code"] == 0, "Guest failed")
        lines = (directory / "run.log").read_text().splitlines()
        measure.require(CHECK_MARKER in lines, "Missing vector check marker")
        measure.require(
            any(
                line.startswith("Exiting @ tick ")
                and line.endswith(" because semi:ADP_Stopped_ApplicationExit.")
                for line in lines
            ),
            "Missing semihosting exit",
        )
        check_vlen(directory, vlen)
        result["status"] = "PASS"
    except (OSError, ValueError, configparser.Error) as error:
        result.setdefault("error", str(error))
    measure.write_json(directory / "result.json", result)
    print(f"VLEN={vlen} check-{abi}: {result['status']}", flush=True)
    return result


def timed_job(args, job):
    result = measure.run_job(args, job)
    directory = Path(result["output_dir"])
    if result["status"] == "PASS":
        try:
            check_vlen(directory, job["vlen"])
        except (OSError, ValueError, configparser.Error) as error:
            result.update(status="FAIL", error=str(error))
        measure.write_json(directory / "result.json", result)
    print(
        f"VLEN={job['vlen']} {result['name']}: {result['status']}", flush=True
    )
    return result


def summarize(vlen, results):
    indexed = {row["name"]: row for row in results if row["vlen"] == vlen}
    summary = []
    for abi in ABIS:
        costs = {}
        counts = {INSTS: set(), OPS: set()}
        pairs = []
        for body, n in product(measure.WORKLOADS, measure.ITERATIONS):
            ref, guard = (
                indexed[f"{abi}_{policy}-{body}-{n}"]
                for policy in ("ref", "guard")
            )
            row = dict(
                vlen=vlen, abi=abi, workload=body, iterations=n, measured=False
            )
            if ref["status"] == guard["status"] == "PASS":
                before, after = ref["statistics"], guard["statistics"]
                delta = Fraction(after[CYCLES] - before[CYCLES], n)
                costs[body, n] = delta
                row.update(
                    measured=True,
                    ref_cycles_per_call=before[CYCLES] / n,
                    guard_cycles_per_call=after[CYCLES] / n,
                    increment_cycles_per_call=float(delta),
                    ref_l1d_misses=before[CPU + "dcache.demandMisses::total"],
                    guard_l1d_misses=after[CPU + "dcache.demandMisses::total"],
                    ref_sq_forwards=before[CPU + "lsq0.forwLoads"],
                    guard_sq_forwards=after[CPU + "lsq0.forwLoads"],
                )
                for key, label in ((INSTS, "instructions"), (OPS, "ops")):
                    diff = Fraction(after[key] - before[key], n)
                    counts[key].add(diff)
                    row[f"extra_{label}_per_call"] = float(diff)
            pairs.append(row)
        # An identical gate retires the same added work on every invocation.
        counts_ok = len(costs) == len(pairs) and all(
            len(values) == 1
            and next(iter(values)) > 0
            and next(iter(values)).denominator == 1
            for values in counts.values()
        )
        for row in pairs:
            short, long = (
                costs.get((row["workload"], n)) for n in measure.ITERATIONS
            )
            drift = None
            if short is not None and long is not None:
                if long:
                    drift = abs(short - long) / abs(long)
                elif short == 0:
                    drift = Fraction(0)
            converged = drift is not None and drift <= Fraction(1, 100)
            row.update(
                increment_drift_percent=(
                    float(drift * 100) if drift is not None else None
                ),
                convergence="PASS" if converged else "FAIL",
                work_validation="PASS" if counts_ok else "FAIL",
                status=(
                    "PASS"
                    if row["measured"] and counts_ok and converged
                    else "FAIL"
                ),
            )
        summary.extend(pairs)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--jobs", type=int, choices=range(1, 9), default=8)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--vlen",
        nargs="+",
        type=int,
        choices=(128, 256, 512, 1024),
        default=[128],
        help="Vector register widths in bits",
    )
    args = parser.parse_args()
    if len(set(args.vlen)) != len(args.vlen):
        parser.error("Each vector length must be specified once")
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    args.outdir = args.outdir.resolve()
    if args.outdir.exists():
        parser.error("Choose a fresh output directory")
    jobs = [
        dict(vlen=vlen, mode=mode, workload=body, iterations=n)
        for vlen, mode, body, n in product(
            args.vlen, MODES, measure.WORKLOADS, measure.ITERATIONS
        )
    ]
    gem5 = measure.REPO / "build/RISCV_DASICS/gem5.opt"
    if not os.access(gem5, os.X_OK):
        parser.error(f"Missing executable: {gem5}")
    probes = list(product(args.vlen, ABIS))
    elfs = [measure.build_dir(v) / f"vector-check-{a}.elf" for v, a in probes]
    elfs.extend(
        measure.build_dir(j["vlen"]) / "roi" / f"{measure.job_name(j)}.elf"
        for j in jobs
    )
    for path in elfs:
        if not path.is_file():
            parser.error(f"Missing input: {path}")
    args.outdir.mkdir(parents=True)
    for vlen in args.vlen:
        (args.outdir / f"vlen-{vlen}").mkdir()
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        checks = list(
            executor.map(lambda p: functional_check(args, *p), probes)
        )
        if not all(c["status"] == "PASS" for c in checks):
            measure.write_json(
                args.outdir / "summary.json",
                dict(status="FAIL", functional=checks),
            )
            return 124 if any(c["timed_out"] for c in checks) else 1
        results = list(executor.map(lambda j: timed_job(args, j), jobs))
    measure.write_json(args.outdir / "results.json", results)
    summary = [row for v in args.vlen for row in summarize(v, results)]
    passed = all(row["status"] == "PASS" for row in summary)
    measure.write_json(
        args.outdir / "summary.json",
        dict(
            status="PASS" if passed else "FAIL",
            functional=checks,
            comparisons=summary,
        ),
    )
    fields = [
        "vlen",
        "abi",
        "workload",
        "iterations",
        "measured",
        "ref_cycles_per_call",
        "guard_cycles_per_call",
        "increment_cycles_per_call",
        "extra_instructions_per_call",
        "extra_ops_per_call",
        "ref_l1d_misses",
        "guard_l1d_misses",
        "ref_sq_forwards",
        "guard_sq_forwards",
        "increment_drift_percent",
        "convergence",
        "work_validation",
        "status",
    ]
    measure.write_csv(args.outdir / "summary.csv", summary, fields)
    for row in summary:
        name = (
            f"VLEN={row['vlen']} {row['abi']} {row['workload']} "
            f"N={row['iterations']}"
        )
        if row["measured"]:
            print(
                f"{name}: {row['ref_cycles_per_call']:.4f} -> "
                f"{row['guard_cycles_per_call']:.4f}, "
                f"delta {row['increment_cycles_per_call']:.4f} cycles/call "
                f"[{row['status']}]"
            )
        else:
            print(f"{name}: missing valid pair")
    print(f"Evidence: {args.outdir}")
    print("\033[1;32m[OK]\033[0m" if passed else "\033[1;31m[FAIL]\033[0m")
    return 0 if passed else 124 if any(r["timed_out"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
