# SPDX-License-Identifier: BSD-3-Clause
"""Compare dynamic fetches that woke O3 after the final beampic fmod call."""

import argparse
import csv
import json
from collections import (
    Counter,
    defaultdict,
)
from pathlib import Path

from fetch_requests import load_pair


def woke(request):
    return request is not None and request.pause is not None


def pair_requests(left, right):
    """A first retired instruction identifies its fill across the aligned ELFs."""
    indexed = defaultdict(lambda: [[], []])
    for side, requests in enumerate((left, right)):
        for r in requests:
            if r.anchor is None:
                if woke(r):
                    yield (r, None) if side == 0 else (None, r)
            else:
                indexed[r.block, r.anchor, r.anchor_pc][side].append(r)

    for sw, gf in indexed.values():
        if len(sw) == len(gf) == 1:
            if woke(sw[0]) or woke(gf[0]):
                yield sw[0], gf[0]
        else:
            # Missing or ambiguous witnesses carry their full idle charge
            # into the ledger, with no invented opposite-run timings.
            for r in sw:
                if woke(r):
                    yield r, None
            for r in gf:
                if woke(r):
                    yield None, r


def classify(sw, gf):
    if sw is None or gf is None:
        r = gf if sw is None else sw
        return "no_witness" if r.anchor is None else "no_unique_counterpart"
    if sw.pc != gf.pc:
        return "different_initiating_pc"
    if sw.crosses_cutoff or gf.crosses_cutoff:
        return "crosses_cutoff"
    if any(
        r.other_idle_ticks
        or r.first_pause != r.pause
        or (woke(r) and r.pause < r.sent)
        for r in (sw, gf)
    ):
        return "overlapping_or_prior_pause"
    if woke(sw) and woke(gf):
        return "both_paused"

    paused, running = (sw, gf) if woke(sw) else (gf, sw)
    threshold = paused.pause - paused.sent
    latency = running.response - running.sent
    if latency < threshold:
        return "reply_before_pause_threshold"
    if latency == threshold:
        return "reply_at_pause_threshold"
    # The no-pause run was scheduled past the other run's observed pause
    # threshold. Its hypothetical eventual pause time is right-censored.
    if latency < paused.response - paused.sent:
        return "longer_coverage_and_earlier_reply"
    return "longer_coverage_without_earlier_reply"


def row_for(sw, gf, period):
    r = sw if sw is not None else gf
    if sw is None or gf is None:
        mode = "unpaired_sw" if gf is None else "unpaired_gf"
    elif woke(sw) and woke(gf):
        mode = "both_wake"
    else:
        mode = "sw_only_wakes" if woke(sw) else "gf_only_wakes"
    row = {
        "block": hex(r.block),
        "witness_ordinal": r.anchor,
        "witness_pc": hex(r.anchor_pc) if r.anchor is not None else None,
        "match": mode,
        "evidence": classify(sw, gf),
    }
    for gate, q in (("sw", sw), ("gf", gf)):
        fields = {}
        if q is not None:
            fields = {
                "request_pc": hex(q.pc),
                "send_tick": q.sent,
                "response_tick": q.response,
                "latency_cycles": (q.response - q.sent) / period,
                "first_pause_tick": q.first_pause,
                "wake_pause_tick": q.pause,
                "cycles_to_wake_pause": (
                    (q.pause - q.sent) / period if woke(q) else None
                ),
                "other_idle_ticks": q.other_idle_ticks,
                "retired_in_flight": q.after - q.before,
                "idle_cycles": q.idle,
            }
        row.update({f"{gate}_{field}": val for field, val in fields.items()})
    return row


def ledger(rows):
    totals = Counter(
        sw_wakes=0, gf_wakes=0, sw_idle_cycles=0, gf_idle_cycles=0
    )
    for row in rows:
        for gate in ("sw", "gf"):
            totals[f"{gate}_wakes"] += (
                row.get(f"{gate}_wake_pause_tick") is not None
            )
            totals[f"{gate}_idle_cycles"] += row.get(f"{gate}_idle_cycles", 0)
    return {
        "rows": len(rows),
        **totals,
        "sw_minus_gf_wakes": totals["sw_wakes"] - totals["gf_wakes"],
        "sw_minus_gf_idle_cycles": totals["sw_idle_cycles"]
        - totals["gf_idle_cycles"],
    }


def grouping(rows, field):
    groups = defaultdict(list)
    for row in rows:
        groups[row[field]].append(row)
    return {group: ledger(items) for group, items in sorted(groups.items())}


def one_sided(rows):
    """Report timings separately for lost and gained pauses."""
    transitions = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["match"] in ("sw_only_wakes", "gf_only_wakes"):
            transitions[r["match"]][r["evidence"]].append(r)
    result = {}
    for direction, groups in transitions.items():
        paused = "sw" if direction == "sw_only_wakes" else "gf"
        result[direction] = {}
        for label, items in sorted(groups.items()):
            fields = [f"{paused}_cycles_to_wake_pause"]
            for gate in ("sw", "gf"):
                fields.extend(
                    [f"{gate}_latency_cycles", f"{gate}_retired_in_flight"]
                )
            means = {
                f"mean_{field}": sum(r[field] for r in items) / len(items)
                for field in fields
            }
            result[direction][label] = {**ledger(items), **means}
    return result


def both_paused(rows, period):
    """Disjoint terms of the charged idle-cycle difference for two observed pauses."""
    rows = [r for r in rows if r["evidence"] == "both_paused"]
    changes = Counter(
        response_latency_cycles=0, cycles_to_pause=0, edge_correction=0
    )
    for r in rows:

        def gap(gate, boundary):
            def edge(which):
                return -(-r[f"{gate}_{which}_tick"] // period)

            return edge(boundary) - edge("send")

        latency = gap("sw", "response") - gap("gf", "response")
        overlap = gap("gf", "wake_pause") - gap("sw", "wake_pause")
        changes["response_latency_cycles"] += latency
        changes["cycles_to_pause"] += overlap
        # A wake on the pause edge charges zero, not minus one.
        changes["edge_correction"] += (
            r["sw_idle_cycles"] - r["gf_idle_cycles"] - latency - overlap
        )
    return {**ledger(rows), **changes}


def write_csv(path, rows):
    fields = dict.fromkeys(field for row in rows for field in row)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def compare(runs, baseline, outdir):
    data = load_pair(runs, baseline)
    sw, sw_meta = data["sw"]
    gf, gf_meta = data["gf"]
    period = sw_meta["period"]
    if period != gf_meta["period"]:
        raise ValueError("CPU clock periods differ")
    rows = [row_for(s, g, period) for s, g in pair_requests(sw, gf)]
    rows.sort(
        key=lambda row: (
            int(row["block"], 16),
            row["witness_ordinal"] is None,
            row["witness_ordinal"] or 0,
        )
    )
    total = ledger(rows)
    reference = json.loads((baseline / "wake-summary.json").read_text())
    icache = next(
        r for r in reference["by_reason"] if r["reason"] == "icache_response"
    )
    for key in ("sw_wakes", "gf_wakes", "sw_idle_cycles", "gf_idle_cycles"):
        if total[key] != icache[key]:
            raise ValueError(
                f"Fetch-request accounting mismatch for {key}: {total[key]} vs {icache[key]}"
            )

    blocks = grouping(rows, "block")
    block_rows = [
        {
            "block": addr,
            "sw_usable_responses": sw_meta["blocks"].get(int(addr, 16), 0),
            "gf_usable_responses": gf_meta["blocks"].get(int(addr, 16), 0),
            **totals,
        }
        for addr, totals in sorted(
            blocks.items(), key=lambda item: int(item[0], 16)
        )
    ]
    summary = {
        "period": period,
        "blocks_waking_either_run": len(block_rows),
        "total": total,
        "by_match": grouping(rows, "match"),
        "by_evidence": grouping(rows, "evidence"),
        "one_sided_by_evidence": one_sided(rows),
        "both_paused_decomposition": both_paused(rows, period),
        "runs": {
            gate: {k: v for k, v in meta.items() if k != "blocks"}
            for gate, (_, meta) in data.items()
        },
    }
    outdir.mkdir(parents=True, exist_ok=True)
    write_csv(outdir / "fetch-pairs.csv", rows)
    write_csv(outdir / "fetch-blocks.csv", block_rows)
    (outdir / "fetch-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    print(
        f"[OK] {total['sw_minus_gf_wakes']} net fetch wakes; {total['sw_minus_gf_idle_cycles']} idle cycles"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    try:
        compare(args.runs, args.baseline, args.outdir)
    except (KeyError, OSError, ValueError) as err:
        parser.exit(1, f"[FAIL] {err}\n")
