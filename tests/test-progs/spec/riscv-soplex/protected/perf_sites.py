# SPDX-License-Identifier: BSD-3-Clause
"""Verify paired SoPlex gate layouts and locate retiring calls and outcomes."""

import os
import subprocess
import sys
from pathlib import Path

from elftools.elf.elffile import ELFFile

CASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CASE))
sys.path.insert(0, str(CASE.parent / "riscv-calculix/protected/len-trim"))
from layout_check import (
    check_policy,
    read_layout,
)
from strtok_sites import (
    LINE,
    READLINE,
    transfer,
)

MARKERS = (
    "main",
    "strtok",
    "strtok_gate",
    "gate_call",
    "b_strtok",
    "b___strtok_r",
    "gate_return",
    "gate_ret",
    "gate_proreg_g",
    "gate_proreg_f",
    "gate_clr_g",
    "gate_clr_f",
    "gate_leave",
)
SYMBOLS = MARKERS + (
    READLINE,
    "__dasics_trusted_start",
    "__dasics_trusted_end",
    "__dasics_untrusted_start",
    "__dasics_untrusted_end",
    "__dasics_context_base",
    "__dasics_stack_bottom",
    "__dasics_stack_top",
    "__strtok_b_rw_start",
    "__strtok_b_rw_end",
    "__strtok_b_ro_start",
    "__strtok_b_ro_end",
    "b_delim",
    "b_strtok_cursor",
)


def instructions(path, function):
    tool = os.environ.get("CROSS_COMPILE", "riscv64-linux-gnu-") + "objdump"
    listing = subprocess.check_output(
        [
            tool,
            f"--disassemble={function}",
            "--prefix-addresses",
            "--show-raw-insn",
            "-M",
            "no-aliases",
            path,
        ],
        text=True,
    )
    body = {}
    for line in listing.splitlines():
        match = LINE.match(line)
        if match:
            addr, _, raw, op, args = match.groups()
            body[int(addr, 16)] = int(raw, 16), op, (args or "").split(" <")[0]
    if not body:
        raise ValueError(f"{path}: empty disassembly of {function}")
    return body


def call_sites(body, pcs):
    sites = {}
    ordinary = 0
    previous = None
    for pc, (word, op, args) in body.items():
        dest = transfer(pc, word, op, args, previous)
        if dest in (pcs["strtok"], pcs["strtok_gate"]):
            # A JAL/JALR writes the caller's continuation address to ra.
            if word & 0xFFF not in (0xEF, 0xE7) or pc + 4 not in body:
                raise ValueError(f"Expected a returning call at {pc:#x}")
            if dest == pcs["strtok_gate"]:
                sites[pc] = pc + 4
            else:
                ordinary += 1
        previous = pc, word
    if len(sites) != 5 or ordinary != 2:
        raise ValueError(
            f"Expected 5 direct gate sites and 2 ordinary sites; "
            f"found {len(sites)} and {ordinary}"
        )
    return sites


def outcomes(body):
    """Locate the saved-cursor read and the NULL result on the glibc return path."""
    (branch,) = (
        pc
        for pc, (_, op, args) in body.items()
        if op == "c.beqz" and args.startswith("a0,")
    )
    next_input = int(body[branch][2].split(",")[1], 16)
    if (
        body[next_input][1:] != ("c.ld", "s1,0(a2)")
        or body[next_input + 2][1] != "c.j"
        or int(body[next_input + 2][2], 16) != branch + 2
    ):
        raise ValueError("Unexpected glibc saved-cursor branch")
    (null_result,) = (
        pc
        for pc, (_, op, args) in body.items()
        if (op, args) == ("c.li", "s2,0")
    )
    (ret,) = (
        pc
        for pc, (_, op, args) in body.items()
        if (op, args) == ("c.jr", "ra")
    )
    if body[null_result + 2][1] != "c.j":
        raise ValueError("NULL token does not jump to the shared return")
    epilogue = int(body[null_result + 2][2], 16)
    if not any(
        epilogue <= pc < ret and (op, args) == ("c.mv", "a0,s2")
        for pc, (_, op, args) in body.items()
    ):
        raise ValueError("Token result is not returned in a0")
    return {"next_input": next_input, "null_result": null_result}


def discover_pair(sw_elf, hw_elf):
    paths = [Path(sw_elf), Path(hw_elf)]
    layouts = []
    for path, mode in zip(paths, ("sw", "hw")):
        with path.open("rb") as stream:
            table = ELFFile(stream).get_section_by_name(".symtab")
            if any(
                table.get_symbol_by_name(name)
                for name in (
                    "checked_strtok",
                    "strtok_verified_first",
                    "strtok_verified_next",
                    "strtok_verified_null",
                )
            ):
                raise ValueError(
                    f"{path}: functional instrumentation is linked"
                )
        layout = read_layout(
            path,
            mode,
            full=True,
            common_symbols=SYMBOLS,
            gate_name="strtok_gate",
        )
        check_policy(layout, mode)
        layouts.append(layout)
    sw, hw = layouts
    if (
        sw.sections != hw.sections
        or sw.blocks != hw.blocks
        or sw.addresses != hw.addresses
    ):
        raise ValueError(
            "Loaded sections or symbols differ outside gate policies"
        )

    pcs = sw.addresses
    sites = call_sites(instructions(paths[0], READLINE), pcs)
    markers = {name: pcs[name] for name in MARKERS}
    markers.update(outcomes(instructions(paths[0], "b___strtok_r")))
    probes = [*markers.values(), *sites, *sites.values()]
    if len(set(probes)) != len(probes):
        raise ValueError("Overlapping retirement probe addresses")
    return markers, sites
