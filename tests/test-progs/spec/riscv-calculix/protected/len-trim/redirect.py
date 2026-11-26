# SPDX-License-Identifier: BSD-3-Clause
"""Retarget the observed one-character call in a private getnewline.o."""

import argparse
import struct
from pathlib import Path

from elftools.elf.elffile import ELFFile

TARGET = "_gfortran_string_len_trim"
# These offsets identify the three getnewline_ sites in the ordinary objects
# used for the beampic count. Only the first site maps to ordinary PC 0xb4108.
HOT_SITE = 0x124
SITES = (HOT_SITE, 0x2C4, 0x366)
R_RISCV_CALL = 18
R_RISCV_CALL_PLT = 19


def redirect(source, destination):
    with source.open("rb") as stream:
        elf = ELFFile(stream)
        if (
            elf.header.e_type != "ET_REL"
            or elf.header.e_machine != "EM_RISCV"
            or not elf.little_endian
            or elf.elfclass != 64
        ):
            raise ValueError("Expected an RV64 little-endian object")
        text = elf.get_section_by_name(".text")
        relocations = elf.get_section_by_name(".rela.text")
        symbols = elf.get_section(relocations["sh_link"])
        (caller,) = symbols.get_symbol_by_name("getnewline_")
        base = caller["st_value"]
        if elf.get_section(caller["st_shndx"]).name != ".text":
            raise ValueError("getnewline_ is outside .text")
        gates = [
            i
            for i, symbol in enumerate(symbols.iter_symbols())
            if symbol.name == "trim_gate" and symbol["st_shndx"] == "SHN_UNDEF"
        ]
        if len(gates) != 1:
            raise ValueError("Expected one undefined trim_gate from ld -u")
        sites = {}
        for i, r in enumerate(relocations.iter_relocations()):
            if symbols.get_symbol(r["r_info_sym"]).name == TARGET:
                if (
                    r["r_info_type"] not in (R_RISCV_CALL, R_RISCV_CALL_PLT)
                    or r["r_addend"]
                ):
                    raise ValueError("Unexpected LEN_TRIM call relocation")
                sites[r["r_offset"] - base] = (i, r["r_info_type"])
        if tuple(sorted(sites)) != SITES:
            raise ValueError(
                f"Unexpected LEN_TRIM sites in getnewline_: {sorted(sites)}"
            )
        # c.ldsp a1,8(sp); c.li a0,1; auipc ra,0; jalr ra,ra,0
        wanted = bytes.fromhex("a265054597000000e7800000")
        if text.data()[base + HOT_SITE - 4 : base + HOT_SITE + 8] != wanted:
            raise ValueError(
                "Unexpected argument setup or call at the selected site"
            )
        i, kind = sites[HOT_SITE]
        # ELF64 little-endian Rela: r_offset, r_info, r_addend. Keep the
        # paired RELAX and both sibling calls unchanged for the final link.
        position = relocations["sh_offset"] + i * relocations["sh_entsize"] + 8
        stream.seek(0)
        result = bytearray(stream.read())
    struct.pack_into("<Q", result, position, (gates[0] << 32) | kind)
    destination.write_bytes(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    redirect(args.source, args.destination)
