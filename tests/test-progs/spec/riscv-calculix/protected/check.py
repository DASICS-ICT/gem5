# SPDX-License-Identifier: BSD-3-Clause
"""Run one protected CalculiX gate and verify beampic outputs and retirements."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from cache_targets import selected_pairs
from check_layout import call_sites

CASE = Path(__file__).resolve().parents[1]
SPEC = CASE.parent
REPO = SPEC.parents[2]
sys.path.insert(0, str(SPEC))
import run as spec

CALLS = 585
# In the aligned beampic ELF the final fmod call resumes at this PC.
TAIL_PC = 0x108948
TAIL_OCCURRENCE = 291
CONTROL = ("call", "body", "return", "ret", "error")
PROTECTION = {"proreg_g": 0xFFF0300B, "proreg_f": 0xFFF0400B, "leave": 0x500B}


def gate_targets(elf, variant):
    prefix = os.environ.get("CROSS_COMPILE", "riscv64-linux-gnu-")
    output = subprocess.check_output(
        [prefix + "nm", "-n", "--defined-only", elf], text=True
    )
    symbols = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[2].startswith("dasics_fmod_"):
            symbols[fields[2].removeprefix("dasics_fmod_")] = int(
                fields[0], 16
            )

    roles = (*CONTROL, *PROTECTION) if variant == "gf" else CONTROL
    for name in ("gate", *roles):
        if name not in symbols:
            raise ValueError(f"Missing dasics_fmod_{name} in {elf}")
    if symbols["return"] != symbols["call"] + 4:
        raise ValueError("The trusted return path does not follow DASICSCALL")

    # Bind each GF counter to its opcode; also check the SW gate for unlabeled
    # PROREG/LEAVE instructions so absent symbols cannot mask a wrong build.
    disassembly = subprocess.check_output(
        [
            prefix + "objdump",
            "-d",
            f"--start-address={symbols['gate']}",
            f"--stop-address={symbols['ret'] + 4}",
            elf,
        ],
        text=True,
    )
    words = {
        int(pc, 16): int(word, 16)
        for pc, word in re.findall(
            r"^\s*([\da-f]+):\s+([\da-f]{8})\s", disassembly, re.M
        )
    }
    if (words.get(symbols["call"], 0) & 0x707F) != 0x0B:
        raise ValueError("The trusted call PC does not contain DASICSCALL.J")
    if words.get(symbols["ret"]) != 0x8067:
        raise ValueError("The trusted final return PC is not a ret")
    protected = {
        pc: word
        for pc, word in words.items()
        if (word & 0xFFFFF) in (0x300B, 0x400B) or word == PROTECTION["leave"]
    }
    expected = (
        {symbols[name]: word for name, word in PROTECTION.items()}
        if variant == "gf"
        else {}
    )
    if protected != expected or (
        variant == "sw" and PROTECTION.keys() & symbols.keys()
    ):
        raise ValueError(
            f"Unexpected register-protection instructions in {elf}"
        )
    return {f"dasics_fmod_{name}": symbols[name] for name in roles}


def check(args):
    elf = args.elf.resolve()
    assets = args.assets.resolve()
    out = args.outdir.resolve()
    case_assets = assets / CASE.name
    runtime = assets / "tools/specdiff-runtime"
    plan = json.loads((CASE / "workload.json").read_text())["sizes"]["test"]
    (invocation,) = plan["runs"]
    spec.require_file(case_assets / "data/test/input/beampic.inp")
    spec.require_executable(runtime / "bin/specdiff")
    for compare in plan["comparisons"]:
        spec.reference_file(case_assets, "test", compare["file"])
    gate = gate_targets(elf, args.variant)
    targets = gate.copy()
    sites = []
    fetch_trace = args.fetch_requests or args.cache_pairs is not None
    idle_wakes = args.idle_wakes or fetch_trace
    tail_stats = args.tail_stats or idle_wakes
    trace_calls = args.time_calls or tail_stats
    if trace_calls:
        for caller in ("Drand_setSeed", "Drand_value"):
            sites.extend(call_sites(elf, caller))
        for call, resume in sites:
            targets[f"call_{call:x}"] = call
            targets[f"resume_{call:x}"] = resume
    if tail_stats and TAIL_PC not in {resume for _, resume in sites}:
        raise ValueError(f"{TAIL_PC:#x} is not an fmod continuation in {elf}")

    # A fresh directory keeps the two gates' inputs, outputs and counts apart,
    # and prevents an interrupted run from passing on an earlier result.
    out.mkdir(parents=True, exist_ok=False)
    current = out / "work/01"
    before = spec.prepare_workdir(case_assets, "test", current, None)
    m5out = out / "m5out"
    m5out.mkdir()
    command = [
        "timeout",
        "--signal=INT",
        "--kill-after=5s",
        f"{args.timeout}s",
        str(args.gem5.resolve()),
        "--listener-mode=off",
        f"--outdir={m5out}",
    ]
    if trace_calls:
        flags = "PcCountTracker,O3Idle" if idle_wakes else "PcCountTracker"
        command.extend([f"--debug-flags={flags}", "--debug-file=retire.log"])
    command.extend(
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
    for name, pc in targets.items():
        command.extend(["--retired-pc", f"{name}={pc:#x}"])
    if tail_stats:
        command.extend(
            ["--stats-at-retire", hex(TAIL_PC), str(TAIL_OCCURRENCE)]
        )
    if fetch_trace:
        command.append("--trace-tail-fetch")
    if args.cache_pairs is not None:
        pairs = selected_pairs(args.cache_pairs)
        ticks = sorted(int(r[f"{args.variant}_send_tick"]) for r in pairs)
        command.extend(["--cache-hit-ticks", ",".join(map(str, ticks))])
    command.extend([str(elf), *invocation["argv"]])
    result = {"variant": args.variant, "elf": str(elf), "input": "test"}
    try:
        code = spec.execute(command, current, invocation, "gem5")
        result["returncode"] = code
        if code:
            raise ValueError(
                f"gem5 exited with code {code}; see {current}/gem5.log"
            )
        log = (current / "gem5.log").read_text()
        if not re.search(
            r"^Exiting @ tick \d+ because exiting with last active thread "
            r"context\. Guest exit code: 0$",
            log,
            re.M,
        ):
            raise ValueError(
                f"Missing successful guest exit in {current}/gem5.log"
            )
        outputs = [
            name
            for name, state in spec.file_state(current).items()
            if before.get(name) != state
        ]
        comparisons = spec.check_outputs(
            case_assets,
            "test",
            plan,
            current.parent,
            [{"returncode": code, "outputs": outputs}],
            "gem5",
            runtime=runtime,
        )
        result["comparisons"] = comparisons
        counts = json.loads((m5out / "retired-pcs.json").read_text())
        result["retired_pcs"] = counts
        expected = {
            name: 0 if name == "dasics_fmod_error" else CALLS for name in gate
        }
        if counts.keys() != targets.keys() or any(
            counts[name] != count for name, count in expected.items()
        ):
            raise ValueError(
                f"Retirements differ: expected {expected}; got {counts}"
            )
        if trace_calls:
            spec.require_file(m5out / "retire.log")
            if sum(counts[f"call_{call:x}"] for call, _ in sites) != CALLS:
                raise ValueError(f"Expected {CALLS} caller-side calls")
            for call, _ in sites:
                # Control flow can also reach a continuation without this call.
                if counts[f"resume_{call:x}"] < counts[f"call_{call:x}"]:
                    raise ValueError(
                        f"Missing continuation for call {call:#x}"
                    )
        if any(item["status"] != "PASS" for item in comparisons):
            raise ValueError("SPEC output validation failed")
        result["status"] = "OK"
        spec.report(
            "OK",
            f"{args.variant}: {CALLS} fmod round trips, both SPEC outputs passed",
        )
    except (OSError, ValueError) as error:
        result.update(status="FAIL", error=str(error))
        raise
    finally:
        spec.write_result(out / "result.json", result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("variant", choices=("sw", "gf"))
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument(
        "--outdir", required=True, type=Path, help="New run directory"
    )
    parser.add_argument(
        "--assets",
        type=Path,
        default=SPEC,
        help="SPEC tree with licensed data and specdiff",
    )
    parser.add_argument(
        "--gem5", type=Path, default=REPO / "build/RISCV_DASICS/gem5.opt"
    )
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument(
        "--time-calls",
        action="store_true",
        help="trace the retirement ticks of fmod calls and caller continuations",
    )
    parser.add_argument(
        "--tail-stats",
        action="store_true",
        help="trace calls and dump cumulative stats at the final fmod return",
    )
    parser.add_argument(
        "--idle-wakes",
        action="store_true",
        help="record O3 idle intervals and the callback that scheduled the next tick",
    )
    parser.add_argument(
        "--fetch-requests",
        action="store_true",
        help="trace fetch responses and retiring instructions from each buffer in the tail",
    )
    parser.add_argument(
        "--cache-pairs",
        type=Path,
        metavar="FETCH_BATCH",
        help="trace cache paths for the early-reply witnesses from a fetch batch",
    )
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        check(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        spec.report("FAIL", str(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
