# SPDX-License-Identifier: BSD-3-Clause

"""Locate LEN_TRIM's entry, returns and statically resolved RV64 callers."""

import re
import subprocess

TARGET = "_gfortran_string_len_trim"


def discover(elf, prefix="riscv64-linux-gnu-", *, target=TARGET):
    """Return (entry PC, return PCs, {direct transfer PC: caller}, main PC)."""
    nm = subprocess.check_output(
        [prefix + "nm", "-n", "-S", "--defined-only", elf], text=True
    )
    symbols = {}
    for line in nm.splitlines():
        fields = line.split()
        if (
            len(fields) == 4
            and fields[2] in ("t", "T")
            and fields[3] in (target, "main")
        ):
            name = fields[3]
            if name in symbols:
                raise ValueError(f"Ambiguous {name} in {elf}")
            symbols[name] = (int(fields[0], 16), int(fields[1], 16))
    if target not in symbols or "main" not in symbols:
        raise ValueError(f"Missing {target} or main in {elf}")

    entry, size = symbols[target]
    listing = subprocess.check_output(
        [
            prefix + "objdump",
            "-d",
            "--prefix-addresses",
            "--show-raw-insn",
            "-M",
            "no-aliases",
            elf,
        ],
        text=True,
    )
    # Match the numerical destination, including direct tail jumps. Similar
    # symbols and branches to offsets inside the function have different PCs.
    jumps = re.compile(
        rf"^([0-9a-f]+) <([^>]+)> [0-9a-f]+\s+"
        rf"(?:jal\s+\w+,\s*|c\.j\s+)0*{entry:x}\b",
        re.MULTILINE,
    )
    sites = {
        int(pc, 16): re.sub(r"\+0x[0-9a-f]+$", "", caller)
        for pc, caller in jumps.findall(listing)
    }
    # RV64 ret is either jalr x0,0(ra) or compressed jr ra. Restrict
    # these exact encodings to the target's ELF symbol extent.
    rets = re.compile(
        r"^([0-9a-f]+) <[^>]+> (?:00008067\s+jalr|8082\s+c\.jr)\b",
        re.MULTILINE,
    )
    returns = sorted(
        pc
        for match in rets.findall(listing)
        if entry <= (pc := int(match, 16)) < entry + size
    )
    if not returns:
        raise ValueError(f"No return instruction inside {target} in {elf}")
    return entry, returns, dict(sorted(sites.items())), symbols["main"][0]
