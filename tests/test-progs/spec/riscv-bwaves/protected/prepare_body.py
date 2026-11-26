# SPDX-License-Identifier: BSD-3-Clause
"""Place libm's RV64 pow implementation and its lookup tables inside B."""

import argparse
import struct
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from elftools.elf.elffile import ELFFile

POINTERS = {
    "__stack_chk_guard": "b_pow_guard_slot",
    "__pow_log_data": "b_pow_log_slot",
    "__exp_data": "b_pow_exp_slot",
}
MATH_ERRORS = {
    "__math_oflow",
    "__math_check_uflow",
    "__math_invalid",
    "__math_divzero",
    "__math_check_oflow",
    "__math_uflow",
}
CALL_PLT, GOT_HI20, PCREL_HI20, PCREL_LO12_I, RELAX = 19, 20, 23, 24, 51


def isolate_relocations(path):
    """Preserve pow's pointer loads and keep all exceptional exits in B."""
    with path.open("r+b") as stream:
        elf = ELFFile(stream)
        if (elf.elfclass, elf.little_endian, elf["e_machine"]) != (
            64,
            True,
            "EM_RISCV",
        ):
            raise ValueError("Expected a little-endian RV64 libm archive")
        symbols = elf.get_section_by_name(".symtab")
        undefined = {
            sym.name: i
            for i, sym in enumerate(symbols.iter_symbols())
            if sym.name and sym["st_shndx"] == "SHN_UNDEF"
        }
        if undefined.keys() != (
            POINTERS.keys() | MATH_ERRORS | {"__stack_chk_fail"}
        ):
            raise ValueError(
                f"Unexpected pow dependencies: {undefined.keys()}"
            )
        relocations = elf.get_section_by_name(".rela.text")
        entries = list(relocations.iter_relocations())
        # B clears gp on entry. PC-relative constant loads must retain
        # their AUIPC even if the final link places some constants near gp.
        addresses = {
            rel["r_offset"]
            for rel in entries
            if rel["r_info_type"] in (GOT_HI20, PCREL_HI20, PCREL_LO12_I)
        }
        loaded = []
        for i, rel in enumerate(entries):
            kind = rel["r_info_type"]
            symbol = rel["r_info_sym"]
            name = symbols.get_symbol(symbol).name
            if kind == GOT_HI20:
                if name not in POINTERS or rel["r_addend"]:
                    raise ValueError(f"Unexpected pow GOT reference: {name}")
                # The following LD reads a dedicated pointer slot instead
                # of exposing part of the application's GOT to B.
                loaded.append(name)
                kind = PCREL_HI20
            elif name in MATH_ERRORS:
                if kind != CALL_PLT or rel["r_addend"]:
                    raise ValueError(f"Unexpected pow error transfer: {name}")
                symbol = undefined["__stack_chk_fail"]
            elif kind == RELAX and rel["r_offset"] in addresses:
                symbol, kind = 0, 0
            else:
                continue
            # Elf64_Rela.r_info follows the 8-byte relocation offset.
            stream.seek(
                relocations["sh_offset"] + i * relocations["sh_entsize"] + 8
            )
            stream.write(struct.pack("<Q", (symbol << 32) | kind))
        if sorted(loaded) != sorted(POINTERS):
            raise ValueError(f"Unexpected set of pow pointer loads: {loaded}")


def build(prefix, libm, output):
    with TemporaryDirectory(dir=output.parent) as tmp:

        def run(tool, *args):
            subprocess.run([prefix + tool, *args], cwd=tmp, check=True)

        run("ar", "x", libm, "e_pow.o", "e_pow_log_data.o", "e_exp_data.o")
        isolate_relocations(Path(tmp) / "e_pow.o")
        names = dict(POINTERS, __pow="b_pow", __stack_chk_fail="b_pow_error")
        strip = MATH_ERRORS | {"__ieee754_pow", "pow", "powf32x", "powf64"}
        run(
            "objcopy",
            *(f"--redefine-sym={k}={v}" for k, v in names.items()),
            *(f"--strip-symbol={s}" for s in sorted(strip)),
            "--rename-section=.text=.dasics.pow.text",
            "--rename-section=.rodata.cst8=.dasics.pow.literals",
            "e_pow.o",
            "private.o",
        )
        for member, symbol, table in (
            ("e_pow_log_data.o", "__pow_log_data", "log"),
            ("e_exp_data.o", "__exp_data", "exp"),
        ):
            run(
                "objcopy",
                f"--redefine-sym={symbol}=b_pow_{table}_table",
                "--rename-section=.rodata=.dasics.pow.tables",
                member,
                f"{table}.o",
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
        run(
            "ld",
            "-r",
            "-o",
            output,
            "private.o",
            "log.o",
            "exp.o",
            "support.o",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix")
    parser.add_argument("libm", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.prefix, args.libm.resolve(), args.output.resolve())
