#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

"""Measure paired register-protection costs on the v5_full platform."""

import argparse
import csv
import json
import os
import shlex
import subprocess
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from datetime import (
    datetime,
    timezone,
)
from fractions import Fraction
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
MODES = ("boundary", "save", "restore", "software")
# Marginal costs use matched modes; "restore" performs both save and restore.
CONTRASTS = (
    ("save", "save", "boundary", 24),
    ("clear", "software", "restore", 55),
    ("restore", "restore", "save", 24),
)
WORKLOADS = ("empty", "compute")
ITERATIONS = (1024, 4096)
CLOBBER_COUNTS = (0, 1, 6, 12)
WARMUP = 128
MARKER = "[OK] DASICS register protection: roi"
STAT_KEYS = (
    "simTicks",
    "system.cpu.numCycles",
    "system.cpu.commitStats0.numInsts",
    "system.cpu.commitStats0.numOps",
    "system.cpu.commitStats0.numLoadInsts",
    "system.cpu.commitStats0.numStoreInsts",
    "system.cpu.lsq0.forwLoads",
    "system.cpu.lsq0.rescheduledLoads",
    "system.cpu.lsq0.blockedByCache",
    "system.cpu.dcache.demandHits::total",
    "system.cpu.dcache.demandMisses::total",
    "system.cpu.dcache.demandAccesses::total",
    "system.cpu.dcache.demandMissLatency::total",
    "system.cpu.dcache.demandMshrHits::total",
    "system.cpu.dcache.demandMshrMisses::total",
)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def write_csv(path, rows, fields):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_stats(path):
    text = path.read_text()
    require(
        text.count("Begin Simulation Statistics") == 1
        and text.count("End Simulation Statistics") == 1,
        "Expected one complete ROI statistics block",
    )
    stats = {}
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0] in STAT_KEYS:
            key = fields[0]
            require(key not in stats, f"Duplicate ROI statistic: {key}")
            require(len(fields) >= 2, f"Missing ROI statistic value: {key}")
            value = int(fields[1])
            require(value >= 0, f"Negative ROI statistic: {key}")
            stats[key] = value
    # Classic-cache totals suppress zero entries. Reconcile misses against
    # the reported accesses and hits before accepting an omitted miss total.
    prefix = "system.cpu.dcache."
    hits, misses, accesses = (
        prefix + f"demand{field}::total"
        for field in ("Hits", "Misses", "Accesses")
    )
    require(accesses in stats, "Missing L1D demand access total")
    if stats.get(hits, 0) + stats.get(misses, 0) != stats[accesses]:
        raise ValueError("Inconsistent L1D access, hit and miss totals")
    for key in (hits, misses):
        stats.setdefault(key, 0)
    for field in ("MissLatency", "MshrHits", "MshrMisses"):
        stats.setdefault(prefix + f"demand{field}::total", 0)
    require(set(stats) == set(STAT_KEYS), "Missing required ROI statistics")
    return stats


def validate(directory, job):
    require(
        MARKER in (directory / "run.log").read_text().splitlines(),
        "The guest success marker is missing",
    )
    roi = json.loads((directory / "roi.json").read_text())
    require(isinstance(roi, dict), "ROI metadata must be a JSON object")
    expected = dict(
        job,
        status="PASS",
        warmup=WARMUP,
        guest_exit_code=0,
        exit_cause="semi:ADP_Stopped_ApplicationExit",
    )
    for key, value in expected.items():
        require(
            roi.get(key) == value,
            f"ROI {key}: expected {value!r}, got {roi.get(key)!r}",
        )
    for key in ("start_tick", "end_tick", "clock_period_ticks"):
        require(type(roi.get(key)) is int, f"Invalid ROI {key}")
    start, end = roi["start_tick"], roi["end_tick"]
    period = roi["clock_period_ticks"]
    require(start >= 0 and end > start and period > 0, "Invalid ROI interval")
    cycles = Fraction(end - start, period)
    require(
        type(roi.get("elapsed_cycles")) in (int, float)
        and Fraction(str(roi["elapsed_cycles"])) == cycles,
        "ROI elapsed_cycles does not match the tick interval",
    )
    stats = read_stats(directory / "roi-stats.txt")
    require(stats["simTicks"] == end - start, "ROI simTicks mismatch")
    require(
        stats["system.cpu.numCycles"] == cycles,
        "ROI numCycles does not match elapsed_cycles",
    )
    require(
        stats["system.cpu.commitStats0.numInsts"] > 0
        and stats["system.cpu.commitStats0.numOps"]
        >= stats["system.cpu.commitStats0.numInsts"],
        "Invalid ROI committed instruction or operation counts",
    )
    return roi, stats


def job_name(job):
    name = f"{job['mode']}-{job['workload']}-{job['iterations']}"
    if "clobber_count" in job:
        name += f"-clobber{job['clobber_count']}"
    return name


def run_process(directory, command, timeout):
    result = dict(
        command=command,
        output_dir=str(directory),
        started=timestamp(),
        process_exit_code=None,
        timed_out=False,
    )
    with (directory / "run.log").open("w") as log:
        log.write(f"Started: {result['started']}\n")
        log.write(f"Command: {shlex.join(command)}\n")
        log.flush()
        try:
            with subprocess.Popen(
                command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT
            ) as process:
                try:
                    result["process_exit_code"] = process.wait(timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    result["process_exit_code"] = process.wait()
                    result["timed_out"] = True
                    result["error"] = f"Timeout after {timeout} seconds"
        except OSError as error:
            result["error"] = f"Launch failed: {error}"
        result["finished"] = timestamp()
        log.write(f"Finished: {result['finished']}\n")
        log.write(f"Process exit code: {result['process_exit_code']}\n")
        if "error" in result:
            log.write(result["error"] + "\n")
    return result


def build_dir(vlen=128):
    build = TEST_DIR / "build"
    return build if vlen == 128 else build / f"vlen-{vlen}"


def run_job(args, job, *, debug_flags=None):
    name = job_name(job)
    root = args.outdir
    if "vlen" in job:
        root = root / f"vlen-{job['vlen']}"
    directory = root / name
    directory.mkdir()
    command = [
        str(REPO / "build/RISCV_DASICS/gem5.opt"),
        "--listener-mode=off",
        f"--outdir={directory}",
    ]
    if debug_flags:
        command.extend(
            [f"--debug-flags={debug_flags}", "--debug-file=debug.trace.gz"]
        )
    command += [
        str(REPO / "configs/dasics/riscv_dasics_reg_protection_o3_v5_full.py"),
        str(build_dir(job.get("vlen", 128)) / "roi" / f"{name}.elf"),
        "--mode",
        job["mode"],
        "--workload",
        job["workload"],
        "--iterations",
        str(job["iterations"]),
    ]
    if "vlen" in job:
        command.extend(["--vlen", str(job["vlen"])])
    if "clobber_count" in job:
        command.extend(["--clobber-count", str(job["clobber_count"])])
    result = dict(job, name=name, warmup=WARMUP, status="FAIL")
    result.update(run_process(directory, command, args.timeout))

    if result["timed_out"]:
        result["status"] = "TIMEOUT"
    elif result["process_exit_code"] != 0:
        result.setdefault("error", "gem5 exited with a nonzero status")
    else:
        try:
            roi, stats = validate(directory, job)
            result.update(status="PASS", roi=roi, statistics=stats)
        except (OSError, ValueError, TypeError) as error:
            result["error"] = str(error)
    write_json(directory / "result.json", result)
    return result


def convergence(increments):
    if len(increments) != 2:
        return None, False
    short, long = increments
    if long == 0:
        return (Fraction(0), True) if short == 0 else (None, False)
    drift = abs(short - long) / abs(long)
    return drift, drift <= Fraction(1, 100)


def summarize(results):
    indexed = {
        (row["mode"], row["workload"], row["iterations"]): row
        for row in results
    }
    rows = []
    for workload in WORKLOADS:
        pairs = []
        increments = []
        for count in ITERATIONS:
            modes = {mode: indexed[mode, workload, count] for mode in MODES}
            pair = dict(workload=workload, iterations=count, status="FAIL")
            if all(row["status"] == "PASS" for row in modes.values()):
                cycles = {
                    mode: Fraction(
                        row["statistics"]["system.cpu.numCycles"], count
                    )
                    for mode, row in modes.items()
                }
                increment = cycles["software"] - cycles["boundary"]
                increments.append(increment)
                pair.update(
                    status="PASS",
                    software_cycles_per_call=float(cycles["software"]),
                    boundary_cycles_per_call=float(cycles["boundary"]),
                    save_only_cycles_per_call=float(cycles["save"]),
                    save_restore_cycles_per_call=float(cycles["restore"]),
                    increment_cycles_per_call=float(increment),
                )
                for label, upper, lower, _ in CONTRASTS:
                    pair[f"{label}_cycles_per_call"] = float(
                        cycles[upper] - cycles[lower]
                    )
            pairs.append(pair)
        drift, converged = convergence(increments)
        for pair in pairs:
            for label, *_ in CONTRASTS:
                key = f"{label}_cycles_per_call"
                pair[f"{label}_absolute_drift"] = (
                    abs(pairs[0][key] - pairs[1][key])
                    if len(increments) == 2
                    else None
                )
            pair.update(
                convergence_reference_iterations=ITERATIONS[-1],
                increment_drift_percent=(
                    float(drift * 100) if drift is not None else None
                ),
                convergence="PASS" if converged else "FAIL",
            )
        rows.extend(pairs)
    return rows


def validate_instruction_deltas(results):
    indexed = {row["name"]: row for row in results}
    comparisons = []
    for count in ITERATIONS:
        for workload in WORKLOADS:
            for _, upper, lower, instructions in CONTRASTS:
                comparisons.append(
                    (
                        f"{upper}-{workload}-{count}",
                        f"{lower}-{workload}-{count}",
                        instructions * count,
                    )
                )
        # The compute and empty bodies retire 56 and 3 instructions per call.
        for mode in MODES:
            comparisons.append(
                (
                    f"{mode}-compute-{count}",
                    f"{mode}-empty-{count}",
                    53 * count,
                )
            )
    checks = []
    for positive, negative, expected in comparisons:
        left, right = indexed[positive], indexed[negative]
        observed = None
        if left["status"] == right["status"] == "PASS":
            key = "system.cpu.commitStats0.numInsts"
            observed = left["statistics"][key] - right["statistics"][key]
        checks.append(
            dict(
                positive=positive,
                negative=negative,
                expected_instruction_delta=expected,
                observed_instruction_delta=observed,
                status="PASS" if observed == expected else "FAIL",
            )
        )
    return checks


def proreg_pairs(results):
    indexed = {(r["workload"], r["iterations"], r["mode"]): r for r in results}
    # Twelve stores, clears, and loads become one PROREG and one LEAVE.
    counters = (
        ("instructions_saved_per_call", "numInsts", 34),
        ("loads_saved_per_call", "numLoadInsts", 12),
        ("stores_saved_per_call", "numStoreInsts", 12),
    )
    fields = [
        "workload",
        "iterations",
        "software_cycles_per_call",
        "proreg_cycles_per_call",
        "saved_cycles_per_call",
        *(key for key, _, _ in counters),
        "counter_validation",
        "savings_drift_percent",
        "convergence",
        "status",
    ]
    summary = []
    for workload in WORKLOADS:
        pairs = []
        savings = []
        for count in ITERATIONS:
            sw = indexed[workload, count, "software"]
            hw = indexed[workload, count, "proreg"]
            pair = dict.fromkeys(fields)
            pair.update(
                workload=workload, iterations=count, counter_validation="FAIL"
            )
            if sw["status"] == hw["status"] == "PASS":
                sw_stats, hw_stats = sw["statistics"], hw["statistics"]
                cycle_stat = "system.cpu.numCycles"
                saved = Fraction(
                    sw_stats[cycle_stat] - hw_stats[cycle_stat], count
                )
                savings.append(saved)
                pair.update(
                    software_cycles_per_call=sw_stats[cycle_stat] / count,
                    proreg_cycles_per_call=hw_stats[cycle_stat] / count,
                    saved_cycles_per_call=float(saved),
                    counter_validation="PASS",
                )
                for key, counter, expected in counters:
                    stat = f"system.cpu.commitStats0.{counter}"
                    delta = sw_stats[stat] - hw_stats[stat]
                    pair[key] = delta / count
                    if delta != expected * count:
                        pair["counter_validation"] = "FAIL"
            pairs.append(pair)
        drift, converged = convergence(savings)
        for pair in pairs:
            passed = converged and pair["counter_validation"] == "PASS"
            pair.update(
                savings_drift_percent=(
                    None if drift is None else float(100 * drift)
                ),
                convergence="PASS" if converged else "FAIL",
                status="PASS" if passed else "FAIL",
            )
        summary.extend(pairs)
    return summary


def clobber_pairs(results):
    zero = [r for r in results if r["clobber_count"] == 0]
    controls = {(r["mode"], r["workload"], r["iterations"]): r for r in zero}
    zero_pairs = {
        (p["workload"], p["iterations"]): p for p in proreg_pairs(zero)
    }
    summary = []
    for k in CLOBBER_COUNTS:
        runs = [r for r in results if r["clobber_count"] == k]
        indexed = {
            (r["mode"], r["workload"], r["iterations"]): r for r in runs
        }
        for pair in proreg_pairs(runs):
            key = (pair["workload"], pair["iterations"])
            reference = zero_pairs[key]
            pair["clobber_count"] = k
            pair["change_vs_zero_cycles_per_call"] = None
            current, baseline = (
                pair["saved_cycles_per_call"],
                reference["saved_cycles_per_call"],
            )
            if current is not None and baseline is not None:
                pair["change_vs_zero_cycles_per_call"] = current - baseline

            # Every level executes twelve integer writes at the same PCs.
            # Changing their destinations must preserve retired work in each gate.
            equal_work = True
            for mode in ("software", "proreg"):
                arm = (mode, pair["workload"], pair["iterations"])
                trial, control = indexed[arm], controls[arm]
                if trial["status"] != "PASS" or control["status"] != "PASS":
                    equal_work = False
                    break
                for counter in ("numInsts", "numLoadInsts", "numStoreInsts"):
                    stat = f"system.cpu.commitStats0.{counter}"
                    if (
                        trial["statistics"][stat]
                        != control["statistics"][stat]
                    ):
                        equal_work = False
            pair["fixed_work_validation"] = "PASS" if equal_work else "FAIL"
            if not equal_work or reference["status"] != "PASS":
                pair["status"] = "FAIL"
            summary.append(pair)
    return summary


def report_proreg(outdir, results, *, clobber=False):
    summary = clobber_pairs(results) if clobber else proreg_pairs(results)
    for pair in summary:
        level = f" k={pair['clobber_count']}" if clobber else ""
        relative = (
            f", change vs k=0: {pair['change_vs_zero_cycles_per_call']}"
            if clobber
            else ""
        )
        print(
            f"{pair['workload']} N={pair['iterations']}{level}: "
            f"SW={pair['software_cycles_per_call']}, "
            f"PROREG={pair['proreg_cycles_per_call']}, "
            f"saved={pair['saved_cycles_per_call']}{relative} cycles/call "
            f"[{pair['status']}]"
        )
    passed = all(r["status"] == "PASS" for r in summary)
    write_csv(outdir / "summary.csv", summary, list(summary[0]))
    write_json(
        outdir / "summary.json",
        {
            "status": "PASS" if passed else "FAIL",
            "pairs": summary,
        },
    )
    print(f"Results: {outdir}")
    return 0 if passed else 124 if any(r["timed_out"] for r in results) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--jobs", type=int, choices=range(1, 33), default=8)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--comparison",
        choices=("components", "proreg", "clobber"),
        default="components",
        help="Measure software components or paired software and PROREG gates.",
    )
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    args.outdir = args.outdir.resolve()
    jobs = [
        dict(mode=mode, workload=workload, iterations=count)
        for mode in (
            MODES
            if args.comparison == "components"
            else ("software", "proreg")
        )
        for workload in WORKLOADS
        for count in ITERATIONS
    ]
    if args.comparison == "clobber":
        jobs = [
            dict(job, clobber_count=k) for job in jobs for k in CLOBBER_COUNTS
        ]
    gem5 = REPO / "build/RISCV_DASICS/gem5.opt"
    config = REPO / "configs/dasics/riscv_dasics_reg_protection_o3_v5_full.py"
    for path in [gem5, config] + [
        TEST_DIR / "build/roi" / f"{job_name(job)}.elf" for job in jobs
    ]:
        if not path.is_file():
            parser.error(f"Missing required input: {path}")
    if not os.access(gem5, os.X_OK):
        parser.error(f"gem5 is not executable: {gem5}")
    for name in [job_name(job) for job in jobs] + [
        "results.json",
        "results.csv",
        "summary.json",
        "summary.csv",
    ]:
        if (args.outdir / name).exists():
            parser.error(f"Output already exists: {args.outdir / name}")
    args.outdir.mkdir(parents=True, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = [executor.submit(run_job, args, job) for job in jobs]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            good = result["status"] == "PASS"
            color, label = ("32", "OK") if good else ("31", result["status"])
            print(
                f"\033[1;{color}m[{label}] {result['name']}\033[0m",
                flush=True,
            )
            if not good:
                print(f"  {result.get('error')}; log: {result['output_dir']}")
    results.sort(key=lambda row: row["name"])
    write_json(args.outdir / "results.json", results)
    result_rows = []
    for result in results:
        row = {
            key: result.get(key)
            for key in (
                "name",
                "mode",
                "workload",
                "iterations",
                "warmup",
                "status",
                "process_exit_code",
                "timed_out",
                "error",
            )
        }
        if "clobber_count" in result:
            row["clobber_count"] = result["clobber_count"]
        row.update(
            {key: result.get("statistics", {}).get(key) for key in STAT_KEYS}
        )
        result_rows.append(row)
    write_csv(args.outdir / "results.csv", result_rows, list(result_rows[0]))
    if args.comparison in ("proreg", "clobber"):
        return report_proreg(
            args.outdir, results, clobber=args.comparison == "clobber"
        )
    summary = summarize(results)
    checks = validate_instruction_deltas(results)
    for row in summary:
        names = {
            f"{mode}-{row['workload']}-{row['iterations']}" for mode in MODES
        }
        valid = all(
            check["status"] == "PASS"
            for check in checks
            if check["positive"] in names or check["negative"] in names
        )
        row["instruction_validation"] = "PASS" if valid else "FAIL"
    passed = all(
        row["status"]
        == row["convergence"]
        == row["instruction_validation"]
        == "PASS"
        for row in summary
    )
    write_json(
        args.outdir / "summary.json",
        dict(
            status="PASS" if passed else "FAIL",
            pairs=summary,
            validation=checks,
        ),
    )
    fields = [
        "workload",
        "iterations",
        "status",
        "software_cycles_per_call",
        "boundary_cycles_per_call",
        "save_only_cycles_per_call",
        "save_restore_cycles_per_call",
        "increment_cycles_per_call",
        *(f"{label}_cycles_per_call" for label, *_ in CONTRASTS),
        *(f"{label}_absolute_drift" for label, *_ in CONTRASTS),
        "convergence_reference_iterations",
        "increment_drift_percent",
        "convergence",
        "instruction_validation",
    ]
    write_csv(args.outdir / "summary.csv", summary, fields)
    print(
        "\nCycles per call "
        "(boundary reference does not protect data registers):"
    )
    displayed = [
        "software",
        "boundary",
        "save",
        "clear",
        "restore",
        "increment",
    ]
    print(
        f"{'Workload':<10} {'N':>5} "
        + " ".join(f"{label.title():>12}" for label in displayed)
    )
    for row in summary:
        values = [
            format(row[key], ".6f") if key in row else "N/A"
            for key in (f"{label}_cycles_per_call" for label in displayed)
        ]
        print(
            f"{row['workload']:<10} {row['iterations']:>5} "
            + " ".join(f"{value:>12}" for value in values)
        )
    for row in summary[::2]:
        drift = row["increment_drift_percent"]
        value = f"{drift:.6f}%" if drift is not None else "N/A"
        print(
            f"{row['workload']} increment drift: {value}; {row['convergence']}"
        )
    if all(check["status"] == "PASS" for check in checks):
        print(
            f"Committed-instruction deltas: {len(checks)}/{len(checks)} PASS"
        )
    else:
        for check in checks:
            if check["status"] != "PASS":
                print(
                    f"\033[1;31m[FAIL] {check['positive']} minus "
                    f"{check['negative']}: instructions "
                    f"{check['observed_instruction_delta']}, expected "
                    f"{check['expected_instruction_delta']}\033[0m"
                )
    color, label = ("32", "OK") if passed else ("31", "FAIL")
    print(f"\033[1;{color}m[{label}] DASICS ROI batch\033[0m")
    print(f"Results: {args.outdir}")
    return 0 if passed else 124 if any(r["timed_out"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
