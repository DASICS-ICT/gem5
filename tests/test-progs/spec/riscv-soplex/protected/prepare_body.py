# SPDX-License-Identifier: BSD-3-Clause
"""Isolate the RV64 glibc strtok call chain and its persistent cursor."""

import argparse
import struct
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from elftools.elf.elffile import ELFFile

MEMBERS = ("strtok.o", "strtok_r.o", "strspn.o", "strcspn.o", "strchrnul.o")
GOT_HI20 = 20
PCREL_HI20 = 23


def isolate_guard(path):
    # The following LD still loads a pointer. Retarget each AUIPC to a
    # private pointer slot containing the address of B's own canary.
    with path.open("r+b") as stream:
        elf = ELFFile(stream)
        if (elf.elfclass, elf.little_endian, elf["e_machine"]) != (
            64,
            True,
            "EM_RISCV",
        ):
            raise ValueError("Expected a little-endian RV64 glibc archive")
        symbols = elf.get_section_by_name(".symtab")
        undefined = {
            s.name
            for s in symbols.iter_symbols()
            if s.name and s["st_shndx"] == "SHN_UNDEF"
        }
        if undefined != {"__stack_chk_guard", "__stack_chk_fail"}:
            raise ValueError(f"Unexpected strtok dependencies: {undefined}")
        (cursor,) = symbols.get_symbol_by_name("olds.0")
        bss = elf.get_section(cursor["st_shndx"])
        if bss.name != ".bss" or cursor["st_size"] != 8 or bss["sh_size"] != 8:
            raise ValueError("Expected one private 8-byte glibc cursor")
        relocs = elf.get_section_by_name(".rela.text")
        guards = []
        for i, rel in enumerate(relocs.iter_relocations()):
            if rel["r_info_type"] == GOT_HI20:
                name = symbols.get_symbol(rel["r_info_sym"]).name
                if name != "__stack_chk_guard" or rel["r_addend"]:
                    raise ValueError(f"Unexpected B GOT reference: {name}")
                guards.append((i, rel["r_info_sym"]))
        if len(guards) != 2:
            raise ValueError("Expected one guard reference per span function")
        for index, symbol in guards:
            # Elf64_Rela.r_info follows the 8-byte relocation address.
            stream.seek(relocs["sh_offset"] + index * relocs["sh_entsize"] + 8)
            stream.write(struct.pack("<Q", symbol << 32 | PCREL_HI20))


def build(prefix, archive, destination, temporary):
    def run(tool, *args):
        subprocess.run([prefix + tool, *args], cwd=temporary, check=True)

    run("ar", "x", archive, *MEMBERS)
    run("ld", "-r", "-o", "lib.o", *MEMBERS)
    isolate_guard(temporary / "lib.o")
    renames = [
        "--redefine-sym=" + symbol + "=b_" + symbol
        for symbol in (
            "strtok",
            "__strtok_r",
            "strtok_r",
            "strspn",
            "strcspn",
            "__strchrnul",
            "strchrnul",
        )
    ]
    run(
        "objcopy",
        *renames,
        "--redefine-sym=__stack_chk_guard=b_strtok_guard_slot",
        "--redefine-sym=__stack_chk_fail=b_strtok_stack_fail",
        "--redefine-sym=olds.0=b_strtok_cursor",
        "--globalize-symbol=b_strtok_cursor",
        "--rename-section=.bss=.dasics.strtok.cursor",
        "--rename-section=.text=.dasics.strtok.text",
        "lib.o",
        "private.o",
    )
    support = Path(__file__).resolve().with_name("body_support.c")
    run(
        "gcc",
        "-march=rv64gc",
        "-mabi=lp64d",
        "-O2",
        "-c",
        support,
        "-o",
        "support.o",
    )
    run("ld", "-r", "-o", destination, "private.o", "support.o")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix")
    parser.add_argument("libc", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(dir=args.output.parent) as tmp:
        build(
            args.prefix, args.libc.resolve(), args.output.resolve(), Path(tmp)
        )
