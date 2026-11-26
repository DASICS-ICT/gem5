# SPDX-License-Identifier: BSD-3-Clause
"""Run ordinary one-step bwaves in O3 and compare it with the protected gates."""

import argparse
import json
import re
from pathlib import Path

from compare import (
    SITE_COUNTS,
    probe_targets,
)
from native_compare import compare_native
from pow_sites import ordinary_sites
from run_pair import (
    CASE,
    SIMULATOR,
    reference_counts,
    run_one,
    spec,
)


def paired_input(ordinary, paired, simulator):
    summary = json.loads((paired / "summary.json").read_text())
    if summary["status"] != "PASS" or summary["timesteps"] != 1:
        raise ValueError("Expected a passing, one-step protected pair")
    ref = paired / "one-step-reference/work/01"
    ref_input = (ref / "bwaves.in").read_bytes()
    # Restoring the step count must reproduce every byte of the SPEC input.
    full_input, matches = re.subn(
        rb"^('Number of Time Steps'[ \t]*\r?\n[ \t]*)1(?=[ \t]*\r?$)",
        lambda m: m[1] + b"25",
        ref_input,
        flags=re.M,
    )
    if (
        matches != 1
        or full_input != (ordinary / "data/test/input/bwaves.in").read_bytes()
    ):
        raise ValueError(
            "One-step input differs from SPEC test beyond the step count"
        )
    for mode in ("sw", "hw"):
        directory = paired / mode
        result = json.loads((directory / "result.json").read_text())
        images = [
            Path(arg).resolve()
            for arg in result["command"]
            if Path(arg).name == "gem5.opt"
        ]
        if (
            result["status"] != "PASS"
            or result["steps"] != 1
            or result["variant"] != mode
            or result["guest_exit_code"] != 0
            or images != [simulator.resolve()]
            or (directory / "work/01/bwaves.in").read_bytes() != ref_input
        ):
            raise ValueError(
                f"{mode}: expected the same simulator and one-step input"
            )
    return ref


def run(ordinary, paired, batch):
    if any(
        (batch / name).exists()
        for name in ("work", "m5out", "result.json", "summary.json")
    ):
        raise ValueError("Use a fresh native batch directory")
    spec.require_executable(SIMULATOR)
    reference = paired_input(ordinary, paired, SIMULATOR)
    ref_counts = reference_counts(paired / "one-step-reference", 1)
    plan = json.loads((CASE / "workload.json").read_text())["sizes"]["test"]
    runtime = ordinary.parent / "tools/specdiff-runtime"
    spec.require_executable(runtime / "bin/specdiff")
    for item in plan["comparisons"]:
        spec.require_file(reference / item["file"])

    elf = ordinary / "build/bwaves.elf"
    markers, sites = ordinary_sites(elf)
    targets = probe_targets(markers, sites, "native")
    # All six math error transfers and the stack-canary failure must stay cold.
    expected = dict.fromkeys(markers, 0)
    expected.update(main=1, pow=sum(SITE_COUNTS.values()))
    if ref_counts != {**expected, **SITE_COUNTS}:
        raise ValueError(
            "One-step QEMU pow counts differ from the measured workload"
        )
    for site, count in SITE_COUNTS.items():
        expected[f"call_{site}"] = expected[f"resume_{site}"] = count
    run_one("native", elf, batch, targets, expected, reference, plan, runtime)
    compare_native(paired, batch, targets, sites)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ordinary-case", required=True, type=Path)
    parser.add_argument("--paired-batch", required=True, type=Path)
    parser.add_argument("--batch", required=True, type=Path)
    args = parser.parse_args()
    run(
        args.ordinary_case.resolve(),
        args.paired_batch.resolve(),
        args.batch.resolve(),
    )
