# SPDX-License-Identifier: BSD-3-Clause
"""Pair BWaves pow calls from the caller transfer to its retired continuation."""

import configparser
import csv
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

SPEC = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SPEC))
sys.path.insert(0, str(SPEC / "riscv-soplex"))
import run as spec
from strtok_sequences import EVENT

SITE_COUNTS = {
    "flux": 17424,
    "jacobian_first": 52272,
    "jacobian_second": 52272,
    "shell": 17424,
}
HW = (
    "gate_proreg_g",
    "gate_proreg_f",
    "gate_clr_g",
    "gate_clr_f",
    "gate_leave",
)
POLICY_DELTA = {
    "system.cpu.commitStats0.numInsts": 81,
    "system.cpu.commitStats0.numLoadInsts": 24,
    "system.cpu.commitStats0.numStoreInsts": 24,
}
CYCLES = "system.cpu.numCycles"


def probe_targets(markers, sites, mode):
    if (
        len(sites) != len(SITE_COUNTS)
        or set(sites.values()) != SITE_COUNTS.keys()
    ):
        raise ValueError("Expected all four protected pow call sites")
    targets = {
        name: pc
        for name, pc in markers.items()
        if mode == "hw" or name not in HW
    }
    for pc, site in sites.items():
        targets[f"call_{site}"] = pc
        targets[f"resume_{site}"] = pc + 4
    if len(set(targets.values())) != len(targets):
        raise ValueError("Retirement markers alias")
    return targets


def events(m5out, targets):
    names = {pc: name for name, pc in targets.items()}
    seen = dict.fromkeys(targets, 0)
    previous = 0
    trace = m5out / "retire.log"
    with trace.open() as stream:
        for number, line in enumerate(stream, 1):
            if "retired pc=" not in line:
                continue
            match = EVENT.fullmatch(line)
            if not match:
                raise ValueError(f"{trace}:{number}: malformed retirement")
            tick, pc, count = match.groups()
            name = names.get(int(pc, 16))
            tick, count = int(tick), int(count)
            if not name or tick < previous or count != seen[name] + 1:
                raise ValueError(f"{trace}:{number}: inconsistent retirement")
            seen[name] = count
            previous = tick
            yield name, tick, count
    if seen != json.loads((m5out / "retired-pcs.json").read_text()):
        raise ValueError(f"{trace}: probe totals disagree with trace")
    error_count = sum(
        count
        for name, count in seen.items()
        if name in ("b_pow_error", "canary_fail") or name.startswith("error_")
    )
    if seen["main"] != 1 or error_count:
        raise ValueError(f"{trace}: unexpected main or pow error count")
    if any(
        seen[f"call_{site}"] != calls for site, calls in SITE_COUNTS.items()
    ):
        raise ValueError(f"{trace}: unexpected one-step call counts")


def windows(m5out, targets, mode, period):
    # The probes are in retirement order even when several retire on one tick.
    inside = ["pow_gate"]
    if mode == "hw":
        inside.extend(HW[:-1])
    inside.extend(("gate_call", "b_pow", "gate_return"))
    if mode == "hw":
        inside.append("gate_leave")
    inside.append("gate_ret")
    stream = events(m5out, targets)
    for name, start, occurrence in stream:
        if name == "main":
            continue
        if not name.startswith("call_"):
            raise ValueError(f"{mode}: unexpected {name} outside a call")
        site = name.removeprefix("call_")
        for wanted in (*inside, f"resume_{site}"):
            actual, end, _ = next(stream, (None, None, None))
            if actual != wanted:
                raise ValueError(
                    f"{mode}/{name} #{occurrence}: expected {wanted}, got {actual}"
                )
        cycles, remainder = divmod(end - start, period)
        if remainder:
            raise ValueError(
                f"{mode}/{name} #{occurrence}: fractional CPU cycle"
            )
        yield site, occurrence, start, end, cycles


def load(batch, markers, sites, mode):
    m5out = batch / mode / "m5out"
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(m5out / "config.ini")
    period = int(cfg[cfg["system.cpu"]["clk_domain"]]["clock"])
    stats = {
        key: spec.last_stat(m5out, key) for key in (CYCLES, *POLICY_DELTA)
    }
    if period <= 0 or any(v is None or v <= 0 for v in stats.values()):
        raise ValueError(f"{m5out}: invalid CPU clock or missing statistics")
    return (
        windows(m5out, probe_targets(markers, sites, mode), mode, period),
        stats,
        period,
    )


def cycle_summary(sw, hw, calls):
    return {
        "calls": calls,
        "sw_cycles": sw,
        "hw_cycles": hw,
        "mean_sw_cycles": sw / calls,
        "mean_hw_cycles": hw / calls,
        "saved_cycles": sw - hw,
        "mean_saved_cycles": (sw - hw) / calls,
        "saved_percent": 100 * (sw - hw) / sw,
    }


def compare(batch, markers, sites):
    sw, sw_stats, period = load(batch, markers, sites, "sw")
    hw, hw_stats, hw_period = load(batch, markers, sites, "hw")
    if period != hw_period:
        raise ValueError("SW and HW CPU clock periods differ")
    call_pcs = {site: pc for pc, site in sites.items()}
    sw_sum, hw_sum = Counter(), Counter()
    temporary = batch / "paired-calls.csv.gz.tmp"
    try:
        with gzip.open(temporary, "wt", newline="") as out:
            writer = csv.writer(out)
            writer.writerow(
                (
                    "call",
                    "site",
                    "call_pc",
                    "resume_pc",
                    "site_occurrence",
                    "sw_call_tick",
                    "sw_resume_tick",
                    "sw_cycles",
                    "hw_call_tick",
                    "hw_resume_tick",
                    "hw_cycles",
                    "saved_cycles",
                )
            )
            for number, (left, right) in enumerate(
                zip(sw, hw, strict=True), 1
            ):
                site, occurrence = left[:2]
                if left[:2] != right[:2]:
                    raise ValueError(
                        f"Call {number}: site or occurrence differs"
                    )
                pc = call_pcs[site]
                writer.writerow(
                    (
                        number,
                        site,
                        hex(pc),
                        hex(pc + 4),
                        occurrence,
                        *left[2:],
                        *right[2:],
                        left[4] - right[4],
                    )
                )
                sw_sum[site] += left[4]
                hw_sum[site] += right[4]
        temporary.replace(batch / "paired-calls.csv.gz")
    finally:
        temporary.unlink(missing_ok=True)
    calls = sum(SITE_COUNTS.values())
    window = cycle_summary(sum(sw_sum.values()), sum(hw_sum.values()), calls)
    outside_sw = sw_stats[CYCLES] - window["sw_cycles"]
    outside_hw = hw_stats[CYCLES] - window["hw_cycles"]
    if min(outside_sw, outside_hw) < 0:
        raise ValueError("Call windows exceed whole-program cycles")
    whole = sw_stats[CYCLES] - hw_stats[CYCLES]
    observed = {key: sw_stats[key] - hw_stats[key] for key in POLICY_DELTA}
    predicted = {key: delta * calls for key, delta in POLICY_DELTA.items()}
    report = {
        "status": "PASS" if observed == predicted else "COUNTER_MISMATCH",
        "timesteps": 1,
        "cpu_ticks_per_cycle": period,
        "window": window,
        "by_site": {
            site: cycle_summary(sw_sum[site], hw_sum[site], n)
            for site, n in SITE_COUNTS.items()
        },
        "whole_program": {
            "sw": sw_stats,
            "hw": hw_stats,
            "saved_cycles": whole,
            "saved_percent": 100 * whole / sw_stats[CYCLES],
            "outside_windows_sw_cycles": outside_sw,
            "outside_windows_hw_cycles": outside_hw,
            "outside_windows_saved_cycles": outside_sw - outside_hw,
            "observed_retired_deltas": observed,
            "expected_retired_deltas": predicted,
        },
    }
    spec.write_result(batch / "summary.json", report)
    return report
