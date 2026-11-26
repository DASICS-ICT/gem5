# SPDX-License-Identifier: BSD-3-Clause
"""Copy the RV64 glibc objects used by the fixed decimal printf into domain B."""

import argparse
import struct
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from elftools.elf.constants import SH_FLAGS
from elftools.elf.elffile import ELFFile

# These are original archive members, including the stdio registration tables
# whose initial (empty) state is local to this copy of printf.
MEMBERS = """
printf.o vfprintf-internal.o printf_buffer_to_file.o printf_buffer_write.o
printf_buffer_putc_1.o printf_buffer_puts_1.o printf_buffer_done.o
printf_buffer_flush.o printf_buffer_pad_1.o _itoa.o itoa-digits.o
itoa-udigits.o memcpy.o mempcpy.o memset.o strchrnul.o strlen.o strnlen.o
reg-printf.o reg-modifier.o reg-type.o single_threaded.o xlocale.o
""".split()

GOT_HI20 = 20
TLS_GOT_HI20 = 21
PCREL_HI20 = 23

# These initial-exec TLS references use the dedicated single-thread B
# block defined by the linker script. The process keeps its own libc TLS.
TLS_OFFSETS = {"__libc_errno": 0, "__libc_tsd_LOCALE": 8}


def got_relocations(elf):
    for section in elf.iter_sections():
        if section.header.sh_type != "SHT_RELA":
            continue
        symbols = elf.get_section(section.header.sh_link)
        for i, rel in enumerate(section.iter_relocations()):
            kind = rel["r_info_type"]
            if kind in (GOT_HI20, TLS_GOT_HI20):
                target = symbols.get_symbol(rel["r_info_sym"]).name
                if kind == TLS_GOT_HI20 and target not in TLS_OFFSETS:
                    continue
                if not target or rel["r_addend"]:
                    raise ValueError(
                        "Unsupported anonymous or offset GOT reference"
                    )
                yield section, i, target


def build(prefix, archive, destination, tmp):
    def run(tool, *args):
        subprocess.run([prefix + tool, *args], cwd=tmp, check=True)

    run("ar", "x", archive, *MEMBERS)
    run("ld", "-r", "-o", "members.o", *MEMBERS)
    with (tmp / "members.o").open("rb") as src:
        elf = ELFFile(src)
        renames = {
            sym.name: "b_" + sym.name
            for sym in elf.get_section_by_name(".symtab").iter_symbols()
            if sym.name
            and sym["st_shndx"] != "SHN_UNDEF"
            and sym["st_info"]["bind"] in ("STB_GLOBAL", "STB_WEAK")
        }
    renames.update(stdout="b_stdout", __stack_chk_guard="b_stack_guard")
    (tmp / "renames").write_text(
        "".join(f"{old} {new}\n" for old, new in sorted(renames.items()))
    )
    run("objcopy", "--redefine-syms=renames", "members.o", "private.o")

    # Give ordinary GOT references their own read-only slots. A paired
    # AUIPC/LD then loads the same real symbol address without sharing A's GOT.
    with (tmp / "private.o").open("rb") as src:
        targets = sorted(
            {name for _, _, name in got_relocations(ELFFile(src))}
        )
    slots = {name: f"b_printf_got_{i}" for i, name in enumerate(targets)}
    (tmp / "slots.S").write_text(
        '.section .dasics.printf.got,"a",@progbits\n.balign 8\n'
        + "".join(
            f".globl {slot}\n.hidden {slot}\n{slot}: .dword "
            + str(TLS_OFFSETS.get(name, name))
            + "\n"
            for name, slot in slots.items()
        )
        + '.section .note.GNU-stack,"",@progbits\n'
    )
    run("as", "-o", "slots.o", "slots.S")
    run("ld", "-r", "-o", "private-slots.o", "private.o", "slots.o")
    merged = tmp / "private-slots.o"
    with merged.open("rb") as src:
        elf = ELFFile(src)
        if (
            elf.elfclass != 64
            or not elf.little_endian
            or elf["e_machine"] != "EM_RISCV"
        ):
            raise ValueError("Expected little-endian ELF64 RISC-V")
        indexes = {
            s.name: i
            for i, s in enumerate(
                elf.get_section_by_name(".symtab").iter_symbols()
            )
        }
        replacements = [
            (
                section["sh_offset"] + i * section["sh_entsize"] + 8,
                (indexes[slots[target]] << 32) | PCREL_HI20,
            )
            for section, i, target in got_relocations(elf)
        ]
        sections = []
        for sec in elf.iter_sections():
            name = sec.name
            if (
                not sec["sh_flags"] & SH_FLAGS.SHF_ALLOC
                or not sec["sh_size"]
                or name == ".dasics.printf.got"
            ):
                continue
            if sec["sh_flags"] & SH_FLAGS.SHF_TLS:
                raise ValueError(f"Unexpected TLS definition in B: {name}")
            if sec["sh_flags"] & SH_FLAGS.SHF_EXECINSTR:
                group = "text"
            elif not sec["sh_flags"] & SH_FLAGS.SHF_WRITE or name.startswith(
                ".data.rel.ro"
            ):
                group = "ro"
            else:
                group = "data"
            sections.extend(
                [
                    "--rename-section",
                    f"{name}=.dasics.printf.lib.{group}{name}",
                ]
            )
    with merged.open("r+b") as out:
        for offset, info in replacements:
            out.seek(offset)
            out.write(struct.pack("<Q", info))
    run("objcopy", *sections, merged, destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix")
    parser.add_argument("libc", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with TemporaryDirectory(dir=args.output.parent) as temporary:
        build(
            args.prefix,
            args.libc.resolve(),
            args.output.resolve(),
            Path(temporary),
        )
