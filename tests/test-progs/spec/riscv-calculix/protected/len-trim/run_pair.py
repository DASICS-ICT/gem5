# SPDX-License-Identifier: BSD-3-Clause
"""Run the two DASICS gates on the same getnewline_ call in beampic."""

import argparse
import csv
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from layout_check import inspect_pair

CASE = Path(__file__).resolve().parents[2]
REPO = CASE.parents[3]
sys.path.insert(0, str(CASE.parent))
import run as spec

HW_MARKERS = {
    "gate_proreg_g",
    "gate_proreg_f",
    "gate_clr_g",
    "gate_clr_f",
    "gate_leave",
}


def run_one(variant, elf, batch, ordinary, plan, markers, calls, others):
    (invocation,) = plan["runs"]
    directory = batch / variant
    directory.mkdir()
    current = directory / "work/01"
    m5out = directory / "m5out"
    m5out.mkdir()
    before = spec.prepare_workdir(ordinary, "test", current, None)
    targets = {
        name: pc
        for name, pc in markers.items()
        if variant == "hw" or name not in HW_MARKERS
    }
    cmd = [
        "timeout",
        "--signal=INT",
        "--kill-after=15s",
        "2400s",
        str(REPO / "build/RISCV_DASICS/gem5.opt"),
        "--listener-mode=off",
        f"--outdir={m5out}",
        "--debug-flags=PcCountTracker",
        "--debug-file=retire.log",
        str(REPO / "configs/spec/riscv_se_dasics_v5_full.py"),
        "--workdir",
        str(current),
        "--stdout",
        str(current / invocation["stdout"]),
        "--stderr",
        str(current / invocation["stderr"]),
    ]
    for name, pc in targets.items():
        cmd.extend(("--retired-pc", f"{name}={pc:#x}"))
    cmd.extend([str(elf), *invocation["argv"]])
    result = dict(
        status="FAIL",
        variant=variant,
        input="test",
        argv=invocation["argv"],
        elf=str(elf),
        targets=targets,
        expected_gate_calls=calls,
        expected_ordinary_calls=others,
        command=cmd,
    )
    try:
        rc = spec.execute(cmd, current, invocation, "gem5")
        if rc or not re.search(
            r"^Exiting @ tick \d+ because exiting with last active thread context\. Guest exit code: 0$",
            (current / "gem5.log").read_text(),
            re.M,
        ):
            raise ValueError(
                f"{variant}: unsuccessful guest exit; see {current}/gem5.log"
            )
        result["guest_exit_code"] = 0
        outputs = [
            f
            for f, stamp in spec.file_state(current).items()
            if before.get(f) != stamp
        ]
        comparisons = spec.check_outputs(
            ordinary,
            "test",
            plan,
            current.parent,
            [{"outputs": outputs, "returncode": rc}],
            "gem5",
            runtime=ordinary.parent / "tools/specdiff-runtime",
        )
        result["comparisons"] = comparisons
        if any(c["status"] != "PASS" for c in comparisons):
            raise ValueError(f"{variant}: SPEC output comparison failed")
        counts = json.loads((m5out / "retired-pcs.json").read_text())
        result["retired_pcs"] = counts
        expected = {
            n: others if n == "ordinary_trim" else calls for n in targets
        }
        if counts != expected:
            raise ValueError(
                f"{variant}: unexpected retired PC counts: {counts}"
            )
        result["status"] = "PASS"
        print(
            f"PASS {variant}: {calls} protected calls, {others} ordinary calls",
            flush=True,
        )
    except (OSError, ValueError, KeyError) as exc:
        result["error"] = str(exc)
        raise
    finally:
        spec.write_result(directory / "result.json", result)


def run(ordinary, baseline, batch):
    prior = json.loads((baseline / "result.json").read_text())
    if prior["status"] != "PASS" or prior["input"] != ["-i", "beampic"]:
        raise ValueError("Expected a passing ordinary beampic baseline")
    elf = ordinary / "build/calculix.elf"
    if elf.read_bytes() != (baseline / "calculix.elf").read_bytes():
        raise ValueError("Ordinary ELF differs from the counted baseline")
    with (baseline / "callsites.csv").open() as source:
        # Identify the measured call by its caller and baseline PC.
        (calls,) = (
            int(r["count"])
            for r in csv.DictReader(source)
            if r["caller"] == "getnewline_"
            and int(r["call_pc"], 16) == 0xB4108
        )
    if calls <= 0 or prior["entry_count"] < calls:
        raise ValueError("Invalid baseline counts for the selected call")
    others = prior["entry_count"] - calls
    plan = json.loads((CASE / "workload.json").read_text())["sizes"]["test"]
    for comparison in plan["comparisons"]:
        spec.reference_file(ordinary, "test", comparison["file"])
    spec.require_file(ordinary / "data/test/input/beampic.inp")
    spec.require_executable(
        ordinary.parent / "tools/specdiff-runtime/bin/specdiff"
    )
    modes = ("sw", "hw")
    elfs = {mode: batch / "elfs" / f"calculix-{mode}.elf" for mode in modes}
    markers = inspect_pair(elfs["sw"], elfs["hw"], elf)
    spec.write_result(
        batch / "layout.json", {k: hex(v) for k, v in markers.items()}
    )
    print(
        f"Both ELFs verified. Expect {calls} protected and {others} ordinary calls.",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [
            pool.submit(
                run_one,
                mode,
                elfs[mode],
                batch,
                ordinary,
                plan,
                markers,
                calls,
                others,
            )
            for mode in modes
        ]
        for future in jobs:
            future.result()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ordinary-case", type=Path, required=True)
    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Ordinary count directory containing result.json and callsites.csv",
    )
    parser.add_argument(
        "--batch",
        type=Path,
        required=True,
        help="Batch with elfs/ and fresh sw/ and hw/ output paths",
    )
    args = parser.parse_args()
    run(
        args.ordinary_case.resolve(),
        args.baseline.resolve(),
        args.batch.resolve(),
    )
