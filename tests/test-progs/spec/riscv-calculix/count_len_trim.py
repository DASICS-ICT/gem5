# SPDX-License-Identifier: BSD-3-Clause
"""Count libgfortran trim calls during the ordinary SPEC CPU2006 beampic run."""

import argparse
import csv
import json
import os
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

from len_trim_sites import discover

CASE = Path(__file__).resolve().parent
REPO = CASE.parents[3]
sys.path.insert(0, str(CASE.parent))
import run as spec


def write_table(path, header, rows):
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def count_calls(ordinary, out):
    runtime = ordinary.parent / "tools/specdiff-runtime"
    plan = json.loads((CASE / "workload.json").read_text())["sizes"]["test"]
    (invocation,) = plan["runs"]
    spec.require_file(ordinary / "data/test/input/beampic.inp")
    spec.require_executable(runtime / "bin/specdiff")
    for item in plan["comparisons"]:
        spec.reference_file(ordinary, "test", item["file"])
    prefix = os.getenv("CROSS_COMPILE", "riscv64-linux-gnu-")
    source = ordinary / "build/calculix.elf"
    out.mkdir(parents=True)
    elf = out / "calculix.elf"
    shutil.copy2(source, elf)
    spec.verify_build(elf, prefix + "readelf")
    entry, returns, sites, main = discover(elf, prefix)
    targets = {"entry": entry, "main": main}
    targets.update({f"ret_{pc:x}": pc for pc in returns})
    targets.update({f"call_{pc:x}": pc for pc in sites})
    manifest = {
        "symbol": "_gfortran_string_len_trim",
        "source_elf": str(source),
        "entry_pc": hex(entry),
        "return_pcs": [hex(pc) for pc in returns],
        "main_pc": hex(main),
        "direct_calls": {hex(pc): caller for pc, caller in sites.items()},
    }
    spec.write_result(out / "targets.json", manifest)
    workdir = out / "work" / "01"
    before = spec.prepare_workdir(ordinary, "test", workdir, None)
    m5out = out / "m5out"
    cmd = [
        "timeout",
        "--signal=INT",
        "--kill-after=15s",
        "1800s",
        str(REPO / "build/RISCV/gem5.opt"),
        "--listener-mode=off",
        f"--outdir={m5out}",
        str(REPO / "configs/spec/riscv_se_v5_full.py"),
        "--workdir",
        str(workdir),
        "--stdout",
        str(workdir / invocation["stdout"]),
        "--stderr",
        str(workdir / invocation["stderr"]),
    ]
    for label, pc in targets.items():
        cmd.extend(["--retired-pc", f"{label}=0x{pc:x}"])
    cmd.extend([str(elf), *invocation["argv"]])
    print(
        f"Tracking {len(sites)} direct sites in {len(set(sites.values()))} callers, "
        f"entry {entry:#x}, {len(returns)} return(s) and main",
        flush=True,
    )
    result = {"status": "FAIL", "input": invocation["argv"], "command": cmd}
    try:
        rc = spec.execute(cmd, workdir, invocation, "gem5")
        result["process_exit"] = rc
        if rc or not re.search(
            r"^Exiting @ tick \d+ because exiting with last active thread context\. Guest exit code: 0$",
            (workdir / "gem5.log").read_text(),
            re.M,
        ):
            raise ValueError(
                f"Guest exit check failed; see {workdir / 'gem5.log'}"
            )
        outputs = [
            f
            for f, stamp in spec.file_state(workdir).items()
            if before.get(f) != stamp
        ]
        checks = spec.check_outputs(
            ordinary,
            "test",
            plan,
            workdir.parent,
            [{"outputs": outputs, "returncode": rc}],
            "gem5",
            runtime=runtime,
        )
        result["comparisons"] = checks
        raw = json.loads((m5out / "retired-pcs.json").read_text())
        if raw.keys() != targets.keys() or any(
            type(n) is not int or n < 0 for n in raw.values()
        ):
            raise ValueError("Incomplete or invalid retired PC counters")
        total = raw["entry"]
        ret_count = sum(raw[f"ret_{pc:x}"] for pc in returns)
        counts = {pc: raw[f"call_{pc:x}"] for pc in sites}
        by_caller = Counter()
        for pc, name in sites.items():
            by_caller[name] += counts[pc]

        def share(n):
            return f"{100 * n / total:.6f}" if total else ""

        write_table(
            out / "callsites.csv",
            ["caller", "call_pc", "count", "percent_of_entries"],
            (
                (sites[pc], hex(pc), n, share(n))
                for pc, n in sorted(
                    counts.items(), key=lambda row: (-row[1], row[0])
                )
            ),
        )
        write_table(
            out / "callers.csv",
            ["caller", "count", "percent_of_entries"],
            ((name, n, share(n)) for name, n in by_caller.most_common()),
        )
        result.update(
            entry_count=total,
            return_count=ret_count,
            callsite_sum=sum(counts.values()),
            main_count=raw["main"],
            static_sites=len(sites),
            active_sites=sum(n > 0 for n in counts.values()),
            static_callers=len(by_caller),
            active_callers=sum(n > 0 for n in by_caller.values()),
        )
        if (
            raw["main"] != 1
            or total != ret_count
            or total != sum(counts.values())
        ):
            raise ValueError(
                "Retirement counts disagree; see result.json and callsites.csv"
            )
        if len(checks) != len(plan["comparisons"]) or any(
            c["status"] != "PASS" for c in checks
        ):
            raise ValueError("SPEC output comparison failed")
        result["status"] = "PASS"
        print(
            f"PASS: {total:,} entries = {ret_count:,} returns = {sum(counts.values()):,} direct calls"
        )
    except (OSError, ValueError, KeyError) as error:
        result["error"] = str(error)
        raise
    finally:
        spec.write_result(out / "result.json", result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ordinary-case",
        type=Path,
        default=CASE,
        help="CalculiX directory containing the ordinary ELF and SPEC data",
    )
    parser.add_argument(
        "--outdir", type=Path, required=True, help="New directory for this run"
    )
    args = parser.parse_args()
    count_calls(args.ordinary_case.resolve(), args.outdir.resolve())
