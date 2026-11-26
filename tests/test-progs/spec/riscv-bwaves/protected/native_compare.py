# SPDX-License-Identifier: BSD-3-Clause
"""Compare ordinary one-step BWaves with the previously measured DASICS gates."""

import configparser
import csv
import gzip
import json
from collections import Counter

from compare import (
    CYCLES,
    POLICY_DELTA,
    SITE_COUNTS,
    events,
    spec,
)


def model_config(path, protected):
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    with path.open() as source:
        cfg.read_file(source)
    if cfg.getboolean("system.workload", "dasics_init") != protected:
        raise ValueError(f"{path}: unexpected DASICS process initialization")
    # The ELF, output destinations, monitored PCs and domain initialization
    # vary by design. All other simulator configuration must match.
    cfg.remove_option("system.workload", "dasics_init")
    for key in ("cmd", "cwd", "executable", "output", "errout"):
        cfg.remove_option("system.cpu.workload", key)
    for section in ("system.pc_counts", "system.cpu.probeListener"):
        cfg.remove_option(section, "targets")
    return cfg


def costs(native, sw, hw, calls=None):
    if native <= 0:
        raise ValueError("Expected a positive ordinary cycle count")
    extra = {"sw": sw - native, "hw": hw - native}
    cycles = {"native": native, "sw": sw, "hw": hw}
    result = {
        "cycles": cycles,
        "extra_cycles": extra,
        "overhead_percent": {
            mode: 100 * delta / native for mode, delta in extra.items()
        },
        "saved_fraction_of_sw_overhead_percent": (
            100 * (sw - hw) / extra["sw"] if extra["sw"] > 0 else None
        ),
    }
    if calls is not None:
        result.update(
            calls=calls,
            mean_cycles={k: v / calls for k, v in cycles.items()},
            mean_extra_cycles={k: v / calls for k, v in extra.items()},
        )
    return result


def match_calls(source, output, m5out, targets, sites, period):
    # Linking moves the call and return PCs. The Fortran site and its
    # invocation index still describe the same dynamic call in each ELF.
    stream = events(m5out, targets)
    if next(stream, (None,))[0] != "main":
        raise ValueError("Expected main before the first Fortran call")
    native_pcs = {site: pc for pc, site in sites.items()}
    totals = {mode: Counter() for mode in ("native", "sw", "hw")}
    output.writerow(
        (
            "call",
            "site",
            "site_occurrence",
            "native_call_pc",
            "native_resume_pc",
            "native_call_tick",
            "native_resume_tick",
            "native_cycles",
            "sw_cycles",
            "hw_cycles",
        )
    )
    for number, row in enumerate(csv.DictReader(source), 1):
        site, occurrence = row["site"], int(row["site_occurrence"])
        if int(row["call"]) != number or site not in native_pcs:
            raise ValueError(f"Invalid paired call {number}")
        times = []
        for name, counter in (
            (f"call_{site}", occurrence),
            ("pow", number),
            (f"resume_{site}", occurrence),
        ):
            actual, tick, index = next(stream, (None, None, None))
            if (actual, index) != (name, counter):
                raise ValueError(f"Call {number}: expected {name} #{counter}")
            times.append(tick)
        cycles, remainder = divmod(times[2] - times[0], period)
        if remainder:
            raise ValueError(f"Call {number}: fractional ordinary CPU cycle")
        sw, hw = int(row["sw_cycles"]), int(row["hw_cycles"])
        totals["native"][site] += cycles
        totals["sw"][site] += sw
        totals["hw"][site] += hw
        pc = native_pcs[site]
        output.writerow(
            (
                number,
                site,
                occurrence,
                hex(pc),
                hex(pc + 4),
                times[0],
                times[2],
                cycles,
                sw,
                hw,
            )
        )
    # Consuming the final event also checks every trace count against gem5.
    if next(stream, None) is not None:
        raise ValueError("Unpaired ordinary retirement events")
    return totals


def compare_native(paired_batch, batch, targets, sites):
    paired = json.loads((paired_batch / "summary.json").read_text())
    if paired["status"] != "PASS" or paired["timesteps"] != 1:
        raise ValueError("Expected a passing one-step paired run")
    m5out = batch / "m5out"
    cfg = model_config(m5out / "config.ini", False)
    period = int(cfg[cfg["system.cpu"]["clk_domain"]]["clock"])
    if period <= 0 or period != paired["cpu_ticks_per_cycle"]:
        raise ValueError("Ordinary and protected CPU clock periods differ")
    stats = {}
    for mode, directory in (
        ("native", m5out),
        ("sw", paired_batch / "sw/m5out"),
        ("hw", paired_batch / "hw/m5out"),
    ):
        stats[mode] = {
            key: spec.last_stat(directory, key)
            for key in (CYCLES, *POLICY_DELTA)
        }
        if any(value is None or value <= 0 for value in stats[mode].values()):
            raise ValueError(f"{directory}: missing completion statistics")
        if mode != "native":
            if model_config(directory / "config.ini", True) != cfg:
                raise ValueError(
                    f"{mode} and ordinary model configurations differ"
                )
            if stats[mode] != paired["whole_program"][mode]:
                raise ValueError(
                    f"{mode} final statistics differ from paired run"
                )
    temporary = batch / "three-way-calls.csv.gz.tmp"
    try:
        with (
            gzip.open(
                paired_batch / "paired-calls.csv.gz", "rt", newline=""
            ) as src,
            gzip.open(temporary, "wt", newline="") as dst,
        ):
            totals = match_calls(
                src, csv.writer(dst), m5out, targets, sites, period
            )
        sums = {
            mode: sum(per_site.values()) for mode, per_site in totals.items()
        }
        for mode in ("sw", "hw"):
            key = f"{mode}_cycles"
            if sums[mode] != paired["window"][key] or any(
                totals[mode][site] != paired["by_site"][site][key]
                or count != paired["by_site"][site]["calls"]
                for site, count in SITE_COUNTS.items()
            ):
                raise ValueError(
                    f"{mode} window cycles differ from paired summary"
                )
        temporary.replace(batch / "three-way-calls.csv.gz")
    finally:
        temporary.unlink(missing_ok=True)
    whole = {mode: data[CYCLES] for mode, data in stats.items()}
    outside = {mode: n - sums[mode] for mode, n in whole.items()}
    report = {
        "status": "PASS",
        "timesteps": 1,
        "cpu_ticks_per_cycle": period,
        "by_site": {
            site: costs(**{k: v[site] for k, v in totals.items()}, calls=count)
            for site, count in SITE_COUNTS.items()
        },
        "window": costs(**sums, calls=sum(SITE_COUNTS.values())),
        "whole_program": costs(**whole),
        "outside_windows": costs(**outside),
        "stats": stats,
    }
    spec.write_result(batch / "summary.json", report)
    return report
