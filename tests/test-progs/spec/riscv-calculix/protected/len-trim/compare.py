# SPDX-License-Identifier: BSD-3-Clause
"""Pair the selected getnewline_ call windows in two verified beampic runs."""

import argparse
import configparser
import csv
import gzip
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paired_calls import (
    spec,
    windows,
)

HOT_CALLS = 93_148
OTHER_CALLS = 100_617 - HOT_CALLS
BASE_ORDER = (
    "trim_gate",
    "gate_call",
    "b_len_trim",
    "b_ret",
    "gate_return",
    "gate_ret",
)
HW_ORDER = (
    "trim_gate",
    "gate_proreg_g",
    "gate_proreg_f",
    "gate_clr_g",
    "gate_clr_f",
    "gate_call",
    "b_len_trim",
    "b_ret",
    "gate_return",
    "gate_leave",
    "gate_ret",
)
CYCLES = "system.cpu.numCycles"
DELTAS = {
    "system.cpu.commitStats0.numInsts": 81,
    "system.cpu.commitStats0.numLoadInsts": 24,
    "system.cpu.commitStats0.numStoreInsts": 24,
}


def load_run(batch, variant):
    directory = batch / variant
    m5out = directory / "m5out"
    result = json.loads((directory / "result.json").read_text())
    if (
        result["status"] != "PASS"
        or result["variant"] != variant
        or result["guest_exit_code"] != 0
    ):
        raise ValueError(
            f"{directory}: expected a passing {variant} beampic run"
        )
    comparisons = {
        item["file"]: item["status"] for item in result["comparisons"]
    }
    if comparisons != {
        "beampic.dat": "PASS",
        "SPECtestformatmodifier_z.txt": "PASS",
    }:
        raise ValueError(f"{variant}: SPEC outputs differ from the reference")

    targets = result["targets"]
    counts = json.loads((m5out / "retired-pcs.json").read_text())
    order = HW_ORDER if variant == "hw" else BASE_ORDER
    expected = {name: HOT_CALLS for name in ("call_site", *order, "resume")}
    expected["ordinary_trim"] = OTHER_CALLS
    if counts != expected or targets.keys() != expected.keys():
        raise ValueError(
            f"{variant}: unexpected monitored PCs or retirement counts: {counts}"
        )

    config = configparser.ConfigParser(interpolation=None)
    config.read(m5out / "config.ini")
    period = int(config[config["system.cpu"]["clk_domain"]]["clock"])
    if period <= 0:
        raise ValueError(f"{variant}: invalid CPU clock period")
    rows = windows(
        m5out / "retire.log",
        {targets["call_site"]: ("getnewline_", targets["resume"])},
        [targets[name] for name in order],
        period,
        targets,
        counts,
        expected_calls=HOT_CALLS,
        outside_pcs={targets["ordinary_trim"]},
    )
    stats = {key: spec.last_stat(m5out, key) for key in (CYCLES, *DELTAS)}
    if any(value is None or value <= 0 for value in stats.values()):
        raise ValueError(f"{variant}: missing whole-program statistics")
    return targets, period, rows, stats


def compare(batch):
    sw_pcs, period, sw, sw_stats = load_run(batch, "sw")
    hw_pcs, hw_period, hw, hw_stats = load_run(batch, "hw")
    if period != hw_period or any(hw_pcs[k] != pc for k, pc in sw_pcs.items()):
        raise ValueError(
            "Paired variants have different common marker PCs or clock periods"
        )

    savings = Counter()
    with gzip.open(batch / "paired-calls.csv.gz", "wt", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "occurrence",
                "sw_call_tick",
                "sw_resume_tick",
                "sw_cycles",
                "hw_call_tick",
                "hw_resume_tick",
                "hw_cycles",
                "saved_cycles",
            )
        )
        for left, right in zip(sw, hw, strict=True):
            if left[:2] != right[:2]:
                raise ValueError(
                    "Call site or occurrence differs between runs"
                )
            saved = left[4] - right[4]
            writer.writerow((left[1], *left[2:], *right[2:], saved))
            savings[saved] += 1

    sw_window_cycles = sum(row[4] for row in sw)
    hw_window_cycles = sum(row[4] for row in hw)
    in_windows = sw_window_cycles - hw_window_cycles
    if sum(c * n for c, n in savings.items()) != in_windows:
        raise ValueError("Paired differences disagree with window sums")
    outside_sw = sw_stats[CYCLES] - sw_window_cycles
    outside_hw = hw_stats[CYCLES] - hw_window_cycles
    if min(outside_sw, outside_hw) < 0:
        raise ValueError("Call windows exceed whole-program cycles")
    whole = sw_stats[CYCLES] - hw_stats[CYCLES]

    observed = {key: sw_stats[key] - hw_stats[key] for key in DELTAS}
    expected = {key: HOT_CALLS * delta for key, delta in DELTAS.items()}
    report = {
        "status": "PASS" if observed == expected else "COUNTER_MISMATCH",
        "cpu_ticks_per_cycle": period,
        "caller": "getnewline_",
        "call_pc": hex(sw_pcs["call_site"]),
        "resume_pc": hex(sw_pcs["resume"]),
        "paired_calls": HOT_CALLS,
        "unwrapped_calls": OTHER_CALLS,
        "window": {
            "sw_cycles": sw_window_cycles,
            "hw_cycles": hw_window_cycles,
            "mean_sw_cycles": sw_window_cycles / HOT_CALLS,
            "mean_hw_cycles": hw_window_cycles / HOT_CALLS,
            "saved_cycles": in_windows,
            "mean_saved_cycles": in_windows / HOT_CALLS,
            "saved_percent": 100 * in_windows / sw_window_cycles,
            "median_saved_cycles": statistics.median(savings.elements()),
            "min_saved_cycles": min(savings),
            "max_saved_cycles": max(savings),
            "hw_faster": sum(n for t, n in savings.items() if t > 0),
            "equal": savings[0],
            "hw_slower": sum(n for t, n in savings.items() if t < 0),
            "savings_histogram": dict(sorted(savings.items())),
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
            "policy_expected_retired_deltas": expected,
        },
    }
    spec.write_result(batch / "summary.json", report)
    print(
        f"Paired {HOT_CALLS:,} calls; mean savings {in_windows/HOT_CALLS:.4f} cycles/call; "
        f"whole program saved {whole:,} cycles; outside windows {outside_sw-outside_hw:+,}."
    )
    if observed != expected:
        raise ValueError(
            f"Whole-program retired deltas outside the policy prediction: "
            f"observed {observed}, expected {expected}; see summary.json"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, type=Path)
    args = parser.parse_args()
    compare(args.batch.resolve())
