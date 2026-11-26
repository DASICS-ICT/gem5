# SPDX-License-Identifier: BSD-3-Clause
"""Pair retired caller-to-continuation intervals for the two fmod gates."""

import argparse
import configparser
import csv
import json
import re
import statistics
import subprocess
from collections import (
    Counter,
    defaultdict,
)
from pathlib import Path

from check import (
    CALLS,
    gate_targets,
    spec,
)
from check_layout import call_sites

EVENT = re.compile(
    r"^\s*(\d+): system\.pc_counts: retired pc=(0x[0-9a-f]+) count=(\d+)\s*$",
    re.IGNORECASE,
)


def windows(
    trace,
    sites,
    inner,
    period,
    targets,
    final_counts,
    *,
    expected_calls=CALLS,
    outside_pcs=(),
):
    """Match events in retirement order, including instructions on the same tick."""
    seen = Counter()
    expected = []
    ticks = []
    rows = []
    previous = 0
    with trace.open() as stream:
        for line_no, line in enumerate(stream, 1):
            if "retired pc=" not in line.lower():
                continue
            match = EVENT.fullmatch(line)
            if not match:
                raise ValueError(f"{trace}:{line_no}: malformed retirement")
            tick, pc, count = match.groups()
            tick, pc = int(tick), int(pc, 16)
            seen[pc] += 1
            if tick < previous or seen[pc] != int(count):
                raise ValueError(
                    f"{trace}:{line_no}: unordered event at {pc:#x}"
                )
            previous = tick
            if pc in outside_pcs:
                if expected:
                    raise ValueError(
                        f"{trace}:{line_no}: unexpected PC inside a call window"
                    )
                continue
            if not expected:
                if pc not in sites:
                    raise ValueError(
                        f"{trace}:{line_no}: expected a caller, got {pc:#x}"
                    )
                expected = [pc, *inner, sites[pc][1]]
            if pc != expected[len(ticks)]:
                raise ValueError(
                    f"{trace}:{line_no}: expected {expected[len(ticks)]:#x}, got {pc:#x}"
                )
            ticks.append(tick)
            if len(ticks) == len(expected):
                start_pc = expected[0]
                cycles, remainder = divmod(tick - ticks[0], period)
                if remainder:
                    raise ValueError(
                        f"{trace}:{line_no}: fractional CPU cycle"
                    )
                rows.append((start_pc, seen[start_pc], ticks[0], tick, cycles))
                ticks = []
                expected = []
    if expected or len(rows) != expected_calls:
        raise ValueError(
            f"{trace}: expected {expected_calls} complete windows, got {len(rows)}"
        )
    for name, pc in targets.items():
        if seen[pc] != final_counts[name]:
            raise ValueError(
                f"{trace}: {name} trace count differs from probe total"
            )
    return rows


def load_run(runs, baseline, variant):
    directory = runs / variant
    m5out = directory / "m5out"
    result = json.loads((directory / "result.json").read_text())
    if (
        result["status"] != "OK"
        or result["variant"] != variant
        or result["input"] != "test"
    ):
        raise ValueError(
            f"{directory}: expected a passing beampic {variant} run"
        )
    elf = Path(result["elf"])
    sites = {
        call: (caller, resume)
        for caller in ("Drand_setSeed", "Drand_value")
        for call, resume in call_sites(elf, caller)
    }
    targets = gate_targets(elf, variant)
    order = ["call", "body", "return", "ret"]
    if variant == "gf":
        order = [
            "proreg_g",
            "proreg_f",
            "call",
            "body",
            "return",
            "leave",
            "ret",
        ]
    inner = [targets[f"dasics_fmod_{name}"] for name in order]
    for call, (_, resume) in sites.items():
        targets[f"call_{call:x}"] = call
        targets[f"resume_{call:x}"] = resume

    config = configparser.ConfigParser(interpolation=None)
    config.read(m5out / "config.ini")
    period = int(config[config["system.cpu"]["clk_domain"]]["clock"])
    if period <= 0:
        raise ValueError(f"Invalid CPU clock in {m5out}")
    rows = windows(
        m5out / "retire.log",
        sites,
        inner,
        period,
        targets,
        result["retired_pcs"],
    )
    stats = {}
    for name in ("system.cpu.numCycles", "simInsts"):
        value = spec.last_stat(m5out, name)
        reference = spec.last_stat(baseline / variant / "m5out", name)
        if value is None or value != reference:
            raise ValueError(
                f"{variant}: {name} {value} differs from baseline {reference}"
            )
        stats[name] = value
    return sites, period, rows, stats


def summary(rows):
    saved = [row["saved_cycles"] for row in rows]
    return {
        "calls": len(rows),
        "mean_sw_cycles": statistics.mean(row["sw_cycles"] for row in rows),
        "mean_gf_cycles": statistics.mean(row["gf_cycles"] for row in rows),
        "saved_cycles_total": sum(saved),
        "mean_saved_cycles": statistics.mean(saved),
        "median_saved_cycles": statistics.median(saved),
        "min_saved_cycles": min(saved),
        "max_saved_cycles": max(saved),
        "gf_faster": sum(x > 0 for x in saved),
        "equal": saved.count(0),
        "gf_slower": sum(x < 0 for x in saved),
    }


def compare(runs, baseline, outdir):
    sites, period, sw, sw_stats = load_run(runs, baseline, "sw")
    gf_sites, gf_period, gf, gf_stats = load_run(runs, baseline, "gf")
    if period != gf_period or sites != gf_sites:
        raise ValueError(
            "Caller addresses or CPU clock periods differ between variants"
        )
    rows = []
    groups = defaultdict(list)
    for sequence, (left, right) in enumerate(zip(sw, gf, strict=True), 1):
        call, occurrence, start, end, cycles = left
        gf_call, gf_occurrence, gf_start, gf_end, gf_cycles = right
        if (call, occurrence) != (gf_call, gf_occurrence):
            raise ValueError(
                f"Different caller or occurrence at invocation {sequence}"
            )
        caller, resume = sites[call]
        row = {
            "invocation": sequence,
            "caller": caller,
            "call_pc": hex(call),
            "resume_pc": hex(resume),
            "site_occurrence": occurrence,
            "sw_start_tick": start,
            "sw_resume_tick": end,
            "gf_start_tick": gf_start,
            "gf_resume_tick": gf_end,
            "sw_cycles": cycles,
            "gf_cycles": gf_cycles,
            "saved_cycles": cycles - gf_cycles,
        }
        rows.append(row)
        groups[call].append(row)

    all_calls = summary(rows)
    whole = sw_stats["system.cpu.numCycles"] - gf_stats["system.cpu.numCycles"]
    report = {
        "cpu_ticks_per_cycle": period,
        "all_calls": all_calls,
        "by_call_site": {
            hex(pc): {"caller": sites[pc][0], **summary(groups[pc])}
            for pc in sorted(groups)
        },
        "whole_program": {
            "sw": sw_stats,
            "gf": gf_stats,
            "saved_cycles": whole,
            "outside_windows_saved_cycles": whole
            - all_calls["saved_cycles_total"],
        },
    }
    outdir.mkdir(parents=True, exist_ok=True)
    with (outdir / "paired-calls.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    (outdir / "paired-summary.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        f"{len(rows)} paired calls; mean savings {all_calls['mean_saved_cycles']:.3f} cycles/call"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    try:
        compare(args.runs, args.baseline, args.outdir)
    except (
        OSError,
        ValueError,
        KeyError,
        configparser.Error,
        subprocess.CalledProcessError,
    ) as error:
        parser.exit(1, f"[FAIL] {error}\n")
