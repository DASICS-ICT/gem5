# SPDX-License-Identifier: BSD-3-Clause
"""Find the retired control transfers and strtok's argument discriminator."""

import re
import subprocess

READLINE = "_ZN6soplex8MPSInput8readLineEv"
LINE = re.compile(r"^([0-9a-f]+) <(.+)> ([0-9a-f]{4,8})\s+(\S+)(?:\s+(.*))?$")


def transfer(pc, word, op, args, previous):
    """Resolve JAL, C.J and adjacent AUIPC/JALR pairs at the jump PC."""
    if op in ("jal", "c.j"):
        # GNU objdump prints the resolved address as the last operand.
        operands = args.partition("<")[0].strip()
        return int(operands.rsplit(",", 1)[-1], 16)
    if word & 0x707F == 0x67 and previous is not None:
        addr, auipc = previous
        base = word >> 15 & 31
        if (
            addr + 4 == pc
            and auipc & 0x7F == 0x17
            and base
            and (auipc >> 7 & 31) == base
        ):
            hi = (auipc & 0xFFFFF000) - ((auipc >> 31) << 32)
            lo = (word >> 20) - ((word >> 31) << 12)
            return (addr + hi + lo) & ~1
    return None


def discover(elf, prefix="riscv64-linux-gnu-"):
    """Return named probe addresses and all resolved public strtok call sites."""
    nm = subprocess.check_output(
        [prefix + "nm", "-n", "-S", "--defined-only", elf], text=True
    )
    wanted = {"strtok", "__strtok_r", "strtok_r", "main", READLINE}
    symbols = {}
    for line in nm.splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[3] in wanted:
            if fields[3] in symbols:
                raise ValueError(f"Ambiguous symbol {fields[3]}")
            symbols[fields[3]] = (int(fields[0], 16), int(fields[1], 16))
    if (
        wanted != symbols.keys()
        or symbols["strtok_r"] != symbols["__strtok_r"]
    ):
        raise ValueError("Missing or incompatible SoPlex/glibc symbols")
    entry, wrapper_size = symbols["strtok"]
    helper, helper_size = symbols["__strtok_r"]
    sites = {}
    other = {}
    tails = []
    body = {}
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
    previous = None
    for line in listing.splitlines():
        match = LINE.match(line)
        if not match:
            previous = None
            continue
        addr, symbol, raw, op, args = match.groups()
        pc, word = int(addr, 16), int(raw, 16)
        if op in ("jal", "jalr", "c.j"):
            dest = transfer(pc, word, op, args, previous)
            if dest == entry:
                sites[pc] = re.sub(r"\+0x[0-9a-f]+$", "", symbol)
            elif dest == helper:
                if entry <= pc < entry + wrapper_size:
                    tails.append(pc)
                else:
                    other[f"other_{pc:x}"] = pc
        if helper <= pc < helper + helper_size:
            body[pc] = (word, op, args)
        previous = (pc, word)
    # This glibc tests the original a0 exactly once and loads *saveptr
    # only on the taken NULL path. The fall-through is also the join PC.
    branches = [
        (pc, int(args.split(",")[1].split()[0], 16))
        for pc, (_, op, args) in body.items()
        if op == "c.beqz" and args.startswith("a0,")
    ]
    returns = [
        pc for pc, (word, _, _) in body.items() if word in (0x8082, 0x00008067)
    ]
    if len(tails) != 1 or len(branches) != 1 or len(returns) != 1 or not sites:
        raise ValueError("Unexpected strtok wrapper or helper control flow")
    branch, null_pc = branches[0]
    _, load_op, load_args = body[null_pc]
    _, jump_op, jump_args = body[null_pc + 2]
    if (
        load_op != "c.ld"
        or not load_args.endswith(",0(a2)")
        or jump_op != "c.j"
        or int(jump_args.split()[0], 16) != branch + 2
    ):
        raise ValueError(
            "NULL discriminator does not load and rejoin the caller's saved cursor"
        )
    targets = dict(
        main=symbols["main"][0],
        readline=symbols[READLINE][0],
        strtok=entry,
        tail=tails[0],
        helper=helper,
        null_path=null_pc,
        helper_ret=returns[0],
    )
    targets.update({f"site_{pc:x}": pc for pc in sites})
    targets.update(other)
    if len(targets) != len(set(targets.values())):
        raise ValueError("Overlapping PC markers")
    return targets, sites
