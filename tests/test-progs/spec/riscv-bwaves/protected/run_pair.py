# SPDX-License-Identifier: BSD-3-Clause
"""Run both protected bwaves gates on the verified one-step test grid."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from compare import (
    compare,
    probe_targets,
)
from pow_sites import discover_pair

CASE = Path(__file__).resolve().parents[1]
REPO = CASE.parents[3]
SIMULATOR = REPO / "build/RISCV_DASICS/gem5.opt"
sys.path.insert(0, str(CASE.parent))
import run as spec


def compare_outputs(current, reference, plan, runtime):
    # The official test oracle covers 25 steps. Use its comparison rules on
    # files produced by the ordinary ELF with precisely the one-step input.
    env = dict(os.environ, LC_ALL="C", SPEC=str(runtime))
    env.pop("SPEC_SPECDIFF", None)
    checks = []
    for item in plan["comparisons"]:
        name = item["file"]
        actual, expected = current / name, reference / name
        spec.require_file(actual)
        spec.require_file(expected)
        cmd = [
            runtime / "bin/specdiff",
            *item["args"],
            "--mis",
            expected,
            actual,
        ]
        with (current / (name + ".specdiff.log")).open("w") as output:
            rc = subprocess.run(
                cmd,
                cwd=current,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
            ).returncode
        checks.append(
            dict(
                file=name,
                reference=str(expected),
                args=item["args"],
                returncode=rc,
                status="FAIL" if rc else "PASS",
            )
        )
    return checks


def run_one(
    variant, elf, directory, targets, expected, reference, plan, runtime
):
    current = directory / "work/01"
    current.mkdir(parents=True)
    m5out = directory / "m5out"
    shutil.copyfile(reference / "bwaves.in", current / "bwaves.in")
    (invocation,) = plan["runs"]
    config = (
        "riscv_se_v5_full.py"
        if variant == "native"
        else "riscv_se_dasics_v5_full.py"
    )
    cmd = [
        "timeout",
        "--signal=INT",
        "--kill-after=15s",
        "6h",
        str(SIMULATOR),
        "--listener-mode=off",
        f"--outdir={m5out}",
        "--debug-flags=PcCountTracker",
        "--debug-file=retire.log",
        str(REPO / "configs/spec" / config),
        "--workdir",
        str(current),
        "--stdout",
        str(current / invocation["stdout"]),
        "--stderr",
        str(current / invocation["stderr"]),
    ]
    for name, pc in targets.items():
        cmd.extend(("--retired-pc", f"{name}={pc:#x}"))
    cmd.extend((str(elf), *invocation["argv"]))
    result = dict(
        status="FAIL", variant=variant, steps=1, command=cmd, targets=targets
    )
    try:
        rc = spec.execute(cmd, current, invocation, "gem5")
        result["returncode"] = rc
        if rc or not re.search(
            r"^Exiting @ tick \d+ because exiting with last active thread context\. Guest exit code: 0$",
            (current / "gem5.log").read_text(),
            re.M,
        ):
            raise ValueError(
                f"{variant}: guest exit failed; see {current}/gem5.log"
            )
        result["guest_exit_code"] = 0
        checks = compare_outputs(current, reference, plan, runtime)
        result["comparisons"] = checks
        if not all(c["status"] == "PASS" for c in checks):
            raise ValueError(
                f"{variant}: output differs from the one-step QEMU run"
            )
        counts = json.loads((m5out / "retired-pcs.json").read_text())
        result["retired_pcs"] = counts
        if counts != expected:
            raise ValueError(
                f"{variant}: expected {expected}, observed {counts}"
            )
        result["status"] = "PASS"
        calls = sum(counts[k] for k in counts if k.startswith("call_"))
        print(
            f"PASS {variant}: {calls:,} pow calls, three numerical outputs",
            flush=True,
        )
    except (OSError, ValueError, KeyError) as exc:
        result["error"] = str(exc)
        raise
    finally:
        spec.write_result(directory / "result.json", result)


def reference_counts(directory, steps):
    ref = json.loads((directory / "result.json").read_text())
    if ref["status"] != "PASS" or ref["steps"] != steps:
        raise ValueError(
            f"{directory}: expected a passing {steps}-step QEMU reference"
        )
    return ref["counts"]


def run(ordinary, batch):
    plan = json.loads((CASE / "workload.json").read_text())["sizes"]["test"]
    runtime = ordinary.parent / "tools/specdiff-runtime"
    spec.require_executable(runtime / "bin/specdiff")
    reference_counts(batch / "full-reference", 25)
    ref_counts = reference_counts(batch / "one-step-reference", 1)
    reference = batch / "one-step-reference/work/01"
    for name in ("bwaves.in", *(c["file"] for c in plan["comparisons"])):
        spec.require_file(reference / name)
    modes = ("sw", "hw")
    if any((batch / mode).exists() for mode in modes):
        raise ValueError("Use fresh software and hardware output directories")
    elfs = {mode: batch / "elfs" / f"bwaves-{mode}.elf" for mode in modes}
    markers, sites = discover_pair(elfs["sw"], elfs["hw"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = []
        for mode in modes:
            targets = probe_targets(markers, sites, mode)
            expected = dict.fromkeys(targets, ref_counts["pow"])
            expected.update(main=1, b_pow_error=0)
            for site in sites.values():
                expected[f"call_{site}"] = expected[f"resume_{site}"] = (
                    ref_counts[site]
                )
            jobs.append(
                pool.submit(
                    run_one,
                    mode,
                    elfs[mode],
                    batch / mode,
                    targets,
                    expected,
                    reference,
                    plan,
                    runtime,
                )
            )
        for job in jobs:
            job.result()
    report = compare(batch, markers, sites)
    if report["status"] != "PASS":
        raise ValueError(f"{report['status']}: see {batch}/summary.json")
    print(
        f"PASS: paired pow windows and whole-program results in {batch}/summary.json",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ordinary-case", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    args = parser.parse_args()
    run(args.ordinary_case.resolve(), args.batch.resolve())
