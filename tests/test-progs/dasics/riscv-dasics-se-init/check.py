# SPDX-License-Identifier: BSD-3-Clause
"""Check one v5_full SE initialization case against its expected outcome."""

import argparse
import re
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "case",
        choices=(
            "trusted",
            "untrusted",
            "missing-context",
            "overlap",
            "ordinary",
        ),
    )
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--gem5", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--nm", required=True)
    args = parser.parse_args()

    case = args.case
    elf = args.build / "se-init.elf"
    guest_args = []
    if case == "untrusted":
        guest_args = ["deny"]
        symbols = subprocess.check_output([args.nm, "-n", elf], text=True)
        pc = re.search(r"^([0-9a-f]+) T untrusted_proreg$", symbols, re.M)
        if pc is None:
            parser.error(f"untrusted_proreg missing from {elf}")
        # The upper bits of ExtMachInst carry RISC-V decoder state.
        pattern = (
            rf"Illegal instruction 0x[0-9a-f]*0080300b at pc "
            rf"\({int(pc[1], 16):#x}=>[^\n]*?: Instruction requires trusted "
            r"execution in an enabled non-virtualized U/S domain"
        )
    elif case in ("missing-context", "overlap"):
        elf = args.build / f"{case}.elf"
        pattern = (
            "Missing DASICS ELF symbol __dasics_context_base"
            if case == "missing-context"
            else "Overlapping DASICS code ranges"
        )
    else:
        guest_code = 2 if case == "ordinary" else 0
        pattern = (
            rf"because exiting with last active thread context\. "
            rf"Guest exit code: {guest_code}$"
        )

    directory = (args.outdir / case).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    log = directory / "gem5.log"
    command = [
        args.gem5.resolve(),
        "--listener-mode=off",
        f"--outdir={directory}",
        args.config.resolve(),
        "--workdir",
        directory,
        "--stdout",
        directory / "guest.out",
        "--stderr",
        directory / "guest.err",
        elf.resolve(),
        *guest_args,
    ]
    with log.open("w") as stream:
        result = subprocess.run(
            command, stdout=stream, stderr=subprocess.STDOUT, timeout=120
        )
    if (result.returncode == 0) != (case == "trusted") or not re.search(
        pattern, log.read_text(), re.M
    ):
        raise SystemExit(
            f"[FAIL] {case}: gem5 exit {result.returncode}; {log}"
        )
    print(f"[OK] {case}")


if __name__ == "__main__":
    main()
