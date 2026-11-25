# SPDX-License-Identifier: BSD-3-Clause
"""Follow a paired instruction fetch through cache targets, MSHRs and memory."""

import argparse
from pathlib import Path

from cache_ingest import load_gate
from cache_report import write_report
from cache_targets import selected_pairs


class IncompletePath(ValueError):
    """The trace does not uniquely identify a dependency."""


def exactly_one(matches, description):
    if len(matches) != 1:
        raise IncompletePath(f"{description}: found {len(matches)} events")
    return matches[0]


def key(event, prefix=""):
    return tuple(event[prefix + field] for field in ("rid", "born", "pa"))


def records(events, ops, **match):
    return [
        event
        for event in events
        if event["op"] in ops
        and all(event.get(k) == v for k, v in match.items())
    ]


def span(start, end):
    if start is None or end is None or end < start:
        raise IncompletePath(f"unordered interval {start}..{end}")
    return end - start


def duration(intervals):
    # Service of an incumbent prefetch can precede the demand and overlap
    # other levels' waiting times. Count each post-demand wall-clock tick once.
    total = 0
    last = -1
    for start, end in sorted(intervals):
        total += max(0, end - max(last, start))
        last = max(last, end)
    return total


def cache_level(component):
    if component == "system.cpu.icache":
        return "L1I"
    if component.startswith("system.l2"):
        return "L2"
    if component.startswith("system.l3"):
        return "L3"
    return None


class RequestPath:
    def __init__(self, events, issue, response):
        self.events = events
        self.issue = issue
        self.response = response
        self.levels = []
        self.queues = []
        self.mem_queue = None
        self.source = "unknown"
        self.source_level = "unknown"
        self.ledger = None

    def set_ledger(self, hit, forward, lower, fill, due):
        delivery = span(due, self.response)
        if (
            hit + forward + lower + fill + delivery
            != self.response - self.issue
        ):
            raise IncompletePath("L1 latency components do not reconcile")
        self.ledger = dict(
            l1_hit_service_ticks=hit,
            l1_to_accept_ticks=forward,
            l1_wait_fill_ticks=lower,
            l1_fill_to_due_ticks=fill,
            l1_due_to_return_ticks=delivery,
        )

    def memory(self, send, parent_fill, engaged):
        linked = [
            e
            for e in self.events
            if e["kind"] == "mpath"
            and key(e) == key(send)
            and send["tick"] <= e["tick"] <= parent_fill
        ]
        bursts = records(linked, {"queue", "bypass"}, tick=send["tick"])
        if not bursts:
            raise IncompletePath("no memory admission at LLC send")
        replies = records(linked, {"response"})
        response = exactly_one(replies, "memory response")
        row = dict(
            cache=response["component"],
            level="memory",
            op="read",
            lookup_tick=send["tick"],
            due_tick=response["due"],
            bursts=len(bursts),
            issue_tick=self.issue,
            request_pf=send["pf"],
        )
        self.levels.append(row)
        if all(b["op"] == "bypass" for b in bursts):
            self.source_level = "write_queue"
            self.source = "memory_write_queue"
            self.mem_queue = 0
            return
        # These v5_full 64-byte fills use a single DRAM burst. Do not add
        # service times of multiple bursts if a later configuration splits it.
        if len(bursts) != 1:
            raise IncompletePath("multi-burst memory admission")
        issue = exactly_one(
            records(linked, {"issue"}, addr=bursts[0]["addr"]),
            "DRAM burst issue",
        )
        if (
            issue["entry"] != bursts[0]["tick"]
            or response["due"] > parent_fill
        ):
            raise IncompletePath("DRAM admission/response timing")
        row.update(
            op="dram_read",
            ready_tick=issue["ready"],
            cmd_tick=issue["cmd"],
            scheduler_tick=issue["tick"],
            entry_tick=issue["entry"],
            queue_ticks=span(issue["entry"], issue["tick"]),
            command_delay_ticks=span(issue["tick"], issue["cmd"]),
            burst_service_ticks=span(issue["cmd"], issue["ready"]),
            return_to_llc_ticks=span(response["due"], parent_fill),
        )
        self.mem_queue = max(0, issue["tick"] - max(engaged, issue["entry"]))
        row["queue_post_demand_ticks"] = self.mem_queue
        self.source_level, self.source = "DRAM", "dram_read"

    def visit(self, access, engaged, upstream_return):
        cache = access["component"]
        level = cache_level(cache)
        op = access["op"]
        lookup = access["tick"]
        engaged = max(engaged, lookup)
        row = dict(
            cache=cache,
            level=level,
            op=op,
            lookup_tick=lookup,
            issue_tick=self.issue,
            request_pf=access["pf"],
            requestor=access["rid"],
            command=access["cmd"],
        )
        self.levels.append(row)
        if op == "hit":
            row.update(
                marked=access["marked"],
                fill_pf=access["fill_pf"],
                fill_rid=access["fill_rid"],
                inserted_tick=access["inserted"],
                block_ready_tick=access["block_ready"],
                hit_since_insert_ticks=span(access["inserted"], lookup),
                hit_since_ready_ticks=lookup - access["block_ready"],
                due_tick=access["due"],
                queue_post_demand_ticks=0,
            )
            # The first-use bit is cleared on use. Preserve the allocating
            # source separately and date its fill when the trace includes it.
            if row["fill_pf"]:
                origin = records(
                    self.events,
                    {"fill"},
                    component=cache,
                    tick=row["inserted_tick"],
                    leader_rid=row["fill_rid"],
                    leader_pf=1,
                )
                if len(origin) == 1:
                    row["historical_pf_recv_tick"] = origin[0]["recv"]
                    row["historical_pf_lead_ticks"] = (
                        lookup - origin[0]["recv"]
                    )
            if access["due"] > upstream_return:
                raise IncompletePath(
                    f"{level} hit due after upstream response"
                )
            if level == "L1I":
                self.set_ledger(
                    span(lookup, access["due"]), 0, 0, 0, access["due"]
                )
            self.source_level, self.source = level, f"{level}_hit"
            self.mem_queue = 0
            return

        txn = [
            e
            for e in self.events
            if e["kind"] == "cpath"
            and e["component"] == cache
            and e.get("order") == access["order"]
        ]
        # The target identity matches this demand even if another request
        # originally allocated the MSHR and issued the downstream read.
        reply = exactly_one(
            [
                e
                for e in records(txn, {"respond"})
                if key(e) == key(access)
                and lookup <= e["tick"] <= upstream_return
            ],
            f"{level} target response",
        )
        fill = exactly_one(
            records(txn, {"fill"}, tick=reply["tick"]), f"{level} fill"
        )
        leader = key(fill, "leader_")
        send = exactly_one(
            [
                e
                for e in records(txn, {"send", "snoop"})
                if key(e, "leader_") == leader
                and fill["recv"] <= e["tick"] <= fill["tick"]
            ],
            f"{level} MSHR departure",
        )
        row.update(
            leader_pf=fill["leader_pf"],
            leader_rid=fill["leader_rid"],
            mshr_order=access["order"],
            leader_received_tick=send["recv"],
            ready_tick=send["ready"],
            send_tick=send["tick"],
            fill_tick=fill["tick"],
            due_tick=reply["due"],
            downstream_retries=sum(
                e["op"] == "retry"
                and send["recv"] <= e["tick"] <= send["tick"]
                for e in txn
            ),
            prefetch_lead_ticks=(
                span(send["recv"], lookup)
                if op == "join" and send["leader_pf"]
                else None
            ),
            join_already_in_service=(
                access.get("service") if op == "join" else None
            ),
            after_ready_queue_ticks=span(send["ready"], send["tick"]),
        )
        post_ready = max(engaged, send["ready"])
        row["queue_post_demand_ticks"] = max(0, send["tick"] - post_ready)
        if send["tick"] > post_ready:
            self.queues.append((post_ready, send["tick"]))
        if level == "L1I":
            outbound = max(lookup, send["tick"])
            self.set_ledger(
                0,
                span(lookup, outbound),
                span(outbound, fill["tick"]),
                span(fill["tick"], reply["due"]),
                reply["due"],
            )
        if send["op"] == "snoop":
            self.source_level, self.source = "snoop", "upper_snoop"
            self.mem_queue = 0
            return
        if level == "L3":
            self.memory(send, fill["tick"], max(engaged, send["tick"]))
            return
        next_level = "L2" if level == "L1I" else "L3"
        child = exactly_one(
            [
                e
                for e in self.events
                if e["kind"] == "cpath"
                and e["op"] in ("hit", "new", "join")
                and cache_level(e["component"]) == next_level
                and e["tick"] == send["tick"]
                and key(e) == leader
            ],
            f"{level} departure to {next_level}",
        )
        self.visit(child, engaged, fill["tick"])

    def result(self, root):
        error = None
        try:
            self.visit(root, self.issue, self.response)
        except IncompletePath as exc:
            error = str(exc)
        result = dict(
            source_level=self.source_level,
            source=self.source,
            levels=self.levels,
            status="partial" if error else "resolved",
            partial_reason=error,
            target_pa=hex(root["pa"]),
            physical_line=hex(root["line"]),
            request_latency_ticks=self.response - self.issue,
            l1_queue_post_demand_ticks=self.levels[0].get(
                "queue_post_demand_ticks"
            ),
            path_queue_post_demand_ticks=(
                duration(self.queues) if not error else None
            ),
            dram_queue_post_demand_ticks=self.mem_queue,
        )
        result.update(self.ledger or {})
        return result


def compare(runs, baseline, outdir):
    pairs = selected_pairs(baseline)
    resolved = {gate: [] for gate in ("sw", "gf")}
    meta = {}
    for gate in resolved:
        roots, events, meta[gate] = load_gate(runs, baseline, gate, pairs)
        for pair in pairs:
            sent = int(pair[f"{gate}_send_tick"])
            response = int(pair[f"{gate}_response_tick"])
            root = roots[sent]
            path = RequestPath(events[root["line"]], sent, response)
            resolved[gate].append(path.result(root))
    periods = {data["period"] for data in meta.values()}
    if len(periods) != 1:
        raise ValueError("Different CPU clock periods")
    return write_report(
        outdir,
        zip(pairs, resolved["sw"], resolved["gf"], strict=True),
        periods.pop(),
        meta,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    try:
        compare(args.runs, args.baseline, args.outdir)
    except (KeyError, ValueError, OSError) as error:
        parser.exit(1, f"[FAIL] {error}\n")
