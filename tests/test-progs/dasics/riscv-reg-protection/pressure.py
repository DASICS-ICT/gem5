#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

"""Compare register-protection overhead under fixed-count pointer chasing."""

import argparse
import math
import os
import re
import shlex
import socket
import sys
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import (
    asdict,
    dataclass,
)
from datetime import datetime
from pathlib import Path

import run

WORKING_SETS = (1024, 32768, 65536, 131072, 262144)
ALLOCATION_BYTES = 262144
COUNT_KEYS = (
    "system.cpu.commitStats0.numInsts",
    "system.cpu.commitStats0.numOps",
    "system.cpu.commitStats0.numLoadInsts",
    "system.cpu.commitStats0.numStoreInsts",
)


@dataclass(frozen=True)
class PressureJob(run.Job):
    working_set: int = 0
    seed: int = 0
    loads_per_call: int = 4096

    @property
    def name(self):
        if self.mode == "verify":
            return super().name
        return (
            f"w{self.working_set}-seed{self.seed}-{self.case}"
            f"-n{self.iterations}"
        )

    @property
    def guest_args(self):
        args = super().guest_args
        if self.mode == "measure":
            args += [
                str(self.working_set),
                str(self.seed),
                str(self.loads_per_call),
            ]
        return args


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_counts(directory):
    counts = {}
    # The shared runner has validated one complete ROI statistics block.
    for line in (directory / "roi-stats.txt").read_text().splitlines():
        fields = line.split()
        if fields and fields[0] in COUNT_KEYS:
            require(len(fields) >= 2, f"Missing count for {fields[0]}")
            counts[fields[0]] = int(fields[1])
    require(
        set(counts) == set(COUNT_KEYS),
        "Missing committed instruction, operation, load, or store count",
    )
    return counts


def validate_pressure(result, job):
    directory = Path(result["output_dir"])
    guest = run.read_guest(directory / "guest.stdout")
    if job.mode == "verify":
        require(
            isinstance(guest.get("checks"), int) and guest["checks"] > 0,
            "Guest verification did not report positive checks",
        )
        require(
            guest.get("failures", 0) == 0,
            "Guest verification reported failed checks",
        )
        result["checks"] = guest["checks"]
        return
    for key, value in dict(
        working_set=job.working_set,
        seed=job.seed,
        loads_per_call=job.loads_per_call,
        allocated_bytes=ALLOCATION_BYTES,
    ).items():
        require(
            guest.get(key) == value,
            f"Guest {key}: expected {value!r}, got {guest.get(key)!r}",
        )
    for key in ("ring_address", "frame_address", "head_address"):
        value = guest.get(key)
        require(
            isinstance(value, str) and re.fullmatch(r"0x[0-9a-fA-F]+", value),
            f"Missing or invalid hexadecimal {key}",
        )
        require(int(value, 16) > 0, f"Null {key}")
        result[key] = value
    ring = int(result["ring_address"], 16)
    head = int(result["head_address"], 16)
    require(
        ring % 64 == 0
        and ring <= head < ring + job.working_set
        and (head - ring) % 64 == 0,
        "Ring or head address violates the cache-line ring geometry",
    )
    lines = job.working_set // 64
    expected_checksum = (
        (job.loads_per_call // lines)
        * (lines * ring + 64 * lines * (lines - 1) // 2)
        % (1 << 64)
    )
    for key in ("checksum", "expected_checksum"):
        require(
            type(guest.get(key)) is int and guest[key] == expected_checksum,
            f"Incorrect {key} for the fixed-count address checksum",
        )
    for key in ("checksum", "expected_checksum", "allocated_bytes"):
        result[key] = guest[key]
    result.update(read_counts(directory))
    # Each gate has eight common loads/stores; GF adds 19 GPR and 24 FPR
    # transfers and 43 clears. The batch adds six instructions per call,
    # seven boundary instructions, and one marker within the ROI counters.
    protected = 43 if job.case == "GF_SCR" else 0
    loads = job.iterations * (job.loads_per_call + 8 + protected)
    stores = job.iterations * (8 + protected)
    instructions = (
        job.iterations * (4 * job.loads_per_call + 31 + 3 * protected) + 8
    )
    result.update(
        expected_committed_loads=loads,
        expected_committed_stores=stores,
        expected_committed_instructions=instructions,
    )
    for suffix, expected in (
        ("numLoadInsts", loads),
        ("numStoreInsts", stores),
        ("numInsts", instructions),
        ("numOps", instructions),
    ):
        actual = result[f"system.cpu.commitStats0.{suffix}"]
        require(
            actual == expected,
            f"Committed {suffix}: expected {expected}, got {actual}",
        )
    result["count_validation"] = "PASS"


def save_validation(result):
    directory = Path(result["output_dir"])
    run.write_json(directory / "result.json", result)
    with (directory / "gem5.log").open("a") as stream:
        stream.write(f"pressure_validation: {result['status']}\n")
        if result["reason"]:
            stream.write(f"pressure_reason: {result['reason']}\n")


def execute(args, job):
    result = run.run_job(args, job)
    if result["status"] == "PASS":
        try:
            validate_pressure(result, job)
        except (OSError, ValueError) as error:
            result.update(status="FAIL", reason=str(error))
        save_validation(result)
    return result


def run_batch(args, jobs):
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(execute, args, job) for job in jobs]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            label = "OK" if result["status"] == "PASS" else result["status"]
            run.report(
                label,
                f"{result['name']} "
                f"({result['wall_seconds']:.2f} s) {result['reason']}",
            )
    return sorted(results, key=lambda row: row["name"])


def make_summary(results):
    pairs = {}
    for row in results:
        if row["mode"] == "measure":
            key = (row["working_set"], row["seed"], row["iterations"])
            pairs.setdefault(key, {})[row["case"]] = row
    summary = []
    for (working_set, seed, iterations), pair in sorted(pairs.items()):
        base, guard = pair.get("B"), pair.get("GF_SCR")
        row = dict(
            working_set=working_set,
            seed=seed,
            iterations=iterations,
            status="FAIL",
            reason="A paired job failed or is missing",
            baseline_cycles=None,
            guard_cycles=None,
            baseline_cycles_per_call=None,
            guard_cycles_per_call=None,
            incremental_cycles_per_call=None,
            relative_overhead_percent=None,
        )
        if base and guard and base["status"] == guard["status"] == "PASS":
            keys = (
                "ring_address",
                "frame_address",
                "head_address",
                "checksum",
                "expected_checksum",
                "loads_per_call",
                "allocated_bytes",
                "warmup",
            )
            mismatched = [key for key in keys if base[key] != guard[key]]
            if mismatched:
                reason = "Paired job mismatch: " + ", ".join(mismatched)
                row["reason"] = reason
                for result in (base, guard):
                    result.update(status="FAIL", reason=reason)
                    save_validation(result)
                run.report(
                    "FAIL",
                    f"W={working_set}, seed={seed}, "
                    f"N={iterations}: {reason}",
                )
            else:
                b, g = base["elapsed_cycles"], guard["elapsed_cycles"]
                row.update(
                    status="PASS",
                    reason="",
                    baseline_cycles=b,
                    guard_cycles=g,
                    baseline_cycles_per_call=b / iterations,
                    guard_cycles_per_call=g / iterations,
                    incremental_cycles_per_call=(g - b) / iterations,
                    relative_overhead_percent=100 * (g - b) / b,
                )
                row.update({key: base[key] for key in keys})
        summary.append(row)
    return summary


def compare_iterations(summary):
    groups = {}
    for row in summary:
        if row["status"] == "PASS":
            groups.setdefault((row["working_set"], row["seed"]), []).append(
                row
            )
    comparisons = []
    metrics = (
        "baseline_cycles_per_call",
        "guard_cycles_per_call",
        "incremental_cycles_per_call",
        "relative_overhead_percent",
    )
    for (working_set, seed), rows in sorted(groups.items()):
        rows.sort(key=lambda row: row["iterations"])
        if len(rows) < 2:
            comparisons.append(
                dict(
                    working_set=working_set,
                    seed=seed,
                    status="UNASSESSED",
                    low_iterations=rows[0]["iterations"],
                    high_iterations=None,
                    threshold=0.01,
                )
            )
        for low, high in zip(rows, rows[1:]):
            for metric in metrics:
                a, b = low[metric], high[metric]
                change = abs(a - b) / abs(b) if b else (0 if a == b else None)
                comparisons.append(
                    dict(
                        working_set=working_set,
                        seed=seed,
                        metric=metric,
                        low_iterations=low["iterations"],
                        high_iterations=high["iterations"],
                        low_value=a,
                        high_value=b,
                        relative_change=change,
                        threshold=0.01,
                        status=(
                            "PASS"
                            if change is not None and change <= 0.01
                            else "NOT_CONVERGED"
                        ),
                    )
                )
    return comparisons


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gem5", type=Path, default=run.ROOT / "build/RISCV/gem5.opt"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=run.ROOT / "configs/dasics/riscv_reg_protection_o3_v5_full.py",
    )
    parser.add_argument(
        "--binary", type=Path, default=run.TEST_DIR / "build/reg-pressure.elf"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=run.TEST_DIR
        / "build/runs"
        / datetime.now().strftime("pressure-%Y%m%d-%H%M%S-%f"),
    )
    parser.add_argument(
        "--working-set",
        nargs="+",
        type=int,
        choices=WORKING_SETS,
        default=list(WORKING_SETS),
    )
    parser.add_argument(
        "--seeds", nargs="+", type=int, choices=(0, 1, 2), default=[0, 1, 2]
    )
    parser.add_argument(
        "--iterations", nargs="+", type=run.positive_int, default=[32, 64]
    )
    parser.add_argument("--warmup", type=int, choices=(8,), default=8)
    parser.add_argument(
        "--loads-per-call", type=int, choices=(4096,), default=4096
    )
    parser.add_argument("--jobs", type=run.positive_int, default=8)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--max-ticks", type=run.positive_int)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
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
    for key in ("working_set", "seeds", "iterations"):
        setattr(args, key, list(dict.fromkeys(getattr(args, key))))
    return args


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    jobs = [
        PressureJob(
            "measure",
            128,
            case,
            "memory",
            iterations,
            args.warmup,
            size,
            seed,
            args.loads_per_call,
        )
        for size in args.working_set
        for seed in args.seeds
        for iterations in args.iterations
        for case in ("B", "GF_SCR")
    ]
    if args.verify_only:
        jobs = []
    manifest = dict(
        status="RUNNING",
        start_time=run.utc_now(),
        end_time=None,
        returncode=None,
        hostname=socket.gethostname(),
        command=shlex.join([sys.executable, *sys.argv]),
        arguments={
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        },
        jobs=[asdict(job) for job in jobs],
        comparison="Paired B/GF_SCR with equal W, seed, N, K and addresses",
        seed_scope="All seeds retained individually; no confidence interval",
    )
    run.write_json(args.output_dir / "finalrun.json", manifest, exclusive=True)
    print(
        f"Host: {manifest['hostname']}; workers: {args.jobs}; "
        f"measurement jobs: {len(jobs)}\nOutput: {args.output_dir}",
        flush=True,
    )
    results = run_batch(args, [PressureJob("verify", 128)])
    if all(result["status"] == "PASS" for result in results):
        results += run_batch(args, jobs)
    else:
        run.report(
            "FAIL", "Functional verification failed; measurements skipped"
        )
    summary = make_summary(results)
    comparisons = compare_iterations(summary)
    run.write_table(args.output_dir, "results", results)
    run.write_table(args.output_dir, "summary", summary)
    run.write_table(args.output_dir, "n-comparison", comparisons)
    print(
        "\nW bytes  Seed     N  Status    Base/call   Guard/call"
        "    Delta/call    Overhead%"
    )
    for row in summary:
        values = [
            f"{row[key]:.4f}" if row[key] is not None else "N/A"
            for key in (
                "baseline_cycles_per_call",
                "guard_cycles_per_call",
                "incremental_cycles_per_call",
                "relative_overhead_percent",
            )
        ]
        print(
            f"{row['working_set']:7}  {row['seed']:4}  {row['iterations']:4}  "
            f"{row['status']:6}  "
            + "  ".join(f"{value:>11}" for value in values)
        )
    review = any(row["status"] != "PASS" for row in comparisons)
    if review:
        run.report(
            "WARN",
            "Iteration convergence needs review (1% threshold); "
            "see n-comparison.csv. No automatic reruns.",
        )
    failed = any(row["status"] != "PASS" for row in results + summary)
    manifest.update(
        status="FAIL" if failed else "PASS",
        end_time=run.utc_now(),
        returncode=int(failed),
        completed_jobs=len(results),
        convergence_status=(
            "REVIEW" if review else "PASS" if comparisons else "UNASSESSED"
        ),
    )
    run.write_json(args.output_dir / "finalrun.json", manifest)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
