# SPDX-License-Identifier: BSD-3-Clause
"""Pair complete SoPlex caller-to-resume windows using host retirement events."""

import configparser
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import NamedTuple

from run_pair import (
    HW,
    read_trace,
    spec,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from strtok_sequences import EVENT

EXPECTED = {"first_token": 2174, "next_token": 6524, "next_null": 898}
CYCLES = "system.cpu.numCycles"
POLICY_DELTA = {
    "system.cpu.commitStats0.numInsts": 81,
    "system.cpu.commitStats0.numLoadInsts": 24,
    "system.cpu.commitStats0.numStoreInsts": 24,
}


def probe_targets(markers, sites, variant):
    targets = {
        name: pc
        for name, pc in markers.items()
        if variant == "hw" or name not in HW
    }
    for call, resume in sites.items():
        targets[f"call_{call:x}"] = call
        targets[f"resume_{call:x}"] = resume
    if len(set(targets.values())) != len(targets) or len(sites) != 5:
        raise ValueError("Expected five call sites and distinct probe PCs")
    return targets


class Window(NamedTuple):
    call: int
    occurrence: int
    category: str
    tick: int
    resume_tick: int
    cycles: int


def retired_events(path, targets, totals):
    names = {pc: name for name, pc in targets.items()}
    seen = dict.fromkeys(targets, 0)
    last_tick = 0
    with path.open() as stream:
        for line_no, line in enumerate(stream, 1):
            if "retired pc=" not in line:
                continue
            match = EVENT.fullmatch(line)
            if not match:
                raise ValueError(f"{path}:{line_no}: malformed retirement")
            tick, pc, count = match.groups()
            tick, pc, count = int(tick), int(pc, 16), int(count)
            name = names.get(pc)
            if not name or tick < last_tick or seen[name] + 1 != count:
                raise ValueError(f"{path}:{line_no}: inconsistent event")
            seen[name] = count
            last_tick = tick
            yield name, tick, count
    if seen != totals:
        raise ValueError(f"{path}: trace and final retired-PC counts differ")


def read_windows(m5out, sites, targets, variant, period):
    # Both classification probes lie inside b___strtok_r. Each can retire
    # at most once, in this order, before B returns across the gate.
    prefix = ["strtok_gate"] if "strtok_gate" in targets else []
    if variant == "hw":
        prefix.extend(HW[:-1])
    prefix.extend(["gate_call", "b_strtok", "b___strtok_r"])
    suffix = (
        ["gate_return", "gate_leave", "gate_ret"]
        if variant == "hw"
        else ["gate_return", "gate_ret"]
    )
    starts = {f"call_{pc:x}": pc for pc in sites}
    totals = json.loads((m5out / "retired-pcs.json").read_text())
    if totals.get("main") != 1 or totals.get("strtok") != 12:
        raise ValueError(f"{m5out}: unexpected main or ordinary strtok count")
    windows = []
    call = None
    inner = []
    for name, tick, count in retired_events(
        m5out / "retire.log", targets, totals
    ):
        if call is None:
            if name in ("main", "strtok"):
                continue
            if name not in starts:
                raise ValueError(f"{variant}: {name} outside a call at {tick}")
            call, start, occurrence = starts[name], tick, count
            continue
        if name == f"resume_{call:x}":
            classification = [
                n for n in ("next_input", "null_result") if n in inner
            ]
            if inner != prefix + classification + suffix:
                raise ValueError(
                    f"{variant}: unexpected path at {call:#x}: {inner}"
                )
            cycles, rem = divmod(tick - start, period)
            if rem or cycles < 0:
                raise ValueError(
                    f"{variant}: invalid retirement interval at {call:#x}"
                )
            kind = "next" if "next_input" in classification else "first"
            result = "null" if "null_result" in classification else "token"
            windows.append(
                Window(
                    call, occurrence, f"{kind}_{result}", start, tick, cycles
                )
            )
            call = None
            inner.clear()
        elif (
            name in starts
            or name.startswith("resume_")
            or name in ("main", "strtok")
        ):
            raise ValueError(
                f"{variant}: unexpected {name} before resume at {call:#x}"
            )
        else:
            inner.append(name)
    if call is not None or Counter(w.category for w in windows) != EXPECTED:
        raise ValueError(
            f"{variant}: incomplete or unexpected call categories"
        )
    return windows


def load(batch, markers, sites, variant):
    m5out = batch / variant / "m5out"
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(m5out / "config.ini")
    period = int(cfg[cfg["system.cpu"]["clk_domain"]]["clock"])
    if period <= 0:
        raise ValueError(f"{m5out}: invalid CPU clock period")
    targets = probe_targets(markers, sites, variant)
    windows = read_windows(m5out, sites, targets, variant, period)
    stats = {
        key: spec.last_stat(m5out, key) for key in (CYCLES, *POLICY_DELTA)
    }
    if any(value is None or value <= 0 for value in stats.values()):
        raise ValueError(f"{m5out}: missing whole-program stats")
    return windows, stats, period


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


def compare(batch, markers, sites, reference_csv):
    sw, sw_stats, period = load(batch, markers, sites, "sw")
    hw, hw_stats, hw_period = load(batch, markers, sites, "hw")
    if period != hw_period:
        raise ValueError("CPU clock periods differ")
    reference = read_trace(reference_csv)
    paired = []
    sw_sums, hw_sums = Counter(), Counter()
    for ordinal, (left, right, ref) in enumerate(
        zip(sw, hw, reference, strict=True), 1
    ):
        kind, offset, _ = ref
        category = f"{kind}_{'null' if offset == -1 else 'token'}"
        if left[:3] != right[:3] or left.category != category:
            raise ValueError(
                f"Invocation {ordinal}: SW, HW or functional trace disagrees"
            )
        sw_sums[category] += left.cycles
        hw_sums[category] += right.cycles
        paired.append(
            (
                ordinal,
                hex(left.call),
                hex(sites[left.call]),
                left.occurrence,
                category,
                left.tick,
                left.resume_tick,
                left.cycles,
                right.tick,
                right.resume_tick,
                right.cycles,
                left.cycles - right.cycles,
            )
        )
    with (batch / "paired-calls.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "call",
                "call_pc",
                "resume_pc",
                "site_occurrence",
                "category",
                "sw_call_tick",
                "sw_resume_tick",
                "sw_cycles",
                "hw_call_tick",
                "hw_resume_tick",
                "hw_cycles",
                "saved_cycles",
            )
        )
        writer.writerows(paired)
    window = cycle_summary(
        sum(sw_sums.values()), sum(hw_sums.values()), len(sw)
    )
    outside_sw = sw_stats[CYCLES] - window["sw_cycles"]
    outside_hw = hw_stats[CYCLES] - window["hw_cycles"]
    if min(outside_sw, outside_hw) < 0:
        raise ValueError(
            "Accumulated call windows exceed whole-program cycles"
        )
    whole = sw_stats[CYCLES] - hw_stats[CYCLES]
    observed = {key: sw_stats[key] - hw_stats[key] for key in POLICY_DELTA}
    predicted = {key: delta * len(sw) for key, delta in POLICY_DELTA.items()}
    report = {
        "status": "PASS" if observed == predicted else "COUNTER_MISMATCH",
        "cpu_ticks_per_cycle": period,
        "window": window,
        "by_category": {
            cat: cycle_summary(sw_sums[cat], hw_sums[cat], count)
            for cat, count in EXPECTED.items()
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
