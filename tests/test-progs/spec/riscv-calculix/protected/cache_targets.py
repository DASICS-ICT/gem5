# SPDX-License-Identifier: BSD-3-Clause
"""Select the previously witnessed, one-sided fetch pairs for cache tracing."""

import csv
from collections import Counter


def selected_pairs(previous_batch):
    with (previous_batch / "fetch-pairs.csv").open(newline="") as stream:
        rows = [
            row
            for row in csv.DictReader(stream)
            if row["evidence"] == "reply_before_pause_threshold"
        ]
    counts = Counter(row["match"] for row in rows)
    if counts != {"sw_only_wakes": 168, "gf_only_wakes": 136}:
        raise ValueError(f"Unexpected beampic target population: {counts}")
    witnesses = {
        (r["block"], r["witness_ordinal"], r["witness_pc"]) for r in rows
    }
    if len(witnesses) != len(rows) or any(
        not n or not pc for _, n, pc in witnesses
    ):
        raise ValueError("Cache targets must have unique retired witnesses")
    for gate in ("sw", "gf"):
        if len({int(r[f"{gate}_send_tick"]) for r in rows}) != len(rows):
            raise ValueError(f"Duplicate cache access tick for {gate}")
    return rows
