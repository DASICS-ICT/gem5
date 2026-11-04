#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

"""Run isolated v5_full register-protection measurements and comparisons."""

import argparse
import csv
import json
import math
import os
import shlex
import socket
import subprocess
import sys
import time
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import (
    asdict,
    dataclass,
)
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
ROOT = TEST_DIR.parents[3]
VLENS = (128, 256, 512, 1024)
CASES = (
    "B",
    "G_SR",
    "G_SCR",
    "F_SR",
    "F_SCR",
    "GF_SR",
    "GF_SCR",
    "V_SR",
    "V_SCR",
    "GFV_SR",
    "GFV_SCR",
    "VCTL",
)
SCALAR_CASES = {"G_SR", "G_SCR", "F_SR", "F_SCR", "GF_SR", "GF_SCR"}
STAT_KEYS = (
    "system.cpu.numCycles",
    "system.cpu.commitStats0.numInsts",
    "system.cpu.commitStats0.numOps",
    "system.cpu.commit.branchMispredicts",
    "system.cpu.commit.commitNonSpecStalls",
    "system.cpu.rename.status::SerializeStall",
    "system.cpu.rename.SQFullEvents",
    "system.cpu.iew.iqFullEvents",
    "system.cpu.numRecvResp",
    "system.cpu.numRecvRespBytes",
    "system.cpu.branchPred.mispredictDueToBTBMiss_0::Return",
    "system.cpu.branchPred.mispredictDueToBTBMiss_0::CallIndirect",
    "system.cpu.branchPred.btb.lookups::Return",
    "system.cpu.branchPred.btb.lookups::CallIndirect",
    "system.cpu.lsq0.forwLoads",
    "system.cpu.lsq0.blockedByCache",
    "system.cpu.lsq0.lqAvgOccupancy",
    "system.cpu.lsq0.sqAvgOccupancy",
    "system.cpu.iew.lsqFullEvents",
    "system.cpu.dcache.overallAccesses::total",
    "system.cpu.dcache.overallMisses::total",
)


@dataclass(frozen=True)
class Job:
    mode: str
    vlen: int
    case: str = ""
    callee: str = ""
    iterations: int = 0
    warmup: int = 0

    @property
    def name(self):
        if self.mode == "verify":
            return f"verify-vlen{self.vlen}"
        return (
            f"vlen{self.vlen}-{self.case}-{self.callee}" f"-n{self.iterations}"
        )

    @property
    def guest_args(self):
        if self.mode == "verify":
            return ["verify", str(self.vlen)]
        return [
            "measure",
            self.case,
            self.callee,
            str(self.iterations),
            str(self.warmup),
            str(self.vlen),
        ]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data, exclusive=False):
    with path.open("x" if exclusive else "w") as stream:
        stream.write(json.dumps(data, indent=2, allow_nan=False) + "\n")


def report(status, detail):
    color = "32" if status == "OK" else "33" if status == "WARN" else "31"
    label = f"[{status}]"
    if sys.stdout.isatty():
        label = f"\033[1;{color}m{label}\033[0m"
    print(f"{label} {detail}", flush=True)


def read_object(path):
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path.name}")
    return value


def read_guest(path):
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    if not lines:
        raise ValueError("Guest output is empty")
    value = json.loads(lines[-1])
    if not isinstance(value, dict):
        raise ValueError("The final guest output must be a JSON object")
    return value


def read_stats(path):
    lines = path.read_text().splitlines()
    begins = [
        i
        for i, line in enumerate(lines)
        if "Begin Simulation Statistics" in line
    ]
    ends = [
        i
        for i, line in enumerate(lines)
        if "End Simulation Statistics" in line
    ]
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        raise ValueError("ROI statistics must contain one complete block")
    values = {}
    for line in lines[begins[0] + 1 : ends[0]]:
        fields = line.split()
        if len(fields) < 2 or fields[0].startswith("#"):
            continue
        try:
            value = int(fields[1])
        except ValueError:
            try:
                value = float(fields[1])
            except ValueError:
                continue
            if not math.isfinite(value):
                value = None
        values[fields[0]] = value
    if not values:
        raise ValueError("ROI statistics contain no numeric entries")
    selected = {key: values.get(key) for key in STAT_KEYS}
    selected.update(
        {
            key: value
            for key, value in values.items()
            if key.startswith(("system.cpu.lsq0.", "system.cpu.dcache."))
        }
    )
    return selected


def validate_outputs(job, directory):
    guest = read_guest(directory / "guest.stdout")
    expected = {"status": "PASS", "mode": job.mode, "vlen": job.vlen}
    if job.mode == "measure":
        expected.update(
            case=job.case,
            callee=job.callee,
            iterations=job.iterations,
            warmup=job.warmup,
        )
    for key, value in expected.items():
        if guest.get(key) != value:
            raise ValueError(
                f"Guest {key}: expected {value!r}, " f"got {guest.get(key)!r}"
            )
    roi = read_object(directory / "roi.json")
    expected_roi = {
        "status": "PASS",
        "mode": job.mode,
        "vlen_bits": job.vlen,
        "program_args": job.guest_args,
        "guest_exit_code": 0,
    }
    for key, value in expected_roi.items():
        if roi.get(key) != value:
            raise ValueError(
                f"ROI {key}: expected {value!r}, " f"got {roi.get(key)!r}"
            )
    if job.mode == "verify":
        return {}, None
    numbers = {}
    for key in (
        "start_tick",
        "end_tick",
        "clock_period_ticks",
        "elapsed_cycles",
    ):
        value = roi.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"Invalid ROI {key}: {value!r}")
        numbers[key] = value
    if (
        numbers["start_tick"] < 0
        or numbers["end_tick"] <= numbers["start_tick"]
        or numbers["clock_period_ticks"] <= 0
    ):
        raise ValueError("Invalid ROI tick interval or clock period")
    elapsed = (numbers["end_tick"] - numbers["start_tick"]) / numbers[
        "clock_period_ticks"
    ]
    if not math.isclose(
        numbers["elapsed_cycles"], elapsed, rel_tol=1e-12, abs_tol=1e-9
    ):
        raise ValueError("ROI cycle count does not match its tick interval")
    return read_stats(directory / "roi-stats.txt"), elapsed


def run_job(args, job):
    directory = args.output_dir / job.name
    directory.mkdir()
    command = [
        str(args.gem5),
        "--listener-mode=off",
        "-d",
        str(directory),
        str(args.config),
        "--vlen",
        str(job.vlen),
        "--stdout",
        str(directory / "guest.stdout"),
        "--stderr",
        str(directory / "guest.stderr"),
    ]
    if args.max_ticks is not None:
        command += ["--max-ticks", str(args.max_ticks)]
    command += [str(args.binary), *job.guest_args]
    result = {
        **dict.fromkeys(STAT_KEYS),
        **asdict(job),
        "name": job.name,
        "status": "RUNNING",
        "reason": "",
        "output_dir": str(directory),
        "command": shlex.join(command),
        "start_time": utc_now(),
        "end_time": None,
        "returncode": None,
        "elapsed_cycles": None,
    }
    write_json(directory / "command.json", command)
    write_json(directory / "result.json", result)
    started = time.monotonic()
    with (directory / "gem5.log").open("w") as log:
        log.write(f"start_time: {result['start_time']}\n")
        log.write(f"command: {result['command']}\n")
        log.flush()
        try:
            # A timeout kills only the child owned by this worker.
            process = subprocess.Popen(
                command,
                cwd=directory,
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            )
            result["pid"] = process.pid
            write_json(directory / "result.json", result)
            try:
                result["returncode"] = process.wait(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                result["returncode"] = process.wait()
                result.update(
                    status="TIMEOUT",
                    reason=(
                        f"Exceeded {args.timeout:g} seconds; child terminated"
                    ),
                )
            if result["status"] != "TIMEOUT":
                if result["returncode"] != 0:
                    raise ValueError(
                        f"gem5 exited with code {result['returncode']}"
                    )
                stats, cycles = validate_outputs(job, directory)
                result.update(stats)
                result.update(status="PASS", elapsed_cycles=cycles)
        except (OSError, ValueError) as error:
            result.update(status="FAIL", reason=str(error))
        result["end_time"] = utc_now()
        result["wall_seconds"] = time.monotonic() - started
        log.write(f"\nend_time: {result['end_time']}\n")
        log.write(f"returncode: {result['returncode']}\n")
        log.write(f"status: {result['status']}\n")
        if result["reason"]:
            log.write(f"reason: {result['reason']}\n")
    write_json(directory / "result.json", result)
    return result


def run_batch(args, jobs):
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(run_job, args, job): job for job in jobs}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            status = "OK" if result["status"] == "PASS" else result["status"]
            detail = f"{result['name']} ({result['wall_seconds']:.2f} s)"
            if result["reason"]:
                detail += f": {result['reason']}"
            report(status, detail)
    return sorted(results, key=lambda row: row["name"])


def write_table(directory, name, rows):
    write_json(directory / f"{name}.json", rows)
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with (directory / f"{name}.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, restval="N/A")
        writer.writeheader()
        writer.writerows(
            {
                key: "N/A" if value is None else value
                for key, value in row.items()
            }
            for row in rows
        )


def make_summary(results):
    passed = [
        row
        for row in results
        if row["mode"] == "measure" and row["status"] == "PASS"
    ]
    index = {
        (r["vlen"], r["callee"], r["iterations"], r["case"]): r for r in passed
    }
    rows = []
    for result in passed:
        vlen, callee, count, case = (
            result[key] for key in ("vlen", "callee", "iterations", "case")
        )
        baseline = index.get((vlen, callee, count, "B"))
        sr = (
            index.get((vlen, callee, count, case.replace("_SCR", "_SR")))
            if case.endswith("_SCR")
            else None
        )
        cycles = result["elapsed_cycles"]
        registers = case.split("_")[0] if "_" in case else ""
        logical_bytes = 2 * (
            (152 if "G" in registers else 0)
            + (192 if "F" in registers else 0)
            + (4 * vlen if "V" in registers else 0)
        )
        row = {
            "vlen": vlen,
            "case": case,
            "callee": callee,
            "iterations": count,
            "warmup": result["warmup"],
            "elapsed_cycles": cycles,
            "cycles_per_call": cycles / count,
            "baseline_cycles": (
                baseline["elapsed_cycles"] if baseline else None
            ),
            "incremental_cycles_per_call": (
                (cycles - baseline["elapsed_cycles"]) / count
                if baseline
                else None
            ),
            "scr_minus_sr_cycles_per_call": (
                (cycles - sr["elapsed_cycles"]) / count if sr else None
            ),
            "logical_bytes_per_call": logical_bytes,
            "incremental_cycles_per_logical_byte": (
                (cycles - baseline["elapsed_cycles"]) / count / logical_bytes
                if baseline and logical_bytes
                else None
            ),
        }
        rows.append(row)
    return sorted(
        rows,
        key=lambda r: (
            r["vlen"],
            r["callee"],
            CASES.index(r["case"]),
            r["iterations"],
        ),
    )


def make_convergence(summary):
    groups = {}
    for row in summary:
        key = (row["vlen"], row["case"], row["callee"])
        groups.setdefault(key, []).append(row)
    rows = []
    metrics = (
        "cycles_per_call",
        "incremental_cycles_per_call",
        "scr_minus_sr_cycles_per_call",
    )
    for (vlen, case, callee), samples in sorted(groups.items()):
        samples.sort(key=lambda r: r["iterations"])
        if len(samples) < 2:
            rows.append(
                {
                    "vlen": vlen,
                    "case": case,
                    "callee": callee,
                    "metric": "cycles_per_call",
                    "status": "UNASSESSED",
                    "low_iterations": samples[0]["iterations"],
                    "high_iterations": None,
                    "low_value": None,
                    "high_value": None,
                    "relative_change": None,
                    "threshold": 0.01,
                }
            )
            continue
        # Compare adjacent counts, including explicitly requested longer runs.
        for low, high in zip(samples, samples[1:]):
            for metric in metrics:
                a, b = low[metric], high[metric]
                if a is None or b is None:
                    continue
                change = abs(a - b) / abs(b) if b else (0 if a == b else None)
                rows.append(
                    {
                        "vlen": vlen,
                        "case": case,
                        "callee": callee,
                        "metric": metric,
                        "status": (
                            "PASS"
                            if change is not None and change <= 0.01
                            else "NOT_CONVERGED"
                        ),
                        "low_iterations": low["iterations"],
                        "high_iterations": high["iterations"],
                        "low_value": a,
                        "high_value": b,
                        "relative_change": change,
                        "threshold": 0.01,
                    }
                )
    return rows


def display_summary(summary):
    print(
        "\nVLEN  Case     Callee       N     cycles/call    delta/B    SCR-SR"
    )
    for row in summary:
        values = [
            row[key]
            for key in (
                "cycles_per_call",
                "incremental_cycles_per_call",
                "scr_minus_sr_cycles_per_call",
            )
        ]
        formatted = [
            f"{value:.4f}" if value is not None else "N/A" for value in values
        ]
        print(
            f"{row['vlen']:4}  {row['case']:7}  {row['callee']:7}  "
            f"{row['iterations']:6}  {formatted[0]:>14}  "
            f"{formatted[1]:>9}  {formatted[2]:>8}"
        )


def add_convergence_to_summary(summary, convergence):
    index = {
        (r["vlen"], r["case"], r["callee"], r["iterations"]): r
        for r in summary
    }
    for row in summary:
        row["convergence_status"] = "UNASSESSED"
        row["convergence_threshold"] = 0.01
    for check in convergence:
        key = (
            check["vlen"],
            check["case"],
            check["callee"],
            check["high_iterations"],
        )
        if key not in index:
            continue
        row = index[key]
        row[f"{check['metric']}_relative_change"] = check["relative_change"]
        row[f"{check['metric']}_convergence"] = check["status"]
        row["compared_to_iterations"] = check["low_iterations"]
        if row["convergence_status"] != "NOT_CONVERGED":
            row["convergence_status"] = check["status"]


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gem5", type=Path, default=ROOT / "build/RISCV/gem5.opt"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=(ROOT / "configs/dasics/riscv_reg_protection_o3_v5_full.py"),
    )
    parser.add_argument(
        "--binary",
        type=Path,
        default=TEST_DIR / "build/riscv-reg-protection.elf",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=(
            TEST_DIR
            / "build/runs"
            / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        ),
    )
    parser.add_argument(
        "--jobs",
        type=positive_int,
        default=max(1, min(8, (os.cpu_count() or 1) - 2)),
    )
    parser.add_argument(
        "--vlen", type=int, nargs="+", choices=VLENS, default=list(VLENS)
    )
    parser.add_argument(
        "--iterations", type=positive_int, nargs="+", default=[1024, 4096]
    )
    parser.add_argument(
        "--cases", nargs="+", choices=CASES, default=list(CASES)
    )
    parser.add_argument(
        "--callees",
        nargs="+",
        choices=("empty", "compute"),
        default=["empty", "compute"],
    )
    parser.add_argument("--warmup", type=int, default=128)
    parser.add_argument(
        "--timeout",
        type=float,
        default=180,
        help="wall-clock seconds per gem5 child (default: 180)",
    )
    parser.add_argument("--max-ticks", type=positive_int)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.warmup < 0:
        parser.error("--warmup must be nonnegative")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be finite and positive")
    for key in ("gem5", "config", "binary"):
        path = getattr(args, key).expanduser().resolve()
        if not path.is_file():
            parser.error(f"Missing {key}: {path}")
        setattr(args, key, path)
    if not os.access(args.gem5, os.X_OK):
        parser.error(f"gem5 is not executable: {args.gem5}")
    args.output_dir = args.output_dir.expanduser().resolve()
    if args.output_dir.exists() and (
        not args.output_dir.is_dir() or any(args.output_dir.iterdir())
    ):
        parser.error(f"Output directory is not empty: {args.output_dir}")
    for key in ("vlen", "iterations", "cases", "callees"):
        setattr(args, key, list(dict.fromkeys(getattr(args, key))))
    # Include matched baselines and SR counterparts for requested SCR cases.
    paired = [
        case.replace("_SCR", "_SR")
        for case in args.cases
        if case.endswith("_SCR")
    ]
    args.cases = list(dict.fromkeys(["B", *args.cases, *paired]))
    return args


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    verification = [Job("verify", vlen) for vlen in args.vlen]
    measurements = (
        [
            Job("measure", vlen, case, callee, iterations, args.warmup)
            for vlen in args.vlen
            for case in args.cases
            if case not in SCALAR_CASES or vlen == 128
            for callee in args.callees
            for iterations in args.iterations
        ]
        if not args.verify_only
        else []
    )
    manifest = {
        "start_time": utc_now(),
        "end_time": None,
        "status": "RUNNING",
        "returncode": None,
        "hostname": socket.gethostname(),
        "runner_command": shlex.join([sys.executable, *sys.argv]),
        "arguments": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        },
        "verification_jobs": [asdict(job) for job in verification],
        "measurement_jobs": [asdict(job) for job in measurements],
        "cost_definition": "ROI tick interval divided by clock period",
        "comparison_scope": (
            "Software sequences on this gem5 model; matched-baseline and "
            "SCR-SR differences are not additive hardware costs."
        ),
    }
    write_json(args.output_dir / "finalrun.json", manifest, exclusive=True)
    print(
        f"Output: {args.output_dir}\nHost: {manifest['hostname']}\n"
        f"Workers: {args.jobs}; verification: {len(verification)}; "
        f"measurements: {len(measurements)}",
        flush=True,
    )
    results = run_batch(args, verification)
    if all(row["status"] == "PASS" for row in results):
        results += run_batch(args, measurements)
    else:
        report("FAIL", "Functional verification failed; measurements skipped")
    write_table(args.output_dir, "results", results)
    summary = make_summary(results)
    convergence = make_convergence(summary)
    add_convergence_to_summary(summary, convergence)
    write_table(args.output_dir, "summary", summary)
    display_summary(summary)
    failed = any(row["status"] != "PASS" for row in results)
    unconverged = [row for row in convergence if row["status"] != "PASS"]
    if unconverged:
        report(
            "WARN",
            f"{len(unconverged)} convergence checks need review; "
            "see summary.csv (1% threshold). No automatic reruns.",
        )
    manifest.update(
        end_time=utc_now(),
        status="FAIL" if failed else "PASS",
        returncode=1 if failed else 0,
        convergence_status=(
            "REVIEW"
            if unconverged
            else "PASS" if convergence else "UNASSESSED"
        ),
        completed_jobs=len(results),
    )
    write_json(args.output_dir / "finalrun.json", manifest)
    report("FAIL" if failed else "OK", f"Results saved in {args.output_dir}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
