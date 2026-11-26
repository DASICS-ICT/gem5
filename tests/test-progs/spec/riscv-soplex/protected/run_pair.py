# SPDX-License-Identifier: BSD-3-Clause
"""Verify the software and hardware strtok gates on short and SPEC MPS inputs."""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
REPO = CASE.parents[3]
sys.path.insert(0, str(CASE.parent))
import run as spec

COMMON = ("gate_call", "gate_return", "b_strtok", "b___strtok_r")
HW = (
    "gate_proreg_g",
    "gate_proreg_f",
    "gate_clr_g",
    "gate_clr_f",
    "gate_leave",
)
VERIFIED = (
    "strtok_verified_first",
    "strtok_verified_next",
    "strtok_verified_null",
)
# Minimize X with X >= 7. The fixed-column format preserves all field offsets.
SHORT_MPS = """NAME          SHORT
ROWS
 N  OBJ
 G  FLOOR
COLUMNS
    X         OBJ                  1   FLOOR                1
RHS
    RIGHT     FLOOR                7
ENDATA
"""


def marker_pcs(elf, variant):
    prefix = os.environ.get("CROSS_COMPILE", "riscv64-linux-gnu-")
    listing = subprocess.check_output(
        [prefix + "nm", "--defined-only", elf], text=True
    )
    names = {*COMMON, *VERIFIED, "main", "strtok"}
    if variant == "hw":
        names.update(HW)
    pcs = {}
    for line in listing.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2] in names:
            if fields[2] in pcs:
                raise ValueError(f"{elf}: duplicate marker {fields[2]}")
            pcs[fields[2]] = int(fields[0], 16)
    if pcs.keys() != names or len(set(pcs.values())) != len(names):
        raise ValueError(
            f"{elf}: missing or aliased markers: {names - pcs.keys()}, {pcs}"
        )
    return pcs


def read_trace(path):
    rows = []
    with path.open(newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["call", "kind", "offset", "length"]:
            raise ValueError(f"{path}: unexpected token trace header")
        for call, row in enumerate(reader, start=1):
            kind = row["kind"]
            offset, length = int(row["offset"]), int(row["length"])
            if (
                int(row["call"]) != call
                or kind not in ("first", "next")
                or (not rows and kind != "first")
                or not (
                    (offset == -1 and length == 0)
                    or (1 <= offset and 0 < length and offset + length < 256)
                )
            ):
                raise ValueError(f"{path}: invalid trace row {row}")
            rows.append((kind, offset, length))
    return rows


def check_trace(size, rows, counts, variant):
    first = sum(kind == "first" for kind, _, _ in rows)
    nulls = sum(offset == -1 for _, offset, _ in rows)
    if size == "short":
        expected = []
        for line in SHORT_MPS.splitlines():
            if not line.startswith(" "):
                continue
            words = list(re.finditer(r"\S+", line))
            for index, word in enumerate(words):
                expected.append(
                    (
                        "first" if index == 0 else "next",
                        word.start(),
                        len(word[0]),
                    )
                )
            if len(words) < 5:
                expected.append(("next", -1, 0))
        if rows != expected:
            raise ValueError(
                f"Short MPS trace differs from its input fields: {rows}"
            )
        # Each of the five section headers calls ordinary strtok twice.
        ordinary = 10
    else:
        if (first, len(rows) - first) != (2174, 7422) or nulls == 0:
            raise ValueError(
                "Full MPS trace disagrees with ordinary data-row counts"
            )
        ordinary = 12
    markers = (*COMMON, *HW) if variant == "hw" else COMMON
    expected_counts = dict.fromkeys(markers, len(rows))
    expected_counts.update(
        main=1,
        strtok=ordinary,
        strtok_verified_first=first,
        strtok_verified_next=len(rows) - first,
        strtok_verified_null=nulls,
    )
    if counts != expected_counts:
        raise ValueError(
            f"Retired counts differ: expected {expected_counts}, got {counts}"
        )
    return dict(
        calls=len(rows),
        first=first,
        continuation=len(rows) - first,
        null_returns=nulls,
        ordinary=ordinary,
    )


def gem5_command(elf, pcs, m5out, current, invocation, *, trace=False):
    cmd = [
        "timeout",
        "--signal=INT",
        "--kill-after=15s",
        "2400s",
        str(REPO / "build/RISCV_DASICS/gem5.opt"),
        "--listener-mode=off",
        f"--outdir={m5out}",
    ]
    if trace:
        cmd.extend(("--debug-flags=PcCountTracker", "--debug-file=retire.log"))
    cmd.extend(
        [
            str(REPO / "configs/spec/riscv_se_dasics_v5_full.py"),
            "--workdir",
            str(current),
            "--stdout",
            str(current / invocation["stdout"]),
            "--stderr",
            str(current / invocation["stderr"]),
        ]
    )
    for name, pc in pcs.items():
        cmd.extend(("--retired-pc", f"{name}={pc:#x}"))
    cmd.extend([str(elf), *invocation["argv"]])
    return cmd


def guest_exit_ok(current, rc):
    return (
        rc == 0
        and re.search(
            r"^Exiting @ tick \d+ because exiting with last active thread context\. Guest exit code: 0$",
            (current / "gem5.log").read_text(),
            re.M,
        )
        is not None
    )


def spec_outputs(ordinary, current, plan, before, rc):
    outputs = [
        name
        for name, stamp in spec.file_state(current).items()
        if before.get(name) != stamp
    ]
    return spec.check_outputs(
        ordinary,
        "test",
        plan,
        current.parent,
        [dict(outputs=outputs, returncode=rc)],
        "gem5",
        runtime=ordinary.parent / "tools/specdiff-runtime",
    )


def run_one(size, variant, elf, pcs, ordinary, batch, plan):
    directory = batch / size / variant
    directory.mkdir(parents=True)
    current = directory / "work/01"
    m5out = directory / "m5out"
    (invocation,) = plan["runs"]
    if size == "test":
        before = spec.prepare_workdir(ordinary, "test", current, None)
    else:
        current.mkdir(parents=True)
        (current / "short.mps").write_text(SHORT_MPS)
        invocation = dict(invocation, argv=["-m10000", "short.mps"])
    cmd = gem5_command(elf, pcs, m5out, current, invocation)
    result = dict(status="FAIL", input=size, variant=variant, command=cmd)
    try:
        rc = spec.execute(cmd, current, invocation, "gem5")
        result["returncode"] = rc
        if not guest_exit_ok(current, rc):
            raise ValueError(
                f"{size}/{variant}: guest did not exit successfully"
            )
        counts = json.loads((m5out / "retired-pcs.json").read_text())
        rows = read_trace(current / "strtok-tokens.csv")
        result["tokens"] = check_trace(size, rows, counts, variant)
        if size == "short":
            text = (current / invocation["stdout"]).read_text()
            value = re.search(r"^solution value is:\s*(\S+)", text, re.M)
            if not value or float(value[1]) != 7.0:
                raise ValueError(f"{size}/{variant}: expected optimum 7")
        else:
            checks = spec_outputs(ordinary, current, plan, before, rc)
            result["comparisons"] = checks
            if {c["file"]: c["status"] for c in checks} != {
                "test.out": "PASS",
                "test.stderr": "PASS",
            }:
                raise ValueError(f"{size}/{variant}: SPEC outputs differ")
        result["status"] = "PASS"
        print(f"PASS {size}/{variant}: {result['tokens']}", flush=True)
        return rows, result["tokens"]
    except (ValueError, OSError, KeyError) as exc:
        result["error"] = str(exc)
        raise
    finally:
        spec.write_result(directory / "result.json", result)


def run(ordinary, elf_dir, batch):
    plan = json.loads((CASE / "workload.json").read_text())["sizes"]["test"]
    spec.require_executable(
        ordinary.parent / "tools/specdiff-runtime/bin/specdiff"
    )
    spec.require_file(ordinary / "data/test/input/test.mps")
    for comparison in plan["comparisons"]:
        spec.reference_file(ordinary, "test", comparison["file"])
    variants = {}
    for mode in ("sw", "hw"):
        elf = elf_dir / f"soplex-{mode}.elf"
        variants[mode] = elf, marker_pcs(elf, mode)
    # Both variants must pass the small input before either can run full SPEC.
    if any((batch / size).exists() for size in ("short", "test")):
        raise ValueError("Use a fresh batch for the short and test outputs")
    summary = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for size in ("short", "test"):
            jobs = [
                pool.submit(
                    run_one, size, mode, elf, pcs, ordinary, batch, plan
                )
                for mode, (elf, pcs) in variants.items()
            ]
            (left, left_totals), (right, _) = (job.result() for job in jobs)
            if left != right:
                raise ValueError(
                    f"{size}: software and hardware token traces differ"
                )
            summary[size] = left_totals
    spec.write_result(
        batch / "summary.json", dict(status="PASS", inputs=summary)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ordinary-case", type=Path, required=True)
    parser.add_argument("--elf-dir", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    args = parser.parse_args()
    run(
        args.ordinary_case.resolve(),
        args.elf_dir.resolve(),
        args.batch.resolve(),
    )
