# SPDX-License-Identifier: BSD-3-Clause
"""Reconstruct strtok sequences from selected single-thread retirement events."""

import gzip
import re
from collections import Counter
from pathlib import Path

EVENT = re.compile(r"^\s*(\d+): \S+: retired pc=(0x[0-9a-f]+) count=(\d+)\s*$")


def _events(path, targets, raw):
    names = {pc: name for name, pc in targets.items()}
    if len(names) != len(targets):
        raise ValueError("Each retired PC must have one marker")
    seen = dict.fromkeys(targets, 0)
    previous = 0
    open_trace = gzip.open if path.suffix == ".gz" else open
    with open_trace(path, "rt") as stream:
        for line_no, line in enumerate(stream, 1):
            if "retired pc=" not in line:
                continue
            match = EVENT.fullmatch(line)
            if not match:
                raise ValueError(
                    f"{path}:{line_no}: malformed retirement event"
                )
            tick, pc, count = match.groups()
            tick = int(tick)
            name = names.get(int(pc, 16))
            if name is None or int(count) != seen[name] + 1 or tick < previous:
                raise ValueError(
                    f"{path}:{line_no}: inconsistent retirement event"
                )
            seen[name] += 1
            previous = tick
            yield name
    if seen != raw:
        raise ValueError("Trace totals disagree with retired-pcs.json")


def _expect(events, wanted, site):
    actual = next(events, None)
    if actual != wanted:
        raise ValueError(f"{site}: expected {wanted}, observed {actual}")


def analyze(trace, targets, raw):
    """Count first/continuation inputs and sessions delimited by non-NULL inputs."""
    counts = {
        name: {"first": 0, "continuation": 0, "total": 0}
        for name in targets
        if name.startswith("site_")
    }
    direct = Counter()
    paths = Counter()
    session = []
    events = _events(Path(trace), targets, raw)
    for site in events:
        if site in ("main", "readline"):
            continue
        wrapper = site in counts
        if wrapper:
            _expect(events, "strtok", site)
            _expect(events, "tail", site)
        elif not site.startswith("other_"):
            raise ValueError(f"Unexpected {site} outside a tokenizer call")
        _expect(events, "helper", site)
        # Only the taken NULL-input branch loads *saveptr. Its successor
        # rejoins the non-NULL path, so only the private load distinguishes it.
        after = next(events, None)
        kind = "continuation" if after == "null_path" else "first"
        if kind == "continuation":
            _expect(events, "helper_ret", site)
        elif after != "helper_ret":
            raise ValueError(
                f"{site}: unexpected event before return: {after}"
            )
        if not wrapper:
            # Direct __strtok_r calls use a caller-owned cursor.
            direct[kind] += 1
            continue
        counts[site][kind] += 1
        counts[site]["total"] += 1
        if kind == "first":
            if session:
                paths[tuple(session)] += 1
            session = []
        elif not session:
            raise ValueError("Continuation before the first strtok input")
        session.append(site)
    if session:
        paths[tuple(session)] += 1

    first = sum(c["first"] for c in counts.values())
    continuation = sum(c["continuation"] for c in counts.values())
    total = first + continuation
    histogram = Counter()
    for path, occurrences in paths.items():
        histogram[len(path)] += occurrences
    if (
        sum(paths.values()) != first
        or sum(n * k for n, k in histogram.items()) != total
    ):
        raise ValueError("Tokenization sessions do not account for all calls")
    return dict(
        site_counts=counts,
        first_calls=first,
        continuation_calls=continuation,
        total_calls=total,
        sessions=first,
        calls_per_session_mean=total / first if first else None,
        calls_per_session_histogram=dict(sorted(histogram.items())),
        session_paths=[
            dict(sites=list(path), sessions=n, calls=len(path) * n)
            for path, n in paths.most_common()
        ],
        direct_helper_calls=sum(direct.values()),
        direct_helper_first_calls=direct["first"],
        direct_helper_continuation_calls=direct["continuation"],
    )
