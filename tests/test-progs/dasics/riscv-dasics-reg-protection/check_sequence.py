#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

"""Validate both sequential gates and their committed calls before timing."""

import argparse
import gzip
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import measure
import measure_sequence
from check_clobber import COMMIT
from src.run import run_case

MODES = ("software", "proreg_gf")
SHORT_COUNT = 4
COMMON_LAYOUT = (
    "roi_loop",
    "roi_work_begin",
    "roi_work_end",
    "seq_call_b",
    "seq_after_b",
    "seq_call_c",
    "seq_after_c",
    "sequence_gate",
    "b_entry",
    "b_end",
    "c_entry",
    "c_end",
    "context_frame",
    "a_stack_top",
    "b_stack_bottom",
    "b_stack_top",
    "c_stack_bottom",
    "c_stack_top",
)


def protection_words(mask):
    return {
        "sequence_proreg_g": (mask << 20) | 0x300B,
        "sequence_proreg_f": (mask << 20) | 0x400B,
        "sequence_leave": 0x0000500B,
    }


def elf_symbols(elf):
    prefix = os.environ.get("CROSS_COMPILE", "riscv64-linux-gnu-")
    symbols = {}
    output = subprocess.check_output(
        [prefix + "nm", "--defined-only", elf], text=True
    )
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 3:
            symbols[fields[2]] = int(fields[0], 16)

    return symbols


def section(elf, name):
    prefix = os.environ.get("CROSS_COMPILE", "riscv64-linux-gnu-")
    return subprocess.check_output(
        [
            prefix + "objcopy",
            "-O",
            "binary",
            "--only-section=" + name,
            elf,
            "/dev/stdout",
        ]
    )


def gate_bytes(symbols, trusted):
    base = symbols["trusted_start"]
    return trusted[
        symbols["sequence_gate"]
        - base : symbols["sequence_gate_ret"]
        + 4
        - base
    ]


def inspect(mode, count, full=False):
    elf = measure_sequence.elf_path(mode, count, full=full)
    symbols = elf_symbols(elf)
    hw = mode == "proreg_gf"
    mask = 0xFFF if full else 0x008
    measure.require(
        symbols.get("roi_sequence_mask", 0x008) == mask,
        f"{elf}: expected protection mask {mask:#x}",
    )
    for label, value in (
        ("roi_iterations", count),
        ("roi_int_proreg", int(hw)),
        ("roi_fp_proreg", int(hw)),
    ):
        measure.require(
            symbols.get(label) == value, f"{elf}: expected {label}={value}"
        )

    trusted = section(elf, ".text.trusted")
    base = symbols["trusted_start"]
    gate = symbols["sequence_gate"]
    gate_ret = symbols["sequence_gate_ret"]

    def word(pc):
        return int.from_bytes(trusted[pc - base : pc - base + 4], "little")

    # Check executable words so a missing symbol cannot disguise an active
    # PROREG/LEAVE in the software gate. Mask bits [31:20] select registers.
    protected = {
        pc: word(pc)
        for pc in range(gate, gate_ret + 1, 4)
        if word(pc) & 0xFFFFF in (0x300B, 0x400B) or word(pc) == 0x500B
    }
    expected = (
        {
            symbols[label]: value
            for label, value in protection_words(mask).items()
        }
        if hw
        else {}
    )
    measure.require(
        protected == expected, f"{elf}: unexpected protection instructions"
    )
    measure.require(
        word(symbols["gate_call"]) == 0x0005108B
        and symbols["return_gate"] == symbols["gate_call"] + 4
        and word(gate_ret) == 0x8067,
        f"{elf}: incorrect DASICSCALL.JR or trusted return",
    )
    # The caller, marker locations, B and C (including their padding) and
    # data layout must match; the implementation inside the gate may differ.
    layout = (
        tuple(symbols[name] for name in COMMON_LAYOUT),
        trusted[: gate - base],
        section(elf, ".text.untrusted"),
    )
    return symbols, layout, gate_bytes(symbols, trusted)


def functional_case(mode, full):
    group = "sequence-full" if full else "sequence"
    return f"{group}-{'gf' if mode == 'proreg_gf' else 'sw'}"


def check_layouts(full=False):
    short_symbols = {}
    functional_gates = {}
    for mode in MODES:
        case = functional_case(mode, full)
        elf = measure.build_dir() / f"riscv-dasics-reg-protection-{case}.elf"
        functional_gates[mode] = gate_bytes(
            elf_symbols(elf), section(elf, ".text.trusted")
        )
    for count in (SHORT_COUNT, *measure.ITERATIONS):
        layouts = []
        for mode in MODES:
            symbols, layout, gate = inspect(mode, count, full)
            layouts.append(layout)
            measure.require(
                gate == functional_gates[mode],
                f"{mode} N={count}: timed gate differs from the functional gate",
            )
            if full:
                _, narrow_layout, _ = inspect(mode, count)
                measure.require(
                    layout == narrow_layout,
                    f"{mode} N={count}: caller, callee or layout differs from s3/fs3",
                )
            if count == SHORT_COUNT:
                short_symbols[mode] = symbols
        measure.require(
            layouts[0] == layouts[1], f"N={count}: mismatched paired layout"
        )
    return short_symbols


def check_trace(mode, symbols, trace):
    chain = []
    for target in ("b", "c"):
        chain += [f"seq_call_{target}", "sequence_gate"]
        if mode == "proreg_gf":
            chain.extend(("sequence_proreg_g", "sequence_proreg_f"))
        chain += ["gate_call", target + "_entry", "return_gate"]
        if mode == "proreg_gf":
            chain.append("sequence_leave")
        chain += ["sequence_gate_ret", f"seq_after_{target}"]

    expected = (
        chain * measure.WARMUP
        + ["roi_work_begin"]
        + chain * SHORT_COUNT
        + ["roi_work_end"]
    )
    watched = {symbols[name] for name in expected}
    position, last_seq = 0, -1
    with gzip.open(trace, "rt") as stream:
        for line in stream:
            match = COMMIT.search(line)
            if not match:
                continue
            seq, pc = int(match[1]), int(match[2], 16)
            if pc not in watched:
                continue
            want = expected[position] if position < len(expected) else None
            measure.require(
                seq > last_seq and want is not None and pc == symbols[want],
                f"{mode}: commit {position} at {pc:#x} (sn={seq}), expected {want}",
            )
            position, last_seq = position + 1, seq
    measure.require(
        position == len(expected), f"{mode}: incomplete Commit trace"
    )


def run_checks(outdir, full=False):
    short_symbols = check_layouts(full)
    args = argparse.Namespace(
        repo=measure.REPO,
        gem5=measure.REPO / "build/RISCV_DASICS/gem5.opt",
        config=measure.REPO / "configs/dasics/riscv_dasics_o3_v5_full.py",
        cpu="v5_full",
        outdir=outdir,
    )

    def trace(mode):
        result = measure_sequence.run_one(
            outdir, mode, SHORT_COUNT, trace=True, full=full
        )
        check_trace(
            mode,
            short_symbols[mode],
            Path(result["output_dir"]) / "debug.trace.gz",
        )
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        functional = list(
            pool.map(
                lambda name: run_case(args, name),
                [functional_case(mode, full) for mode in MODES],
            )
        )
        for case in functional:
            measure.require(
                case["exit_code"] == 0, f"Functional failure: {case['log']}"
            )
        sw, gf = pool.map(trace, MODES)
    for key, per_chain in zip(
        ("numInsts", "numLoadInsts", "numStoreInsts"),
        measure_sequence.expected_deltas(full),
        strict=True,
    ):
        stat = "system.cpu.commitStats0." + key
        difference = sw["statistics"][stat] - gf["statistics"][stat]
        measure.require(
            difference == per_chain * SHORT_COUNT,
            f"Unexpected {key} delta {difference}",
        )
    mask = 0xFFF if full else 0x008
    return {
        "status": "PASS",
        "sequence_mask": mask,
        "functional": [r["case"] for r in functional],
        "layout_checked_chain_counts": [SHORT_COUNT, *measure.ITERATIONS],
        "warmup_chains_per_mode": measure.WARMUP,
        "measured_chains_per_mode": SHORT_COUNT,
        "B_calls_per_mode": SHORT_COUNT,
        "C_calls_per_mode": SHORT_COUNT,
        "dasicscall_per_mode": 2 * SHORT_COUNT,
        "gf_commits": {
            name: 2 * SHORT_COUNT for name in protection_words(mask)
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument(
        "--full",
        action="store_true",
        help="protect all twelve s/fs register pairs",
    )
    args = parser.parse_args()
    directory = args.outdir.resolve()
    directory.mkdir(parents=True)
    try:
        result = run_checks(directory, args.full)
    except (
        OSError,
        ValueError,
        KeyError,
        EOFError,
        subprocess.CalledProcessError,
    ) as error:
        result = {"status": "FAIL", "error": str(error)}
    measure.write_json(directory / "checks.json", result)
    print(
        result["status"],
        result.get("error", directory / "checks.json"),
        flush=True,
    )
    return int(result["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
