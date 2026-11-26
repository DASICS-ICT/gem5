# SPDX-License-Identifier: BSD-3-Clause
"""Profile starts and continuations of ordinary SoPlex strtok sequences."""

import argparse
import csv
import json
import os
import re
import shutil
import sys
from pathlib import Path

from strtok_sequences import analyze
from strtok_sites import discover

CASE = Path(__file__).resolve().parent
REPO = CASE.parents[3]
sys.path.insert(0, str(CASE.parent))
import run as spec


def profile(ordinary, out):
    runtime = ordinary.parent / "tools/specdiff-runtime"
    plan = json.loads((CASE / "workload.json").read_text())["sizes"]["test"]
    (invocation,) = plan["runs"]
    spec.require_file(ordinary / "data/test/input/test.mps")
    spec.require_executable(runtime / "bin/specdiff")
    for comparison in plan["comparisons"]:
        spec.reference_file(ordinary, "test", comparison["file"])
    source = ordinary / "build/soplex.elf"
    prefix = os.environ.get("CROSS_COMPILE", "riscv64-linux-gnu-")
    out.mkdir(parents=True)
    elf = out / "soplex.elf"
    shutil.copy2(source, elf)
    spec.verify_build(elf, prefix + "readelf")
    targets, sites = discover(elf, prefix)
    spec.write_result(
        out / "targets.json",
        {
            "source_elf": str(source),
            "targets": {k: hex(v) for k, v in targets.items()},
            "callers": {hex(pc): name for pc, name in sites.items()},
        },
    )
    m5out = out / "m5out"
    current = out / "work/01"
    before = spec.prepare_workdir(ordinary, "test", current, None)
    cmd = [
        "timeout",
        "--signal=INT",
        "--kill-after=15s",
        "1800s",
        str(REPO / "build/RISCV/gem5.opt"),
        "--listener-mode=off",
        f"--outdir={m5out}",
        "--debug-flags=PcCountTracker",
        "--debug-file=retire.log",
        str(REPO / "configs/spec/riscv_se_v5_full.py"),
        "--workdir",
        str(current),
        "--stdout",
        str(current / invocation["stdout"]),
        "--stderr",
        str(current / invocation["stderr"]),
    ]
    for label, pc in targets.items():
        cmd.extend(("--retired-pc", f"{label}={pc:#x}"))
    cmd.extend((str(elf), *invocation["argv"]))
    print(
        f"Tracking {len(sites)} calls to strtok, including AUIPC/JALR pairs",
        flush=True,
    )
    result = dict(status="FAIL", argv=invocation["argv"], command=cmd)
    try:
        rc = spec.execute(cmd, current, invocation, "gem5")
        result["process_exit"] = rc
        if rc or not re.search(
            r"^Exiting @ tick \d+ because exiting with last active thread context\. Guest exit code: 0$",
            (current / "gem5.log").read_text(),
            re.M,
        ):
            raise ValueError(
                f"Guest exit check failed; see {current}/gem5.log"
            )
        outputs = [
            f
            for f, stamp in spec.file_state(current).items()
            if before.get(f) != stamp
        ]
        checks = spec.check_outputs(
            ordinary,
            "test",
            plan,
            current.parent,
            [{"outputs": outputs, "returncode": rc}],
            "gem5",
            runtime=runtime,
        )
        result["comparisons"] = checks
        if len(checks) != len(plan["comparisons"]) or any(
            c["status"] != "PASS" for c in checks
        ):
            raise ValueError("SPEC outputs differ from references")
        raw = json.loads((m5out / "retired-pcs.json").read_text())
        if (
            raw.keys() != targets.keys()
            or any(type(n) is not int or n < 0 for n in raw.values())
            or raw["main"] != 1
        ):
            raise ValueError("Invalid retired counters or main control")
        summary = analyze(m5out / "retire.log", targets, raw)
        with (out / "callsites.csv").open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ("caller", "call_pc", "first", "continuation", "total")
            )
            for pc, caller in sorted(sites.items()):
                counts = summary["site_counts"][f"site_{pc:x}"]
                writer.writerow(
                    (
                        caller,
                        hex(pc),
                        counts["first"],
                        counts["continuation"],
                        counts["total"],
                    )
                )
        result.update(status="PASS", **summary)
        print(
            f"PASS: {summary['total_calls']:,} strtok calls = {summary['first_calls']:,} starts + "
            f"{summary['continuation_calls']:,} continuations",
            flush=True,
        )
    except (OSError, ValueError, KeyError) as exc:
        result["error"] = str(exc)
        raise
    finally:
        spec.write_result(out / "result.json", result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ordinary-case",
        type=Path,
        default=CASE,
        help="SoPlex directory with the ordinary static ELF and SPEC data",
    )
    parser.add_argument(
        "--outdir", type=Path, required=True, help="New directory for this run"
    )
    args = parser.parse_args()
    profile(args.ordinary_case.resolve(), args.outdir.resolve())
