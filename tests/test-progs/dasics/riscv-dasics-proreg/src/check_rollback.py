# SPDX-License-Identifier: BSD-3-Clause
"""Run the single-hart O3 probe and verify the loop-exit rename history."""

import argparse
import gzip
import re
import subprocess
import sys
from pathlib import Path


def check_trace(nm, elf, trace):
    symbols = {}
    for row in subprocess.check_output(
        [nm, "-n", elf], text=True
    ).splitlines():
        fields = row.split()
        if len(fields) == 3 and fields[2].startswith("generation_"):
            symbols[fields[2]] = int(fields[0], 16)

    # A PC can occur on both paths. Identify individual instructions by SN.
    pcs = {}
    allowed = set()
    exit_branches = set()
    retired_leaves = set()
    rollbacks = {}
    mispredict = boundary = None
    pc_pattern = r"\((0x[0-9a-f]+)=>"
    with gzip.open(trace, "rt") as stream:
        for line in stream:
            if "[tid:0]" not in line:
                continue
            if "Processing instruction [sn:" in line:
                match = re.search(r"\[sn:(\d+)\] with PC " + pc_pattern, line)
                pcs[int(match[1])] = int(match[2], 16)
            elif "rename access: allowed" in line:
                allowed.add(int(re.search(r"\[sn:(\d+)\]", line)[1]))
            elif "Squashing due to branch mispred PC:" in line:
                match = re.search(r"PC:(0x[0-9a-f]+) \[sn:(\d+)\]", line)
                mispredict = int(match[2])
                if int(match[1], 16) != symbols["generation_branch"]:
                    mispredict = None
            elif "Redirecting to PC" in line:
                dest = int(re.search(pc_pattern, line)[1], 16)
                if (
                    mispredict is not None
                    and dest == symbols["generation_exit"]
                ):
                    exit_branches.add(mispredict)
                mispredict = None
            elif "Squashing instructions." in line:
                boundary = int(re.search(r"\[squash sn:(\d+)\]", line)[1])
                if boundary in exit_branches:
                    rollbacks[boundary] = []
            elif boundary in rollbacks and "Removing history entry" in line:
                # Only x19 (s3) changes ownership in this loop.
                match = re.search(
                    r"number (\d+) \(archReg: 19, newPhysReg: (\d+), "
                    r"prevPhysReg: (\d+)\)",
                    line,
                )
                if match:
                    rollbacks[boundary].append(tuple(map(int, match.groups())))
            elif "Retiring rename of reg" in line:
                sn = int(re.search(r"\[sn:(\d+)\]", line)[1])
                if pcs.get(sn) == symbols["generation_final_leave"]:
                    retired_leaves.add(sn)

    expected_pcs = [
        symbols["generation_" + name] for name in ("leave", "write", "proreg")
    ]
    for branch, rows in rollbacks.items():
        speculative = sorted(sn for sn in pcs if sn > branch)[:3]
        if [pcs[sn] for sn in speculative] != expected_pcs:
            continue
        # Match these exact instructions within one youngest-first rollback.
        changes = [row for row in reversed(rows) if row[0] in speculative]
        if [row[0] for row in changes] != speculative:
            continue
        (
            (leave, caller, local),
            (_, fresh, previous),
            (protect, saved, same),
        ) = changes
        if (
            {leave, protect} <= allowed
            and previous == caller
            and saved == same == fresh
            and len({caller, local, fresh}) == 3
            and any(sn > protect for sn in retired_leaves & allowed)
        ):
            print(
                f"Loop-exit squash sn={branch}: caller P{caller}, "
                f"local P{local}, discarded P{fresh}"
            )
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nm")
    parser.add_argument("gem5")
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("config")
    parser.add_argument("elf")
    args = parser.parse_args()
    trace = args.outdir / "rollback.trace.gz"
    trace.unlink(missing_ok=True)
    result = subprocess.run(
        [
            args.gem5,
            f"--outdir={args.outdir}",
            "--debug-flags=Rename,Commit",
            f"--debug-file={trace.name}",
            args.config,
            args.elf,
        ]
    )
    if result.returncode:
        return (
            result.returncode
            if result.returncode > 0
            else 128 - result.returncode
        )
    if check_trace(args.nm, args.elf, trace):
        return 0
    print("Missing loop-exit rollback coverage", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
