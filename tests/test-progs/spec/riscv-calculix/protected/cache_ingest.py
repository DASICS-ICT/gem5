# SPDX-License-Identifier: BSD-3-Clause
"""Stream replay evidence and retain cache transactions on the selected lines."""

import configparser
import json
from collections import defaultdict

from fetch_requests import original_event
from tail_stats import (
    counter_names,
    dumps,
)


def replay_event(line):
    return (
        b": fetch-r " in line or b": fetch-a " in line or original_event(line)
    )


def number_or_name(value):
    try:
        return int(value, 0)
    except ValueError:
        return value.decode()


def parse_event(line):
    stamp, component, description = line.split(b": ", 2)
    prefix, *fields = description.split()
    if prefix == b"cachepath":
        kind = "mpath"
        op = fields.pop(0).removeprefix(b"mem-").decode()
    elif prefix == b"cpath":
        kind = "cpath"
        op = fields.pop(0).removeprefix(b"op=").decode()
    else:
        raise ValueError(f"Unexpected cache path event: {line!r}")
    result = {
        "tick": int(stamp),
        "component": component.decode(),
        "kind": kind,
        "op": op,
    }
    for field in fields:
        key, value = field.split(b"=", 1)
        result[key.decode()] = number_or_name(value)
    return result


def validate_run(directory, reference):
    a, b = (
        json.loads((d / "result.json").read_text())
        for d in (directory, reference)
    )
    for record in (a, b):
        outputs = {c["file"]: c["status"] for c in record["comparisons"]}
        if (
            record["status"] != "OK"
            or record["returncode"] != 0
            or record["variant"] != directory.name
            or record["input"] != "test"
            or outputs
            != {"beampic.dat": "PASS", "SPECtestformatmodifier_z.txt": "PASS"}
        ):
            raise ValueError(f"Invalid functional run for {directory}")
    for key in ("elf", "retired_pcs"):
        if a[key] != b[key]:
            raise ValueError(f"{directory}: {key} changed in replay")

    new, old = (d / "m5out" for d in (directory, reference))
    names = set(counter_names())
    blocks = dumps(new / "stats.txt", names, 2)
    if blocks != dumps(old / "stats.txt", names, 2) or any(
        set(s) != names for s in blocks
    ):
        raise ValueError(
            f"{directory}: changed or missing cumulative counters"
        )
    marker = json.loads((new / "retire-snapshot.json").read_text())
    if (
        marker != json.loads((old / "retire-snapshot.json").read_text())
        or marker["tick"] != blocks[0]["finalTick"][0]
    ):
        raise ValueError(f"{directory}: retirement snapshot changed")

    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(new / "config.ini")
    period = int(cfg[cfg["system.cpu"]["clk_domain"]]["clock"])
    return {
        "period": period,
        "cache_line_size": int(cfg["system"]["cache_line_size"]),
        "fetch_width": int(cfg["system.cpu"]["fetchBufferSize"]),
        "snapshot_tick": marker["tick"],
        "snapshot_insts": blocks[0]["simInsts"][0],
        "final_tick": blocks[1]["finalTick"][0],
        "verified_counters_per_dump": len(names),
    }


def match_roots(path, previous, gate, pairs, metadata):
    by_send = {int(r[f"{gate}_send_tick"]): r for r in pairs}
    by_return = {int(r[f"{gate}_response_tick"]): r for r in pairs}
    roots = {}
    replies, witnesses = set(), set()
    checked = 0
    line_size = metadata["cache_line_size"]
    with path.open("rb") as current, previous.open("rb") as baseline:
        old = filter(replay_event, baseline)
        for line in current:
            if replay_event(line):
                if line != next(old, None):
                    raise ValueError(f"{gate}: replay event changed: {line!r}")
                checked += 1
                if b": fetch-r " in line:
                    response = int(line.split(b":", 1)[0])
                    pair = by_return.get(response)
                    if pair is None:
                        continue
                    event = dict(x.split(b"=", 1) for x in line.split()[3:])
                    if (
                        response in replies
                        or int(event[b"sent"])
                        != int(pair[f"{gate}_send_tick"])
                        or int(event[b"block"], 16) != int(pair["block"], 16)
                        or int(event[b"pc"], 16)
                        != int(pair[f"{gate}_request_pc"], 16)
                    ):
                        raise ValueError(
                            f"{gate}: invalid O3 response at {response}"
                        )
                    replies.add(response)
                elif b": fetch-a " in line:
                    fields = line.split()
                    response = int(fields[3].removeprefix(b"response="))
                    pair = by_return.get(response)
                    if pair is None:
                        continue
                    if (
                        response in witnesses
                        or int(fields[4][8:]) - metadata["snapshot_insts"]
                        != int(pair["witness_ordinal"])
                        or int(fields[5][3:], 16)
                        != int(pair["witness_pc"], 16)
                    ):
                        raise ValueError(
                            f"{gate}: changed witness for response {response}"
                        )
                    witnesses.add(response)
            elif b": system.cpu.icache: cpath " in line:
                tick = int(line.split(b":", 1)[0])
                pair = by_send.get(tick)
                if pair is None:
                    continue
                e = parse_event(line)
                if e["op"] not in ("hit", "new", "join") or e["pf"]:
                    continue
                if e["va"] != int(pair["block"], 16) or e["pc"] != int(
                    pair[f"{gate}_request_pc"], 16
                ):
                    continue
                if (
                    tick in roots
                    or e["line"] != e["pa"] // line_size * line_size
                    or e["va"] % line_size != e["pa"] % line_size
                ):
                    raise ValueError(
                        f"{gate}: ambiguous or unaligned target at {tick}"
                    )
                roots[tick] = e
        if next(old, None) is not None:
            raise ValueError(f"{gate}: truncated replay trace")
    if roots.keys() != by_send.keys():
        raise ValueError(
            f"{gate}: missing L1I accepts at {sorted(by_send.keys()-roots.keys())}"
        )
    if replies != by_return.keys() or witnesses != replies:
        raise ValueError(f"{gate}: missing target responses or witnesses")
    return roots, checked


def line_history(path, lines, line_size):
    events = defaultdict(list)
    with path.open("rb") as stream:
        for line in stream:
            if b": cpath " in line:
                token = b" line="
            elif b": cachepath mem-" in line:
                token = b" addr="
            else:
                continue
            start = line.index(token) + len(token)
            end = line.find(b" ", start)
            address = int(line[start : None if end == -1 else end], 0)
            block = address // line_size * line_size
            if block not in lines:
                continue
            event = parse_event(line)
            if events[block] and event["tick"] < events[block][-1]["tick"]:
                raise ValueError(f"Time went backwards on line {block:#x}")
            events[block].append(event)
    return events


def load_gate(runs, baseline, gate, pairs):
    """Resolve O3 replay and root physical lines before retaining line histories."""
    directory, reference = runs / gate, baseline / "functional" / gate
    meta = validate_run(directory, reference)
    path = directory / "m5out/retire.log"
    roots, meta["verified_replay_events"] = match_roots(
        path, reference / "m5out/retire.log", gate, pairs, meta
    )
    lines = {e["line"] for e in roots.values()}
    events = line_history(path, lines, meta["cache_line_size"])
    meta.update(targets=len(roots), physical_lines=len(lines))
    return roots, events, meta
