# SPDX-License-Identifier: BSD-3-Clause
"""Measure the two SoPlex strtok gates with host retirement probes."""

import argparse
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from perf_compare import (
    EXPECTED,
    compare,
    probe_targets,
)
from perf_sites import discover_pair
from run_pair import (
    CASE,
    gem5_command,
    guest_exit_ok,
    read_trace,
    spec,
    spec_outputs,
)


def check_counts(counts, targets, sites):
    calls = sum(EXPECTED.values())
    expected = dict.fromkeys(targets, calls)
    expected.update(
        main=1,
        strtok=12,
        next_input=EXPECTED["next_token"] + EXPECTED["next_null"],
        null_result=EXPECTED["next_null"],
    )
    site_counts = []
    for call in sites:
        n = counts[f"call_{call:x}"]
        site_counts.append(n)
        expected[f"call_{call:x}"] = expected[f"resume_{call:x}"] = n
    # The parser can stop after any field. Call-site PCs may move on relink.
    if (
        sorted(site_counts) != [1398, 1676, 2174, 2174, 2174]
        or counts != expected
    ):
        raise ValueError(f"Unexpected retired PCs: {counts}")


def run_one(variant, elf, ordinary, batch, plan, markers, sites):
    directory = batch / variant
    directory.mkdir(parents=True)
    current = directory / "work/01"
    m5out = directory / "m5out"
    (invocation,) = plan["runs"]
    before = spec.prepare_workdir(ordinary, "test", current, None)
    targets = probe_targets(markers, sites, variant)
    command = gem5_command(
        elf, targets, m5out, current, invocation, trace=True
    )
    result = dict(
        status="FAIL",
        input="test",
        variant=variant,
        targets=targets,
        command=command,
    )
    try:
        rc = spec.execute(command, current, invocation, "gem5")
        result["returncode"] = rc
        if not guest_exit_ok(current, rc):
            raise ValueError(
                f"{variant}: unsuccessful exit; see {current}/gem5.log"
            )
        result["guest_exit_code"] = 0
        checks = spec_outputs(ordinary, current, plan, before, rc)
        result["comparisons"] = checks
        if {c["file"]: c["status"] for c in checks} != {
            "test.out": "PASS",
            "test.stderr": "PASS",
        }:
            raise ValueError(f"{variant}: SPEC output comparison failed")
        counts = json.loads((m5out / "retired-pcs.json").read_text())
        result["retired_pcs"] = counts
        check_counts(counts, targets, sites)
        result["status"] = "PASS"
        print(
            f"PASS {variant}: {counts['b_strtok']:,} protected calls; both SPEC outputs match",
            flush=True,
        )
    except (ValueError, OSError, KeyError) as exc:
        result["error"] = str(exc)
        raise
    finally:
        spec.write_result(directory / "result.json", result)


def run(ordinary, elf_dir, batch, reference_csv):
    plan = json.loads((CASE / "workload.json").read_text())["sizes"]["test"]
    spec.require_file(ordinary / "data/test/input/test.mps")
    spec.require_executable(
        ordinary.parent / "tools/specdiff-runtime/bin/specdiff"
    )
    for check in plan["comparisons"]:
        spec.reference_file(ordinary, "test", check["file"])
    reference = read_trace(reference_csv)
    categories = Counter(
        f"{kind}_{'null' if offset == -1 else 'token'}"
        for kind, offset, _ in reference
    )
    if categories != EXPECTED:
        raise ValueError(
            f"Expected the verified test.mps token trace; got {categories}"
        )
    modes = ("sw", "hw")
    if any((batch / mode).exists() for mode in modes):
        raise ValueError("Use a fresh batch for software and hardware runs")
    elfs = {mode: elf_dir / f"soplex-perf-{mode}.elf" for mode in modes}
    markers, sites = discover_pair(elfs["sw"], elfs["hw"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [
            pool.submit(
                run_one,
                mode,
                elfs[mode],
                ordinary,
                batch,
                plan,
                markers,
                sites,
            )
            for mode in modes
        ]
        for job in jobs:
            job.result()
    result = compare(batch, markers, sites, reference_csv)
    if result["status"] != "PASS":
        raise ValueError(
            f"{result['status']}: retained paired windows and counter deltas in {batch}/summary.json"
        )
    print(
        f"PASS: {result['window']['calls']:,} paired calls; results in {batch}/summary.json",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ordinary-case", type=Path, required=True)
    parser.add_argument("--elf-dir", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--reference-csv", type=Path, required=True)
    args = parser.parse_args()
    run(
        args.ordinary_case.resolve(),
        args.elf_dir.resolve(),
        args.batch.resolve(),
        args.reference_csv.resolve(),
    )
