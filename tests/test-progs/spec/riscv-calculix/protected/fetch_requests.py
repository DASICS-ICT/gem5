# SPDX-License-Identifier: BSD-3-Clause
"""Stream usable O3 fetch responses and retain dynamic counterparts of idle wakes."""

import collections
import configparser
import csv
import json
from bisect import bisect_left
from dataclasses import dataclass
from typing import NamedTuple

from tail_stats import (
    counter_names,
    dumps,
)


class Span(NamedTuple):
    pause: int
    wake: int
    credited: int
    reason: str


@dataclass
class Request:
    block: int
    pc: int
    sent: int
    response: int
    before: int
    after: int
    pause: int | None
    idle: int
    first_pause: int | None
    other_idle_ticks: int
    crosses_cutoff: bool
    anchor: int | None = None
    anchor_pc: int | None = None


def original_event(line):
    return (
        b": system.cpu: idle-" in line
        or b": system.pc_counts: retired pc=" in line
    )


class GateTrace:
    def __init__(self, gate, runs, baseline):
        directory = runs / gate
        ref = baseline / "functional" / gate
        result, old = (
            json.loads((d / "result.json").read_text())
            for d in (directory, ref)
        )
        for name in ("variant", "input", "elf", "retired_pcs", "comparisons"):
            if result[name] != old[name]:
                raise ValueError(
                    f"{gate}: different {name} from wake reference"
                )
        if (
            result["variant"] != gate
            or result["input"] != "test"
            or result["returncode"] != 0
            or result["status"] != "OK"
            or {c["file"]: c["status"] for c in result["comparisons"]}
            != {"SPECtestformatmodifier_z.txt": "PASS", "beampic.dat": "PASS"}
        ):
            raise ValueError(f"{gate}: incomplete beampic result")

        out = directory / "m5out"
        names = set(counter_names())
        blocks = dumps(out / "stats.txt", names, 2)
        if blocks != dumps(ref / "m5out/stats.txt", names, 2) or any(
            set(b) != names for b in blocks
        ):
            raise ValueError(
                f"{gate}: cumulative counters differ or are missing"
            )
        marker = json.loads((out / "retire-snapshot.json").read_text())
        if marker != json.loads(
            (ref / "m5out/retire-snapshot.json").read_text()
        ):
            raise ValueError(f"{gate}: different retirement boundary")
        self.cutoff = marker["tick"]
        self.base = blocks[0]["simInsts"][0]
        self.finish = blocks[1]["finalTick"][0]
        self.path = out / "retire.log"
        self.reference = ref / "m5out/retire.log"
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(out / "config.ini")
        self.period = int(cfg[cfg["system.cpu"]["clk_domain"]]["clock"])
        self.width = int(cfg["system.cpu"]["fetchBufferSize"])
        self.gate = gate
        self.spans = []
        with (baseline / "wake-intervals.csv").open(newline="") as stream:
            for r in csv.DictReader(stream):
                if r["gate"] != gate:
                    continue
                if r["status"] not in ("complete", "crosses_snapshot"):
                    raise ValueError(
                        f"{gate}: open idle span cannot be compared"
                    )
                span = Span(
                    int(r["pause_tick"]),
                    int(r["wake_tick"]),
                    int(r["idle_cycles"]),
                    r["reason"],
                )
                if self.spans and self.spans[-1].wake > span.pause:
                    raise ValueError(f"{gate}: overlapping idle intervals")
                self.spans.append(span)
        self.ends = [s.wake for s in self.spans]
        self.wakes = {
            s.wake: s for s in self.spans if s.reason == "icache_response"
        }
        if len(self.wakes) != sum(
            s.reason == "icache_response" for s in self.spans
        ):
            raise ValueError(f"{gate}: multiple instruction wakes in one tick")
        if sum(s.credited for s in self.spans) != (
            blocks[1]["system.cpu.idleCycles"][0]
            - blocks[0]["system.cpu.idleCycles"][0]
        ):
            raise ValueError(f"{gate}: reference idle cycles do not reconcile")
        self.records = {}
        self.block_counts = collections.Counter()
        self.trace_anchors = 0

    def request(self, fields, response):
        sent = int(fields[3].removeprefix(b"sent="))
        block = int(fields[4].removeprefix(b"block="), 16)
        pc = int(fields[5].removeprefix(b"pc="), 16)
        before = int(fields[6].removeprefix(b"before=")) - self.base
        after = int(fields[7].removeprefix(b"after=")) - self.base
        if not (
            sent <= response <= self.finish
            and self.cutoff <= response
            and block % self.width == 0
            and before <= after
        ):
            raise ValueError(
                f"{self.gate} at {response}: invalid fetch record"
            )
        terminal = self.wakes.get(response)
        first = None
        other = 0
        i = bisect_left(self.ends, sent)
        while i < len(self.spans):
            span = self.spans[i]
            if span.pause > response:
                break
            overlap = min(response, span.wake) - max(sent, span.pause)
            if overlap > 0 or span is terminal:
                if first is None:
                    first = max(sent, span.pause)
                if span is not terminal:
                    other += overlap
            i += 1
        return Request(
            block,
            pc,
            sent,
            response,
            before,
            after,
            terminal.pause if terminal else None,
            terminal.credited if terminal else 0,
            first,
            other,
            sent < self.cutoff,
        )

    def discover(self):
        """Match precisely the accepted fill immediately preceding each effective wake."""
        seen_wakes = set()
        preceding_response = None
        with self.path.open("rb") as stream, self.reference.open("rb") as ref:
            previous = filter(original_event, ref)
            for line in stream:
                if b": fetch-r " in line:
                    fields = line.split()
                    tick = int(fields[0][:-1])
                    block = int(fields[4][6:], 16)
                    if tick < self.cutoff:
                        raise ValueError(
                            f"{self.gate}: fetch timing active before cutoff"
                        )
                    self.block_counts[block] += 1
                    if tick in self.wakes:
                        if tick in self.records:
                            raise ValueError(
                                f"{self.gate}: ambiguous response at {tick}"
                            )
                        self.records[tick] = self.request(fields, tick)
                    preceding_response = tick
                elif b": fetch-a " in line:
                    fields = line.split()
                    response = int(fields[3][9:])
                    self.trace_anchors += 1
                    r = self.records.get(response)
                    if r is not None:
                        if r.anchor is not None:
                            raise ValueError(
                                f"{self.gate}: duplicate witness at {response}"
                            )
                        r.anchor = int(fields[4][8:]) - self.base
                        r.anchor_pc = int(fields[5][3:], 16)
                        if (
                            r.anchor <= r.after
                            or not r.block
                            <= r.anchor_pc
                            < r.block + self.width
                        ):
                            raise ValueError(
                                f"{self.gate}: inconsistent witness for {response}"
                            )
                elif original_event(line):
                    if line != next(previous, None):
                        raise ValueError(
                            f"{self.gate}: changed idle or retirement event {line!r}"
                        )
                    if b"idle-wake reason=icache_response " in line:
                        tick = int(line.split(b":", 1)[0])
                        if tick in self.wakes:
                            if tick != preceding_response:
                                raise ValueError(
                                    f"{self.gate}: no valid response at wake {tick}"
                                )
                            seen_wakes.add(tick)
            if next(previous, None) is not None:
                raise ValueError(
                    f"{self.gate}: truncated idle/retirement trace"
                )
        if (
            seen_wakes != self.records.keys()
            or seen_wakes != self.wakes.keys()
        ):
            raise ValueError(
                f"{self.gate}: responses do not cover reference wakes"
            )
        if not self.block_counts or not self.trace_anchors:
            raise ValueError(f"{self.gate}: incomplete fetch timing trace")

    def counterparts(self, wanted, relevant_blocks):
        """Keep recent fills until their first retiring witness advances beyond them."""
        pending = collections.OrderedDict()
        last_anchor = -1
        with self.path.open("rb") as stream:
            for line in stream:
                if b": fetch-r " in line:
                    fields = line.split()
                    if int(fields[4][6:], 16) in relevant_blocks:
                        pending[int(fields[0][:-1])] = fields
                elif b": fetch-a " in line:
                    fields = line.split()
                    response = int(fields[3][9:])
                    if response < last_anchor:
                        raise ValueError(
                            f"{self.gate}: fetch witnesses arrive out of order"
                        )
                    last_anchor = response
                    ordinal = int(fields[4][8:]) - self.base
                    pc = int(fields[5][3:], 16)
                    if (ordinal, pc) in wanted and response in pending:
                        if response not in self.records:
                            r = self.request(pending[response], response)
                            r.anchor, r.anchor_pc = ordinal, pc
                            self.records[response] = r
                    # Single-hart in-order retirement makes older fills ineligible
                    # for a later first-retired witness, including wrong-path fills.
                    while pending and next(iter(pending)) <= response:
                        pending.popitem(last=False)

    def output(self):
        return list(self.records.values()), {
            "period": self.period,
            "block_size": self.width,
            "cutoff_tick": self.cutoff,
            "cutoff_retired_instructions": self.base,
            "usable_responses": self.block_counts.total(),
            "witness_events": self.trace_anchors,
            "blocks": self.block_counts,
            "verified_idle_intervals": len(self.spans),
        }


def load_pair(runs, baseline):
    """Return each gate's observed wakes and any witnessed opposite-run counterpart."""
    traces = {gate: GateTrace(gate, runs, baseline) for gate in ("sw", "gf")}
    wanted = set()
    blocks = set()
    for trace in traces.values():
        trace.discover()
        for r in trace.records.values():
            if r.anchor is not None:
                wanted.add((r.anchor, r.anchor_pc))
                blocks.add(r.block)
    for trace in traces.values():
        trace.counterparts(wanted, blocks)
    return {gate: trace.output() for gate, trace in traces.items()}
