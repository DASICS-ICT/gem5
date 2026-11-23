#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

"""Verify a short batch of committed callee writes before measuring cycles."""

import argparse
import gzip
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path

import measure

SHORT_COUNT = 4
SAVED = (8, 9, *range(18, 28))  # s0-s11 and fs0-fs11 use the same indices.
INT_SCRATCH = (5, 6, 7, 28, 29, 30, 31, 11, 12, 13, 14, 15)  # t0-t6, a1-a5
FP_SCRATCH = (*range(8), *range(28, 32))  # ft0-ft11
COMMIT = re.compile(
    r"system\.cpu\.commit: \[tid:0\] \[sn:(\d+)\] "
    r"Committing instruction with PC \((0x[\da-f]+)=>"
)


def inspect_elf(job, prefix):
    elf = measure.build_dir() / "roi" / f"{measure.job_name(job)}.elf"
    symbols = {}
    for line in subprocess.check_output(
        [prefix + "nm", elf], text=True
    ).splitlines():
        fields = line.split()
        if len(fields) == 3:
            symbols[fields[2]] = int(fields[0], 16)
    fp = "fp_clobber_count" in job
    k = job["fp_clobber_count" if fp else "clobber_count"]
    expected_symbols = {
        "roi_clobber_count": k,
        "roi_iterations": job["iterations"],
        "roi_int_proreg": int(job["mode"] in ("proreg", "proreg_gf")),
        "roi_workload": int(job["workload"] == "compute"),
    }
    if fp:
        expected_symbols.update(
            roi_fp_clobber=1, roi_fp_proreg=int(job["mode"] == "proreg_gf")
        )
    for key, value in expected_symbols.items():
        measure.require(
            symbols.get(key) == value, f"{elf.name}: unexpected {key}"
        )

    text = subprocess.check_output(
        [prefix + "objdump", "-d", "-j", ".text.untrusted", elf], text=True
    )
    words = {
        int(pc, 16): int(raw, 16)
        for pc, raw in re.findall(
            r"^\s*([\da-f]+):\s+([\da-f]{8})\b", text, re.M
        )
    }
    begin, end = symbols["clobber_writes_begin"], symbols["clobber_writes_end"]
    measure.require(
        end == begin + 12 * 4 and words[end] == 0x8067,
        f"{elf.name}: expected twelve writes followed by ret",
    )
    if fp:
        # addi t6,x0,0x5a5 supplies identical nonzero bits to all FP writes.
        measure.require(
            words.get(begin - 4) == 0x5A500F93,
            f"{elf.name}: incorrect FP source setup",
        )
    scratch = FP_SCRATCH if fp else INT_SCRATCH
    for slot, dest in enumerate(SAVED[:k] + scratch[k:]):
        if fp:
            expected = 0xF2000053 | (31 << 15) | (dest << 7)  # fmv.d.x fd,t6
        else:
            expected = ((0x101 + slot) << 20) | (dest << 7) | 0x13
        pc = begin + 4 * slot
        measure.require(
            words[pc] == expected, f"{elf.name}: incorrect write at {pc:#x}"
        )
        words[pc] &= ~(31 << 7)

    # Within one workload only the destination fields may vary among B images.
    layout = tuple(
        symbols[key]
        for key in (
            "roi_loop",
            "roi_gate_call",
            "roi_work_begin",
            "roi_work_end",
            "protected_gate",
            "callee_entry",
            "clobber_writes_begin",
            "clobber_writes_end",
            "context_frame",
            "b_stack_top",
            "input_buffer",
            "output_buffer",
        )
    )
    return symbols, (layout, words)


def verify_commits(trace, symbols):
    begin, end = symbols["clobber_writes_begin"], symbols["clobber_writes_end"]
    start = begin - 4 if symbols.get("roi_fp_clobber") else begin
    call = [
        symbols["gate_call"],
        symbols["callee_entry"],
        *range(start, end + 4, 4),
        symbols["return_gate"],
    ]
    # Include both markers to distinguish warmup calls from measured calls.
    expected = (
        call * measure.WARMUP
        + [symbols["roi_work_begin"]]
        + call * SHORT_COUNT
        + [symbols["roi_work_end"]]
    )
    watched = set(expected)
    index = 0
    previous_sn = -1
    with gzip.open(trace, "rt") as stream:
        for line in stream:
            match = COMMIT.search(line)
            if match:
                sn, pc = int(match[1]), int(match[2], 16)
                if pc not in watched:
                    continue
                measure.require(
                    sn > previous_sn
                    and index < len(expected)
                    and pc == expected[index],
                    f"Unexpected commit at {pc:#x}, sn={sn}, event={index}",
                )
                index += 1
                previous_sn = sn
    measure.require(
        index == len(expected),
        f"Missing commit events: {index}/{len(expected)}",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument(
        "--fp", action="store_true", help="Check floating-point callee writes."
    )
    parser.add_argument("--jobs", type=int, choices=range(1, 17), default=16)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    args.outdir = args.outdir.resolve()
    if args.timeout <= 0 or args.outdir.exists():
        parser.error("Use a positive timeout and a new output directory.")
    modes = ("proreg", "proreg_gf") if args.fp else ("software", "proreg")
    count_key = "fp_clobber_count" if args.fp else "clobber_count"
    jobs = [
        {
            "mode": mode,
            "workload": workload,
            "iterations": SHORT_COUNT,
            count_key: k,
        }
        for mode, workload, k in product(
            modes, measure.WORKLOADS, measure.CLOBBER_COUNTS
        )
    ]
    layouts = {}
    images = {}
    for job in jobs:
        symbols, layout = inspect_elf(
            job, os.environ.get("CROSS_COMPILE", "riscv64-linux-gnu-")
        )
        images[measure.job_name(job)] = symbols
        measure.require(
            layouts.setdefault(job["workload"], layout) == layout,
            f"{measure.job_name(job)}: unmatched caller, callee or data layout",
        )

    def run(job):
        result = measure.run_job(args, job, debug_flags="Commit")
        if result["status"] == "PASS":
            try:
                verify_commits(
                    Path(result["output_dir"]) / "debug.trace.gz",
                    images[result["name"]],
                )
                result.update(
                    warmup_calls=measure.WARMUP,
                    measured_calls=SHORT_COUNT,
                    saved_writes_per_call=job[count_key],
                )
            except (OSError, EOFError, ValueError) as error:
                result.update(status="FAIL", error=str(error))
        measure.write_json(Path(result["output_dir"]) / "result.json", result)
        print(
            result["name"],
            result["status"],
            result.get("error", ""),
            flush=True,
        )
        return result

    args.outdir.mkdir(parents=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        results = list(executor.map(run, jobs))
    passed = all(r["status"] == "PASS" for r in results)
    measure.write_json(
        args.outdir / "checks.json",
        {
            "status": "PASS" if passed else "FAIL",
            "jobs": results,
        },
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
