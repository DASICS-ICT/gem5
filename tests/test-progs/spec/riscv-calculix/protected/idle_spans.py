# SPDX-License-Identifier: BSD-3-Clause
"""Attribute O3 idleCycles to the callback that first rescheduled the CPU."""

import argparse
import configparser
import csv
import json
import re
from bisect import (
    bisect_left,
    bisect_right,
)
from collections import Counter
from pathlib import Path
from typing import NamedTuple

from tail_stats import (
    counter_names,
    cutoff_tick,
    dumps,
)


class Event(NamedTuple):
    tick: int
    cycle: int
    reason: str = ""
    last: int = 0
    credited: int = 0
    edge: int = 0


PAUSE = re.compile(r"\s*(\d+): system\.cpu: idle-pause cycle=(\d+)\s*")
WAKE = re.compile(
    r"\s*(\d+): system\.cpu: idle-wake reason=(\w+) cycle=(\d+) "
    r"last=(\d+) credited=(\d+) edge=(\d+)\s*"
)


def read_events(path, period):
    events = []
    with path.open() as stream:
        for line_no, line in enumerate(stream, 1):
            if "idle-pause" in line:
                match = PAUSE.fullmatch(line)
                if not match:
                    raise ValueError(f"{path}:{line_no}: malformed pause")
                event = Event(*map(int, match.groups()))
                if event.tick != event.cycle * period:
                    raise ValueError(
                        f"{path}:{line_no}: pause off the CPU edge"
                    )
            elif "idle-wake" in line:
                match = WAKE.fullmatch(line)
                if not match:
                    raise ValueError(f"{path}:{line_no}: malformed wake")
                tick, reason, cycle, last, credit, edge = match.groups()
                event = Event(
                    int(tick),
                    int(cycle),
                    reason,
                    int(last),
                    int(credit),
                    int(edge),
                )
                if (
                    not event.tick <= event.edge < event.tick + period
                    or event.edge != event.cycle * period
                    or event.cycle < event.last
                    or event.credited != max(event.cycle - event.last - 1, 0)
                ):
                    raise ValueError(
                        f"{path}:{line_no}: wake accounting mismatch"
                    )
            else:
                continue
            if events and event.tick < events[-1].tick:
                raise ValueError(
                    f"{path}:{line_no}: trace tick moved backwards"
                )
            events.append(event)
    return events


def counts(events):
    return (
        sum(not event.reason for event in events),
        sum(event.credited for event in events),
    )


def snapshot_split(events, tick, target):
    # A Python snapshot is delivered after the O3 tick. A callback at the
    # same tick can be ordered on either side; use the actual snapshot totals.
    ticks = [event.tick for event in events]
    left, right = bisect_left(ticks, tick), bisect_right(ticks, tick)
    splits = [
        i for i in range(left, right + 1) if counts(events[:i]) == target
    ]
    if len(splits) != 1:
        raise ValueError(
            f"Cannot place snapshot at tick {tick}: counts {target}, splits {splits}"
        )
    return splits[0]


def group(reason):
    if reason == "icache_response":
        return "instruction_cache_response"
    if reason.startswith("dcache_") and reason.endswith("_response"):
        return "data_cache_response"
    return reason


def intervals(events, split, final_tick, gate):
    pending = None
    rows = []
    for index, event in enumerate(events):
        if index < split:
            pending = (index, event) if not event.reason else None
            continue
        if event.tick > final_tick:
            raise ValueError(f"{gate}: event after simulation exit")
        if not event.reason:
            if pending:
                raise ValueError(
                    f"{gate} at {event.tick}: two pauses without an effective wake"
                )
            pending = (index, event)
            continue
        if not pending or pending[1].cycle != event.last:
            raise ValueError(
                f"{gate} at {event.tick}: no pause matching lastRunningCycle {event.last}"
            )
        start_index, pause = pending
        rows.append(
            {
                "gate": gate,
                "status": (
                    "crosses_snapshot" if start_index < split else "complete"
                ),
                "pause_tick": pause.tick,
                "pause_cycle": pause.cycle,
                "wake_tick": event.tick,
                "wake_cycle": event.cycle,
                "resume_edge_tick": event.edge,
                "elapsed_ticks": event.tick - pause.tick,
                "edge_cycles": event.cycle - pause.cycle,
                "idle_cycles": event.credited,
                "category": group(event.reason),
                "reason": event.reason,
            }
        )
        pending = None
    if pending:
        start_index, pause = pending
        rows.append(
            {
                "gate": gate,
                "status": (
                    "open_at_exit"
                    if start_index >= split
                    else "open_across_snapshot_and_exit"
                ),
                "pause_tick": pause.tick,
                "pause_cycle": pause.cycle,
            }
        )
    return rows


def load(gate, runs, baseline):
    new, ref = runs / gate, baseline / gate
    result, old = (
        json.loads((p / "result.json").read_text()) for p in (new, ref)
    )
    for record in (result, old):
        passed = {
            item["file"]: item["status"] for item in record["comparisons"]
        }
        if (
            record["status"] != "OK"
            or record["returncode"] != 0
            or passed
            != {"beampic.dat": "PASS", "SPECtestformatmodifier_z.txt": "PASS"}
        ):
            raise ValueError(f"{gate}: invalid beampic result")
    for name in ("variant", "input", "elf", "retired_pcs"):
        if result[name] != old[name]:
            raise ValueError(f"{gate}: reference differs at {name}")
    new, ref = new / "m5out", ref / "m5out"
    names = set(counter_names())
    current = dumps(new / "stats.txt", names, 2)
    previous = dumps(ref / "stats.txt", names, 2)
    for block, (a, b) in enumerate(zip(current, previous)):
        for key in names:
            if key not in a or a[key] != b.get(key):
                raise ValueError(f"{gate}: snapshot {block} differs at {key}")
    marker = json.loads((new / "retire-snapshot.json").read_text())
    if marker != json.loads((ref / "retire-snapshot.json").read_text()):
        raise ValueError(f"{gate}: retirement snapshot differs from reference")
    cutoff, finish = (block["finalTick"][0] for block in current)
    if marker["tick"] != cutoff or cutoff_tick(new / "retire.log") != cutoff:
        raise ValueError(
            f"{gate}: last fmod retirement does not match snapshot"
        )
    config = configparser.ConfigParser(interpolation=None)
    config.read(new / "config.ini")
    period = int(config[config["system.cpu"]["clk_domain"]]["clock"])
    events = read_events(new / "retire.log", period)
    prefix, total = (
        tuple(
            block["system.cpu." + key][0]
            for key in ("timesIdled", "idleCycles")
        )
        for block in current
    )
    if counts(events) != total:
        raise ValueError(
            f"{gate}: whole trace {counts(events)} differs from CPU counters {total}"
        )
    split = snapshot_split(events, cutoff, prefix)
    rows = intervals(events, split, finish, gate)
    pauses, idle = counts(events[split:])
    if sum(row.get("idle_cycles", 0) for row in rows) != idle:
        raise ValueError(
            f"{gate}: interval accounting differs from idleCycles"
        )
    return rows, {
        "snapshot_tick": cutoff,
        "final_tick": finish,
        "ticks_per_cycle": period,
        "times_idled": pauses,
        "effective_wakes": sum("reason" in row for row in rows),
        "open_at_exit": sum("reason" not in row for row in rows),
        "crosses_snapshot": sum("snapshot" in row["status"] for row in rows),
        "zero_credit_wakes": sum(row.get("idle_cycles") == 0 for row in rows),
        "idle_cycles": idle,
        "verified_counters_per_dump": len(names),
    }


def totals(rows, key):
    counts_by = Counter((r["gate"], r[key]) for r in rows if key in r)
    cycles_by = Counter()
    for row in rows:
        if key in row:
            cycles_by[row["gate"], row[key]] += row["idle_cycles"]
    groups = []
    for reason in sorted({name for gate, name in counts_by}):
        item = {key: reason}
        for gate in ("sw", "gf"):
            n, cycles = counts_by[gate, reason], cycles_by[gate, reason]
            item.update(
                {
                    f"{gate}_wakes": n,
                    f"{gate}_idle_cycles": cycles,
                    f"{gate}_mean_idle_cycles": cycles / n if n else None,
                }
            )
        for field in ("wakes", "idle_cycles"):
            item["sw_minus_gf_" + field] = (
                item["sw_" + field] - item["gf_" + field]
            )
        groups.append(item)
    return groups


def csv_table(path, rows, fields):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def compare(runs, baseline, outdir):
    all_rows, metrics = [], {}
    for gate in ("sw", "gf"):
        rows, metrics[gate] = load(gate, runs, baseline)
        all_rows.extend(rows)
    reasons = totals(all_rows, "reason")
    categories = totals(all_rows, "category")
    savings = metrics["sw"]["idle_cycles"] - metrics["gf"]["idle_cycles"]
    if sum(row["sw_minus_gf_idle_cycles"] for row in reasons) != savings:
        raise ValueError("Attributed cycles do not match the tail difference")
    outdir.mkdir(parents=True, exist_ok=True)
    csv_table(
        outdir / "wake-intervals.csv",
        all_rows,
        (
            "gate",
            "status",
            "pause_tick",
            "pause_cycle",
            "wake_tick",
            "wake_cycle",
            "resume_edge_tick",
            "elapsed_ticks",
            "edge_cycles",
            "idle_cycles",
            "category",
            "reason",
        ),
    )
    csv_table(outdir / "wake-by-reason.csv", reasons, reasons[0].keys())
    summary = {
        "runs": metrics,
        "idle_cycles_sw_minus_gf": savings,
        "by_category": categories,
        "by_reason": reasons,
    }
    (outdir / "wake-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    print(f"{savings} tail idle cycles attributed by effective wake source")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    try:
        compare(args.runs, args.baseline, args.outdir)
    except (OSError, ValueError, KeyError, configparser.Error) as err:
        parser.exit(1, f"[FAIL] {err}\n")
