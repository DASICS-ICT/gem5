# SPDX-License-Identifier: BSD-3-Clause
"""Compare the linked code and data used by the two fmod gate variants."""

import argparse
import os
import re
import subprocess
from pathlib import Path


def binutils(tool, *args):
    prefix = os.environ.get("CROSS_COMPILE", "riscv64-linux-gnu-")
    return subprocess.check_output([prefix + tool, *args], text=True)


def symbols(elf):
    result = {}
    for line in binutils("nm", "-n", "--defined-only", elf).splitlines():
        fields = line.split()
        if len(fields) == 3:
            result[fields[2]] = int(fields[0], 16)
    return result


def call_sites(elf, caller):
    text = binutils("objdump", "-d", "--disassemble=" + caller, elf)
    sites = []
    for address, word in re.findall(
        r"^\s*([0-9a-f]+):\s+([0-9a-f]+)\s+jalr?\s+.*<dasics_fmod_gate>$",
        text,
        re.M,
    ):
        pc = int(address, 16)
        sites.append((pc, pc + len(word) // 2))
    if not sites:
        raise ValueError(
            f"No calls from {caller} to dasics_fmod_gate in {elf}"
        )
    return sites


def image(elf, names):
    raw = elf.read_bytes()
    start = names["dasics_fmod_gate"]
    end = names["dasics_fmod_gate_slot_end"]
    if not start <= names["dasics_fmod_ret"] <= end - 4:
        raise ValueError(f"Final return outside the gate slot in {elf}")
    sections = {}
    found_gate = False
    for line in binutils("objdump", "-wh", elf).splitlines():
        if "ALLOC" not in line:
            continue
        _, name, size, vma, lma, offset, alignment, flags = line.split(None, 7)
        size, vma, offset = (int(s, 16) for s in (size, vma, offset))
        data = b""
        if "CONTENTS" in flags and name != ".note.gnu.build-id":
            data = raw[offset : offset + size]
            if vma <= start < end <= vma + size and "CODE" in flags:
                ret = names["dasics_fmod_ret"] - vma
                if data[ret : ret + 4] != bytes.fromhex("67800000") or any(
                    data[ret + 4 : end - vma]
                ):
                    raise ValueError(f"Expected ret then zero fill in {elf}")
                data = data[: start - vma] + data[end - vma :]
                found_gate = True
        sections[name] = (vma, size, lma, alignment, flags, data)
    if not found_gate:
        raise ValueError(f"Gate slot outside loaded code in {elf}")

    # The helpers load the address of their private table from this GOT slot.
    addr, _, _, _, _, got = sections[".got"]
    ptr = names["dasics_fmod_table"].to_bytes(8, "little")
    slots = [addr + i for i in range(0, len(got), 8) if got[i : i + 8] == ptr]
    if len(slots) != 1:
        raise ValueError(f"Expected one private fmod table pointer in {elf}")
    return sections, slots[0]


def compare(sw, gf):
    left, right = symbols(sw), symbols(gf)
    for name in (
        "main",
        "Drand_setSeed",
        "Drand_value",
        "dasics_fmod_gate",
        "dasics_fmod_gate_slot_end",
        "dasics_fmod_body",
        "dasics_fmod_clz",
        "dasics_fmod_ctz",
        "dasics_fmod_error",
        "dasics_fmod_table",
        "__dasics_context_base",
        "__dasics_stack_bottom",
        "__dasics_stack_top",
    ):
        a, b = left[name], right[name]
        if a != b:
            raise ValueError(f"{name}: SW {a:#x}, G+F {b:#x}")
        print(f"{name}: {a:#x}")
    for caller in ("Drand_setSeed", "Drand_value"):
        a, b = call_sites(sw, caller), call_sites(gf, caller)
        if a != b:
            raise ValueError(f"Call or return addresses differ in {caller}")
        for call, resume in a:
            print(f"{caller} call {call:#x}, resume {resume:#x}")

    first, ptr1 = image(sw, left)
    second, ptr2 = image(gf, right)
    if ptr1 != ptr2:
        raise ValueError(f"Table GOT slot: SW {ptr1:#x}, G+F {ptr2:#x}")
    print(f"Private table GOT slot: {ptr1:#x}")
    for name in sorted(first.keys() | second.keys()):
        if first.get(name) != second.get(name):
            raise ValueError(f"Allocated section differs outside gate: {name}")
    print("[OK] Matched allocated sections outside gate and build-ID payload")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sw", type=Path)
    parser.add_argument("gf", type=Path)
    args = parser.parse_args()
    try:
        compare(args.sw, args.gf)
    except (
        OSError,
        KeyError,
        ValueError,
        subprocess.CalledProcessError,
    ) as err:
        parser.exit(1, f"[FAIL] {err}\n")
