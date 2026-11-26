# SPDX-License-Identifier: BSD-3-Clause
"""Check the paired DASICS printf gates before measuring the ROI."""

import argparse
import gzip
import json
from collections import Counter
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

# Architectural indices in ABI order. The integer and FP saved banks have the
# same indices; integer temporaries jump from x7 to x28, while ft0-ft6 span f0-f6.
SAVED = (8, 9, *range(18, 28))
INT_TEMP = (5, 6, 7, *range(28, 32))
FP_TEMP = tuple(range(7))
PROBE_STAGES = ("seed", "entry", "clobber", "restore_check")


def full_software_words():
    stores, loads = [], []
    # ra holds the frame base for sd/fsd and ld/fld.
    base = (1 << 15) | (3 << 12)
    for i, reg in enumerate(SAVED):
        for slot, store_opcode, load_opcode in (
            (40, 0x23, 0x03),
            (136, 0x27, 0x07),
        ):
            offset = slot + 8 * i
            stores.append(
                ((offset >> 5) << 25)
                | (reg << 20)
                | base
                | ((offset & 31) << 7)
                | store_opcode
            )
            loads.append((offset << 20) | base | (reg << 7) | load_opcode)
    zeros = [0x13 | reg << 7 for reg in SAVED]
    zeros += [0xF2000053 | reg << 7 for reg in SAVED]  # fmv.d.x fd,x0
    zeros += [0x13 | reg << 7 for reg in INT_TEMP]
    zeros += [0xF2000053 | reg << 7 for reg in FP_TEMP]
    return stores + zeros, loads


FULL_POLICY = {
    "sw": full_software_words(),
    "hw": (
        tuple(check.FULL_GATE_OPS.values())[:-1],
        (check.FULL_GATE_OPS["gate_leave"],),
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


def read_layout(
    path,
    mode,
    *,
    full=False,
    sentinels=False,
    common_symbols=COMMON,
    gate_name="run_printf",
):
    with path.open("rb") as stream:
        elf = ELFFile(stream)
        symbols = {
            sym.name: sym
            for sym in elf.get_section_by_name(".symtab").iter_symbols()
        }
        pcs = {name: symbols[name]["st_value"] for name in common_symbols}
        if full:
            pcs["gate_clr_f"] = symbols["gate_clr_f"]["st_value"]
        if sentinels:
            for stage in PROBE_STAGES:
                for suffix in ("start", "end"):
                    name = f"full_{stage}_{suffix}"
                    pcs[name] = symbols[name]["st_value"]
        blocks = [
            (
                symbols[f"{label}_start"]["st_value"],
                symbols[f"{label}_end"]["st_value"],
            )
            for label in BLOCKS
        ]
        gate = pcs[gate_name]
        gate_end = gate + symbols[gate_name]["st_size"]
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
                policy = FULL_POLICY if full else POLICY
                expected = (
                    [*policy["hw"][0], *policy["hw"][1]]
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


def sentinel_pcs(addresses, words):
    """Verify distinct register coverage in each functional probe region."""
    all_pcs = set()
    for stage in PROBE_STAGES:
        expected = [(bank, reg) for bank in ("x", "f") for reg in SAVED]
        if stage in ("seed", "entry"):
            expected.extend(("x", reg) for reg in INT_TEMP)
            expected.extend(("f", reg) for reg in FP_TEMP)
        reading = stage in ("entry", "restore_check")
        observed = []
        lo, hi = (addresses[f"full_{stage}_{s}"] for s in ("start", "end"))
        for pc in range(lo, hi, 4):
            all_pcs.add(pc)
            word = words[pc]
            rd, rs1 = (word >> 7) & 31, (word >> 15) & 31
            if reading:
                if word & 0x707F == 0x1063 and ("x", rs1) in expected:  # bne
                    observed.append(("x", rs1))
                elif word & 0xFFF0707F == 0xE2000053:  # fmv.x.d
                    observed.append(("f", rs1))
            elif (
                word & 0xFF07F == 0x13 and word >> 20 and ("x", rd) in expected
            ):
                observed.append(("x", rd))  # addi rd,x0,nonzero
            elif word & 0xFFF0707F == 0xF2000053 and rs1 != 0:  # fmv.d.x
                observed.append(("f", rd))
        check.require(
            Counter(observed) == Counter(expected),
            f"Wrong register coverage in {stage}",
        )
    return all_pcs


def check_policy_trace(
    directory, blocks, words, mode, *, full=False, probe_pcs=()
):
    actual = [[], []]
    jumps = [[], []]
    trace = directory / "m5out/commit.trace.gz"
    unseen = set(probe_pcs)
    with gzip.open(trace, "rt") as stream:
        for line in stream:
            match = check.RETIRE.search(line)
            if not match:
                continue
            pc = int(match[1], 16)
            unseen.discard(pc)
            for i, (lo, hi) in enumerate(blocks):
                if lo <= pc < hi:
                    word = words[pc]
                    if word & 0xFFF == 0x06F:  # jal x0, target
                        jumps[i].append(pc)
                    else:
                        actual[i].append(word)
    policy = FULL_POLICY if full else POLICY
    check.require(
        not unseen,
        f"{mode}: skipped {len(unseen)} functional probe instructions",
    )
    for i, expected in enumerate(policy[mode]):
        check.require(
            actual[i] == list(expected),
            f"{mode}: unexpected retired {BLOCKS[i]} policy {actual[i]}",
        )
        check.require(
            len(jumps[i]) == 1,
            f"{mode}: expected one layout jump in {BLOCKS[i]}",
        )
    return jumps


def check_pair(directory, prefix, full):
    elfs = {
        mode: HERE / "build" / f"{prefix}-{mode}.elf" for mode in ("sw", "hw")
    }
    sentinels = prefix == "full-check"
    layouts = {
        mode: read_layout(path, mode, full=full, sentinels=sentinels)
        for mode, path in elfs.items()
    }
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
        words = check.run(args, full=full)
        layout = layouts[mode]
        probe_pcs = sentinel_pcs(layout.addresses, words) if sentinels else ()
        return check_policy_trace(
            args.outdir,
            layout.blocks,
            layout.gate_words,
            mode,
            full=full,
            probe_pcs=probe_pcs,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        sw_jumps, hw_jumps = pool.map(short, ("sw", "hw"))
    check.require(
        sw_jumps == hw_jumps, "Modes retired layout jumps at different PCs"
    )
    evidence = {
        "status": "PASS",
        "common_pcs": {name: hex(pc) for name, pc in sw.addresses.items()},
        "policy_regions": [[hex(lo), hex(hi)] for lo, hi in sw.blocks],
        "save_restore_jumps": [hex(item[0]) for item in sw_jumps],
        "calls_per_gate": 1,
    }
    # Compare the actual words, including the layout jump and skipped padding,
    # when the register-sentinel and measured guests have different text sizes.
    policies = {
        mode: tuple(
            tuple(layout.gate_words[pc] for pc in range(lo, hi, 4))
            for lo, hi in layout.blocks
        )
        for mode, layout in layouts.items()
    }
    return evidence, policies


def verify(directory, *, full=False):
    if not full:
        result, _ = check_pair(directory, "roi", False)
        return result
    sentinels, checked_policy = check_pair(
        directory / "sentinels", "full-check", True
    )
    timed, timed_policy = check_pair(directory / "timed", "full", True)
    check.require(
        checked_policy == timed_policy,
        "Sentinel and timed guests use different register policies",
    )
    return {
        "status": "PASS",
        "entry_registers_checked": 38,
        "restored_registers_checked": 24,
        "sentinels": sentinels,
        "timed": timed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Check all 24 saved registers and 14 temporaries",
    )
    args = parser.parse_args()
    directory = args.outdir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    try:
        result = verify(directory, full=args.full)
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
