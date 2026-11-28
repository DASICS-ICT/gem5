# SPDX-License-Identifier: BSD-3-Clause
"""Check the loaded images and locate the caller's retiring control transfer."""

import struct

from elftools.elf.elffile import ELFFile
from run_prf_pressure import (
    SAVED,
    inspect_image,
    require,
)

DATA = (
    "context_frame",
    "context_frame_end",
    "a_stack_bottom",
    "a_stack_top",
    "b_stack_bottom",
    "b_stack_top",
    "input_buffer",
    "output_buffer",
    "output_buffer_end",
)


def stack_transfer(reg, offset, store, fp=False):
    # The software gate addresses its trusted save frame through t0 (x5).
    base = (5 << 15) | (3 << 12)
    if store:
        return (
            offset >> 5 << 25
            | reg << 20
            | base
            | (offset & 31) << 7
            | (0x27 if fp else 0x23)
        )
    return offset << 20 | base | reg << 7 | (0x07 if fp else 0x03)


def pcrel_target(pc, hi, lo):
    return (
        pc
        + (hi & 0xFFFFF000)
        - ((hi >> 31) << 32)
        + (lo >> 20)
        - ((lo >> 31) << 12)
    )


def gate_image(elf_path, syms, hardware):
    with elf_path.open("rb") as stream:
        elf = ELFFile(stream)
        symtab = elf.get_section_by_name(".symtab")
        for name in (
            *DATA,
            "trusted_code_end",
            "dasics_call_displacement",
            "dasics_call_encoding",
        ):
            syms[name] = symtab.get_symbol_by_name(name)[0]["st_value"]
        trusted = elf.get_section_by_name(".text.trusted")
        data, base = trusted.data(), trusted["sh_addr"]

    a = syms["prf_measure_call"]
    hi, lo = struct.unpack_from("<II", data, a - base)
    require(
        hi & 0xFFF == 0x97
        and lo & 0xFFFFF == 0x080E7
        and pcrel_target(a, hi, lo) == syms["protected_gate"]
        and a + 8 == syms["prf_measure_return"],
        f"{elf_path}: unexpected measured AUIPC/JALR",
    )
    syms["caller_transfer"] = a + 4
    gate, end = syms["protected_gate"], syms["trusted_code_end"]
    sw_policy = [
        stack_transfer(r, 40 + i * 8, True) for i, r in enumerate(SAVED)
    ]
    sw_policy += [r << 7 | 0x13 for r in SAVED]
    sw_policy += [
        stack_transfer(r, 40 + i * 8, False) for i, r in enumerate(SAVED)
    ]
    hw_policy = [0xFFF0300B, 0x0000500B]
    policy = set(sw_policy + hw_policy)
    actual, common = [[], []], []
    pc = gate
    while pc < end:
        (word,) = struct.unpack_from("<I", data, pc - base)
        if word in policy:
            actual[pc >= syms["return_gate"]].append(word)
        elif pc == syms["gate_call"]:
            require(
                word == syms["dasics_call_encoding"]
                and pc + syms["dasics_call_displacement"]
                == syms["callee_entry"]
                and pc + 4 == syms["return_gate"],
                "DASICSCALL targets differ",
            )
            common.append(("domain call", syms["callee_entry"]))
        elif word & 0x7F == 0x17:
            # Input/stack address materialization moves with the gate code.
            rd = word >> 7 & 31
            (lo,) = struct.unpack_from("<I", data, pc + 4 - base)
            require(
                lo & 0xFFFFF == rd << 15 | rd << 7 | 0x13,
                "Expected AUIPC/ADDI",
            )
            common.append(("address", rd, pcrel_target(pc, word, lo)))
            pc += 4
        else:
            common.append(word)
        pc += 4
    expected = (
        [hw_policy[:1], hw_policy[1:]]
        if hardware
        else [sw_policy[:24], sw_policy[24:]]
    )
    require(
        actual == expected, "Incorrect integer gate entry or return policy"
    )
    for i, reg in enumerate(SAVED):
        for store in (False, True):
            require(
                common.count(stack_transfer(reg, 136 + i * 8, store, fp=True))
                == 1,
                "Incorrect floating-point gate policy",
            )
    return common, data[gate - base : end - base]


def inspect_pair(hw_paths, sw_paths):
    addresses = {}
    fixed_image = None
    for mode, paths in (("hw", hw_paths), ("sw", sw_paths)):
        addresses[mode] = {}
        fixed_gate = None
        for k in (0, 12):
            hardware = mode == "hw"
            symbols, segments = inspect_image(paths[k], k, hardware=hardware)
            gate, raw_gate = gate_image(paths[k], symbols, hardware)
            if fixed_gate is None:
                fixed_gate = symbols, raw_gate
            require(
                (symbols, raw_gate) == fixed_gate,
                f"{mode}: k changes the gate",
            )
            addresses[mode][k] = symbols
            # inspect_image validated the twelve entry writes before masking
            # their rd fields. Remove the gate (already compared by semantics)
            # to check every other loaded byte, segment and address.
            lo, hi = symbols["protected_gate"], symbols["trusted_code_end"]
            for base, _, _, _, contents in segments:
                if base <= lo < hi <= base + len(contents):
                    contents[lo - base : hi - base] = bytes(hi - lo)
            variable = {
                "gate_call",
                "return_gate",
                "trusted_code_end",
                "dasics_call_encoding",
                "dasics_call_displacement",
            }
            fixed_symbols = {
                n: v for n, v in symbols.items() if n not in variable
            }
            image = (fixed_symbols, segments, gate)
            if fixed_image is None:
                fixed_image = image
            require(
                image == fixed_image,
                f"{paths[k]}: unexpected code, data or symbol differences",
            )
    return addresses
