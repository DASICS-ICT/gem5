# SPDX-License-Identifier: BSD-3-Clause
"""Summarize paired dynamic fetch paths for the two pause directions."""

import json
from collections import Counter

from fetch_pairs import write_csv

L1_LEDGER = (
    "l1_hit_service_ticks",
    "l1_to_accept_ticks",
    "l1_wait_fill_ticks",
    "l1_fill_to_due_ticks",
    "l1_due_to_return_ticks",
)
QUEUE_METRICS = (
    "l1_queue_post_demand_ticks",
    "path_queue_post_demand_ticks",
    "dram_queue_post_demand_ticks",
)


def observation(level):
    op = level["op"]
    if op == "hit":
        if level.get("marked"):
            return "hit_marked_prefetch"
        if level.get("fill_pf"):
            return "hit_unmarked_prefetch_origin"
        return "hit_unmarked"
    if op == "join":
        if level.get("leader_pf") is None:
            return "join_unknown_origin"
        return "join_prefetch" if level["leader_pf"] else "join_other"
    return op


def features(request):
    chain = request["levels"]
    if not chain or chain[0]["level"] != "L1I":
        raise ValueError("Missing L1 instruction-cache observation")
    result = {
        **{k: v for k, v in request.items() if k != "levels"},
        "l1_outcome": observation(chain[0]),
        "path": "/".join(f"{r['level']}:{observation(r)}" for r in chain),
        # These observations can coexist at different levels in a single path.
        "marked_hit": any(bool(r.get("marked")) for r in chain),
        "unmarked_prefetch_fill_hit": any(
            observation(r) == "hit_unmarked_prefetch_origin" for r in chain
        ),
        "joined_prefetch": any(
            observation(r) == "join_prefetch" for r in chain
        ),
    }
    l1 = chain[0]
    if result["l1_outcome"] == "join_prefetch":
        result["l1_prefetch_lead_ticks"] = l1["prefetch_lead_ticks"]
        result["l1_prefetch_in_service_at_join"] = l1[
            "join_already_in_service"
        ]
        result["l1_prefetch_head_start_after_send_ticks"] = max(
            0, l1["lookup_tick"] - l1["send_tick"]
        )
    if any(
        result[k]
        for k in (
            "marked_hit",
            "unmarked_prefetch_fill_hit",
            "joined_prefetch",
        )
    ):
        result["prefetch_evidence"] = "observed"
    elif request["status"] == "resolved":
        result["prefetch_evidence"] = "unobserved"
    else:
        result["prefetch_evidence"] = "incomplete"
    return result


def paired_timing(data, field, period):
    # Use the same set of known observations on both sides. A missing
    # prefetch predecessor cannot be treated as zero queue delay.
    known = [
        (fast[field], slow[field])
        for fast, slow in data
        if fast.get(field) is not None and slow.get(field) is not None
    ]
    n = len(known)
    if not n:
        return {"known_pairs": 0}
    fast_total = sum(a for a, _ in known)
    slow_total = sum(b for _, b in known)
    return {
        "known_pairs": n,
        "fast_mean_cycles": fast_total / (n * period),
        "paused_mean_cycles": slow_total / (n * period),
        "paused_minus_fast_mean_cycles": (slow_total - fast_total)
        / (n * period),
        "paused_minus_fast_sum_ticks": slow_total - fast_total,
    }


def transitions(data, field):
    """Both directions order the labels as paused path -> early-reply path."""
    return dict(
        sorted(
            Counter(
                f"{paused[field]} -> {fast[field]}" for fast, paused in data
            ).items()
        )
    )


def direction(data, period):
    joins = {}
    for index, name in enumerate(("fast", "paused")):
        samples = [
            pair[index]
            for pair in data
            if pair[index]["l1_outcome"] == "join_prefetch"
        ]
        stats = {"pairs": len(samples)}
        if samples:
            stats["already_in_service"] = sum(
                bool(r["l1_prefetch_in_service_at_join"]) for r in samples
            )
            for k in (
                "l1_prefetch_lead_ticks",
                "l1_prefetch_head_start_after_send_ticks",
                "l1_wait_fill_ticks",
            ):
                valid = [r[k] for r in samples if r.get(k) is not None]
                if valid:
                    stats["mean_" + k.removesuffix("_ticks") + "_cycles"] = (
                        sum(valid) / (len(valid) * period)
                    )
                    stats[k + "_samples"] = len(valid)
        joins[name] = stats
    return {
        "pairs": len(data),
        "both_paths_resolved": sum(
            f["status"] == p["status"] == "resolved" for f, p in data
        ),
        "source_transitions": transitions(data, "source_level"),
        "l1_outcome_transitions": transitions(data, "l1_outcome"),
        "path_transitions": transitions(data, "path"),
        "prefetch_transitions": transitions(data, "prefetch_evidence"),
        "l1_prefetch_joins": joins,
        "prefetch_observations_on_resolved_paths": {
            side: {
                obs: sum(
                    request[index][obs]
                    for request in data
                    if request[index]["status"] == "resolved"
                )
                for obs in (
                    "marked_hit",
                    "unmarked_prefetch_fill_hit",
                    "joined_prefetch",
                )
            }
            for index, side in enumerate(("fast", "paused"))
        },
        "timings": {
            key: paired_timing(data, key, period)
            for key in ("request_latency_ticks", *L1_LEDGER, *QUEUE_METRICS)
        },
    }


def net_counts(sw, gf):
    return {
        label: {
            "sw_only_wakes": sw.get(label, 0),
            "gf_only_wakes": gf.get(label, 0),
            "net_fewer_gf_wakes": sw.get(label, 0) - gf.get(label, 0),
        }
        for label in sorted(sw.keys() | gf.keys())
    }


def write_report(outdir, pairs, period, meta):
    flat, levels = [], []
    directions = {"sw_only_wakes": [], "gf_only_wakes": []}
    idle_cycles = Counter()
    for prior, sw, gf in pairs:
        mode = prior["match"]
        key = {
            k: prior[k]
            for k in ("block", "witness_ordinal", "witness_pc", "match")
        }
        row = dict(prior)
        swf, gff = features(sw), features(gf)
        for gate, result, feature in (("sw", sw, swf), ("gf", gf, gff)):
            latency = int(prior[f"{gate}_response_tick"]) - int(
                prior[f"{gate}_send_tick"]
            )
            if latency != result["request_latency_ticks"]:
                raise ValueError(
                    f"{key}: {gate} response timing differs from paired trace"
                )
            if all(result.get(k) is not None for k in L1_LEDGER):
                if sum(result[k] for k in L1_LEDGER) != latency:
                    raise ValueError(
                        f"{key}: {gate} L1 elapsed ledger differs"
                    )
            row.update({f"{gate}_{k}": v for k, v in feature.items()})
            for hop, level in enumerate(result["levels"]):
                levels.append(
                    {
                        **key,
                        "gate": gate,
                        "hop": hop,
                        **level,
                        "outcome": observation(level),
                    }
                )
            idle_cycles[gate] += int(prior[f"{gate}_idle_cycles"])
        flat.append(row)
        directions[mode].append(
            (gff, swf) if mode == "sw_only_wakes" else (swf, gff)
        )

    if [len(x) for x in directions.values()] != [168, 136]:
        raise ValueError(
            "Expected 168 SW-only and 136 G/F-only early-reply pairs"
        )
    groups = {k: direction(v, period) for k, v in directions.items()}
    sw, gf = groups["sw_only_wakes"], groups["gf_only_wakes"]
    report = {
        "ticks_per_cycle": period,
        "pairs": len(flat),
        "net_fewer_gf_wakes": sw["pairs"] - gf["pairs"],
        "net_saved_idle_cycles_for_selected_pairs": idle_cycles["sw"]
        - idle_cycles["gf"],
        "groups": groups,
        "net_by_source_transition": net_counts(
            sw["source_transitions"], gf["source_transitions"]
        ),
        "net_by_l1_transition": net_counts(
            sw["l1_outcome_transitions"], gf["l1_outcome_transitions"]
        ),
        "net_by_path_transition": net_counts(
            sw["path_transitions"], gf["path_transitions"]
        ),
        "net_by_prefetch_transition": net_counts(
            sw["prefetch_transitions"], gf["prefetch_transitions"]
        ),
        "runs": meta,
    }
    outdir.mkdir(parents=True, exist_ok=True)
    write_csv(outdir / "cache-pairs.csv", flat)
    write_csv(outdir / "cache-levels.csv", levels)
    (outdir / "cache-summary.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        f"[OK] {len(flat)} paired fetches, {report['net_fewer_gf_wakes']} net fewer G/F pauses"
    )
    return report
