# SPDX-License-Identifier: BSD-3-Clause
"""Validate the full-register DASICS gates and glibc copy paths before timing."""

import argparse
import gzip
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "riscv-dasics-printf"))
from check import (
    FAULT_DELIVERED,
    FULL_GATE_OPS,
    REPO,
    RETIRE,
    require,
)
from roi_check import (
    FULL_POLICY,
    PROBE_STAGES,
    read_layout,
    sentinel_pcs,
)

SIZES = (1, 2, 15, 16, 64, 4096)
MODES = ("sw", "hw")
ALIGNED = "b_wordcopy_fwd_aligned"
UNALIGNED = "b_wordcopy_fwd_dest_aligned"
B_PATH = ("probe_b_entry", "b_memcpy", ALIGNED, UNALIGNED, "probe_b_return")
COMMON = (
    "run_memcpy",
    "gate_call",
    "gate_return",
    *B_PATH,
    *FULL_GATE_OPS,
    "source",
    "destination",
    "roi_call_loop",
    "roi_begin",
    "roi_end",
    "__dasics_context_base",
    "__dasics_stack_bottom",
    "__dasics_stack_top",
    "__dasics_untrusted_start",
    "__dasics_untrusted_end",
)


def read_pair():
    layouts = {
        mode: read_layout(
            HERE / "build" / f"{mode}.elf",
            mode,
            full=True,
            sentinels=True,
            common_symbols=COMMON,
            gate_name="run_memcpy",
        )
        for mode in MODES
    }
    sw, hw = layouts.values()
    require(
        sw.addresses == hw.addresses and sw.blocks == hw.blocks,
        "Gate, data, probe, or ROI locations differ",
    )
    require(
        sw.sections == hw.sections,
        "Loaded bytes differ outside register policies",
    )
    pcs = sw.addresses
    lo, hi = pcs["__dasics_untrusted_start"], pcs["__dasics_untrusted_end"]
    require(all(lo <= pcs[name] < hi for name in B_PATH), "Callee outside B")
    require(pcs["gate_return"] == pcs["gate_call"] + 4, "Invalid return gate")
    for layout in layouts.values():
        require(
            layout.gate_words[pcs["gate_call"]] == 0x0000908B,
            "Expected DASICSCALL.JR ra,ra,0",
        )
    return layouts


def policy_pcs(layout, mode):
    sequence = []
    for (lo, hi), words in zip(layout.blocks, FULL_POLICY[mode], strict=True):
        first = hi - 4 * len(words)
        require(
            layout.gate_words[lo] & 0xFFF == 0x06F and first > lo,
            "Missing policy layout jump",
        )
        operations = list(range(first, hi, 4))
        require(
            [layout.gate_words[pc] for pc in operations] == list(words),
            "Unexpected protection instructions",
        )
        sequence += [lo, *operations]
    return sequence


def probe_words(layout):
    pcs = layout.addresses
    words = {}
    for stage in PROBE_STAGES:
        lo, hi = (pcs[f"full_{stage}_{bound}"] for bound in ("start", "end"))
        for (addr, _, flags, _), data in layout.sections.values():
            if flags & 4 and addr <= lo < hi <= addr + len(data):
                words.update(
                    {
                        pc: int.from_bytes(
                            data[pc - addr : pc - addr + 4], "little"
                        )
                        for pc in range(lo, hi, 4)
                    }
                )
                break
    return sentinel_pcs(pcs, words)


def check_calls(trace, layout, mode, length):
    pcs = layout.addresses
    lo, hi = pcs["__dasics_untrusted_start"], pcs["__dasics_untrusted_end"]
    # Functional coverage lives in trusted and untrusted code; both are
    # outside the masked policy blocks in the normalized section images.
    unseen = probe_words(layout)
    expected_policy = policy_pcs(layout, mode)
    selected = {
        p for start, end in layout.blocks for p in range(start, end, 4)
    }
    names = {pcs[name]: name for name in B_PATH}
    regions = []
    seen_policy = []
    inside = False
    previous = None
    with gzip.open(trace, "rt") as stream:
        for line in stream:
            match = RETIRE.search(line)
            if not match:
                if inside and FAULT_DELIVERED.search(line):
                    raise ValueError("Exception delivered in B")
                continue
            pc = int(match[1], 16)
            unseen.discard(pc)
            if pc in selected:
                seen_policy.append(pc)
            if pc == pcs["gate_call"]:
                require(not inside, "Nested B entry")
                regions.append([])
                inside = True
            elif pc == pcs["gate_return"]:
                require(inside, "Return gate reached without a call")
                inside = False
            elif inside:
                require(
                    lo <= pc < hi,
                    f"B retired code outside its range at {pc:#x}",
                )
                if previous == pcs["gate_call"]:
                    target = (
                        "probe_b_entry" if len(regions) == 1 else "b_memcpy"
                    )
                    require(
                        pc == pcs[target], f"Wrong DASICSCALL target {pc:#x}"
                    )
                if pc in names:
                    regions[-1].append(names[pc])
            previous = pc
    require(
        not unseen, "A register sentinel or a restore assertion was skipped"
    )
    helper = [ALIGNED] if length >= 16 else []
    require(
        not inside
        and regions
        == [
            ["probe_b_entry", "b_memcpy", *helper, "probe_b_return"],
            ["b_memcpy", *helper],
        ],
        f"Unexpected copy paths for {length} bytes: {regions}",
    )
    require(
        seen_policy == expected_policy * 2,
        "Unexpected retired policy or padding",
    )
    return regions


def run_job(directory, mode, length, layout):
    job = directory / f"{mode}-{length}"
    job.mkdir()
    m5out = job / "m5out"
    elf = HERE / "build" / f"{mode}.elf"
    command = [
        REPO / "build/RISCV_DASICS/gem5.opt",
        "--listener-mode=off",
        f"--outdir={m5out}",
        "--debug-flags=Commit",
        "--debug-file=commit.trace.gz",
        REPO / "configs/spec/riscv_se_dasics_v5_full.py",
        "--workdir",
        job,
        "--stdout",
        job / "guest.out",
        "--stderr",
        job / "guest.err",
        elf,
        str(length),
    ]
    with (job / "gem5.log").open("w") as log:
        subprocess.run(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=120,
        )
    require(
        (job / "guest.out").stat().st_size == 0
        and (job / "guest.err").stat().st_size == 0,
        f"Unexpected guest output: {job}",
    )
    require(
        "because exiting with last active thread context. Guest exit code: 0"
        in (job / "gem5.log").read_text(),
        f"Guest exit not confirmed: {job}",
    )
    paths = check_calls(m5out / "commit.trace.gz", layout, mode, length)
    return dict(mode=mode, bytes=length, guest_exit=0, b_paths=paths)


def main(directory):
    directory.mkdir(parents=True)
    report = directory / "checks.json"
    try:
        layouts = read_pair()
        with ThreadPoolExecutor(max_workers=len(SIZES) * len(MODES)) as pool:
            jobs = [
                pool.submit(run_job, directory, mode, size, layouts[mode])
                for mode, size in product(MODES, SIZES)
            ]
            results = [job.result() for job in jobs]
        evidence = dict(
            status="PASS",
            jobs=results,
            common_pcs={
                s: hex(p)
                for s, p in layouts["hw"].addresses.items()
                if s in COMMON
            },
            policies=dict(sw=86, hw=5),
        )
        report.write_text(json.dumps(evidence, indent=2) + "\n")
        print(
            f"[OK] both gates, six copy lengths, guarded buffers and register probes; {report}"
        )
    except Exception as err:
        report.write_text(
            json.dumps({"status": "FAIL", "error": str(err)}, indent=2) + "\n"
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, required=True)
    main(parser.parse_args().outdir.resolve())
