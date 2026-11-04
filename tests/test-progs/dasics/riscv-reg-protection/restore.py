#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

"""Measure single register restores with independently checked data sources."""

import argparse
import configparser
import math
import os
import re
import shlex
import socket
import statistics
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
from datetime import datetime
from pathlib import Path

from run import (
    ROOT,
    TEST_DIR,
    VLENS,
    positive_int,
    read_guest,
    read_object,
    report,
    utc_now,
    write_json,
    write_table,
)

READ_COMMANDS = ("ReadReq", "ReadCleanReq", "ReadSharedReq", "ReadExReq")


@dataclass(frozen=True)
class RestoreJob:
    source: str
    vlen: int
    group: str
    samples: int

    @property
    def name(self):
        return f"{self.source}-vlen{self.vlen}-{self.group}"

    @property
    def guest_args(self):
        return [self.group, str(self.samples), str(self.vlen)]

    @property
    def target_lines(self):
        return {"B": 0, "G": 3, "F": 4, "V": self.vlen // 16}[self.group]


def require(condition, message):
    if not condition:
        raise ValueError(message)


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
    require(
        len(begins) == len(ends) == 1 and begins[0] < ends[0],
        "Sample statistics must contain one complete block",
    )
    result = {}
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
        require(fields[0] not in result, f"Duplicate statistic: {fields[0]}")
        result[fields[0]] = value
    require(bool(result), "Sample statistics contain no numeric entries")
    return result


def triplet(stats, prefix, demand=False, zero_if_absent=False):
    names = (
        ("demandAccesses", "demandHits", "demandMisses")
        if demand
        else ("accesses", "hits", "misses")
    )
    a, h, m = (stats.get(f"{prefix}.{name}::total") for name in names)
    if zero_if_absent and a is h is m is None:
        return 0, 0, 0
    # Cache counters use nozero: infer a missing member only from the identity.
    if a is None and h is not None and m is not None:
        a = h + m
    if h is None and a is not None and m is not None:
        h = a - m
    if m is None and a is not None and h is not None:
        m = a - h
    require(
        all(value is None or value >= 0 for value in (a, h, m)),
        f"Negative cache count: {prefix}",
    )
    if all(value is not None for value in (a, h, m)):
        require(a == h + m, f"Inconsistent cache counts: {prefix}")
    return a, h, m


def cache_reads(stats, banks):
    totals = [0, 0, 0]
    for bank in banks:
        # Cache/Tags always emit these scalars. CacheCmdStats marks command
        # counters nozero, so their complete omission then establishes zero.
        schema = all(
            stats.get(f"{bank}.{suffix}") is not None
            for suffix in ("tags.tagAccesses", "blockedCycles::no_mshrs")
        )
        if not schema:
            return None, None, None
        commands = []
        for command in READ_COMMANDS:
            counts = triplet(stats, f"{bank}.{command}", zero_if_absent=True)
            if any(value is not None for value in counts):
                if any(value is None for value in counts):
                    return None, None, None
                commands.append(counts)
        if not commands:
            return None, None, None
        bank_counts = [sum(values) for values in zip(*commands)]
        demand_accesses = triplet(
            stats, bank, demand=True, zero_if_absent=True
        )[0]
        require(
            demand_accesses == bank_counts[0],
            f"Unproven read-only demand traffic at {bank}",
        )
        totals = [a + b for a, b in zip(totals, bank_counts)]
    return tuple(totals)


def read_config(directory, job):
    config = configparser.ConfigParser(interpolation=None)
    require(config.read(directory / "config.ini"), "Missing config.ini")
    cpu = config["system.cpu"]
    require(cpu["type"] == "BaseO3CPU", "CPU is not BaseO3CPU")
    require(
        config.getint("system.cpu.isa", "vlen") == job.vlen,
        "Generated VLEN does not match the job",
    )
    period = int(config[cpu["clk_domain"]]["clock"].split()[0])
    require(
        config.getint("system", "cache_line_size") == 64,
        "Unexpected cache line size",
    )
    groups = {"l1": ["system.cpu.dcache"]}
    require(
        config["system.cpu.icache"].get("type") == "Cache",
        "Unexpected instruction-cache statistics schema",
    )
    for level in ("l2", "l3"):
        groups[level] = sorted(
            name
            for name in config.sections()
            if re.fullmatch(rf"system\.{level}\d+", name)
        )
        require(len(groups[level]) == 2, f"Expected two {level} banks")
    sizes = {"l1": 65536, "l2": 1048576, "l3": 2097152}
    ways = {"l1": 4, "l2": 8, "l3": 16}
    for level, banks in groups.items():
        require(
            sum(config.getint(bank, "size") for bank in banks) == sizes[level],
            f"Unexpected {level} capacity",
        )
        for bank in banks:
            require(
                config[bank].get("type") == "Cache",
                f"Unexpected cache statistics schema: {bank}",
            )
            require(
                config.getint(bank, "assoc") == ways[level],
                f"Unexpected associativity: {bank}",
            )
            require(
                config[bank].get("prefetcher") == "Null",
                f"Data prefetcher is enabled or unproven: {bank}",
            )
    return {
        "clock_period_ticks": period,
        "vlen_bits": job.vlen,
        "data_prefetchers_disabled": True,
        "cache_line_bytes": 64,
        "cache_sizes_bytes": sizes,
        "cache_banks": groups,
    }


def source_evidence(stats, job, config):
    evidence = {
        "target_lines": job.target_lines,
        "forwarded_loads": stats.get("system.cpu.lsq0.forwLoads"),
        "dram_read_bursts": stats.get("system.mem_ctrl.dram.readBursts"),
        "controller_read_requests": stats.get("system.mem_ctrl.readReqs"),
        "controller_write_queue_forwards": stats.get(
            "system.mem_ctrl.servicedByWrQ"
        ),
    }
    for level, banks in config["cache_banks"].items():
        for suffix, value in zip(
            ("accesses", "hits", "misses"), cache_reads(stats, banks)
        ):
            evidence[f"{level}_read_{suffix}"] = value
    icache_schema = all(
        stats.get(f"system.cpu.icache.{suffix}") is not None
        for suffix in ("tags.tagAccesses", "blockedCycles::no_mshrs")
    )
    ia, ih, im = triplet(
        stats, "system.cpu.icache.ReadReq", zero_if_absent=icache_schema
    )
    evidence.update(
        icache_read_accesses=ia, icache_read_hits=ih, icache_read_misses=im
    )
    require(
        evidence["forwarded_loads"] == 0,
        "Store-queue forwarding is nonzero or unproven",
    )
    require(im == 0, "Instruction-cache misses are nonzero or unproven")
    for name in ("dtb", "itb"):
        prefix = f"system.cpu.mmu.{name}"
        available = {
            key: stats[f"{prefix}.{key}"]
            for key in ("misses", "readMisses", "writeMisses")
            if f"{prefix}.{key}" in stats
        }
        evidence[f"{name}_misses"] = available.get("misses")
        evidence[f"{name}_check"] = "PASS" if available else "UNAVAILABLE"
        require(
            all(value == 0 for value in available.values()),
            f"Translation misses at {prefix}",
        )
    miss = evidence["l1_read_misses"]
    mshr = stats.get("system.cpu.dcache.ReadReq.mshrMisses::total")
    merged = stats.get("system.cpu.dcache.ReadReq.mshrHits::total")
    if mshr is None and miss == 0:
        mshr = 0
    if mshr is None and miss is not None and merged is not None:
        mshr = miss - merged
    if merged is None and miss is not None and mshr is not None:
        merged = miss - mshr
    evidence.update(l1_mshr_misses=mshr, l1_mshr_hits=merged)
    if job.group == "B":
        evidence["source_check"] = "BASELINE_NO_TARGET"
        return evidence
    require(
        evidence["l1_read_accesses"] is not None
        and evidence["l1_read_accesses"] > 0,
        "No proven target reads at L1D",
    )
    if job.source == "l1":
        require(miss == 0, "L1 source has misses or missing hit evidence")
    else:
        require(
            mshr == job.target_lines,
            f"Cold L1 line misses: expected {job.target_lines}, got {mshr}",
        )
        if job.source == "l2":
            require(
                evidence["l2_read_hits"] == job.target_lines
                and evidence["l2_read_misses"] == 0,
                "L2 hits do not cover all target lines without misses",
            )
        else:
            for level in ("l2", "l3"):
                require(
                    evidence[f"{level}_read_misses"] == job.target_lines
                    and evidence[f"{level}_read_hits"] == 0,
                    f"DRAM source is not cold at {level}",
                )
            require(
                evidence["dram_read_bursts"] == job.target_lines,
                "DRAM reads do not match the target line count",
            )
            require(
                evidence["controller_write_queue_forwards"] == 0,
                "Memory-controller write-queue forwarding is unproven",
            )
    evidence["source_check"] = "PASS"
    return evidence


def validate_job(directory, job):
    guest = read_guest(directory / "guest.stdout")
    for key, value in dict(
        status="PASS",
        mode="restore",
        group=job.group,
        samples=job.samples,
        vlen=job.vlen,
        failures=0,
        cache_lines=job.target_lines,
        data_bytes={"B": 0, "G": 152, "F": 192, "V": 4 * job.vlen}[job.group],
    ).items():
        require(
            guest.get(key) == value,
            f"Guest {key}: expected {value!r}, got {guest.get(key)!r}",
        )
    require(
        isinstance(guest.get("checks"), int)
        and guest["checks"] >= job.samples,
        "Guest did not report enough independent correctness checks",
    )
    metadata = read_object(directory / "restore.json")
    for key, value in dict(
        status="PASS",
        source=job.source,
        vlen_bits=job.vlen,
        program_args=job.guest_args,
        guest_exit_code=0,
    ).items():
        require(
            metadata.get(key) == value,
            f"Restore {key}: expected {value!r}, got {metadata.get(key)!r}",
        )
    samples = metadata.get("samples")
    require(
        isinstance(samples, list) and len(samples) == job.samples,
        "Restore sample count mismatch",
    )
    require(
        [sample.get("index") for sample in samples]
        == list(range(job.samples)),
        "Sample indices must be consecutive and start at zero",
    )
    config = read_config(directory, job)
    require(
        metadata.get("sim_frequency")
        == config["clock_period_ticks"] * 2_000_000_000
        and metadata.get("cpu_frequency_hz") == 2_000_000_000
        and metadata.get("cache_line_bytes") == 64,
        "Restore clock or cache geometry differs from the configuration",
    )
    rows = []
    for sample in samples:
        row = {
            "sample": sample["index"],
            "status": "FAIL",
            "reason": "",
            "elapsed_cycles": None,
            "stats_file": sample.get("stats_file"),
        }
        try:
            expected_file = f"sample-{sample['index']:03d}-stats.txt"
            require(
                sample.get("stats_file") == expected_file,
                "Unexpected sample statistics filename",
            )
            stats = read_stats(directory / expected_file)
            start, end, period, cycles = (
                sample.get(key)
                for key in (
                    "start_tick",
                    "end_tick",
                    "clock_period_ticks",
                    "elapsed_cycles",
                )
            )
            require(
                all(
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(value)
                    for value in (start, end, period, cycles)
                ),
                "Sample timing is incomplete or non-finite",
            )
            require(
                start >= 0 and end > start and period > 0,
                "Invalid sample tick interval",
            )
            require(
                period == config["clock_period_ticks"],
                "Sample clock period differs from generated configuration",
            )
            require(
                stats.get("simFreq") == period * 2_000_000_000,
                "Actual simulation frequency does not establish a 2 GHz CPU",
            )
            require(
                stats.get("simTicks") == end - start,
                "Sample statistics do not cover the recorded ROI interval",
            )
            require(
                math.isclose(
                    cycles, (end - start) / period, rel_tol=1e-12, abs_tol=1e-9
                ),
                "Sample cycles do not match its tick interval",
            )
            row.update(
                start_tick=start,
                end_tick=end,
                elapsed_cycles=cycles,
                clock_period_ticks=period,
                cpu_frequency_hz=2_000_000_000,
                data_prefetchers_disabled=True,
            )
            for key in (
                "system.cpu.numCycles",
                "system.cpu.commitStats0.numInsts",
                "system.cpu.commitStats0.numOps",
            ):
                row[key] = stats.get(key)
            row.update(source_evidence(stats, job, config))
            row["status"] = "PASS"
        except (OSError, ValueError) as error:
            row["reason"] = str(error)
        rows.append(row)
    return config, rows


def run_job(args, job):
    directory = args.output_dir / job.name
    directory.mkdir()
    command = [
        str(args.gem5),
        "--listener-mode=off",
        "-d",
        str(directory),
        str(args.config),
        "--source",
        job.source,
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
        **asdict(job),
        "name": job.name,
        "status": "RUNNING",
        "reason": "",
        "start_time": utc_now(),
        "end_time": None,
        "returncode": None,
        "output_dir": str(directory),
        "command": shlex.join(command),
        "sample_results": [],
    }
    write_json(directory / "command.json", command)
    write_json(directory / "result.json", result)
    started = time.monotonic()
    with (directory / "gem5.log").open("w") as log:
        log.write(
            f"start_time: {result['start_time']}\n"
            f"command: {result['command']}\n"
        )
        log.flush()
        try:
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
                    reason=f"Exceeded {args.timeout:g} seconds",
                )
            if result["status"] != "TIMEOUT":
                require(
                    result["returncode"] == 0,
                    f"gem5 exited with code {result['returncode']}",
                )
                config, rows = validate_job(directory, job)
                result.update(configuration=config, sample_results=rows)
                failed = [row for row in rows if row["status"] != "PASS"]
                result.update(
                    status="FAIL" if failed else "PASS",
                    reason=f"{len(failed)} invalid samples" if failed else "",
                )
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            configparser.Error,
        ) as error:
            result.update(status="FAIL", reason=str(error))
        result.update(
            end_time=utc_now(), wall_seconds=time.monotonic() - started
        )
        for key in ("end_time", "returncode", "status", "reason"):
            log.write(f"\n{key}: {result[key]}")
        log.write("\n")
    write_json(directory / "result.json", result)
    return result


def aggregate(results):
    baselines = {
        (job["source"], job["vlen"], row["sample"]): row["elapsed_cycles"]
        for job in results
        if job["group"] == "B" and job["status"] == "PASS"
        for row in job["sample_results"]
    }
    rows, summary = [], []
    for job in results:
        samples = job["sample_results"]
        net = []
        for sample in samples or [
            {
                "sample": None,
                "status": job["status"],
                "reason": job["reason"],
                "elapsed_cycles": None,
            }
        ]:
            row = {
                key: job[key] for key in ("source", "vlen", "group", "name")
            }
            row.update(
                sample,
                job_status=job["status"],
                output_dir=job["output_dir"],
                baseline_cycles=None,
                net_cycles=None,
            )
            baseline = baselines.get(
                (job["source"], job["vlen"], row["sample"])
            )
            if job["status"] == "PASS" and baseline is not None:
                row.update(
                    baseline_cycles=baseline,
                    net_cycles=row["elapsed_cycles"] - baseline,
                )
                net.append(row["net_cycles"])
            rows.append(row)
        item = {
            key: job[key]
            for key in (
                "source",
                "vlen",
                "group",
                "samples",
                "status",
                "reason",
                "output_dir",
            )
        }
        raw = (
            [row["elapsed_cycles"] for row in samples]
            if job["status"] == "PASS"
            else []
        )
        for label, values in (("raw", raw), ("net", net)):
            for name, function in (
                ("median", statistics.median),
                ("min", min),
                ("max", max),
            ):
                item[f"{label}_{name}_cycles"] = (
                    function(values) if values else None
                )
        summary.append(item)
    return rows, summary


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gem5", type=Path, default=ROOT / "build/RISCV/gem5.opt"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs/dasics/riscv_reg_restore_o3_v5_full.py",
    )
    parser.add_argument(
        "--binary", type=Path, default=TEST_DIR / "build/reg-restore.elf"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=TEST_DIR
        / "build/runs"
        / datetime.now().strftime("restore-%Y%m%d-%H%M%S-%f"),
    )
    parser.add_argument(
        "--source",
        nargs="+",
        choices=("l1", "l2", "dram"),
        default=["l1", "l2", "dram"],
    )
    parser.add_argument(
        "--vlen", nargs="+", type=int, choices=VLENS, default=list(VLENS)
    )
    parser.add_argument(
        "--groups",
        nargs="+",
        choices=("B", "G", "F", "V"),
        default=["B", "G", "F", "V"],
    )
    parser.add_argument("--samples", type=positive_int, default=32)
    parser.add_argument("--jobs", type=positive_int, default=8)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--max-ticks", type=positive_int)
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
    for key in ("source", "vlen", "groups"):
        setattr(args, key, list(dict.fromkeys(getattr(args, key))))
    args.groups = list(dict.fromkeys(["B", *args.groups]))
    return args


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    jobs = [
        RestoreJob(source, vlen, group, args.samples)
        for source in args.source
        for vlen in args.vlen
        for group in args.groups
        if group not in ("G", "F") or vlen == 128
    ]
    manifest = {
        "status": "RUNNING",
        "start_time": utc_now(),
        "end_time": None,
        "returncode": None,
        "hostname": socket.gethostname(),
        "command": shlex.join([sys.executable, *sys.argv]),
        "arguments": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        },
        "jobs": [asdict(job) for job in jobs],
        "cost_definition": "One restore per sample; ROI ticks / clock period",
        "net_definition": (
            "Raw cycles minus B at the same source, VLEN, sample index"
        ),
    }
    write_json(args.output_dir / "finalrun.json", manifest, exclusive=True)
    print(
        f"Host: {manifest['hostname']}; workers: {args.jobs}; "
        f"jobs: {len(jobs)}\n"
        f"Output: {args.output_dir}",
        flush=True,
    )
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_job, args, job) for job in jobs]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            report(
                "OK" if result["status"] == "PASS" else result["status"],
                f"{result['name']} ({result['wall_seconds']:.2f} s) "
                f"{result['reason']}",
            )
    results.sort(key=lambda job: (job["source"], job["vlen"], job["group"]))
    rows, summary = aggregate(results)
    write_table(args.output_dir, "results", rows)
    write_table(args.output_dir, "summary", summary)
    print("\nSource  VLEN  Group  Status     Raw median  Net median")
    for row in summary:
        raw = row["raw_median_cycles"]
        net = row["net_median_cycles"]
        raw = f"{raw:.3f}" if raw is not None else "N/A"
        net = f"{net:.3f}" if net is not None else "N/A"
        print(
            f"{row['source']:6}  {row['vlen']:4}  {row['group']:5}  "
            f"{row['status']:8}"
            f"  {raw:>10}  {net:>10}"
        )
    failed = any(job["status"] != "PASS" for job in results)
    manifest.update(
        status="FAIL" if failed else "PASS",
        end_time=utc_now(),
        returncode=int(failed),
        completed_jobs=len(results),
        passed_samples=sum(row["status"] == "PASS" for row in rows),
    )
    write_json(args.output_dir / "finalrun.json", manifest)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
