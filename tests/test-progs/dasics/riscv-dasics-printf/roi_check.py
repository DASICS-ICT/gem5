# SPDX-License-Identifier: BSD-3-Clause
"""Check the paired DASICS printf gates before measuring the ROI."""

import argparse
import gzip
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NamedTuple

import check
from elftools.elf.constants import SH_FLAGS
from elftools.elf.elffile import ELFFile

HERE = Path(__file__).resolve().parent
BLOCKS = ("roi_save", "roi_restore")
COMMON = (
    *check.CALL_PATH,
    *check.GATE_OPS,
    "run_printf",
    "roi_call_loop",
    "roi_begin",
    "roi_end",
    "b_stdout",
    "b_format",
    "b_buffer",
    "__dasics_context_base",
    "__dasics_stack_bottom",
    "__dasics_stack_top",
    "__dasics_untrusted_start",
    "__dasics_untrusted_end",
)
# Exact instructions retired in each patch region, apart from its common jump.
POLICY = {
    "sw": (
        (0x0332B423, 0x0932B427, 0x00000993, 0xF20009D3, 0x00000F93),
        (0x0282B983, 0x0882B987),
    ),
    "hw": (
        (0x0080300B, 0x0080400B, 0x0400200B),
        (0x0000500B,),
    ),
}


class Layout(NamedTuple):
    addresses: dict
    blocks: list
    sections: dict
    gate_words: dict


def reg_protection_word(word):
    return (
        (word & 0xFFFFF) in (0x300B, 0x400B)
        or word in (0x0000308B, 0x0000408B, 0x0000500B)
        or (word & 0xF80FFFFF) in (0x200B, 0x600B)
    )


def read_layout(path, mode):
    with path.open("rb") as stream:
        elf = ELFFile(stream)
        symbols = {
            sym.name: sym
            for sym in elf.get_section_by_name(".symtab").iter_symbols()
        }
        pcs = {name: symbols[name]["st_value"] for name in COMMON}
        blocks = [
            (
                symbols[f"{label}_start"]["st_value"],
                symbols[f"{label}_end"]["st_value"],
            )
            for label in BLOCKS
        ]
        gate = pcs["run_printf"]
        gate_end = gate + symbols["run_printf"]["st_size"]
        check.require(
            gate
            <= blocks[0][0]
            < blocks[0][1]
            <= pcs["gate_call"]
            < pcs["gate_return"]
            <= blocks[1][0]
            < blocks[1][1]
            <= gate_end,
            f"{mode}: invalid policy regions",
        )
        sections = {}
        for section in elf.iter_sections():
            if not section["sh_flags"] & SH_FLAGS.SHF_ALLOC:
                continue
            addr = section["sh_addr"]
            size = section["sh_size"]
            layout = (addr, size, section["sh_flags"], section["sh_type"])
            data = bytearray()
            if (
                section["sh_type"] != "SHT_NOBITS"
                and section.name != ".note.gnu.build-id"
            ):
                data = bytearray(section.data())
            if section.name == ".text":
                check.require(
                    addr <= gate < gate_end <= addr + size,
                    "Gate outside .text",
                )
                words = {
                    pc: int.from_bytes(
                        data[pc - addr : pc - addr + 4], "little"
                    )
                    for pc in range(gate, gate_end, 4)
                }
                hw_words = [
                    word
                    for word in words.values()
                    if reg_protection_word(word)
                ]
                expected = (
                    [*POLICY["hw"][0], *POLICY["hw"][1]]
                    if mode == "hw"
                    else []
                )
                check.require(
                    hw_words == expected,
                    f"{mode}: unexpected register instruction",
                )
                for lo, hi in blocks:
                    data[lo - addr : hi - addr] = bytes(hi - lo)
            sections[section.name] = (layout, data)
    return Layout(pcs, blocks, sections, words)


def check_policy_trace(directory, blocks, words, mode):
    actual = [[], []]
    jumps = [[], []]
    trace = directory / "m5out/commit.trace.gz"
    with gzip.open(trace, "rt") as stream:
        for line in stream:
            match = check.RETIRE.search(line)
            if not match:
                continue
            pc = int(match[1], 16)
            for i, (lo, hi) in enumerate(blocks):
                if lo <= pc < hi:
                    word = words[pc]
                    if word & 0xFFF == 0x06F:  # jal x0, target
                        jumps[i].append(pc)
                    else:
                        actual[i].append(word)
    for i, expected in enumerate(POLICY[mode]):
        check.require(
            actual[i] == list(expected),
            f"{mode}: unexpected retired {BLOCKS[i]} policy {actual[i]}",
        )
        check.require(
            len(jumps[i]) == 1,
            f"{mode}: expected one layout jump in {BLOCKS[i]}",
        )
    return jumps


def verify(directory):
    elfs = {mode: HERE / "build" / f"roi-{mode}.elf" for mode in ("sw", "hw")}
    layouts = {mode: read_layout(path, mode) for mode, path in elfs.items()}
    sw, hw = layouts["sw"], layouts["hw"]
    check.require(
        sw.addresses == hw.addresses and sw.blocks == hw.blocks,
        "Gate, code, data or ROI symbol addresses differ",
    )
    check.require(
        sw.sections.keys() == hw.sections.keys(),
        "Loadable section sets differ",
    )
    for name, data in sw.sections.items():
        check.require(
            data == hw.sections[name],
            f"ELFs differ outside the policy regions in {name}",
        )

    def short(mode):
        args = argparse.Namespace(
            mode="dasics-sw" if mode == "sw" else "protected",
            elf=elfs[mode],
            outdir=directory / mode,
        )
        check.run(args)
        layout = layouts[mode]
        return check_policy_trace(
            args.outdir, layout.blocks, layout.gate_words, mode
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        sw_jumps, hw_jumps = pool.map(short, ("sw", "hw"))
    check.require(
        sw_jumps == hw_jumps, "Modes retired layout jumps at different PCs"
    )
    return {
        "status": "PASS",
        "common_pcs": {name: hex(pc) for name, pc in sw.addresses.items()},
        "policy_regions": [[hex(lo), hex(hi)] for lo, hi in sw.blocks],
        "save_restore_jumps": [hex(item[0]) for item in sw_jumps],
        "calls_per_gate": 1,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, required=True)
    directory = parser.parse_args().outdir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    try:
        result = verify(directory)
    except Exception as error:
        (directory / "checks.json").write_text(
            json.dumps({"status": "FAIL", "error": str(error)}, indent=2)
            + "\n"
        )
        raise
    (directory / "checks.json").write_text(json.dumps(result, indent=2) + "\n")
    print("[OK] Both DASICS gates, register policies and aligned ELF layout")


if __name__ == "__main__":
    main()
