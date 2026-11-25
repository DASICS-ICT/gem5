# SPDX-License-Identifier: BSD-3-Clause
"""Compare cumulative v5_full counters after the last beampic fmod return."""

import argparse
import configparser
import csv
import json
import re
from pathlib import Path

from check import (
    TAIL_OCCURRENCE,
    TAIL_PC,
)
from paired_calls import EVENT


def counter_names():
    """Select additive counts, durations and byte traffic with known semantics."""
    groups = {
        "": "finalTick simTicks simInsts simOps",
        "system.cpu.": "numCycles idleCycles timesIdled",
        "system.cpu.commitStats0.": "numLoadInsts numStoreInsts numFpInsts",
        "system.cpu.commit.": "commitNonSpecStalls branchMispredicts commitSquashedInsts numCommittedDist::samples numCommittedDist::0",
        "system.cpu.fetchStats0.": "icacheStallCycles numInsts",
        "system.cpu.fetch.": "icacheSquashes status::ftqWait status::icacheWaitRetry",
        "system.cpu.branchPred.": "mispredicted_0::total mispredicted_0::DirectCond mispredicted_0::Return",
        "system.cpu.rename.": "status::Blocked status::SerializeStall status::Squashing ROBFullEvents SQFullEvents",
        "system.cpu.iew.": "iqFullEvents lsqFullEvents memOrderViolationEvents dispLoadInsts dispStoreInsts",
        "system.cpu.lsq0.": "forwLoads squashedLoads squashedStores rescheduledLoads blockedByCache",
        "system.cpu.dcache.": (
            "ReadReq.misses::total ReadReq.missLatency::total "
            "WriteReq.accesses::total WriteReq.misses::total "
            "WriteReq.missLatency::total WriteReq.mshrHits::total "
            "WriteReq.mshrMisses::total"
        ),
        "system.mem_ctrl.dram.": "readBursts writeBursts readRowHits writeRowHits bytesRead::total bytesWritten::total totQLat totBusLat totMemAccLat",
    }
    names = [
        prefix + key for prefix, keys in groups.items() for key in keys.split()
    ]
    for cache in ("cpu.icache", "cpu.dcache", "l20", "l21", "l30", "l31"):
        keys = [
            "demandAccesses::total",
            "demandMisses::total",
            "demandMshrMisses::total",
            "demandMissLatency::total",
        ]
        if cache.startswith("cpu."):
            keys += ["blockedCycles::no_mshrs", "blockedCycles::no_targets"]
        if not cache.startswith("l3"):
            keys += ["prefetcher.pfIssued", "prefetcher.pfUseful"]
        names.extend(f"system.{cache}.{key}" for key in keys)
    return names


def dumps(path, names, expected):
    blocks = []
    current = None
    for line in path.read_text().splitlines():
        if line.startswith("---------- Begin Simulation Statistics"):
            if current is not None:
                raise ValueError(f"Incomplete stats block in {path}")
            current = {}
        elif line.startswith("---------- End Simulation Statistics"):
            if current is None:
                raise ValueError(f"Unexpected end of stats in {path}")
            blocks.append(current)
            current = None
        elif (
            current is not None
            and (fields := line.split())
            and fields[0] in names
        ):
            name = fields[0]
            unit = re.search(r"\((Count|Cycle|Tick|Byte)\)\s*$", line)
            if not unit or not fields[1].isdigit() or name in current:
                raise ValueError(
                    f"Invalid cumulative counter {name} in {path}"
                )
            current[name] = (int(fields[1]), unit[1])
    if current is not None or len(blocks) != expected:
        raise ValueError(
            f"Expected {expected} complete statistics dumps in {path}"
        )
    return blocks


def cutoff_tick(trace):
    last = None
    with trace.open() as stream:
        for line in stream:
            match = EVENT.fullmatch(line)
            if match:
                last = (int(match[2], 16), int(match[3]), int(match[1]))
    if last is None or last[:2] != (TAIL_PC, TAIL_OCCURRENCE):
        raise ValueError(
            f"The baseline trace does not end at the last fmod return: {trace}"
        )
    return last[2]


def load_run(directory, reference, names):
    m5out = directory / "m5out"
    result = json.loads((directory / "result.json").read_text())
    previous = json.loads((reference / "result.json").read_text())
    if result["elf"] != previous["elf"]:
        raise ValueError(f"Expected the paired reference ELF in {directory}")
    for run in (result, previous):
        outputs = {item["file"]: item["status"] for item in run["comparisons"]}
        if (
            run["status"] != "OK"
            or run["returncode"] != 0
            or run["input"] != "test"
            or run["variant"] != directory.name
            or outputs
            != {"beampic.dat": "PASS", "SPECtestformatmodifier_z.txt": "PASS"}
        ):
            raise ValueError(
                f"Expected passing beampic results for {directory.name}"
            )

    boundary, final = dumps(m5out / "stats.txt", names, 2)
    (old,) = dumps(reference / "m5out/stats.txt", names, 1)
    marker = json.loads((m5out / "retire-snapshot.json").read_text())
    tick = cutoff_tick(reference / "m5out/retire.log")
    if (marker["pc"], marker["count"], marker["tick"]) != (
        TAIL_PC,
        TAIL_OCCURRENCE,
        tick,
    ):
        raise ValueError(
            f"{m5out}: snapshot does not match reference PC, occurrence and tick"
        )
    if boundary["finalTick"][0] != tick or boundary["simTicks"][0] != tick:
        raise ValueError(
            f"{m5out}: stats snapshot does not match the retirement tick"
        )
    for name in (
        "simTicks",
        "finalTick",
        "system.cpu.numCycles",
        "simInsts",
        "simOps",
    ):
        if final[name] != old[name]:
            raise ValueError(
                f"{m5out}: final {name} differs from paired baseline"
            )
    different = [key for key in names if final.get(key) != old.get(key)]
    cpus = configparser.ConfigParser(interpolation=None)
    cpus.read(m5out / "config.ini")
    period = int(cpus[cpus["system.cpu"]["clk_domain"]]["clock"])
    cycles, remainder = divmod(final["finalTick"][0] - tick, period)
    if remainder or cycles <= 0:
        raise ValueError(
            f"{m5out}: tail does not span whole positive CPU cycles"
        )
    counter_cycles = (
        final["system.cpu.numCycles"][0] - boundary["system.cpu.numCycles"][0]
    )
    return (
        boundary,
        final,
        {
            "cutoff_tick": tick,
            "final_tick": final["finalTick"][0],
            "period": period,
            "elapsed_cycles": cycles,
            "counted_cycles": counter_cycles,
            "counted_minus_elapsed_cycles": counter_cycles - cycles,
            "changed_final_counters_vs_reference": different,
        },
    )


def compare(runs, baseline, outdir):
    names = counter_names()
    runs_data = {
        gate: load_run(runs / gate, baseline / gate, set(names))
        for gate in ("sw", "gf")
    }
    meta = {gate: data[2] for gate, data in runs_data.items()}
    if meta["sw"]["period"] != meta["gf"]["period"]:
        raise ValueError("Different CPU clock periods across variants")
    rows = []
    missing = {}
    for name in names:
        row = {"counter": name}
        units = set()
        for gate, (before, after, _) in runs_data.items():
            for label, block in (("snapshot", before), ("final", after)):
                if name not in block:
                    missing.setdefault(name, []).append(f"{gate}.{label}")
                else:
                    units.add(block[name][1])
                    row[f"{gate}_{label}"] = block[name][0]
            if name in before and name in after:
                value = after[name][0] - before[name][0]
                if value < 0:
                    raise ValueError(
                        f"Decreasing cumulative counter {name} for {gate}"
                    )
                row[f"{gate}_tail"] = value
        if len(units) > 1:
            raise ValueError(f"Inconsistent units for {name}")
        row["unit"] = next(iter(units), "")
        for label in ("final", "tail"):
            if f"sw_{label}" in row and f"gf_{label}" in row:
                row[f"sw_minus_gf_{label}"] = (
                    row[f"sw_{label}"] - row[f"gf_{label}"]
                )
        rows.append(row)
    metrics = {row["counter"]: row for row in rows}
    cpu = metrics["system.cpu.numCycles"]
    idle = metrics["system.cpu.idleCycles"]
    parts = {}
    for gate in ("sw", "gf"):
        key = f"{gate}_tail"
        sampled = metrics["system.cpu.commit.numCommittedDist::samples"][key]
        zero = metrics["system.cpu.commit.numCommittedDist::0"][key]
        parts[gate] = {
            "unscheduled": idle[key],
            "zero_retire_samples": zero,
            "positive_retire_samples": sampled - zero,
            "scheduled_without_commit_sample": cpu[key] - idle[key] - sampled,
        }
    parts["sw_minus_gf"] = {
        k: v - parts["gf"][k] for k, v in parts["sw"].items()
    }
    summary = {
        "cutoff_pc": hex(TAIL_PC),
        "occurrence": TAIL_OCCURRENCE,
        "runs": meta,
        "tail_cycles_sw_minus_gf": meta["sw"]["elapsed_cycles"]
        - meta["gf"]["elapsed_cycles"],
        "cpu_cycle_components": parts,
        "tail_retired_instructions_sw_minus_gf": metrics["simInsts"][
            "sw_minus_gf_tail"
        ],
        "tail_idle_cycles_sw_minus_gf": idle["sw_minus_gf_tail"],
        "tail_scheduled_cycles_sw_minus_gf": cpu["sw_minus_gf_tail"]
        - idle["sw_minus_gf_tail"],
        "boundary_note": "Counters are sampled at the end of the retirement tick, after same-tick CPU activity.",
        "missing_counter_fields": missing,
    }
    outdir.mkdir(parents=True, exist_ok=True)
    with (outdir / "tail-stats.csv").open("w", newline="") as stream:
        columns = (
            "counter",
            "unit",
            "sw_snapshot",
            "gf_snapshot",
            "sw_final",
            "gf_final",
            "sw_minus_gf_final",
            "sw_tail",
            "gf_tail",
            "sw_minus_gf_tail",
        )
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    (outdir / "tail-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    print(
        f"Post-return cycle difference (SW - G/F): {summary['tail_cycles_sw_minus_gf']}"
    )
    for gate in ("sw", "gf"):
        if meta[gate]["counted_minus_elapsed_cycles"]:
            print(
                f"{gate}: CPU counted cycles and elapsed cycles differ; see tail-summary.json"
            )
    if missing:
        print(
            f"{len(missing)} counters have unavailable fields; see tail-summary.json"
        )


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
