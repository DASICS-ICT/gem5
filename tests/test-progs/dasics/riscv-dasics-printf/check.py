# SPDX-License-Identifier: BSD-3-Clause
"""Check the guest result and the retired path through real glibc printf."""

import argparse
import gzip
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
EXPECTED = b"n=7\n"
GATE_OPS = {
    "gate_proreg_g": 0x0080300B,
    "gate_proreg_f": 0x0080400B,
    "gate_clr_g": 0x0400200B,
    "gate_leave": 0x0000500B,
}
CALL_PATH = (
    "gate_call",
    "probe_b_entry",
    "b_printf",
    "b___vfprintf_internal",
    "probe_b_clobber",
    "probe_b_return",
    "gate_return",
    "a_result",
    "emit_buffer",
)
RETIRE = re.compile(
    r"\[tid:0\] \[sn:\d+\] Committing instruction with PC \((0x[0-9a-f]+)=>"
)
FAULT_HEAD = re.compile(
    r"Inst \[tid:0\] \[sn:(\d+)\] PC \((0x[0-9a-f]+)=>.* has a fault"
)
FAULT_DELIVERED = re.compile(
    r"\[tid:0\] \[sn:(\d+)\] Committing instruction with fault"
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inspect_elf(elf, protected):
    prefix = os.environ.get("CROSS_COMPILE", "riscv64-linux-gnu-")
    table = subprocess.check_output(
        [prefix + "nm", "-n", "--defined-only", elf], text=True
    )
    symbols = {
        name: int(pc, 16)
        for pc, name in re.findall(r"^([0-9a-f]+) \w (\S+)$", table, re.M)
    }
    markers = {name: symbols[name] for name in CALL_PATH}
    start, end = (
        symbols[f"__dasics_untrusted_{limit}"] for limit in ("start", "end")
    )
    require(start < end and not ((start | end) & 7), "Invalid B code range")
    for name in CALL_PATH[1:6]:
        require(start <= markers[name] < end, f"{name} is outside B")
    if protected:
        markers.update({name: symbols[name] for name in GATE_OPS})
        lo, hi = (
            symbols[f"__dasics_trusted_{limit}"] for limit in ("start", "end")
        )
        for name in (
            "gate_call",
            "gate_return",
            "a_result",
            "emit_buffer",
            *GATE_OPS,
        ):
            require(lo <= markers[name] < hi, f"{name} is outside A")

    # The trace provides PCs; use the linked ELF to identify the actual opcodes.
    disassembly = subprocess.check_output(
        [prefix + "objdump", "-d", elf], text=True
    )
    words = {
        int(pc, 16): int(raw, 16)
        for pc, raw in re.findall(
            r"^\s*([0-9a-f]+):\s+([0-9a-f]{4,8})\s", disassembly, re.M
        )
    }
    if protected:
        for name, word in GATE_OPS.items():
            require(
                words.get(markers[name]) == word,
                f"Unexpected opcode at {name}",
            )
        call = markers["gate_call"]
        require(words[call] == 0x0002908B, "Expected DASICSCALL.JR ra,t0,0")
        require(markers["gate_return"] == call + 4, "Unexpected return gate")
    return markers, start, end, words


def verify_trace(path, markers, start, end, words, protected):
    counts = Counter()
    first = {}
    watched = set(markers.values())
    inside = False
    last_pc = None
    b_instructions = 0
    fault_sn = fault_pc = None
    with gzip.open(path, "rt") as trace:
        for line in trace:
            if ".commit:" not in line:
                continue
            match = RETIRE.search(line)
            if not match:
                if match := FAULT_HEAD.search(line):
                    fault_sn, fault_pc = int(match[1]), int(match[2], 16)
                elif match := FAULT_DELIVERED.search(line):
                    # SE system calls can be delivered as faults, without a
                    # normal retirement message for the ECALL instruction.
                    if int(match[1]) == fault_sn and inside:
                        require(
                            words[fault_pc] != 0x73, "B delivered an ECALL"
                        )
                continue
            pc = int(match[1], 16)
            if pc in watched:
                counts[pc] += 1
                first.setdefault(pc, len(first))
            if pc == markers["probe_b_entry"]:
                if protected:
                    require(
                        last_pc == markers["gate_call"],
                        "B entered outside DASICSCALL",
                    )
                inside = True
            if pc == markers["gate_return"]:
                require(
                    inside and last_pc == markers["probe_b_return"],
                    "Unexpected return to A",
                )
                inside = False
            if inside:
                require(
                    start <= pc < end,
                    f"B called code outside its range at {pc:#x}",
                )
                require(words[pc] != 0x73, "B retired an ECALL")
                b_instructions += 1
            last_pc = pc
    require(not inside and b_instructions > 0, "Missing complete B invocation")
    for name, pc in markers.items():
        require(
            counts[pc] == 1, f"{name} at {pc:#x} retired {counts[pc]} times"
        )
    order = list(CALL_PATH)
    if protected:
        before = sorted(
            (n for n in GATE_OPS if n != "gate_leave"), key=markers.get
        )
        order = before + order
        order.insert(order.index("a_result"), "gate_leave")
    positions = [first[markers[name]] for name in order]
    require(positions == sorted(positions), "Unexpected retirement order")
    return {
        "retired_path": [
            {"marker": name, "pc": hex(markers[name])} for name in order
        ],
        "b_range": [hex(start), hex(end)],
        "b_retired_instructions": b_instructions,
        "b_ecalls": 0,
    }


def run(args):
    elf = args.elf.resolve(strict=True)
    directory = args.outdir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    m5out = directory / "m5out"
    m5out.mkdir(exist_ok=True)
    protected = args.mode == "protected"
    guest_out, guest_err = (
        directory / name for name in ("guest.out", "guest.err")
    )
    trace = m5out / "commit.trace.gz"
    report = directory / "result.json"
    for output in (guest_out, guest_err, trace, report):
        output.unlink(missing_ok=True)
    config = (
        "riscv_se_dasics_v5_full.py" if protected else "riscv_se_v5_full.py"
    )
    command = [
        REPO / "build/RISCV_DASICS/gem5.opt",
        "--listener-mode=off",
        f"--outdir={m5out}",
        "--debug-flags=Commit",
        "--debug-file=commit.trace.gz",
        REPO / "configs/spec" / config,
        "--workdir",
        directory,
        "--stdout",
        guest_out,
        "--stderr",
        guest_err,
        elf,
    ]
    result = {"mode": args.mode, "elf": str(elf), "status": "FAIL"}
    try:
        markers, start, end, words = inspect_elf(elf, protected)
        log = directory / "gem5.log"
        with log.open("w") as stream:
            completed = subprocess.run(
                command, stdout=stream, stderr=subprocess.STDOUT, timeout=120
            )
        require(
            completed.returncode == 0,
            f"gem5 exit {completed.returncode}; see {log}",
        )
        require(
            re.search(
                r"because exiting with last active thread context\. Guest exit code: 0$",
                log.read_text(),
                re.M,
            ),
            f"Guest exit check failed; see {log}",
        )
        actual = guest_out.read_bytes()
        require(
            actual == EXPECTED,
            f"Guest stdout is {actual!r}, expected {EXPECTED!r}",
        )
        require(
            guest_err.read_bytes() == b"",
            f"Unexpected guest stderr in {guest_err}",
        )
        result.update(
            verify_trace(trace, markers, start, end, words, protected)
        )
        result.update(
            status="PASS",
            guest_exit=0,
            stdout_hex=actual.hex(),
            verified_printf_return=len(EXPECTED),
        )
        print(
            f"[OK] {args.mode}: guest exit 0, printf returned 4, stdout={actual!r}; {report}"
        )
    except (
        OSError,
        KeyError,
        ValueError,
        subprocess.SubprocessError,
    ) as error:
        result["error"] = str(error)
        raise
    finally:
        report.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plain", "protected"))
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    try:
        run(parser.parse_args())
    except (OSError, KeyError, ValueError, subprocess.SubprocessError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        sys.exit(1)
