# SPDX-License-Identifier: BSD-3-Clause
"""Check that both CalculiX ELFs protect just one matched LEN_TRIM call."""

import os
import sys
from pathlib import Path

from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE.parents[3] / "dasics/riscv-dasics-printf"))
from len_trim_sites import (
    TARGET,
    discover,
)
from roi_check import (
    FULL_POLICY,
    read_layout,
)

MARKERS = (
    "trim_gate",
    "gate_call",
    "gate_return",
    "gate_ret",
    "b_len_trim",
    "gate_proreg_g",
    "gate_proreg_f",
    "gate_clr_g",
    "gate_clr_f",
    "gate_leave",
)
LAYOUT = MARKERS + (
    TARGET,
    "getnewline_",
    "main",
    "__dasics_trusted_start",
    "__dasics_trusted_end",
    "__dasics_untrusted_start",
    "__dasics_untrusted_end",
    "__dasics_stack_bottom",
    "__dasics_stack_top",
    "__dasics_context_base",
    "__trim_input",
    "__trim_input_end",
    "b_trim_space",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_at(elf, pc, size):
    for seg in elf.iter_segments():
        if seg["p_type"] != "PT_LOAD":
            continue
        offset = pc - seg["p_vaddr"]
        if 0 <= offset and offset + size <= seg["p_filesz"]:
            elf.stream.seek(seg["p_offset"] + offset)
            return elf.stream.read(size)
    raise ValueError(f"No initialized ELF data at {pc:#x} for {size} bytes")


def function_image(path, name, blank=None):
    """Normalize just the PC-relative address of the eight-space constant."""
    with path.open("rb") as stream:
        elf = ELFFile(stream)
        (symbol,) = elf.get_section_by_name(".symtab").get_symbol_by_name(name)
        start = symbol["st_value"]
        raw = bytearray(read_at(elf, start, symbol["st_size"]))
        addresses = 0
        pos = 0
        while pos < len(raw):
            word = int.from_bytes(raw[pos : pos + 4], "little")
            if word & 3 != 3:
                pos += 2
                continue
            if word & 0x7F == 0x17:  # auipc
                addi = int.from_bytes(raw[pos + 4 : pos + 8], "little")
                rd = (word >> 7) & 31
                require(
                    addi & 0xFFFFF == (rd << 15 | rd << 7 | 0x13),
                    "Expected an AUIPC/ADDI reference to the blank constant",
                )
                upper = (word & 0xFFFFF000) - ((word >> 31) << 32)
                lower = (addi >> 20) - ((addi >> 31) << 12)
                target = start + pos + upper + lower
                require(
                    blank is None or target == blank,
                    "The clone references a non-private blank constant",
                )
                require(
                    read_at(elf, target, 8) == b" " * 8,
                    "The LEN_TRIM constant is not eight spaces",
                )
                raw[pos : pos + 4] = (word & 0xFFF).to_bytes(4, "little")
                raw[pos + 4 : pos + 8] = (addi & 0xFFFFF).to_bytes(4, "little")
                addresses += 1
            pos += 4
        require(addresses == 1, "Unexpected LEN_TRIM constant-reference count")
    return raw


def site_offsets(path, sites):
    """Label direct transfers by stable offsets within their caller."""
    with path.open("rb") as stream:
        symbols = ELFFile(stream).get_section_by_name(".symtab")
        offsets = set()
        for pc, caller in sites.items():
            (function,) = symbols.get_symbol_by_name(caller)
            offset = pc - function["st_value"]
            require(
                0 <= offset < function["st_size"],
                f"Call at {pc:#x} outside {caller}",
            )
            offsets.add((caller, offset))
    return offsets


def check_policy(layout, mode):
    for (lo, hi), ops in zip(layout.blocks, FULL_POLICY[mode], strict=True):
        entry = hi - 4 * len(ops)
        w = layout.gate_words
        # The common JAL x0 skips zero-filled instruction slots.
        j = w[lo]
        offset = (
            (j >> 31) * -(1 << 20)
            | ((j >> 12) & 255) << 12
            | ((j >> 20) & 1) << 11
            | ((j >> 21) & 1023) << 1
        )
        require(
            j & 0xFFF == 0x6F and lo + offset == entry and entry > lo,
            f"{mode}: invalid policy layout jump",
        )
        require(
            all(w[pc] == 0 for pc in range(lo + 4, entry, 4)),
            f"{mode}: unexpected padding in policy",
        )
        require(
            [w[pc] for pc in range(entry, hi, 4)] == list(ops),
            f"{mode}: incorrect register policy",
        )
    pcs = layout.addresses
    require(
        layout.gate_words[pcs["gate_call"]] == 0x0000908B
        and pcs["gate_return"] == pcs["gate_call"] + 4
        and layout.gate_words[pcs["gate_ret"]] == 0x8067,
        f"{mode}: unexpected cross-domain call or return",
    )


def inspect_pair(sw, hw, ordinary):
    """Return the common PC markers from the linked software/hardware pair."""
    sw, hw, ordinary = map(Path, (sw, hw, ordinary))
    prefix = os.environ.get("CROSS_COMPILE", "riscv64-linux-gnu-")
    layouts = [
        read_layout(
            path, mode, full=True, common_symbols=LAYOUT, gate_name="trim_gate"
        )
        for path, mode in ((sw, "sw"), (hw, "hw"))
    ]
    left, right = layouts
    require(
        left.addresses == right.addresses and left.blocks == right.blocks,
        "Software and hardware gate addresses differ",
    )
    require(
        left.sections == right.sections,
        "Loaded sections differ outside the register policies",
    )
    check_policy(left, "sw")
    check_policy(right, "hw")
    pcs = left.addresses
    require(
        pcs["__dasics_trusted_start"]
        <= pcs["trim_gate"]
        < pcs["gate_ret"]
        < pcs["__dasics_trusted_end"],
        "Gate is outside the trusted region",
    )
    input_base = pcs["__trim_input"]
    require(
        input_base % 8 == 0 and pcs["__trim_input_end"] == input_base + 8,
        "Expected an aligned, dedicated eight-byte staging area",
    )
    areas = sorted(
        (
            (input_base, input_base + 8),
            (pcs["__dasics_context_base"], pcs["__dasics_context_base"] + 256),
            (pcs["__dasics_stack_bottom"], pcs["__dasics_stack_top"]),
        )
    )
    require(
        all(lo < hi for lo, hi in areas)
        and all(a[1] <= b[0] for a, b in zip(areas, areas[1:])),
        "Overlapping or empty gate data areas",
    )

    old_entry, old_returns, old_sites, _ = discover(ordinary, prefix)
    original, returns, sites, _ = discover(sw, prefix)
    gate, _, gate_sites, _ = discover(sw, prefix, target="trim_gate")
    require(
        gate == pcs["trim_gate"] and original == pcs[TARGET],
        "Disassembly and ELF symbols disagree",
    )
    require(
        list(gate_sites.values()) == ["getnewline_"],
        "Expected exactly one direct caller of the gate",
    )
    (call_pc,) = gate_sites
    require(
        site_offsets(ordinary, old_sites)
        == site_offsets(sw, sites | gate_sites),
        "The original per-caller instruction offsets did not survive relinking",
    )
    siblings = sorted(
        pc for pc, caller in sites.items() if caller == "getnewline_"
    )
    require(
        len(siblings) == 2 and call_pc < siblings[0],
        "The gated call must precede the two ordinary calls in getnewline_",
    )
    with sw.open("rb") as stream:
        elf = ELFFile(stream)
        opcodes = read_at(elf, call_pc - 2, 6)
        require(
            opcodes[:2] == bytes.fromhex("0545")
            and int.from_bytes(opcodes[2:], "little") & 0xFFF == 0xEF,
            "Hot site is not c.li a0,1 followed by jal ra",
        )
    image = function_image(ordinary, TARGET)
    require(
        image
        == function_image(sw, "b_len_trim", pcs["b_trim_space"])
        == function_image(sw, TARGET),
        "The untrusted clone or ordinary routine differs from the original",
    )
    require(
        len(old_returns) == len(returns) == 1
        and old_returns[0] - old_entry == returns[0] - original,
        "Unexpected LEN_TRIM return layout",
    )
    body = pcs["b_len_trim"]
    require(
        pcs["__dasics_untrusted_start"] <= body
        and body + len(image) <= pcs["__dasics_untrusted_end"],
        "LEN_TRIM clone is outside B",
    )
    return {
        **{k: pcs[k] for k in MARKERS},
        "call_site": call_pc,
        "resume": call_pc + 4,
        "ordinary_trim": original,
        "b_ret": body + old_returns[0] - old_entry,
    }
